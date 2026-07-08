"""Multi-hop retrieval: retrieve, refine the query from what was found, retrieve
again, then merge. Surfaces evidence a single query would miss."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import llm
from .retriever import hybrid_retrieve

_REFINE_SYSTEM = (
    "You refine search queries. Given some retrieved context and the user's "
    "original question, write ONE more specific search query that would find "
    "additional relevant information. Return only the query string, nothing else."
)


def _refine_query(query: str, context: list[dict]) -> str:
    snippets = "\n".join(f"- {c['text'][:200]}" for c in context[:5])
    prompt = f"Original question: {query}\n\nContext found:\n{snippets}\n\nRefined query:"
    refined = llm.complete_text(prompt, system=_REFINE_SYSTEM, temperature=0.2)
    refined = refined.strip().strip('"').splitlines()[0] if refined else ""
    return refined[:500]


def multihop_retrieve(
    db: Session,
    user_id: str,
    query: str,
    *,
    document_ids: list[str] | None = None,
    collection_id: str | None = None,
) -> list[dict]:
    """Two retrieval rounds merged: exactly two ``hybrid_retrieve`` calls."""
    from .retriever import _record_retrievals

    round1 = hybrid_retrieve(
        db, user_id, query, document_ids=document_ids,
        collection_id=collection_id, top_k=5, record=False,
    )
    refined = _refine_query(query, round1) or query
    round2 = hybrid_retrieve(
        db, user_id, refined, document_ids=document_ids,
        collection_id=collection_id, top_k=5, record=False,
    )

    # Merge, keeping the higher ranked_score for chunks seen in both rounds.
    merged: dict[str, dict] = {}
    for item in round1 + round2:
        cid = item["chunk_id"]
        if cid not in merged or item["ranked_score"] > merged[cid]["ranked_score"]:
            merged[cid] = item

    results = sorted(merged.values(), key=lambda d: d["ranked_score"], reverse=True)[:8]
    if results:
        _record_retrievals(db, user_id, [r["chunk_id"] for r in results])
    return results
