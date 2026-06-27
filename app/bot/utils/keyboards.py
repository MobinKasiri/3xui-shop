"""Shared inline-keyboard builders with NC VPN button colors."""
from __future__ import annotations

from typing import Any

from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.i18n import fa
from app.bot.utils.emoji import (
    btn_label,
    button_vector_icons_enabled,
    custom_emoji_ready,
    icon_id,
)

# Telegram Bot API 9.4 — primary (blue), success (green), danger (red)
PRIMARY = "primary"
SUCCESS = "success"
DANGER = "danger"


class K:
    """Styled inline keyboard builder."""

    def __init__(self) -> None:
        self._b = InlineKeyboardBuilder()

    def btn(
        self,
        text: str,
        *,
        callback_data: str | None = None,
        url: str | None = None,
        style: str | None = None,
        icon: str | None = None,
        copy_text: str | None = None,
        **kwargs: Any,
    ) -> K:
        label = btn_label(icon, text)
        args: dict[str, Any] = {"text": label}
        if callback_data is not None:
            args["callback_data"] = callback_data
        if url is not None:
            args["url"] = url
        if style:
            args["style"] = style
        if copy_text is not None:
            args["copy_text"] = CopyTextButton(text=copy_text)
        if icon and button_vector_icons_enabled() and custom_emoji_ready():
            eid = icon_id(icon)
            if eid:
                args["icon_custom_emoji_id"] = eid
        self._b.button(**args, **kwargs)
        return self

    def primary(self, text: str, *, icon: str | None = None, **kwargs: Any) -> K:
        return self.btn(text, style=PRIMARY, icon=icon, **kwargs)

    def success(self, text: str, *, icon: str | None = None, **kwargs: Any) -> K:
        return self.btn(text, style=SUCCESS, icon=icon, **kwargs)

    def danger(self, text: str, *, icon: str | None = None, **kwargs: Any) -> K:
        return self.btn(text, style=DANGER, icon=icon, **kwargs)

    def cancel(self, callback_data: str = "cancel_fsm") -> K:
        return self.danger(fa.CANCEL_PLAIN, callback_data=callback_data, icon="cancel")

    def back(self, callback_data: str = "main_menu") -> K:
        return self.btn(fa.BACK, callback_data=callback_data, icon="back")

    def home(self) -> K:
        return self.btn(fa.HOME, callback_data="main_menu", icon="home")

    def back_to_menu(self) -> K:
        return self.btn(fa.BACK_TO_MENU, callback_data="main_menu", icon="home")

    def nav(self, back_callback: str = "main_menu") -> K:
        """Back + home on one row."""
        return self.back(back_callback).home()

    def row(self, *buttons: InlineKeyboardButton) -> K:
        self._b.row(*buttons)
        return self

    def adjust(self, *sizes: int, repeat: bool = False) -> K:
        self._b.adjust(*sizes, repeat=repeat)
        return self

    def as_markup(self) -> InlineKeyboardMarkup:
        return self._b.as_markup()


def back_keyboard(callback: str = "main_menu") -> InlineKeyboardMarkup:
    return K().back(callback).as_markup()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return K().back_to_menu().as_markup()


def home_keyboard() -> InlineKeyboardMarkup:
    return K().home().as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    return K().cancel().as_markup()


def confirm_cancel_keyboard(confirm_cb: str) -> InlineKeyboardMarkup:
    return (
        K()
        .success(fa.CONFIRM, callback_data=confirm_cb, icon="confirm")
        .cancel()
        .adjust(2)
        .as_markup()
    )
