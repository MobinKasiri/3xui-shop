"""Verify mandatory channel membership."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.routers.main_menu.handler import send_welcome
from app.bot.services.required_channels import (
    audit_channels,
    missing_joined_channels,
)
from app.db.models import User

logger = logging.getLogger(__name__)

router = Router(name="channel_gate")


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

    audits = await audit_channels(bot, user.tg_id, channels)
    missing = missing_joined_channels(audits)
    if missing:
        names = ", ".join(ch.label for ch in missing)
        await callback.answer(
            fa.CHANNEL_GATE_NOT_JOINED.format(channels=names),
            show_alert=True,
        )
        return

    await User.update(session, user.tg_id, channel_gate_passed=True)
    user.channel_gate_passed = True

    await send_welcome(callback, user, session, is_new_user=is_new_user, **kwargs)
    await callback.answer()
