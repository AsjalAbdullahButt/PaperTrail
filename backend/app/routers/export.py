"""Data export: a user downloads all of their own data as a ZIP.

Contains documents.json, queries.json, highlights.json, and (when originals are
stored) the raw uploaded files. Rate limited to once per hour per user."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import ChatHistory, Document, User
from ..ratelimit import export_limit, limiter
from ..storage import StorageNotFoundError, storage

router = APIRouter(prefix="/api/export", tags=["export"])


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


@router.get("/my-data")
@limiter.limit(export_limit)
def export_my_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = db.execute(
        select(Document).where(
            Document.user_id == current_user.id, Document.deleted_at.is_(None)
        )
    ).scalars().all()
    queries = db.execute(
        select(ChatHistory).where(
            ChatHistory.user_id == current_user.id, ChatHistory.deleted_at.is_(None)
        )
    ).scalars().all()

    documents_json = [
        {
            "id": d.id, "filename": d.filename, "file_type": d.file_type,
            "page_count": d.page_count, "word_count": d.word_count,
            "version_number": d.version_number, "created_at": _iso(d.created_at),
        }
        for d in docs
    ]
    queries_json = [
        {
            "id": q.id, "question": q.question, "answer": q.answer, "mode": q.mode,
            "confidence_score": q.confidence_score, "bookmarked": q.bookmarked,
            "sources": json.loads(q.sources_json) if q.sources_json else [],
            "created_at": _iso(q.created_at),
        }
        for q in queries
    ]
    highlights_json = [
        {"document_id": d.id, "filename": d.filename,
         "highlights": json.loads(d.highlights_json) if d.highlights_json else []}
        for d in docs
    ]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("documents.json", json.dumps(documents_json, indent=2))
        zf.writestr("queries.json", json.dumps(queries_json, indent=2))
        zf.writestr("highlights.json", json.dumps(highlights_json, indent=2))
        for d in docs:
            if d.storage_key:
                try:
                    data = storage.get(d.storage_key)
                except StorageNotFoundError:
                    continue
                zf.writestr(f"files/{d.id}_{d.filename}", data)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="papertrail-export.zip"'},
    )
