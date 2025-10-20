# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .db import Base, engine, get_settings, get_db
from .seed import seed
from .routers import health, meetings, chat, auth, hubspot, admin, gmail_calendar

import os

os.environ['HTTP_PROXY'] = 'socks5://14ac63464dbca:b9e059af46@64.84.118.137:12324'
os.environ['HTTPS_PROXY'] = 'socks5://14ac63464dbca:b9e059af46@64.84.118.137:12324'


settings = get_settings()
app = FastAPI(title=getattr(settings, "APP_NAME", "ai-agent-backend"))

# Sessions (required by Authlib for authorize_redirect / callback)
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",   # good for localhost
    https_only=False,  # set True in production behind HTTPS
    max_age=60 * 60 * 24 * 7,  # 7 days is fine for OAuth state
)

# CORS
# origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
origins = [o.strip() for o in os.getenv("CORS_ORIGINS","http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB init + seed
Base.metadata.create_all(bind=engine)
with next(get_db()) as db:
    seed(db)

# Routes
API_V1 = settings.API_V1
app.include_router(auth.router, prefix=API_V1)
app.include_router(health.router, prefix=API_V1)
app.include_router(meetings.router, prefix=API_V1)
app.include_router(chat.router, prefix=API_V1)
app.include_router(hubspot.router, prefix=API_V1)
app.include_router(admin.router, prefix=API_V1)
app.include_router(gmail_calendar.router, prefix=API_V1)
