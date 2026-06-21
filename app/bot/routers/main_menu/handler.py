"""
Main menu (screenshot 1).

Single welcome message with one InlineKeyboardMarkup that routes to every
top-level flow. Also handles `/start ref_<code>` deep links.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from app.bot.utils.keyboards import K
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.db.models import Referral, User

logger = logging.getLogger(__name__)

router = Router(name="main_menu")


def main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """The main inline keyboard. Shows admin button only for admins."""
    kb = (
        K()
        .primary(fa.MAIN_BTN_BUY, callback_data="menu:buy")
        .btn(fa.MAIN_BTN_CONFIGS, callback_data="menu:configs")
        .primary(fa.MAIN_BTN_BALANCE, callback_data="menu:balance")
        .btn(fa.MAIN_BTN_ACCOUNT, callback_data="menu:account")
        .success(fa.MAIN_BTN_FREE, callback_data="menu:free")
        .btn(fa.MAIN_BTN_APPS, callback_data="menu:apps")
        .btn(fa.MAIN_BTN_SUPPORT, callback_data="menu:support")
    )
    if is_admin:
        kb.danger(fa.MAIN_BTN_ADMIN, callback_data="menu:admin")
        return kb.adjust(2, 2, 2, 1, 1).as_markup()
    return kb.adjust(2, 2, 2, 1).as_markup()


async def _record_referral(
    session: AsyncSession, user: User, code: str
) -> None:
    referrer = await User.get_by_referral_code(session, code)
    if not referrer or referrer.tg_id == user.tg_id:
        return
    existing = await Referral.get_by_referred(session, user.tg_id)
    if existing:
        return
    await User.update(session, user.tg_id, referred_by=referrer.tg_id)
    await Referral.create(
        session, referrer_id=referrer.tg_id, referred_id=user.tg_id
    )
    logger.info("New referral: %s -> %s", referrer.tg_id, user.tg_id)


async def _maybe_credit_friend_bonus(
    session: AsyncSession, user: User, bot, friend_bonus: int
) -> None:
    """Give the friend bonus to a newly-referred user (only once)."""
    if friend_bonus <= 0 or not user.referred_by:
        return
    ref = await Referral.get_by_referred(session, user.tg_id)
    if not ref or ref.friend_bonus_given:
        return
    from app.bot.services.wallet import credit
    from app.db.models.transaction import TX_REFERRAL

    try:
        await credit(
            session,
            user.tg_id,
            friend_bonus,
            fa.TX_DESC_REFERRAL_FRIEND,
            tx_type=TX_REFERRAL,
        )
        await Referral.mark_friend_bonus(session, ref.id)
    except Exception:
        logger.exception("Failed to credit friend bonus to %s", user.tg_id)


def _is_admin(user: User, config) -> bool:
    if config and hasattr(config, "bot") and config.bot.ADMINS:
        return user.tg_id in config.bot.ADMINS
    return False


async def send_welcome(
    target: Message | CallbackQuery,
    user: User,
    session: AsyncSession,
    *,
    is_new_user: bool = False,
    **kwargs,
) -> None:
    config = kwargs.get("config")

    if isinstance(target, Message):
        args = ""
        if target.text:
            parts = target.text.split(maxsplit=1)
            if len(parts) > 1:
                args = parts[1].strip()

        if is_new_user and args.startswith("ref_") and not user.referred_by:
            await _record_referral(session, user, args[4:])
            if config:
                await _maybe_credit_friend_bonus(
                    session,
                    user,
                    target.bot,
                    config.pricing.REFERRAL_FRIEND_BONUS_TOMAN,
                )
                user = await User.get(session, user.tg_id) or user

        await target.answer(
            fa.WELCOME, reply_markup=main_menu_keyboard(_is_admin(user, config))
        )
        return

    markup = main_menu_keyboard(_is_admin(user, config))
    try:
        await target.message.edit_text(fa.WELCOME, reply_markup=markup)
    except Exception:
        await target.message.answer(fa.WELCOME, reply_markup=markup)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    user: User,
    session: AsyncSession,
    is_new_user: bool = False,
    **kwargs,
) -> None:
    await send_welcome(message, user, session, is_new_user=is_new_user, **kwargs)


@router.message(Command("buy"))
async def cmd_buy(message: Message, state, **kwargs) -> None:
    from app.bot.routers.purchase.handler import show_type_screen

    await show_type_screen(message, state, **kwargs)


@router.message(Command("configs"))
async def cmd_configs(
    message: Message, user: User, session: AsyncSession, **kwargs
) -> None:
    from app.bot.routers.my_services.handler import show_configs_list

    await show_configs_list(message, user, session, **kwargs)


@router.message(Command("topup"))
async def cmd_topup(message: Message, state, **kwargs) -> None:
    from app.bot.routers.wallet.handler import show_topup_amounts

    await show_topup_amounts(message, state, **kwargs)


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, user: User, **kwargs) -> None:
    config = kwargs.get("config")
    markup = main_menu_keyboard(_is_admin(user, config))
    try:
        await callback.message.edit_text(fa.WELCOME, reply_markup=markup)
    except Exception:
        await callback.message.answer(fa.WELCOME, reply_markup=markup)
    await callback.answer()


# ── 7 top-level dispatch callbacks ───────────────────────────────────────────

@router.callback_query(F.data == "menu:buy")
async def cb_menu_buy(callback: CallbackQuery, state, **kwargs) -> None:
    from app.bot.routers.purchase.handler import show_type_screen

    await show_type_screen(callback, state, **kwargs)


@router.callback_query(F.data == "menu:configs")
async def cb_menu_configs(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    from app.bot.routers.my_services.handler import show_configs_list

    await show_configs_list(callback, user, session, **kwargs)


@router.callback_query(F.data == "menu:balance")
async def cb_menu_balance(callback: CallbackQuery, state, **kwargs) -> None:
    from app.bot.routers.wallet.handler import show_topup_amounts

    await show_topup_amounts(callback, state, **kwargs)


@router.callback_query(F.data == "menu:account")
async def cb_menu_account(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    from app.bot.routers.wallet.handler import show_profile

    await show_profile(callback, user, session, **kwargs)


@router.callback_query(F.data == "menu:free")
async def cb_menu_free(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    from app.bot.routers.referral.handler import show_referral_landing

    await show_referral_landing(callback, user, session, **kwargs)


@router.callback_query(F.data == "menu:apps")
async def cb_menu_apps(callback: CallbackQuery, **kwargs) -> None:
    from app.bot.routers.apps.handler import show_apps_menu

    await show_apps_menu(callback, **kwargs)


@router.callback_query(F.data == "menu:support")
async def cb_menu_support(callback: CallbackQuery, **kwargs) -> None:
    from app.bot.routers.support.handler import show_support_menu

    await show_support_menu(callback, **kwargs)


@router.callback_query(F.data == "menu:admin")
async def cb_menu_admin(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    if not _is_admin(user, config):
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return
    from app.bot.routers.admin.handler import _admin_keyboard, _dashboard_text

    try:
        text = await _dashboard_text(session, kwargs.get("xui_service"))
    except Exception:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return
    try:
        await callback.message.edit_text(text, reply_markup=_admin_keyboard())
    except Exception:
        await callback.message.answer(text, reply_markup=_admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery, **kwargs) -> None:
    """Used as a do-nothing callback for inline buttons that are pure labels."""
    await callback.answer()
