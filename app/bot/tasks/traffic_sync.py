"""
Every 30 min: fetch live traffic from 3X-UI for all active configs
and update vpn_configs.traffic_used_bytes.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.utils.jalali import ms_to_datetime

from app.bot.services.xui_api import XUIApiService, XUIError
from app.db.models import VPNConfig

logger = logging.getLogger(__name__)

_FETCH_CONCURRENCY = 8


async def run_traffic_sync(session_factory: async_sessionmaker, xui: XUIApiService) -> None:
    logger.info("Running traffic sync...")
    total = 0
    updated = 0
    async with session_factory() as session:
        configs = await VPNConfig.get_active(session)
        total = len(configs)
        if not configs:
            logger.info("Traffic sync complete. No active configs.")
            return

        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)

        async def _fetch_one(config: VPNConfig) -> tuple[int, dict | None]:
            async with sem:
                try:
                    traffic = await xui.get_client_traffic(config.panel_email)
                    updates: dict = {"traffic_used_bytes": traffic.used_bytes}
                    if traffic.expiry_time > 0:
                        updates["expiry_date"] = ms_to_datetime(traffic.expiry_time)
                    return config.id, updates
                except XUIError as e:
                    logger.debug("Traffic sync skip %s: %s", config.panel_email, e)
                except Exception as e:
                    logger.warning("Unexpected error syncing %s: %s", config.panel_email, e)
                return config.id, None

        results = await asyncio.gather(*(_fetch_one(cfg) for cfg in configs))
        updated = 0
        for config_id, updates in results:
            if not updates:
                continue
            await session.execute(
                update(VPNConfig).where(VPNConfig.id == config_id).values(**updates)
            )
            updated += 1
        if updated:
            await session.commit()
    logger.info("Traffic sync complete. Updated %d/%d configs.", updated, total)
