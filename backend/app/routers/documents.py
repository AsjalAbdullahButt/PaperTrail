"""Document upload / listing / deletion routes."""
from __future__ import annotations

import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import llm
from ..auth import get_current_user
from ..cache import cache, user_prefix
from ..config import settings
from ..database import get_db
from ..ratelimit import limiter, upload_limit
from ..ingestion import chunk_blocks, chunk_blocks_semantic, file_type_from_name
from ..models import (
    Chunk,
    Document,
    DocumentCollection,
    DocumentTag,
    DocumentTimeline,
    DocumentVersion,
    User,
)
from ..storage import storage
from ..schemas import (
    CoverageCell,
    DeleteResult,
    DocumentOut,
    DocumentStatus,
    DocumentTagsOut,
    Highlight,
    OutlineEntry,
    TagsIn,
    TimelineEvent,
    UploadResult,
    VersionOut,
)
from ..services import extractor
from ..services.importance import extract_highlights, score_chunks
from ..services.outliner import extract_outline
from ..services.visuals import extract_timeline

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
    """Persist the raw upload as uploads/{user_id}/{uuid}.{ext} via the
    configured storage backend. Returns the storage key, or None when
    STORE_ORIGINALS is disabled. The key uses a fresh UUID — the user's
    original filename never touches it."""
    if not settings.store_originals:
        return None
    key = f"{settings.uploads_dir}/{user_id}/{uuid.uuid4().hex}.{file_type}"
    return storage.put(key, data)


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


def _process_upload(
    db: Session, document: Document, data: bytes, file_type: str
) -> UploadResult:
    """Heavy half of ingestion: extract -> chunk -> score -> embed ->
    duplicate-detect -> persist chunks.

    Entirely synchronous and CPU/network-bound, so it MUST run on a worker
    thread (``run_in_threadpool``) — never on the event loop, where one large
    PDF would stall every concurrent request on this worker.
    """
    try:
        blocks = extractor.extract_blocks(data, file_type)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not read file: {exc}")

    strategy = settings.chunking_strategy
    chunk_dicts = chunk_blocks(blocks) if strategy == "character" else chunk_blocks_semantic(blocks)
    if not chunk_dicts:
        raise HTTPException(
            status_code=422, detail="No extractable text found in the document."
        )

    chunk_texts = [c["text"] for c in chunk_dicts]

    # Embeddings are a network round trip (batched internally); everything
    # else here is pure-Python CPU work with no dependency on the embedding
    # result, so run them concurrently instead of paying for both in
    # sequence — same computations and results, just overlapped.
    with ThreadPoolExecutor(max_workers=1) as pool:
        embed_future = pool.submit(llm.embed_texts, chunk_texts)

        scores = score_chunks(chunk_texts)
        highlights = extract_highlights(chunk_texts, scores, n=8)
        outline = extract_outline(blocks, chunk_texts)
        full_text = extractor.blocks_to_text(blocks)

        embeddings = embed_future.result()

    if len(embeddings) != len(chunk_texts):
        raise HTTPException(status_code=500, detail="Embedding count mismatch.")

    # Duplicate detection: flag (do not block) near-identical prior uploads.
    # The in-flight document has no chunks yet, so it never matches itself.
    dup = _detect_duplicate(db, document.user_id, embeddings)

    # Store the original first so a DB failure below can clean it up.
    storage_key = _store_original(data, document.user_id, file_type)
    try:
        document.page_count = extractor.page_count(blocks) or None
        document.word_count = extractor.count_words(full_text)
        document.storage_key = storage_key
        document.chunking_strategy = strategy
        document.outline_json = json.dumps(outline)
        document.highlights_json = json.dumps(highlights)
        document.processed_at = datetime.now(timezone.utc)
        document.duplicate_of = dup[0] if dup else None
        document.processing_status = "done"

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
        if storage_key:
            storage.delete(storage_key)
        raise

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


def _mark_failed(db: Session, document: Document, message: str) -> None:
    """Record a processing failure on the document row so /status can show a
    real failure state instead of the frontend polling forever."""
    db.rollback()
    document.processing_status = "failed"
    document.processing_error = message[:1000]
    db.commit()


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

    Only the cheap validation happens on the event loop; the Document row is
    created up-front (processing_status="processing") and the blocking
    pipeline runs on a threadpool worker, so concurrent requests keep being
    served while a large file is processed.
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

    document = Document(
        user_id=current_user.id,
        filename=filename,
        file_type=file_type,
        processing_status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        result = await run_in_threadpool(_process_upload, db, document, data, file_type)
    except HTTPException as exc:
        _mark_failed(db, document, str(exc.detail))
        raise
    except Exception as exc:  # noqa: BLE001
        _mark_failed(db, document, str(exc))
        raise

    # The user's document set changed -> drop their cached query answers.
    cache.invalidate_prefix(user_prefix(current_user.id))

    return result


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
        processing_status=document.processing_status,
        error=document.processing_error,
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
        .where(
            Document.user_id == current_user.id,
            Document.deleted_at.is_(None),
            # Failed ingestions never become part of the library; their state
            # remains visible via /status (by id) for the upload flow only.
            Document.processing_status != "failed",
        )
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
            storage_key=doc.storage_key,
        )
    )
    # Blocking file I/O — keep it off the event loop.
    new_key = await run_in_threadpool(_store_original, data, current_user.id, file_type)
    doc.version_number += 1
    doc.storage_key = new_key
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


@router.get("/{document_id}/timeline", response_model=list[TimelineEvent])
def document_timeline(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dated events extracted from the document (cached after first request)."""
    doc = _owned_doc(db, document_id, current_user)
    cached = db.get(DocumentTimeline, document_id)
    if cached is not None:
        return [TimelineEvent(**e) for e in json.loads(cached.events_json)]

    highlights = json.loads(doc.highlights_json) if doc.highlights_json else []
    events = extract_timeline(highlights)
    # Cache even an empty result so a second view never re-calls the model.
    db.add(DocumentTimeline(document_id=document_id, events_json=json.dumps(events)))
    db.commit()
    return [TimelineEvent(**e) for e in events]


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


@router.get("/trash", response_model=list[DocumentOut])
def list_trash(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-deleted documents still within the retention window."""
    rows = db.execute(
        select(Document)
        .where(Document.user_id == current_user.id, Document.deleted_at.is_not(None))
        .order_by(Document.deleted_at.desc())
    ).scalars().all()
    return [DocumentOut.model_validate(d) for d in rows]


@router.delete("/{document_id}", response_model=DeleteResult)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a document: mark ``deleted_at`` so it is excluded from every
    read (list, retrieval, analytics) but can be restored within 30 days. The
    on-disk file and chunks are retained until the cleanup job hard-deletes it.

    Ownership rule: a document owned by another user returns 403; a missing id
    returns 404.
    """
    document = _owned_doc(db, document_id, current_user)  # 404/403 + not already deleted
    document.deleted_at = datetime.now(timezone.utc)
    db.commit()

    # The user's document set changed -> drop their cached query answers so a
    # deleted document can never resurface via a cached RAG response.
    cache.invalidate_prefix(user_prefix(current_user.id))

    return DeleteResult(id=document_id, deleted=True)


@router.post("/{document_id}/restore", response_model=DeleteResult)
def restore_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore a soft-deleted document if within the 30-day retention window."""
    doc = db.get(Document, document_id)
    if doc is None or doc.deleted_at is None:
        raise HTTPException(status_code=404, detail="No deleted document to restore.")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this document.")
    if (datetime.now(timezone.utc) - _aware(doc.deleted_at)).days >= 30:
        raise HTTPException(status_code=410, detail="Retention window has passed.")
    doc.deleted_at = None
    db.commit()
    cache.invalidate_prefix(user_prefix(current_user.id))
    return DeleteResult(id=document_id, deleted=False)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
