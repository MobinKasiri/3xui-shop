"""Referral signup rewards and referrer purchase bonus helpers."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from aiogram import Bot

from app.bot.i18n import fa
from app.bot.utils.emoji import i
from app.bot.services.referral_settings import referral_settings_for_config
from app.db.models import DiscountCode, Referral, User

logger = logging.getLogger(__name__)


def _parse_start_ref_code(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    arg = parts[1].strip()
    if not arg.startswith("ref_"):
        return None
    code = arg[4:].strip()
    return code or None


async def record_referral(
    session: AsyncSession, user: User, code: str
) -> Referral | None:
    referrer = await User.get_by_referral_code(session, code)
    if not referrer or referrer.tg_id == user.tg_id:
        return None
    existing = await Referral.get_by_referred(session, user.tg_id)
    if existing:
        return existing
    await User.update(session, user.tg_id, referred_by=referrer.tg_id)
    ref = await Referral.create(
        session, referrer_id=referrer.tg_id, referred_id=user.tg_id
    )
    logger.info("New referral: %s -> %s", referrer.tg_id, user.tg_id)
    return ref


async def _unique_discount_code(session: AsyncSession) -> str:
    for _ in range(8):
        code = f"NC{secrets.token_hex(3).upper()}"
        if await DiscountCode.get_by_code(session, code) is None:
            return code
    return f"NC{secrets.token_hex(4).upper()}"


async def grant_friend_welcome(
    session: AsyncSession,
    user: User,
    bot: "Bot",
    config,
) -> None:
    """One-time welcome gift for a user who joined via referral link."""
    if not user.referred_by:
        return
    ref = await Referral.get_by_referred(session, user.tg_id)
    if not ref or ref.friend_bonus_given:
        return

    settings = referral_settings_for_config(config)
    fw = settings.friend_welcome
    kind = (fw.get("type") or "discount_percent").strip()
    gift_label = settings.friend_gift_label()

    try:
        if kind == "wallet_toman":
            amount = int(fw.get("toman") or 0)
            if amount <= 0:
                return
            from app.bot.services.wallet import credit
            from app.db.models.transaction import TX_REFERRAL

            await credit(
                session,
                user.tg_id,
                amount,
                fa.TX_DESC_REFERRAL_FRIEND,
                tx_type=TX_REFERRAL,
            )
            await Referral.mark_friend_bonus(session, ref.id)
            await bot.send_message(
                user.tg_id,
                f"{i('gift')}<b>هدیه خوش‌آمد NC VPN</b>\n\n{gift_label} به کیف پولت واریز شد.",
                parse_mode="HTML",
            )
            return

        percent = int(fw.get("percent") or 20)
        if percent <= 0:
            return
        valid_days = max(1, int(fw.get("valid_days") or 30))
        code_str = await _unique_discount_code(session)
        expires_at = datetime.utcnow() + timedelta(days=valid_days)
        await DiscountCode.create(
            session,
            code=code_str,
            discount_percent=percent,
            max_uses=1,
            expires_at=expires_at,
            created_by=user.referred_by,
            is_active=True,
        )
        await Referral.mark_friend_bonus(session, ref.id, welcome_code=code_str)
        await bot.send_message(
            user.tg_id,
            settings.text(
                "friend_welcome",
                code=code_str,
                friend_gift=gift_label,
            ),
            parse_mode="HTML",
        )
        logger.info("Friend welcome discount %s for user %s", code_str, user.tg_id)
    except Exception:
        logger.exception("Failed to grant friend welcome to %s", user.tg_id)


async def handle_start_referral(
    session: AsyncSession,
    user: User,
    start_text: str | None,
    *,
    is_new_user: bool,
    config,
    bot: "Bot",
) -> None:
    """Process /start ref_XXX — idempotent; runs even when channel gate blocks."""
    if not is_new_user or user.referred_by:
        return
    code = _parse_start_ref_code(start_text)
    if not code:
        return
    ref = await record_referral(session, user, code)
    if ref:
        user = await User.get(session, user.tg_id) or user
        await grant_friend_welcome(session, user, bot, config)


async def credit_referrer_for_purchase(
    session: AsyncSession,
    user: User,
    config=None,
    *,
    data_dir=None,
) -> None:
    """Credit referrer when a referred user completes a purchase."""
    if not user.referred_by:
        return
    if config is not None:
        settings = referral_settings_for_config(config)
    else:
        from pathlib import Path
        from app.bot.services.referral_settings import ReferralSettingsView, load_referral_settings

        dd = Path(data_dir) if data_dir else None
        settings = ReferralSettingsView(data=load_referral_settings(dd), data_dir=dd)
    bonus = int(settings.referrer_bonus_toman or 0)
    if bonus <= 0:
        return
    ref = await Referral.get_by_referred(session, user.tg_id)
    if not ref:
        return
    from app.bot.services.wallet import credit
    from app.db.models.transaction import TX_REFERRAL

    try:
        await credit(
            session,
            ref.referrer_id,
            bonus,
            fa.TX_DESC_REFERRAL_RECEIVED,
            tx_type=TX_REFERRAL,
        )
        await Referral.add_purchase(session, ref.id, bonus)
        logger.info(
            "Referrer %s credited %s for purchase by %s",
            ref.referrer_id,
            bonus,
            user.tg_id,
        )
    except Exception:
        logger.exception("Failed to credit referrer %s", ref.referrer_id)
