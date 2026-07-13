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

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
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
from ..services.followup import generate_followup_questions, parse_followup_questions
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


def _history_dicts(payload: QueryRequest) -> list[dict]:
    """Prior conversation turns as plain dicts, oldest first, ready to thread
    into an llm.py call. QueryRequest already caps/truncates to the last 6."""
    return [{"role": t.role, "content": t.content} for t in payload.conversation_history]


COMPARE_TOP_K = 4


def _retrieve_for_compare(
    db: Session, current_user: User, document_ids: list[str], question: str
) -> tuple[dict[str, list[str]], list[dict]]:
    """Retrieve top-``COMPARE_TOP_K`` chunks per document (not pooled across
    documents), so every selected document gets a fair shot at contributing
    passages regardless of how the others rank. Returns
    (chunks_by_doc keyed by filename, the flattened retrieved list in the
    same order chunks_by_doc was built — sources/citations line up with
    llm._build_compare_messages' numbering)."""
    chunks_by_doc: dict[str, list[str]] = {}
    all_retrieved: list[dict] = []
    for doc_id in document_ids:
        retrieved = hybrid_retrieve(
            db, current_user.id, question, document_ids=[doc_id], top_k=COMPARE_TOP_K,
        )
        if not retrieved:
            continue
        doc_name = retrieved[0]["document_name"]
        chunks_by_doc[doc_name] = [c["text"] for c in retrieved]
        all_retrieved.extend(retrieved)
    return chunks_by_doc, all_retrieved


def _compute_compare_query(
    db: Session, current_user: User, payload: QueryRequest, question: str
) -> QueryResponse:
    if len(payload.document_ids) < 2:
        raise HTTPException(
            status_code=400, detail="Compare mode requires at least 2 selected documents."
        )

    chunks_by_doc, retrieved = _retrieve_for_compare(
        db, current_user, payload.document_ids, question
    )
    if not retrieved:
        answer = "There are no relevant passages in the selected documents to compare."
        return QueryResponse(answer=answer, mode="compare", sources=[], confidence_score=0.0)

    answer = llm.generate_compare_answer(question, chunks_by_doc)
    sources = _build_sources(retrieved)
    followups = generate_followup_questions(question, answer, retrieved)
    unsupported = [
        UnsupportedSentence(sentence=s["sentence"], source_chunk_id=s["source_chunk_id"])
        for s in check_answer(answer, retrieved)
        if not s["supported"]
    ]
    confidence = _confidence(retrieved, answer, unsupported)

    return QueryResponse(
        answer=answer,
        mode="compare",
        sources=sources,
        confidence_score=confidence,
        followup_questions=followups,
        unsupported_sentences=unsupported,
    )


def _compute_query(
    db: Session, current_user: User, payload: QueryRequest, question: str, mode: str
) -> QueryResponse:
    history = _history_dicts(payload)
    if mode == "direct":
        answer = llm.generate_answer(question, [], "direct", history)
        return QueryResponse(answer=answer, mode=mode, sources=[], confidence_score=0.0)

    if mode == "compare":
        return _compute_compare_query(db, current_user, payload, question)

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
    # One model call for both the answer and its follow-up questions (was two
    # sequential calls) — see llm.generate_rag_answer_with_followups.
    answer, followups_raw = llm.generate_rag_answer_with_followups(question, context_chunks, history)

    sources = _build_sources(retrieved)
    followups = parse_followup_questions(followups_raw) if followups_raw else []
    unsupported = [
        UnsupportedSentence(sentence=s["sentence"], source_chunk_id=s["source_chunk_id"])
        for s in check_answer(answer, retrieved)
        if not s["supported"]
    ]
    confidence = _confidence(retrieved, answer, unsupported)

    return QueryResponse(
        answer=answer,
        mode=mode,
        sources=sources,
        confidence_score=confidence,
        followup_questions=followups,
        unsupported_sentences=unsupported,
    )


def _confidence(retrieved: list[dict], answer: str, unsupported: list) -> float:
    """Calibrated multi-signal confidence, clamped to [0, 1].

    The old formula (mean of the top-3 ranked scores) is purely relative — a
    confident-sounding answer generated from off-topic context could still
    score ~0.7. This blends four signals instead:
      1. Top-chunk similarity as an absolute quality gate: below 0.4, the best
         match is likely off-topic, so the score is capped low regardless of
         how the other signals look.
      2. Mean of the top-3 ranked scores (the original signal).
      3. A hallucination penalty from the fraction of unsupported sentences.
      4. A small bonus for having enough chunks to draw from.
    """
    if not retrieved:
        return 0.0

    top_sim = retrieved[0].get("similarity_score", 0.0)
    if top_sim < 0.4:
        return round(min(0.35, top_sim), 4)

    top3 = [c["ranked_score"] for c in retrieved[:3]]
    retrieval_conf = sum(top3) / len(top3)

    total_sents = max(1, len(answer.split(". ")))
    unsupported_frac = len(unsupported) / total_sents
    hallucination_penalty = 1.0 - min(0.5, unsupported_frac * 2)

    coverage_bonus = min(0.1, 0.02 * len(retrieved))

    raw = 0.5 * retrieval_conf + 0.3 * top_sim + 0.2 * hallucination_penalty + coverage_bonus
    return round(min(1.0, max(0.0, raw)), 4)


def _build_sources(retrieved: list[dict]) -> list[SourceOut]:
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
    return sources


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


# --------------------------------------------------------------------------- #
# Streaming (SSE) variant — kept alongside the blocking endpoint above, not a
# replacement, for clients (tests, exports, share links) that need one
# synchronous JSON response.
# --------------------------------------------------------------------------- #
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _stream_events(
    db: Session, current_user: User, payload: QueryRequest, question: str, mode: str
):
    """Generator of SSE-formatted strings for POST /api/query/stream.

    Emits ``sources`` immediately (before any answer text), streams ``token``
    events as the answer is generated, then trailing ``followups`` /
    ``hallucination`` / ``done`` events. ChatHistory is persisted only once
    the full answer is known (after the stream completes), same as the
    blocking endpoint.
    """
    history = _history_dicts(payload)
    if mode == "direct":
        answer = llm.generate_answer(question, [], "direct", history)
        yield _sse("sources", {"sources": []})
        yield _sse("token", {"token": answer})
        response = QueryResponse(answer=answer, mode=mode, sources=[], confidence_score=0.0)
        row = _save_history(db, current_user, question, response, mode)
        yield _sse("followups", {"followups": []})
        yield _sse("hallucination", {"unsupported_sentences": []})
        yield _sse("done", {"query_id": row.id, "confidence_score": 0.0})
        return

    if mode == "compare":
        # The <2-documents check runs in query_stream() before this generator
        # is ever iterated — StreamingResponse commits a 200 as soon as the
        # body starts streaming, so an HTTPException raised from in here would
        # arrive too late to become a clean 400.
        chunks_by_doc, retrieved = _retrieve_for_compare(
            db, current_user, payload.document_ids, question
        )
    else:
        chunks_by_doc = None
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

    sources = _build_sources(retrieved)
    yield _sse("sources", {"sources": [s.model_dump() for s in sources]})

    if not retrieved:
        answer = (
            "There are no relevant passages in the selected documents to compare."
            if mode == "compare"
            else "There are no documents (or no relevant passages) to answer that yet. "
            "Upload a document, or widen your selection, and ask again."
        )
        yield _sse("token", {"token": answer})
        response = QueryResponse(answer=answer, mode=mode, sources=[], confidence_score=0.0)
        row = _save_history(db, current_user, question, response, mode)
        yield _sse("followups", {"followups": []})
        yield _sse("hallucination", {"unsupported_sentences": []})
        yield _sse("done", {"query_id": row.id, "confidence_score": 0.0})
        return

    parts: list[str] = []
    if mode == "compare":
        token_stream = llm.stream_compare_answer(question, chunks_by_doc)
    else:
        context_chunks = [c["text"] for c in retrieved]
        token_stream = llm.stream_rag_answer(question, context_chunks, history)
    for token in token_stream:
        parts.append(token)
        yield _sse("token", {"token": token})
    answer = "".join(parts)

    followups = generate_followup_questions(question, answer, retrieved)
    unsupported = [
        UnsupportedSentence(sentence=s["sentence"], source_chunk_id=s["source_chunk_id"])
        for s in check_answer(answer, retrieved)
        if not s["supported"]
    ]
    confidence = _confidence(retrieved, answer, unsupported)

    response = QueryResponse(
        answer=answer,
        mode=mode,
        sources=sources,
        confidence_score=confidence,
        followup_questions=followups,
        unsupported_sentences=unsupported,
    )
    row = _save_history(db, current_user, question, response, mode)

    yield _sse("followups", {"followups": followups})
    yield _sse(
        "hallucination",
        {"unsupported_sentences": [u.model_dump() for u in unsupported]},
    )
    yield _sse("done", {"query_id": row.id, "confidence_score": confidence})


@router.post("/query/stream")
@limiter.limit(query_limit)
def query_stream(
    request: Request,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE variant of /api/query: source cards arrive before the model starts
    answering, then the answer streams in token-by-token."""
    question = payload.question.strip()
    mode = payload.mode
    # Validated here (before the streaming response starts) rather than
    # inside _stream_events: StreamingResponse commits a 200 status as soon as
    # the body begins streaming, so raising after that point can't produce a
    # clean 400.
    if mode == "compare" and len(payload.document_ids) < 2:
        raise HTTPException(
            status_code=400, detail="Compare mode requires at least 2 selected documents."
        )
    return StreamingResponse(
        _stream_events(db, current_user, payload, question, mode),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
