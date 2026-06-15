from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.is_admin import IsAdmin
from app.bot.i18n import fa
from app.bot.utils.keyboards import back_to_menu_keyboard
from app.bot.utils.persian import format_toman, to_persian_digits
from app.db.models import User, VPNConfig
from app.db.models.transaction import Transaction
from app.db.models.agency_request import AgencyRequest

logger = logging.getLogger(__name__)
router = Router(name="admin")


async def _dashboard_text(session: AsyncSession, xui_service=None) -> str:
    today_users = await User.today_count(session)
    total_users = await User.count(session)
    active_configs = await VPNConfig.count_active(session)
    today_rev = int(await Transaction.today_revenue(session))
    total_rev = int(await Transaction.total_revenue(session))

    cpu = ram = "—"
    xray_state = "—"
    if xui_service:
        try:
            status = await xui_service.get_server_status()
            cpu = f"{status.cpu:.1f}"
            ram_pct = (status.mem_current / status.mem_total * 100) if status.mem_total else 0
            ram = f"{ram_pct:.1f}"
            xray_state = status.xray_state
        except Exception:
            pass

    return fa.ADMIN_DASHBOARD.format(
        today_users=to_persian_digits(today_users),
        today_revenue=format_toman(today_rev),
        total_users=to_persian_digits(total_users),
        active_configs=to_persian_digits(active_configs),
        total_revenue=format_toman(total_rev),
        cpu=to_persian_digits(cpu),
        ram=to_persian_digits(ram),
        xray_state=xray_state,
    )


def _admin_keyboard() -> object:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 تراکنش‌های معلق", callback_data="admin:pending_txs")
    builder.button(text="📨 درخواست نمایندگی", callback_data="admin:pending_agency")
    builder.button(text="👥 لیست کاربران", callback_data="admin:users:0")
    builder.button(text="📢 ارسال همگانی", callback_data="admin:broadcast")
    builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


@router.message(IsAdmin(), Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, **kwargs) -> None:
    xui_service = kwargs.get("xui_service")
    text = await _dashboard_text(session, xui_service)
    await message.answer(text, reply_markup=_admin_keyboard())


@router.callback_query(F.data == "admin:dashboard")
async def cb_admin_dashboard(callback: CallbackQuery, user: User, session: AsyncSession, **kwargs) -> None:
    config_obj = kwargs.get("config")
    admin_ids = config_obj.bot.ADMINS if config_obj else []
    if user.tg_id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return
    xui_service = kwargs.get("xui_service")
    text = await _dashboard_text(session, xui_service)
    await callback.message.edit_text(text, reply_markup=_admin_keyboard())
    await callback.answer()


@router.message(IsAdmin(), Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, **kwargs) -> None:
    xui_service = kwargs.get("xui_service")
    text = await _dashboard_text(session, xui_service)
    await message.answer(text)


@router.message(IsAdmin(), Command("users"))
async def cmd_users(message: Message, session: AsyncSession, **kwargs) -> None:
    users = await User.get_all(session)
    lines = [f"<b>👥 کاربران ({to_persian_digits(len(users))} نفر)</b>\n"]
    for u in users[:20]:
        lines.append(f"• {u.full_name} (@{u.username or '—'}) — ID: <code>{u.tg_id}</code> — موجودی: {format_toman(u.balance)} تومان")
    if len(users) > 20:
        lines.append(f"\n... و {to_persian_digits(len(users)-20)} کاربر دیگر")
    await message.answer("\n".join(lines))


@router.message(IsAdmin(), Command("addbalance"))
async def cmd_addbalance(message: Message, session: AsyncSession, **kwargs) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("استفاده: /addbalance {user_id} {amount}")
        return
    try:
        target_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("آیدی و مبلغ باید عدد باشند.")
        return
    from app.bot.services.wallet import credit
    from app.db.models.transaction import TX_ADMIN_CREDIT
    try:
        await credit(session, target_id, amount, f"شارژ توسط مدیر", tx_type=TX_ADMIN_CREDIT)
        target = await User.get(session, target_id)
        bal = target.balance if target else amount
        await message.answer(f"✅ موجودی کاربر {target_id} به اندازه {format_toman(amount)} تومان شارژ شد.\nموجودی فعلی: {format_toman(bal)} تومان")
        try:
            await message.bot.send_message(
                target_id,
                fa.WALLET_CHARGED.format(balance=format_toman(bal)),
                parse_mode="HTML",
            )
        except Exception:
            pass
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")


@router.message(IsAdmin(), Command("ban"))
async def cmd_ban(message: Message, session: AsyncSession, **kwargs) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("استفاده: /ban {user_id}")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("آیدی باید عدد باشد.")
        return
    await User.update(session, target_id, is_banned=True)
    await message.answer(f"🚫 کاربر {target_id} مسدود شد.")


@router.message(IsAdmin(), Command("unban"))
async def cmd_unban(message: Message, session: AsyncSession, **kwargs) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("استفاده: /unban {user_id}")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("آیدی باید عدد باشد.")
        return
    await User.update(session, target_id, is_banned=False)
    await message.answer(f"✅ کاربر {target_id} رفع مسدودیت شد.")


@router.message(IsAdmin(), Command("makeagent"))
async def cmd_makeagent(message: Message, session: AsyncSession, **kwargs) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("استفاده: /makeagent {user_id} {credit_gb}")
        return
    try:
        target_id = int(parts[1])
        credit_gb = int(parts[2])
    except ValueError:
        await message.answer("آیدی و اعتبار باید عدد باشند.")
        return
    await User.update(session, target_id, is_agent=True, agent_credit_gb=credit_gb)
    await message.answer(f"✅ کاربر {target_id} نماینده شد. اعتبار: {credit_gb} گیگابایت")
    try:
        await message.bot.send_message(
            target_id,
            fa.AGENCY_APPROVED_USER,
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(IsAdmin(), Command("broadcast"))
async def cmd_broadcast_prompt(message: Message, session: AsyncSession, **kwargs) -> None:
    await message.answer(
        "📢 <b>ارسال همگانی</b>\n\nپیام مورد نظر را در قالب ریپلای ارسال کنید.\n\nمثال:\n/broadcast_send پیام شما اینجا"
    )


@router.message(IsAdmin(), Command("broadcast_send"))
async def cmd_broadcast_send(message: Message, session: AsyncSession, **kwargs) -> None:
    text = (message.text or "").split(" ", 1)
    if len(text) < 2 or not text[1].strip():
        await message.answer("متن پیام خالی است.")
        return
    broadcast_text = text[1].strip()
    users = await User.get_all(session)
    sent = 0
    failed = 0
    import asyncio
    status_msg = await message.answer(f"⏳ در حال ارسال به {to_persian_digits(len(users))} کاربر...")
    for u in users:
        try:
            await message.bot.send_message(u.tg_id, broadcast_text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.04)  # ~25 msg/sec
    await status_msg.edit_text(
        f"✅ ارسال همگانی کامل شد.\n"
        f"• موفق: {to_persian_digits(sent)}\n"
        f"• ناموفق: {to_persian_digits(failed)}"
    )


# ── Admin callback panels ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:pending_txs")
async def cb_pending_txs(callback: CallbackQuery, user: User, session: AsyncSession, **kwargs) -> None:
    config_obj = kwargs.get("config")
    admin_ids = config_obj.bot.ADMINS if config_obj else []
    if user.tg_id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return
    txs = await Transaction.get_pending(session)
    if not txs:
        await callback.answer("هیچ تراکنش معلقی وجود ندارد.", show_alert=True)
        return
    lines = [f"💳 <b>تراکنش‌های معلق ({to_persian_digits(len(txs))})</b>\n"]
    for tx in txs[:10]:
        lines.append(
            f"• #{tx.id} — کاربر {tx.user_id} — {format_toman(tx.amount)} تومان — {tx.type}\n"
            f"  /approve_{tx.id} | /reject_{tx.id}"
        )
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:pending_agency")
async def cb_pending_agency(callback: CallbackQuery, user: User, session: AsyncSession, **kwargs) -> None:
    config_obj = kwargs.get("config")
    admin_ids = config_obj.bot.ADMINS if config_obj else []
    if user.tg_id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return
    reqs = await AgencyRequest.get_pending(session)
    if not reqs:
        await callback.answer("هیچ درخواست نمایندگی معلقی وجود ندارد.", show_alert=True)
        return
    lines = [f"📨 <b>درخواست‌های نمایندگی ({to_persian_digits(len(reqs))})</b>\n"]
    for req in reqs[:10]:
        lines.append(f"• #{req.id} — کاربر {req.user_id}\n  {req.message[:80]}...")
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:users:"))
async def cb_users_list(callback: CallbackQuery, user: User, session: AsyncSession, **kwargs) -> None:
    config_obj = kwargs.get("config")
    admin_ids = config_obj.bot.ADMINS if config_obj else []
    if user.tg_id not in admin_ids:
        await callback.answer(fa.ERRORS["admin_only"], show_alert=True)
        return

    page = int(callback.data.split(":")[-1])
    per_page = 10
    all_users = await User.get_all(session)
    start = page * per_page
    page_users = all_users[start:start + per_page]

    lines = [f"👥 <b>کاربران (صفحه {to_persian_digits(page+1)})</b>\n"]
    for u in page_users:
        lines.append(f"• <code>{u.tg_id}</code> — {u.full_name} (@{u.username or '—'}) — {format_toman(u.balance)} تومان")

    builder = InlineKeyboardBuilder()
    if start > 0:
        builder.button(text="◀️ قبل", callback_data=f"admin:users:{page-1}")
    if start + per_page < len(all_users):
        builder.button(text="بعد ▶️", callback_data=f"admin:users:{page+1}")
    builder.button(text=fa.BACK, callback_data="admin:dashboard")
    builder.adjust(2, 1)

    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()
