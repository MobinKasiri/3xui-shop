from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from app.bot.i18n.fa import ERRORS
from app.bot.utils.emoji import plain_alert_text
from app.bot.utils.messaging import answer_message

logger = logging.getLogger(__name__)

router = Router(name="common")


@router.errors()
async def on_error(event: ErrorEvent) -> None:
    logger.exception(f"Unhandled error: {event.exception}", exc_info=event.exception)
    # Try to notify the user if possible
    if event.update.callback_query:
        try:
            await event.update.callback_query.answer(
                plain_alert_text(ERRORS["general"]), show_alert=True
            )
        except Exception:
            pass
    elif event.update.message:
        try:
            await answer_message(event.update.message, ERRORS["general"])
        except Exception:
            pass
