"""Hybrid retrieval: dense (ANN + cosine) + sparse (BM25), importance-reranked.

``hybrid_retrieve`` fuses embedding similarity with lexical BM25, then boosts by
each chunk's importance score, and returns fully-annotated results (page,
section, all three scores). It also records that the returned chunks were
retrieved (``retrieved_count`` + per-user coverage), which powers analytics and
the coverage heatmap.

To avoid rebuilding indexes per query, each user's retrieval corpus is cached in
process (same invalidation hook as query-response cache). The sparse side keeps
a cached BM25 index; the dense side keeps a cached ANN index per embedding
dimension. This comfortably handles low/mid-size collections; beyond that, the
next step is a dedicated vector database/service.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import cast

from scipy.spatial import cKDTree
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import llm
from ..cache import get_or_build_object, retrieval_index_key
from ..config import settings
from ..models import Chunk, Document
from .bm25_index import BM25Index

logger = logging.getLogger("papertrail.retriever")

DENSE_WEIGHT = 0.6
SPARSE_WEIGHT = 0.4
IMPORTANCE_BOOST = 0.2
_ANN_CANDIDATE_MULTIPLIER = 20

try:  # Optional ANN backend (faster than KD-tree for larger corpora).
    from usearch.index import Index as USearchIndex
except Exception:  # noqa: BLE001
    USearchIndex = None


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
    db: Session,
    user_id: str,
    document_ids: list[str] | None,
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


@dataclass(frozen=True)
class _ChunkRow:
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    embedding: list[float]
    importance_score: float
    page_number: int
    section_heading: str | None
    filename: str


class _DenseAnnIndex:
    """Approximate nearest-neighbor index over one embedding dimension."""

    def __init__(self, row_ids: list[int], vectors: list[list[float]]) -> None:
        import numpy as np

        self._row_ids = row_ids
        if not vectors:
            self._vectors = np.empty((0, 0), dtype=np.float32)
            self._tree = None
            self._usearch = None
            return

        arr = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._vectors = arr / norms
        self._tree = cKDTree(self._vectors)
        self._usearch = None

        if USearchIndex is not None:
            try:
                idx = USearchIndex(ndim=self._vectors.shape[1], metric="cos")
                idx.add(self._row_ids, self._vectors)
                self._usearch = idx
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "USearch index build failed; using KD-tree fallback (%s)", exc
                )

    def search(
        self, query_vec: list[float], limit: int, *, approximate: bool
    ) -> list[tuple[int, float]]:
        import numpy as np

        if limit <= 0 or not self._row_ids:
            return []

        q = np.asarray(query_vec, dtype=np.float32)
        qn = np.linalg.norm(q)
        if qn == 0.0:
            return []
        q = q / qn
        k = min(limit, len(self._row_ids))

        if approximate:
            if self._usearch is not None:
                try:
                    hits = self._usearch.search(q, k)
                    return [
                        (int(rid), float(max(-1.0, 1.0 - dist)))
                        for rid, dist in zip(hits.keys, hits.distances)
                    ]
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "USearch query failed; using KD-tree fallback (%s)", exc
                    )

            if self._tree is not None:
                dists, locs = self._tree.query(q, k=k, eps=0.2)
                if k == 1:
                    dists = [float(dists)]
                    locs = [int(locs)]
                out: list[tuple[int, float]] = []
                for dist, local_idx in zip(dists, locs):
                    # For L2-normalized vectors: ||a-b||^2 = 2 - 2*cos(a,b)
                    cosine = 1.0 - (float(dist) ** 2) / 2.0
                    out.append((self._row_ids[int(local_idx)], float(max(-1.0, cosine))))
                return out

        sims = self._vectors @ q
        order = np.argsort(-sims)[:k]
        return [(self._row_ids[int(i)], float(sims[int(i)])) for i in order]


@dataclass
class _UserRetrievalIndex:
    rows: list[_ChunkRow]
    bm25: BM25Index
    dense_by_dim: dict[int, _DenseAnnIndex]
    row_ids_by_doc: dict[str, list[int]]


def _build_user_index(db: Session, user_id: str) -> _UserRetrievalIndex:
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.chunk_index,
            Chunk.content,
            Chunk.embedding,
            Chunk.importance_score,
            Chunk.page_number,
            Chunk.section_heading,
            Document.filename,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.user_id == user_id, Document.deleted_at.is_(None))
        .order_by(Chunk.document_id.desc(), Chunk.id.desc())
        .limit(settings.max_query_chunks)
    )
    raw = db.execute(stmt).all()

    rows: list[_ChunkRow] = []
    texts: list[str] = []
    vectors_by_dim: dict[int, list[list[float]]] = {}
    ids_by_dim: dict[int, list[int]] = {}
    row_ids_by_doc: dict[str, list[int]] = {}

    for rec in raw:
        emb = json.loads(rec.embedding)
        if not isinstance(emb, list) or not emb:
            continue
        row_id = len(rows)
        rows.append(
            _ChunkRow(
                chunk_id=rec.id,
                document_id=rec.document_id,
                chunk_index=int(rec.chunk_index),
                content=rec.content,
                embedding=emb,
                importance_score=float(rec.importance_score or 0.0),
                page_number=int(rec.page_number or 1),
                section_heading=rec.section_heading,
                filename=rec.filename,
            )
        )
        texts.append(rec.content)
        row_ids_by_doc.setdefault(rec.document_id, []).append(row_id)
        dim = len(emb)
        ids_by_dim.setdefault(dim, []).append(row_id)
        vectors_by_dim.setdefault(dim, []).append(emb)

    dense_by_dim = {
        dim: _DenseAnnIndex(ids_by_dim[dim], vectors_by_dim[dim])
        for dim in vectors_by_dim
    }
    return _UserRetrievalIndex(
        rows=rows,
        bm25=BM25Index().build(texts),
        dense_by_dim=dense_by_dim,
        row_ids_by_doc=row_ids_by_doc,
    )


def _get_user_index(db: Session, user_id: str) -> _UserRetrievalIndex:
    key = retrieval_index_key(user_id)
    return cast(_UserRetrievalIndex, get_or_build_object(key, lambda: _build_user_index(db, user_id)))


def _scope_row_ids(index: _UserRetrievalIndex, doc_scope: set[str]) -> list[int]:
    out: list[int] = []
    for doc_id in doc_scope:
        out.extend(index.row_ids_by_doc.get(doc_id, []))
    return out


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

    index = _get_user_index(db, user_id)
    if not index.rows:
        return []

    query_vec = llm.embed_texts([query])[0]
    qdim = len(query_vec)
    dense_index = index.dense_by_dim.get(qdim)
    if dense_index is None:
        return []

    if scope is None:
        dense_limit = max(top_k * _ANN_CANDIDATE_MULTIPLIER, top_k)
        dense_candidates = {
            row_id for row_id, _ in dense_index.search(query_vec, dense_limit, approximate=True)
        }
        sparse_candidates = {
            row_id
            for row_id, _ in index.bm25.search(query, top_k=dense_limit)
            if len(index.rows[row_id].embedding) == qdim
        }
        candidate_ids = sorted(dense_candidates | sparse_candidates)
    else:
        candidate_ids = [
            row_id
            for row_id in _scope_row_ids(index, scope)
            if len(index.rows[row_id].embedding) == qdim
        ]

    if not candidate_ids:
        return []

    sparse_map = dict(index.bm25.search(query, top_k=len(index.rows)))
    dense_raw = [_cosine(query_vec, index.rows[i].embedding) for i in candidate_ids]
    sparse_raw = [float(sparse_map.get(i, 0.0)) for i in candidate_ids]

    dense_norm = _minmax(dense_raw)
    sparse_norm = _minmax(sparse_raw)

    scored: list[dict] = []
    for pos, row_id in enumerate(candidate_ids):
        row = index.rows[row_id]
        fused = DENSE_WEIGHT * dense_norm[pos] + SPARSE_WEIGHT * sparse_norm[pos]
        ranked = fused * (1 + IMPORTANCE_BOOST * row.importance_score)
        scored.append(
            {
                "chunk_id": row.chunk_id,
                "text": row.content,
                "document_id": row.document_id,
                "document_name": row.filename,
                "chunk_index": row.chunk_index,
                "page_number": row.page_number,
                "section_heading": row.section_heading,
                "similarity_score": round(max(0.0, dense_raw[pos]), 6),
                "sparse_score": round(sparse_raw[pos], 6),
                "importance_score": round(row.importance_score, 6),
                "ranked_score": round(ranked, 6),
            }
        )

    scored.sort(key=lambda d: d["ranked_score"], reverse=True)
    top = scored[: max(0, top_k)]

    if record and top:
        _record_retrievals(db, user_id, [d["chunk_id"] for d in top])

    return top
