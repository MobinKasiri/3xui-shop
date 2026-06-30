"""
VPN config service — creates, deletes, toggles configs via 3X-UI.

Each VPN config has a user-facing ``service_name`` (bot UI) and a system
``panel_email`` (3X-UI client id). Panel ``comment`` stores the display name.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.services.node_sync import schedule_node_sync
from app.bot.services.xui_api import (
    ClientAddPayload,
    ClientTraffic,
    XUIApiService,
    XUIAPIError,
    XUIError,
    XUINotFound,
    extract_vless_uuid,
)
from app.bot.utils.jalali import (
    add_days_ms,
    is_delayed_start,
    ms_to_datetime,
    start_after_first_use_ms,
)
from app.bot.utils.service_name import allocate_panel_email
from app.bot.utils.renewal_pricing import SERVICE_MAX_DAYS
from app.db.models import VPNConfig

logger = logging.getLogger(__name__)

GB = 1024 ** 3

# Panel traffic/expiry reads can lag briefly after clients/update.
RENEW_VERIFY_ATTEMPTS = 3
RENEW_VERIFY_DELAY_SEC = 0.35
RENEW_EXPIRY_TOLERANCE_MS = 120_000

# Panel disable → brief wait → delete so CDN + direct nodes drop the UUID cleanly.
DELETE_DISABLE_DELAY_SEC = 5
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
        refresh_inbound_ids: Callable[[], Awaitable[list[int]]] | None = None,
        node_sync_enabled: bool = True,
        node_ssh_user: str = "root",
        node_ssh_port: int = 22,
        node_ssh_identity: str = "",
        notify_panel_clients_changed: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.xui = xui
        self.inbound_ids = list(inbound_ids)
        self.sub_base_url = sub_base_url.rstrip("/") + "/"
        self.start_after_first_use = start_after_first_use
        self.default_duration_days = default_duration_days
        self._refresh_inbound_ids = refresh_inbound_ids
        self._node_sync_enabled = node_sync_enabled
        self._node_ssh_user = node_ssh_user
        self._node_ssh_port = node_ssh_port
        self._node_ssh_identity = node_ssh_identity
        self._notify_panel_clients_changed = notify_panel_clients_changed

    async def _signal_direct_nodes(self) -> None:
        if self._notify_panel_clients_changed:
            await self._notify_panel_clients_changed()

    async def _active_inbound_ids(self) -> list[int]:
        """Re-fetch enabled inbounds so new nodes appear without bot restart."""
        if self._refresh_inbound_ids:
            ids = await self._refresh_inbound_ids()
            if ids:
                self.inbound_ids = ids
        return self.inbound_ids

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
        display_name = service_name.strip().lower()
        if await VPNConfig.get_by_name(session, user_id, display_name):
            raise XUIError(f"duplicate_service_name:{display_name}")

        email = await allocate_panel_email(session, self.xui, tg_id)
        vless_uuid_hint = _make_uuid()
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
            uuid=vless_uuid_hint,
            sub_id=sub_id,
            total_bytes=total_bytes,
            expiry_ms=expiry_ms,
            flow="",
            inbound_ids=await self._active_inbound_ids(),
            tg_id=tg_id,
            comment=display_name,
        )

        try:
            await self.xui.add_client(payload)
            vless_uuid = await self.xui.resolve_client_uuid(
                email, hint=vless_uuid_hint,
            )
            if not vless_uuid:
                raise XUIError(f"Panel did not return uuid for {email}")
            logger.info("Panel uuid for %s: %s", email, vless_uuid)
            await self.xui.ensure_client_on_inbounds(
                email, vless_uuid, payload.inbound_ids,
            )
            if self._node_sync_enabled:
                schedule_node_sync(
                    self.xui,
                    ssh_user=self._node_ssh_user,
                    ssh_port=self._node_ssh_port,
                    ssh_identity=self._node_ssh_identity,
                )
        except XUIError as e:
            logger.error("Panel create failed for %s: %s", email, e)
            try:
                await self.xui.delete_client(email)
            except Exception as rollback_err:
                logger.debug("Rollback failed for %s: %s", email, rollback_err)
            msg = str(e).lower()
            if "duplicate email" in msg:
                raise XUIError(f"duplicate_email:{email}") from e
            raise

        sub_url = self.sub_url(sub_id)
        config = await VPNConfig.create(
            session,
            user_id=user_id,
            service_name=display_name,
            panel_email=email,
            panel_uuid=vless_uuid,
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
        logger.info(
            "Created config user=%s name=%s sub=%s inbounds=%s",
            user_id, display_name, sub_url, payload.inbound_ids,
        )
        await self._signal_direct_nodes()
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

    async def _purge_panel_client(self, email: str) -> None:
        disabled = False
        try:
            await self.xui.set_client_enabled(email, False)
            disabled = True
            logger.info("Disabled panel client before delete: %s", email)
        except XUINotFound:
            logger.info("Panel client %s not found for disable — continuing delete", email)
        except XUIError:
            raise

        if disabled:
            await self._signal_direct_nodes()
            await asyncio.sleep(DELETE_DISABLE_DELAY_SEC)

        await self.xui.delete_client(email)

    async def _panel_client_absent(self, email: str) -> bool:
        """True when the central clients API no longer has this email."""
        try:
            await self.xui.get_client(email)
            return False
        except XUINotFound:
            return True
        except XUIError:
            return False

    async def delete(self, session: AsyncSession, config: VPNConfig) -> None:
        """
        Remove a service from 3X-UI first, then the bot database.
        Tries panel_email and service_name in case they diverged.
        """
        candidates: list[str] = []
        for raw in (config.panel_email, config.service_name):
            em = (raw or "").strip().lower()
            if em and em not in candidates:
                candidates.append(em)
        if not candidates:
            raise XUIError("Config has no panel email / service name")

        last_error: XUIError | None = None
        for email in candidates:
            try:
                await self._purge_panel_client(email)
                await VPNConfig.delete(session, config.id)
                await self._signal_direct_nodes()
                return
            except XUIError as exc:
                last_error = exc
                logger.warning("Panel delete failed for %s (config %s): %s", email, config.id, exc)
                if await self._panel_client_absent(email):
                    logger.warning(
                        "Panel client %s is gone despite delete error — removing bot config %s",
                        email,
                        config.id,
                    )
                    await VPNConfig.delete(session, config.id)
                    await self._signal_direct_nodes()
                    return

        if last_error:
            raise last_error
        raise XUIError("Panel delete failed")

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

    async def renew_one(
        self,
        session: AsyncSession,
        config: VPNConfig,
        *,
        plan_id: str,
        plan_gb: int,
        plan_days: int = 0,  # ignored — renew always applies SERVICE_MAX_DAYS
    ) -> VPNConfig:
        """
        Renew: add plan GB and reset duration to SERVICE_MAX_DAYS.
        With start_after_first_use: negative expiry (clock starts on first connection).
        Preserves UUID, sub_id, and inbounds (same sub link).
        """
        email = config.panel_email
        if not await self.xui.client_exists(email):
            raise XUINotFound(f"Panel client missing: {email}")

        add_bytes = int(plan_gb) * GB
        if add_bytes <= 0:
            raise XUIError("Renewal plan has no traffic")

        traffic_before = await self.xui.get_client_traffic(email)
        record = await self.xui.get_client(email)
        new_total = (
            traffic_before.total + add_bytes
            if traffic_before.total > 0
            else add_bytes
        )
        fresh_expiry_ms = self._renew_expiry_ms()

        traffic_after = await self._apply_renew_panel_state(
            email,
            record,
            traffic_before,
            new_total=new_total,
            fresh_expiry_ms=fresh_expiry_ms,
        )
        self._assert_renewal_applied(
            traffic_before,
            traffic_after,
            add_bytes=add_bytes,
            target_expiry_ms=fresh_expiry_ms,
        )

        if not traffic_after.enable:
            try:
                await self.set_enabled(session, config, True)
            except XUIError as exc:
                logger.warning("Could not re-enable %s after renew: %s", email, exc)

        updates: dict = {
            "plan_id": plan_id,
            "plan_gb": int(traffic_after.total / GB) if traffic_after.total > 0 else config.plan_gb + plan_gb,
            "plan_days": SERVICE_MAX_DAYS,
            "is_active": True,
            "traffic_used_bytes": traffic_after.used_bytes,
        }
        if traffic_after.total > 0:
            updates["traffic_limit_bytes"] = traffic_after.total
        elif add_bytes > 0:
            updates["traffic_limit_bytes"] = config.traffic_limit_bytes + add_bytes
        if is_delayed_start(traffic_after.expiry_time):
            updates["expiry_date"] = None
        elif traffic_after.expiry_time > 0:
            updates["expiry_date"] = ms_to_datetime(traffic_after.expiry_time)

        await VPNConfig.update(session, config.id, **updates)
        for k, v in updates.items():
            setattr(config, k, v)
        expiry_mode = "first_use" if self.start_after_first_use else "from_now"
        logger.info(
            "Renewed config %s (%s): +%sGB, expiry reset to %sd (%s)",
            config.id,
            config.service_name,
            plan_gb,
            SERVICE_MAX_DAYS,
            expiry_mode,
        )
        return config

    def _renew_expiry_ms(self) -> int:
        """Panel expiry after renew — delayed start when enabled (negative ms)."""
        if self.start_after_first_use:
            return start_after_first_use_ms(SERVICE_MAX_DAYS)
        return add_days_ms(0, SERVICE_MAX_DAYS)

    async def _apply_renew_panel_state(
        self,
        email: str,
        record: dict,
        traffic_before: ClientTraffic,
        *,
        new_total: int,
        fresh_expiry_ms: int,
    ) -> ClientTraffic:
        """
        One atomic clients/update (traffic + expiry), then sync inbounds and verify.
        Re-applies start-after-first-use (negative expiry) when configured.
        """
        vless_uuid = extract_vless_uuid(record)
        inbound_ids = self.xui.inbound_ids_from_record(record)

        for attempt in range(RENEW_VERIFY_ATTEMPTS):
            await self.xui.update_client(
                email,
                **self.xui._client_fields_for_update(
                    record,
                    traffic_before,
                    total_bytes=new_total,
                    expiry_ms=fresh_expiry_ms,
                    enable=True,
                ),
            )
            if vless_uuid and inbound_ids:
                await self.xui.sync_client_quota_on_inbounds(
                    email,
                    vless_uuid,
                    inbound_ids,
                    total_bytes=new_total,
                    expiry_ms=fresh_expiry_ms,
                    enable=True,
                )

            traffic = await self.xui.get_client_traffic(email)
            if self._renew_state_ok(traffic, new_total, fresh_expiry_ms):
                logger.info(
                    "Renew panel state OK for %s (attempt %s): total=%s expiry=%s",
                    email,
                    attempt + 1,
                    traffic.total,
                    traffic.expiry_time,
                )
                return traffic

            logger.warning(
                "Renew verify retry for %s (attempt %s): total=%s expiry=%s "
                "(want total>=%s expiry~%s)",
                email,
                attempt + 1,
                traffic.total,
                traffic.expiry_time,
                new_total,
                fresh_expiry_ms,
            )
            record = await self.xui.get_client(email)
            traffic_before = traffic
            if attempt + 1 < RENEW_VERIFY_ATTEMPTS:
                await asyncio.sleep(RENEW_VERIFY_DELAY_SEC)

        return await self.xui.get_client_traffic(email)

    @staticmethod
    def _renew_state_ok(
        traffic: ClientTraffic,
        expected_total: int,
        expected_expiry_ms: int,
    ) -> bool:
        if traffic.total < expected_total:
            return False
        if is_delayed_start(expected_expiry_ms):
            if not is_delayed_start(traffic.expiry_time):
                return False
        elif is_delayed_start(traffic.expiry_time):
            return False
        return abs(traffic.expiry_time - expected_expiry_ms) <= RENEW_EXPIRY_TOLERANCE_MS

    @staticmethod
    def _assert_renewal_applied(
        before: ClientTraffic,
        after: ClientTraffic,
        *,
        add_bytes: int,
        target_expiry_ms: int,
    ) -> None:
        """Ensure panel traffic and expiry both changed — avoids charging on silent no-ops."""
        traffic_ok = False
        if add_bytes > 0 and before.total > 0 and after.total > before.total:
            traffic_ok = True
        if add_bytes > 0 and before.total == 0 and after.total >= add_bytes:
            traffic_ok = True

        expected_total = before.total + add_bytes if before.total > 0 else add_bytes
        expiry_ok = VPNService._renew_state_ok(after, expected_total, target_expiry_ms)

        if not traffic_ok:
            raise XUIAPIError(
                f"Renewal verify failed for {before.email}: panel traffic quota unchanged"
            )
        if not expiry_ok:
            raise XUIAPIError(
                f"Renewal verify failed for {before.email}: "
                f"expiry not reset to {SERVICE_MAX_DAYS}d (got {after.expiry_time})"
            )

    # ── status / VLESS strings ───────────────────────────────────────────────

    async def refresh_traffic(
        self,
        session: AsyncSession,
        config: VPNConfig,
        *,
        traffic: ClientTraffic | None = None,
    ) -> VPNConfig:
        if traffic is None:
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

    async def fetch_all_links(self, config: VPNConfig) -> list[str]:
        """All VLESS links from subscription (every enabled inbound)."""
        try:
            links = await self.xui.get_sub_links(config.subscription_id)
            if links:
                return links
        except XUIError:
            pass
        try:
            return await self.xui.get_client_links(config.panel_email)
        except XUIError:
            return []

    async def fetch_links(self, config: VPNConfig) -> tuple[str, str]:
        """
        Return (ws_link, reality_link) for legacy UI.
        When multiple Reality nodes exist, the first WS and first Reality link are returned.
        """
        links = await self.fetch_all_links(config)
        ws_link = ""
        reality_link = ""
        for link in links:
            low = link.lower()
            if "reality" in low or "pbk=" in low or "fp=" in low:
                if not reality_link:
                    reality_link = link
            elif not ws_link:
                ws_link = link
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
