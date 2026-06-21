from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Self

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

logger = logging.getLogger(__name__)


class VPNConfig(Base):
    __tablename__ = "vpn_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "service_name", name="uq_vpn_configs_user_service"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.tg_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_name: Mapped[str] = mapped_column(String(40), nullable=False)
    panel_email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    panel_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    subscription_id: Mapped[str] = mapped_column(String(50), nullable=False)
    subscription_url: Mapped[str] = mapped_column(Text, nullable=False)
    traffic_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    traffic_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    expiry_date: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plan_id: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    plan_gb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    plan_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="vpn_configs")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<VPNConfig id={self.id} name={self.service_name} "
            f"email={self.panel_email} active={self.is_active}>"
        )

    @property
    def traffic_limit_gb(self) -> float:
        return self.traffic_limit_bytes / (1024 ** 3)

    @property
    def traffic_used_gb(self) -> float:
        return self.traffic_used_bytes / (1024 ** 3)

    @property
    def traffic_remaining_bytes(self) -> int:
        return max(0, self.traffic_limit_bytes - self.traffic_used_bytes)

    @property
    def usage_percent(self) -> float:
        if self.traffic_limit_bytes == 0:
            return 0.0
        return (self.traffic_used_bytes / self.traffic_limit_bytes) * 100

    @classmethod
    async def get(cls, session: AsyncSession, config_id: int) -> Self | None:
        result = await session.execute(select(cls).where(cls.id == config_id))
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_email(cls, session: AsyncSession, email: str) -> Self | None:
        result = await session.execute(select(cls).where(cls.panel_email == email))
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_name(cls, session: AsyncSession, user_id: int, service_name: str) -> Self | None:
        result = await session.execute(
            select(cls).where(
                cls.user_id == user_id,
                cls.service_name == service_name,
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def name_exists(cls, session: AsyncSession, service_name: str) -> bool:
        from sqlalchemy import func as f
        result = await session.execute(
            select(f.count()).select_from(cls).where(cls.service_name == service_name)
        )
        return (result.scalar_one() or 0) > 0

    @classmethod
    async def get_for_user(cls, session: AsyncSession, user_id: int) -> list[Self]:
        result = await session.execute(
            select(cls)
            .where(cls.user_id == user_id)
            .order_by(cls.is_active.desc(), cls.created_at.desc())
        )
        return list(result.scalars().all())

    @classmethod
    async def get_active(cls, session: AsyncSession) -> list[Self]:
        result = await session.execute(select(cls).where(cls.is_active == True))
        return list(result.scalars().all())

    @classmethod
    async def get_by_subscription_id(cls, session: AsyncSession, sub_id: str) -> Self | None:
        result = await session.execute(
            select(cls).where(cls.subscription_id == sub_id).limit(1)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def rewrite_subscription_urls(cls, session: AsyncSession, base_url: str) -> int:
        """Point all stored subscription URLs at XUI_SUB_BASE_URL + subscription_id."""
        prefix = base_url.rstrip("/") + "/"
        configs = await cls.get_all(session)
        updated = 0
        for cfg in configs:
            new_url = prefix + cfg.subscription_id
            if cfg.subscription_url != new_url:
                cfg.subscription_url = new_url
                updated += 1
        if updated:
            await session.commit()
        return updated

    @classmethod
    async def get_all(cls, session: AsyncSession) -> list[Self]:
        result = await session.execute(select(cls))
        return list(result.scalars().all())

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs: Any) -> Self:
        config = cls(**kwargs)
        session.add(config)
        await session.commit()
        await session.refresh(config)
        logger.info(f"VPNConfig created for user {config.user_id}: {config.service_name}")
        return config

    @classmethod
    async def update(cls, session: AsyncSession, config_id: int, **kwargs: Any) -> bool:
        result = await session.execute(
            update(cls).where(cls.id == config_id).values(**kwargs)
        )
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def delete(cls, session: AsyncSession, config_id: int) -> bool:
        from sqlalchemy import delete as sa_delete
        result = await session.execute(sa_delete(cls).where(cls.id == config_id))
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def count_active(cls, session: AsyncSession) -> int:
        from sqlalchemy import func as f
        result = await session.execute(
            select(f.count()).select_from(cls).where(cls.is_active == True)
        )
        return result.scalar_one()
