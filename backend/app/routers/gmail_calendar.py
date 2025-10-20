# app/routers/gmail_calendar.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta, timezone
import requests

from ..db import get_db, get_settings
from ..models import User, GoogleAccount
from ..security import verify_session_jwt

router = APIRouter(prefix="/user-data", tags=["user-data"])
logger = logging.getLogger("gmail_calendar")
logger.setLevel(logging.INFO)


# ----------------------------- helpers -----------------------------
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


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _get_google_oauth_client():
    s = get_settings()

    cid = getattr(s, "OAUTH_GOOGLE_CLIENT_ID", None) or getattr(s, "GOOGLE_CLIENT_ID", None)
    csec = getattr(s, "OAUTH_GOOGLE_CLIENT_SECRET", None) or getattr(s, "GOOGLE_CLIENT_SECRET", None)
    if not cid or not csec:
        raise RuntimeError("Google OAuth client not configured (check env OAUTH_GOOGLE_CLIENT_ID/_SECRET)")
    return cid, csec


def _auth_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


# ------------------------ token refresh (fixed) ------------------------
async def refresh_google_token(google_account: GoogleAccount, db: Session) -> str:
    """
    Refresh Google access token IF expired (with a 5-minute buffer).
    - Uses google_account.refresh_token (previously code used access_token by mistake).
    - Persists new access/refresh tokens + expires_at.
    """
    # If we don't know expiry, force refresh once (if refresh_token exists)
    expires_at = float(google_account.expires_at or 0)
    needs_refresh = True
    if expires_at > 0:
        needs_refresh = (_now_ts() >= (expires_at - 300))  # refresh if within 5 minutes

    if not needs_refresh:
        return google_account.access_token

    if not google_account.refresh_token:
        logger.error("No refresh_token stored; cannot refresh access token.")
        raise HTTPException(status_code=401, detail="Missing refresh token; please re-connect Google")

    client_id, client_secret = _get_google_oauth_client()

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": google_account.refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        resp = requests.post(token_url, data=data, timeout=30)
        logger.info("GOOGLE_REFRESH_RESP status=%s body=%s", resp.status_code, resp.text[:500])

        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail=f"Google token refresh failed: {resp.text}")

        token_data = resp.json()
        new_access = token_data.get("access_token")
        if not new_access:
            raise HTTPException(status_code=401, detail="Google refresh returned no access_token")

        google_account.access_token = new_access

        # expires_in is seconds from now
        expires_in = token_data.get("expires_in", 3600)
        google_account.expires_at = _now_ts() + float(expires_in)

        # Sometimes a new refresh_token is returned; if so, persist it
        new_refresh = token_data.get("refresh_token")
        if new_refresh:
            google_account.refresh_token = new_refresh

        db.add(google_account)
        db.commit()

        return new_access

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Token refresh error: %s", e)
        raise HTTPException(status_code=401, detail="Google token refresh failed")


# ------------------------------ Gmail ------------------------------
@router.get("/gmail/emails")
async def get_gmail_emails(
    request: Request,
    max_results: int = 10,
    db: Session = Depends(get_db),
):
    """Get recent emails from user's Gmail"""
    user = await get_current_user(request, db)

    google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    if not google_account:
        raise HTTPException(status_code=400, detail="Google account not connected")

    try:
        access_token = await refresh_google_token(google_account, db)
        headers = _auth_headers(access_token)

        # List messages
        messages_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        params = {"maxResults": max_results}
        response = requests.get(messages_url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch emails: {response.text}")

        messages_data = response.json()
        emails: List[Dict[str, Any]] = []
        
        # Fetch details for each message (format=metadata + headers to be light)
        for msg in messages_data.get("messages", []):
            message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}"
            msg_response = requests.get(
                message_url,
                headers=headers,
                params={"format": "full"},
                timeout=30,
            )
            if msg_response.status_code != 200:
                logger.warning("Failed to fetch message %s: %s", msg["id"], msg_response.text)
                continue

            msg_data = msg_response.json()
            email_info = {
                "id": msg_data.get("id"),
                "threadId": msg_data.get("threadId"),
                "snippet": msg_data.get("snippet", ""),
                "internalDate": msg_data.get("internalDate"),
                "labels": msg_data.get("labelIds", []),
            }

            # Extract headers
            headers_map = {}
            for h in (msg_data.get("payload", {}) or {}).get("headers", []):
                name = h.get("name")
                value = h.get("value")
                if name and value is not None:
                    headers_map[name] = value

            email_info.update({
                "subject": headers_map.get("Subject", ""),
                "from": headers_map.get("From", ""),
                "to": headers_map.get("To", ""),
                "date": headers_map.get("Date", ""),
            })
            emails.append(email_info)

        return {
            "user_email": user.email,
            "total_emails": len(emails),
            "emails": emails,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Gmail API error")
        raise HTTPException(status_code=500, detail=f"Failed to fetch Gmail data: {str(e)}")


@router.get("/gmail/labels")
async def get_gmail_labels(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get Gmail labels/folders"""
    user = await get_current_user(request, db)

    google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    if not google_account:
        raise HTTPException(status_code=400, detail="Google account not connected")

    try:
        access_token = await refresh_google_token(google_account, db)
        headers = _auth_headers(access_token)

        labels_url = "https://gmail.googleapis.com/gmail/v1/users/me/labels"
        response = requests.get(labels_url, headers=headers, timeout=30)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch labels: {response.text}")

        labels_data = response.json()
        return {
            "user_email": user.email,
            "labels": labels_data.get("labels", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Gmail labels error")
        raise HTTPException(status_code=500, detail=f"Failed to fetch Gmail labels: {str(e)}")


# ---------------------------- Calendar ----------------------------
@router.get("/calendar/events")
async def get_calendar_events(
    request: Request,
    days: int = 7,
    db: Session = Depends(get_db),
):
    """Get Google Calendar events for the next N days."""
    user = await get_current_user(request, db)

    google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    if not google_account:
        raise HTTPException(status_code=400, detail="Google account not connected")

    try:
        access_token = await refresh_google_token(google_account, db)
        headers = _auth_headers(access_token)

        # Time range in RFC3339 / UTC
        now = datetime.now(timezone.utc)
        time_min = now.isoformat().replace("+00:00", "Z")
        time_max = (now + timedelta(days=days)).isoformat().replace("+00:00", "Z")

        calendar_url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 50,
        }

        response = requests.get(calendar_url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch calendar events: {response.text}")

        events_data = response.json()
        events: List[Dict[str, Any]] = []

        for event in events_data.get("items", []):
            events.append({
                "id": event.get("id"),
                "summary": event.get("summary", "No title"),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "creator": event.get("creator", {}),
                "organizer": event.get("organizer", {}),
                "start": event.get("start", {}),
                "end": event.get("end", {}),
                "status": event.get("status", ""),
                "htmlLink": event.get("htmlLink", ""),
                "created": event.get("created", ""),
                "updated": event.get("updated", ""),
            })

        return {
            "user_email": user.email,
            "time_range": {"from": time_min, "to": time_max, "days": days},
            "total_events": len(events),
            "events": events,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Calendar API error")
        raise HTTPException(status_code=500, detail=f"Failed to fetch calendar data: {str(e)}")


@router.get("/calendar/calendars")
async def get_calendar_list(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get list of user's calendars"""
    user = await get_current_user(request, db)

    google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    if not google_account:
        raise HTTPException(status_code=400, detail="Google account not connected")

    try:
        access_token = await refresh_google_token(google_account, db)
        headers = _auth_headers(access_token)

        calendars_url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
        response = requests.get(calendars_url, headers=headers, timeout=30)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch calendars: {response.text}")

        calendars_data = response.json()
        return {
            "user_email": user.email,
            "calendars": calendars_data.get("items", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Calendar list error")
        raise HTTPException(status_code=500, detail=f"Failed to fetch calendar list: {str(e)}")


# ---------------------- Full profile & admin ----------------------
@router.get("/full-profile")
async def get_full_user_profile(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get complete user profile with Gmail and Calendar availability summary."""
    user = await get_current_user(request, db)
    google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()

    profile_data: Dict[str, Any] = {
        "user_info": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
        },
        "google_connected": google_account is not None,
        "gmail_data_available": False,
        "calendar_data_available": False,
        "google_scopes": [],
    }

    if google_account:
        try:
            access_token = await refresh_google_token(google_account, db)
            headers = _auth_headers(access_token)

            # Check Gmail available
            gmail_response = requests.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params={"maxResults": 1},
                timeout=20,
            )
            profile_data["gmail_data_available"] = gmail_response.status_code == 200

            # Check Calendar available
            cal_response = requests.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers=headers,
                params={"maxResults": 1},
                timeout=20,
            )
            profile_data["calendar_data_available"] = cal_response.status_code == 200

            if google_account.scope:
                profile_data["google_scopes"] = google_account.scope.split()

        except Exception as e:
            logger.exception("Profile check error: %s", e)

    return profile_data


@router.get("/admin/{user_id}/gmail-calendar")
async def admin_get_user_gmail_calendar(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Admin endpoint to get Gmail and Calendar data summary for any user.
    NOTE: This is a simplistic admin check; improve for production.
    """
    admin_user = await get_current_user(request, db)
    if "admin" not in (admin_user.email or "").lower():
        raise HTTPException(status_code=403, detail="Admin access required")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    emails = await get_gmail_emails_internal(target_user, db, max_results=5)
    events = await get_calendar_events_internal(target_user, db, days=30)

    return {
        "user": {"id": target_user.id, "email": target_user.email, "name": target_user.name},
        "gmail_summary": emails,
        "calendar_summary": events,
    }


# -------------------- internal summary helpers --------------------
async def get_gmail_emails_internal(user: User, db: Session, max_results: int = 5) -> Dict[str, Any]:
    google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    if not google_account:
        return {"error": "Google account not connected", "available": False}

    try:
        access_token = await refresh_google_token(google_account, db)
        headers = _auth_headers(access_token)

        response = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers=headers,
            params={"maxResults": max_results},
            timeout=20,
        )
        if response.status_code == 200:
            data = response.json()
            return {"total_emails": len(data.get("messages", [])), "available": True}
        else:
            return {"error": f"Gmail: {response.text}", "available": False}

    except Exception as e:
        return {"error": str(e), "available": False}


async def get_calendar_events_internal(user: User, db: Session, days: int = 30) -> Dict[str, Any]:
    google_account = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first()
    if not google_account:
        return {"error": "Google account not connected", "available": False}

    try:
        access_token = await refresh_google_token(google_account, db)
        headers = _auth_headers(access_token)

        now = datetime.now(timezone.utc)
        time_min = now.isoformat().replace("+00:00", "Z")
        time_max = (now + timedelta(days=days)).isoformat().replace("+00:00", "Z")

        response = requests.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            params={"timeMin": time_min, "timeMax": time_max, "maxResults": 10},
            timeout=20,
        )

        if response.status_code == 200:
            events_data = response.json()
            return {"total_events": len(events_data.get("items", [])), "available": True}
        else:
            return {"error": f"Calendar: {response.text}", "available": False}

    except Exception as e:
        return {"error": str(e), "available": False}
