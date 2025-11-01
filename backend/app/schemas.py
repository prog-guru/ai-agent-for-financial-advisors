# app/schemas.py
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

# ----- Shared types
Role = Literal["user", "assistant", "system"]

class Person(BaseModel):
    id: str
    name: str
    avatar: Optional[str] = None

# ----- Meetings
class MeetingOut(BaseModel):
    id: int
    title: str
    start_iso: str
    end_iso: str
    attendees: Dict[str, Any]  # { "people": Person[] }

class MeetingCreate(BaseModel):
    title: str
    start_iso: str           # ISO 8601 e.g. "2025-11-01T15:00:00Z"
    end_iso: str
    attendees: Dict[str, Any]  # { "people": [{ id, name, avatar? }] }

# ----- Chat
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
