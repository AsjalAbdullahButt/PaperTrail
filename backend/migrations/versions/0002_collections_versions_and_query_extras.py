"""collections, tags, document versions, chunk coverage, timelines; document
and chat_history extras

Revision ID: 0002_collections
Revises: 0001_initial
Create Date: 2026-07-09

Adds: collections, document_collections, document_tags, document_versions,
chunk_coverage, document_timelines. Adds columns: documents.version_number,
documents.duplicate_of, documents.deleted_at; chat_history.sources_json,
chat_history.confidence_score, chat_history.bookmarked,
chat_history.bookmark_note, chat_history.collection_id,
chat_history.deleted_at.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision = "0002_collections"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _uuid_col() -> sa.String:
    return sa.String(length=36)


def _timestamp() -> sa.DateTime:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _longtext() -> sa.Text:
    return mysql.LONGTEXT().with_variant(sa.Text(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "version_number", sa.Integer(), nullable=False, server_default="1"
        ),
    )
    op.add_column(
        "documents", sa.Column("duplicate_of", _uuid_col(), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("deleted_at", _timestamp(), nullable=True)
    )

    op.add_column(
        "chat_history", sa.Column("sources_json", _longtext(), nullable=True)
    )
    op.add_column(
        "chat_history",
        sa.Column("confidence_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "chat_history",
        sa.Column(
            "bookmarked", sa.Boolean(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "chat_history", sa.Column("bookmark_note", sa.Text(), nullable=True)
    )
    op.add_column(
        "chat_history", sa.Column("collection_id", _uuid_col(), nullable=True)
    )
    op.add_column(
        "chat_history", sa.Column("deleted_at", _timestamp(), nullable=True)
    )

    op.create_table(
        "collections",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("user_id", _uuid_col(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted_at", _timestamp(), nullable=True),
        sa.Column(
            "created_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])

    op.create_table(
        "document_collections",
        sa.Column("document_id", _uuid_col(), nullable=False),
        sa.Column("collection_id", _uuid_col(), nullable=False),
        sa.Column(
            "added_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id", "collection_id"),
    )

    op.create_table(
        "document_tags",
        sa.Column("document_id", _uuid_col(), nullable=False),
        sa.Column("tag", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id", "tag"),
    )

    op.create_table(
        "document_versions",
        sa.Column("id", _uuid_col(), nullable=False),
        sa.Column("document_id", _uuid_col(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column(
            "uploaded_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_versions_document_id", "document_versions", ["document_id"]
    )

    op.create_table(
        "chunk_coverage",
        sa.Column("chunk_id", _uuid_col(), nullable=False),
        sa.Column("user_id", _uuid_col(), nullable=False),
        sa.Column(
            "retrieved_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_retrieved", _timestamp(), nullable=True),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chunk_id", "user_id"),
    )

    op.create_table(
        "document_timelines",
        sa.Column("document_id", _uuid_col(), nullable=False),
        sa.Column("events_json", _longtext(), nullable=False),
        sa.Column(
            "generated_at", _timestamp(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id"),
    )


def downgrade() -> None:
    op.drop_table("document_timelines")
    op.drop_table("chunk_coverage")
    op.drop_index(
        "ix_document_versions_document_id", table_name="document_versions"
    )
    op.drop_table("document_versions")
    op.drop_table("document_tags")
    op.drop_table("document_collections")
    op.drop_index("ix_collections_user_id", table_name="collections")
    op.drop_table("collections")

    op.drop_column("chat_history", "deleted_at")
    op.drop_column("chat_history", "collection_id")
    op.drop_column("chat_history", "bookmark_note")
    op.drop_column("chat_history", "bookmarked")
    op.drop_column("chat_history", "confidence_score")
    op.drop_column("chat_history", "sources_json")

    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "duplicate_of")
    op.drop_column("documents", "version_number")
