"""3X-UI panel bootstrap — login and inbound ID cache."""
from __future__ import annotations

import asyncio
import logging

from app.bot.services.vpn import VPNService
from app.bot.services.xui_api import XUIApiService
from app.config import Config

logger = logging.getLogger(__name__)

xui_service: XUIApiService | None = None
INBOUND_IDS: list[int] | None = None


async def bootstrap_inbounds(config: Config) -> bool:
    """Login to panel and cache inbound IDs. Returns True on success."""
    global xui_service, INBOUND_IDS

    if xui_service is None:
        xui_service = XUIApiService(config.xui)
    else:
        xui_service._logged_in = False

    try:
        logger.info("Connecting to XUI panel at %s", config.xui.base_url)
        if config.xui.TOKEN:
            logger.info("Using Bearer token auth — skipping cookie login.")
            xui_service._logged_in = True
        else:
            await xui_service.login()
        inbound_ids = await xui_service.enabled_inbound_ids(
            filter_names=config.xui.INBOUND_FILTER,
        )
        INBOUND_IDS = inbound_ids
        logger.info("✅ Inbound bootstrap OK — ids=%s", inbound_ids)
        return True
    except Exception as e:
        logger.warning(
            "⚠️ Inbound bootstrap FAILED: %s. "
            "VPN creation disabled until panel is reachable.",
            e,
        )
        INBOUND_IDS = None
        return False


async def bootstrap_with_retries(config: Config, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        if await bootstrap_inbounds(config):
            return True
        if attempt < retries:
            logger.info(f"Retrying XUI bootstrap ({attempt}/{retries}) in 3s...")
            await asyncio.sleep(3)
    return False


def get_vpn_service(config: Config) -> VPNService | None:
    if INBOUND_IDS and xui_service:
        return VPNService(
            xui=xui_service,
            inbound_ids=INBOUND_IDS,
            sub_base_url=config.xui.SUB_BASE_URL,
            start_after_first_use=config.xui.START_AFTER_FIRST_USE,
            default_duration_days=config.xui.DEFAULT_DURATION_DAYS,
        )
    return None


async def ensure_vpn_service(config: Config) -> VPNService | None:
    service = get_vpn_service(config)
    if service:
        return service
    if await bootstrap_inbounds(config):
        return get_vpn_service(config)
    return None


async def close_xui() -> None:
    global xui_service
    if xui_service:
        await xui_service.close()
