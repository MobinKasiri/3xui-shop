from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Self

from sqlalchemy import BigInteger, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

logger = logging.getLogger(__name__)


class FestivalGrant(Base):
    __tablename__ = "festival_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    discount_code_id: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<FestivalGrant user={self.user_id} code={self.code} slot={self.slot_number}>"

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs: Any) -> Self:
        row = cls(**kwargs)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row

    @classmethod
    async def get_for_user_campaign(
        cls, session: AsyncSession, user_id: int, campaign_id: str
    ) -> Self | None:
        result = await session.execute(
            select(cls).where(cls.user_id == user_id, cls.campaign_id == campaign_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def count_for_campaign(cls, session: AsyncSession, campaign_id: str) -> int:
        result = await session.execute(
            select(func.count()).select_from(cls).where(cls.campaign_id == campaign_id)
        )
        return int(result.scalar_one())

    @classmethod
    async def list_for_campaign(
        cls,
        session: AsyncSession,
        campaign_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Self]:
        result = await session.execute(
            select(cls)
            .where(cls.campaign_id == campaign_id)
            .order_by(cls.slot_number.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
