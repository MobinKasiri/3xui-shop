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
from app.bot.utils.messaging import answer_message, edit_or_answer_callback
from app.db.models import User

logger = logging.getLogger(__name__)

router = Router(name="main_menu")


def main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """The main inline keyboard. Shows admin button only for admins."""
    kb = (
        K()
        .btn(fa.MAIN_BTN_BUY, callback_data="menu:buy", icon="btn_buy")
        .btn(fa.MAIN_BTN_CONFIGS, callback_data="menu:configs", icon="btn_configs")
        .btn(fa.MAIN_BTN_BALANCE, callback_data="menu:balance", icon="btn_balance")
        .btn(fa.MAIN_BTN_ACCOUNT, callback_data="menu:account", icon="btn_account")
        .btn(fa.MAIN_BTN_FREE, callback_data="menu:free", icon="btn_free")
        .btn(fa.MAIN_BTN_APPS, callback_data="menu:apps", icon="btn_apps")
        .btn(fa.MAIN_BTN_SUPPORT, callback_data="menu:support", icon="btn_support")
    )
    if is_admin:
        kb.danger(fa.MAIN_BTN_ADMIN, callback_data="menu:admin", icon="btn_admin")
        return kb.adjust(2, 2, 2, 1, 1).as_markup()
    return kb.adjust(2, 2, 2, 1).as_markup()


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

    markup = main_menu_keyboard(_is_admin(user, config))

    if isinstance(target, Message):
        if is_new_user and config:
            try:
                from app.bot.services.referral_reward import handle_start_referral

                await handle_start_referral(
                    session,
                    user,
                    target.text,
                    is_new_user=is_new_user,
                    config=config,
                    bot=target.bot,
                )
                user = await User.get(session, user.tg_id) or user
            except Exception:
                logger.exception("Referral handling failed on /start for user %s", user.tg_id)

        try:
            from app.bot.services.festival_promo import handle_start_festival

            await handle_start_festival(
                session,
                user,
                target.bot,
                is_new_user=is_new_user,
                config=config,
            )
        except Exception:
            logger.exception("Festival promo failed on /start for user %s", user.tg_id)

        await answer_message(target, fa.WELCOME, reply_markup=markup)
        return

    await edit_or_answer_callback(target, fa.WELCOME, reply_markup=markup)


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
    await edit_or_answer_callback(callback, fa.WELCOME, reply_markup=markup)
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
