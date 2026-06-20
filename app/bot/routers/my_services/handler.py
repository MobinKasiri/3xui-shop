"""
Manage configs (screenshots 9–10).

- List screen: button per config (label = service_name).
- Detail screen: text card + QR + 6-row action keyboard:
    status / get configs / get sub / toggle / delete / reset sub / QR sub
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.vpn import VPNService
from app.bot.services.xui_api import XUIError
from app.bot.utils.jalali import (
    delayed_start_days,
    is_delayed_start,
    to_jalali,
)
from app.bot.utils.persian import format_toman, to_persian_digits
from app.bot.utils.progress import format_gb, traffic_bar
from app.bot.utils.qr import make_qr_png
from app.db.models import User, VPNConfig

logger = logging.getLogger(__name__)

router = Router(name="my_services")


# ── list ─────────────────────────────────────────────────────────────────────

def _list_keyboard(configs: list[VPNConfig]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cfg in configs:
        label = (fa.CONFIG_LIST_ROW if cfg.is_active else fa.CONFIG_LIST_ROW_EXPIRED).format(
            name=cfg.service_name
        )
        builder.button(text=label, callback_data=f"cfg:open:{cfg.id}")
    builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


async def show_configs_list(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    configs = await VPNConfig.get_for_user(session, user.tg_id)
    if not configs:
        builder = InlineKeyboardBuilder()
        builder.button(text=fa.MAIN_BTN_BUY, callback_data="menu:buy")
        builder.button(text=fa.BACK_TO_MENU, callback_data="main_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            fa.CONFIGS_LIST_EMPTY, reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    text = fa.CONFIGS_LIST_HEADER.format(count=to_persian_digits(len(configs)))
    await callback.message.edit_text(text, reply_markup=_list_keyboard(configs))
    await callback.answer()


# ── detail ───────────────────────────────────────────────────────────────────

def _detail_keyboard(config_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.CONFIG_BTN_USAGE, callback_data=f"cfg:status:{config_id}")
    builder.button(text=fa.CONFIG_BTN_GET_CONFIGS, callback_data=f"cfg:links:{config_id}")
    builder.button(text=fa.CONFIG_BTN_GET_SUB, callback_data=f"cfg:sub:{config_id}")
    toggle_text = fa.CONFIG_BTN_DISABLE if is_active else fa.CONFIG_BTN_ENABLE
    builder.button(text=toggle_text, callback_data=f"cfg:toggle:{config_id}")
    builder.button(text=fa.CONFIG_BTN_RESET_SUB, callback_data=f"cfg:resetsub:{config_id}")
    builder.button(text=fa.CONFIG_BTN_QR, callback_data=f"cfg:qr:{config_id}")
    builder.button(text=fa.CONFIG_BTN_DELETE, callback_data=f"cfg:delete:{config_id}")
    builder.button(text=fa.BACK, callback_data="menu:configs")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(1, 1, 1, 1, 1, 1, 1, 2)
    return builder.as_markup()


def _expiry_text(cfg: VPNConfig, panel_expiry_ms: int | None) -> str:
    if panel_expiry_ms is not None and is_delayed_start(panel_expiry_ms):
        return fa.DELAYED_START_FMT.format(n=to_persian_digits(delayed_start_days(panel_expiry_ms)))
    if cfg.expiry_date is None:
        return fa.CONFIG_NOT_STARTED
    return to_jalali(cfg.expiry_date)


def _duration_text(cfg: VPNConfig) -> str:
    return f"{to_persian_digits(cfg.plan_days)} روز"


async def _detail_text(
    vpn: VPNService | None, cfg: VPNConfig
) -> tuple[str, int | None, str, str]:
    """Return (text, panel_expiry_ms, ws_link, reality_link)."""
    panel_expiry_ms: int | None = None
    ws_link = reality_link = ""
    if vpn:
        try:
            traffic = await vpn.xui.get_client_traffic(cfg.panel_email)
            panel_expiry_ms = traffic.expiry_time
        except XUIError:
            pass
        try:
            ws_link, reality_link = await vpn.fetch_links(cfg)
        except XUIError:
            pass

    vless = ws_link or reality_link or "—"
    text = fa.CONFIG_DETAIL.format(
        name=cfg.service_name,
        plan_name="VIP",
        total_gb=to_persian_digits(cfg.plan_gb),
        duration=_duration_text(cfg),
        vless=vless,
        sub_url=cfg.subscription_url,
    )
    return text, panel_expiry_ms, ws_link, reality_link


async def _send_detail(
    target: Message | CallbackQuery,
    cfg: VPNConfig,
    vpn: VPNService | None,
    *,
    edit: bool = True,
) -> None:
    text, _, _, _ = await _detail_text(vpn, cfg)
    markup = _detail_keyboard(cfg.id, cfg.is_active)
    msg = target.message if isinstance(target, CallbackQuery) else target
    try:
        if edit:
            await msg.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        else:
            await msg.answer(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        await msg.answer(text, reply_markup=markup, disable_web_page_preview=True)
    if isinstance(target, CallbackQuery):
        await target.answer()


@router.callback_query(F.data.startswith("cfg:open:"))
async def cb_open_config(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    await _send_detail(callback, cfg, vpn, edit=True)


# ── status (usage + traffic) ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:status:"))
async def cb_status(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    vpn: VPNService | None = kwargs.get("vpn_service")

    up = down = 0
    panel_expiry_ms = None
    if vpn:
        try:
            traffic = await vpn.xui.get_client_traffic(cfg.panel_email)
            up = traffic.up
            down = traffic.down
            panel_expiry_ms = traffic.expiry_time
            await vpn.refresh_traffic(session, cfg)
        except XUIError:
            pass

    expiry = _expiry_text(cfg, panel_expiry_ms)
    days_left: str = "—"
    if cfg.expiry_date and panel_expiry_ms != 0 and not (panel_expiry_ms and is_delayed_start(panel_expiry_ms)):
        from app.bot.utils.jalali import days_until
        try:
            d = days_until(cfg.expiry_date)
            days_left = to_persian_digits(max(0, d))
        except Exception:
            pass
    if panel_expiry_ms and is_delayed_start(panel_expiry_ms):
        days_left = to_persian_digits(delayed_start_days(panel_expiry_ms))

    text = fa.CONFIG_STATUS_TEXT.format(
        name=cfg.service_name,
        bar=traffic_bar(cfg.traffic_used_bytes, cfg.traffic_limit_bytes),
        used_gb=to_persian_digits(format_gb(cfg.traffic_used_bytes)),
        total_gb=to_persian_digits(cfg.plan_gb),
        pct=to_persian_digits(int(cfg.usage_percent)),
        expiry=expiry,
        days=days_left,
        up=to_persian_digits(format_gb(up)) + " GB",
        down=to_persian_digits(format_gb(down)) + " GB",
    )
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.BACK, callback_data=f"cfg:open:{cid}")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(2)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ── get configs (VLESS links) ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:links:"))
async def cb_links(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return
    try:
        all_links = await vpn.fetch_all_links(cfg)
    except XUIError:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return

    if all_links:
        lines = []
        for i, link in enumerate(all_links, 1):
            lines.append(f"{to_persian_digits(i)}. <code>{link}</code>")
        links_block = "\n\n".join(lines)
    else:
        links_block = fa.CONFIG_GET_CONFIGS_EMPTY

    text = fa.CONFIG_GET_CONFIGS_TEXT.format(
        name=cfg.service_name,
        links=links_block,
    )
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.BACK, callback_data=f"cfg:open:{cid}")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(2)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    await callback.answer()


# ── get sub ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:sub:"))
async def cb_sub(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    text = fa.CONFIG_GET_SUB_TEXT.format(name=cfg.service_name, url=cfg.subscription_url)
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.BACK, callback_data=f"cfg:open:{cid}")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(2)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    await callback.answer()


# ── toggle enable/disable ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:toggle:"))
async def cb_toggle(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return
    new_state = not cfg.is_active
    try:
        await vpn.set_enabled(session, cfg, new_state)
    except XUIError:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return
    cfg.is_active = new_state
    await callback.answer(
        fa.CONFIG_ENABLED if new_state else fa.CONFIG_DISABLED, show_alert=True
    )
    await _send_detail(callback, cfg, vpn, edit=True)


# ── reset subscription ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:resetsub:"))
async def cb_reset_sub(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return
    try:
        cfg = await vpn.reset_sub(session, cfg)
    except XUIError:
        await callback.answer(fa.ERRORS["api_error"], show_alert=True)
        return
    await callback.answer(
        fa.CONFIG_RESET_SUB_DONE.format(url=cfg.subscription_url), show_alert=True
    )
    await _send_detail(callback, cfg, vpn, edit=True)


# ── QR ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:qr:"))
async def cb_qr(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    qr = make_qr_png(cfg.subscription_url)
    photo = BufferedInputFile(qr.getvalue(), filename="qr.png")
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.BACK, callback_data=f"cfg:open:{cid}")
    builder.button(text=fa.HOME, callback_data="main_menu")
    builder.adjust(2)
    await callback.message.answer_photo(
        photo=photo,
        caption=fa.CONFIG_QR_CAPTION.format(name=cfg.service_name),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


# ── delete ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:delete:"))
async def cb_delete_prompt(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    builder.button(text=fa.CONFIG_DELETE_YES, callback_data=f"cfg:delyes:{cid}")
    builder.button(text=fa.CONFIG_DELETE_NO, callback_data=f"cfg:open:{cid}")
    builder.adjust(2)
    await callback.message.edit_text(
        fa.CONFIG_DELETE_CONFIRM.format(name=cfg.service_name),
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cfg:delyes:"))
async def cb_delete_yes(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await callback.answer(fa.ERRORS["config_not_found"], show_alert=True)
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    name = cfg.service_name
    if vpn:
        try:
            await vpn.delete(session, cfg)
        except XUIError:
            await callback.answer(fa.ERRORS["api_error"], show_alert=True)
            return
    else:
        await VPNConfig.delete(session, cfg.id)
    await callback.answer(fa.CONFIG_DELETED.format(name=name), show_alert=True)
    await show_configs_list(callback, user, session, **kwargs)
