# app/services/data_sync.py
import requests
import httpx
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging
from datetime import datetime, timezone
import base64
import email
from email.mime.text import MIMEText

from ..models import User, GoogleAccount, HubspotAccount, GmailEmail, HubspotContact, HubspotNote
from .rag import rag_service

logger = logging.getLogger("data_sync")

class DataSyncService:
    
    async def sync_gmail_emails(self, db: Session, user: User, max_emails: int = 100):
        """Sync Gmail emails and create embeddings"""
        google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
        if not google_account:
            raise ValueError("Google account not connected")
        
        # Get access token (refresh if needed)
        from ..routers.gmail_calendar import refresh_google_token
        access_token = await refresh_google_token(google_account, db)
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Get email list
        messages_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        params = {"maxResults": max_emails}
        response = requests.get(messages_url, headers=headers, params=params, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch emails: {response.text}")
        
        messages_data = response.json()
        synced_count = 0
        
        for msg in messages_data.get("messages", []):
            try:
                # Get full message details
                message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}"
                msg_response = requests.get(message_url, headers=headers, params={"format": "full"}, timeout=30)
                
                if msg_response.status_code != 200:
                    continue
                
                msg_data = msg_response.json()
                
                # Check if email already exists
                existing = db.query(GmailEmail).filter(GmailEmail.gmail_id == msg_data["id"]).first()
                if existing:
                    continue
                
                # Extract email details
                headers_map = {}
                payload = msg_data.get("payload", {})
                for h in payload.get("headers", []):
                    headers_map[h.get("name", "")] = h.get("value", "")
                
                # Extract body
                body = self._extract_email_body(payload)
                
                # Create email record
                email_record = GmailEmail(
                    user_id=user.id,
                    gmail_id=msg_data["id"],
                    thread_id=msg_data.get("threadId", ""),
                    subject=headers_map.get("Subject", ""),
                    sender=headers_map.get("From", ""),
                    recipient=headers_map.get("To", ""),
                    body=body,
                    snippet=msg_data.get("snippet", ""),
                    date_sent=datetime.fromtimestamp(int(msg_data.get("internalDate", 0)) / 1000, tz=timezone.utc),
                    labels={"labels": msg_data.get("labelIds", [])}
                )
                
                db.add(email_record)
                db.flush()
                
                # Create embedding
                content = f"Subject: {email_record.subject}\nFrom: {email_record.sender}\nBody: {body}"
                metadata = {
                    "subject": email_record.subject,
                    "sender": email_record.sender,
                    "date": email_record.date_sent.isoformat(),
                    "type": "email"
                }
                
                rag_service.store_embedding(
                    db, user.id, "gmail", email_record.gmail_id, content, metadata
                )
                
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Error syncing email {msg.get('id')}: {e}")
                continue
        
        db.commit()
        return synced_count
    
    async def sync_hubspot_contacts(self, db: Session, user: User):
        """Sync HubSpot contacts and notes"""
        hubspot_account = db.query(HubspotAccount).filter(HubspotAccount.user_id == user.id).first()
        if not hubspot_account:
            raise ValueError("HubSpot account not connected")
        
        headers = {"Authorization": f"Bearer {hubspot_account.access_token}"}
        synced_contacts = 0
        synced_notes = 0
        
        # Sync contacts
        contacts_url = "https://api.hubapi.com/crm/v3/objects/contacts"
        params = {
            "properties": "email,firstname,lastname,company,phone",
            "limit": 100
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(contacts_url, headers=headers, params=params)
            
            if response.status_code == 200:
                contacts_data = response.json()
                
                for contact_data in contacts_data.get("results", []):
                    try:
                        hubspot_id = contact_data["id"]
                        properties = contact_data.get("properties", {})
                        
                        # Check if contact exists
                        existing = db.query(HubspotContact).filter(HubspotContact.hubspot_id == hubspot_id).first()
                        
                        if existing:
                            # Update existing
                            existing.email = properties.get("email", "")
                            existing.first_name = properties.get("firstname", "")
                            existing.last_name = properties.get("lastname", "")
                            existing.company = properties.get("company", "")
                            existing.phone = properties.get("phone", "")
                            existing.properties = properties
                        else:
                            # Create new
                            contact = HubspotContact(
                                user_id=user.id,
                                hubspot_id=hubspot_id,
                                email=properties.get("email", ""),
                                first_name=properties.get("firstname", ""),
                                last_name=properties.get("lastname", ""),
                                company=properties.get("company", ""),
                                phone=properties.get("phone", ""),
                                properties=properties
                            )
                            db.add(contact)
                            synced_contacts += 1
                        
                        db.flush()
                        
                        # Create embedding for contact
                        name = f"{properties.get('firstname', '')} {properties.get('lastname', '')}".strip()
                        content = f"Contact: {name}\nEmail: {properties.get('email', '')}\nCompany: {properties.get('company', '')}\nPhone: {properties.get('phone', '')}"
                        
                        metadata = {
                            "name": name,
                            "email": properties.get("email", ""),
                            "company": properties.get("company", ""),
                            "type": "contact"
                        }
                        
                        rag_service.store_embedding(
                            db, user.id, "hubspot", hubspot_id, content, metadata
                        )
                        
                        # Sync notes for this contact
                        notes_count = await self._sync_contact_notes(db, user, hubspot_id, headers, client)
                        synced_notes += notes_count
                        
                    except Exception as e:
                        logger.error(f"Error syncing contact {contact_data.get('id')}: {e}")
                        continue
        
        db.commit()
        return synced_contacts, synced_notes
    
    async def _sync_contact_notes(self, db: Session, user: User, contact_hubspot_id: str, 
                                 headers: Dict[str, str], client: httpx.AsyncClient) -> int:
        """Sync notes for a specific contact"""
        notes_url = f"https://api.hubapi.com/crm/v3/objects/notes"
        params = {
            "properties": "hs_note_body,hs_createdate",
            "associations": f"contact:{contact_hubspot_id}"
        }
        
        try:
            response = await client.get(notes_url, headers=headers, params=params)
            if response.status_code != 200:
                return 0
            
            notes_data = response.json()
            synced_count = 0
            
            # Get contact record
            contact = db.query(HubspotContact).filter(HubspotContact.hubspot_id == contact_hubspot_id).first()
            if not contact:
                return 0
            
            for note_data in notes_data.get("results", []):
                try:
                    note_id = note_data["id"]
                    properties = note_data.get("properties", {})
                    body = properties.get("hs_note_body", "")
                    
                    if not body:
                        continue
                    
                    # Check if note exists
                    existing = db.query(HubspotNote).filter(HubspotNote.hubspot_id == note_id).first()
                    if existing:
                        continue
                    
                    # Create note
                    note = HubspotNote(
                        user_id=user.id,
                        contact_id=contact.id,
                        hubspot_id=note_id,
                        body=body
                    )
                    db.add(note)
                    db.flush()
                    
                    # Create embedding
                    content = f"Note about {contact.first_name} {contact.last_name}: {body}"
                    metadata = {
                        "contact_name": f"{contact.first_name} {contact.last_name}",
                        "contact_email": contact.email,
                        "type": "note"
                    }
                    
                    rag_service.store_embedding(
                        db, user.id, "hubspot", note_id, content, metadata
                    )
                    
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"Error syncing note {note_data.get('id')}: {e}")
                    continue
            
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing notes for contact {contact_hubspot_id}: {e}")
            return 0
    
    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from Gmail payload"""
        body = ""
        
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        break
        else:
            if payload.get("mimeType") == "text/plain":
                data = payload.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        
        return body
    


# Global instance
data_sync_service = DataSyncService()