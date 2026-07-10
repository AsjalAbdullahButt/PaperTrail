"""Public, unauthenticated read of a shared query — the landing page behind
a "Copy share link" export. No ownership check: possessing the token (a
32-byte random value, never guessable) is the access control."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChatHistory
from ..schemas import SharedQueryOut

router = APIRouter(prefix="/api/share", tags=["share"])


def _hash_share_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.get("/{token}", response_model=SharedQueryOut)
def get_shared_query(token: str, db: Session = Depends(get_db)):
    token_hash = _hash_share_token(token)
    row = db.execute(
        select(ChatHistory).where(
            ChatHistory.share_token_hash == token_hash,
            ChatHistory.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="This share link is invalid or has expired.")
    sources = json.loads(row.sources_json) if row.sources_json else []
    return SharedQueryOut(
        question=row.question,
        answer=row.answer,
        mode=row.mode,
        confidence_score=row.confidence_score,
        source_count=len(sources),
        created_at=row.created_at,
    )
