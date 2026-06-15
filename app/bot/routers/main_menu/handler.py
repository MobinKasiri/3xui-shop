from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.db.models import User

router = Router(name="main_menu")

# ── Reply keyboard button labels ──────────────────────────────────────────────
BTN_TRIAL      = "🔑 اکانت تست"
BTN_PURCHASE   = "📦 خرید اشتراک"
BTN_SERVICES   = "🗂 سرویس های من"
BTN_WALLET     = "🏠 کیف پول + شارژ"
BTN_GUIDE      = "📖 آموزش"
BTN_SUPPORT    = "📞 پشتیبانی"
BTN_AGENCY     = "🤝 درخواست نمایندگی"
BTN_REFERRAL   = "👥 زیر مجموعه گیری"
BTN_PRICING    = "📋 تعرفه‌ها"
BTN_BULK       = "🛒 خرید عمده"
BTN_ADMIN      = "🔐 مدیریت"

ALL_REPLY_BTNS = {
    BTN_TRIAL, BTN_PURCHASE, BTN_SERVICES, BTN_WALLET,
    BTN_GUIDE, BTN_SUPPORT, BTN_AGENCY, BTN_REFERRAL,
    BTN_PRICING, BTN_BULK, BTN_ADMIN,
}


def main_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=BTN_TRIAL),
        KeyboardButton(text=BTN_PURCHASE),
    )
    builder.row(
        KeyboardButton(text=BTN_SERVICES),
        KeyboardButton(text=BTN_WALLET),
    )
    builder.row(
        KeyboardButton(text=BTN_GUIDE),
        KeyboardButton(text=BTN_SUPPORT),
    )
    builder.row(
        KeyboardButton(text=BTN_REFERRAL),
        KeyboardButton(text=BTN_PRICING),
    )
    if is_admin:
        builder.row(
            KeyboardButton(text=BTN_AGENCY),
            KeyboardButton(text=BTN_ADMIN),
        )
    else:
        builder.row(KeyboardButton(text=BTN_AGENCY))
    return builder.as_markup(resize_keyboard=True, persistent=True)


def back_inline() -> object:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
    return builder.as_markup()


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, user: User, session: AsyncSession, **kwargs) -> None:
    config = kwargs.get("config")
    admin_ids: list[int] = config.bot.ADMINS if config else []
    is_admin = user.tg_id in admin_ids

    # Handle referral deep link: /start ref_<code>
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    if args.startswith("ref_") and not user.referred_by:
        code = args[4:]
        referrer = await User.get_by_referral_code(session, code)
        if referrer and referrer.tg_id != user.tg_id:
            from app.db.models.referral import Referral
            existing = await Referral.get_by_referred(session, user.tg_id)
            if not existing:
                await User.update(session, user.tg_id, referred_by=referrer.tg_id)
                await Referral.create(
                    session, referrer_id=referrer.tg_id, referred_id=user.tg_id
                )

    await message.answer(
        fa.WELCOME.format(name=message.from_user.full_name),
        reply_markup=main_reply_keyboard(is_admin),
    )


# ── Reply-keyboard button → route to the right flow ──────────────────────────

@router.message(F.text == BTN_TRIAL)
async def msg_trial(message: Message, user: User, **kwargs) -> None:
    from app.bot.routers.trial.handler import _trial_confirm_keyboard
    from app.bot.i18n.fa import TRIAL_ALREADY_USED, TRIAL_ALREADY_USED_BUY_BTN, TRIAL_CONFIRM
    if user.is_trial_used:
        builder = InlineKeyboardBuilder()
        builder.button(text=TRIAL_ALREADY_USED_BUY_BTN, callback_data="purchase:start")
        await message.answer(TRIAL_ALREADY_USED, reply_markup=builder.as_markup())
    else:
        await message.answer(TRIAL_CONFIRM, reply_markup=_trial_confirm_keyboard())


@router.message(F.text == BTN_PURCHASE)
async def msg_purchase(message: Message, **kwargs) -> None:
    config = kwargs.get("config")
    plans = config.pricing.PLANS if config else {}
    from app.bot.routers.purchase.handler import _plans_keyboard
    await message.answer(fa.PURCHASE_HEADER, reply_markup=_plans_keyboard(plans))


@router.message(F.text == BTN_SERVICES)
async def msg_services(message: Message, user: User, session: AsyncSession, **kwargs) -> None:
    from app.bot.routers.my_services.handler import _render_services
    await _render_services(message, user, session, **kwargs)


@router.message(F.text == BTN_WALLET)
async def msg_wallet(message: Message, user: User, session: AsyncSession, **kwargs) -> None:
    from app.bot.routers.wallet.handler import _wallet_home_keyboard
    from app.bot.i18n.fa import WALLET_HEADER, WALLET_NO_TX, WALLET_TX_ROW_CREDIT, WALLET_TX_ROW_DEBIT
    from app.db.models.transaction import Transaction
    from app.bot.utils.jalali import to_jalali
    from app.bot.utils.persian import format_toman
    txs = await Transaction.get_for_user(session, user.tg_id, limit=5)
    tx_lines = []
    for tx in txs:
        date = to_jalali(tx.created_at) if tx.created_at else "—"
        if tx.amount >= 0:
            tx_lines.append(WALLET_TX_ROW_CREDIT.format(desc=tx.description or tx.type, amount=format_toman(tx.amount), date=date))
        else:
            tx_lines.append(WALLET_TX_ROW_DEBIT.format(desc=tx.description or tx.type, amount=format_toman(abs(tx.amount)), date=date))
    tx_text = "\n".join(tx_lines) if tx_lines else WALLET_NO_TX
    await message.answer(
        WALLET_HEADER.format(balance=format_toman(user.balance)) + tx_text,
        reply_markup=_wallet_home_keyboard(),
    )


@router.message(F.text == BTN_GUIDE)
async def msg_guide(message: Message, **kwargs) -> None:
    from app.bot.routers.guide.handler import _guide_main_keyboard
    await message.answer(fa.GUIDE_MAIN, reply_markup=_guide_main_keyboard())


@router.message(F.text == BTN_SUPPORT)
async def msg_support(message: Message, **kwargs) -> None:
    config = kwargs.get("config")
    support_username = config.payment.SUPPORT_USERNAME if config else "@support"
    await message.answer(fa.SUPPORT_MSG.format(support_username=support_username))


@router.message(F.text == BTN_AGENCY)
async def msg_agency(message: Message, state, **kwargs) -> None:
    from aiogram.fsm.context import FSMContext
    from app.bot.routers.agency.handler import AgencyStates
    st: FSMContext = state
    await st.set_state(AgencyStates.waiting_message)
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.CANCEL, callback_data="cancel_fsm")
    await message.answer(fa.AGENCY_INFO, reply_markup=builder.as_markup())


@router.message(F.text == BTN_REFERRAL)
async def msg_referral(message: Message, user: User, session: AsyncSession, **kwargs) -> None:
    from app.db.models.referral import Referral
    from sqlalchemy import select, func
    count = await Referral.count_for_referrer(session, user.tg_id)
    from app.db.models.referral import Referral as R
    result = await session.execute(
        select(func.coalesce(func.sum(R.bonus_mb), 0)).where(
            R.referrer_id == user.tg_id, R.bonus_given == True
        )
    )
    total_mb = result.scalar_one() or 0
    bot_info = await message.bot.get_me()
    from app.bot.utils.persian import to_persian_digits
    text = fa.REFERRAL_PAGE.format(
        bot_username=bot_info.username,
        referral_code=user.referral_code,
        count=to_persian_digits(count),
        total_mb=to_persian_digits(total_mb),
    )
    builder = InlineKeyboardBuilder()
    builder.button(
        text=fa.REFERRAL_SHARE_BTN,
        url=f"https://t.me/share/url?url=https://t.me/{bot_info.username}?start=ref_{user.referral_code}",
    )
    await message.answer(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)


@router.message(F.text == BTN_PRICING)
async def msg_pricing(message: Message, **kwargs) -> None:
    config = kwargs.get("config")
    plans = config.pricing.PLANS if config else {}
    from app.bot.utils.persian import format_toman
    lines = [fa.PRICING_HEADER]
    for plan in plans.values():
        per_gb = plan["price"] // plan["traffic_gb"]
        lines.append(fa.PRICING_ROW.format(
            emoji=plan["emoji"], name=plan["name"],
            traffic_gb=plan["traffic_gb"], duration_days=plan["duration_days"],
            price=format_toman(plan["price"]), per_gb=format_toman(per_gb),
        ))
    lines.append(fa.PRICING_FOOTER)
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.MAIN_MENU_BUTTONS["purchase"], callback_data="purchase:start")
    await message.answer("\n".join(lines), reply_markup=builder.as_markup())


@router.message(F.text == BTN_ADMIN)
async def msg_admin(message: Message, user: User, session: AsyncSession, **kwargs) -> None:
    config = kwargs.get("config")
    admin_ids: list[int] = config.bot.ADMINS if config else []
    if user.tg_id not in admin_ids:
        await message.answer(fa.ERRORS["admin_only"])
        return
    from app.bot.routers.admin.handler import _dashboard_text, _admin_keyboard
    xui_service = kwargs.get("xui_service")
    text = await _dashboard_text(session, xui_service)
    await message.answer(text, reply_markup=_admin_keyboard())


# ── cancel FSM (from any state) ───────────────────────────────────────────────

@router.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(callback: CallbackQuery, state, **kwargs) -> None:
    from aiogram.fsm.context import FSMContext
    st: FSMContext = state
    await st.clear()
    await callback.message.delete()
    await callback.answer("لغو شد.")


# ── Legacy inline main_menu callback (for back buttons in sub-menus) ──────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, **kwargs) -> None:
    await callback.message.delete()
    await callback.answer("از منوی پایین انتخاب کنید.")
