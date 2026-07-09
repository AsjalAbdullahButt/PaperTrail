"""users.revoked_before for refresh-token reuse revocation

Revision ID: 0003_revoked_before
Revises: 0002_collections
Create Date: 2026-07-09

Refresh tokens are rotated on every use; replay of a rotated-away token is a
theft signal. Rather than only rejecting the replayed token, the whole session
family is revoked by stamping users.revoked_before — any refresh token whose
``iat`` predates it is rejected.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision = "0003_revoked_before"
down_revision = "0002_collections"
branch_labels = None
depends_on = None


def _timestamp() -> sa.DateTime:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("revoked_before", _timestamp(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "revoked_before")
