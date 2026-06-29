"""Link an existing 3X-UI panel client to a bot user and notify them."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.utils.plan_labels import DEFAULT_TIER_DISPLAY_NAME
from app.bot.services.vpn import GB, VPNService
from app.bot.services.xui_api import XUIApiService, XUIError, XUINotFound, extract_vless_uuid
from app.bot.utils.jalali import (
    delayed_start_days,
    is_delayed_start,
    ms_to_datetime,
    to_jalali,
)
from app.bot.utils.persian import to_persian_digits
from app.bot.utils.service_activation import send_service_activated
from app.bot.utils.service_name import panel_email, validate
from app.db.models import User, VPNConfig

logger = logging.getLogger(__name__)


@dataclass
class ManualAssignResult:
    config: VPNConfig
    sub_url: str
    created: bool
    notified: bool


def expiry_text_for_config(cfg: VPNConfig) -> str:
    if cfg.expiry_date is None:
        return fa.DELAYED_START_FMT.format(n=to_persian_digits(cfg.plan_days))
    return to_jalali(cfg.expiry_date)


def _plan_gb_from_traffic(total_bytes: int, *, fallback_gb: int) -> int:
    if total_bytes > 0:
        return max(1, int(round(total_bytes / GB)))
    return fallback_gb


def _plan_days_from_expiry(expiry_ms: int, *, fallback_days: int) -> int:
    if is_delayed_start(expiry_ms):
        return delayed_start_days(expiry_ms)
    return fallback_days


async def assign_panel_client_to_user(
    session: AsyncSession,
    *,
    xui: XUIApiService,
    vpn: VPNService,
    bot: Bot | None,
    tg_id: int,
    service_name: str,
    plan_id: str = "manual",
    plan_gb: int = 0,
    plan_days: int = 30,
    plan_name: str = "",
    sync_tg_id: bool = True,
    send_notification: bool = True,
    dry_run: bool = False,
) -> ManualAssignResult:
    """
    Register a client that already exists on the 3X-UI panel under ``service_name``
    (panel email) for ``tg_id``, then optionally send the same activation message as
    purchase approval.
    """
    email = panel_email(service_name)
    if not validate(email):
        raise ValueError(
            f"Invalid service name {service_name!r} — use 3–30 lowercase letters/digits"
        )

    user = await User.get(session, tg_id)
    if not user:
        raise ValueError(f"User tg_id={tg_id} not found in bot database")

    try:
        record = await xui.get_client(email)
        traffic = await xui.get_client_traffic(email)
    except XUINotFound as exc:
        raise ValueError(f"Panel client {email!r} not found — create it in 3X-UI first") from exc
    except XUIError as exc:
        raise RuntimeError(f"Panel error for {email}: {exc}") from exc

    sub_id = str(record.get("subId") or record.get("sub_id") or "").strip()
    if not sub_id:
        raise ValueError(f"Panel client {email!r} has no subId — set subscription ID on panel")

    vless_uuid = extract_vless_uuid(record)
    if not vless_uuid:
        raise ValueError(f"Panel client {email!r} has no VLESS uuid")

    existing_email = await VPNConfig.get_by_email(session, email)
    if existing_email:
        if existing_email.user_id == tg_id:
            raise ValueError(
                f"Config already linked: vpn_configs.id={existing_email.id} user={tg_id}"
            )
        raise ValueError(
            f"Panel email {email!r} already belongs to user {existing_email.user_id}"
        )

    existing_name = await VPNConfig.get_by_name(session, tg_id, email)
    if existing_name:
        raise ValueError(
            f"User {tg_id} already has service {email!r} (config id={existing_name.id})"
        )

    resolved_gb = (
        plan_gb if plan_gb > 0 else _plan_gb_from_traffic(traffic.total, fallback_gb=0)
    )
    resolved_days = (
        plan_days
        if plan_days > 0
        else _plan_days_from_expiry(
            traffic.expiry_time, fallback_days=vpn.default_duration_days
        )
    )
    if resolved_gb <= 0 and traffic.total <= 0:
        raise ValueError("Could not infer plan GB — pass --plan-gb")

    total_bytes = traffic.total if traffic.total > 0 else resolved_gb * GB
    used_bytes = traffic.up + traffic.down
    expiry_dt = None
    if traffic.expiry_time > 0:
        expiry_dt = ms_to_datetime(traffic.expiry_time)

    sub_url = vpn.sub_url(sub_id)
    panel_tg = int(record.get("tgId") or 0)

    logger.info(
        "Manual assign: user=%s email=%s sub=%s gb=%s days=%s dry_run=%s",
        tg_id,
        email,
        sub_id,
        resolved_gb,
        resolved_days,
        dry_run,
    )

    if dry_run:
        placeholder = VPNConfig(
            user_id=tg_id,
            service_name=email,
            panel_email=email,
            panel_uuid=vless_uuid,
            subscription_id=sub_id,
            subscription_url=sub_url,
            traffic_limit_bytes=total_bytes,
            traffic_used_bytes=used_bytes,
            expiry_date=expiry_dt,
            is_active=bool(traffic.enable),
            plan_id=plan_id,
            plan_gb=resolved_gb,
            plan_days=resolved_days,
        )
        return ManualAssignResult(
            config=placeholder,
            sub_url=sub_url,
            created=False,
            notified=False,
        )

    if sync_tg_id and panel_tg != tg_id:
        await xui.update_client(
            email,
            **xui._client_fields_for_update(record, traffic, tg_id=tg_id),
        )
        logger.info("Panel tgId for %s set to %s", email, tg_id)

    inbound_ids = xui.inbound_ids_from_record(record)
    if inbound_ids:
        await xui.ensure_client_on_inbounds(email, vless_uuid, inbound_ids)

    config = await VPNConfig.create(
        session,
        user_id=tg_id,
        service_name=email,
        panel_email=email,
        panel_uuid=vless_uuid,
        subscription_id=sub_id,
        subscription_url=sub_url,
        traffic_limit_bytes=total_bytes,
        traffic_used_bytes=used_bytes,
        expiry_date=expiry_dt,
        is_active=bool(traffic.enable),
        plan_id=plan_id,
        plan_gb=resolved_gb,
        plan_days=resolved_days,
    )

    notified = False
    if send_notification:
        if bot is None:
            raise ValueError("BOT_TOKEN required to send notification (or use --no-send)")
        try:
            display_plan_name = (plan_name or "").strip() or DEFAULT_TIER_DISPLAY_NAME
            await send_service_activated(
                bot,
                tg_id,
                name=config.service_name,
                plan_name=display_plan_name,
                gb=config.plan_gb,
                days=config.plan_days,
                expiry=expiry_text_for_config(config),
                sub_url=sub_url,
            )
            notified = True
        except Exception:
            logger.exception("Failed to notify user %s after manual assign", tg_id)
            raise

    return ManualAssignResult(
        config=config,
        sub_url=sub_url,
        created=True,
        notified=notified,
    )
