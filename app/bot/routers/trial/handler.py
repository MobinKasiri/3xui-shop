from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.bootstrap import ensure_vpn_service
from app.bot.services.vpn import VPNService
from app.bot.utils.keyboards import back_to_menu_keyboard
from app.db.models import User

logger = logging.getLogger(__name__)
router = Router(name="trial")


def _trial_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.TRIAL_CONFIRM_BTN, callback_data="trial:confirm")
    builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "trial:start")
async def cb_trial_start(callback: CallbackQuery, user: User, **kwargs) -> None:
    if user.is_trial_used:
        builder = InlineKeyboardBuilder()
        builder.button(text=fa.TRIAL_ALREADY_USED_BUY_BTN, callback_data="purchase:start")
        builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            fa.TRIAL_ALREADY_USED, reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        fa.TRIAL_CONFIRM, reply_markup=_trial_confirm_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "trial:confirm")
async def cb_trial_confirm(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    if user.is_trial_used:
        await callback.answer(fa.ERRORS["trial_used"], show_alert=True)
        return

    config = kwargs.get("config")
    vpn_service: VPNService | None = kwargs.get("vpn_service")
    if vpn_service is None and config:
        vpn_service = await ensure_vpn_service(config)

    if vpn_service is None:
        await callback.message.edit_text(fa.ERRORS["api_error"], reply_markup=back_to_menu_keyboard())
        await callback.answer()
        return

    await callback.message.edit_text(fa.TRIAL_CREATING)
    await callback.answer()

    free_mb = config.pricing.FREE_TRIAL_MB if config else 100
    free_days = config.pricing.FREE_TRIAL_DAYS if config else 1

    try:
        result = await vpn_service.create_config(
            session=session,
            user_id=user.tg_id,
            plan_key="trial",
            traffic_mb=free_mb,
            duration_days=free_days,
            tg_id=user.tg_id,
            is_trial=True,
        )
        await User.update(session, user.tg_id, is_trial_used=True)

        builder = InlineKeyboardBuilder()
        builder.button(text=fa.MAIN_MENU_BUTTONS["guide"], callback_data="guide:connect")
        builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
        builder.adjust(1)

        await callback.message.edit_text(
            fa.TRIAL_SUCCESS.format(sub_url=result.subscription_url),
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.error(f"Trial creation failed for user {user.tg_id}: {e}")
        await callback.message.edit_text(fa.TRIAL_FAILED, reply_markup=back_to_menu_keyboard())
