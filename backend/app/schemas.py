"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Documents ---
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    page_count: int | None = None
    created_at: datetime
    chunk_count: int | None = None


class UploadResult(BaseModel):
    id: int
    filename: str
    chunks_created: int


class DeleteResult(BaseModel):
    id: int
    deleted: bool


# --- Query (Phase 4) ---
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    mode: str = Field("rag", pattern="^(rag|direct)$")


class SourceOut(BaseModel):
    n: int  # citation number [1], [2], ...
    title: str  # filename
    snippet: str
    score: float  # similarity as a percentage (0-100)
    document_id: int
    chunk_index: int


class QueryResponse(BaseModel):
    answer: str
    mode: str
    sources: list[SourceOut]
