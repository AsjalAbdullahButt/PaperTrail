"""documents.summary

Revision ID: 0009_document_summary
Revises: 0008_chunking_strategy
Create Date: 2026-07-13

LLM-generated executive summary (2-4 sentences) from a document's top
highlights, shown in the upload result and document list. Nullable — offline
mode uploads and rows predating this column simply display no summary.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_document_summary"
down_revision = "0008_chunking_strategy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "summary")
