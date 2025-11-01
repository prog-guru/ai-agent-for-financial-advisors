# app/services/hubspot_tools.py
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
import requests

from ..models import User, HubspotAccount, HubspotContact, HubspotNote

logger = logging.getLogger(__name__)

class HubspotTools:
    def __init__(self):
        self.base_url = "https://api.hubapi.com"
    
    def _get_hubspot_headers(self, user: User, db: Session) -> Dict[str, str]:
        """Get HubSpot API headers with access token"""
        hubspot_account = db.query(HubspotAccount).filter(HubspotAccount.user_id == user.id).first()
        if not hubspot_account:
            raise Exception("No HubSpot account connected")
        
        return {
            "Authorization": f"Bearer {hubspot_account.access_token}",
            "Content-Type": "application/json"
        }
    
    async def create_contact(self, db: Session, user: User, email: str, first_name: str = None, last_name: str = None, company: str = None, note: str = None) -> Dict[str, Any]:
        """Create a contact in HubSpot"""
        try:
            headers = self._get_hubspot_headers(user, db)
            
            properties = {"email": email}
            if first_name:
                properties["firstname"] = first_name
            if last_name:
                properties["lastname"] = last_name
            if company:
                properties["company"] = company
            
            data = {"properties": properties}
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=headers,
                json=data
            )
            
            if response.status_code == 201:
                result = response.json()
                hubspot_id = result["id"]
                
                # Store in local database
                contact = HubspotContact(
                    user_id=user.id,
                    hubspot_id=hubspot_id,
                    email=email,
                    first_name=first_name or "",
                    last_name=last_name or "",
                    company=company or "",
                    properties=result.get("properties", {})
                )
                db.add(contact)
                db.commit()
                
                # Add note if provided
                if note:
                    await self.add_note(db, user, email, note)
                
                return {
                    "success": True,
                    "contact_id": hubspot_id,
                    "email": email,
                    "name": f"{first_name or ''} {last_name or ''}".strip()
                }
            else:
                return {"success": False, "error": f"HubSpot API error: {response.text}"}
                
        except Exception as e:
            logger.error(f"Failed to create HubSpot contact: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_contacts(self, db: Session, user: User, query: str) -> Dict[str, Any]:
        """Search HubSpot contacts"""
        try:
            # Check if HubSpot is connected
            hubspot_account = db.query(HubspotAccount).filter(HubspotAccount.user_id == user.id).first()
            if not hubspot_account:
                return {
                    "success": False, 
                    "error": "HubSpot not connected. Please connect HubSpot first.",
                    "results": [],
                    "count": 0
                }
            
            # Search local database first
            contacts = db.query(HubspotContact).filter(
                HubspotContact.user_id == user.id,
                (HubspotContact.email.contains(query) | 
                 HubspotContact.first_name.contains(query) |
                 HubspotContact.last_name.contains(query))
            ).limit(10).all()
            
            results = []
            for contact in contacts:
                results.append({
                    "id": contact.hubspot_id,
                    "email": contact.email,
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "company": contact.company
                })
            
            return {
                "success": True,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            logger.error(f"Failed to search HubSpot contacts: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_note(self, db: Session, user: User, contact_email: str, note: str) -> Dict[str, Any]:
        """Add a note to a HubSpot contact"""
        try:
            # Find contact in local database
            contact = db.query(HubspotContact).filter(
                HubspotContact.user_id == user.id,
                HubspotContact.email == contact_email
            ).first()
            
            if not contact:
                return {"success": False, "error": "Contact not found"}
            
            headers = self._get_hubspot_headers(user, db)
            
            data = {
                "properties": {
                    "hs_note_body": note,
                    "hs_timestamp": int(datetime.now().timestamp() * 1000)
                },
                "associations": [
                    {
                        "to": {"id": contact.hubspot_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]
                    }
                ]
            }
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/notes",
                headers=headers,
                json=data
            )
            
            if response.status_code == 201:
                result = response.json()
                
                # Store in local database
                hubspot_note = HubspotNote(
                    user_id=user.id,
                    contact_id=contact.id,
                    hubspot_id=result["id"],
                    body=note
                )
                db.add(hubspot_note)
                db.commit()
                
                return {
                    "success": True,
                    "note_id": result["id"],
                    "contact_email": contact_email,
                    "note": note
                }
            else:
                return {"success": False, "error": f"HubSpot API error: {response.text}"}
                
        except Exception as e:
            logger.error(f"Failed to add HubSpot note: {e}")
            return {"success": False, "error": str(e)}