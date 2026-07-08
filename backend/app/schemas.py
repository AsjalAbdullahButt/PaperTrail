"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth ---
class UserCreate(BaseModel):
    """Login/registration credentials. ``display_name`` is optional (register)."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    display_name: str | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Documents ---
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: str
    page_count: int | None = None
    created_at: datetime
    chunk_count: int | None = None


class UploadResult(BaseModel):
    id: str
    filename: str
    chunks_created: int


class DeleteResult(BaseModel):
    id: str
    deleted: bool


# --- Query ---
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    mode: str = Field("rag", pattern="^(rag|direct)$")


class SourceOut(BaseModel):
    n: int  # citation number [1], [2], ...
    title: str  # filename
    snippet: str
    score: float  # similarity as a percentage (0-100)
    document_id: str
    chunk_index: int


class QueryResponse(BaseModel):
    answer: str
    mode: str
    sources: list[SourceOut]


# --- Chat history ---
class ChatHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    answer: str
    mode: str
    created_at: datetime


class ChatHistoryPage(BaseModel):
    """Paginated, newest-first chat history."""

    items: list[ChatHistoryOut]
    total: int
    limit: int
    offset: int
