"""Document upload / listing / deletion routes."""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import llm
from ..auth import get_current_user
from ..cache import cache, user_prefix
from ..config import settings
from ..database import get_db
from ..ratelimit import limiter, upload_limit
from ..ingestion import chunk_blocks, file_type_from_name
from ..models import Chunk, Document, User
from ..schemas import (
    DeleteResult,
    DocumentOut,
    DocumentStatus,
    Highlight,
    OutlineEntry,
    UploadResult,
)
from ..services import extractor
from ..services.importance import extract_highlights, score_chunks
from ..services.outliner import extract_outline

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger("papertrail.documents")

EMBED_BATCH = 20


def _store_original(data: bytes, user_id: str, file_type: str) -> str | None:
    """Persist the raw upload as uploads/{user_id}/{uuid}.{ext}. Returns the
    path, or None when STORE_ORIGINALS is disabled. The filesystem name is a
    fresh UUID — the user's original filename never touches the path."""
    if not settings.store_originals:
        return None
    user_dir = os.path.join(settings.uploads_dir, user_id)
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"{uuid.uuid4().hex}.{file_type}")
    with open(path, "wb") as fh:
        fh.write(data)
    return path


@router.post("/upload", response_model=UploadResult)
@limiter.limit(upload_limit)
async def upload_document(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ingest one document: extract -> chunk -> score -> embed -> persist.

    Produces per-chunk importance scores, document highlights, and an outline,
    and stores the original upload under the user's private uploads directory.
    """
    filename = file.filename or "untitled"
    file_type = file_type_from_name(filename)
    if file_type not in extractor.SUPPORTED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '.{file_type}'. Allowed: "
            + ", ".join(sorted(extractor.SUPPORTED_TYPES)),
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum upload size of "
            f"{settings.max_upload_mb} MB.",
        )

    # Content must match the extension (magic bytes / decodability).
    if not extractor.validate_content(data, file_type):
        raise HTTPException(
            status_code=422,
            detail=f"File content does not match a valid .{file_type} file.",
        )

    try:
        blocks = extractor.extract_blocks(data, file_type)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not read file: {exc}")

    chunk_dicts = chunk_blocks(blocks)
    if not chunk_dicts:
        raise HTTPException(
            status_code=422, detail="No extractable text found in the document."
        )

    chunk_texts = [c["text"] for c in chunk_dicts]
    scores = score_chunks(chunk_texts)
    highlights = extract_highlights(chunk_texts, scores, n=8)
    outline = extract_outline(blocks, chunk_texts)
    full_text = extractor.blocks_to_text(blocks)

    # Embeddings, batched (llm.embed_texts already batches internally).
    embeddings = llm.embed_texts(chunk_texts)
    if len(embeddings) != len(chunk_texts):
        raise HTTPException(status_code=500, detail="Embedding count mismatch.")

    # Store the original first so a DB failure below can clean it up.
    file_path = _store_original(data, current_user.id, file_type)
    try:
        document = Document(
            user_id=current_user.id,
            filename=filename,
            file_type=file_type,
            page_count=extractor.page_count(blocks) or None,
            word_count=extractor.count_words(full_text),
            file_path=file_path,
            outline_json=json.dumps(outline),
            highlights_json=json.dumps(highlights),
            processed_at=datetime.now(timezone.utc),
        )
        db.add(document)
        db.flush()  # assign document.id before creating chunk rows

        for idx, (cd, embedding) in enumerate(zip(chunk_dicts, embeddings)):
            db.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=cd["text"],
                    embedding=json.dumps(embedding),
                    importance_score=float(scores[idx]) if idx < len(scores) else 0.0,
                    page_number=int(cd.get("page_number", 1)),
                    section_heading=(cd.get("section_heading") or None),
                )
            )
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise

    # The user's document set changed -> drop their cached query answers.
    cache.invalidate_prefix(user_prefix(current_user.id))

    return UploadResult(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        page_count=document.page_count,
        word_count=document.word_count,
        chunks_created=len(chunk_dicts),
        highlights=[Highlight(**h) for h in highlights],
        outline=[OutlineEntry(**o) for o in outline],
    )


@router.get("/{document_id}/status", response_model=DocumentStatus)
def document_status(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Processing status for a document (drives the upload progress bar)."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this document.")
    chunk_count = db.execute(
        select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
    ).scalar_one()
    return DocumentStatus(
        id=document.id,
        filename=document.filename,
        processed=document.processed_at is not None,
        processed_at=document.processed_at,
        chunk_count=int(chunk_count),
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List the current user's documents, newest first, with chunk counts."""
    rows = (
        db.execute(
            select(Document, func.count(Chunk.id))
            .outerjoin(Chunk, Chunk.document_id == Document.id)
            .where(Document.user_id == current_user.id)
            .group_by(Document.id)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    result: list[DocumentOut] = []
    for doc, count in rows:
        out = DocumentOut.model_validate(doc)
        out.chunk_count = int(count)
        result.append(out)
    return result


@router.delete("/{document_id}", response_model=DeleteResult)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and all of its chunks in one transaction.

    Chunks are removed explicitly in application code so retrieval can never
    surface a deleted document's chunks, even if the DB-level ON DELETE
    CASCADE were missing or disabled. The FK cascade remains as
    defense-in-depth, but correctness does not depend on it.

    Ownership rule (consistent across the API): a document that exists but
    belongs to another user returns 403; a document id that does not exist
    returns 404.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this document.")

    stored_path = document.file_path
    db.execute(delete(Chunk).where(Chunk.document_id == document_id))
    db.delete(document)
    db.commit()

    # Remove the original file from disk (best-effort; the DB is source of truth).
    if stored_path and os.path.exists(stored_path):
        try:
            os.remove(stored_path)
        except OSError as exc:  # noqa: BLE001
            logger.warning("Could not delete file %s: %s", stored_path, exc)

    # The user's document set changed -> drop their cached query answers so a
    # deleted document can never resurface via a cached RAG response.
    cache.invalidate_prefix(user_prefix(current_user.id))

    return DeleteResult(id=document_id, deleted=True)
