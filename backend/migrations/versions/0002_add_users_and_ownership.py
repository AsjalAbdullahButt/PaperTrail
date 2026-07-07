"""add users table and user_id ownership columns

Revision ID: 0002_users
Revises: 0001_initial
Create Date: 2026-07-07

Adds authentication (users) and row-level ownership. user_id is NOT NULL on
documents and chat_history: this is a breaking change for any pre-auth data.
On an empty database it applies cleanly; a populated database must backfill
user_id (e.g. assign existing rows to an admin user) before this runs.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_users"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.add_column("documents", sa.Column("user_id", sa.Integer(), nullable=False))
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_foreign_key(
        "fk_documents_user_id",
        "documents",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column("chat_history", sa.Column("user_id", sa.Integer(), nullable=False))
    op.create_index("ix_chat_history_user_id", "chat_history", ["user_id"])
    op.create_foreign_key(
        "fk_chat_history_user_id",
        "chat_history",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_history_user_id", "chat_history", type_="foreignkey")
    op.drop_index("ix_chat_history_user_id", table_name="chat_history")
    op.drop_column("chat_history", "user_id")

    op.drop_constraint("fk_documents_user_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_column("documents", "user_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
