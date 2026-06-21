"""
Purchase FSM (screenshots 2–8).

Flow:
    type  -> plan  -> quantity  -> service_name  -> discount?  -> payment method
    wallet path => deduct + create configs immediately
    card path   => upload receipt -> admin approves -> create configs
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.notifications import forward_purchase_to_admin
from app.bot.services.wallet import deduct
from app.bot.utils.discount import record_usage, validate_and_apply
from app.bot.utils.payment_keyboard import card_payment_keyboard
from app.bot.utils.persian import format_toman, to_persian_digits
from app.bot.utils.service_name import (
    is_taken,
    numbered_name,
    random_name,
    validate as validate_service_name,
)
from app.db.models import User
from app.db.models.transaction import (
    PAY_CARD,
    TX_PENDING,
    TX_PURCHASE,
    Transaction,
)

logger = logging.getLogger(__name__)

router = Router(name="purchase")


class PurchaseStates(StatesGroup):
    plan = State()
    quantity = State()
    service_name = State()
    discount = State()
    payment_method = State()
    awaiting_receipt = State()


# ── helpers ──────────────────────────────────────────────────────────────────

def _purchase_quantity(data: dict) -> int:
    return max(1, int(data.get("quantity", 1)))


def _unit_price(data: dict) -> int:
    plan = data.get("plan") or {}
    return int(plan.get("price", 0))


def _compute_base_amount(data: dict) -> int:
    return _unit_price(data) * _purchase_quantity(data)


def _resolve_final_amount(data: dict) -> int:
    """Total payable — ignore stale final_amount unless a discount is active."""
    base = int(data.get("base_amount", 0)) or _compute_base_amount(data)
    if data.get("discount_code") and int(data.get("discount_amount", 0)) > 0:
        return int(data.get("final_amount", base))
    return base


async def _commit_pricing(
    state: FSMContext,
    *,
    service_names: list[str] | None = None,
    base_amount: int | None = None,
    data: dict | None = None,
) -> int:
    """Store service names and reset discount when quantity/price changes."""
    payload: dict[str, Any] = {
        "base_amount": base_amount if base_amount is not None else _compute_base_amount(data or {}),
        "final_amount": base_amount if base_amount is not None else _compute_base_amount(data or {}),
        "discount_code": None,
        "discount_id": None,
        "discount_amount": 0,
    }
    if service_names is not None:
        payload["service_names"] = service_names
    await state.update_data(**payload)
    return int(payload["base_amount"])


def _back_home_row() -> tuple[str, str]:
    return fa.BACK, fa.HOME


def _format_plan_label(plan: dict) -> str:
    emoji = plan.get("emoji", "")
    recommended = plan.get("recommended")
    if recommended:
        lead = "⭐ "
        badge = " · (پیشنهادی)"
    elif emoji:
        lead = f"{emoji} "
        badge = ""
    else:
        lead = ""
        badge = ""
    return fa.VIP_PLAN_BTN.format(
        lead=lead,
        gb=to_persian_digits(plan["gb"]),
        price=format_toman(plan["price"]),
        badge=badge,
    )


def _type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.BUY_VIP_BTN, callback_data="buy:type:vip")
    builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def _plans_keyboard(plans: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        builder.button(text=_format_plan_label(plan), callback_data=f"buy:plan:{plan['id']}")
    builder.button(text=fa.BACK, callback_data="buy:type")
    builder.button(text=fa.HOME, callback_data="main_menu")
    # One plan per row; back + home share the last row
    builder.adjust(*([1] * len(plans)), 2)
    return builder.as_markup()


def _quantity_back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.BACK, callback_data="buy:type:vip")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()


def _service_name_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.SERVICE_NAME_RANDOM_BTN, callback_data="buy:name:random")
    builder.button(text=fa.BACK, callback_data="buy:back_to_qty")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(1, 2)
    return builder.as_markup()


def _discount_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.DISCOUNT_SKIP_BTN, callback_data="buy:discount:skip")
    builder.button(text=fa.BACK, callback_data="buy:back_to_name")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(1, 2)
    return builder.as_markup()


def _method_keyboard(balance: int, required: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    wallet_label = fa.PAY_WALLET_BTN.format(balance=format_toman(balance))
    builder.button(text=wallet_label, callback_data="buy:pay:wallet")
    builder.button(text=fa.PAY_CARD_BTN, callback_data="buy:pay:card")
    builder.button(text=fa.BACK, callback_data="buy:back_to_discount")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(1, 1, 2)
    return builder.as_markup()


def _render_plans_text(plans: list[dict]) -> str:
    rows = [fa.VIP_PLANS_TABLE_HEADER, ""]
    for plan in plans:
        emoji = plan.get("emoji", "")
        if plan.get("recommended"):
            prefix = "⭐ "
            badge = " · (پیشنهادی)"
        elif emoji:
            prefix = f"{emoji} "
            badge = ""
        else:
            prefix = "▫️ "
            badge = ""
        rows.append(
            fa.VIP_PLANS_TABLE_ROW.format(
                emoji=prefix,
                gb=to_persian_digits(plan["gb"]),
                days=to_persian_digits(plan["days"]),
                price=format_toman(plan["price"]),
                badge=badge,
            )
        )
    rows.append(fa.VIP_PLANS_TABLE_FOOTER)
    return "\n".join(rows)


# ── entry: type screen ───────────────────────────────────────────────────────

async def show_type_screen(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.clear()
    await callback.message.edit_text(fa.BUY_TYPE_HEADER, reply_markup=_type_keyboard())
    await callback.answer()


@router.callback_query(F.data == "buy:type")
async def cb_back_to_type(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await show_type_screen(callback, state, **kwargs)


@router.callback_query(F.data == "buy:type:vip")
async def cb_type_vip(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    config = kwargs.get("config")
    if not config:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return
    plans = config.pricing.list_plans("vip")
    if not plans:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return
    await state.set_state(PurchaseStates.plan)
    await state.update_data(tier="vip")
    text = _render_plans_text(plans)
    await callback.message.edit_text(text, reply_markup=_plans_keyboard(plans))
    await callback.answer()


# ── plan selection → quantity ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy:plan:"))
async def cb_select_plan(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    config = kwargs.get("config")
    if not config:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return
    plan_id = callback.data.split(":", 2)[-1]
    plan = config.pricing.get_plan(plan_id)
    if not plan:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return

    await state.update_data(plan_id=plan_id, plan=plan)
    await state.set_state(PurchaseStates.quantity)
    text = fa.QUANTITY_PROMPT.format(
        gb=to_persian_digits(plan["gb"]),
        days=to_persian_digits(plan["days"]),
        price=format_toman(plan["price"]),
        max=to_persian_digits(config.pricing.QUANTITY_MAX),
    )
    await callback.message.edit_text(text, reply_markup=_quantity_back_keyboard())
    await callback.answer()


@router.message(PurchaseStates.quantity, F.text)
async def msg_quantity(message: Message, state: FSMContext, **kwargs) -> None:
    config = kwargs.get("config")
    if not config:
        await message.answer(fa.ERRORS["general"])
        return
    text = (message.text or "").strip()
    # convert persian digits to arabic
    text = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if not text.isdigit():
        await message.answer(
            fa.ERRORS["quantity_invalid"].format(
                min=to_persian_digits(1),
                max=to_persian_digits(config.pricing.QUANTITY_MAX),
            )
        )
        return
    qty = int(text)
    if not (1 <= qty <= config.pricing.QUANTITY_MAX):
        await message.answer(
            fa.ERRORS["quantity_invalid"].format(
                min=to_persian_digits(1),
                max=to_persian_digits(config.pricing.QUANTITY_MAX),
            )
        )
        return

    await state.update_data(
        quantity=qty,
        discount_code=None,
        discount_id=None,
        discount_amount=0,
        base_amount=None,
        final_amount=None,
    )
    await state.set_state(PurchaseStates.service_name)
    if qty == 1:
        await message.answer(fa.SERVICE_NAME_PROMPT, reply_markup=_service_name_keyboard())
    else:
        await message.answer(
            fa.SERVICE_NAME_MULTI_PROMPT.format(n=to_persian_digits(qty)),
            reply_markup=_service_name_keyboard(),
        )


# ── back nav ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "buy:back_to_qty")
async def cb_back_to_qty(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    config = kwargs.get("config")
    data = await state.get_data()
    plan = data.get("plan")
    if not (config and plan):
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return
    await state.set_state(PurchaseStates.quantity)
    text = fa.QUANTITY_PROMPT.format(
        gb=to_persian_digits(plan["gb"]),
        days=to_persian_digits(plan["days"]),
        price=format_toman(plan["price"]),
        max=to_persian_digits(config.pricing.QUANTITY_MAX),
    )
    await callback.message.edit_text(text, reply_markup=_quantity_back_keyboard())
    await callback.answer()


# ── service name ─────────────────────────────────────────────────────────────

async def _enter_discount_step(
    target: CallbackQuery | Message, state: FSMContext, base_amount: int
) -> None:
    data = await state.get_data()
    text = fa.DISCOUNT_PROMPT.format(
        quantity=to_persian_digits(_purchase_quantity(data)),
        amount=format_toman(base_amount),
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=_discount_keyboard())
        await target.answer()
    else:
        await target.answer(text, reply_markup=_discount_keyboard())
    await state.set_state(PurchaseStates.discount)


@router.callback_query(PurchaseStates.service_name, F.data == "buy:name:random")
async def cb_name_random(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs
) -> None:
    data = await state.get_data()
    quantity = int(data.get("quantity", 1))

    base = await _free_base_name(session)
    if quantity == 1:
        names = [base]
    else:
        names = [numbered_name(base, i + 1) for i in range(quantity)]
        if any([await is_taken(session, n) for n in names]):
            # rare collision — pick another base
            base = await _free_base_name(session)
            names = [numbered_name(base, i + 1) for i in range(quantity)]
    plan = data.get("plan") or {}
    qty = int(data.get("quantity", 1))
    base_amount = int(plan.get("price", 0)) * qty
    await _commit_pricing(state, service_names=names, base_amount=base_amount)
    await _enter_discount_step(callback, state, base_amount)


async def _free_base_name(session: AsyncSession) -> str:
    for _ in range(20):
        candidate = random_name()
        if not await is_taken(session, candidate):
            return candidate
    return random_name()


@router.message(PurchaseStates.service_name, F.text)
async def msg_service_name(
    message: Message, state: FSMContext, session: AsyncSession, **kwargs
) -> None:
    raw = (message.text or "").strip().lower()
    raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if not validate_service_name(raw):
        await message.answer(fa.ERRORS["service_name_invalid"], reply_markup=_service_name_keyboard())
        return

    data = await state.get_data()
    quantity = int(data.get("quantity", 1))

    if quantity == 1:
        if await is_taken(session, raw):
            await message.answer(fa.ERRORS["service_name_taken"], reply_markup=_service_name_keyboard())
            return
        names = [raw]
    else:
        names = [numbered_name(raw, i + 1) for i in range(quantity)]
        for n in names:
            if await is_taken(session, n):
                await message.answer(fa.ERRORS["service_name_taken"], reply_markup=_service_name_keyboard())
                return

    plan = data.get("plan") or {}
    base_amount = int(plan.get("price", 0)) * quantity
    await _commit_pricing(state, service_names=names, base_amount=base_amount)
    await _enter_discount_step(message, state, base_amount)


@router.callback_query(F.data == "buy:back_to_name")
async def cb_back_to_name(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    data = await state.get_data()
    quantity = int(data.get("quantity", 1))
    await state.set_state(PurchaseStates.service_name)
    if quantity == 1:
        await callback.message.edit_text(fa.SERVICE_NAME_PROMPT, reply_markup=_service_name_keyboard())
    else:
        await callback.message.edit_text(
            fa.SERVICE_NAME_MULTI_PROMPT.format(n=to_persian_digits(quantity)),
            reply_markup=_service_name_keyboard(),
        )
    await callback.answer()


# ── discount ─────────────────────────────────────────────────────────────────

@router.callback_query(PurchaseStates.discount, F.data == "buy:discount:skip")
async def cb_discount_skip(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    await _go_to_payment_method(callback, state, user, session, **kwargs)


@router.message(PurchaseStates.discount, F.text)
async def msg_discount_code(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    data = await state.get_data()
    base_amount = int(data.get("base_amount", 0))
    code_str = (message.text or "").strip()

    result = await validate_and_apply(session, code_str, user.tg_id, base_amount)
    if result.error:
        await message.answer(fa.ERRORS[result.error], reply_markup=_discount_keyboard())
        return

    await state.update_data(
        discount_code=result.code.code if result.code else None,
        discount_id=result.code.id if result.code else None,
        discount_amount=result.discount_amount,
        final_amount=result.final_amount,
    )
    await message.answer(
        fa.DISCOUNT_APPLIED.format(
            discount=format_toman(result.discount_amount),
            new_amount=format_toman(result.final_amount),
        )
    )
    await _go_to_payment_method(message, state, user, session, **kwargs)


async def _go_to_payment_method(
    target: CallbackQuery | Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    data = await state.get_data()
    plan = data.get("plan") or {}
    quantity = _purchase_quantity(data)
    unit_price = _unit_price(data)
    base_amount = int(data.get("base_amount", 0)) or _compute_base_amount(data)
    final_amount = _resolve_final_amount({**data, "base_amount": base_amount})
    await state.update_data(base_amount=base_amount, final_amount=final_amount)
    await state.set_state(PurchaseStates.payment_method)

    text = fa.PAYMENT_METHOD_HEADER.format(
        gb=to_persian_digits(plan.get("gb", 0)),
        days=to_persian_digits(plan.get("days", 0)),
        unit_price=format_toman(unit_price),
        quantity=to_persian_digits(quantity),
        amount=format_toman(final_amount),
    )
    markup = _method_keyboard(user.balance, final_amount)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup)


@router.callback_query(F.data == "buy:back_to_discount")
async def cb_back_to_discount(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    data = await state.get_data()
    base_amount = int(data.get("base_amount", 0))
    await _enter_discount_step(callback, state, base_amount)


# ── payment: wallet ─────────────────────────────────────────────────────────

@router.callback_query(PurchaseStates.payment_method, F.data == "buy:pay:wallet")
async def cb_pay_wallet(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    data = await state.get_data()
    plan = data.get("plan") or {}
    final_amount = _resolve_final_amount(data)

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

    vpn_service = kwargs.get("vpn_service")
    if vpn_service is None:
        await callback.answer(fa.ERRORS["vpn_unavailable"], show_alert=True)
        return

    await callback.message.edit_text(fa.WAIT_CREATING)
    await callback.answer()

    try:
        results = await _create_configs_for_user(
            session, user, data, vpn_service
        )
    except Exception:
        logger.exception("Wallet purchase: create_configs failed")
        await callback.message.edit_text(fa.ERRORS["config_create_failed"])
        await state.clear()
        return

    tx_desc = fa.TX_DESC_PURCHASE.format(
        plan_name=plan.get("tier_name", "VIP"),
        qty=to_persian_digits(int(data.get("quantity", 1))),
        name=", ".join(data.get("service_names", [])),
    )
    try:
        tx = await deduct(
            session,
            user,
            final_amount,
            tx_desc,
            tx_type=TX_PURCHASE,
            plan_id=plan.get("id"),
            config_id=results[0].config.id if results else None,
            service_name=data.get("service_names", [None])[0],
            quantity=int(data.get("quantity", 1)),
            discount_code=data.get("discount_code"),
            discount_amount=int(data.get("discount_amount", 0)),
        )
    except ValueError:
        await callback.message.edit_text(
            fa.ERRORS["insufficient_balance"].format(
                balance=format_toman(user.balance),
                required=format_toman(final_amount),
                shortage=format_toman(final_amount - user.balance),
            )
        )
        await state.clear()
        return

    if data.get("discount_id"):
        try:
            await record_usage(session, int(data["discount_id"]), user.tg_id)
        except Exception:
            logger.exception("Failed to record discount usage")

    await _credit_referrer(session, user, kwargs.get("config"), callback.bot)
    await _send_purchase_success(callback.message, results, plan)
    await state.clear()


# ── payment: card ────────────────────────────────────────────────────────────

@router.callback_query(PurchaseStates.payment_method, F.data == "buy:pay:card")
async def cb_pay_card(
    callback: CallbackQuery, state: FSMContext, **kwargs
) -> None:
    config = kwargs.get("config")
    data = await state.get_data()
    final_amount = _resolve_final_amount(data)
    payment_amount = final_amount

    await state.update_data(
        payment_amount=payment_amount,
        payment_method=PAY_CARD,
    )
    await state.set_state(PurchaseStates.awaiting_receipt)

    text = fa.CARD_PAYMENT.format(
        bank=config.payment.CARD_BANK if config else "—",
        owner=config.payment.CARD_OWNER if config else "—",
        card=config.payment.CARD_NUMBER if config else "—",
        amount=format_toman(payment_amount),
    )
    await callback.message.edit_text(
        text,
        reply_markup=card_payment_keyboard(
            toman=payment_amount,
            card=config.payment.CARD_NUMBER if config else "",
        ),
    )
    await callback.answer()


@router.message(PurchaseStates.awaiting_receipt, F.photo)
async def msg_receipt_photo(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    await _create_pending_purchase_tx(message, state, user, session, **kwargs)


@router.message(PurchaseStates.awaiting_receipt)
async def msg_receipt_other(message: Message, **kwargs) -> None:
    await message.answer(fa.RECEIPT_PROMPT)


async def _create_pending_purchase_tx(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    data = await state.get_data()
    plan = data.get("plan") or {}
    final_amount = _resolve_final_amount(data)
    payment_amount = int(data.get("payment_amount", final_amount))
    names = data.get("service_names", [])

    tx_desc = fa.TX_DESC_PURCHASE.format(
        plan_name=plan.get("tier_name", "VIP"),
        qty=to_persian_digits(int(data.get("quantity", 1))),
        name=", ".join(names) if names else "—",
    )

    receipt_photo = message.photo[-1].file_id if message.photo else None

    tx = await Transaction.create(
        session,
        user_id=user.tg_id,
        amount=final_amount,
        payment_amount=payment_amount,
        type=TX_PURCHASE,
        description=tx_desc,
        plan_id=plan.get("id"),
        quantity=int(data.get("quantity", 1)),
        service_name=names[0] if names else None,
        payment_method=PAY_CARD,
        payment_receipt=receipt_photo,
        discount_code=data.get("discount_code"),
        discount_amount=int(data.get("discount_amount", 0)),
        status=TX_PENDING,
    )
    # Persist purchase intent in admin_note as JSON so approve handler can reconstruct
    import json as _json
    admin_payload = _json.dumps({
        "plan_id": plan.get("id"),
        "plan_gb": plan.get("gb"),
        "plan_days": plan.get("days"),
        "service_names": names,
        "tier": data.get("tier", "vip"),
        "discount_id": data.get("discount_id"),
    }, ensure_ascii=False)
    await Transaction.update(session, tx.id, admin_note=admin_payload)

    await forward_purchase_to_admin(
        message.bot,
        admin_chat_id=config.payment.ADMIN_CHAT_ID if config else 0,
        tx_id=tx.id,
        user_name=user.full_name,
        username=user.username,
        tg_id=user.tg_id,
        plan_name=plan.get("tier_name", "VIP"),
        quantity=int(data.get("quantity", 1)),
        service_name=names[0] if names else "—",
        amount=payment_amount,
        discount_code=data.get("discount_code"),
        discount_amount=int(data.get("discount_amount", 0)),
        receipt_photo=receipt_photo,
    )

    await message.answer(fa.RECEIPT_RECEIVED)
    await state.clear()


# ── shared create + success ──────────────────────────────────────────────────

async def _create_configs_for_user(
    session: AsyncSession,
    user: User,
    data: dict[str, Any],
    vpn_service,
):
    if vpn_service is None:
        raise RuntimeError("VPN service unavailable")
    plan = data.get("plan") or {}
    names = list(data.get("service_names", []))
    return await vpn_service.create_many(
        session,
        user_id=user.tg_id,
        plan_id=plan.get("id", ""),
        plan_gb=int(plan.get("gb", 0)),
        plan_days=int(plan.get("days", 0)),
        service_names=names,
        tg_id=user.tg_id,
    )


def _success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.MAIN_BTN_CONFIGS, callback_data="menu:configs")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


async def _send_purchase_success(message: Message, results, plan: dict) -> None:
    from app.bot.utils.jalali import is_delayed_start

    plan_name = plan.get("tier_name", "VIP")

    if len(results) == 1:
        r = results[0]
        cfg = r.config
        if cfg.expiry_date is None:
            expiry_text = fa.DELAYED_START_FMT.format(n=to_persian_digits(cfg.plan_days))
        else:
            from app.bot.utils.jalali import to_jalali
            expiry_text = to_jalali(cfg.expiry_date)

        text = fa.PURCHASE_SUCCESS_ONE.format(
            name=cfg.service_name,
            plan_name=plan_name,
            gb=to_persian_digits(cfg.plan_gb),
            days=to_persian_digits(cfg.plan_days),
            expiry=expiry_text,
            sub_url=cfg.subscription_url,
        )
        await message.answer(text, reply_markup=_success_keyboard(), disable_web_page_preview=True)
        return

    lines = [
        fa.PURCHASE_LINE.format(name=r.config.service_name, sub_url=r.config.subscription_url)
        for r in results
    ]
    text = fa.PURCHASE_SUCCESS_BULK.format(
        n=to_persian_digits(len(results)),
        lines="\n".join(lines),
    )
    await message.answer(text, reply_markup=_success_keyboard(), disable_web_page_preview=True)


async def _credit_referrer(
    session: AsyncSession, user: User, config, bot
) -> None:
    """Give referral bonus to the referrer when the referred user makes a successful purchase."""
    if not config or not user.referred_by:
        return
    bonus = int(config.pricing.REFERRAL_BONUS_TOMAN or 0)
    if bonus <= 0:
        return
    from app.db.models import Referral
    from app.bot.services.wallet import credit
    from app.db.models.transaction import TX_REFERRAL

    ref = await Referral.get_by_referred(session, user.tg_id)
    if not ref:
        return
    try:
        await credit(
            session,
            ref.referrer_id,
            bonus,
            fa.TX_DESC_REFERRAL_RECEIVED,
            tx_type=TX_REFERRAL,
        )
        await Referral.add_purchase(session, ref.id, bonus)
    except Exception:
        logger.exception("Failed to credit referrer %s", ref.referrer_id)


# ── admin approve / reject ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:approve_purchase:"))
async def cb_admin_approve(
    callback: CallbackQuery, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    admin_ids = config.bot.ADMINS if config else []
    if callback.from_user.id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return

    tx_id = int(callback.data.rsplit(":", 1)[-1])
    tx = await Transaction.get(session, tx_id)
    if not tx:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return
    if tx.status != TX_PENDING:
        await callback.answer("✅ این تراکنش قبلاً پردازش شده است.", show_alert=True)
        return

    user = await User.get(session, tx.user_id)
    if not user:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return

    if tx.type != TX_PURCHASE:
        # Wallet topup is handled in wallet handler
        return

    import json as _json
    try:
        intent = _json.loads(tx.admin_note or "{}")
    except Exception:
        intent = {}

    plan = config.pricing.get_plan(intent.get("plan_id", ""))
    if not plan:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return

    names: list[str] = intent.get("service_names") or []
    if not names:
        await callback.answer(fa.ERRORS["general"], show_alert=True)
        return

    vpn = kwargs.get("vpn_service")
    if vpn is None:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return

    try:
        await callback.message.edit_text(fa.WAIT_CREATING)
    except Exception:
        pass
    await callback.answer()

    try:
        results = await vpn.create_many(
            session,
            user_id=user.tg_id,
            plan_id=plan["id"],
            plan_gb=plan["gb"],
            plan_days=plan["days"],
            service_names=names,
            tg_id=user.tg_id,
        )
    except Exception:
        logger.exception("Admin approve: create_many failed for tx=%s", tx_id)
        await callback.answer(fa.ERRORS["config_create_failed"], show_alert=True)
        return

    await Transaction.update(
        session,
        tx_id,
        status="confirmed",
        confirmed_at=datetime.utcnow(),
        config_id=results[0].config.id if results else None,
    )
    if intent.get("discount_id"):
        try:
            await record_usage(session, int(intent["discount_id"]), user.tg_id)
        except Exception:
            logger.exception("Failed to record discount usage on approve")

    await _credit_referrer(session, user, config, callback.bot)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    try:
        await _send_purchase_success_to_user(callback.bot, user.tg_id, results, plan)
    except Exception:
        logger.exception("Failed to send purchase success to user %s", user.tg_id)


async def _send_purchase_success_to_user(bot, user_id: int, results, plan: dict) -> None:
    from app.bot.utils.jalali import to_jalali

    plan_name = plan.get("tier_name", "VIP")
    if len(results) == 1:
        cfg = results[0].config
        if cfg.expiry_date is None:
            expiry_text = fa.DELAYED_START_FMT.format(n=to_persian_digits(cfg.plan_days))
        else:
            expiry_text = to_jalali(cfg.expiry_date)
        text = fa.PURCHASE_SUCCESS_ONE.format(
            name=cfg.service_name,
            plan_name=plan_name,
            gb=to_persian_digits(cfg.plan_gb),
            days=to_persian_digits(cfg.plan_days),
            expiry=expiry_text,
            sub_url=cfg.subscription_url,
        )
    else:
        lines = [
            fa.PURCHASE_LINE.format(name=r.config.service_name, sub_url=r.config.subscription_url)
            for r in results
        ]
        text = fa.PURCHASE_SUCCESS_BULK.format(
            n=to_persian_digits(len(results)),
            lines="\n".join(lines),
        )
    await bot.send_message(user_id, text, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data.startswith("admin:reject_purchase:"))
async def cb_admin_reject(
    callback: CallbackQuery, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    admin_ids = config.bot.ADMINS if config else []
    if callback.from_user.id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return

    tx_id = int(callback.data.rsplit(":", 1)[-1])
    tx = await Transaction.get(session, tx_id)
    if not tx or tx.status != TX_PENDING:
        await callback.answer("این تراکنش قبلاً پردازش شده.", show_alert=True)
        return

    await Transaction.update(session, tx_id, status="rejected", admin_note="rejected by admin")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    try:
        await callback.bot.send_message(
            tx.user_id,
            fa.PURCHASE_REJECTED.format(reason="رسید پرداخت تایید نشد."),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.answer("❌ رد شد.", show_alert=False)


@router.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(
    callback: CallbackQuery, state: FSMContext, user: User, **kwargs
) -> None:
    await state.clear()
    from app.bot.routers.main_menu.handler import _is_admin, main_menu_keyboard

    config = kwargs.get("config")
    markup = main_menu_keyboard(_is_admin(user, config))
    try:
        await callback.message.edit_text(fa.WELCOME, reply_markup=markup)
    except Exception:
        await callback.message.answer(fa.WELCOME, reply_markup=markup)
    await callback.answer("لغو شد.")
