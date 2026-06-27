"""Apps menu (screenshots 14–18). OS picker → list of url= buttons per OS."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from app.bot.utils.keyboards import K

from app.bot.i18n import fa

logger = logging.getLogger(__name__)

router = Router(name="apps")

OS_LABELS = {
    "android": "Android",
    "ios": "iOS",
    "windows": "Windows",
    "mac": "Mac",
    "linux": "Linux",
}

APP_LINKS: dict[str, list[tuple[str, str]]] = {
    "android": [
        ("V2rayNG", "https://play.google.com/store/apps/details?id=com.v2ray.ang"),
        ("Hiddify", "https://play.google.com/store/apps/details?id=app.hiddify.com"),
        ("NPV Tunnel", "https://play.google.com/store/apps/details?id=com.npv.tunnel"),
        ("V2Box", "https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box"),
    ],
    "ios": [
        ("V2Box", "https://apps.apple.com/app/v2box-v2ray-client/id6446814690"),
        ("Streisand", "https://apps.apple.com/app/streisand/id6450534064"),
        ("Hiddify", "https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532"),
        ("Shadowrocket", "https://apps.apple.com/app/shadowrocket/id932747118"),
    ],
    "windows": [
        ("Hiddify", "https://github.com/hiddify/hiddify-app/releases/latest"),
        ("Nekoray", "https://github.com/MatsuriDayo/nekoray/releases/latest"),
        ("v2rayN", "https://github.com/2dust/v2rayN/releases/latest"),
    ],
    "mac": [
        ("Hiddify", "https://github.com/hiddify/hiddify-app/releases/latest"),
        ("V2Box", "https://apps.apple.com/app/v2box-v2ray-client/id6446814690"),
        ("Streisand", "https://apps.apple.com/app/streisand/id6450534064"),
    ],
    "linux": [
        ("Hiddify", "https://github.com/hiddify/hiddify-app/releases/latest"),
        ("Nekoray", "https://github.com/MatsuriDayo/nekoray/releases/latest"),
    ],
}


OS_ICONS = {
    "android": "os_android",
    "ios": "os_ios",
    "windows": "os_windows",
    "mac": "os_mac",
    "linux": "os_linux",
}


def _os_picker_keyboard() -> InlineKeyboardMarkup:
    kb = K()
    for os_id, label in fa.APPS_OS_BTN.items():
        kb.btn(label, callback_data=f"apps:os:{os_id}", icon=OS_ICONS.get(os_id, "phone"))
    return kb.back_to_menu().adjust(2, 2, 1, 1).as_markup()


def _apps_list_keyboard(os_id: str) -> InlineKeyboardMarkup:
    kb = K()
    for name, url in APP_LINKS.get(os_id, []):
        kb.primary(name, url=url, icon=OS_ICONS.get(os_id, "download"))
    return kb.nav("menu:apps").adjust(1).as_markup()


async def show_apps_menu(callback: CallbackQuery, **kwargs) -> None:
    await callback.message.edit_text(fa.APPS_HEADER, reply_markup=_os_picker_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("apps:os:"))
async def cb_apps_os(callback: CallbackQuery, **kwargs) -> None:
    os_id = callback.data.split(":")[-1]
    if os_id not in APP_LINKS:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return
    text = fa.APPS_OS_HEADER.format(os=OS_LABELS.get(os_id, os_id))
    await callback.message.edit_text(text, reply_markup=_apps_list_keyboard(os_id))
    await callback.answer()
