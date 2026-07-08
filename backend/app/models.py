"""SQLAlchemy ORM models.

Primary keys and foreign keys are UUID strings (CHAR(36) on MySQL, stored as
``String(36)`` so the same schema works on SQLite for the CI/test path). UUIDs
are generated application-side so inserts don't depend on a MySQL-only
``DEFAULT (UUID())`` and behave identically across dialects.

Embeddings are stored as a JSON-serialized list of floats in a LONGTEXT column
(per the design: no separate vector database — similarity is computed in
Python/NumPy).
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


# CHAR(36) on MySQL, String(36) elsewhere. A single alias keeps every PK/FK
# column definition consistent and dialect-portable.
UUID_COL = String(36)

# Microsecond-precision timestamps. With UUID primary keys there is no
# monotonic integer id to break "same-second" ties, so newest-first ordering
# relies on fractional-second precision. Plain MySQL DATETIME truncates to
# whole seconds; DATETIME(6) preserves microseconds. SQLite keeps full
# precision natively, so the base DateTime is used there.
TIMESTAMP_COL = DateTime().with_variant(MYSQL_DATETIME(fsp=6), "mysql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login: Mapped[datetime | None] = mapped_column(TIMESTAMP_COL, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )


class TokenBlacklist(Base):
    """Revoked refresh-token JTIs (populated on logout).

    A refresh token is rejected if its ``jti`` is present here. Rows older than
    the refresh-token lifetime are safe to purge (a background job handles that
    in Phase 8); until then they simply accumulate harmlessly.
    """

    __tablename__ = "token_blacklist"

    jti: Mapped[str] = mapped_column(UUID_COL, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revoked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP_COL, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON-serialized list[float]. LONGTEXT holds large embedding vectors on
    # MySQL (production); TEXT is substituted on other dialects (e.g. SQLite)
    # so a lightweight CI path can exercise the schema without MySQL.
    embedding: Mapped[str] = mapped_column(
        LONGTEXT().with_variant(Text(), "sqlite"), nullable=False
    )
    importance_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # 'rag' | 'direct'
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )
