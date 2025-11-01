# app/models.py
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, DateTime, JSON, Integer, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from .db import Base
from pgvector.sqlalchemy import Vector
import uuid

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

Role = Literal["user", "assistant", "system"]

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sub: Mapped[str] = mapped_column(String(128), unique=True, index=True)  # Google subject
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    picture: Mapped[str] = mapped_column(String(512), default="")

    google_account: Mapped[Optional["GoogleAccount"]] = relationship(back_populates="user", uselist=False)
    hubspot_accounts: Mapped[List["HubspotAccount"]] = relationship(back_populates="user")
    messages: Mapped[List["Message"]] = relationship(back_populates="user")
    meetings: Mapped[List["Meeting"]] = relationship(back_populates="user")

class GoogleAccount(Base):
    __tablename__ = "google_accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    token_type: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[float] = mapped_column()  # epoch seconds
    scope: Mapped[str] = mapped_column(Text)
    raw_token: Mapped[Dict[str, Any]] = mapped_column(JSON)

    user: Mapped["User"] = relationship(back_populates="google_account")

class HubspotAccount(Base):
    __tablename__ = "hubspot_accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(String)
    expires_in: Mapped[Optional[int]] = mapped_column(Integer)
    hubspot_user_id: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="hubspot_accounts")

class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), index=True)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="messages")

class Meeting(Base):
    __tablename__ = "meetings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255))
    start_iso: Mapped[str] = mapped_column(String(64))
    end_iso: Mapped[str] = mapped_column(String(64))
    attendees: Mapped[Dict[str, Any]] = mapped_column(JSON)  # {people: [{id,name,avatar?}]}

    user: Mapped["User"] = relationship(back_populates="meetings")

class GmailEmail(Base):
    __tablename__ = "gmail_emails"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    gmail_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    thread_id: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(Text)
    sender: Mapped[str] = mapped_column(String(512))
    recipient: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    snippet: Mapped[str] = mapped_column(Text)
    date_sent: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    labels: Mapped[Dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship()

class HubspotContact(Base):
    __tablename__ = "hubspot_contacts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    hubspot_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(512), index=True)
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(512))
    phone: Mapped[str] = mapped_column(String(50))
    properties: Mapped[Dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship()
    notes: Mapped[List["HubspotNote"]] = relationship(back_populates="contact")

class HubspotNote(Base):
    __tablename__ = "hubspot_notes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("hubspot_contacts.id"), nullable=False, index=True)
    hubspot_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship()
    contact: Mapped["HubspotContact"] = relationship(back_populates="notes")

class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)  # 'gmail' or 'hubspot'
    source_id: Mapped[str] = mapped_column(String(255), index=True)  # gmail_id or hubspot_id
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Vector] = mapped_column(Vector(384))  # sentence-transformers dimension
    meta_data: Mapped[Dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship()

class AgentTask(Base):
    __tablename__ = "agent_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, in_progress, waiting_response, completed, failed
    context: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship()

class AgentInstruction(Base):
    __tablename__ = "agent_instructions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    instruction: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship()

# Pydantic models (for API schemas)
class Person(BaseModel):
    id: str
    name: str
    avatar: Optional[str] = None

class MeetingOut(BaseModel):
    id: int
    title: str
    start_iso: str
    end_iso: str
    attendees: Dict[str, Any]  # { "people": Person[] }

class MeetingCreate(BaseModel):
    title: str
    start_iso: str   # ISO 8601 e.g. "2025-11-01T15:00:00Z"
    end_iso: str
    attendees: Dict[str, Any]  # { "people": [{ "id": "...", "name": "...", "avatar"?: "..." }] }

class MessageOut(BaseModel):
    id: int
    role: Role
    content: str
    created_at: datetime

class MessageIn(BaseModel):
    role: Role = Field("user")
    content: str

class ChatSendResponse(BaseModel):
    messages: List[MessageOut]
    meetings: List[MeetingOut]

class UserSummary(BaseModel):
    id: int
    email: str
    name: str
    sub: str
    created_meetings: int
    sent_messages: int
    has_google: bool
    has_hubspot: bool

class GoogleAccountDetail(BaseModel):
    user_id: int
    user_email: str
    user_name: str
    scopes: str
    expires_at: datetime

class HubspotAccountDetail(BaseModel):
    user_id: int
    user_email: str
    user_name: str
    hubspot_user_id: Optional[str]
    access_token: str
    refresh_token: Optional[str]
    expires_in: Optional[int]
    created_at: datetime
    updated_at: datetime

class UserMessages(BaseModel):
    user_id: int
    user_email: str
    messages: List[Dict[str, Any]]

class UserMeetings(BaseModel):
    user_id: int
    user_email: str
    meetings: List[Dict[str, Any]]

class AdminStats(BaseModel):
    total_users: int
    total_messages: int
    total_meetings: int
    google_connected_users: int
    hubspot_connected_users: int
    active_today: int

class AgentTaskOut(BaseModel):
    id: int
    description: str
    status: str
    context: Dict[str, Any]
    result: Optional[str]
    created_at: datetime
    updated_at: datetime

class AgentTaskCreate(BaseModel):
    description: str
    context: Dict[str, Any] = Field(default_factory=dict)

class AgentInstructionOut(BaseModel):
    id: int
    instruction: str
    is_active: bool
    created_at: datetime

class AgentInstructionCreate(BaseModel):
    instruction: str