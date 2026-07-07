"""Chat-history route: exposes the ChatHistory rows already persisted on every
query. Read-only, paginated, newest-first."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import ChatHistory, User
from ..schemas import ChatHistoryOut, ChatHistoryPage

router = APIRouter(prefix="/api/chat-history", tags=["chat-history"])


@router.get("", response_model=ChatHistoryPage)
def list_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Return the current user's exchanges, newest first (paginated)."""
    total = db.execute(
        select(func.count(ChatHistory.id)).where(
            ChatHistory.user_id == current_user.id
        )
    ).scalar_one()
    rows = (
        db.execute(
            select(ChatHistory)
            .where(ChatHistory.user_id == current_user.id)
            .order_by(ChatHistory.created_at.desc(), ChatHistory.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return ChatHistoryPage(
        items=[ChatHistoryOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )
