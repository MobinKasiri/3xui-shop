from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Self

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

logger = logging.getLogger(__name__)

# Transaction type
TX_PURCHASE = "purchase"
TX_WALLET_TOPUP = "wallet_topup"
TX_REFERRAL = "referral"
TX_REFUND = "refund"
TX_ADMIN_CREDIT = "admin_credit"

# Status
TX_PENDING = "pending"
TX_CONFIRMED = "confirmed"
TX_REJECTED = "rejected"

# Payment method
PAY_WALLET = "wallet"
PAY_CARD = "card"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.tg_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Toman, signed
    payment_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # amount user must transfer (card)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    service_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_receipt: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TX_PENDING)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_admin_notify: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="transactions")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} user={self.user_id} "
            f"type={self.type} status={self.status} amount={self.amount}>"
        )

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs: Any) -> Self:
        tx = cls(**kwargs)
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        logger.info(f"Transaction {tx.id} created user={tx.user_id} type={tx.type} amount={tx.amount}")
        return tx

    @classmethod
    async def get(cls, session: AsyncSession, tx_id: int) -> Self | None:
        result = await session.execute(select(cls).where(cls.id == tx_id))
        return result.scalar_one_or_none()

    @classmethod
    async def get_for_user(
        cls, session: AsyncSession, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[Self]:
        result = await session.execute(
            select(cls)
            .where(cls.user_id == user_id)
            .order_by(cls.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @classmethod
    async def count_for_user(cls, session: AsyncSession, user_id: int) -> int:
        from sqlalchemy import func as f
        result = await session.execute(
            select(f.count()).select_from(cls).where(cls.user_id == user_id)
        )
        return result.scalar_one()

    @classmethod
    async def get_pending(cls, session: AsyncSession) -> list[Self]:
        result = await session.execute(
            select(cls).where(cls.status == TX_PENDING).order_by(cls.created_at.asc())
        )
        return list(result.scalars().all())

    @classmethod
    async def update(cls, session: AsyncSession, tx_id: int, **kwargs: Any) -> bool:
        result = await session.execute(
            update(cls).where(cls.id == tx_id).values(**kwargs)
        )
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def claim_if_pending(cls, session: AsyncSession, tx_id: int, **kwargs: Any) -> bool:
        """Update only while status is pending — avoids double approve races."""
        result = await session.execute(
            update(cls)
            .where(cls.id == tx_id, cls.status == TX_PENDING)
            .values(**kwargs)
        )
        await session.commit()
        return result.rowcount > 0

    @classmethod
    async def count_pending(cls, session: AsyncSession) -> int:
        from sqlalchemy import func as f
        result = await session.execute(
            select(f.count()).select_from(cls).where(cls.status == TX_PENDING)
        )
        return result.scalar_one()

    @classmethod
    async def today_revenue(cls, session: AsyncSession) -> int:
        """Sum positive TXs of type 'purchase' or 'wallet_topup' confirmed today."""
        from datetime import datetime, timedelta
        from sqlalchemy import func as f
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today_start + timedelta(days=1)
        result = await session.execute(
            select(f.coalesce(f.sum(cls.amount), 0))
            .where(cls.status == TX_CONFIRMED)
            .where(cls.amount > 0)
            .where(cls.type.in_([TX_PURCHASE, TX_WALLET_TOPUP]))
            .where(cls.confirmed_at >= today_start)
            .where(cls.confirmed_at < tomorrow)
        )
        return int(result.scalar_one() or 0)

    @classmethod
    async def total_revenue(cls, session: AsyncSession) -> int:
        from sqlalchemy import func as f
        result = await session.execute(
            select(f.coalesce(f.sum(cls.amount), 0))
            .where(cls.status == TX_CONFIRMED)
            .where(cls.amount > 0)
            .where(cls.type.in_([TX_PURCHASE, TX_WALLET_TOPUP]))
        )
        return int(result.scalar_one() or 0)
