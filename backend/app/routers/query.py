"""Query routes: the core RAG loop plus direct (no-retrieval) mode."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import llm
from ..auth import get_current_user
from ..cache import cache, make_query_key
from ..config import settings
from ..database import get_db
from ..models import ChatHistory, Chunk, Document, User
from ..ratelimit import limiter, query_limit
from ..schemas import QueryRequest, QueryResponse, SourceOut
from ..similarity import top_k_by_similarity

router = APIRouter(prefix="/api", tags=["query"])

TOP_K = 4  # retrieve top 3-5 chunks; 4 is a good default
SNIPPET_CHARS = 240


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

    # Cache: identical (user, normalized question, mode) served without
    # re-invoking the LLM. Invalidated when the user's document set changes.
    cache_key = make_query_key(current_user.id, question, mode)
    if settings.query_cache_ttl_seconds > 0:
        cached = cache.get(cache_key)
        if cached is not None:
            response = QueryResponse.model_validate_json(cached)
            _save_history(db, current_user.id, question, response.answer, mode)
            return response

    response = _compute_query(db, current_user, question, mode)
    _save_history(db, current_user.id, question, response.answer, mode)
    if settings.query_cache_ttl_seconds > 0:
        cache.set(cache_key, response.model_dump_json(), settings.query_cache_ttl_seconds)
    return response


def _compute_query(
    db: Session, current_user: User, question: str, mode: str
) -> QueryResponse:
    if mode == "direct":
        answer = llm.generate_answer(question, [], "direct")
        return QueryResponse(answer=answer, mode=mode, sources=[])

    # --- RAG mode ---
    # 1) Embed the question.
    query_vec = llm.embed_texts([question])[0]

    # 2) Load chunk embeddings and rank by cosine similarity.
    # Scoped to the current user's own documents (row-level isolation enforced
    # in application code — MySQL has no native RLS). Capped at
    # settings.max_query_chunks: brute-force NumPy cosine similarity scans every
    # loaded chunk on every query, which does not scale. Past a few thousand
    # chunks a real ANN/vector index (pgvector, Qdrant, ...) is required.
    rows = db.execute(
        select(
            Chunk.id, Chunk.document_id, Chunk.chunk_index, Chunk.content, Chunk.embedding
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.user_id == current_user.id)
        .limit(settings.max_query_chunks)
    ).all()

    if not rows:
        answer = (
            "No documents have been uploaded yet, so there's nothing to search. "
            "Upload a document first, then ask again."
        )
        return QueryResponse(answer=answer, mode=mode, sources=[])

    candidates = [(r.id, json.loads(r.embedding)) for r in rows]
    ranked = top_k_by_similarity(query_vec, candidates, TOP_K)

    # 3) Assemble the ranked context + source metadata (this user's docs only).
    by_id = {r.id: r for r in rows}
    doc_titles = {
        d.id: d.filename
        for d in db.execute(
            select(Document.id, Document.filename).where(
                Document.user_id == current_user.id
            )
        ).all()
    }

    context_chunks: list[str] = []
    sources: list[SourceOut] = []
    for citation_n, (chunk_id, score) in enumerate(ranked, start=1):
        r = by_id[chunk_id]
        context_chunks.append(r.content)
        snippet = r.content.strip().replace("\n", " ")
        if len(snippet) > SNIPPET_CHARS:
            snippet = snippet[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"
        sources.append(
            SourceOut(
                n=citation_n,
                title=doc_titles.get(r.document_id, "unknown"),
                snippet=snippet,
                score=round(max(0.0, score) * 100, 1),
                document_id=r.document_id,
                chunk_index=r.chunk_index,
            )
        )

    # 4) Generate the grounded answer.
    answer = llm.generate_answer(question, context_chunks, "rag")

    return QueryResponse(answer=answer, mode=mode, sources=sources)


def _save_history(
    db: Session, user_id: int, question: str, answer: str, mode: str
) -> None:
    db.add(
        ChatHistory(user_id=user_id, question=question, answer=answer, mode=mode)
    )
    db.commit()
