from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Any, Self

from sqlalchemy import BigInteger, Boolean, Integer, String, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

logger = logging.getLogger(__name__)


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    referral_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    channel_gate_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), nullable=False
    )

    vpn_configs: Mapped[list["VPNConfig"]] = relationship(  # type: ignore[name-defined]
        "VPNConfig", back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # type: ignore[name-defined]
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )
    referrals_sent: Mapped[list["Referral"]] = relationship(  # type: ignore[name-defined]
        "Referral",
        foreign_keys="Referral.referrer_id",
        back_populates="referrer",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User tg_id={self.tg_id} username={self.username}>"

    @classmethod
    def _new_referral_code(cls) -> str:
        return secrets.token_urlsafe(6).upper()[:8]

    @classmethod
    async def get(cls, session: AsyncSession, tg_id: int) -> Self | None:
        result = await session.execute(select(cls).where(cls.tg_id == tg_id))
        return result.scalar_one_or_none()

    @classmethod
    async def get_all(cls, session: AsyncSession) -> list[Self]:
        result = await session.execute(select(cls))
        return list(result.scalars().all())

    @classmethod
    async def create(cls, session: AsyncSession, tg_id: int, full_name: str, **kwargs: Any) -> Self:
        user = cls(
            tg_id=tg_id,
            full_name=full_name,
            referral_code=cls._new_referral_code(),
            **kwargs,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"User {tg_id} created.")
        return user

    @classmethod
    async def update(cls, session: AsyncSession, tg_id: int, **kwargs: Any) -> bool:
        result = await session.execute(
            update(cls).where(cls.tg_id == tg_id).values(**kwargs)
        )
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def get_by_referral_code(cls, session: AsyncSession, code: str) -> Self | None:
        result = await session.execute(select(cls).where(cls.referral_code == code))
        return result.scalar_one_or_none()

    @classmethod
    async def count(cls, session: AsyncSession) -> int:
        from sqlalchemy import func as f
        result = await session.execute(select(f.count()).select_from(cls))
        return result.scalar_one()

    @classmethod
    async def today_count(cls, session: AsyncSession) -> int:
        from datetime import datetime, timedelta
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today_start + timedelta(days=1)
        from sqlalchemy import func as f
        result = await session.execute(
            select(f.count()).select_from(cls).where(
                cls.created_at >= today_start,
                cls.created_at < tomorrow,
            )
        )
        return result.scalar_one()
