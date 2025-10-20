# app/oauth.py
from authlib.integrations.starlette_client import OAuth
from pydantic_settings import BaseSettings
from functools import lru_cache

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

class OAuthSettings(BaseSettings):
    OAUTH_GOOGLE_CLIENT_ID: str
    OAUTH_GOOGLE_CLIENT_SECRET: str
    OAUTH_REDIRECT_URL: str

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_oauth_settings() -> OAuthSettings:
    return OAuthSettings()

def get_oauth():
    s = get_oauth_settings()
    oauth = OAuth()
    oauth.register(
        name="google",
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_id=s.OAUTH_GOOGLE_CLIENT_ID,
        client_secret=s.OAUTH_GOOGLE_CLIENT_SECRET,
        client_kwargs={
            "scope": "openid email profile https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar",
            "access_type": "offline",
            "prompt": "consent",  # ensure refresh_token on every login in dev
        },
    )
    return oauth
