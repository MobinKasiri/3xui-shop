"""Festival promotion — grant discount codes to first N /start users."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.services.festival_settings import (
    DELIVERY_AT_PURCHASE,
    DELIVERY_ON_START,
    FestivalSettingsView,
    festival_settings_for_config,
)
from app.db.models import DiscountCode, FestivalGrant, User

logger = logging.getLogger(__name__)


async def _unique_code(session: AsyncSession, prefix: str) -> str:
    prefix = (prefix or "JSH").strip().upper()[:8]
    for _ in range(10):
        code = f"{prefix}{secrets.token_hex(3).upper()}"
        if await DiscountCode.get_by_code(session, code) is None:
            return code
    return f"{prefix}{secrets.token_hex(4).upper()}"


async def get_active_festival_grant(
    session: AsyncSession,
    user_id: int,
    config,
) -> FestivalGrant | None:
    settings = festival_settings_for_config(config)
    if not settings.is_active():
        return None
    campaign_id = settings.campaign_id
    if not campaign_id:
        return None
    grant = await FestivalGrant.get_for_user_campaign(session, user_id, campaign_id)
    if not grant:
        return None
    code = await DiscountCode.get_by_code(session, grant.code)
    if not code or not code.is_active:
        return None
    if code.expires_at and code.expires_at < datetime.utcnow():
        return None
    if code.used_count >= code.max_uses:
        return None
    return grant


async def _create_grant(
    session: AsyncSession,
    user: User,
    settings: FestivalSettingsView,
    campaign_id: str,
) -> FestivalGrant | None:
    count = await FestivalGrant.count_for_campaign(session, campaign_id)
    if count >= settings.max_users:
        return None

    existing = await FestivalGrant.get_for_user_campaign(session, user.tg_id, campaign_id)
    if existing:
        return existing

    percent = settings.data.get("discount_percent")
    amount = settings.data.get("discount_amount")
    if not percent and not amount:
        percent = 10

    valid_days = max(1, int(settings.data.get("valid_days") or 14))
    expires_at = datetime.utcnow() + timedelta(days=valid_days)
    code_str = await _unique_code(session, str(settings.data.get("code_prefix") or "JSH"))

    discount = await DiscountCode.create(
        session,
        code=code_str,
        discount_percent=int(percent) if percent else None,
        discount_amount=int(amount) if amount and not percent else None,
        max_uses=1,
        expires_at=expires_at,
        created_by=None,
        is_active=True,
    )

    slot = count + 1
    grant = await FestivalGrant.create(
        session,
        campaign_id=campaign_id,
        user_id=user.tg_id,
        code=code_str,
        discount_code_id=discount.id,
        slot_number=slot,
    )
    logger.info(
        "Festival grant slot %s/%s: code=%s user=%s campaign=%s",
        slot,
        settings.max_users,
        code_str,
        user.tg_id,
        campaign_id,
    )
    return grant


async def handle_start_festival(
    session: AsyncSession,
    user: User,
    bot: Bot,
    *,
    is_new_user: bool,
    config,
) -> FestivalGrant | None:
    """Try to grant festival discount on /start. Idempotent per user+campaign."""
    settings = festival_settings_for_config(config)
    if not settings.is_active():
        return None
    if settings.new_users_only and not is_new_user:
        return None

    campaign_id = settings.campaign_id
    if not campaign_id:
        return None

    existing = await FestivalGrant.get_for_user_campaign(session, user.tg_id, campaign_id)
    if existing:
        return existing

    grant = await _create_grant(session, user, settings, campaign_id)
    if not grant:
        return None

    try:
        if settings.delivery_mode == DELIVERY_ON_START:
            await bot.send_message(
                user.tg_id,
                settings.text(
                    "welcome_granted",
                    code=grant.code,
                    slot=grant.slot_number,
                ),
                parse_mode="HTML",
            )
        elif settings.delivery_mode == DELIVERY_AT_PURCHASE:
            await bot.send_message(
                user.tg_id,
                settings.text(
                    "welcome_pending",
                    slot=grant.slot_number,
                ),
                parse_mode="HTML",
            )
    except Exception:
        logger.exception("Failed to send festival welcome to user %s", user.tg_id)

    return grant


def festival_discount_keyboard_markup(grant: FestivalGrant):
    from app.bot.utils.keyboards import K

    return (
        K()
        .success("🎉 استفاده از تخفیف جشنواره", callback_data="buy:discount:festival")
        .adjust(1)
        .as_markup()
    )
