"""Block bot usage until the user joins required channels."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.required_channels import (
    channel_gate_keyboard,
    should_block_for_channels,
)
from app.bot.utils.messaging import (
    answer_message,
    edit_or_answer_callback,
    inner_event,
)
from app.config import Config
from app.db.models import User

logger = logging.getLogger(__name__)


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
        inner = inner_event(event)

        if (
            not config
            or not config.bot.gate_channels
            or user is None
            or bot is None
            or inner is None
        ):
            return await handler(event, data)

        if isinstance(inner, CallbackQuery) and inner.data == "channel:joined":
            return await handler(event, data)

        block, missing = await should_block_for_channels(
            bot,
            user.tg_id,
            config.bot.gate_channels,
            channel_gate_passed=user.channel_gate_passed,
        )

        if not block:
            if session is not None and not user.channel_gate_passed:
                await User.update(session, user.tg_id, channel_gate_passed=True)
                user.channel_gate_passed = True
            return await handler(event, data)

        if session is not None and user.channel_gate_passed and missing:
            await User.update(session, user.tg_id, channel_gate_passed=False)
            user.channel_gate_passed = False

        markup = channel_gate_keyboard(config.bot.gate_channels)

        if isinstance(inner, Message) and inner.text and inner.text.startswith("/start"):
            if session is not None:
                try:
                    from app.bot.services.referral_reward import handle_start_referral

                    await handle_start_referral(
                        session,
                        user,
                        inner.text,
                        is_new_user=data.get("is_new_user", False),
                        config=config,
                        bot=bot,
                    )
                except Exception:
                    logger.exception(
                        "Referral handling failed during channel gate for user %s",
                        user.tg_id,
                    )

        try:
            if isinstance(inner, Message):
                await answer_message(inner, fa.CHANNEL_GATE_TEXT, reply_markup=markup)
            elif isinstance(inner, CallbackQuery):
                await edit_or_answer_callback(
                    inner, fa.CHANNEL_GATE_TEXT, reply_markup=markup
                )
                await inner.answer()
        except Exception:
            logger.exception("Failed to show channel gate for user %s", user.tg_id)
            try:
                if isinstance(inner, Message):
                    await inner.answer(
                        "برای استفاده از ربات، ابتدا در کانال ما عضو شوید.",
                        reply_markup=markup,
                        parse_mode=None,
                    )
            except Exception:
                logger.exception(
                    "Plain channel gate fallback also failed for user %s", user.tg_id
                )
        return None
