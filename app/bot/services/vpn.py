"""
VPN config service — creates, deletes, toggles configs via 3X-UI.

Each VPN config maps to a single panel client (email = service_name@nexora.vpn)
attached to one or more panel inbounds.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.services.xui_api import (
    ClientAddPayload,
    XUIApiService,
    XUIError,
)
from app.bot.utils.jalali import (
    add_days_ms,
    is_delayed_start,
    ms_to_datetime,
    start_after_first_use_ms,
)
from app.bot.utils.service_name import panel_email
from app.db.models import VPNConfig

logger = logging.getLogger(__name__)

GB = 1024 ** 3
MB = 1024 ** 2


def _make_uuid() -> str:
    import uuid
    return str(uuid.uuid4())


def _make_sub_id() -> str:
    return secrets.token_hex(12)


@dataclass
class VPNConfigResult:
    config: VPNConfig
    subscription_url: str


class VPNService:
    def __init__(
        self,
        xui: XUIApiService,
        inbound_ids: list[int],
        sub_base_url: str,
        *,
        start_after_first_use: bool = True,
        default_duration_days: int = 30,
    ) -> None:
        self.xui = xui
        self.inbound_ids = list(inbound_ids)
        self.sub_base_url = sub_base_url.rstrip("/") + "/"
        self.start_after_first_use = start_after_first_use
        self.default_duration_days = default_duration_days

    def sub_url(self, sub_id: str) -> str:
        return self.sub_base_url + sub_id

    # ── single-create ────────────────────────────────────────────────────────

    async def create_one(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        plan_id: str,
        plan_gb: int,
        plan_days: int,
        service_name: str,
        tg_id: int,
    ) -> VPNConfigResult:
        """
        Create a single client on the panel and a corresponding VPNConfig row.
        Raises XUIError on panel failure (and rolls back any partial panel state).
        """
        email = panel_email(service_name)
        uuid_str = _make_uuid()
        sub_id = _make_sub_id()

        total_bytes = plan_gb * GB
        days = plan_days or self.default_duration_days
        if self.start_after_first_use:
            expiry_ms = start_after_first_use_ms(days)
            expiry_dt = None
        else:
            expiry_ms = add_days_ms(0, days)
            expiry_dt = ms_to_datetime(expiry_ms)

        payload = ClientAddPayload(
            email=email,
            uuid=uuid_str,
            sub_id=sub_id,
            total_bytes=total_bytes,
            expiry_ms=expiry_ms,
            flow="",
            inbound_ids=self.inbound_ids,
            tg_id=tg_id,
        )

        try:
            await self.xui.add_client(payload)
        except XUIError as e:
            logger.error("Panel create failed for %s: %s", email, e)
            try:
                await self.xui.delete_client(email)
            except Exception as rollback_err:
                logger.debug("Rollback failed for %s: %s", email, rollback_err)
            raise

        sub_url = self.sub_url(sub_id)
        config = await VPNConfig.create(
            session,
            user_id=user_id,
            service_name=service_name,
            panel_email=email,
            panel_uuid=uuid_str,
            subscription_id=sub_id,
            subscription_url=sub_url,
            traffic_limit_bytes=total_bytes,
            traffic_used_bytes=0,
            expiry_date=expiry_dt,
            is_active=True,
            plan_id=plan_id,
            plan_gb=plan_gb,
            plan_days=plan_days,
        )
        logger.info("Created config user=%s name=%s sub=%s", user_id, service_name, sub_url)
        return VPNConfigResult(config=config, subscription_url=sub_url)

    # ── bulk-create ──────────────────────────────────────────────────────────

    async def create_many(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        plan_id: str,
        plan_gb: int,
        plan_days: int,
        service_names: Iterable[str],
        tg_id: int,
    ) -> list[VPNConfigResult]:
        """Create N independent configs. If one fails, prior ones remain (admin can clean up)."""
        results: list[VPNConfigResult] = []
        for name in service_names:
            result = await self.create_one(
                session,
                user_id=user_id,
                plan_id=plan_id,
                plan_gb=plan_gb,
                plan_days=plan_days,
                service_name=name,
                tg_id=tg_id,
            )
            results.append(result)
        return results

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def set_enabled(
        self, session: AsyncSession, config: VPNConfig, enabled: bool
    ) -> None:
        try:
            await self.xui.set_client_enabled(config.panel_email, enabled)
        except XUIError as e:
            logger.warning("Panel toggle failed for %s: %s", config.panel_email, e)
            raise
        await VPNConfig.update(session, config.id, is_active=enabled)

    async def delete(self, session: AsyncSession, config: VPNConfig) -> None:
        try:
            await self.xui.delete_client(config.panel_email)
        except XUIError as e:
            logger.warning("Panel delete failed for %s: %s", config.panel_email, e)
        await VPNConfig.delete(session, config.id)

    async def reset_sub(self, session: AsyncSession, config: VPNConfig) -> VPNConfig:
        new_sub_id = _make_sub_id()
        try:
            await self.xui.reset_subscription(config.panel_email, new_sub_id)
        except XUIError:
            raise
        new_url = self.sub_url(new_sub_id)
        await VPNConfig.update(
            session, config.id, subscription_id=new_sub_id, subscription_url=new_url
        )
        config.subscription_id = new_sub_id
        config.subscription_url = new_url
        return config

    # ── status / VLESS strings ───────────────────────────────────────────────

    async def refresh_traffic(
        self, session: AsyncSession, config: VPNConfig
    ) -> VPNConfig:
        try:
            traffic = await self.xui.get_client_traffic(config.panel_email)
        except XUIError:
            return config

        updates: dict = {"traffic_used_bytes": traffic.used_bytes}
        if traffic.expiry_time > 0:
            updates["expiry_date"] = ms_to_datetime(traffic.expiry_time)
        elif is_delayed_start(traffic.expiry_time):
            updates["expiry_date"] = None
        await VPNConfig.update(session, config.id, **updates)
        for k, v in updates.items():
            setattr(config, k, v)
        return config

    async def fetch_links(self, config: VPNConfig) -> tuple[str, str]:
        """
        Return (ws_link, reality_link) by asking the panel for the per-client links.
        Heuristic: links containing 'reality' (in security or fp) → reality, else WS.
        Returns empty strings when not available.
        """
        try:
            links = await self.xui.get_client_links(config.panel_email)
        except XUIError:
            return "", ""

        ws_link = ""
        reality_link = ""
        for link in links:
            low = link.lower()
            if "reality" in low or "pbk=" in low or "fp=" in low:
                reality_link = link
            else:
                ws_link = link
        # Fallback: assign by order if heuristic missed
        if not (ws_link or reality_link) and links:
            ws_link = links[0] if links else ""
            reality_link = links[1] if len(links) > 1 else ""
        return ws_link, reality_link


async def get_or_refresh_traffic(
    vpn: VPNService, session: AsyncSession, config: VPNConfig
) -> tuple[int, int | None]:
    """
    Convenience: return (used_bytes, panel_expiry_ms_or_None).
    Falls back to the DB row when the panel is unreachable.
    """
    try:
        traffic = await vpn.xui.get_client_traffic(config.panel_email)
    except XUIError:
        return config.traffic_used_bytes, None
    return traffic.used_bytes, traffic.expiry_time


def utcnow() -> datetime:
    return datetime.utcnow()
