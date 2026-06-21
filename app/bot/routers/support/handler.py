"""Support menu + FAQ static page."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from app.bot.utils.keyboards import K

from app.bot.i18n import fa

logger = logging.getLogger(__name__)

router = Router(name="support")


def _support_keyboard(support_username: str) -> InlineKeyboardMarkup:
    return (
        K()
        .btn(fa.SUPPORT_FAQ_BTN, callback_data="support:faq", icon="faq")
        .primary(
            fa.SUPPORT_ONLINE_BTN,
            url=f"https://t.me/{support_username}",
            icon="chat",
        )
        .back_to_menu()
        .adjust(1)
        .as_markup()
    )


def _faq_keyboard() -> InlineKeyboardMarkup:
    return K().nav("menu:support").adjust(2).as_markup()


async def show_support_menu(callback: CallbackQuery, **kwargs) -> None:
    config = kwargs.get("config")
    support_username = config.payment.SUPPORT_USERNAME if config else "support"
    await callback.message.edit_text(
        fa.SUPPORT_HEADER,
        reply_markup=_support_keyboard(support_username),
    )
    await callback.answer()


@router.callback_query(F.data == "support:faq")
async def cb_support_faq(callback: CallbackQuery, **kwargs) -> None:
    config = kwargs.get("config")
    support_username = config.payment.SUPPORT_USERNAME if config else "support"
    bot_username = config.bot.USERNAME if config else "nc_vpn_bot"
    text = fa.FAQ_TEXT.format(
        bot_username=bot_username,
        support_username=support_username,
    )
    await callback.message.edit_text(
        text,
        reply_markup=_faq_keyboard(),
        disable_web_page_preview=True,
    )
    await callback.answer()
