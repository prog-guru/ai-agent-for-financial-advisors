# app/routers/hubspot.py
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import os, time, base64, json, urllib.parse
import httpx
import logging

from ..db import get_db
from ..models import User, HubspotAccount  # keep your casing as-is
from ..security import verify_session_jwt
from ..db import get_settings as get_app_settings

router = APIRouter(prefix="/hubspot", tags=["hubspot"])
logger = logging.getLogger("hubspot")
logger.setLevel(logging.INFO)

SESSION_COOKIE = "session"
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"


# ------------- helpers -------------
def _env():
    s = get_app_settings()
    # Prefer env for safety; fall back to settings if present there
    client_id = os.getenv("HUBSPOT_CLIENT_ID", getattr(s, "HUBSPOT_CLIENT_ID", ""))
    client_secret = os.getenv("HUBSPOT_CLIENT_SECRET", getattr(s, "HUBSPOT_CLIENT_SECRET", ""))
    redirect_uri = os.getenv("HUBSPOT_REDIRECT_URI", getattr(s, "HUBSPOT_REDIRECT_URI", ""))
    scopes = os.getenv(
        "HUBSPOT_SCOPES",
        getattr(s, "HUBSPOT_SCOPES", ""),
    )
    return client_id, client_secret, redirect_uri, scopes


def _require_user(request: Request, db: Session) -> User:
    tok = request.cookies.get(SESSION_COOKIE)
    data = verify_session_jwt(tok) if tok else None
    if not data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.sub == data["sub"]).one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def _exchange_code_for_token(code: str, redirect_uri: str, client_id: str, client_secret: str) -> dict:
    """
    Exchange HubSpot OAuth code -> access/refresh tokens with rich diagnostics.

    Requirements:
      - Authorization: Basic base64(client_id:client_secret)
      - Content-Type: application/x-www-form-urlencoded;charset=utf-8
      - Body: grant_type=authorization_code & code & redirect_uri
      - redirect_uri MUST exactly match the one configured in your HubSpot app
        AND the one used during /connect (authorize) step.
    """
    
    
    # --- 0) Sanity checks (fail fast with clear messages)
    cfg_redirect = os.getenv("HUBSPOT_REDIRECT_URI", "").strip()
    problems = []
    if not code:
        problems.append("missing code")
    if not client_id:
        problems.append("missing client_id")
    if not client_secret:
        problems.append("missing client_secret")
    if not redirect_uri:
        problems.append("missing redirect_uri")
    if cfg_redirect and redirect_uri != cfg_redirect:
        problems.append(f"redirect_uri mismatch (passed='{redirect_uri}' != env='{cfg_redirect}')")
    if problems:
        logger.error("HS_TOKEN_INPUT_ERROR %s", json.dumps({"problems": problems}))
        raise HTTPException(status_code=400, detail="HubSpot token exchange: invalid input/config (see server logs)")

    # --- 1) Build request
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret
    }

    # --- 2) Call HubSpot
    async with httpx.AsyncClient(timeout=30) as client:
        print("posting...")
        print(HUBSPOT_TOKEN_URL)
        print(data)
        print(headers)
        resp = await client.post(HUBSPOT_TOKEN_URL, data=data, headers=headers)
        text = resp.text
        status = resp.status_code

    # Log response (truncate to keep logs tidy, never log secrets)
    print(
        "HS_TOKEN_RESP ",
        json.dumps({
            "status": status,
            "body": text[:800],
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        })
    )

    # --- 3) Handle errors with actionable hints
    if status != 200:
        # HubSpot often returns JSON like:
        # {"error":"INVALID_CLIENT", "error_description":"client_id ..."} OR
        # {"message":"MISSING_OR_INVALID_AUTH_CODE"} OR
        # {"message":"redirect_uri does not match registered value"} etc.
        hint = "Failed to exchange code for token."
        try:
            body = resp.json()
        except Exception:
            body = {"raw": text}

        # Heuristics → clearer error
        msg = (body.get("message") or body.get("error_description") or body.get("error") or "").lower()

        if "redirect_uri" in msg and "match" in msg:
            hint = ("Redirect URI mismatch. Ensure the redirect_uri used here, your /connect authorize URL, "
                    "and the HubSpot app's OAuth Redirect URL are EXACTLY identical (scheme/host/port/path/trailing slash).")
        elif "invalid_client" in msg:
            hint = ("INVALID_CLIENT. Check HUBSPOT_CLIENT_ID / HUBSPOT_CLIENT_SECRET belong to the SAME app you authorized, "
                    "and that the secret is correct.")
        elif "missing_or_invalid_auth_code" in msg or "invalid_grant" in msg:
            hint = ("Auth code invalid or already used/expired. Restart the OAuth flow from /hubspot/connect "
                    "and do not refresh the callback URL.")
        elif status == 401:
            hint = ("Unauthorized from HubSpot. Verify Basic auth header and credentials. "
                    "Also confirm the app's Acceptable Use Policy is accepted and app installed to a valid portal.")
        # else keep the generic hint

        logger.error("HS_TOKEN_EXCHANGE_ERROR %s", json.dumps({"status": status, "body": body, "hint": hint}))
        raise HTTPException(status_code=400, detail=hint)

    # --- 4) Success
    try:
        return resp.json()
    except Exception:
        logger.error("HS_TOKEN_PARSE_ERROR %s", text[:800])
        raise HTTPException(status_code=400, detail="Token response parse error")
# ------------- routes -------------
@router.get("/status")
async def hubspot_status(request: Request, db: Session = Depends(get_db)):
    """
    Check if current user has a connected HubSpot account.
    """
    user = _require_user(request, db)
    acc = db.query(HubspotAccount).filter(HubspotAccount.user_id == user.id).one_or_none()
    return {
        "connected": acc is not None,
        # HubSpot returns "hub_id" in token responses; store it as hubspot_user_id in your model
        "account_id": getattr(acc, "hubspot_user_id", None) if acc else None,
        "expires_in": getattr(acc, "expires_in", None) if acc else None,
    }


@router.get("/connect")
async def hubspot_connect(request: Request):
    """
    Start HubSpot OAuth flow by redirecting to HubSpot's authorize URL.
    Uses redirect_uri from env/settings to ensure an exact match.
    """
    client_id, _, redirect_uri, scopes = _env()

    print("client_id", client_id)
    print("_", _)
    print("redirect_uri", redirect_uri)
    print("scopes", scopes)
    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="HubSpot OAuth not configured")

    # Optional: include a small state to mitigate CSRF & correlate user
    state = "init"  # you can put a nonce or user hint here

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,            # must exactly match HubSpot app config
        "scope": scopes,                         # space-delimited
        "state": state,
    }
    url = f"{HUBSPOT_AUTH_URL}?{urllib.parse.urlencode(params)}"
    logger.info("HS_AUTH_URL %s", url)
    return RedirectResponse(url, status_code=302)


@router.get("/callback")
async def hubspot_callback(
    request: Request,
    code: str = Query(None),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    HubSpot OAuth callback: exchange `code` for tokens and upsert the connection row.
    """

    print("Code: ", code)
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code")

    user = _require_user(request, db)
    client_id, client_secret, redirect_uri, _ = _env()

    # Sanity log to troubleshoot mismatches quickly
    print(json.dumps({
        "have_code": True,
        "state": state,
        "redirect_uri_env": redirect_uri,
        "host": request.url.hostname,
    }))

    print("Successfully parsed!")

    if not (client_id and client_secret and redirect_uri):
        raise HTTPException(status_code=500, detail="HubSpot OAuth env not configured")

    # Exchange code -> tokens
    tok = await _exchange_code_for_token(code, redirect_uri, client_id, client_secret)

    print("Token: ", tok)
    access = tok.get("access_token")
    refresh = tok.get("refresh_token", "")
    expires_in = int(tok.get("expires_in", 0))  # seconds
    scope = tok.get("scope", "")
    hub_id = tok.get("hub_id")  # portal (account) ID

    if not access:
        raise HTTPException(status_code=400, detail="Token response missing access_token")

    # Upsert the user connection (keep your model field names)
    acc = db.query(HubspotAccount).filter(HubspotAccount.user_id == user.id).one_or_none()
    if not acc:
        acc = HubspotAccount(
            user_id=user.id,
            hubspot_user_id=str(hub_id) if hub_id else None,
            access_token=access,
            refresh_token=refresh,
            expires_in=expires_in,
        )
        db.add(acc)
    else:
        acc.hubspot_user_id = str(hub_id) if hub_id else acc.hubspot_user_id
        acc.access_token = access
        if refresh:
            acc.refresh_token = refresh
        acc.expires_in = expires_in

    db.commit()
    logger.info("HS_CB_SUCCESS %s", json.dumps({
        "user": user.email,
        "hubspot_user_id": acc.hubspot_user_id,
        "has_refresh_token": bool(acc.refresh_token),
        "expires_in": acc.expires_in,
    }))

    # Redirect back to your frontend
    frontend = get_app_settings().CORS_ORIGINS.split(",")[0].strip()
    return RedirectResponse(url=f"{frontend}/chat?hubspot=connected", status_code=302)


@router.post("/disconnect")
async def hubspot_disconnect(request: Request, db: Session = Depends(get_db)):
    """
    Disconnect HubSpot account for current user (delete stored tokens).
    """
    user = _require_user(request, db)
    db.query(HubspotAccount).filter(HubspotAccount.user_id == user.id).delete()
    db.commit()
    return {"status": "disconnected"}
