"""Send Persian notifications to users and forward events to admin chats."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message
from app.bot.utils.keyboards import K

from app.bot.i18n import fa
from app.bot.utils.jalali import to_jalali_full
from app.bot.utils.persian import format_toman, to_persian_digits

logger = logging.getLogger(__name__)


async def notify_user(
    bot: Bot,
    user_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=reply_markup)
        return True
    except Exception as e:
        logger.warning(f"Failed to notify user {user_id}: {e}")
        return False


def _approve_reject_keyboard(approve_cb: str, reject_cb: str, *, wallet: bool) -> InlineKeyboardMarkup:
    text_btn = fa.ADMIN_APPROVE_WALLET_BTN if wallet else fa.ADMIN_APPROVE_BTN
    return (
        K()
        .success(text_btn, callback_data=approve_cb, icon="confirm")
        .danger(fa.ADMIN_REJECT_BTN, callback_data=reject_cb, icon="reject")
        .adjust(2)
        .as_markup()
    )


async def _notify_admin_chats(
    bot: Bot,
    admin_chat_ids: list[int],
    send_fn: Callable[[Bot, int], Awaitable[Message | None]],
) -> list[tuple[int, Message]]:
    seen: set[int] = set()
    sent: list[tuple[int, Message]] = []
    for chat_id in admin_chat_ids:
        if not chat_id or chat_id in seen:
            continue
        seen.add(chat_id)
        try:
            msg = await send_fn(bot, chat_id)
            if msg:
                sent.append((chat_id, msg))
        except Exception as e:
            logger.error("Failed to notify admin chat %s: %s", chat_id, e)
    return sent


async def forward_purchase_to_admin(
    bot: Bot,
    *,
    admin_chat_id: int,
    tx_id: int,
    user_name: str,
    username: str | None,
    tg_id: int,
    plan_name: str,
    quantity: int,
    service_name: str,
    amount: int,
    discount_code: str | None,
    discount_amount: int,
    receipt_photo: str | None,
) -> Message | None:
    dt = datetime.now(tz=timezone.utc)
    discount_text = "—"
    if discount_code:
        discount_text = f"{discount_code} (-{format_toman(discount_amount)} ت)"

    text = fa.ADMIN_PAYMENT_FWD.format(
        tx_id=tx_id,
        name=user_name,
        username=username or "—",
        tg_id=tg_id,
        plan_name=plan_name,
        quantity=to_persian_digits(quantity),
        service_name=service_name,
        amount=format_toman(amount),
        discount=discount_text,
        datetime=to_jalali_full(dt),
    )
    markup = _approve_reject_keyboard(
        approve_cb=f"admin:approve_purchase:{tx_id}",
        reject_cb=f"admin:reject_purchase:{tx_id}",
        wallet=False,
    )
    try:
        if receipt_photo:
            return await bot.send_photo(
                admin_chat_id,
                photo=receipt_photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        return await bot.send_message(
            admin_chat_id,
            text,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except Exception as e:
        logger.error(f"Failed to forward purchase to admin {admin_chat_id}: {e}")
        return None


async def forward_purchase_to_all_admins(
    bot: Bot,
    *,
    admin_chat_ids: list[int],
    **kwargs: Any,
) -> list[tuple[int, Message]]:
    async def _send(b: Bot, chat_id: int) -> Message | None:
        return await forward_purchase_to_admin(b, admin_chat_id=chat_id, **kwargs)

    return await _notify_admin_chats(bot, admin_chat_ids, _send)


async def forward_wallet_topup_to_admin(
    bot: Bot,
    *,
    admin_chat_id: int,
    tx_id: int,
    user_name: str,
    username: str | None,
    tg_id: int,
    amount: int,
    receipt_photo: str | None,
) -> Message | None:
    dt = datetime.now(tz=timezone.utc)
    text = fa.ADMIN_WALLET_FWD.format(
        tx_id=tx_id,
        name=user_name,
        username=username or "—",
        tg_id=tg_id,
        amount=format_toman(amount),
        datetime=to_jalali_full(dt),
    )
    markup = _approve_reject_keyboard(
        approve_cb=f"admin:approve_wallet:{tx_id}",
        reject_cb=f"admin:reject_wallet:{tx_id}",
        wallet=True,
    )
    try:
        if receipt_photo:
            return await bot.send_photo(
                admin_chat_id,
                photo=receipt_photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        return await bot.send_message(
            admin_chat_id,
            text,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except Exception as e:
        logger.error(f"Failed to forward wallet topup to admin {admin_chat_id}: {e}")
        return None


async def forward_wallet_topup_to_all_admins(
    bot: Bot,
    *,
    admin_chat_ids: list[int],
    **kwargs: Any,
) -> list[tuple[int, Message]]:
    async def _send(b: Bot, chat_id: int) -> Message | None:
        return await forward_wallet_topup_to_admin(b, admin_chat_id=chat_id, **kwargs)

    return await _notify_admin_chats(bot, admin_chat_ids, _send)
