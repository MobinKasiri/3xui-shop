"""Sync payment-request messages across all bot admins after approve/reject."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.utils.plan_labels import DEFAULT_TIER_DISPLAY_NAME
from app.bot.utils.jalali import to_jalali_full
from app.bot.utils.persian import format_toman, to_persian_digits
from app.db.models.transaction import Transaction

logger = logging.getLogger(__name__)

Action = Literal["approved", "rejected"]


@dataclass
class AdminActor:
    tg_id: int
    name: str
    username: str | None = None

    @property
    def ref(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.name or "—"


def admin_chat_ids(config) -> list[int]:
    ids = list(config.bot.ADMINS) if config and config.bot.ADMINS else []
    if config and config.payment.ADMIN_CHAT_ID and config.payment.ADMIN_CHAT_ID not in ids:
        ids.append(config.payment.ADMIN_CHAT_ID)
    return ids


def is_super_admin(tg_id: int, config) -> bool:
    dev_id = getattr(config.bot, "DEV_ID", 0) if config else 0
    return bool(dev_id) and tg_id == dev_id


def actor_from_callback(callback: CallbackQuery) -> AdminActor:
    user = callback.from_user
    name = " ".join(p for p in (user.first_name, user.last_name) if p).strip() or "—"
    return AdminActor(tg_id=user.id, name=name, username=user.username)


def load_meta(tx: Transaction | None) -> dict[str, Any]:
    if not tx or not tx.bot_admin_notify:
        return {}
    try:
        data = json.loads(tx.bot_admin_notify)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


async def save_notify_meta(
    session: AsyncSession,
    tx_id: int,
    *,
    kind: str,
    payload: dict[str, Any],
    messages: list[dict[str, int]],
) -> None:
    meta = {"kind": kind, "payload": payload, "messages": messages}
    await Transaction.update(
        session,
        tx_id,
        bot_admin_notify=json.dumps(meta, ensure_ascii=False),
    )


from app.bot.utils.emoji import i


def _action_label(action: Action, *, wallet: bool, kind: str = "purchase") -> tuple[str, str]:
    if action == "approved":
        icon = i("confirm")
        if wallet:
            return (icon, "شارژ تایید شد")
        if kind == "renew":
            return (icon, "تمدید تایید شد")
        return (icon, "تایید و فعال‌سازی شد")
    return (i("reject"), "رد شد")


def _build_pending_renew_caption(payload: dict[str, Any]) -> str:
    return fa.ADMIN_RENEW_FWD.format(
        tx_id=payload["tx_id"],
        name=payload["user_name"],
        username=payload.get("username") or "—",
        tg_id=payload["tg_id"],
        plan_name=payload.get("plan_name") or DEFAULT_TIER_DISPLAY_NAME,
        service_name=payload.get("service_name") or "—",
        amount=format_toman(int(payload["amount"])),
        discount=payload.get("discount") or "—",
        datetime=payload.get("datetime") or "—",
    )


def _build_pending_purchase_caption(payload: dict[str, Any]) -> str:
    discount_text = "—"
    if payload.get("discount_code"):
        discount_text = (
            f"{payload['discount_code']} "
            f"(-{format_toman(int(payload.get('discount_amount', 0)))} ت)"
        )
    return fa.ADMIN_PAYMENT_FWD.format(
        tx_id=payload["tx_id"],
        name=payload["user_name"],
        username=payload.get("username") or "—",
        tg_id=payload["tg_id"],
        plan_name=payload["plan_name"],
        quantity=to_persian_digits(int(payload.get("quantity", 1))),
        service_name=payload.get("service_name") or "—",
        amount=format_toman(int(payload["amount"])),
        discount=discount_text,
        datetime=payload.get("datetime") or "—",
    )


def _build_pending_wallet_caption(payload: dict[str, Any]) -> str:
    return fa.ADMIN_WALLET_FWD.format(
        tx_id=payload["tx_id"],
        name=payload["user_name"],
        username=payload.get("username") or "—",
        tg_id=payload["tg_id"],
        amount=format_toman(int(payload["amount"])),
        datetime=payload.get("datetime") or "—",
    )


def _processed_at_text(iso_value: str | None) -> str:
    if not iso_value:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return to_jalali_full(dt)
    except ValueError:
        return iso_value


def build_processed_caption(
    meta: dict[str, Any],
    *,
    viewer_chat_id: int,
    config,
    processed: dict[str, Any],
) -> str:
    kind = meta.get("kind", "purchase")
    wallet = kind == "wallet"
    payload = meta.get("payload") or {}
    action: Action = processed.get("action", "approved")
    icon, action_label = _action_label(action, wallet=wallet, kind=kind)

    actor = AdminActor(
        tg_id=int(processed.get("by_tg_id") or 0),
        name=str(processed.get("by_name") or "—"),
        username=processed.get("by_username"),
    )
    processed_at = _processed_at_text(processed.get("at"))

    if is_super_admin(viewer_chat_id, config):
        if wallet:
            base = _build_pending_wallet_caption(payload)
        elif kind == "renew":
            base = _build_pending_renew_caption(payload)
        else:
            base = _build_pending_purchase_caption(payload)
        return base + fa.ADMIN_TX_PROCESSED_SUPER_FOOTER.format(
            icon=icon,
            action_label=action_label,
            admin_name=actor.name,
            admin_ref=actor.ref,
            admin_tg_id=actor.tg_id,
            processed_at=processed_at,
        )

    return fa.ADMIN_TX_PROCESSED_SHORT.format(
        icon=icon,
        tx_id=payload.get("tx_id", "—"),
        action_label=action_label,
        admin_name=actor.name,
        admin_ref=actor.ref,
        processed_at=processed_at,
    )


async def _edit_admin_message(bot: Bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=None,
        )
        return
    except TelegramBadRequest:
        pass
    except Exception as exc:
        logger.debug("edit_message_caption failed chat=%s msg=%s: %s", chat_id, message_id, exc)

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception as exc:
        logger.warning(
            "Could not update admin tx message chat=%s msg=%s: %s",
            chat_id,
            message_id,
            exc,
        )


async def sync_processed_views(
    bot: Bot,
    session: AsyncSession,
    config,
    tx_id: int,
    *,
    actor: AdminActor,
    action: Action,
    processed_at: datetime | None = None,
) -> None:
    tx = await Transaction.get(session, tx_id)
    if not tx:
        return
    meta = load_meta(tx)
    if not meta.get("messages"):
        return

    at = (processed_at or datetime.now(tz=timezone.utc)).isoformat()
    meta["processed"] = {
        "by_tg_id": actor.tg_id,
        "by_name": actor.name,
        "by_username": actor.username,
        "action": action,
        "at": at,
    }
    await Transaction.update(
        session,
        tx_id,
        bot_admin_notify=json.dumps(meta, ensure_ascii=False),
    )

    processed = meta["processed"]
    for ref in meta["messages"]:
        chat_id = int(ref["chat_id"])
        message_id = int(ref["message_id"])
        caption = build_processed_caption(
            meta,
            viewer_chat_id=chat_id,
            config=config,
            processed=processed,
        )
        await _edit_admin_message(bot, chat_id, message_id, caption)


async def refresh_processed_views_if_done(
    bot: Bot,
    session: AsyncSession,
    config,
    tx_id: int,
) -> None:
    """Re-sync admin messages when someone clicks stale approve/reject buttons."""
    tx = await Transaction.get(session, tx_id)
    if not tx or tx.status == "pending":
        return
    meta = load_meta(tx)
    if not meta.get("messages"):
        return

    if not meta.get("processed"):
        action: Action = "approved" if tx.status == "confirmed" else "rejected"
        at = tx.confirmed_at or tx.created_at
        meta["processed"] = {
            "by_tg_id": 0,
            "by_name": "—",
            "by_username": None,
            "action": action,
            "at": (at or datetime.now(tz=timezone.utc)).isoformat(),
        }

    processed = meta["processed"]
    for ref in meta["messages"]:
        chat_id = int(ref["chat_id"])
        message_id = int(ref["message_id"])
        caption = build_processed_caption(
            meta,
            viewer_chat_id=chat_id,
            config=config,
            processed=processed,
        )
        await _edit_admin_message(bot, chat_id, message_id, caption)


async def record_forward_messages(
    session: AsyncSession,
    *,
    tx_id: int,
    kind: str,
    payload: dict[str, Any],
    sent: list[tuple[int, Message]],
) -> None:
    if not sent:
        return
    messages = [{"chat_id": chat_id, "message_id": msg.message_id} for chat_id, msg in sent]
    await save_notify_meta(session, tx_id, kind=kind, payload=payload, messages=messages)


async def _fallback_text_notify(
    bot: Bot,
    admin_ids: list[int],
    *,
    tx_id: int,
    kind: str,
    receipt_photo: str | None,
    payload: dict[str, Any],
) -> list[tuple[int, Message]]:
    """Full-detail fallback when primary photo/HTML notify fails for an admin."""
    from app.bot.services.notifications import _approve_reject_keyboard

    if kind == "wallet":
        text = fa.ADMIN_WALLET_FWD.format(
            tx_id=tx_id,
            name=payload.get("user_name"),
            username=payload.get("username") or "—",
            tg_id=payload.get("tg_id"),
            amount=format_toman(int(payload.get("amount", 0))),
            datetime=payload.get("datetime") or "—",
        )
        approve_cb = f"admin:approve_wallet:{tx_id}"
        reject_cb = f"admin:reject_wallet:{tx_id}"
        wallet = True
        approve_label = None
    elif kind == "renew":
        text = fa.ADMIN_RENEW_FWD.format(
            tx_id=tx_id,
            name=payload.get("user_name"),
            username=payload.get("username") or "—",
            tg_id=payload.get("tg_id"),
            plan_name=payload.get("plan_name") or DEFAULT_TIER_DISPLAY_NAME,
            service_name=payload.get("service_name") or "—",
            amount=format_toman(int(payload.get("amount", 0))),
            discount=payload.get("discount") or "—",
            datetime=payload.get("datetime") or "—",
        )
        approve_cb = f"admin:approve_renew:{tx_id}"
        reject_cb = f"admin:reject_renew:{tx_id}"
        wallet = False
        approve_label = fa.ADMIN_APPROVE_RENEW_BTN
    else:
        discount_text = "—"
        if payload.get("discount_code"):
            discount_text = (
                f"{payload['discount_code']} "
                f"(-{format_toman(int(payload.get('discount_amount', 0)))} ت)"
            )
        text = fa.ADMIN_PAYMENT_FWD.format(
            tx_id=tx_id,
            name=payload.get("user_name"),
            username=payload.get("username") or "—",
            tg_id=payload.get("tg_id"),
            plan_name=payload.get("plan_name"),
            quantity=to_persian_digits(int(payload.get("quantity", 1))),
            service_name=payload.get("service_name") or "—",
            amount=format_toman(int(payload.get("amount", 0))),
            discount=discount_text,
            datetime=payload.get("datetime") or "—",
        )
        approve_cb = f"admin:approve_purchase:{tx_id}"
        reject_cb = f"admin:reject_purchase:{tx_id}"
        wallet = False
        approve_label = None

    markup = _approve_reject_keyboard(
        approve_cb, reject_cb, wallet=wallet, approve_label=approve_label
    )
    sent: list[tuple[int, Message]] = []
    for chat_id in admin_ids:
        try:
            if receipt_photo:
                msg = await bot.send_photo(
                    chat_id,
                    photo=receipt_photo,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=markup,
                )
            else:
                msg = await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            sent.append((chat_id, msg))
        except Exception as exc:
            logger.error("Fallback admin notify failed chat=%s tx=%s: %s", chat_id, tx_id, exc)
    return sent


def _forward_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs = dict(payload)
    if "datetime" in kwargs:
        kwargs["datetime_str"] = kwargs.pop("datetime")
    return kwargs


async def dispatch_tx_to_admins(
    bot: Bot,
    session: AsyncSession,
    config,
    *,
    kind: Literal["purchase", "wallet", "renew"],
    tx_id: int,
    receipt_photo: str | None,
    payload: dict[str, Any],
) -> None:
    """Forward new card-payment request to every admin; store message ids for later sync."""
    from app.bot.services.notifications import (
        forward_purchase_to_all_admins,
        forward_renew_to_all_admins,
        forward_wallet_topup_to_all_admins,
    )

    admin_ids = admin_chat_ids(config)
    if not admin_ids:
        logger.error(
            "TX %s: no admin chat ids (set BOT_ADMINS and/or ADMIN_CHAT_ID in .env)",
            tx_id,
        )
        return

    payload = {**payload, "tx_id": tx_id}
    logger.info("TX %s: notifying admins %s (kind=%s)", tx_id, admin_ids, kind)

    forward_kwargs = _forward_kwargs(payload)
    if kind == "wallet":
        sent = await forward_wallet_topup_to_all_admins(
            bot,
            admin_chat_ids=admin_ids,
            receipt_photo=receipt_photo,
            **forward_kwargs,
        )
    elif kind == "renew":
        sent = await forward_renew_to_all_admins(
            bot,
            admin_chat_ids=admin_ids,
            receipt_photo=receipt_photo,
            **forward_kwargs,
        )
    else:
        sent = await forward_purchase_to_all_admins(
            bot,
            admin_chat_ids=admin_ids,
            receipt_photo=receipt_photo,
            **forward_kwargs,
        )

    if not sent:
        logger.warning(
            "TX %s: primary admin notify failed for all %d admin(s) — trying fallback",
            tx_id,
            len(admin_ids),
        )
        sent = await _fallback_text_notify(
            bot,
            admin_ids,
            tx_id=tx_id,
            kind=kind,
            receipt_photo=receipt_photo,
            payload=payload,
        )

    if sent:
        logger.info("TX %s: notified %d/%d admin chat(s)", tx_id, len(sent), len(admin_ids))
    else:
        logger.error("TX %s: could not notify any admin", tx_id)

    try:
        await record_forward_messages(
            session,
            tx_id=tx_id,
            kind=kind,
            payload=payload,
            sent=sent,
        )
    except Exception:
        logger.exception(
            "TX %s: could not store admin message refs (notify already sent)", tx_id
        )
