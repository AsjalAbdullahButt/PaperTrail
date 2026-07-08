"""initial schema: users, token_blacklist, documents, chunks, chat_history

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-07

This single migration reflects app/models.py in full: UUID (CHAR(36)) primary
keys, user ownership, auth/token-revocation, and the document-processing
columns (outline, highlights, per-chunk importance/section metadata). It is the
authoritative schema so ``alembic upgrade head`` on a fresh database produces
exactly what ``Base.metadata.create_all`` would.

Column types use dialect variants (LONGTEXT/DATETIME(6) on MySQL, TEXT/DATETIME
on SQLite) so the same migration runs on the MySQL production/CI path and the
SQLite unit-test path.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


# --- Dialect-portable column type helpers (mirrors app/models.py) ---
def _uuid_col() -> sa.String:
    return sa.String(length=36)


def _timestamp() -> sa.DateTime:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _longtext() -> sa.Text:
    return mysql.LONGTEXT().with_variant(sa.Text(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login", _timestamp(), nullable=True),
        sa.Column(
            "created_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "token_blacklist",
        sa.Column("jti", _uuid_col(), nullable=False),
        sa.Column("user_id", _uuid_col(), nullable=False),
        sa.Column(
            "revoked_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", _timestamp(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index(
        "ix_token_blacklist_user_id", "token_blacklist", ["user_id"]
    )

    op.create_table(
        "documents",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("user_id", _uuid_col(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "word_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("outline_json", _longtext(), nullable=True),
        sa.Column("highlights_json", _longtext(), nullable=True),
        sa.Column("processed_at", _timestamp(), nullable=True),
        sa.Column(
            "created_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    op.create_table(
        "chunks",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("document_id", _uuid_col(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", _longtext(), nullable=False),
        sa.Column(
            "importance_score", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "page_number", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column("section_heading", sa.String(length=500), nullable=True),
        sa.Column(
            "retrieved_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])

    op.create_table(
        "chat_history",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("user_id", _uuid_col(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_history_user_id", "chat_history", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_history_user_id", table_name="chat_history")
    op.drop_table("chat_history")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_token_blacklist_user_id", table_name="token_blacklist")
    op.drop_table("token_blacklist")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
