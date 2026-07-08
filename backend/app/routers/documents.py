"""Document upload / listing / deletion routes."""
from __future__ import annotations

import json
import logging
import os
import re
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
from ..models import (
    Chunk,
    Document,
    DocumentCollection,
    DocumentTag,
    DocumentVersion,
    User,
)
from ..schemas import (
    CoverageCell,
    DeleteResult,
    DocumentOut,
    DocumentStatus,
    DocumentTagsOut,
    Highlight,
    OutlineEntry,
    TagsIn,
    UploadResult,
    VersionOut,
)
from ..services import extractor
from ..services.importance import extract_highlights, score_chunks
from ..services.outliner import extract_outline

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger("papertrail.documents")

EMBED_BATCH = 20
_TAG_RE = re.compile(r"^[a-z0-9-]+$")


def _owned_doc(db: Session, document_id: str, current_user: User) -> Document:
    """Fetch a live document owned by the user (404 if missing, 403 if others')."""
    doc = db.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this document.")
    return doc


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


DUPLICATE_THRESHOLD = 0.92


def _centroid(vectors: list[list[float]]):
    import numpy as np

    arr = np.asarray(vectors, dtype=np.float64)
    return arr.mean(axis=0)


def _detect_duplicate(
    db: Session, user_id: str, new_embeddings: list[list[float]]
) -> tuple[str, str] | None:
    """Compare the new doc's first-10 chunk centroid against every existing
    document's first-10 centroid. Returns (dup_id, dup_name) if cosine > 0.92."""
    import numpy as np

    if not new_embeddings:
        return None
    new_c = _centroid(new_embeddings[:10])
    new_norm = np.linalg.norm(new_c)
    if new_norm == 0:
        return None

    existing = db.execute(
        select(Document.id, Document.filename).where(
            Document.user_id == user_id, Document.deleted_at.is_(None)
        )
    ).all()
    for doc_id, name in existing:
        rows = db.execute(
            select(Chunk.embedding)
            .where(Chunk.document_id == doc_id)
            .order_by(Chunk.chunk_index)
            .limit(10)
        ).scalars().all()
        vecs = [json.loads(e) for e in rows]
        vecs = [v for v in vecs if len(v) == len(new_c)]
        if not vecs:
            continue
        c = _centroid(vecs)
        denom = new_norm * np.linalg.norm(c)
        if denom == 0:
            continue
        sim = float(np.dot(new_c, c) / denom)
        if sim > DUPLICATE_THRESHOLD:
            return doc_id, name
    return None


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

    # Duplicate detection: flag (do not block) near-identical prior uploads.
    dup = _detect_duplicate(db, current_user.id, embeddings)

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
            duplicate_of=(dup[0] if dup else None),
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
        is_duplicate=dup is not None,
        duplicate_of_name=(dup[1] if dup else None),
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
    tag: str | None = Query(None, max_length=50),
    collection_id: str | None = Query(None),
    type: str | None = Query(None, max_length=20),
    search: str | None = Query(None, max_length=200),
):
    """List the current user's documents (newest first) with optional filters:
    by tag, collection, file type, and filename search."""
    stmt = (
        select(Document, func.count(Chunk.id))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .where(Document.user_id == current_user.id, Document.deleted_at.is_(None))
        .group_by(Document.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    )
    if type:
        stmt = stmt.where(Document.file_type == type.lower())
    if search:
        stmt = stmt.where(Document.filename.ilike(f"%{search}%"))
    if tag:
        stmt = stmt.where(
            Document.id.in_(
                select(DocumentTag.document_id).where(DocumentTag.tag == tag)
            )
        )
    if collection_id:
        stmt = stmt.where(
            Document.id.in_(
                select(DocumentCollection.document_id).where(
                    DocumentCollection.collection_id == collection_id
                )
            )
        )
    rows = db.execute(stmt.limit(limit).offset(offset)).all()

    doc_ids = [doc.id for doc, _ in rows]
    tags_by_doc: dict[str, list[str]] = {i: [] for i in doc_ids}
    if doc_ids:
        for did, t in db.execute(
            select(DocumentTag.document_id, DocumentTag.tag).where(
                DocumentTag.document_id.in_(doc_ids)
            )
        ).all():
            tags_by_doc.setdefault(did, []).append(t)
    dup_names = _duplicate_names(db, [doc for doc, _ in rows])

    result: list[DocumentOut] = []
    for doc, count in rows:
        out = DocumentOut.model_validate(doc)
        out.chunk_count = int(count)
        out.tags = sorted(tags_by_doc.get(doc.id, []))
        out.is_duplicate = doc.duplicate_of is not None
        out.duplicate_of_name = dup_names.get(doc.duplicate_of)
        result.append(out)
    return result


def _duplicate_names(db: Session, docs: list[Document]) -> dict[str, str]:
    """Map duplicate_of ids -> filename for the given documents."""
    ids = {d.duplicate_of for d in docs if d.duplicate_of}
    if not ids:
        return {}
    return dict(
        db.execute(
            select(Document.id, Document.filename).where(Document.id.in_(ids))
        ).all()
    )


@router.post("/{document_id}/tags", response_model=DocumentTagsOut)
def add_tags(
    document_id: str,
    payload: TagsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add tags to a document (max 10 total). Tags are alphanumeric + hyphens."""
    doc = _owned_doc(db, document_id, current_user)
    existing = set(
        db.execute(
            select(DocumentTag.tag).where(DocumentTag.document_id == document_id)
        ).scalars().all()
    )
    for raw in payload.tags:
        tag = raw.strip().lower()
        if not tag or not _TAG_RE.match(tag):
            raise HTTPException(
                status_code=422,
                detail="Tags must be alphanumeric with hyphens only.",
            )
        if len(existing) >= 10:
            raise HTTPException(status_code=422, detail="A document can have at most 10 tags.")
        if tag not in existing:
            db.add(DocumentTag(document_id=document_id, tag=tag))
            existing.add(tag)
    db.commit()
    return DocumentTagsOut(document_id=document_id, tags=sorted(existing))


@router.delete("/{document_id}/tags/{tag}", response_model=DocumentTagsOut)
def remove_tag(
    document_id: str,
    tag: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_doc(db, document_id, current_user)
    link = db.get(DocumentTag, {"document_id": document_id, "tag": tag.lower()})
    if link is not None:
        db.delete(link)
        db.commit()
    remaining = sorted(
        db.execute(
            select(DocumentTag.tag).where(DocumentTag.document_id == document_id)
        ).scalars().all()
    )
    return DocumentTagsOut(document_id=document_id, tags=remaining)


@router.post("/{document_id}/upload-version", response_model=DocumentOut)
async def upload_version(
    document_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a new version of an existing document (archives the current file
    reference and bumps version_number)."""
    doc = _owned_doc(db, document_id, current_user)
    file_type = file_type_from_name(file.filename or "")
    if file_type not in extractor.SUPPORTED_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '.{file_type}'.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the maximum upload size.")
    if not extractor.validate_content(data, file_type):
        raise HTTPException(status_code=422, detail="File content does not match its type.")

    # Snapshot the current version, then store the new file and bump the number.
    db.add(
        DocumentVersion(
            document_id=document_id,
            version_number=doc.version_number,
            file_path=doc.file_path,
        )
    )
    new_path = _store_original(data, current_user.id, file_type)
    doc.version_number += 1
    doc.file_path = new_path
    db.commit()
    db.refresh(doc)
    out = DocumentOut.model_validate(doc)
    return out


@router.get("/{document_id}/versions", response_model=list[VersionOut])
def list_versions(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_doc(db, document_id, current_user)
    rows = db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    ).scalars().all()
    return [VersionOut.model_validate(v) for v in rows]


@router.get("/{document_id}/coverage", response_model=list[CoverageCell])
def document_coverage(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-chunk retrieval counts (for the coverage heatmap)."""
    _owned_doc(db, document_id, current_user)
    rows = db.execute(
        select(Chunk.id, Chunk.chunk_index, Chunk.retrieved_count)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    ).all()
    return [
        CoverageCell(chunk_id=cid, chunk_index=idx, retrieved_count=int(rc or 0))
        for cid, idx, rc in rows
    ]


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
