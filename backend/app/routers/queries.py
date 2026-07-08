"""Query-history routes: list, bookmark toggle, bookmarks list, soft-delete.

These operate on the same ChatHistory rows the query endpoint records, exposing
them as a user's searchable, bookmarkable query history."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import ChatHistory, User
from ..schemas import (
    BookmarkIn,
    DeleteResult,
    MindMap,
    QueryHistoryOut,
    QueryHistoryPage,
)
from ..services.visuals import build_mindmap

router = APIRouter(prefix="/api/queries", tags=["queries"])


def _owned_query(db: Session, query_id: str, user: User) -> ChatHistory:
    row = db.get(ChatHistory, query_id)
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Query not found.")
    if row.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this query.")
    return row


@router.get("", response_model=QueryHistoryPage)
def list_queries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    base = (ChatHistory.user_id == current_user.id, ChatHistory.deleted_at.is_(None))
    total = db.execute(select(func.count(ChatHistory.id)).where(*base)).scalar_one()
    rows = db.execute(
        select(ChatHistory)
        .where(*base)
        .order_by(ChatHistory.created_at.desc(), ChatHistory.id.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    return QueryHistoryPage(
        items=[QueryHistoryOut.model_validate(r) for r in rows],
        total=int(total), limit=limit, offset=offset,
    )


@router.get("/bookmarks", response_model=list[QueryHistoryOut])
def list_bookmarks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(ChatHistory)
        .where(
            ChatHistory.user_id == current_user.id,
            ChatHistory.deleted_at.is_(None),
            ChatHistory.bookmarked.is_(True),
        )
        .order_by(ChatHistory.created_at.desc())
    ).scalars().all()
    return [QueryHistoryOut.model_validate(r) for r in rows]


@router.post("/{query_id}/bookmark", response_model=QueryHistoryOut)
def toggle_bookmark(
    query_id: str,
    payload: BookmarkIn | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle a query's bookmark. When bookmarking, an optional note is stored;
    when un-bookmarking, the note is cleared."""
    row = _owned_query(db, query_id, current_user)
    row.bookmarked = not row.bookmarked
    row.bookmark_note = (payload.note if (payload and row.bookmarked) else None)
    db.commit()
    db.refresh(row)
    return QueryHistoryOut.model_validate(row)


@router.get("/{query_id}/mindmap", response_model=MindMap)
def query_mindmap(
    query_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Node/edge graph of the query and the chunks it retrieved."""
    row = _owned_query(db, query_id, current_user)
    sources = json.loads(row.sources_json) if row.sources_json else []
    return MindMap(**build_mindmap(db, row.question, sources))


@router.delete("/{query_id}", response_model=DeleteResult)
def delete_query(
    query_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _owned_query(db, query_id, current_user)
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return DeleteResult(id=query_id, deleted=True)
