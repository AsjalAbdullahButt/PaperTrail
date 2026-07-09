"""documents.processing_status / processing_error for off-loop ingestion

Revision ID: 0004_processing_status
Revises: 0003_revoked_before
Create Date: 2026-07-09

Upload processing now runs off the event loop with the Document row created
before the heavy pipeline starts. processing_status tracks the pipeline
("queued" | "processing" | "done" | "failed"); processing_error carries a
user-safe message when it fails. Existing rows were all fully processed,
hence the "done" server default.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_processing_status"
down_revision = "0003_revoked_before"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "processing_status",
            sa.String(length=16),
            nullable=False,
            server_default="done",
        ),
    )
    op.add_column(
        "documents", sa.Column("processing_error", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "processing_status")
