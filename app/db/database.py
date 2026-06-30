from __future__ import annotations

import logging
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DatabaseConfig

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, config: DatabaseConfig) -> None:
        url = config.URL
        # asyncpg driver needs postgresql+asyncpg://; aiosqlite for local dev
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)

        engine_kwargs: dict = {"pool_pre_ping": True}
        if "postgresql" in url:
            engine_kwargs.update(
                pool_size=config.POOL_SIZE,
                max_overflow=config.MAX_OVERFLOW,
                pool_recycle=config.POOL_RECYCLE,
            )

        self.engine = create_async_engine(url, **engine_kwargs)
        self.session = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.debug("Database engine initialized.")

    async def close(self) -> None:
        await self.engine.dispose()
        logger.debug("Database engine closed.")
