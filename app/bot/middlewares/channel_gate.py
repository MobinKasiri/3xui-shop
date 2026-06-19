"""Block bot usage until the user joins required channels."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.required_channels import (
    channel_gate_keyboard,
    should_block_for_channels,
)
from app.config import Config
from app.db.models import User

logger = logging.getLogger(__name__)


def _inner_event(event: TelegramObject) -> Message | CallbackQuery | None:
    if isinstance(event, Update):
        return event.event  # type: ignore[return-value]
    if isinstance(event, (Message, CallbackQuery)):
        return event
    return None


class ChannelGateMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        config: Config | None = data.get("config")
        user: User | None = data.get("user")
        bot = data.get("bot")
        session: AsyncSession | None = data.get("session")
        inner = _inner_event(event)

        if (
            not config
            or not config.bot.REQUIRED_CHANNELS
            or user is None
            or bot is None
            or inner is None
        ):
            return await handler(event, data)

        if user.tg_id in config.bot.ADMINS:
            return await handler(event, data)

        if isinstance(inner, CallbackQuery) and inner.data == "channel:joined":
            return await handler(event, data)

        block, missing = await should_block_for_channels(
            bot,
            user.tg_id,
            config.bot.REQUIRED_CHANNELS,
            gate_acknowledged=user.channel_gate_passed,
        )

        if not block:
            return await handler(event, data)

        if user.channel_gate_passed and missing and session is not None:
            await User.update(session, user.tg_id, channel_gate_passed=False)
            user.channel_gate_passed = False

        markup = channel_gate_keyboard(config.bot.REQUIRED_CHANNELS)
        try:
            if isinstance(inner, Message):
                await inner.answer(fa.CHANNEL_GATE_TEXT, reply_markup=markup)
            elif isinstance(inner, CallbackQuery):
                await inner.message.edit_text(fa.CHANNEL_GATE_TEXT, reply_markup=markup)
                await inner.answer()
        except Exception:
            logger.exception("Failed to show channel gate for user %s", user.tg_id)
        return None
