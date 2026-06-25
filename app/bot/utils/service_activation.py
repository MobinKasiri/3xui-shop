"""Professional service-activation message with subscription QR code."""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, Message

from app.bot.i18n import fa
from app.bot.utils.keyboards import K
from app.bot.utils.persian import to_persian_digits
from app.bot.utils.qr import make_qr_png


def build_service_activated_caption(
    *,
    name: str,
    plan_name: str,
    gb: int,
    days: int,
    expiry: str,
    sub_url: str,
) -> str:
    return fa.SERVICE_ACTIVATED_CAPTION.format(
        name=name,
        plan_name=plan_name,
        gb=to_persian_digits(gb),
        days=to_persian_digits(days),
        expiry=expiry,
        sub_url=sub_url,
    )


def service_activated_keyboard(sub_url: str) -> InlineKeyboardMarkup:
    return (
        K()
        .primary(fa.SERVICE_ACTIVATED_COPY_BTN, copy_text=sub_url, icon="copy")
        .btn(fa.SERVICE_ACTIVATED_OPEN_BTN, url=sub_url, icon="link")
        .btn(fa.MAIN_BTN_CONFIGS, callback_data="menu:configs", icon="btn_configs")
        .home()
        .adjust(2, 1, 1)
        .as_markup()
    )


async def send_service_activated(
    bot: Bot,
    chat_id: int,
    *,
    name: str,
    plan_name: str,
    gb: int,
    days: int,
    expiry: str,
    sub_url: str,
) -> None:
    caption = build_service_activated_caption(
        name=name,
        plan_name=plan_name,
        gb=gb,
        days=days,
        expiry=expiry,
        sub_url=sub_url,
    )
    qr = make_qr_png(sub_url)
    photo = BufferedInputFile(qr.getvalue(), filename="qr.png")
    await bot.send_photo(
        chat_id,
        photo=photo,
        caption=caption,
        parse_mode="HTML",
        reply_markup=service_activated_keyboard(sub_url),
    )


async def send_service_activated_reply(
    message: Message,
    *,
    name: str,
    plan_name: str,
    gb: int,
    days: int,
    expiry: str,
    sub_url: str,
) -> None:
    await send_service_activated(
        message.bot,
        message.chat.id,
        name=name,
        plan_name=plan_name,
        gb=gb,
        days=days,
        expiry=expiry,
        sub_url=sub_url,
    )
