"""3X-UI panel bootstrap — login and inbound ID cache."""
from __future__ import annotations

import asyncio
import logging

from app.bot.services.node_sync_signal import bump_node_sync
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
        if config.xui.NODE_SYNC_ENABLED:
            logger.warning(
                "NODE_SYNC_ENABLED=true — bot will SSH to direct nodes (usually blocked). "
                "Set NODE_SYNC_ENABLED=false; nodes use pull sync instead."
            )
        await xui_service.ensure_clean_subscription_names()
        return True
    except Exception as e:
        logger.warning(
            "⚠️ Inbound bootstrap FAILED: %s. "
            "VPN creation disabled until panel is reachable.",
            e,
        )
        INBOUND_IDS = None
        return False


async def sync_subscription_urls(config: Config, session_factory) -> None:
    """Ensure stored subscription URLs match XUI_SUB_BASE_URL (heals old nexora/bot-proxy rows)."""
    from app.db.models import VPNConfig

    base = config.xui.SUB_BASE_URL.strip()
    if not base:
        logger.warning("XUI_SUB_BASE_URL is empty — skipping subscription URL sync")
        return

    async with session_factory() as session:
        count = await VPNConfig.rewrite_subscription_urls(session, base)
    if count:
        logger.info("Synced %d subscription URL(s) to %s", count, base)
    else:
        logger.info("Subscription URLs already use %s", base)


async def bootstrap_with_retries(config: Config, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        if await bootstrap_inbounds(config):
            return True
        if attempt < retries:
            logger.info(f"Retrying XUI bootstrap ({attempt}/{retries}) in 3s...")
            await asyncio.sleep(3)
    return False


async def refresh_inbound_ids(config: Config) -> list[int]:
    """Re-query panel for all enabled inbounds (picks up new direct nodes)."""
    global INBOUND_IDS
    if xui_service is None:
        return INBOUND_IDS or []
    inbound_ids = await xui_service.enabled_inbound_ids(
        filter_names=config.xui.INBOUND_FILTER,
    )
    INBOUND_IDS = inbound_ids
    return inbound_ids


def get_vpn_service(config: Config) -> VPNService | None:
    if INBOUND_IDS and xui_service:
        async def _notify() -> None:
            await bump_node_sync(config)

        return VPNService(
            xui=xui_service,
            inbound_ids=INBOUND_IDS,
            sub_base_url=config.xui.SUB_BASE_URL,
            start_after_first_use=config.xui.START_AFTER_FIRST_USE,
            default_duration_days=config.xui.DEFAULT_DURATION_DAYS,
            refresh_inbound_ids=lambda: refresh_inbound_ids(config),
            node_sync_enabled=config.xui.NODE_SYNC_ENABLED,
            node_ssh_user=config.xui.NODE_SSH_USER,
            node_ssh_port=config.xui.NODE_SSH_PORT,
            node_ssh_identity=config.xui.NODE_SSH_IDENTITY,
            notify_panel_clients_changed=_notify,
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
