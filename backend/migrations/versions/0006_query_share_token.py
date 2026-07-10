"""chat_history.share_token_hash

Revision ID: 0006_query_share
Revises: 0005_profile_reset
Create Date: 2026-07-10

Backs the "Copy share link" export option: a query can be published as a
public, read-only link. Only a hash of the token is stored (same pattern as
password_reset_tokens) so a DB leak doesn't hand out working share links.
Null means sharing is off; set means it's on.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_query_share"
down_revision = "0005_profile_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_history",
        sa.Column("share_token_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_chat_history_share_token_hash",
        "chat_history",
        ["share_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_history_share_token_hash", table_name="chat_history")
    op.drop_column("chat_history", "share_token_hash")
