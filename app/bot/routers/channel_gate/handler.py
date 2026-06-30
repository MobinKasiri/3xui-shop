"""Verify mandatory channel membership."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.routers.main_menu.handler import send_welcome
from app.bot.services.required_channels import (
    audit_channels_live,
    bot_gate_capable,
    is_membership_confirmed,
    mark_gate_passed,
    missing_joined_channels,
)
from app.db.models import User

logger = logging.getLogger(__name__)

router = Router(name="channel_gate")


async def _pass_channel_gate(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    *,
    is_new_user: bool,
    kwargs: dict,
) -> None:
    await User.update(session, user.tg_id, channel_gate_passed=True)
    user.channel_gate_passed = True
    mark_gate_passed(user.tg_id)
    await send_welcome(callback, user, session, is_new_user=is_new_user, **kwargs)
    await callback.answer()


@router.callback_query(F.data == "channel:joined")
async def cb_channel_joined(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    is_new_user: bool = False,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    bot = callback.bot
    channels = config.bot.gate_channels if config else ()

    if not channels:
        await callback.answer("کانال الزامی تنظیم نشده است.", show_alert=True)
        return

    tg_user_id = callback.from_user.id if callback.from_user else user.tg_id
    audits = await audit_channels_live(bot, tg_user_id, channels)

    if is_membership_confirmed(audits):
        await _pass_channel_gate(
            callback, user, session, is_new_user=is_new_user, kwargs=kwargs
        )
        return

    missing = missing_joined_channels(audits)
    if missing:
        names = ", ".join(ch.label for ch in missing)
        await callback.answer(
            fa.CHANNEL_GATE_NOT_JOINED.format(channels=names),
            show_alert=True,
        )
        return

    if not bot_gate_capable():
        logger.warning(
            "Channel gate honor pass for user %s — bot cannot verify %s",
            tg_user_id,
            ", ".join(ch.chat_id for ch in channels),
        )
        await _pass_channel_gate(
            callback, user, session, is_new_user=is_new_user, kwargs=kwargs
        )
        return

    logger.warning(
        "Channel membership unverifiable for user %s in %s",
        tg_user_id,
        ", ".join(ch.chat_id for ch in channels),
    )
    await callback.answer(fa.CHANNEL_GATE_VERIFY_FAILED, show_alert=True)
