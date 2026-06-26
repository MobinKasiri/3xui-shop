"""Add bot_admin_notify JSON on transactions (admin Telegram message refs)

Revision ID: 0006_bot_admin_notify
Revises: 0005_festival_grants
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_bot_admin_notify"
down_revision = "0005_festival_grants"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
        return any(r[1] == column for r in rows)
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if not _column_exists("transactions", "bot_admin_notify"):
        op.add_column("transactions", sa.Column("bot_admin_notify", sa.Text(), nullable=True))


def downgrade() -> None:
    if _column_exists("transactions", "bot_admin_notify"):
        op.drop_column("transactions", "bot_admin_notify")
