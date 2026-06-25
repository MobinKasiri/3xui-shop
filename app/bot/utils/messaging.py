"""Safe Telegram replies — retry as plain text when HTML/custom emoji fails."""
from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from app.bot.utils.emoji import plain_alert_text

logger = logging.getLogger(__name__)


def inner_event(event: TelegramObject) -> Message | CallbackQuery | None:
    if isinstance(event, Update):
        return event.event  # type: ignore[return-value]
    if isinstance(event, (Message, CallbackQuery)):
        return event
    return None


async def answer_message(message: Message, text: str, **kwargs) -> None:
    try:
        await message.answer(text, **kwargs)
    except TelegramBadRequest:
        logger.warning("HTML answer failed for chat %s, retrying plain text", message.chat.id)
        await message.answer(
            plain_alert_text(text),
            reply_markup=kwargs.get("reply_markup"),
            parse_mode=None,
        )


async def edit_or_answer_message(
    message: Message | None,
    text: str,
    *,
    fallback_answer: Message | None = None,
    **kwargs,
) -> None:
    if message is None:
        if fallback_answer is not None:
            await answer_message(fallback_answer, text, **kwargs)
        return
    # Photo/document messages cannot be edited as text — send a new message instead.
    if message.photo or message.document or message.video:
        await answer_message(message, text, **kwargs)
        return
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest:
        logger.warning("HTML edit failed for chat %s, retrying plain text", message.chat.id)
        try:
            await message.edit_text(
                plain_alert_text(text),
                reply_markup=kwargs.get("reply_markup"),
                parse_mode=None,
            )
        except Exception:
            await answer_message(message, text, **kwargs)
    except Exception:
        await answer_message(message, text, **kwargs)


async def edit_or_answer_callback(callback: CallbackQuery, text: str, **kwargs) -> None:
    await edit_or_answer_message(callback.message, text, **kwargs)
