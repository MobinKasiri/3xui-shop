"""Add channel_gate_passed to users

Revision ID: 0003_channel_gate_passed
Revises: 0002_v2_schema
Create Date: 2026-06-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_channel_gate_passed"
down_revision = "0002_v2_schema"
branch_labels = None
depends_on = None


def _dialect() -> str:
    return op.get_bind().dialect.name


def _col_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    if _dialect() == "sqlite":
        rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
        return any(row[1] == column for row in rows)
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if not _col_exists("users", "channel_gate_passed"):
        op.add_column(
            "users",
            sa.Column(
                "channel_gate_passed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    if _col_exists("users", "channel_gate_passed"):
        op.drop_column("users", "channel_gate_passed")
