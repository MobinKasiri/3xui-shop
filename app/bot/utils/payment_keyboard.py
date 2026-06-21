"""Card-to-card payment inline keyboard — copy buttons + cancel."""
from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.i18n import fa


def _digits_only(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


def card_payment_keyboard(*, toman: int, card: str) -> InlineKeyboardMarkup:
    """Copy rial / toman / card number; red cancel."""
    rial = toman * 10
    card_num = _digits_only(card) or card.strip()

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=fa.COPY_RIAL_BTN,
            copy_text=CopyTextButton(text=str(rial)),
        ),
        InlineKeyboardButton(
            text=fa.COPY_TOMAN_BTN,
            copy_text=CopyTextButton(text=str(toman)),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=fa.COPY_CARD_BTN,
            copy_text=CopyTextButton(text=card_num),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=fa.CANCEL_PLAIN,
            callback_data="cancel_fsm",
            style=ButtonStyle.DANGER,
        ),
    )
    return builder.as_markup()
