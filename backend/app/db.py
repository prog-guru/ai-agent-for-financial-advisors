# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, scoped_session
from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    API_V1: str = "/api"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data.db")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")
    HUBSPOT_CLIENT_ID: str = os.getenv("HUBSPOT_CLIENT_ID", "")
    HUBSPOT_CLIENT_SECRET: str = os.getenv("HUBSPOT_CLIENT_SECRET", "")
    HUBSPOT_REDIRECT_URI:  str = os.getenv("HUBSPOT_REDIRECT_URI", "")
    HUBSPOT_SCOPES:  str = os.getenv("HUBSPOT_SCOPES", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OAUTH_GOOGLE_CLIENT_ID: str = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "")
    OAUTH_GOOGLE_CLIENT_SECRET: str = os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "")
    OAUTH_REDIRECT_URL: str = os.getenv("OAUTH_REDIRECT_URL", "")


    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    return Settings()

class Base(DeclarativeBase):
    pass

def get_engine():
    db_url = get_settings().DATABASE_URL
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    return create_engine(db_url, echo=False, future=True, connect_args=connect_args)

engine = get_engine()
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
