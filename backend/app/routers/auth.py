# app/routers/auth.py
from fastapi import APIRouter, Depends, Request, HTTPException, status, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from authlib.integrations.base_client.errors import MismatchingStateError
import logging, json
from urllib.parse import urlparse, parse_qs, urlencode
from typing import Optional

from ..db import get_db
from ..oauth import get_oauth
from ..models import User, GoogleAccount
from ..security import make_session_jwt, verify_session_jwt
from ..db import get_settings as get_app_settings

router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_COOKIE = "session"

# ---------- logger ----------
logger = logging.getLogger("auth")
if not logger.handlers:
    h = logging.StreamHandler()
    f = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    h.setFormatter(f)
    logger.addHandler(h)
logger.setLevel(logging.INFO)

# ---------- WORKING SOLUTION: Pass token via URL parameter ----------
@router.get("/google/login")
async def google_login(request: Request):
    oauth = get_oauth()
    redirect_uri = build_callback_url(request)
    
    logger.info("GOOGLE_LOGIN_START: redirect_uri=%s", redirect_uri)
    return await oauth.google.authorize_redirect(request, redirect_uri, access_type="offline", prompt="consent", include_granted_scopes="true")

def build_callback_url(request: Request) -> str:
    url = request.url_for("google_callback")
    if url.scheme not in ("http", "https"):
        url = url.replace(scheme="http")
    return str(url)

@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Google OAuth callback - WORKING VERSION that passes token to frontend
    """
    oauth = get_oauth()
    
    logger.info("=== GOOGLE CALLBACK STARTED ===")

    try:
        token = await oauth.google.authorize_access_token(request)
        if not token:
            raise HTTPException(status_code=400, detail="No token received")
            
    except Exception as e:
        logger.error("GOOGLE_AUTH_FAILED: %s", str(e))
        raise HTTPException(status_code=400, detail="Authentication failed")

    # Get user info
    userinfo = token.get("userinfo")
    if not userinfo:
        try:
            resp = await oauth.google.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
            userinfo = resp.json()
        except Exception as e:
            logger.error("USERINFO_FAILED: %s", str(e))
            raise HTTPException(status_code=400, detail="Failed to get user info")

    sub = userinfo.get("sub")
    email = userinfo.get("email", "")
    name = userinfo.get("name", "")
    picture = userinfo.get("picture", "")

    if not sub:
        raise HTTPException(status_code=400, detail="Invalid user info")

    # Create/update user in database
    try:
        user = db.query(User).filter(User.sub == sub).one_or_none()
        if not user:
            user = User(sub=sub, email=email, name=name, picture=picture)
            db.add(user)
            db.flush()
            logger.info("USER_CREATED: id=%s, email=%s", user.id, email)
        else:
            user.email = email
            user.name = name
            user.picture = picture
            logger.info("USER_UPDATED: id=%s, email=%s", user.id, email)

        # Update Google account
        ga = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).one_or_none()
        if not ga:
            ga = GoogleAccount(
                user_id=user.id,
                access_token=token["access_token"],
                refresh_token=token.get("refresh_token", ""),
                token_type=token.get("token_type", "Bearer"),
                expires_at=token.get("expires_at"),
                scope=token.get("scope", ""),
                raw_token=json.dumps(token) if isinstance(token, dict) else str(token),
            )
            db.add(ga)
        else:
            ga.access_token = token["access_token"]
            if token.get("refresh_token"):
                ga.refresh_token = token["refresh_token"]

        print("!!!!!!!!!!!!!!!!!!=> refresh token: ", ga.refresh_token)
        db.commit()
        logger.info("DATABASE_SAVED: user_id=%s", user.id)
        
        # Auto-sync Gmail data in background
        background_tasks.add_task(auto_sync_gmail_data, user.id)
        logger.info("AUTO_SYNC_STARTED: user_id=%s", user.id)

    except Exception as e:
        db.rollback()
        logger.error("DATABASE_ERROR: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to save user data")

    # === WORKING SOLUTION: Pass JWT token to frontend via URL parameter ===
    frontend = get_app_settings().CORS_ORIGINS.split(",")[0].strip()
    jwt_token = make_session_jwt(sub=user.sub, email=user.email, name=user.name, picture=user.picture)
    
    # URL encode the token
    import urllib.parse
    encoded_token = urllib.parse.quote(jwt_token)
    
    # Redirect to frontend with token as URL parameter
    redirect_url = f"{frontend}/auth-callback?token={encoded_token}&user_id={user.id}"
    
    logger.info("REDIRECTING_WITH_TOKEN: frontend=%s, token_length=%s", frontend, len(jwt_token))
    
    resp = RedirectResponse(url=redirect_url, status_code=302)
    
    # ALSO try to set cookie (might work in some cases)
    try:
        _set_session_cookie(resp, jwt_token, frontend, request)
        logger.info("COOKIE_SET_ATTEMPTED")
    except Exception as e:
        logger.warning("COOKIE_SET_FAILED: %s", str(e))
    
    return resp

def _set_session_cookie(resp: RedirectResponse, value: str, frontend_origin: str, request: Request):
    """Try to set cookie - might work in same domain setups"""
    cookie_options = {
        "key": SESSION_COOKIE,
        "value": value,
        "httponly": False,  # Set to False so frontend can read it if needed
        "samesite": "lax",
        "secure": False,    # False for localhost
        "path": "/",
        "max_age": 60 * 60 * 24 * 30,
    }
    
    # For localhost, don't set domain
    frontend_parsed = urlparse(frontend_origin)
    if frontend_parsed.hostname not in ["localhost", "127.0.0.1"]:
        cookie_options["domain"] = frontend_parsed.hostname
    
    resp.set_cookie(**cookie_options)

@router.post("/session")
async def create_session(request: Request, db: Session = Depends(get_db)):
    """
    Create session from JWT token and return user details
    """
    try:
        data = await request.json()
        token = data.get('token')
        
        if not token:
            raise HTTPException(status_code=400, detail="No token provided")
        
        # Verify the token
        user_data = verify_session_jwt(token)
        if not user_data:
            raise HTTPException(status_code=400, detail="Invalid token")
        
        # Get user from database to ensure they exist and get latest data
        user = db.query(User).filter(User.sub == user_data["sub"]).first()
        if not user:
            raise HTTPException(status_code=400, detail="User not found")
        
        # Check if user has Google account connected
        has_google = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first() is not None
        
        # Prepare user response data
        user_response = {
            "authenticated": True,
            "user": {
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "sub": user.sub
            },
            "google_connected": has_google
        }
        
        # Set session cookie
        resp = JSONResponse({
            "status": "success",
            "user": user_response
        })
        
        resp.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
            max_age=60 * 60 * 24 * 30,
        )
        
        logger.info("SESSION_CREATED_FROM_TOKEN: user_id=%s, email=%s", user.id, user.email)
        return resp
        
    except Exception as e:
        logger.error("SESSION_CREATION_FAILED: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to create session")
        
@router.get("/me")
def get_current_user_info(request: Request, db: Session = Depends(get_db)):
    """
    Check if user is authenticated
    """
    token = request.cookies.get(SESSION_COOKIE)
    
    logger.info("/ME_CALLED: has_cookie=%s, cookie_value=%s", bool(token), token[:20] + "..." if token else "None")
    
    if not token:
        return JSONResponse(
            {"authenticated": False}, 
            status_code=200
        )

    data = verify_session_jwt(token)
    if not data:
        return JSONResponse(
            {"authenticated": False}, 
            status_code=200
        )

    user = db.query(User).filter(User.sub == data["sub"]).one_or_none()
    if not user:
        return JSONResponse(
            {"authenticated": False}, 
            status_code=200
        )

    has_google = db.query(GoogleAccount).filter(GoogleAccount.user_id == user.id).first() is not None

    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email, 
            "name": user.name, 
            "picture": user.picture, 
            "sub": user.sub,
        },
        "google_connected": has_google,
    }

@router.post("/logout")
def logout():
    """
    Logout user
    """
    frontend = get_app_settings().CORS_ORIGINS.split(",")[0].strip()
    resp = JSONResponse({"status": "logged_out"})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp

# Debug endpoints
@router.get("/debug/cookies")
def debug_cookies(request: Request):
    return {
        "cookies": dict(request.cookies),
        "session_cookie": request.cookies.get(SESSION_COOKIE),
        "headers": dict(request.headers)
    }

@router.get("/debug/create-test-session")
def create_test_session():
    """Manually create a test session"""
    test_jwt = make_session_jwt(
        sub="test-sub-123",
        email="test@example.com", 
        name="Test User", 
        picture=""
    )
    
    resp = JSONResponse({"status": "test_session_created"})
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=test_jwt,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=60 * 60 * 24 * 30,
    )
    return resp

async def auto_sync_gmail_data(user_id: int):
    """Auto-sync Gmail data after OAuth connection"""
    try:
        from ..services.data_sync import data_sync_service
        from ..db import get_db
        
        with next(get_db()) as db:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                count = await data_sync_service.sync_gmail_emails(db, user, max_emails=20)
                logger.info(f"AUTO_SYNC_COMPLETED: user_id={user_id}, emails={count}")
    except Exception as e:
        logger.error(f"AUTO_SYNC_FAILED: user_id={user_id}, error={e}")