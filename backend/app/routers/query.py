"""Query routes: the core RAG loop plus direct (no-retrieval) mode."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import llm
from ..database import get_db
from ..models import ChatHistory, Chunk, Document
from ..schemas import QueryRequest, QueryResponse, SourceOut
from ..similarity import top_k_by_similarity

router = APIRouter(prefix="/api", tags=["query"])

TOP_K = 4  # retrieve top 3-5 chunks; 4 is a good default
SNIPPET_CHARS = 240


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, db: Session = Depends(get_db)):
    question = payload.question.strip()
    mode = payload.mode

    if mode == "direct":
        answer = llm.generate_answer(question, [], "direct")
        _save_history(db, question, answer, mode)
        return QueryResponse(answer=answer, mode=mode, sources=[])

    # --- RAG mode ---
    # 1) Embed the question.
    query_vec = llm.embed_texts([question])[0]

    # 2) Load all chunk embeddings and rank by cosine similarity.
    rows = db.execute(
        select(Chunk.id, Chunk.document_id, Chunk.chunk_index, Chunk.content, Chunk.embedding)
    ).all()

    if not rows:
        answer = (
            "No documents have been uploaded yet, so there's nothing to search. "
            "Upload a document first, then ask again."
        )
        _save_history(db, question, answer, mode)
        return QueryResponse(answer=answer, mode=mode, sources=[])

    candidates = [(r.id, json.loads(r.embedding)) for r in rows]
    ranked = top_k_by_similarity(query_vec, candidates, TOP_K)

    # 3) Assemble the ranked context + source metadata.
    by_id = {r.id: r for r in rows}
    doc_titles = {
        d.id: d.filename
        for d in db.execute(select(Document.id, Document.filename)).all()
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

    # 5) Persist the exchange.
    _save_history(db, question, answer, mode)

    return QueryResponse(answer=answer, mode=mode, sources=sources)


def _save_history(db: Session, question: str, answer: str, mode: str) -> None:
    db.add(ChatHistory(question=question, answer=answer, mode=mode))
    db.commit()
