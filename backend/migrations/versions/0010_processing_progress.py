"""documents.processing_progress

Revision ID: 0010_processing_progress
Revises: 0009_document_summary
Create Date: 2026-07-13

Fine-grained ingestion progress (JSON: step/progress/chunks_done/chunks_total),
updated at checkpoints during upload processing and polled by
GET /api/documents/{id}/progress. Cleared to null once processing finishes
(done or failed).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_processing_progress"
down_revision = "0009_document_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("processing_progress", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "processing_progress")
