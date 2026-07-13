"""documents/document_versions: file_path -> storage_key

Revision ID: 0007_storage_key
Revises: 0006_query_share
Create Date: 2026-07-13

Introduces the storage backend abstraction (storage.py): file references are
now backend-agnostic "storage keys" instead of local filesystem paths. Existing
rows predate the abstraction and still hold a raw local disk path, so they are
prefixed with "legacy://" — storage.get()/exists()/delete() recognize that
prefix and resolve it as a local path directly (regardless of the currently
configured backend), so old uploads keep working without a re-upload.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_storage_key"
down_revision = "0006_query_share"
branch_labels = None
depends_on = None

LEGACY_PREFIX = "legacy://"


def upgrade() -> None:
    op.alter_column(
        "documents",
        "file_path",
        new_column_name="storage_key",
        existing_type=sa.String(length=1024),
        existing_nullable=True,
    )
    op.alter_column(
        "document_versions",
        "file_path",
        new_column_name="storage_key",
        existing_type=sa.String(length=1024),
        existing_nullable=True,
    )

    for table in ("documents", "document_versions"):
        t = sa.table(table, sa.column("storage_key", sa.String(length=1024)))
        op.execute(
            t.update()
            .where(t.c.storage_key.is_not(None))
            .values(storage_key=LEGACY_PREFIX + t.c.storage_key)
        )


def downgrade() -> None:
    for table in ("documents", "document_versions"):
        t = sa.table(table, sa.column("storage_key", sa.String(length=1024)))
        op.execute(
            t.update()
            .where(t.c.storage_key.like(f"{LEGACY_PREFIX}%"))
            .values(storage_key=sa.func.substr(t.c.storage_key, len(LEGACY_PREFIX) + 1))
        )

    op.alter_column(
        "document_versions",
        "storage_key",
        new_column_name="file_path",
        existing_type=sa.String(length=1024),
        existing_nullable=True,
    )
    op.alter_column(
        "documents",
        "storage_key",
        new_column_name="file_path",
        existing_type=sa.String(length=1024),
        existing_nullable=True,
    )
