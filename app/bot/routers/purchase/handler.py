from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.bootstrap import ensure_vpn_service
from app.bot.services.vpn import VPNService
from app.bot.services.wallet import deduct
from app.bot.services.notifications import forward_payment_to_admin
from app.bot.utils.jalali import to_jalali
from app.bot.utils.keyboards import back_to_menu_keyboard
from app.bot.utils.persian import format_toman
from app.db.models import User, VPNConfig
from app.db.models.transaction import (
    Transaction, TX_PURCHASE, TX_CONFIRMED, TX_PENDING, TX_REJECTED
)

logger = logging.getLogger(__name__)
router = Router(name="purchase")


class PurchaseStates(StatesGroup):
    waiting_receipt = State()


def _plans_keyboard(plans: dict) -> object:
    builder = InlineKeyboardBuilder()
    for key, plan in plans.items():
        label = f"{plan['emoji']} {plan['name']} | {plan['traffic_gb']} گیگ — {format_toman(plan['price'])} تومان"
        builder.button(text=label, callback_data=f"purchase:plan:{key}")
    builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def _payment_method_keyboard(plan_key: str, user_balance: int, plan_price: int) -> object:
    builder = InlineKeyboardBuilder()
    if user_balance >= plan_price:
        builder.button(
            text=fa.PAY_FROM_WALLET_BTN.format(balance=format_toman(user_balance)),
            callback_data=f"purchase:pay_wallet:{plan_key}",
        )
    builder.button(text=fa.PAY_CARD_BTN, callback_data=f"purchase:pay_card:{plan_key}")
    builder.button(text=fa.BACK, callback_data="purchase:start")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "purchase:start")
async def cb_purchase_start(callback: CallbackQuery, user: User, **kwargs) -> None:
    config = kwargs.get("config")
    plans = config.pricing.PLANS if config else {}
    await callback.message.edit_text(
        fa.PURCHASE_HEADER, reply_markup=_plans_keyboard(plans)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("purchase:plan:"))
async def cb_plan_selected(callback: CallbackQuery, user: User, **kwargs) -> None:
    plan_key = callback.data.split(":", 2)[2]
    config = kwargs.get("config")
    plans = config.pricing.PLANS if config else {}
    plan = plans.get(plan_key)
    if not plan:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return

    text = fa.PLAN_DETAIL.format(
        emoji=plan["emoji"],
        name=plan["name"],
        traffic_gb=plan["traffic_gb"],
        duration_days=plan["duration_days"],
        price=format_toman(plan["price"]),
    )
    await callback.message.edit_text(
        text,
        reply_markup=_payment_method_keyboard(plan_key, user.balance, plan["price"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("purchase:pay_wallet:"))
async def cb_pay_wallet(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    **kwargs,
) -> None:
    # data format: purchase:pay_wallet:{plan_key}  → split gives 3 parts, index 2
    plan_key = callback.data.split(":", 2)[2]
    config = kwargs.get("config")
    vpn_service: VPNService | None = kwargs.get("vpn_service")
    if vpn_service is None and config:
        vpn_service = await ensure_vpn_service(config)
    plans = config.pricing.PLANS if config else {}
    plan = plans.get(plan_key)
    if not plan:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
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

    if vpn_service is None:
        await callback.message.edit_text(fa.ERRORS["api_error"], reply_markup=back_to_menu_keyboard())
        await callback.answer()
        return

    await callback.message.edit_text(fa.TRIAL_CREATING)
    await callback.answer()

    try:
        # Deduct wallet
        tx = await deduct(
            session, user, price,
            description=f"خرید پلن {plan['name']}",
            plan_key=plan_key,
        )

        # Apply referral bonus if pending
        bonus_mb = 0
        if not user.referred_by:
            pass
        else:
            from app.db.models.referral import Referral
            ref = await Referral.get_pending_bonus(session, user.tg_id)
            if ref:
                bonus_mb = config.pricing.REFERRAL_FRIEND_BONUS_MB if config else 200
                referrer_bonus = config.pricing.REFERRAL_BONUS_MB if config else 500
                await User.update(
                    session, ref.referrer_id,
                    bonus_pending_mb=User.__table__.c.bonus_pending_mb if False else None
                )
                # Give referrer pending bonus
                await User.update(session, ref.referrer_id,
                    bonus_pending_mb=referrer_bonus
                )
                from app.db.models.referral import Referral as R
                await R.mark_bonus_given(session, ref.id, referrer_bonus)

        result = await vpn_service.create_config(
            session=session,
            user_id=user.tg_id,
            plan_key=plan_key,
            traffic_mb=plan["traffic_gb"] * 1024,
            duration_days=plan["duration_days"],
            tg_id=user.tg_id,
            is_trial=False,
            bonus_mb=bonus_mb,
        )
        # Update tx with config_id
        await Transaction.update(session, tx.id, config_id=result.config.id, status=TX_CONFIRMED)

        expiry_jalali = to_jalali(result.config.expiry_date) if result.config.expiry_date else "—"
        await callback.message.edit_text(
            fa.PURCHASE_SUCCESS.format(
                plan_name=plan["name"],
                traffic_gb=plan["traffic_gb"],
                expiry_jalali=expiry_jalali,
                sub_url=result.subscription_url,
            ),
            reply_markup=back_to_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Wallet purchase failed for user {user.tg_id}: {e}")
        await callback.message.edit_text(fa.ERRORS["general"], reply_markup=back_to_menu_keyboard())


@router.callback_query(F.data.startswith("purchase:pay_card:"))
async def cb_pay_card(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    **kwargs,
) -> None:
    # data format: purchase:pay_card:{plan_key}  → split gives 3 parts, index 2
    plan_key = callback.data.split(":", 2)[2]
    config = kwargs.get("config")
    plans = config.pricing.PLANS if config else {}
    plan = plans.get(plan_key)
    if not plan:
        await callback.answer(fa.ERRORS["not_found"], show_alert=True)
        return

    card_num = config.payment.CARD_NUMBER if config else "XXXX"
    card_owner = config.payment.CARD_OWNER if config else "—"

    await state.set_state(PurchaseStates.waiting_receipt)
    await state.update_data(plan_key=plan_key)

    await callback.message.edit_text(
        fa.PAYMENT_CARD_DETAIL.format(
            amount=format_toman(plan["price"]),
            card_number=card_num,
            card_owner=card_owner,
        ),
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()


@router.message(PurchaseStates.waiting_receipt)
async def on_receipt_received(
    message: Message,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    data = await state.get_data()
    plan_key = data.get("plan_key")
    plans = config.pricing.PLANS if config else {}
    plan = plans.get(plan_key)
    if not plan:
        await state.clear()
        await message.answer(fa.ERRORS["general"])
        return

    receipt_photo: str | None = None
    receipt_text: str | None = None

    if message.photo:
        receipt_photo = message.photo[-1].file_id
    elif message.text:
        receipt_text = message.text
    else:
        await message.answer("لطفاً عکس رسید یا متن رسید پرداخت را ارسال کنید.")
        return

    # Create pending transaction
    tx = await Transaction.create(
        session,
        user_id=user.tg_id,
        amount=plan["price"],
        type=TX_PURCHASE,
        description=f"خرید پلن {plan['name']}",
        plan_key=plan_key,
        status=TX_PENDING,
        payment_receipt=receipt_photo or receipt_text,
    )

    await state.clear()
    await message.answer(fa.RECEIPT_RECEIVED, reply_markup=back_to_menu_keyboard())

    # Forward to admin
    admin_chat_id = config.payment.ADMIN_CHAT_ID if config else 0
    if admin_chat_id:
        bot = message.bot
        await forward_payment_to_admin(
            bot=bot,
            admin_chat_id=admin_chat_id,
            tx_id=tx.id,
            user_name=user.full_name,
            username=user.username,
            tg_id=user.tg_id,
            plan_name=plan["name"],
            amount=plan["price"],
            receipt_photo=receipt_photo,
            receipt_text=receipt_text,
            approve_cb=f"admin:approve_tx:{tx.id}",
            reject_cb=f"admin:reject_tx:{tx.id}",
        )


# ── Admin approve / reject handlers ───────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:approve_tx:"))
async def cb_admin_approve(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    admin_ids = config.bot.ADMINS if config else []
    if user.tg_id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return

    tx_id = int(callback.data.split(":")[-1])
    tx = await Transaction.get(session, tx_id)
    if not tx or tx.status != TX_PENDING:
        await callback.answer("این تراکنش قبلاً پردازش شده است.", show_alert=True)
        return

    vpn_service: VPNService | None = kwargs.get("vpn_service")
    if vpn_service is None and config:
        vpn_service = await ensure_vpn_service(config)
    plans = config.pricing.PLANS if config else {}
    plan = plans.get(tx.plan_key or "")

    if not plan or vpn_service is None:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return

    # Get the buyer
    from app.db.models.user import User as U
    buyer = await U.get(session, tx.user_id)
    if not buyer:
        await callback.answer("کاربر یافت نشد.", show_alert=True)
        return

    try:
        result = await vpn_service.create_config(
            session=session,
            user_id=buyer.tg_id,
            plan_key=tx.plan_key,
            traffic_mb=plan["traffic_gb"] * 1024,
            duration_days=plan["duration_days"],
            tg_id=buyer.tg_id,
        )
        await Transaction.update(
            session, tx_id,
            status=TX_CONFIRMED,
            config_id=result.config.id,
            confirmed_at=datetime.now(tz=timezone.utc),
        )

        expiry_jalali = to_jalali(result.config.expiry_date) if result.config.expiry_date else "—"
        # Notify buyer
        await callback.bot.send_message(
            buyer.tg_id,
            fa.PURCHASE_SUCCESS.format(
                plan_name=plan["name"],
                traffic_gb=plan["traffic_gb"],
                expiry_jalali=expiry_jalali,
                sub_url=result.subscription_url,
            ),
            parse_mode="HTML",
        )

        await callback.message.edit_caption(
            (callback.message.caption or callback.message.text or "") + "\n\n✅ تایید شد.",
        )
        await callback.answer("✅ سرویس ایجاد و به کاربر ارسال شد.")
    except Exception as e:
        logger.error(f"Admin approve failed: {e}")
        await callback.answer(f"خطا: {e}", show_alert=True)


@router.callback_query(F.data.startswith("admin:reject_tx:"))
async def cb_admin_reject(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    **kwargs,
) -> None:
    config = kwargs.get("config")
    admin_ids = config.bot.ADMINS if config else []
    if user.tg_id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return

    tx_id = int(callback.data.split(":")[-1])
    tx = await Transaction.get(session, tx_id)
    if not tx or tx.status != TX_PENDING:
        await callback.answer("این تراکنش قبلاً پردازش شده است.", show_alert=True)
        return

    await Transaction.update(session, tx_id, status=TX_REJECTED)

    # Notify buyer
    from app.db.models.user import User as U
    buyer = await U.get(session, tx.user_id)
    if buyer:
        await callback.bot.send_message(
            buyer.tg_id,
            fa.PURCHASE_REJECTED.format(reason="پرداخت تایید نشد."),
            parse_mode="HTML",
        )

    try:
        await callback.message.edit_caption(
            (callback.message.caption or callback.message.text or "") + "\n\n❌ رد شد.",
        )
    except Exception:
        await callback.message.edit_text(
            (callback.message.text or "") + "\n\n❌ رد شد.",
        )
    await callback.answer("❌ تراکنش رد شد.")
