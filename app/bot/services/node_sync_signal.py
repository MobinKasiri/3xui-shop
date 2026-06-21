"""Bump a Redis counter so direct nodes can pull-sync within ~1s of bot purchases."""
from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.config import Config

logger = logging.getLogger(__name__)

SYNC_KEY = "nexora:node_sync:ver"


async def bump_node_sync(config: Config) -> None:
    """Notify SG/PL watchers that panel clients changed."""
    token = (config.xui.NODE_SYNC_TRIGGER_TOKEN or "").strip()
    if not token:
        return
    try:
        client = aioredis.from_url(config.redis.url(), decode_responses=True)
        try:
            await client.incr(SYNC_KEY)
        finally:
            await client.aclose()
    except Exception:
        logger.debug("node sync bump failed (non-fatal)", exc_info=True)


async def read_node_sync_version(config: Config) -> int:
    client = aioredis.from_url(config.redis.url(), decode_responses=True)
    try:
        val = await client.get(SYNC_KEY)
        return int(val or 0)
    finally:
        await client.aclose()
