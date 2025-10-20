# app/routers/meetings.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from ..db import get_db
from ..models import Meeting, User
from ..schemas import MeetingOut, MeetingCreate
from ..security import verify_session_jwt

router = APIRouter(prefix="/meetings", tags=["meetings"])

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

@router.get("", response_model=List[MeetingOut])
async def get_meetings(request: Request, db: Session = Depends(get_db)):
    """Get meetings for the current user only"""
    user = await get_current_user(request, db)
    
    rows = db.query(Meeting).filter(Meeting.user_id == user.id).order_by(Meeting.start_iso.asc()).all()
    return [
        MeetingOut(
            id=mtg.id,
            title=mtg.title,
            start_iso=mtg.start_iso,
            end_iso=mtg.end_iso,
            attendees=mtg.attendees
        ) for mtg in rows
    ]

@router.post("", response_model=MeetingOut)
async def create_meeting(meeting: MeetingCreate, request: Request, db: Session = Depends(get_db)):
    """Create a meeting for the current user"""
    user = await get_current_user(request, db)
    
    db_meeting = Meeting(
        user_id=user.id,
        title=meeting.title,
        start_iso=meeting.start_iso,
        end_iso=meeting.end_iso,
        attendees=meeting.attendees
    )
    db.add(db_meeting)
    db.commit()
    db.refresh(db_meeting)
    
    return MeetingOut(
        id=db_meeting.id,
        title=db_meeting.title,
        start_iso=db_meeting.start_iso,
        end_iso=db_meeting.end_iso,
        attendees=db_meeting.attendees
    )