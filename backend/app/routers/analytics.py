"""Per-user analytics. Every route returns only the current user's data.

Document-usage and most-queried metrics are derived from the source snapshots
stored on each query (ChatHistory.sources_json), so they reflect what was
actually retrieved. Coverage gaps come from per-chunk retrieval counts.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import ChatHistory, Chunk, Document, User
from ..schemas import (
    AnalyticsOverview,
    CoverageGap,
    DayCount,
    DocumentUsage,
    MostQueriedDocument,
    TopQuery,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _live_queries(db: Session, user_id: str) -> list[ChatHistory]:
    return db.execute(
        select(ChatHistory).where(
            ChatHistory.user_id == user_id, ChatHistory.deleted_at.is_(None)
        )
    ).scalars().all()


def _usage_from_sources(queries: list[ChatHistory]) -> dict[str, dict]:
    """Aggregate per-document retrieval stats from query source snapshots."""
    agg: dict[str, dict] = defaultdict(
        lambda: {"name": "", "retrievals": 0, "score_sum": 0.0, "last": None}
    )
    for q in queries:
        if not q.sources_json:
            continue
        try:
            sources = json.loads(q.sources_json)
        except (json.JSONDecodeError, ValueError):
            continue
        for s in sources:
            did = s.get("document_id")
            if not did:
                continue
            entry = agg[did]
            entry["name"] = s.get("document_name") or entry["name"]
            entry["retrievals"] += 1
            entry["score_sum"] += float(s.get("ranked_score", 0.0))
            if entry["last"] is None or (q.created_at and q.created_at > entry["last"]):
                entry["last"] = q.created_at
    return agg


@router.get("/overview", response_model=AnalyticsOverview)
def overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id
    total_documents = db.execute(
        select(func.count(Document.id)).where(
            Document.user_id == uid, Document.deleted_at.is_(None)
        )
    ).scalar_one()
    total_chunks = db.execute(
        select(func.count(Chunk.id))
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.user_id == uid, Document.deleted_at.is_(None))
    ).scalar_one()

    queries = _live_queries(db, uid)
    total_queries = len(queries)
    confidences = [q.confidence_score for q in queries if q.confidence_score is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    usage = _usage_from_sources(queries)
    most = None
    if usage:
        did, entry = max(usage.items(), key=lambda kv: kv[1]["retrievals"])
        most = MostQueriedDocument(name=entry["name"] or "unknown", query_count=entry["retrievals"])

    # Queries per day for the last 7 days (including empty days).
    today = datetime.now(timezone.utc).date()
    per_day: Counter[str] = Counter()
    for q in queries:
        if q.created_at and (today - q.created_at.date()).days < 7:
            per_day[q.created_at.date().isoformat()] += 1
    week = [
        DayCount(date=(today - timedelta(days=i)).isoformat(),
                 count=per_day.get((today - timedelta(days=i)).isoformat(), 0))
        for i in range(6, -1, -1)
    ]

    return AnalyticsOverview(
        total_documents=int(total_documents),
        total_queries=total_queries,
        total_chunks=int(total_chunks),
        avg_confidence=avg_confidence,
        most_queried_document=most,
        queries_this_week=week,
    )


@router.get("/top-queries", response_model=list[TopQuery])
def top_queries(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    queries = _live_queries(db, current_user.id)
    counts = Counter(q.question.strip() for q in queries if q.question.strip())
    return [TopQuery(query=q, count=c) for q, c in counts.most_common(limit)]


@router.get("/document-usage", response_model=list[DocumentUsage])
def document_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    usage = _usage_from_sources(_live_queries(db, current_user.id))
    out: list[DocumentUsage] = []
    for did, entry in usage.items():
        retrievals = entry["retrievals"]
        out.append(
            DocumentUsage(
                document_id=did,
                name=entry["name"] or "unknown",
                total_retrievals=retrievals,
                avg_similarity=round(entry["score_sum"] / retrievals, 4) if retrievals else 0.0,
                last_queried=entry["last"],
            )
        )
    out.sort(key=lambda u: u.total_retrievals, reverse=True)
    return out


@router.get("/coverage-gaps", response_model=list[CoverageGap])
def coverage_gaps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Documents where more than 40% of chunks have never been retrieved."""
    rows = db.execute(
        select(
            Document.id, Document.filename,
            func.count(Chunk.id),
            func.sum(case((Chunk.retrieved_count == 0, 1), else_=0)),
        )
        .join(Chunk, Chunk.document_id == Document.id)
        .where(Document.user_id == current_user.id, Document.deleted_at.is_(None))
        .group_by(Document.id)
    ).all()

    gaps: list[CoverageGap] = []
    for doc_id, name, total, unexplored in rows:
        total = int(total or 0)
        unexplored = int(unexplored or 0)
        if total == 0:
            continue
        pct = round(unexplored / total * 100)
        if pct > 40:
            gaps.append(
                CoverageGap(
                    document_id=doc_id, name=name, total_chunks=total,
                    unexplored_chunks=unexplored, unexplored_pct=pct,
                )
            )
    gaps.sort(key=lambda g: g.unexplored_pct, reverse=True)
    return gaps
