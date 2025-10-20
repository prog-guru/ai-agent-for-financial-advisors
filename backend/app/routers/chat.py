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

async def generate_ai_response(user_message: str, user_meetings: List[Meeting], db: Session) -> str:
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
        
        Respond helpfully and naturally to the user's message. If they ask about meetings, use the meeting information provided.
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
    """Send a message and get AI response - user-specific"""
    user = await get_current_user(request, db)
    content = (payload.content or "").strip()
    
    if not content:
        raise HTTPException(status_code=400, detail="Empty message")

    # Store user message with user_id
    user_msg = Message(role="user", content=content, user_id=user.id)
    db.add(user_msg)
    db.flush()

    meetings_out: List[MeetingOut] = []

    # Get user's meetings for context
    user_meetings = db.query(Meeting).filter(Meeting.user_id == user.id).order_by(Meeting.start_iso.asc()).all()
    
    # Generate AI response
    ai_response = await generate_ai_response(content, user_meetings, db)
    
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

    return ChatSendResponse(
        messages=[
            MessageOut(id=user_msg.id, role=user_msg.role, content=user_msg.content, created_at=user_msg.created_at),
            MessageOut(id=asst_msg.id, role=asst_msg.role, content=asst_msg.content, created_at=asst_msg.created_at),
        ],
        meetings=meetings_out,
    )

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