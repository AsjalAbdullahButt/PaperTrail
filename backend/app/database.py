"""SQLAlchemy engine, session, and schema bootstrap for MySQL (via PyMySQL).

- ``engine`` / ``SessionLocal`` are the standard SQLAlchemy handles.
- ``Base`` is the declarative base every model subclasses.
- ``get_db`` is the FastAPI dependency that yields a request-scoped session.
- ``create_database_if_missing`` connects to the server (no DB selected) and
  runs CREATE DATABASE IF NOT EXISTS so a fresh machine just works.
- ``init_db`` creates all tables defined on ``Base``.
"""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _mysql_connect_args() -> dict:
    """PyMySQL connect_args enabling TLS for managed providers (e.g. Aiven),
    which reject plain connections outright."""
    if not settings.db_ssl_mode:
        return {}
    ssl_args: dict = {"ssl": {}}
    if settings.db_ssl_ca:
        ssl_args["ssl"] = {"ca": settings.db_ssl_ca}
    return ssl_args


# Explicit pool sizing (do not rely on SQLAlchemy defaults of 5+10):
#   pool_size       - persistent connections kept open per worker process.
#   max_overflow    - extra short-lived connections allowed under burst load.
#   pool_timeout    - seconds a request waits for a free connection before erroring.
#   pool_recycle    - proactively recycle connections so MySQL's wait_timeout
#                     (default 8h) never hands us a dead socket.
#   pool_pre_ping   - cheap liveness check that also guards against stale conns.
# Effective ceiling of concurrent DB connections per worker = pool_size +
# max_overflow. Keep (workers * (pool_size + max_overflow)) below MySQL's
# max_connections. See the README's "Deployment & operations" section.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    connect_args=_mysql_connect_args(),
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency: yield a session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db() -> tuple[bool, str | None]:
    """Readiness probe: run a trivial query to confirm the DB is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def create_database_if_missing() -> None:
    """Ensure the target database exists before we connect to it."""
    server_engine = create_engine(
        settings.server_url, connect_args=_mysql_connect_args(), echo=False
    )
    with server_engine.connect() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
        conn.commit()
    server_engine.dispose()


def init_db() -> None:
    """Create the database (if needed) and all tables (if they don't exist)."""
    # Import models so they register on Base.metadata before create_all.
    from . import models  # noqa: F401

    create_database_if_missing()
    Base.metadata.create_all(bind=engine)


def document_storage_keys(db, document_id: str) -> list[str]:
    """Every stored file belonging to one document: the current original plus
    the file of each archived version (``document_versions``). The version rows
    are the only remaining reference to those files, so they must be read
    before the document row (and its cascade) is deleted."""
    from sqlalchemy import select

    from .models import Document, DocumentVersion

    keys = list(
        db.execute(
            select(DocumentVersion.storage_key).where(
                DocumentVersion.document_id == document_id
            )
        ).scalars().all()
    )
    keys.append(db.execute(
        select(Document.storage_key).where(Document.id == document_id)
    ).scalar_one_or_none())
    return [k for k in dict.fromkeys(keys) if k]


def user_storage_keys(db, user_id: str) -> list[str]:
    """Every stored document file (originals + archived versions, including
    soft-deleted documents) owned by a user."""
    from sqlalchemy import select

    from .models import Document, DocumentVersion

    current = db.execute(
        select(Document.storage_key).where(Document.user_id == user_id)
    ).scalars().all()
    versions = db.execute(
        select(DocumentVersion.storage_key)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(Document.user_id == user_id)
    ).scalars().all()
    return [k for k in dict.fromkeys([*current, *versions]) if k]


def purge_soft_deleted(retention_days: int = 30, session_factory=None) -> int:
    """Hard-delete rows soft-deleted longer than ``retention_days`` ago and
    remove their stored files (current original and archived versions).
    Returns the number of documents purged.

    Each document is purged independently: if any of its files can't be
    deleted the row is kept (and retried on the next run) instead of aborting
    the batch, and a database failure for one document doesn't undo the rest.
    Chunks/coverage/versions cascade via FK when a document row is deleted.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from .models import ChatHistory, Collection, Document
    from .storage import delete_many

    log = logging.getLogger("papertrail.cleanup")
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    purged = 0
    with (session_factory or SessionLocal)() as db:
        doc_ids = db.execute(
            select(Document.id).where(
                Document.deleted_at.isnot(None), Document.deleted_at < cutoff
            )
        ).scalars().all()
        for doc_id in doc_ids:
            try:
                doc = db.get(Document, doc_id)
                if doc is None:  # already purged by another worker
                    continue
                failed = delete_many(document_storage_keys(db, doc_id))
                if failed:
                    log.warning(
                        "Keeping document %s for retry: %d file(s) not deleted",
                        doc_id, len(failed),
                    )
                    continue
                db.delete(doc)
                db.commit()
                purged += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                log.warning("Purge of document %s failed: %s", doc_id, exc)
        for model in (Collection, ChatHistory):
            try:
                n = db.query(model).filter(
                    model.deleted_at.isnot(None), model.deleted_at < cutoff
                ).delete(synchronize_session=False)
                db.commit()
                if n:
                    log.info("Purged %d expired %s row(s).", n, model.__tablename__)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                log.warning("Purge of %s failed: %s", model.__tablename__, exc)
    return purged
