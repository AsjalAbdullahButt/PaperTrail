"""Scheduled data-lifecycle cleanup.

Replaces the old purge-only-at-startup behaviour with a periodic job that:

* hard-deletes soft-deleted documents/collections/queries past retention
  (``database.purge_soft_deleted``),
* removes expired refresh-token blacklist rows and old password-reset tokens,
* marks ingestions that were interrupted mid-flight as failed, and
* removes failed-ingestion document rows after a short grace period.

Every step is independent, idempotent and safe to run concurrently from
several workers (a Redis lock, when configured, just avoids duplicate work).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from starlette.concurrency import run_in_threadpool

from .cache import cache
from .config import settings
from .database import SessionLocal, document_storage_keys, purge_soft_deleted

logger = logging.getLogger("papertrail.cleanup")

STUCK_MESSAGE = "Processing was interrupted before it finished. Please upload again."


def purge_expired_tokens(db) -> tuple[int, int]:
    """Delete refresh-token blacklist rows and password-reset rows that can no
    longer matter. A blacklisted jti is only consulted while its refresh token
    is still unexpired (expiry is checked first), so rows past ``expires_at``
    are dead weight; the grace period is slack for clock skew."""
    from .models import PasswordResetToken, TokenBlacklist

    now = datetime.now(timezone.utc)
    blacklist = (
        db.query(TokenBlacklist)
        .filter(
            TokenBlacklist.expires_at
            < now - timedelta(days=settings.blacklist_grace_days)
        )
        .delete(synchronize_session=False)
    )
    resets = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.expires_at
            < now - timedelta(days=settings.reset_token_retention_days)
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return blacklist, resets


def fail_stuck_documents(db) -> int:
    """Flip documents whose ingestion never finished to ``failed`` so they stop
    showing up as empty library entries. Rows are not deleted here."""
    from .models import Document

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.stuck_processing_minutes
    )
    n = (
        db.query(Document)
        .filter(
            Document.processing_status.in_(("processing", "queued")),
            Document.created_at < cutoff,
        )
        .update(
            {
                Document.processing_status: "failed",
                Document.processing_error: STUCK_MESSAGE,
                Document.processing_progress: None,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return n


def purge_failed_documents(db) -> int:
    """Delete failed-ingestion documents older than the grace period. Their
    files (normally none: the original is stored only after embedding
    succeeds) are removed first; a row whose file can't be deleted is kept."""
    from sqlalchemy import select

    from .models import Document
    from .storage import delete_many

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.failed_document_retention_days
    )
    ids = db.execute(
        select(Document.id).where(
            Document.processing_status == "failed", Document.created_at < cutoff
        )
    ).scalars().all()
    removed = 0
    for doc_id in ids:
        try:
            doc = db.get(Document, doc_id)
            if doc is None or doc.processing_status != "failed":
                continue
            if delete_many(document_storage_keys(db, doc_id)):
                continue
            db.delete(doc)
            db.commit()
            removed += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning("Removal of failed document %s failed: %s", doc_id, exc)
    return removed


def run_cleanup(session_factory=None) -> dict[str, int]:
    """Run every cleanup step once; a failing step never blocks the others."""
    counts: dict[str, int] = {}

    try:
        counts["documents_purged"] = purge_soft_deleted(
            session_factory=session_factory
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Soft-delete purge failed: %s", exc)

    steps = (
        ("tokens", purge_expired_tokens),
        ("stuck_documents_failed", fail_stuck_documents),
        ("failed_documents_removed", purge_failed_documents),
    )
    for name, step in steps:
        with (session_factory or SessionLocal)() as db:
            try:
                result = step(db)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.warning("Cleanup step %r failed: %s", name, exc)
                continue
        if name == "tokens":
            counts["blacklist_rows_removed"], counts["reset_tokens_removed"] = result
        else:
            counts[name] = result

    if any(counts.values()):
        logger.info("Cleanup finished: %s", counts)
    return counts


async def cleanup_loop() -> None:
    """Background task started by the app lifespan: run now, then every
    ``cleanup_interval_hours``. Cancelled on shutdown."""
    interval = max(settings.cleanup_interval_hours, 0.01) * 3600
    while True:
        try:
            if cache.try_lock("cleanup", ttl=int(interval * 0.9)):
                await run_in_threadpool(run_cleanup)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop must survive
            logger.warning("Cleanup run failed: %s", exc)
        await asyncio.sleep(interval)
