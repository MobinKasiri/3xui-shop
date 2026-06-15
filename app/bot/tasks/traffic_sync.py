"""
Every 30 min: fetch live traffic from 3X-UI for all active configs
and update vpn_configs.traffic_used_bytes.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.utils.jalali import ms_to_datetime

from app.bot.services.xui_api import XUIApiService, XUIError
from app.db.models import VPNConfig

logger = logging.getLogger(__name__)


async def run_traffic_sync(session_factory: async_sessionmaker, xui: XUIApiService) -> None:
    logger.info("Running traffic sync...")
    async with session_factory() as session:
        configs = await VPNConfig.get_active(session)
        updated = 0
        for config in configs:
            try:
                traffic = await xui.get_client_traffic(config.panel_email)
                updates: dict = {"traffic_used_bytes": traffic.used_bytes}
                if traffic.expiry_time > 0:
                    updates["expiry_date"] = ms_to_datetime(traffic.expiry_time)
                await VPNConfig.update(session, config.id, **updates)
                updated += 1
            except XUIError as e:
                logger.debug(f"Traffic sync skip {config.panel_email}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error syncing {config.panel_email}: {e}")
    logger.info(f"Traffic sync complete. Updated {updated}/{len(configs)} configs.")
