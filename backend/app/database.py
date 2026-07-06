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


# echo=False keeps logs clean; pool_pre_ping avoids stale-connection errors.
engine = create_engine(settings.database_url, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency: yield a session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database_if_missing() -> None:
    """Ensure the target database exists before we connect to it."""
    server_engine = create_engine(settings.server_url, echo=False)
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
