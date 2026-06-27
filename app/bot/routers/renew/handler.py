"""Renew existing VPN config — add traffic and refresh duration with panel discount."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.renewal_settings import renewal_settings_for_config
from app.bot.services.tx_admin_notify import (
    actor_from_callback,
    dispatch_tx_to_admins,
    refresh_processed_views_if_done,
    sync_processed_views,
)
from app.bot.services.vpn import VPNService
from app.bot.services.wallet import deduct
from app.bot.services.xui_api import XUIError
from app.bot.utils.jalali import to_jalali, to_jalali_full
from app.bot.utils.keyboards import K
from app.bot.utils.payment_keyboard import card_payment_keyboard
from app.bot.utils.persian import format_toman, to_persian_digits
from app.bot.utils.plans_display import render_plans_table
from app.bot.utils.receipt_storage import persist_receipt_photo, receipt_file_id
from app.bot.utils.renewal_pricing import SERVICE_MAX_DAYS, renewal_quote
from app.bot.utils.emoji import strip_html_emoji
from app.db.models import User, VPNConfig
from app.db.models.transaction import (
    PAY_CARD,
    TX_PENDING,
    TX_RENEW,
    Transaction,
)

logger = logging.getLogger(__name__)

router = Router(name="renew")


class RenewStates(StatesGroup):
    plan = State()
    payment_method = State()
    awaiting_receipt = State()


def _renew_discount_pct(config_obj) -> int:
    return renewal_settings_for_config(config_obj).discount_percent


def _renew_plan_label(plan: dict, discount_pct: int) -> str:
    quote = renewal_quote(int(plan["price"]), discount_pct)
    emoji = strip_html_emoji(str(plan.get("emoji", "")))
    lead = f"{emoji} " if emoji else ""
    return fa.RENEW_PLAN_BTN.format(
        lead=lead,
        gb=to_persian_digits(plan["gb"]),
        price=format_toman(quote.final_amount),
        was_price=format_toman(quote.base_amount),
    )


def notif_action_keyboard(config_id: int, *, discount_pct: int) -> InlineKeyboardMarkup:
    """Expiry/traffic warnings: renew (discounted) or buy new."""
    renew_label = fa.NOTIF_RENEW_BTN.format(
        discount_pct=to_persian_digits(discount_pct),
    )
    return (
        K()
        .success(renew_label, callback_data=f"renew:start:{config_id}", icon="btn_buy")
        .btn(fa.NOTIF_NEW_CONFIG_BTN, callback_data="menu:buy")
        .adjust(1)
        .as_markup()
    )


def _plans_keyboard(plans: list[dict], config_id: int, discount_pct: int) -> InlineKeyboardMarkup:
    kb = K()
    for plan in plans:
        label = _renew_plan_label(plan, discount_pct)
        cb = f"renew:plan:{plan['id']}"
        if plan.get("recommended"):
            kb.primary(label, callback_data=cb)
        else:
            kb.btn(label, callback_data=cb)
    return kb.nav(f"cfg:open:{config_id}").adjust(*([1] * len(plans)), 2).as_markup()


def _method_keyboard(balance: int, required: int, config_id: int) -> InlineKeyboardMarkup:
    wallet_label = fa.PAY_WALLET_BTN.format(balance=format_toman(balance))
    return (
        K()
        .success(wallet_label, callback_data="renew:pay:wallet", icon="cash")
        .btn(fa.PAY_CARD_BTN, callback_data="renew:pay:card", icon="card")
        .nav(f"renew:back_plans:{config_id}")
        .adjust(1, 1, 2)
        .as_markup()
    )


async def _load_config(
    session: AsyncSession, user: User, config_id: int
) -> VPNConfig | None:
    cfg = await VPNConfig.get(session, config_id)
    if not cfg or cfg.user_id != user.tg_id:
        return None
    return cfg


async def _verify_panel_client(vpn: VPNService, cfg: VPNConfig) -> bool:
    try:
        return await vpn.xui.client_exists(cfg.panel_email)
    except XUIError:
        return False


async def start_renew_flow(
    target: CallbackQuery | Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    config_id: int,
    **kwargs,
) -> None:
    config_obj = kwargs.get("config")
    vpn: VPNService | None = kwargs.get("vpn_service")
    cfg = await _load_config(session, user, config_id)
    if not cfg:
        if isinstance(target, CallbackQuery):
            await target.answer(fa.ERRORS["config_not_found"], show_alert=True)
        else:
            await target.answer(fa.ERRORS["config_not_found"])
        return
    if vpn is None:
        if isinstance(target, CallbackQuery):
            await target.answer(fa.ERRORS["vpn_unavailable"], show_alert=True)
        else:
            await target.answer(fa.ERRORS["vpn_unavailable"])
        return
    if not await _verify_panel_client(vpn, cfg):
        if isinstance(target, CallbackQuery):
            await target.answer(fa.ERRORS["config_not_found"], show_alert=True)
        else:
            await target.answer(fa.ERRORS["config_not_found"])
        return

    if not config_obj:
        if isinstance(target, CallbackQuery):
            await target.answer(fa.ERRORS["general"], show_alert=True)
        return

    plans = config_obj.pricing.list_plans("vip")
    tier = config_obj.pricing.get_tier("vip")
    if not plans:
        if isinstance(target, CallbackQuery):
            await target.answer(fa.ERRORS["general"], show_alert=True)
        return

    await state.clear()
    await state.set_state(RenewStates.plan)
    discount_pct = _renew_discount_pct(config_obj)
    await state.update_data(config_id=config_id, service_name=cfg.service_name, discount_pct=discount_pct)

    header = fa.RENEW_PLANS_HEADER.format(
        name=cfg.service_name,
        discount_pct=to_persian_digits(discount_pct),
        max_days=to_persian_digits(SERVICE_MAX_DAYS),
    )
    text = f"{header}\n\n{_render_plans_text(tier, plans)}"
    markup = _plans_keyboard(plans, config_id, discount_pct)

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup)


def _render_plans_text(tier: dict, plans: list[dict]) -> str:
    return render_plans_table(tier, plans)


@router.callback_query(F.data.startswith("renew:start:"))
async def cb_renew_start(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    config_id = int(callback.data.rsplit(":", 1)[-1])
    await start_renew_flow(callback, state, user, session, config_id, **kwargs)


@router.callback_query(F.data.startswith("renew:back_plans:"))
async def cb_renew_back_plans(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    config_id = int(callback.data.rsplit(":", 1)[-1])
    await start_renew_flow(callback, state, user, session, config_id, **kwargs)


@router.callback_query(RenewStates.plan, F.data.startswith("renew:plan:"))
async def cb_renew_select_plan(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    if not config:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return

    data = await state.get_data()
    config_id = int(data.get("config_id", 0))
    cfg = await _load_config(session, user, config_id)
    if not cfg:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        await state.clear()
        return

    plan_id = callback.data.split(":", 2)[-1]
    plan = config.pricing.get_plan(plan_id)
    if not plan:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return

    discount_pct = int(data.get("discount_pct") or _renew_discount_pct(config))
    quote = renewal_quote(int(plan["price"]), discount_pct)
    await state.update_data(
        plan_id=plan_id,
        plan=plan,
        base_amount=quote.base_amount,
        renewal_discount=quote.renewal_discount,
        final_amount=quote.final_amount,
        discount_pct=discount_pct,
    )
    await state.set_state(RenewStates.payment_method)

    text = fa.RENEW_PAYMENT_HEADER.format(
        name=cfg.service_name,
        gb=to_persian_digits(plan["gb"]),
        max_days=to_persian_digits(SERVICE_MAX_DAYS),
        discount_pct=to_persian_digits(discount_pct),
        discount=format_toman(quote.renewal_discount),
        amount=format_toman(quote.final_amount),
    )
    await callback.message.edit_text(
        text,
        reply_markup=_method_keyboard(user.balance, quote.final_amount, config_id),
    )
    await callback.answer()


@router.callback_query(RenewStates.payment_method, F.data == "renew:pay:wallet")
async def cb_renew_pay_wallet(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    data = await state.get_data()
    plan = data.get("plan") or {}
    final_amount = int(data.get("final_amount", 0))
    config_id = int(data.get("config_id", 0))
    cfg = await _load_config(session, user, config_id)
    if not cfg:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        await state.clear()
        return

    if user.balance < final_amount:
        await callback.answer(
            fa.ERRORS["insufficient_balance_alert"].format(
                balance=format_toman(user.balance),
                required=format_toman(final_amount),
                shortage=format_toman(final_amount - user.balance),
            ),
            show_alert=True,
        )
        return

    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await callback.answer(fa.ERRORS["vpn_unavailable"], show_alert=True)
        return

    await callback.message.edit_text(fa.RENEW_WAIT)
    await callback.answer()

    try:
        cfg = await vpn.renew_one(
            session,
            cfg,
            plan_id=plan.get("id", ""),
            plan_gb=int(plan.get("gb", 0)),
            plan_days=int(plan.get("days", 0)),
        )
    except XUIError:
        logger.exception("Renew wallet: panel extend failed config=%s", config_id)
        await callback.message.edit_text(fa.ERRORS["config_create_failed"])
        await state.clear()
        return
    except Exception:
        logger.exception("Renew wallet: unexpected failure config=%s", config_id)
        await callback.message.edit_text(fa.ERRORS["general"])
        await state.clear()
        return

    tx_desc = fa.TX_DESC_RENEW.format(
        plan_name=plan.get("tier_name", "VIP"),
        name=cfg.service_name,
    )
    discount_pct = int(data.get("discount_pct") or 0)
    try:
        await deduct(
            session,
            user,
            final_amount,
            tx_desc,
            tx_type=TX_RENEW,
            plan_id=plan.get("id"),
            config_id=cfg.id,
            service_name=cfg.service_name,
            quantity=1,
            discount_code=f"renew-{discount_pct}pct",
            discount_amount=int(data.get("renewal_discount", 0)),
        )
    except ValueError:
        logger.error(
            "Renew succeeded on panel but wallet deduct failed user=%s config=%s",
            user.tg_id,
            config_id,
        )
        await callback.message.edit_text(fa.ERRORS["general"])
        await state.clear()
        return

    await _send_renew_success(callback.message, cfg, plan, vpn)
    await state.clear()


@router.callback_query(RenewStates.payment_method, F.data == "renew:pay:card")
async def cb_renew_pay_card(
    callback: CallbackQuery,
    state: FSMContext,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    data = await state.get_data()
    final_amount = int(data.get("final_amount", 0))
    await state.update_data(payment_amount=final_amount, payment_method=PAY_CARD)
    await state.set_state(RenewStates.awaiting_receipt)

    text = fa.CARD_PAYMENT.format(
        bank=config.payment.CARD_BANK if config else "—",
        owner=config.payment.CARD_OWNER if config else "—",
        card=config.payment.CARD_NUMBER if config else "—",
        amount=format_toman(final_amount),
    )
    await callback.message.edit_text(
        text,
        reply_markup=card_payment_keyboard(
            toman=final_amount,
            card=config.payment.CARD_NUMBER if config else "",
        ),
    )
    await callback.answer()


@router.message(RenewStates.awaiting_receipt, F.photo | F.document)
async def msg_renew_receipt(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    await _create_pending_renew_tx(message, state, user, session, **kwargs)


@router.message(RenewStates.awaiting_receipt)
async def msg_renew_receipt_other(message: Message, **kwargs) -> None:
    await message.answer(fa.RECEIPT_PROMPT)


async def _create_pending_renew_tx(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    data = await state.get_data()
    plan = data.get("plan") or {}
    final_amount = int(data.get("final_amount", 0))
    payment_amount = int(data.get("payment_amount", final_amount))
    config_id = int(data.get("config_id", 0))
    service_name = data.get("service_name") or "—"

    tx_desc = fa.TX_DESC_RENEW.format(
        plan_name=plan.get("tier_name", "VIP"),
        name=service_name,
    )
    receipt_photo = receipt_file_id(message)
    discount_pct = int(data.get("discount_pct") or 0)

    tx = await Transaction.create(
        session,
        user_id=user.tg_id,
        amount=final_amount,
        payment_amount=payment_amount,
        type=TX_RENEW,
        description=tx_desc,
        plan_id=plan.get("id"),
        config_id=config_id,
        quantity=1,
        service_name=service_name,
        payment_method=PAY_CARD,
        payment_receipt=receipt_photo,
        discount_code=f"renew-{discount_pct}pct",
        discount_amount=int(data.get("renewal_discount", 0)),
        status=TX_PENDING,
    )

    if config:
        dt = datetime.now(tz=timezone.utc)
        await dispatch_tx_to_admins(
            message.bot,
            session,
            config,
            kind="renew",
            tx_id=tx.id,
            receipt_photo=receipt_photo,
            payload={
                "user_name": user.full_name,
                "username": user.username,
                "tg_id": user.tg_id,
                "plan_name": plan.get("tier_name", "VIP"),
                "service_name": service_name,
                "amount": payment_amount,
                "discount": f"{discount_pct}% (-{format_toman(int(data.get('renewal_discount', 0)))} ت)",
                "datetime": to_jalali_full(dt),
            },
        )

    admin_payload = json.dumps(
        {
            "config_id": config_id,
            "plan_id": plan.get("id"),
            "plan_gb": plan.get("gb"),
            "plan_days": plan.get("days"),
        },
        ensure_ascii=False,
    )
    await Transaction.update(session, tx.id, admin_note=admin_payload)

    receipt_ref = await persist_receipt_photo(message, tx.id)
    if receipt_ref:
        await Transaction.update(session, tx.id, payment_receipt=receipt_ref)

    await message.answer(fa.RECEIPT_RECEIVED)
    await state.clear()


async def _send_renew_success(
    message: Message,
    cfg: VPNConfig,
    plan: dict,
    vpn: VPNService | None,
) -> None:
    expiry = fa.CONFIG_NOT_STARTED
    if cfg.expiry_date:
        expiry = to_jalali(cfg.expiry_date)
    sub_url = vpn.sub_url(cfg.subscription_id) if vpn else cfg.subscription_url
    text = fa.RENEW_SUCCESS.format(
        name=cfg.service_name,
        gb=to_persian_digits(plan.get("gb", 0)),
        max_days=to_persian_digits(SERVICE_MAX_DAYS),
        expiry=expiry,
        sub_url=sub_url,
    )
    markup = (
        K()
        .btn(fa.MAIN_BTN_CONFIGS, callback_data="menu:configs", icon="btn_configs")
        .home()
        .adjust(1)
        .as_markup()
    )
    await message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=markup,
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("admin:approve_renew:"))
async def cb_admin_approve_renew(
    callback: CallbackQuery,
    session: AsyncSession,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    admin_ids = config.bot.ADMINS if config else []
    if callback.from_user.id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return

    tx_id = int(callback.data.rsplit(":", 1)[-1])
    tx = await Transaction.get(session, tx_id)
    if not tx or tx.status != TX_PENDING:
        if tx:
            await refresh_processed_views_if_done(callback.bot, session, config, tx_id)
        await callback.answer("✅ این تراکنش قبلاً پردازش شده است.", show_alert=True)
        return
    if tx.type != TX_RENEW:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return

    try:
        intent = json.loads(tx.admin_note or "{}")
    except json.JSONDecodeError:
        intent = {}

    plan = config.pricing.get_plan(intent.get("plan_id", "")) if config else None
    if not plan:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return

    config_id = int(intent.get("config_id") or tx.config_id or 0)
    cfg = await VPNConfig.get(session, config_id)
    if not cfg or cfg.user_id != tx.user_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return

    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return

    try:
        await callback.message.edit_text(fa.RENEW_WAIT)
    except Exception:
        pass
    await callback.answer()

    try:
        cfg = await vpn.renew_one(
            session,
            cfg,
            plan_id=plan["id"],
            plan_gb=int(plan["gb"]),
            plan_days=int(plan["days"]),
        )
    except XUIError:
        logger.exception("Admin renew approve failed tx=%s", tx_id)
        await callback.answer(fa.ERRORS["config_create_failed"], show_alert=True)
        return

    processed_at = datetime.utcnow()
    claimed = await Transaction.claim_if_pending(
        session,
        tx_id,
        status="confirmed",
        confirmed_at=processed_at,
        config_id=cfg.id,
    )
    if not claimed:
        await refresh_processed_views_if_done(callback.bot, session, config, tx_id)
        return

    await sync_processed_views(
        callback.bot,
        session,
        config,
        tx_id,
        actor=actor_from_callback(callback),
        action="approved",
        processed_at=processed_at.replace(tzinfo=timezone.utc),
    )

    try:
        await callback.bot.send_message(
            tx.user_id,
            fa.RENEW_SUCCESS.format(
                name=cfg.service_name,
                gb=to_persian_digits(plan.get("gb", 0)),
                max_days=to_persian_digits(SERVICE_MAX_DAYS),
                expiry=to_jalali(cfg.expiry_date) if cfg.expiry_date else fa.CONFIG_NOT_STARTED,
                sub_url=vpn.sub_url(cfg.subscription_id),
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        logger.exception("Failed to send renew success to user %s", tx.user_id)


@router.callback_query(F.data.startswith("admin:reject_renew:"))
async def cb_admin_reject_renew(
    callback: CallbackQuery,
    session: AsyncSession,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    admin_ids = config.bot.ADMINS if config else []
    if callback.from_user.id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return

    tx_id = int(callback.data.rsplit(":", 1)[-1])
    tx = await Transaction.get(session, tx_id)
    if not tx or tx.status != TX_PENDING:
        if tx:
            await refresh_processed_views_if_done(callback.bot, session, config, tx_id)
        await callback.answer("این تراکنش قبلاً پردازش شده.", show_alert=True)
        return
    if tx.type != TX_RENEW:
        return

    claimed = await Transaction.claim_if_pending(session, tx_id, status="rejected")
    if not claimed:
        await refresh_processed_views_if_done(callback.bot, session, config, tx_id)
        await callback.answer("این تراکنش قبلاً پردازش شده.", show_alert=True)
        return

    processed_at = datetime.now(tz=timezone.utc)
    await sync_processed_views(
        callback.bot,
        session,
        config,
        tx_id,
        actor=actor_from_callback(callback),
        action="rejected",
        processed_at=processed_at,
    )

    try:
        await callback.bot.send_message(
            tx.user_id,
            fa.RENEW_REJECTED.format(reason="رسید پرداخت تایید نشد."),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.answer("❌ رد شد.", show_alert=False)
