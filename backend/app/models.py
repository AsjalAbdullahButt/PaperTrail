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
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Refresh tokens issued (``iat``) before this instant are rejected. Set when
    # a rotated-away refresh token is replayed — the theft signal — so every
    # outstanding refresh token for the account dies at once, not just the
    # replayed one.
    revoked_before: Mapped[datetime | None] = mapped_column(
        TIMESTAMP_COL, nullable=True
    )
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


class PasswordResetToken(Base):
    """Password-reset tokens (POST /api/auth/forgot-password).

    Only the SHA-256 hash of the raw token is stored — like TokenBlacklist
    stores refresh-token jtis, not the tokens themselves — so a leaked
    database dump can't be used to reset accounts. Single-use via ``used_at``.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP_COL, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_COL, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Storage backend key for the original upload
    # (uploads/{user_id}/{uuid}.ext) — see storage.py. Rows predating the
    # storage abstraction store "legacy://" + their old local disk path.
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # JSON: [{"heading","level","chunk_index"}] and
    #       [{"text","score","chunk_index"}] respectively.
    outline_json: Mapped[str | None] = mapped_column(
        LONGTEXT().with_variant(Text(), "sqlite"), nullable=True
    )
    highlights_json: Mapped[str | None] = mapped_column(
        LONGTEXT().with_variant(Text(), "sqlite"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_COL, nullable=True)
    # Ingestion pipeline state: "queued" | "processing" | "done" | "failed".
    # Rows predating this column were all fully processed, hence the "done"
    # server default; the upload route sets the value explicitly for new rows.
    # ``processed_at`` is kept for backward compatibility with older clients
    # of /status.
    processing_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="queued", server_default="done"
    )
    # Populated when processing_status == "failed"; user-safe message only.
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # Set to the id of an existing near-identical document (duplicate detection).
    duplicate_of: Mapped[str | None] = mapped_column(UUID_COL, nullable=True)
    # Which chunker produced this document's chunks: "character" (legacy,
    # fixed-width windows) or "semantic" (sentence-boundary-aware). Informational
    # only — existing chunks are never re-embedded when the default changes.
    chunking_strategy: Mapped[str | None] = mapped_column(
        String(16), nullable=True, server_default="character"
    )
    # Soft delete (Phase 8): non-null => in trash, excluded from all reads.
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_COL, nullable=True)
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
    page_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    section_heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retrieved_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")


class ChatHistory(Base):
    """One recorded query + answer. (Also the "query_history" of later phases:
    bookmarks, collection scoping, and stored sources for the mind map.)"""

    __tablename__ = "chat_history"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # rag|direct|multihop
    # JSON snapshot of the retrieved sources (chunk ids + scores) for the mind map.
    sources_json: Mapped[str | None] = mapped_column(
        LONGTEXT().with_variant(Text(), "sqlite"), nullable=True
    )
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    bookmarked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    bookmark_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    collection_id: Mapped[str | None] = mapped_column(UUID_COL, nullable=True)
    # Hash of the public share-link token (see password_reset_tokens for the
    # same pattern). Null = sharing is off for this query.
    share_token_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_COL, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP_COL, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )


class DocumentCollection(Base):
    __tablename__ = "document_collections"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )


class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(50), primary_key=True)


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(UUID_COL, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )


class ChunkCoverage(Base):
    """Per-(chunk, user) retrieval tally powering the coverage heatmap."""

    __tablename__ = "chunk_coverage"

    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    retrieved_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_retrieved: Mapped[datetime | None] = mapped_column(TIMESTAMP_COL, nullable=True)


class DocumentTimeline(Base):
    """Cached, LLM-extracted dated events per document (Phase 5)."""

    __tablename__ = "document_timelines"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    events_json: Mapped[str] = mapped_column(
        LONGTEXT().with_variant(Text(), "sqlite"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP_COL, nullable=False, default=_utcnow, server_default=func.now()
    )
