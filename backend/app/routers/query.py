"""Query routes: RAG, multi-hop, and direct (no-retrieval) modes.

RAG/multi-hop retrieve with the hybrid engine (dense + BM25 + importance),
generate a grounded answer, then annotate it: a confidence score, follow-up
questions, and a hallucination check flagging unsupported sentences. Every
query is persisted (with its sources) so it can be revisited, bookmarked, and
visualized as a mind map.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import llm
from ..auth import get_current_user
from ..cache import cache, make_query_key
from ..config import settings
from ..database import get_db
from ..models import ChatHistory, User
from ..ratelimit import limiter, query_limit
from ..schemas import (
    QueryRequest,
    QueryResponse,
    SourceOut,
    UnsupportedSentence,
)
from ..services.followup import generate_followup_questions
from ..services.hallucination_guard import check_answer
from ..services.multihop import multihop_retrieve
from ..services.retriever import hybrid_retrieve

router = APIRouter(prefix="/api", tags=["query"])
logger = logging.getLogger("papertrail.query")

SNIPPET_CHARS = 240
TOP_K = 8


@router.post("/query", response_model=QueryResponse)
@limiter.limit(query_limit)
def query(
    request: Request,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = payload.question.strip()
    mode = payload.mode

    # Cache identical (user, question, mode). Retrieval scoping makes the cache
    # unsafe to reuse across different document_ids/collection, so only the
    # unscoped ("all documents") case is cached.
    scoped = bool(payload.document_ids) or bool(payload.collection_id)
    cache_key = make_query_key(current_user.id, question, mode) if not scoped else None
    if cache_key and settings.query_cache_ttl_seconds > 0:
        cached = cache.get(cache_key)
        if cached is not None:
            response = QueryResponse.model_validate_json(cached)
            row = _save_history(db, current_user, question, response, mode)
            response.query_id = row.id
            return response

    response = _compute_query(db, current_user, payload, question, mode)
    row = _save_history(db, current_user, question, response, mode)
    response.query_id = row.id
    if cache_key and settings.query_cache_ttl_seconds > 0:
        cache.set(cache_key, response.model_dump_json(), settings.query_cache_ttl_seconds)
    return response


def _compute_query(
    db: Session, current_user: User, payload: QueryRequest, question: str, mode: str
) -> QueryResponse:
    if mode == "direct":
        answer = llm.generate_answer(question, [], "direct")
        return QueryResponse(answer=answer, mode=mode, sources=[], confidence_score=0.0)

    document_ids = payload.document_ids or None
    collection_id = payload.collection_id

    if mode == "multihop":
        retrieved = multihop_retrieve(
            db, current_user.id, question,
            document_ids=document_ids, collection_id=collection_id,
        )
    else:
        retrieved = hybrid_retrieve(
            db, current_user.id, question,
            document_ids=document_ids, collection_id=collection_id, top_k=TOP_K,
        )

    if not retrieved:
        answer = (
            "There are no documents (or no relevant passages) to answer that yet. "
            "Upload a document, or widen your selection, and ask again."
        )
        return QueryResponse(answer=answer, mode=mode, sources=[], confidence_score=0.0)

    context_chunks = [c["text"] for c in retrieved]
    answer = llm.generate_answer(question, context_chunks, "rag")

    # Confidence = mean of the top-3 ranked scores, clamped to [0, 1].
    top3 = [c["ranked_score"] for c in retrieved[:3]]
    confidence = min(1.0, sum(top3) / len(top3)) if top3 else 0.0

    sources: list[SourceOut] = []
    for i, c in enumerate(retrieved, start=1):
        snippet = c["text"].strip().replace("\n", " ")
        if len(snippet) > SNIPPET_CHARS:
            snippet = snippet[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"
        relevance = int(round(min(1.0, c["ranked_score"]) * 100))
        sources.append(
            SourceOut(
                n=i,
                title=c["document_name"],
                snippet=snippet,
                score=float(relevance),
                document_id=c["document_id"],
                chunk_id=c["chunk_id"],
                chunk_index=c.get("chunk_index", 0),
                page_number=c.get("page_number", 1),
                section_heading=c.get("section_heading"),
                similarity_score=round(c.get("similarity_score", 0.0), 4),
                importance_score=round(c.get("importance_score", 0.0), 4),
                relevance_pct=relevance,
            )
        )

    followups = generate_followup_questions(question, answer, retrieved)
    unsupported = [
        UnsupportedSentence(sentence=s["sentence"], source_chunk_id=s["source_chunk_id"])
        for s in check_answer(answer, retrieved)
        if not s["supported"]
    ]

    return QueryResponse(
        answer=answer,
        mode=mode,
        sources=sources,
        confidence_score=round(confidence, 4),
        followup_questions=followups,
        unsupported_sentences=unsupported,
    )


def _save_history(
    db: Session, user: User, question: str, response: QueryResponse, mode: str
) -> ChatHistory:
    """Persist the exchange plus a compact source snapshot (for the mind map)."""
    sources_snapshot = [
        {
            "chunk_id": s.chunk_id,
            "document_id": s.document_id,
            "document_name": s.title,
            "page_number": s.page_number,
            "section_heading": s.section_heading,
            "ranked_score": s.relevance_pct / 100.0,
            "importance_score": s.importance_score,
        }
        for s in response.sources
    ]
    row = ChatHistory(
        user_id=user.id,
        question=question,
        answer=response.answer,
        mode=mode,
        sources_json=json.dumps(sources_snapshot) if sources_snapshot else None,
        confidence_score=response.confidence_score,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
