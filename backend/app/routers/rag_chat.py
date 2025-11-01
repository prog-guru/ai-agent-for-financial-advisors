# app/routers/rag_chat.py
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import openai
import logging

from ..db import get_db, get_settings
from ..models import User, Message
from ..schemas import MessageOut, MessageIn
from ..security import verify_session_jwt
from ..services.rag import rag_service
from ..services.data_sync import data_sync_service

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger("rag_chat")

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

@router.post("/sync-data")
async def sync_user_data(
    request: Request, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Sync Gmail and HubSpot data for the current user"""
    user = await get_current_user(request, db)
    
    # Add sync tasks to background
    background_tasks.add_task(sync_gmail_data, db, user)
    background_tasks.add_task(sync_hubspot_data, db, user)
    
    return {"message": "Data sync started in background"}

async def sync_gmail_data(db: Session, user: User):
    """Background task to sync Gmail data"""
    try:
        count = await data_sync_service.sync_gmail_emails(db, user, max_emails=50)
        logger.info(f"Synced {count} emails for user {user.email}")
    except Exception as e:
        logger.error(f"Error syncing Gmail data for user {user.email}: {e}")

async def sync_hubspot_data(db: Session, user: User):
    """Background task to sync HubSpot data"""
    try:
        contacts, notes = await data_sync_service.sync_hubspot_contacts(db, user)
        logger.info(f"Synced {contacts} contacts and {notes} notes for user {user.email}")
    except Exception as e:
        logger.error(f"Error syncing HubSpot data for user {user.email}: {e}")

@router.post("/chat", response_model=MessageOut)
async def rag_chat(
    payload: MessageIn,
    request: Request,
    db: Session = Depends(get_db)
):
    """Chat with RAG-enhanced AI that can answer questions about clients"""
    user = await get_current_user(request, db)
    content = (payload.content or "").strip()
    
    if not content:
        raise HTTPException(status_code=400, detail="Empty message")
    
    # Store user message
    user_msg = Message(role="user", content=content, user_id=user.id)
    db.add(user_msg)
    db.flush()
    
    # Get relevant context using RAG
    context = rag_service.get_context_for_query(db, user.id, content)
    logger.info(f"RAG context found: {len(context)} characters for query: {content[:50]}")
    
    # Generate AI response with context
    ai_response = await generate_rag_response(content, context)
    
    # Store AI response
    asst_msg = Message(role="assistant", content=ai_response, user_id=user.id)
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)
    
    return MessageOut(
        id=asst_msg.id,
        role=asst_msg.role,
        content=asst_msg.content,
        created_at=asst_msg.created_at
    )

async def generate_rag_response(user_message: str, context: str) -> str:
    """Generate AI response using RAG context"""
    try:
        client = openai.OpenAI(api_key=get_settings().OPENAI_API_KEY)
        
        system_prompt = f"""You are a helpful AI assistant that can answer questions about clients based on email and CRM data.

Use the following context from emails and HubSpot records to answer the user's question:

{context}

Instructions:
- Answer based on the provided context
- If the context doesn't contain relevant information, say so
- Be specific and cite details from the context when possible
- For questions about people, include their contact information if available
- Keep responses concise but informative"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        if context:
            return f"I found some relevant information but couldn't generate a proper response. Here's what I found:\n\n{context[:500]}..."
        else:
            return "I couldn't find any relevant information in your emails or HubSpot data to answer that question."

@router.get("/search")
async def search_documents(
    request: Request,
    query: str,
    source_type: str = None,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """Search through user's documents using semantic similarity"""
    user = await get_current_user(request, db)
    
    results = rag_service.similarity_search(db, user.id, query, limit, source_type)
    
    search_results = []
    for doc, similarity in results:
        search_results.append({
            "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
            "source_type": doc.source_type,
            "source_id": doc.source_id,
            "similarity": round(similarity, 3),
            "metadata": doc.meta_data,
            "created_at": doc.created_at
        })
    
    return {
        "query": query,
        "results": search_results,
        "total": len(search_results)
    }

@router.get("/stats")
async def get_rag_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get statistics about user's indexed data"""
    user = await get_current_user(request, db)
    
    from ..models import DocumentEmbedding, GmailEmail, HubspotContact, HubspotNote
    
    gmail_count = db.query(GmailEmail).filter(GmailEmail.user_id == user.id).count()
    hubspot_contacts = db.query(HubspotContact).filter(HubspotContact.user_id == user.id).count()
    hubspot_notes = db.query(HubspotNote).filter(HubspotNote.user_id == user.id).count()
    embeddings_count = db.query(DocumentEmbedding).filter(DocumentEmbedding.user_id == user.id).count()
    
    return {
        "gmail_emails": gmail_count,
        "hubspot_contacts": hubspot_contacts,
        "hubspot_notes": hubspot_notes,
        "total_embeddings": embeddings_count,
        "ready_for_queries": embeddings_count > 0
    }