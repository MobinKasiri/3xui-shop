"""
VPN Config service — creates, renews, and deletes configs using the XUI API.
All 3X-UI calls go through xui_api.XUIApiService; no raw aiohttp here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.services.xui_api import XUIApiService, ClientAddPayload, XUIError
from app.bot.utils.ids import make_panel_email, make_uuid
from app.bot.utils.jalali import (
    add_days_ms,
    extend_expiry_ms,
    is_delayed_start,
    ms_to_datetime,
    start_after_first_use_ms,
)
from app.db.models import VPNConfig

logger = logging.getLogger(__name__)

GB = 1024 ** 3
MB = 1024 ** 2


@dataclass
class VPNConfigResult:
    config: VPNConfig
    subscription_url: str


class VPNService:
    def __init__(
        self,
        xui: XUIApiService,
        ws_inbound_id: int,
        reality_inbound_id: int,
        sub_base_url: str,
        *,
        start_after_first_use: bool = True,
        default_duration_days: int = 30,
    ) -> None:
        self.xui = xui
        self.ws_id = ws_inbound_id
        self.reality_id = reality_inbound_id
        self.sub_base_url = sub_base_url.rstrip("/") + "/"
        self.start_after_first_use = start_after_first_use
        self.default_duration_days = default_duration_days

    async def create_config(
        self,
        session: AsyncSession,
        user_id: int,
        plan_key: str,
        traffic_mb: int,
        duration_days: int,
        tg_id: int,
        is_trial: bool = False,
        bonus_mb: int = 0,
    ) -> VPNConfigResult:
        """
        Create client on both inbounds in one API call.
        Panel returns obj=null on success — subscription URL is built from our subId.
        """
        email = make_panel_email(user_id)
        panel_uuid = make_uuid()
        sub_id = make_uuid().replace("-", "")[:20]

        total_mb = traffic_mb + bonus_mb
        total_bytes = total_mb * MB
        days = duration_days or self.default_duration_days
        if self.start_after_first_use:
            expiry_ms = start_after_first_use_ms(days)
            expiry_dt = None
        else:
            expiry_ms = add_days_ms(0, days)
            expiry_dt = ms_to_datetime(expiry_ms)

        payload = ClientAddPayload(
            email=email,
            uuid=panel_uuid,
            sub_id=sub_id,
            total_bytes=total_bytes,
            expiry_ms=expiry_ms,
            flow="",
            inbound_ids=[self.ws_id, self.reality_id],
            tg_id=tg_id,
        )

        try:
            await self.xui.add_client(payload)
        except XUIError as e:
            logger.error("Panel create failed for %s: %s", email, e)
            try:
                await self.xui.delete_client(email)
            except Exception as rollback_err:
                logger.error("Rollback failed for %s: %s", email, rollback_err)
            raise

        sub_url = self.sub_base_url + sub_id

        config = await VPNConfig.create(
            session,
            user_id=user_id,
            panel_email=email,
            panel_uuid=panel_uuid,
            subscription_id=sub_id,
            subscription_url=sub_url,
            traffic_limit_bytes=total_bytes,
            traffic_used_bytes=0,
            expiry_date=expiry_dt,
            is_trial=is_trial,
            is_active=True,
            plan_key=plan_key,
        )
        logger.info("DB config saved user=%s sub_url=%s", user_id, sub_url)
        return VPNConfigResult(config=config, subscription_url=sub_url)

    async def renew_config(
        self,
        session: AsyncSession,
        config: VPNConfig,
        plan_traffic_mb: int,
        plan_days: int,
    ) -> VPNConfig:
        try:
            live = await self.xui.get_client_traffic(config.panel_email)
            used_bytes = live.used_bytes
            panel_expiry_ms = live.expiry_time
        except XUIError:
            used_bytes = config.traffic_used_bytes
            panel_expiry_ms = 0

        remaining = max(0, config.traffic_limit_bytes - used_bytes)
        new_total_bytes = remaining + (plan_traffic_mb * MB)

        if panel_expiry_ms < 0:
            current_ms = panel_expiry_ms
        elif panel_expiry_ms > 0:
            current_ms = panel_expiry_ms
        elif config.expiry_date:
            current_ms = int(config.expiry_date.timestamp() * 1000)
        else:
            current_ms = 0

        delayed = is_delayed_start(current_ms) or (
            self.start_after_first_use and current_ms == 0
        )
        new_expiry_ms = extend_expiry_ms(
            current_ms, plan_days, delayed_start=delayed
        )
        new_expiry_dt = ms_to_datetime(new_expiry_ms) if new_expiry_ms > 0 else None

        await self.xui.update_client(
            config.panel_email,
            total_bytes=new_total_bytes,
            expiry_ms=new_expiry_ms,
            flow="xtls-rprx-vision",
            tg_id=config.user_id,
        )

        await VPNConfig.update(
            session,
            config.id,
            traffic_limit_bytes=new_total_bytes,
            traffic_used_bytes=used_bytes,
            expiry_date=new_expiry_dt,
            is_active=True,
            renewed_at=datetime.utcnow(),
        )
        await session.refresh(config)
        return config

    async def delete_config(self, session: AsyncSession, config: VPNConfig) -> None:
        try:
            await self.xui.delete_client(config.panel_email)
        except XUIError as e:
            logger.warning(f"Panel delete failed for {config.panel_email}: {e}")
        await VPNConfig.update(session, config.id, is_active=False)
