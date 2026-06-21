"""Card-to-card payment inline keyboard — copy buttons + cancel."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from app.bot.i18n import fa
from app.bot.utils.keyboards import K


def _digits_only(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


def card_payment_keyboard(*, toman: int, card: str) -> InlineKeyboardMarkup:
    """Copy rial / toman / card number; red cancel."""
    rial = toman * 10
    card_num = _digits_only(card) or card.strip()

    return (
        K()
        .primary(fa.COPY_RIAL_BTN, copy_text=str(rial), icon="copy")
        .primary(fa.COPY_TOMAN_BTN, copy_text=str(toman), icon="copy")
        .primary(fa.COPY_CARD_BTN, copy_text=card_num, icon="card")
        .cancel()
        .adjust(2, 1, 1)
        .as_markup()
    )
