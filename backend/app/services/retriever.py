"""Hybrid retrieval: dense (cosine) + sparse (BM25), importance-reranked.

``hybrid_retrieve`` fuses embedding similarity with lexical BM25, then boosts by
each chunk's importance score, and returns fully-annotated results (page,
section, all three scores). It also records that the returned chunks were
retrieved (``retrieved_count`` + per-user coverage), which powers analytics and
the coverage heatmap.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import llm
from ..config import settings
from ..models import Chunk, Document
from .bm25_index import BM25Index

logger = logging.getLogger("papertrail.retriever")

DENSE_WEIGHT = 0.6
SPARSE_WEIGHT = 0.4
IMPORTANCE_BOOST = 0.2


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo
    if span < 1e-12:
        return [0.0 for _ in values]
    return [(v - lo) / span for v in values]


def _cosine(q: list[float], v: list[float]) -> float:
    import numpy as np

    a = np.asarray(q, dtype=np.float64)
    b = np.asarray(v, dtype=np.float64)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _record_retrievals(db: Session, user_id: str, chunk_ids: list[str]) -> None:
    """Increment retrieved_count on chunks and upsert per-user coverage rows."""
    if not chunk_ids:
        return
    from datetime import datetime, timezone

    from ..models import ChunkCoverage

    now = datetime.now(timezone.utc)
    for cid in chunk_ids:
        chunk = db.get(Chunk, cid)
        if chunk is not None:
            chunk.retrieved_count = (chunk.retrieved_count or 0) + 1
        cov = db.get(ChunkCoverage, {"chunk_id": cid, "user_id": user_id})
        if cov is None:
            db.add(
                ChunkCoverage(
                    chunk_id=cid, user_id=user_id, retrieved_count=1, last_retrieved=now
                )
            )
        else:
            cov.retrieved_count = (cov.retrieved_count or 0) + 1
            cov.last_retrieved = now
    db.commit()


def _load_chunk_ids_for_scope(
    db: Session, user_id: str, document_ids: list[str] | None,
    collection_id: str | None,
) -> set[str] | None:
    """Resolve which document ids are in scope; None => all the user's docs."""
    doc_ids: set[str] | None = None
    if collection_id:
        from ..models import DocumentCollection

        rows = db.execute(
            select(DocumentCollection.document_id)
            .join(Document, Document.id == DocumentCollection.document_id)
            .where(
                DocumentCollection.collection_id == collection_id,
                Document.user_id == user_id,
            )
        ).scalars().all()
        doc_ids = set(rows)
    if document_ids:
        wanted = set(document_ids)
        doc_ids = wanted if doc_ids is None else (doc_ids & wanted)
    return doc_ids


def hybrid_retrieve(
    db: Session,
    user_id: str,
    query: str,
    *,
    document_ids: list[str] | None = None,
    collection_id: str | None = None,
    top_k: int = 8,
    record: bool = True,
) -> list[dict]:
    """Return the top-``k`` chunks for ``query`` within the user's scope."""
    scope = _load_chunk_ids_for_scope(db, user_id, document_ids, collection_id)
    if scope is not None and not scope:
        return []  # an explicit but empty scope matches nothing

    stmt = (
        select(
            Chunk.id, Chunk.document_id, Chunk.chunk_index, Chunk.content,
            Chunk.embedding, Chunk.importance_score, Chunk.page_number,
            Chunk.section_heading, Document.filename,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.user_id == user_id, Document.deleted_at.is_(None))
        .order_by(Chunk.document_id.desc(), Chunk.id.desc())
        .limit(settings.max_query_chunks)
    )
    if scope is not None:
        stmt = stmt.where(Chunk.document_id.in_(scope))

    rows = db.execute(stmt).all()
    if not rows:
        return []

    query_vec = llm.embed_texts([query])[0]
    qdim = len(query_vec)

    # Dimension-matched candidates only (mixed embedding providers are skipped).
    cand = []
    for r in rows:
        emb = json.loads(r.embedding)
        if len(emb) == qdim:
            cand.append((r, emb))
    if not cand:
        return []

    texts = [r.content for r, _ in cand]
    dense_raw = [_cosine(query_vec, emb) for _, emb in cand]
    bm25 = BM25Index().build(texts)
    sparse_map = dict(bm25.search(query, top_k=len(texts)))
    sparse_raw = [sparse_map.get(i, 0.0) for i in range(len(texts))]

    dense_norm = _minmax(dense_raw)
    sparse_norm = _minmax(sparse_raw)

    scored: list[dict] = []
    for i, (r, _emb) in enumerate(cand):
        fused = DENSE_WEIGHT * dense_norm[i] + SPARSE_WEIGHT * sparse_norm[i]
        ranked = fused * (1 + IMPORTANCE_BOOST * float(r.importance_score or 0.0))
        scored.append(
            {
                "chunk_id": r.id,
                "text": r.content,
                "document_id": r.document_id,
                "document_name": r.filename,
                "chunk_index": r.chunk_index,
                "page_number": r.page_number,
                "section_heading": r.section_heading,
                "similarity_score": round(max(0.0, dense_raw[i]), 6),
                "sparse_score": round(sparse_raw[i], 6),
                "importance_score": round(float(r.importance_score or 0.0), 6),
                "ranked_score": round(ranked, 6),
            }
        )

    scored.sort(key=lambda d: d["ranked_score"], reverse=True)
    top = scored[: max(0, top_k)]

    if record and top:
        _record_retrievals(db, user_id, [d["chunk_id"] for d in top])

    return top
