# app/services/gmail_tools.py
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from ..models import User, GoogleAccount, GmailEmail

logger = logging.getLogger(__name__)

class GmailTools:
    def __init__(self):
        pass
    
    def _get_gmail_service(self, user: User, db: Session):
        """Get authenticated Gmail service"""
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
        
        return build('gmail', 'v1', credentials=credentials)
    
    async def send_email(self, db: Session, user: User, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Send an email"""
        try:
            service = self._get_gmail_service(user, db)
            
            message = {
                'raw': self._create_message(to, subject, body)
            }
            
            result = service.users().messages().send(userId='me', body=message).execute()
            
            return {
                "success": True,
                "message_id": result.get('id'),
                "to": to,
                "subject": subject
            }
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_emails(self, db: Session, user: User, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search emails in database first, then Gmail if needed"""
        try:
            # Search local database first
            emails = db.query(GmailEmail).filter(
                GmailEmail.user_id == user.id,
                GmailEmail.subject.contains(query) | GmailEmail.body.contains(query)
            ).limit(limit).all()
            
            results = []
            for email in emails:
                results.append({
                    "id": email.gmail_id,
                    "subject": email.subject,
                    "sender": email.sender,
                    "snippet": email.snippet,
                    "date": email.date_sent.isoformat()
                })
            
            return {
                "success": True,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            logger.error(f"Failed to search emails: {e}")
            return {"success": False, "error": str(e)}
    
    def _create_message(self, to: str, subject: str, body: str) -> str:
        """Create a message for Gmail API"""
        import base64
        from email.mime.text import MIMEText
        
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        
        return base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    async def find_contact_info(self, db: Session, user: User, name: str) -> Dict[str, Any]:
        """Find contact information from emails"""
        try:
            print(f"🔍 SEARCHING for: '{name}' in emails")
            
            # Search emails for the person's name (case insensitive)
            name_parts = name.lower().split()
            print(f"🔍 NAME PARTS: {name_parts}")
            
            # Get all emails for this user
            all_emails = db.query(GmailEmail).filter(GmailEmail.user_id == user.id).all()
            print(f"📧 TOTAL EMAILS: {len(all_emails)}")
            
            contacts = []
            for email in all_emails:
                sender_lower = email.sender.lower()
                body_lower = email.body.lower() if email.body else ""
                
                # Check if any part of the name matches
                name_match = any(part in sender_lower or part in body_lower for part in name_parts)
                
                if name_match:
                    print(f"✅ MATCH FOUND: {email.sender}")
                    
                    # Extract email from sender
                    sender_parts = email.sender.split('<')
                    if len(sender_parts) > 1:
                        email_addr = sender_parts[1].replace('>', '').strip()
                        sender_name = sender_parts[0].strip()
                    else:
                        email_addr = email.sender
                        sender_name = email.sender
                    
                    contacts.append({
                        "name": sender_name,
                        "email": email_addr,
                        "source": "gmail",
                        "last_contact": email.date_sent.isoformat()
                    })
            
            print(f"📋 FOUND CONTACTS: {len(contacts)}")
            
            return {
                "success": True,
                "results": contacts[:3],  # Return top 3 matches
                "count": len(contacts)
            }
        except Exception as e:
            print(f"❌ CONTACT SEARCH ERROR: {e}")
            return {"success": False, "error": str(e)}