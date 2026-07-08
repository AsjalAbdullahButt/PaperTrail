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
    word_count: int = 0
    version_number: int = 1
    created_at: datetime
    chunk_count: int | None = None
    tags: list[str] = Field(default_factory=list)
    is_duplicate: bool = False
    duplicate_of_name: str | None = None


class Highlight(BaseModel):
    text: str
    score: float
    chunk_index: int


class OutlineEntry(BaseModel):
    heading: str
    level: int
    chunk_index: int


class UploadResult(BaseModel):
    id: str
    filename: str
    file_type: str
    page_count: int | None = None
    word_count: int = 0
    chunks_created: int
    highlights: list[Highlight] = []
    outline: list[OutlineEntry] = []
    is_duplicate: bool = False
    duplicate_of_name: str | None = None


class DocumentStatus(BaseModel):
    id: str
    filename: str
    processed: bool
    processed_at: datetime | None = None
    chunk_count: int = 0


class DeleteResult(BaseModel):
    id: str
    deleted: bool


# --- Collections / tags / versions (Phase 4) ---
class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    created_at: datetime
    document_count: int | None = None


class CollectionDocumentsIn(BaseModel):
    document_ids: list[str] = Field(..., min_length=1)


class TagsIn(BaseModel):
    tags: list[str] = Field(..., min_length=1, max_length=10)


class DocumentTagsOut(BaseModel):
    document_id: str
    tags: list[str]


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    uploaded_at: datetime


class CoverageCell(BaseModel):
    chunk_id: str
    chunk_index: int
    retrieved_count: int


# --- Query history / bookmarks (Phase 4) ---
class QueryHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    answer: str
    mode: str
    confidence_score: float | None = None
    bookmarked: bool = False
    bookmark_note: str | None = None
    created_at: datetime


class QueryHistoryPage(BaseModel):
    items: list[QueryHistoryOut]
    total: int
    limit: int
    offset: int


class BookmarkIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


# --- Query ---
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field("rag", pattern="^(rag|direct|multihop)$")
    document_ids: list[str] = Field(default_factory=list)
    collection_id: str | None = None


class SourceOut(BaseModel):
    n: int  # citation number [1], [2], ...
    title: str  # filename (document_name)
    snippet: str
    score: float  # relevance as a percentage (0-100) — kept for the UI meter
    document_id: str
    chunk_id: str
    chunk_index: int = 0
    page_number: int = 1
    section_heading: str | None = None
    similarity_score: float = 0.0
    importance_score: float = 0.0
    relevance_pct: int = 0


class UnsupportedSentence(BaseModel):
    sentence: str
    source_chunk_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    mode: str
    sources: list[SourceOut]
    confidence_score: float = 0.0
    followup_questions: list[str] = Field(default_factory=list)
    unsupported_sentences: list[UnsupportedSentence] = Field(default_factory=list)
    query_id: str | None = None


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
