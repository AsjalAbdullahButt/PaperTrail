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
    GroundingSentence,
    PipelineInfo,
    QueryRequest,
    QueryResponse,
    SourceOut,
    UnsupportedSentence,
)
from ..services import abstention
from ..services.followup import generate_followup_questions, parse_followup_questions
from ..services.hallucination_guard import check_answer
from ..services.multihop import multihop_retrieve
from ..services.nli_guard import check_answer_nli
from ..services.pipeline_options import PipelineConfig, capabilities, resolve
from ..services.query_expansion import hyde_passage
from ..services.reranker import sigmoid
from ..services.retriever import hybrid_retrieve

router = APIRouter(prefix="/api", tags=["query"])
logger = logging.getLogger("papertrail.query")

SNIPPET_CHARS = 240
TOP_K = 8

ABSTAIN_MESSAGE = (
    "I could not find this in your documents. The passages that matched your question were not "
    "relevant enough to answer from, so I am not going to guess. Try rephrasing, or upload a "
    "document that covers it."
)


@router.get("/query/capabilities")
def query_capabilities(current_user: User = Depends(get_current_user)):
    """Which optional NLP stages (re-ranking, HyDE, NLI grounding, abstention) this
    server can run, and their defaults. The UI uses it to enable/disable toggles."""
    return capabilities()


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
    cfg = resolve(payload.options)
    scoped = bool(payload.document_ids) or bool(payload.collection_id) or cfg.customised
    cache_key = make_query_key(current_user.id, question, mode) if not scoped else None
    if cache_key and settings.query_cache_ttl_seconds > 0:
        cached = cache.get(cache_key)
        if cached is not None:
            response = QueryResponse.model_validate_json(cached)
            row = _save_history(db, current_user, question, response, mode)
            response.query_id = row.id
            return response

    response = _compute_query(db, current_user, payload, question, mode, cfg)
    row = _save_history(db, current_user, question, response, mode)
    response.query_id = row.id
    if cache_key and settings.query_cache_ttl_seconds > 0:
        cache.set(cache_key, response.model_dump_json(), settings.query_cache_ttl_seconds)
    return response


def _history_dicts(payload: QueryRequest) -> list[dict]:
    """Prior conversation turns as plain dicts, oldest first, ready to thread
    into an llm.py call. QueryRequest already caps/truncates to the last 6."""
    return [{"role": t.role, "content": t.content} for t in payload.conversation_history]


def _retrieve(
    db: Session, current_user: User, question: str, mode: str,
    document_ids: list[str] | None, collection_id: str | None, cfg: PipelineConfig,
) -> list[dict]:
    """Retrieval for rag / multihop modes, honouring the resolved pipeline."""
    if mode == "multihop":
        if cfg.customised:
            cfg.notes.append("Re-ranking / HyDE options do not apply to multi-hop mode.")
        return multihop_retrieve(
            db, current_user.id, question, document_ids=document_ids, collection_id=collection_id,
        )
    expanded: str | None = None
    if cfg.expansion == "hyde":
        try:
            expanded = hyde_passage(question) or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("HyDE expansion failed (%s)", exc)
        if expanded is None:
            cfg.expansion = "none"
            cfg.notes.append("HyDE skipped: no language model is available to write the hypothetical passage.")
    return hybrid_retrieve(
        db, current_user.id, question,
        document_ids=document_ids, collection_id=collection_id, top_k=TOP_K,
        rerank=cfg.rerank, expanded_query=expanded,
    )


def _ground(answer: str, retrieved: list[dict], cfg: PipelineConfig) -> tuple[list[GroundingSentence], list[UnsupportedSentence]]:
    """Run the configured grounding check; NLI falls back to the lexical guard."""
    if cfg.grounding == "nli":
        try:
            grounding = [GroundingSentence(**r) for r in check_answer_nli(answer, retrieved)]
            return grounding, [
                UnsupportedSentence(sentence=g.sentence, source_chunk_id=g.source_chunk_id)
                for g in grounding if not g.supported
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("NLI grounding failed (%s); using the lexical check.", exc)
            cfg.grounding = "lexical"
            cfg.notes.append("NLI grounding failed; used the lexical check.")
    results = check_answer(answer, retrieved)
    grounding = [
        GroundingSentence(sentence=r["sentence"], supported=r["supported"], source_chunk_id=r["source_chunk_id"])
        for r in results
    ]
    return grounding, [
        UnsupportedSentence(sentence=r["sentence"], source_chunk_id=r["source_chunk_id"])
        for r in results if not r["supported"]
    ]


def _pipeline_info(cfg: PipelineConfig, retrieved: list[dict]) -> PipelineInfo:
    reranked = bool(retrieved) and "rerank_score" in retrieved[0]
    notes = list(cfg.notes)
    if cfg.rerank and retrieved and not reranked:
        notes.append("Re-ranking failed; results are in first-stage (hybrid) order.")
    return PipelineInfo(
        reranked=reranked,
        expansion=cfg.expansion,
        grounding_method=cfg.grounding,
        abstention_checked=cfg.abstain,
        retrieval_signal=abstention.retrieval_signal(retrieved) if retrieved else None,
        signal_kind=abstention.signal_kind(retrieved) if retrieved else None,
        notes=notes,
    )


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
    db: Session, current_user: User, payload: QueryRequest, question: str, mode: str,
    cfg: PipelineConfig | None = None,
) -> QueryResponse:
    cfg = cfg or resolve(payload.options)
    history = _history_dicts(payload)
    if mode == "direct":
        answer = llm.generate_answer(question, [], "direct", history)
        return QueryResponse(answer=answer, mode=mode, sources=[], confidence_score=0.0)

    if mode == "compare":
        return _compute_compare_query(db, current_user, payload, question)

    retrieved = _retrieve(
        db, current_user, question, mode,
        payload.document_ids or None, payload.collection_id, cfg,
    )

    if not retrieved:
        answer = (
            "There are no documents (or no relevant passages) to answer that yet. "
            "Upload a document, or widen your selection, and ask again."
        )
        return QueryResponse(answer=answer, mode=mode, sources=[], confidence_score=0.0,
                             pipeline=_pipeline_info(cfg, retrieved))

    if abstention.should_abstain(retrieved, cfg.abstain):
        return QueryResponse(
            answer=ABSTAIN_MESSAGE, mode=mode, sources=_build_sources(retrieved),
            confidence_score=abstention.retrieval_signal(retrieved), abstained=True,
            pipeline=_pipeline_info(cfg, retrieved),
        )

    context_chunks = [c["text"] for c in retrieved]
    # One model call for both the answer and its follow-up questions (was two
    # sequential calls) — see llm.generate_rag_answer_with_followups.
    answer, followups_raw = llm.generate_rag_answer_with_followups(question, context_chunks, history)

    sources = _build_sources(retrieved)
    followups = parse_followup_questions(followups_raw) if followups_raw else []
    grounding, unsupported = _ground(answer, retrieved, cfg)
    confidence = _confidence(retrieved, answer, unsupported)

    return QueryResponse(
        answer=answer,
        mode=mode,
        sources=sources,
        confidence_score=confidence,
        followup_questions=followups,
        unsupported_sentences=unsupported,
        grounding=grounding,
        pipeline=_pipeline_info(cfg, retrieved),
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
        rerank_score = c.get("rerank_score")
        rerank_prob = round(sigmoid(rerank_score), 4) if rerank_score is not None else None
        relevance = int(round(min(1.0, rerank_prob if rerank_prob is not None else c["ranked_score"]) * 100))
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
                sparse_score=round(c.get("sparse_score", 0.0), 4),
                rerank_score=round(rerank_score, 4) if rerank_score is not None else None,
                rerank_prob=rerank_prob,
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
    cfg = resolve(payload.options)
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
        retrieved = _retrieve(
            db, current_user, question, mode,
            payload.document_ids or None, payload.collection_id, cfg,
        )

    sources = _build_sources(retrieved)
    yield _sse("sources", {"sources": [s.model_dump() for s in sources]})
    abstain = mode in ("rag", "multihop") and bool(retrieved) and abstention.should_abstain(retrieved, cfg.abstain)
    early = _pipeline_info(cfg, retrieved)
    yield _sse("pipeline", {"pipeline": early.model_dump(), "abstained": abstain})

    if abstain:
        yield _sse("token", {"token": ABSTAIN_MESSAGE})
        response = QueryResponse(
            answer=ABSTAIN_MESSAGE, mode=mode, sources=sources, abstained=True,
            confidence_score=abstention.retrieval_signal(retrieved), pipeline=early,
        )
        row = _save_history(db, current_user, question, response, mode)
        yield _sse("followups", {"followups": []})
        yield _sse("hallucination", {"unsupported_sentences": [], "grounding": [], "grounding_method": cfg.grounding})
        yield _sse("done", {"query_id": row.id, "confidence_score": response.confidence_score})
        return

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
    grounding, unsupported = _ground(answer, retrieved, cfg)
    confidence = _confidence(retrieved, answer, unsupported)

    response = QueryResponse(
        answer=answer,
        mode=mode,
        sources=sources,
        confidence_score=confidence,
        followup_questions=followups,
        unsupported_sentences=unsupported,
        grounding=grounding,
        pipeline=_pipeline_info(cfg, retrieved),
    )
    row = _save_history(db, current_user, question, response, mode)

    yield _sse("followups", {"followups": followups})
    yield _sse(
        "hallucination",
        {
            "unsupported_sentences": [u.model_dump() for u in unsupported],
            "grounding": [g.model_dump() for g in grounding],
            "grounding_method": cfg.grounding,
            "notes": response.pipeline.notes,
        },
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
