"""Add festival_grants table

Revision ID: 0005_festival_grants
Revises: 0004_referral_welcome_code
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_festival_grants"
down_revision = "0004_referral_welcome_code"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        rows = conn.execute(sa.text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{name}'")).fetchall()
        return bool(rows)
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if _table_exists("festival_grants"):
        return
    op.create_table(
        "festival_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("discount_code_id", sa.Integer(), nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_festival_grants_campaign_id", "festival_grants", ["campaign_id"])
    op.create_index("ix_festival_grants_user_id", "festival_grants", ["user_id"])
    op.create_index(
        "uq_festival_grants_campaign_user",
        "festival_grants",
        ["campaign_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    if not _table_exists("festival_grants"):
        return
    op.drop_index("uq_festival_grants_campaign_user", table_name="festival_grants")
    op.drop_index("ix_festival_grants_user_id", table_name="festival_grants")
    op.drop_index("ix_festival_grants_campaign_id", table_name="festival_grants")
    op.drop_table("festival_grants")
