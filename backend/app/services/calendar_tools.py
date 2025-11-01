# app/services/calendar_tools.py
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime

from ..models import User, GoogleAccount, Meeting

logger = logging.getLogger(__name__)

class CalendarTools:
    def __init__(self):
        pass
    
    def _get_calendar_service(self, user: User, db: Session):
        """Get authenticated Calendar service"""
        google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
        if not google_account:
            raise Exception("No Google account connected")
        
        from ..db import get_settings
        settings = get_settings()
        
        credentials = Credentials(
            token=google_account.access_token,
            refresh_token=google_account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.OAUTH_GOOGLE_CLIENT_ID,
            client_secret=settings.OAUTH_GOOGLE_CLIENT_SECRET,
        )
        
        return build('calendar', 'v3', credentials=credentials)
    
    async def create_event(self, db: Session, user: User, title: str, start_time: str, end_time: str, attendees: List[str] = None) -> Dict[str, Any]:
        """Create a calendar event"""
        try:
            service = self._get_calendar_service(user, db)
            
            event = {
                'summary': title,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC',
                },
            }
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            result = service.events().insert(calendarId='primary', body=event).execute()
            
            # Also store in local database
            meeting = Meeting(
                user_id=user.id,
                title=title,
                start_iso=start_time,
                end_iso=end_time,
                attendees={"people": [{"id": email, "name": email} for email in (attendees or [])]}
            )
            db.add(meeting)
            db.commit()
            
            return {
                "success": True,
                "event_id": result.get('id'),
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "attendees": attendees or []
            }
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_events(self, db: Session, user: User, query: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Search calendar events"""
        try:
            # Search local database first
            meetings_query = db.query(Meeting).filter(
                Meeting.user_id == user.id,
                Meeting.title.contains(query)
            )
            
            if start_date:
                meetings_query = meetings_query.filter(Meeting.start_iso >= start_date)
            if end_date:
                meetings_query = meetings_query.filter(Meeting.end_iso <= end_date)
            
            meetings = meetings_query.limit(10).all()
            
            results = []
            for meeting in meetings:
                results.append({
                    "id": meeting.id,
                    "title": meeting.title,
                    "start_time": meeting.start_iso,
                    "end_time": meeting.end_iso,
                    "attendees": meeting.attendees
                })
            
            return {
                "success": True,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            logger.error(f"Failed to search calendar events: {e}")
            return {"success": False, "error": str(e)}