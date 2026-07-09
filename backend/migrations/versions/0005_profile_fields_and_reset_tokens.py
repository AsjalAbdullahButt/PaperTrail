"""users.bio/avatar_url and password_reset_tokens table

Revision ID: 0005_profile_reset
Revises: 0004_processing_status
Create Date: 2026-07-10

Adds the profile fields backing PATCH /api/auth/me (bio, avatar_url) and a
password_reset_tokens table backing POST /api/auth/forgot-password and
POST /api/auth/reset-password, following the TokenBlacklist model as a
pattern: only a hash of the token is stored, with an expiry and a used_at
marker for single use.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision = "0005_profile_reset"
down_revision = "0004_processing_status"
branch_labels = None
depends_on = None


def _timestamp() -> sa.DateTime:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=1024), nullable=True))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", _timestamp(), nullable=False),
        sa.Column("used_at", _timestamp(), nullable=True),
        sa.Column(
            "created_at", _timestamp(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"]
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "bio")
