"""
Manage configs (screenshots 9–10).

- List screen: button per config (label = service_name).
- Detail screen: text card + 2-column action keyboard
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
from app.bot.utils.keyboards import K
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.renewal_settings import renewal_settings_for_config
from app.bot.services.vpn import VPNService
from app.bot.services.xui_api import XUIError
from app.bot.utils.emoji import plain_alert_text
from app.bot.utils.jalali import (
    delayed_start_days,
    is_delayed_start,
    to_jalali,
)
from app.bot.utils.messaging import edit_or_answer_callback
from app.bot.utils.persian import format_toman, to_persian_digits
from app.bot.utils.progress import format_gb, traffic_bar
from app.bot.utils.qr import make_qr_png
from app.db.models import User, VPNConfig

logger = logging.getLogger(__name__)

router = Router(name="my_services")


async def _alert(callback: CallbackQuery, text: str) -> None:
    """Popup alert — plain text only (Telegram rejects HTML in show_alert)."""
    await callback.answer(plain_alert_text(text), show_alert=True)


# ── list ─────────────────────────────────────────────────────────────────────

def _list_keyboard(configs: list[VPNConfig]) -> InlineKeyboardMarkup:
    kb = K()
    for cfg in configs:
        label = (fa.CONFIG_LIST_ROW if cfg.is_active else fa.CONFIG_LIST_ROW_EXPIRED).format(
            name=cfg.service_name
        )
        kb.btn(label, callback_data=f"cfg:open:{cfg.id}", icon="server")
    return kb.back_to_menu().adjust(1).as_markup()


async def show_configs_list(
    target: CallbackQuery | Message, user: User, session: AsyncSession, **kwargs
) -> None:
    configs = await VPNConfig.get_for_user(session, user.tg_id)
    empty_markup = (
        K()
        .primary(fa.MAIN_BTN_BUY, callback_data="menu:buy", icon="btn_buy")
        .back_to_menu()
        .adjust(1)
        .as_markup()
    )
    if not configs:
        if isinstance(target, CallbackQuery):
            await edit_or_answer_callback(
                target, fa.CONFIGS_LIST_EMPTY, reply_markup=empty_markup
            )
            await target.answer()
        else:
            await target.answer(fa.CONFIGS_LIST_EMPTY, reply_markup=empty_markup)
        return

    text = fa.CONFIGS_LIST_HEADER.format(count=to_persian_digits(len(configs)))
    markup = _list_keyboard(configs)
    if isinstance(target, CallbackQuery):
        await edit_or_answer_callback(target, text, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup)


# ── detail ───────────────────────────────────────────────────────────────────

def _sub_qr_keyboard(sub_url: str, cid: int) -> InlineKeyboardMarkup:
    return (
        K()
        .primary(fa.CONFIG_BTN_COPY_SUB, copy_text=sub_url, icon="copy")
        .btn(fa.SERVICE_ACTIVATED_OPEN_BTN, url=sub_url, icon="link")
        .nav(f"cfg:open:{cid}")
        .adjust(2, 2)
        .as_markup()
    )


def _detail_keyboard(config_id: int, is_active: bool, *, renew_label: str) -> InlineKeyboardMarkup:
    cid = config_id
    kb = K()
    kb.primary(renew_label, callback_data=f"renew:start:{cid}", icon="refresh")
    kb.btn(fa.CONFIG_BTN_SUB_QR, callback_data=f"cfg:subqr:{cid}", icon="link")
    kb.btn(fa.CONFIG_BTN_GET_CONFIGS, callback_data=f"cfg:links:{cid}", icon="download")
    toggle_text = fa.CONFIG_BTN_DISABLE if is_active else fa.CONFIG_BTN_ENABLE
    toggle_cb = f"cfg:toggle:{cid}" if is_active else f"cfg:enable:{cid}"
    toggle_icon = "pause" if is_active else "play"
    kb.btn(toggle_text, callback_data=toggle_cb, icon=toggle_icon)
    kb.btn(fa.CONFIG_BTN_RESET_SUB, callback_data=f"cfg:resetsub:{cid}", icon="refresh")
    kb.danger(fa.CONFIG_BTN_DELETE, callback_data=f"cfg:delete:{cid}", icon="trash")
    return kb.nav("menu:configs").adjust(2, 2, 2, 2).as_markup()


def _expiry_text(cfg: VPNConfig, panel_expiry_ms: int | None) -> str:
    if panel_expiry_ms is not None and is_delayed_start(panel_expiry_ms):
        return fa.DELAYED_START_FMT.format(n=to_persian_digits(delayed_start_days(panel_expiry_ms)))
    if cfg.expiry_date is None:
        return fa.CONFIG_NOT_STARTED
    return to_jalali(cfg.expiry_date)


def _days_left_text(cfg: VPNConfig, panel_expiry_ms: int | None) -> str:
    if panel_expiry_ms and is_delayed_start(panel_expiry_ms):
        return to_persian_digits(delayed_start_days(panel_expiry_ms))
    if cfg.expiry_date and panel_expiry_ms != 0:
        from app.bot.utils.jalali import days_until

        try:
            d = days_until(cfg.expiry_date)
            return to_persian_digits(max(0, d))
        except Exception:
            pass
    return "—"


async def _load_panel_traffic(
    vpn: VPNService | None, cfg: VPNConfig, session: AsyncSession
) -> int | None:
    panel_expiry_ms: int | None = None
    if vpn:
        try:
            traffic = await vpn.xui.get_client_traffic(cfg.panel_email)
            panel_expiry_ms = traffic.expiry_time
            await vpn.refresh_traffic(session, cfg)
        except XUIError:
            pass
    return panel_expiry_ms


async def _detail_text(
    vpn: VPNService | None, cfg: VPNConfig, session: AsyncSession
) -> str:
    panel_expiry_ms = await _load_panel_traffic(vpn, cfg, session)
    expiry = _expiry_text(cfg, panel_expiry_ms)
    days_left = _days_left_text(cfg, panel_expiry_ms)
    return fa.CONFIG_DETAIL.format(
        name=cfg.service_name,
        plan_name="VIP",
        bar=traffic_bar(cfg.traffic_used_bytes, cfg.traffic_limit_bytes),
        used_gb=to_persian_digits(format_gb(cfg.traffic_used_bytes)),
        total_gb=to_persian_digits(cfg.plan_gb),
        pct=to_persian_digits(int(cfg.usage_percent)),
        expiry=expiry,
        days=days_left,
    )


def _sub_url(vpn: VPNService | None, cfg: VPNConfig) -> str:
    if vpn:
        return vpn.sub_url(cfg.subscription_id)
    from app.bot.utils.sub_url import normalize_subscription_url

    return normalize_subscription_url(cfg.subscription_url)


async def _send_detail(
    target: Message | CallbackQuery,
    cfg: VPNConfig,
    vpn: VPNService | None,
    session: AsyncSession,
    *,
    edit: bool = True,
    bot_config=None,
) -> None:
    discount_pct = renewal_settings_for_config(bot_config).discount_percent
    renew_label = fa.CONFIG_BTN_RENEW.format(
        discount_pct=to_persian_digits(discount_pct),
    )
    text = await _detail_text(vpn, cfg, session)
    markup = _detail_keyboard(cfg.id, cfg.is_active, renew_label=renew_label)
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
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    await _send_detail(callback, cfg, vpn, session, edit=True, bot_config=kwargs.get("config"))


# ── subscription + QR (merged) ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:subqr:"))
async def cb_sub_qr(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    sub_url = _sub_url(vpn, cfg)
    text = fa.CONFIG_SUB_QR_TEXT.format(name=cfg.service_name, url=sub_url)
    await callback.message.edit_text(
        text,
        reply_markup=_sub_qr_keyboard(sub_url, cid),
        disable_web_page_preview=True,
    )
    qr = make_qr_png(sub_url)
    photo = BufferedInputFile(qr.getvalue(), filename="qr.png")
    await callback.message.answer_photo(
        photo=photo,
        caption=fa.CONFIG_QR_CAPTION.format(name=cfg.service_name),
        parse_mode="HTML",
        reply_markup=K().nav(f"cfg:open:{cid}").adjust(2).as_markup(),
    )
    await callback.answer()


# ── get configs (VLESS links) ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:links:"))
async def cb_links(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await _alert(callback, fa.ERRORS["api_error"])
        return
    try:
        all_links = await vpn.fetch_all_links(cfg)
    except XUIError:
        await _alert(callback, fa.ERRORS["api_error"])
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
    await callback.message.edit_text(
        text,
        reply_markup=K().nav(f"cfg:open:{cid}").adjust(2).as_markup(),
        disable_web_page_preview=True,
    )
    await callback.answer()


# ── toggle enable/disable ────────────────────────────────────────────────────

async def _apply_toggle(
    callback: CallbackQuery,
    cfg: VPNConfig,
    vpn: VPNService,
    session: AsyncSession,
    new_state: bool,
    **kwargs,
) -> None:
    try:
        await vpn.set_enabled(session, cfg, new_state)
    except XUIError:
        await _alert(callback, fa.ERRORS["api_error"])
        return
    cfg.is_active = new_state
    await _alert(
        callback,
        fa.CONFIG_ENABLED if new_state else fa.CONFIG_DISABLED,
    )
    await _send_detail(
        callback, cfg, vpn, session, edit=True, bot_config=kwargs.get("config")
    )


@router.callback_query(F.data.startswith("cfg:toggle:"))
async def cb_toggle_prompt(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    await callback.message.edit_text(
        fa.CONFIG_DISABLE_CONFIRM.format(name=cfg.service_name),
        reply_markup=(
            K()
            .danger(fa.CONFIG_DISABLE_YES, callback_data=f"cfg:disableyes:{cid}", icon="confirm")
            .btn(fa.CONFIG_DISABLE_NO, callback_data=f"cfg:open:{cid}", icon="reject")
            .adjust(2)
            .as_markup()
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cfg:disableyes:"))
async def cb_disable_yes(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await _alert(callback, fa.ERRORS["api_error"])
        return
    await _apply_toggle(callback, cfg, vpn, session, False, **kwargs)


@router.callback_query(F.data.startswith("cfg:enable:"))
async def cb_enable(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await _alert(callback, fa.ERRORS["api_error"])
        return
    await _apply_toggle(callback, cfg, vpn, session, True, **kwargs)


# ── reset subscription ───────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^cfg:resetsub:\d+$"))
async def cb_reset_sub_prompt(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    await callback.message.edit_text(
        fa.CONFIG_RESET_SUB_CONFIRM.format(name=cfg.service_name),
        reply_markup=(
            K()
            .danger(fa.CONFIG_RESET_SUB_YES, callback_data=f"cfg:resetsubyes:{cid}", icon="confirm")
            .btn(fa.CONFIG_RESET_SUB_NO, callback_data=f"cfg:open:{cid}", icon="reject")
            .adjust(2)
            .as_markup()
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cfg:resetsubyes:"))
async def cb_reset_sub_yes(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    if vpn is None:
        await _alert(callback, fa.ERRORS["api_error"])
        return
    try:
        cfg = await vpn.reset_sub(session, cfg)
    except XUIError:
        await _alert(callback, fa.ERRORS["api_error"])
        return
    sub_url = _sub_url(vpn, cfg)
    await callback.message.answer(
        fa.CONFIG_RESET_SUB_DONE.format(url=sub_url),
        parse_mode="HTML",
        reply_markup=_sub_qr_keyboard(sub_url, cid),
        disable_web_page_preview=True,
    )
    await callback.answer()
    await _send_detail(callback, cfg, vpn, session, edit=True, bot_config=kwargs.get("config"))


# ── delete ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg:delete:"))
async def cb_delete_prompt(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    await callback.message.edit_text(
        fa.CONFIG_DELETE_CONFIRM.format(name=cfg.service_name),
        reply_markup=(
            K()
            .danger(fa.CONFIG_DELETE_YES, callback_data=f"cfg:delyes:{cid}", icon="confirm")
            .btn(fa.CONFIG_DELETE_NO, callback_data=f"cfg:open:{cid}", icon="reject")
            .adjust(2)
            .as_markup()
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cfg:delyes:"))
async def cb_delete_yes(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    cid = int(callback.data.rsplit(":", 1)[-1])
    cfg = await VPNConfig.get(session, cid)
    if not cfg or cfg.user_id != user.tg_id:
        await _alert(callback, fa.ERRORS["config_not_found"])
        return
    vpn: VPNService | None = kwargs.get("vpn_service")
    name = cfg.service_name
    if not vpn:
        await _alert(callback, fa.ERRORS["vpn_unavailable"])
        return
    try:
        await vpn.delete(session, cfg)
    except XUIError:
        await _alert(callback, fa.ERRORS["api_error"])
        return
    await _alert(callback, fa.CONFIG_DELETED.format(name=name))
    await show_configs_list(callback, user, session, **kwargs)
