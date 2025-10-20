# app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Any
import logging
from datetime import datetime

from ..db import get_db
from ..models import *
from ..security import verify_session_jwt

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger("admin")

# Simple admin authentication (you might want to enhance this)
def verify_admin(request: Request, db: Session = Depends(get_db)):
    """Verify if the user is an admin"""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_data = verify_session_jwt(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    user = db.query(User).filter(User.sub == user_data["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Simple admin check - you might want to add an 'is_admin' field to User model
    # For now, we'll check if the user email contains 'admin' or is a specific email
    if "admin" not in user.email.lower() and user.email != "chrisdev0117@gmail.com":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return user

@router.get("/users", response_model=List[UserSummary])
async def get_all_users(
    request: Request, 
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get summary of all users"""
    users = db.query(User).options(
        joinedload(User.google_account),
        joinedload(User.hubspot_accounts),
        joinedload(User.messages),
        joinedload(User.meetings)
    ).all()
    
    user_summaries = []
    for user in users:
        user_summaries.append(UserSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            sub=user.sub,
            created_meetings=len(user.meetings),
            sent_messages=len(user.messages),
            has_google=user.google_account is not None,
            has_hubspot=len(user.hubspot_accounts) > 0
        ))
    
    return user_summaries

@router.get("/google-accounts", response_model=List[GoogleAccountDetail])
async def get_all_google_accounts(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get all Google OAuth accounts with user info"""
    google_accounts = db.query(GoogleAccount).join(User).options(joinedload(GoogleAccount.user)).all()
    
    accounts = []
    for ga in google_accounts:
        print(ga.__dict__)
        accounts.append(GoogleAccountDetail(
            user_id=ga.user_id,
            user_email=ga.user.email,
            user_name=ga.user.name,
            scopes=ga.scope,
            expires_at=datetime.fromtimestamp(ga.expires_at)
        ))
    
    return accounts

@router.get("/hubspot-accounts", response_model=List[HubspotAccountDetail])
async def get_all_hubspot_accounts(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get all HubSpot OAuth accounts with user info"""
    hubspot_accounts = db.query(HubspotAccount).join(User).options(joinedload(HubspotAccount.user)).all()
    
    accounts = []
    for ha in hubspot_accounts:
        accounts.append(HubspotAccountDetail(
            user_id=ha.user_id,
            user_email=ha.user.email,
            user_name=ha.user.name,
            hubspot_user_id=ha.hubspot_user_id,
            access_token=ha.access_token,  # Be careful with this in production!
            refresh_token=ha.refresh_token,
            expires_in=ha.expires_in,
            created_at=ha.created_at,
            updated_at=ha.updated_at
        ))
    
    return accounts

@router.get("/messages", response_model=List[UserMessages])
async def get_all_messages(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get all messages grouped by user"""
    users = db.query(User).options(joinedload(User.messages)).all()
    
    user_messages = []
    for user in users:
        user_messages.append(UserMessages(
            user_id=user.id,
            user_email=user.email,
            messages=[
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in user.messages
            ]
        ))
    
    return user_messages

@router.get("/meetings", response_model=List[UserMeetings])
async def get_all_meetings(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get all meetings grouped by user"""
    users = db.query(User).options(joinedload(User.meetings)).all()
    
    user_meetings = []
    for user in users:
        user_meetings.append(UserMeetings(
            user_id=user.id,
            user_email=user.email,
            meetings=[
                {
                    "id": mtg.id,
                    "title": mtg.title,
                    "start_iso": mtg.start_iso,
                    "end_iso": mtg.end_iso,
                    "attendees": mtg.attendees
                }
                for mtg in user.meetings
            ]
        ))
    
    return user_meetings

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get admin dashboard statistics"""
    total_users = db.query(User).count()
    total_messages = db.query(Message).count()
    total_meetings = db.query(Meeting).count()
    
    google_connected_users = db.query(GoogleAccount).distinct(GoogleAccount.user_id).count()
    hubspot_connected_users = db.query(HubspotAccount).distinct(HubspotAccount.user_id).count()
    
    # Users active today (created messages today)
    today = datetime.now().date()
    active_today = db.query(Message).filter(
        Message.created_at >= datetime.combine(today, datetime.min.time())
    ).distinct(Message.user_id).count()
    
    return AdminStats(
        total_users=total_users,
        total_messages=total_messages,
        total_meetings=total_meetings,
        google_connected_users=google_connected_users,
        hubspot_connected_users=hubspot_connected_users,
        active_today=active_today
    )

@router.get("/user/{user_id}/full-data")
async def get_user_full_data(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get complete data for a specific user"""
    user = db.query(User).options(
        joinedload(User.google_account),
        joinedload(User.hubspot_accounts),
        joinedload(User.messages),
        joinedload(User.meetings)
    ).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_info": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "sub": user.sub,
            "picture": user.picture
        },
        "google_account": {
            "exists": user.google_account is not None,
            "scopes": user.google_account.scope if user.google_account else None,
            "expires_at": datetime.fromtimestamp(user.google_account.expires_at).isoformat() if user.google_account else None
        } if user.google_account else None,
        "hubspot_accounts": [
            {
                "hubspot_user_id": ha.hubspot_user_id,
                "created_at": ha.created_at.isoformat(),
                "updated_at": ha.updated_at.isoformat()
            }
            for ha in user.hubspot_accounts
        ],
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in user.messages
        ],
        "meetings": [
            {
                "id": mtg.id,
                "title": mtg.title,
                "start_iso": mtg.start_iso,
                "end_iso": mtg.end_iso,
                "attendees": mtg.attendees
            }
            for mtg in user.meetings
        ]
    }

# Gmail and HubSpot API data endpoints
@router.get("/gmail-data")
async def get_gmail_data(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get Gmail data for all users (this would integrate with Gmail API)"""
    # This is a placeholder - you would need to implement Gmail API integration
    google_accounts = db.query(GoogleAccount).join(User).all()
    
    gmail_data = []
    for ga in google_accounts:
        # In a real implementation, you would use the access_token to call Gmail API
        # For now, we'll return the account info
        gmail_data.append({
            "user_id": ga.user_id,
            "user_email": ga.user.email,
            "gmail_scopes": ga.scope,
            "access_token_available": bool(ga.access_token),
            "note": "Gmail API integration required to fetch actual email data"
        })
    
    return gmail_data

@router.get("/hubspot-data")
async def get_hubspot_data(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get HubSpot data for all users (this would integrate with HubSpot API)"""
    import requests
    
    hubspot_accounts = db.query(HubspotAccount).join(User).all()
    
    hubspot_data = []
    for ha in hubspot_accounts:
        try:
            # Example: Get contacts from HubSpot API
            headers = {
                "Authorization": f"Bearer {ha.access_token}",
                "Content-Type": "application/json"
            }
            
            # Get basic account info
            response = requests.get(
                "https://api.hubapi.com/account-info/v3/details",
                headers=headers,
                timeout=10
            )
            
            account_info = response.json() if response.status_code == 200 else None
            
            # Get contacts count
            contacts_response = requests.get(
                "https://api.hubapi.com/contacts/v1/lists/all/contacts/all?count=1",
                headers=headers,
                timeout=10
            )
            
            contacts_count = 0
            if contacts_response.status_code == 200:
                contacts_data = contacts_response.json()
                contacts_count = contacts_data.get('total', 0)
            
            hubspot_data.append({
                "user_id": ha.user_id,
                "user_email": ha.user.email,
                "hubspot_user_id": ha.hubspot_user_id,
                "account_info": account_info,
                "contacts_count": contacts_count,
                "token_valid": response.status_code == 200
            })
            
        except Exception as e:
            hubspot_data.append({
                "user_id": ha.user_id,
                "user_email": ha.user.email,
                "hubspot_user_id": ha.hubspot_user_id,
                "error": str(e),
                "token_valid": False
            })
    
    return hubspot_data