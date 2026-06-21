"""Support menu + FAQ static page."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.i18n import fa

logger = logging.getLogger(__name__)

router = Router(name="support")


def _support_keyboard(support_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.SUPPORT_FAQ_BTN, callback_data="support:faq")
    builder.button(
        text=fa.SUPPORT_ONLINE_BTN,
        url=f"https://t.me/{support_username}",
    )
    builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def _faq_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.BACK, callback_data="menu:support")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()


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
