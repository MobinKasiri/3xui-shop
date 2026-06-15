from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.vpn import VPNService
from app.bot.services.wallet import deduct
from app.bot.utils.jalali import to_jalali, days_until
from app.bot.utils.keyboards import back_to_menu_keyboard
from app.bot.utils.persian import format_toman, to_persian_digits
from app.bot.utils.progress import format_gb
from app.db.models import User, VPNConfig
from app.db.models.transaction import Transaction, TX_RENEWAL, TX_CONFIRMED, TX_PENDING

logger = logging.getLogger(__name__)
router = Router(name="renewal")


def _renewal_plan_keyboard(config_id: int, plans: dict, current_balance: int) -> object:
    builder = InlineKeyboardBuilder()
    for key, plan in plans.items():
        label = f"{plan['emoji']} {plan['name']} — {format_toman(plan['price'])} تومان"
        builder.button(text=label, callback_data=f"renewal:pay:{config_id}:{key}")
    builder.button(text=fa.BACK, callback_data="my_services:list")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "renewal:start")
async def cb_renewal_start(callback: CallbackQuery, user: User, session: AsyncSession, **kwargs) -> None:
    configs = await VPNConfig.get_for_user(session, user.tg_id)
    active = [c for c in configs if c.is_active]
    if not active:
        await callback.message.edit_text(fa.ERRORS["no_services"], reply_markup=back_to_menu_keyboard())
        await callback.answer()
        return

    config_obj = kwargs.get("config")
    plans = config_obj.pricing.PLANS if config_obj else {}
    builder = InlineKeyboardBuilder()
    for i, c in enumerate(active, 1):
        plan = plans.get(c.plan_key, {})
        label = plan.get("name", c.plan_key or f"سرویس {to_persian_digits(i)}")
        if c.expiry_date:
            expiry_str = to_jalali(c.expiry_date)
        elif plan.get("duration_days"):
            expiry_str = fa.DELAYED_START_FMT.format(
                n=to_persian_digits(plan["duration_days"])
            )
        else:
            expiry_str = "—"
        builder.button(
            text=f"{to_persian_digits(i)}) {label} — انقضا: {expiry_str}",
            callback_data=f"renewal:config:{c.id}",
        )
    builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
    builder.adjust(1)
    await callback.message.edit_text(fa.RENEWAL_SELECT_CONFIG, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("renewal:config:"))
async def cb_renewal_config(callback: CallbackQuery, user: User, session: AsyncSession, **kwargs) -> None:
    config_id = int(callback.data.split(":")[-1])
    config = await VPNConfig.get(session, config_id)
    if not config or config.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return

    config_obj = kwargs.get("config")
    plans = config_obj.pricing.PLANS if config_obj else {}
    plan = plans.get(config.plan_key, {})
    plan_name = plan.get("name", config.plan_key or "سرویس")
    remaining_bytes = config.traffic_remaining_bytes
    total_gb = config.traffic_limit_gb
    expiry_str = (
        to_jalali(config.expiry_date)
        if config.expiry_date
        else fa.DELAYED_START_FMT.format(n=to_persian_digits(plan.get("duration_days", 30)))
        if plan
        else "—"
    )

    text = fa.RENEWAL_SELECT_PLAN.format(
        plan_name=plan_name,
        remaining=remaining_bytes / (1024 ** 3),
        total=total_gb,
        expiry_jalali=expiry_str,
    )
    await callback.message.edit_text(text, reply_markup=_renewal_plan_keyboard(config_id, plans, user.balance))
    await callback.answer()


@router.callback_query(F.data.startswith("renewal:pay:"))
async def cb_renewal_pay(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    # renewal:pay:{config_id}:{plan_key}
    parts = callback.data.split(":")
    config_id = int(parts[2])
    plan_key = parts[3]

    config = await VPNConfig.get(session, config_id)
    if not config or config.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return

    config_obj = kwargs.get("config")
    plans = config_obj.pricing.PLANS if config_obj else {}
    plan = plans.get(plan_key)
    if not plan:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return

    vpn_service: VPNService | None = kwargs.get("vpn_service")

    # Compute preview
    remaining_gb = config.traffic_remaining_bytes / (1024 ** 3)
    new_total_gb = remaining_gb + plan["traffic_gb"]
    from app.bot.utils.jalali import extend_expiry_ms, is_delayed_start, ms_to_datetime

    panel_expiry_ms = 0
    xui = kwargs.get("xui_service")
    if xui:
        try:
            panel_expiry_ms = (await xui.get_client_traffic(config.panel_email)).expiry_time
        except Exception:
            pass

    if panel_expiry_ms < 0:
        current_ms = panel_expiry_ms
    elif panel_expiry_ms > 0:
        current_ms = panel_expiry_ms
    elif config.expiry_date:
        current_ms = int(config.expiry_date.timestamp() * 1000)
    else:
        current_ms = 0

    delayed = is_delayed_start(current_ms) or (
        vpn_service and vpn_service.start_after_first_use and current_ms == 0
    )
    new_expiry_ms = extend_expiry_ms(
        current_ms, plan["duration_days"], delayed_start=delayed
    )
    if is_delayed_start(new_expiry_ms):
        new_expiry_jalali = fa.DELAYED_START_FMT.format(
            n=to_persian_digits(abs(new_expiry_ms) // 86_400_000)
        )
    else:
        new_expiry_dt = ms_to_datetime(new_expiry_ms)
        new_expiry_jalali = to_jalali(new_expiry_dt) if new_expiry_dt else "—"

    text = fa.RENEWAL_SUMMARY.format(
        plan_name=plan["name"],
        price=format_toman(plan["price"]),
        new_total=new_total_gb,
        new_expiry_jalali=new_expiry_jalali,
    )

    builder = InlineKeyboardBuilder()
    builder.button(text=fa.CONFIRM, callback_data=f"renewal:confirm:{config_id}:{plan_key}")
    builder.button(text=fa.CANCEL, callback_data=f"renewal:config:{config_id}")
    builder.adjust(2)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("renewal:confirm:"))
async def cb_renewal_confirm(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    parts = callback.data.split(":")
    config_id = int(parts[2])
    plan_key = parts[3]

    config = await VPNConfig.get(session, config_id)
    if not config or config.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return

    config_obj = kwargs.get("config")
    plans = config_obj.pricing.PLANS if config_obj else {}
    plan = plans.get(plan_key)
    if not plan:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return

    vpn_service: VPNService | None = kwargs.get("vpn_service")
    if vpn_service is None:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return

    price = plan["price"]
    if user.balance < price:
        await callback.answer(
            fa.ERRORS["insufficient_balance"].format(
                balance=format_toman(user.balance),
                required=format_toman(price),
            ),
            show_alert=True,
        )
        return

    await callback.message.edit_text("⏳ در حال تمدید سرویس...")
    await callback.answer()

    try:
        await deduct(session, user, price, f"تمدید {plan['name']}", tx_type=TX_RENEWAL, plan_key=plan_key, config_id=config_id)
        updated = await vpn_service.renew_config(session, config, plan["traffic_gb"] * 1024, plan["duration_days"])

        expiry_jalali = (
            to_jalali(updated.expiry_date)
            if updated.expiry_date
            else fa.DELAYED_START_FMT.format(n=to_persian_digits(plan["duration_days"]))
        )
        await callback.message.edit_text(
            fa.RENEWAL_SUCCESS.format(
                traffic_gb=plan["traffic_gb"],
                expiry_jalali=expiry_jalali,
            ),
            reply_markup=back_to_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Renewal failed for config {config_id}: {e}")
        await callback.message.edit_text(fa.ERRORS["general"], reply_markup=back_to_menu_keyboard())
