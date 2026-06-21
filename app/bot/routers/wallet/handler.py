"""
Wallet / profile (screenshot 11).

- Profile: avatar/name/balance + buttons (top-up, transactions).
- Top-up: amount presets + custom amount FSM.
- Card payment: shared with purchase flow but writes a wallet_charge TX.
- Transactions: paginated list.
"""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)
from app.bot.utils.keyboards import K
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.notifications import forward_wallet_topup_to_admin
from app.bot.utils.payment_keyboard import card_payment_keyboard
from app.bot.utils.receipt_storage import persist_receipt_photo
from app.bot.utils.jalali import to_jalali
from app.bot.utils.persian import format_toman, normalize_digits, to_persian_digits
from app.db.models import Transaction, User
from app.db.models.transaction import (
    PAY_CARD,
    TX_CONFIRMED,
    TX_PENDING,
    TX_REFERRAL,
    TX_REJECTED,
    TX_WALLET_TOPUP,
)

logger = logging.getLogger(__name__)

router = Router(name="wallet")

PRESETS = [50_000, 100_000, 200_000, 500_000, 1_000_000]
MIN_TOPUP = 10_000
MAX_TOPUP = 100_000_000  # PostgreSQL INTEGER limit; also blocks typos like 100000000000


def _topup_amount_error(amount: int) -> str | None:
    if amount < MIN_TOPUP:
        return fa.ERRORS["amount_min"].format(min=format_toman(MIN_TOPUP))
    if amount > MAX_TOPUP:
        return fa.ERRORS["amount_max"].format(max=format_toman(MAX_TOPUP))
    return None


class TopupStates(StatesGroup):
    custom_amount = State()
    awaiting_receipt = State()


# ── profile ──────────────────────────────────────────────────────────────────

def _profile_keyboard() -> InlineKeyboardMarkup:
    return (
        K()
        .primary(fa.WALLET_TOPUP_BTN, callback_data="menu:balance")
        .btn(fa.WALLET_TX_BTN, callback_data="wallet:tx:0")
        .back_to_menu()
        .adjust(1)
        .as_markup()
    )


async def show_profile(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    text = fa.PROFILE_TEXT.format(
        name=user.full_name or "—",
        username=f"@{user.username}" if user.username else "—",
        tg_id=to_persian_digits(user.tg_id),
        balance=format_toman(user.balance),
    )
    await callback.message.edit_text(text, reply_markup=_profile_keyboard())
    await callback.answer()


# ── topup amounts ────────────────────────────────────────────────────────────

def _amounts_keyboard() -> InlineKeyboardMarkup:
    kb = K()
    for amount in PRESETS:
        kb.primary(format_toman(amount) + " ت", callback_data=f"wallet:topup:{amount}")
    return (
        kb.primary(fa.TOPUP_CUSTOM_BTN, callback_data="wallet:topup:custom")
        .back_to_menu()
        .adjust(2, 2, 1, 1, 1)
        .as_markup()
    )


async def show_topup_amounts(
    target: CallbackQuery | Message, state: FSMContext, **kwargs
) -> None:
    await state.clear()
    markup = _amounts_keyboard()
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(fa.TOPUP_AMOUNTS_HEADER, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(fa.TOPUP_AMOUNTS_HEADER, reply_markup=markup)


@router.callback_query(F.data == "wallet:topup:custom")
async def cb_custom_amount(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    await state.set_state(TopupStates.custom_amount)
    await callback.message.edit_text(
        fa.TOPUP_CUSTOM_PROMPT, reply_markup=K().cancel().as_markup()
    )
    await callback.answer()


@router.message(TopupStates.custom_amount, F.text)
async def msg_custom_amount(
    message: Message, state: FSMContext, user: User, **kwargs
) -> None:
    raw = normalize_digits((message.text or "").strip())
    raw = raw.replace(",", "").replace("٬", "").replace(" ", "")
    if not raw.isdigit():
        await message.answer(fa.ERRORS["amount_invalid"])
        return
    amount = int(raw)
    if err := _topup_amount_error(amount):
        await message.answer(err)
        return
    await _start_card_topup(message, state, amount, **kwargs)


@router.callback_query(F.data.startswith("wallet:topup:"))
async def cb_preset_topup(
    callback: CallbackQuery, state: FSMContext, **kwargs
) -> None:
    suffix = callback.data.rsplit(":", 1)[-1]
    if suffix == "custom":
        return  # handled separately
    try:
        amount = int(suffix)
    except ValueError:
        await callback.answer(fa.ERRORS["amount_invalid"], show_alert=True)
        return
    await _start_card_topup(callback, state, amount, **kwargs)


async def _start_card_topup(
    target: CallbackQuery | Message,
    state: FSMContext,
    amount: int,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    payment_amount = amount

    await state.update_data(
        topup_amount=amount,
        payment_amount=payment_amount,
    )
    await state.set_state(TopupStates.awaiting_receipt)

    text = fa.CARD_PAYMENT.format(
        bank=config.payment.CARD_BANK if config else "—",
        owner=config.payment.CARD_OWNER if config else "—",
        card=config.payment.CARD_NUMBER if config else "—",
        amount=format_toman(payment_amount),
    )
    markup = card_payment_keyboard(
        toman=payment_amount,
        card=config.payment.CARD_NUMBER if config else "",
    )

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup)


@router.message(TopupStates.awaiting_receipt, F.photo | F.document)
async def msg_receipt(
    message: Message, state: FSMContext, user: User, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    data = await state.get_data()
    amount = int(data.get("topup_amount", 0))
    payment_amount = int(data.get("payment_amount", amount))
    if err := _topup_amount_error(amount):
        await message.answer(err)
        await state.clear()
        return
    receipt_photo = message.photo[-1].file_id if message.photo else (
        message.document.file_id if message.document else None
    )

    tx = await Transaction.create(
        session,
        user_id=user.tg_id,
        amount=amount,
        payment_amount=payment_amount,
        type=TX_WALLET_TOPUP,
        description=fa.TX_DESC_WALLET,
        payment_method=PAY_CARD,
        payment_receipt=receipt_photo,
        status=TX_PENDING,
    )
    receipt_ref = await persist_receipt_photo(message, tx.id)
    if receipt_ref:
        await Transaction.update(session, tx.id, payment_receipt=receipt_ref)

    await forward_wallet_topup_to_admin(
        message.bot,
        admin_chat_id=config.payment.ADMIN_CHAT_ID if config else 0,
        tx_id=tx.id,
        user_name=user.full_name,
        username=user.username,
        tg_id=user.tg_id,
        amount=payment_amount,
        receipt_photo=receipt_photo,
    )
    await message.answer(fa.RECEIPT_RECEIVED)
    await state.clear()


@router.message(TopupStates.awaiting_receipt)
async def msg_receipt_other(message: Message, **kwargs) -> None:
    await message.answer(fa.RECEIPT_PROMPT)


# ── transactions list ────────────────────────────────────────────────────────

PAGE_SIZE = 5


def _tx_icon(tx: Transaction) -> str:
    if tx.status == TX_PENDING:
        return fa.TX_ICON_PENDING
    if tx.type == TX_REFERRAL:
        return fa.TX_ICON_REFERRAL
    return fa.TX_ICON_DEBIT if _is_debit(tx) else fa.TX_ICON_CREDIT


def _is_debit(tx: Transaction) -> bool:
    """A debit is a money-out tx (purchase, refund) regardless of `amount` sign."""
    from app.db.models.transaction import TX_PURCHASE, TX_REFUND
    if tx.type in (TX_PURCHASE, TX_REFUND):
        return True
    return tx.amount < 0


def _tx_sign(tx: Transaction) -> str:
    return "-" if _is_debit(tx) else "+"


@router.callback_query(F.data.startswith("wallet:tx:"))
async def cb_transactions(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    page = int(callback.data.rsplit(":", 1)[-1])
    total = await Transaction.count_for_user(session, user.tg_id)
    if total == 0:
        await callback.message.edit_text(
            fa.TX_LIST_EMPTY,
            reply_markup=K().nav("menu:account").adjust(2).as_markup(),
        )
        await callback.answer()
        return

    txs = await Transaction.get_for_user(
        session, user.tg_id, limit=PAGE_SIZE, offset=page * PAGE_SIZE
    )
    lines = [fa.TX_LIST_HEADER]
    for tx in txs:
        lines.append(
            fa.TX_LIST_ROW.format(
                icon=_tx_icon(tx),
                desc=tx.description or tx.type,
                sign=_tx_sign(tx),
                amount=format_toman(abs(tx.amount)),
                date=to_jalali(tx.created_at) if tx.created_at else "—",
            )
        )
    kb = K()
    if page > 0:
        kb.btn("◀️ قبل", callback_data=f"wallet:tx:{page-1}")
    if (page + 1) * PAGE_SIZE < total:
        kb.btn("بعد ▶️", callback_data=f"wallet:tx:{page+1}")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=kb.nav("menu:account").adjust(2, 2).as_markup(),
    )
    await callback.answer()


# ── admin approve/reject for wallet top-up ───────────────────────────────────

@router.callback_query(F.data.startswith("admin:approve_wallet:"))
async def cb_admin_approve_wallet(
    callback: CallbackQuery, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    admin_ids = config.bot.ADMINS if config else []
    if callback.from_user.id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return

    tx_id = int(callback.data.rsplit(":", 1)[-1])
    tx = await Transaction.get(session, tx_id)
    if not tx or tx.type != TX_WALLET_TOPUP:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return
    if tx.status != TX_PENDING:
        await callback.answer("این تراکنش قبلاً پردازش شده.", show_alert=True)
        return

    user = await User.get(session, tx.user_id)
    if not user:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return

    new_balance = user.balance + tx.amount
    await User.update(session, user.tg_id, balance=new_balance)
    await Transaction.update(
        session,
        tx_id,
        status=TX_CONFIRMED,
        confirmed_at=datetime.utcnow(),
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        await callback.bot.send_message(
            user.tg_id,
            fa.WALLET_CHARGED.format(balance=format_toman(new_balance)),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer("✅ شارژ تایید شد.", show_alert=False)


@router.callback_query(F.data.startswith("admin:reject_wallet:"))
async def cb_admin_reject_wallet(
    callback: CallbackQuery, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    admin_ids = config.bot.ADMINS if config else []
    if callback.from_user.id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return
    tx_id = int(callback.data.rsplit(":", 1)[-1])
    tx = await Transaction.get(session, tx_id)
    if not tx or tx.type != TX_WALLET_TOPUP or tx.status != TX_PENDING:
        await callback.answer("این تراکنش قبلاً پردازش شده.", show_alert=True)
        return
    await Transaction.update(
        session,
        tx_id,
        status=TX_REJECTED,
        admin_note="rejected by admin",
    )
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
