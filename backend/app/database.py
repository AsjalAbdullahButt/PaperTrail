"""SQLAlchemy engine, session, and schema bootstrap for MySQL (via PyMySQL).

- ``engine`` / ``SessionLocal`` are the standard SQLAlchemy handles.
- ``Base`` is the declarative base every model subclasses.
- ``get_db`` is the FastAPI dependency that yields a request-scoped session.
- ``create_database_if_missing`` connects to the server (no DB selected) and
  runs CREATE DATABASE IF NOT EXISTS so a fresh machine just works.
- ``init_db`` creates all tables defined on ``Base``.
"""
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
# max_connections. See DEPLOYMENT.md.
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


def purge_soft_deleted(retention_days: int = 30) -> int:
    """Hard-delete rows soft-deleted longer than ``retention_days`` ago and
    remove their on-disk files. Returns the number of documents purged.

    Runs on startup (see the app lifespan). Chunks/coverage cascade via FK when
    a document row is deleted.
    """
    from datetime import datetime, timedelta, timezone

    from .models import ChatHistory, Collection, Document
    from .storage import storage

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    purged = 0
    with SessionLocal() as db:
        docs = (
            db.query(Document)
            .filter(Document.deleted_at.isnot(None), Document.deleted_at < cutoff)
            .all()
        )
        for doc in docs:
            if doc.storage_key:
                storage.delete(doc.storage_key)
            db.delete(doc)
            purged += 1
        for model in (Collection, ChatHistory):
            db.query(model).filter(
                model.deleted_at.isnot(None), model.deleted_at < cutoff
            ).delete(synchronize_session=False)
        db.commit()
    return purged
