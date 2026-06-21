"""Block user interactions while maintenance mode is active (panel-controlled)."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from app.bot.services.maintenance import is_maintenance_active, user_message
from app.config import Config

logger = logging.getLogger(__name__)


def _inner_event(event: TelegramObject) -> Message | CallbackQuery | None:
    if isinstance(event, Update):
        return event.event  # type: ignore[return-value]
    if isinstance(event, (Message, CallbackQuery)):
        return event
    return None


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not is_maintenance_active():
            return await handler(event, data)

        config: Config | None = data.get("config")
        inner = _inner_event(event)
        if inner is None:
            return await handler(event, data)

        user_id = inner.from_user.id if inner.from_user else None
        if config and user_id in config.bot.ADMINS:
            return await handler(event, data)

        text = user_message()
        try:
            if isinstance(inner, Message):
                await inner.answer(text, parse_mode="HTML")
            elif isinstance(inner, CallbackQuery):
                await inner.answer("ربات موقتاً غیرفعال است.", show_alert=True)
                if inner.message:
                    await inner.message.answer(text, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send maintenance message to user %s", user_id)
        return None
