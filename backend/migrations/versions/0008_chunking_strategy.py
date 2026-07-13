"""documents.chunking_strategy

Revision ID: 0008_chunking_strategy
Revises: 0007_storage_key
Create Date: 2026-07-13

Records which chunker ("character" legacy fixed-width windows, or "semantic"
sentence-boundary-aware) produced a document's chunks. Informational only —
existing documents are never re-embedded when the default strategy changes,
so their rows backfill to "character" (what they were actually chunked with).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_chunking_strategy"
down_revision = "0007_storage_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "chunking_strategy",
            sa.String(length=16),
            nullable=True,
            server_default="character",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "chunking_strategy")
