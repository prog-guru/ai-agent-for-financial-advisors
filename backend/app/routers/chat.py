# app/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
import openai
import os
import logging
import json

from ..db import get_db, get_settings
from ..models import Message, Meeting, User
from ..schemas import MessageOut, MessageIn, MeetingOut, ChatSendResponse
from ..security import verify_session_jwt
from ..services.rag import rag_service
from ..services.data_sync import data_sync_service
from ..services.agent import agent_service

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("chat")

# Initialize OpenAI client

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Get current user from session cookie"""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_data = verify_session_jwt(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    user = db.query(User).filter(User.sub == user_data["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

@router.get("/messages", response_model=List[MessageOut])
async def get_messages(request: Request, db: Session = Depends(get_db)):
    """Get messages for the current user only"""
    user = await get_current_user(request, db)
    
    rows = db.query(Message).filter(Message.user_id == user.id).order_by(Message.created_at.asc(), Message.id.asc()).all()
    return [
        MessageOut(id=r.id, role=r.role, content=r.content, created_at=r.created_at) for r in rows
    ]

def _meeting_to_out(m: Meeting) -> MeetingOut:
    return MeetingOut(
        id=m.id, title=m.title, start_iso=m.start_iso, end_iso=m.end_iso, attendees=m.attendees
    )

async def generate_ai_response_with_rag(user_message: str, user_meetings: List[Meeting], rag_context: str, db: Session) -> str:
    """Generate AI response using OpenAI"""
    try:
        # Prepare context from user's meetings
        meeting_context = ""
        if user_meetings:
            meeting_context = "User's upcoming meetings:\n"
            for meeting in user_meetings[:5]:  # Limit to 5 most recent meetings
                meeting_context += f"- {meeting.title} ({meeting.start_iso})\n"
        
        # Prepare conversation history
        recent_messages = db.query(Message).filter(
            Message.user_id == user_meetings[0].user_id if user_meetings else None
        ).order_by(Message.created_at.desc()).limit(10).all()
        
        conversation_history = ""
        for msg in reversed(recent_messages[-5:]):  # Last 5 messages
            role = "User" if msg.role == "user" else "Assistant"
            conversation_history += f"{role}: {msg.content}\n"
        
        system_prompt = f"""You are a helpful AI assistant that helps users manage their meetings and schedule.
        {meeting_context}
        
        Previous conversation:
        {conversation_history}
        
        Additional context from user's emails and CRM data:
        {rag_context}
        
        IMPORTANT: Use the email context above to answer questions about people, conversations, and details from emails.
        If the context contains relevant information, use it in your response.
        Keep responses concise but informative."""
        
        client = openai.OpenAI(api_key=get_settings().OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        # Fallback responses based on message content
        if any(word in user_message.lower() for word in ['meeting', 'schedule', 'calendar']):
            return "I can help you with your meetings! You can ask me about your schedule or specific meetings."
        elif any(word in user_message.lower() for word in ['hello', 'hi', 'hey']):
            return "Hello! I'm your AI assistant. How can I help you with your meetings today?"
        else:
            return "Thanks for your message! I'm here to help you manage your meetings and schedule."

@router.post("/messages", response_model=ChatSendResponse)
async def send_message(payload: MessageIn, request: Request, db: Session = Depends(get_db)):
    """Send a message and get AI response - user-specific with agent integration"""
    user = await get_current_user(request, db)
    content = (payload.content or "").strip()
    
    print(f"💬 CHAT MESSAGE from {user.email}: {content}")
    
    if not content:
        raise HTTPException(status_code=400, detail="Empty message")

    # Store user message with user_id
    user_msg = Message(role="user", content=content, user_id=user.id)
    db.add(user_msg)
    db.flush()

    meetings_out: List[MeetingOut] = []

    # Check if this is a task request (contains action words)
    task_keywords = ["schedule", "send email", "create contact", "add note", "set up", "arrange", "book"]
    is_task_request = any(keyword in content.lower() for keyword in task_keywords)
    
    print(f"🔍 IS_TASK_REQUEST: {is_task_request}")
    
    if is_task_request:
        print(f"🎯 CREATING AGENT TASK: {content}")
        # Create an agent task for this request
        task = await agent_service.create_task(db, user, content, {"source": "chat"})
        
        # Process task immediately
        print(f"▶️ PROCESSING TASK {task.id}")
        await agent_service.process_task(db, task)
        
        # Get updated task status
        db.refresh(task)
        print(f"📋 FINAL TASK STATUS: {task.status}")
        print(f"📋 FINAL TASK RESULT: {task.result}")
        
        if task.status == "completed":
            ai_response = f"✅ Task completed! {task.result}"
        elif task.status == "waiting_response":
            ai_response = f"📧 I've sent the email and I'm waiting for a response. {task.result}"
        elif task.status == "failed":
            ai_response = f"❌ Task failed: {task.result}"
        else:
            ai_response = f"🔄 Task is {task.status}. I'll continue working on it."
    else:
        # Handle as regular chat with RAG
        user_meetings = db.query(Meeting).filter(Meeting.user_id == user.id).order_by(Meeting.start_iso.asc()).all()
        
        # Get RAG context from user's Gmail/HubSpot data
        rag_context = rag_service.get_context_for_query(db, user.id, content)
        
        # Auto-sync Gmail if no context found and no emails exist
        if not rag_context:
            from ..models import GmailEmail
            existing_emails = db.query(GmailEmail).filter(GmailEmail.user_id == user.id).count()
            
            if existing_emails == 0:
                try:
                    logger.info("No emails found, auto-syncing Gmail data...")
                    count = await data_sync_service.sync_gmail_emails(db, user, max_emails=10)
                    logger.info(f"Auto-synced {count} emails")
                    # Try getting context again after sync
                    rag_context = rag_service.get_context_for_query(db, user.id, content)
                except Exception as e:
                    logger.error(f"Auto-sync failed: {e}")
            else:
                logger.info(f"Found {existing_emails} emails but no RAG context for query")
        
        logger.info(f"RAG context found: {len(rag_context)} characters for query: {content[:50]}")
        if rag_context:
            logger.info(f"RAG context preview: {rag_context[:500]}...")
        else:
            logger.warning(f"No RAG context found for query: {content}")
        
        # Generate AI response with RAG context
        if not rag_context:
            print(f"DEBUG: No RAG context found, using fallback response")
            ai_response = "I couldn't find any relevant information in your emails or CRM data to answer that question. You may need to sync more data or the information might not be available."
        else:
            print(f"DEBUG: Using RAG context with {len(rag_context)} characters")
            ai_response = await generate_ai_response_with_rag(content, user_meetings, rag_context, db)
        
        # Handle meeting-related queries
        if "meeting" in content.lower() or "schedule" in content.lower():
            # Return some meetings if user asks for them
            if user_meetings:
                meetings_out = [_meeting_to_out(mt) for mt in user_meetings[:3]]  # Return up to 3 meetings
    
    # Store AI response with user_id
    asst_msg = Message(role="assistant", content=ai_response, user_id=user.id)
    db.add(asst_msg)
    db.commit()
    db.refresh(user_msg)
    db.refresh(asst_msg)
    
    print(f"💬 CHAT RESPONSE: {ai_response}")

    response = ChatSendResponse(
        messages=[
            MessageOut(id=user_msg.id, role=user_msg.role, content=user_msg.content, created_at=user_msg.created_at),
            MessageOut(id=asst_msg.id, role=asst_msg.role, content=asst_msg.content, created_at=asst_msg.created_at),
        ],
        meetings=meetings_out,
    )
    
    print(f"🚀 SENDING CHAT RESPONSE")
    return response

@router.post("/clear", response_model=ChatSendResponse)
async def clear_chat(request: Request, db: Session = Depends(get_db)):
    """Clear chat for the current user only"""
    user = await get_current_user(request, db)
    
    # Clear only this user's messages and meetings
    db.query(Message).filter(Message.user_id == user.id).delete()
    db.query(Meeting).filter(Meeting.user_id == user.id).delete()
    db.commit()
    
    return ChatSendResponse(messages=[], meetings=[])

@router.get("/meetings", response_model=List[MeetingOut])
async def get_meetings(request: Request, db: Session = Depends(get_db)):
    """Get meetings for the current user only"""
    user = await get_current_user(request, db)
    
    rows = db.query(Meeting).filter(Meeting.user_id == user.id).order_by(Meeting.start_iso.asc()).all()
    return [_meeting_to_out(mt) for mt in rows]

@router.post("/sync-gmail")
async def sync_gmail_data(request: Request, db: Session = Depends(get_db)):
    """Sync Gmail data and create embeddings"""
    user = await get_current_user(request, db)
    
    try:
        count = await data_sync_service.sync_gmail_emails(db, user, max_emails=50)
        return {"message": f"Synced {count} emails successfully"}
    except Exception as e:
        logger.error(f"Gmail sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sync-gmail")
async def sync_gmail_data_get(request: Request, db: Session = Depends(get_db)):
    """Sync Gmail data - GET version for easy testing"""
    return await sync_gmail_data(request, db)

@router.get("/rag-status")
async def check_rag_status(request: Request, db: Session = Depends(get_db)):
    """Check RAG data status"""
    user = await get_current_user(request, db)
    
    from ..models import GmailEmail, DocumentEmbedding
    
    emails_count = db.query(GmailEmail).filter(GmailEmail.user_id == user.id).count()
    embeddings_count = db.query(DocumentEmbedding).filter(DocumentEmbedding.user_id == user.id).count()
    
    return {
        "user_email": user.email,
        "gmail_emails": emails_count,
        "embeddings": embeddings_count,
        "rag_ready": embeddings_count > 0
    }

@router.get("/test-search")
async def test_search(request: Request, query: str = "gmail", db: Session = Depends(get_db)):
    """Test RAG similarity search"""
    user = await get_current_user(request, db)
    
    results = rag_service.similarity_search(db, user.id, query, limit=5)
    
    return {
        "query": query,
        "results": [
            {
                "similarity": similarity,
                "content_preview": doc.content[:200],
                "source_type": doc.source_type,
                "metadata": doc.meta_data
            }
            for doc, similarity in results
        ]
    }