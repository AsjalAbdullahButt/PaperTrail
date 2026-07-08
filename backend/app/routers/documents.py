"""Document upload / listing / deletion routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import llm
from ..auth import get_current_user
from ..cache import cache, user_prefix
from ..config import settings
from ..database import get_db
from ..ratelimit import limiter, upload_limit
from ..ingestion import (
    SUPPORTED_TYPES,
    chunk_text,
    extract_text,
    file_type_from_name,
    sniff_content_ok,
)
from ..models import Chunk, Document, User
from ..schemas import DeleteResult, DocumentOut, UploadResult

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResult)
@limiter.limit(upload_limit)
async def upload_document(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ingest one document: extract -> chunk -> embed -> persist."""
    filename = file.filename or "untitled"
    file_type = file_type_from_name(filename)
    if file_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{file_type}'. Allowed: "
            + ", ".join(sorted(SUPPORTED_TYPES)),
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Enforce a hard, config-driven upload ceiling.
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum upload size of "
            f"{settings.max_upload_mb} MB.",
        )

    # Validate the actual content (magic bytes / decodability), not just the
    # extension — a .pdf that isn't a PDF, or a binary blob renamed .txt, is
    # rejected here rather than corrupting the corpus.
    if not sniff_content_ok(data, file_type):
        raise HTTPException(
            status_code=422,
            detail=f"File content does not match a valid .{file_type} file.",
        )

    try:
        text, page_count = extract_text(data, file_type)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not read file: {exc}")

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in the document.",
        )

    # One embedding per chunk, batched inside llm.embed_texts.
    embeddings = llm.embed_texts(chunks)
    if len(embeddings) != len(chunks):
        raise HTTPException(status_code=500, detail="Embedding count mismatch.")

    document = Document(
        user_id=current_user.id,
        filename=filename,
        file_type=file_type,
        page_count=page_count,
    )
    db.add(document)
    db.flush()  # assign document.id before creating chunk rows

    for idx, (content, embedding) in enumerate(zip(chunks, embeddings)):
        db.add(
            Chunk(
                document_id=document.id,
                chunk_index=idx,
                content=content,
                embedding=json.dumps(embedding),
            )
        )

    db.commit()
    db.refresh(document)

    # The user's document set changed -> drop their cached query answers.
    cache.invalidate_prefix(user_prefix(current_user.id))

    return UploadResult(
        id=document.id, filename=document.filename, chunks_created=len(chunks)
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

    db.execute(delete(Chunk).where(Chunk.document_id == document_id))
    db.delete(document)
    db.commit()

    # The user's document set changed -> drop their cached query answers so a
    # deleted document can never resurface via a cached RAG response.
    cache.invalidate_prefix(user_prefix(current_user.id))

    return DeleteResult(id=document_id, deleted=True)
