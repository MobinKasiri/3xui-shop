"""Bump a Redis counter so direct nodes can pull-sync within ~1s of bot purchases."""
from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.config import Config

logger = logging.getLogger(__name__)

SYNC_KEY = "nexora:node_sync:ver"

_redis_client: aioredis.Redis | None = None


async def _get_redis(config: Config) -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            config.redis.url(),
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def bump_node_sync(config: Config) -> None:
    """Notify SG/PL watchers that panel clients changed."""
    token = (config.xui.NODE_SYNC_TRIGGER_TOKEN or "").strip()
    if not token:
        return
    try:
        client = await _get_redis(config)
        await client.incr(SYNC_KEY)
    except Exception:
        logger.debug("node sync bump failed (non-fatal)", exc_info=True)


async def read_node_sync_version(config: Config) -> int:
    try:
        client = await _get_redis(config)
        val = await client.get(SYNC_KEY)
        return int(val or 0)
    except Exception:
        logger.debug("node sync version read failed", exc_info=True)
        return 0
