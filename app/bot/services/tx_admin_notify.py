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


def _action_label(action: Action, *, wallet: bool) -> tuple[str, str]:
    if action == "approved":
        return ("✅", "شارژ تایید شد" if wallet else "تایید و فعال‌سازی شد")
    return ("❌", "رد شد")


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
    icon, action_label = _action_label(action, wallet=wallet)

    actor = AdminActor(
        tg_id=int(processed.get("by_tg_id") or 0),
        name=str(processed.get("by_name") or "—"),
        username=processed.get("by_username"),
    )
    processed_at = _processed_at_text(processed.get("at"))

    if is_super_admin(viewer_chat_id, config):
        base = (
            _build_pending_wallet_caption(payload)
            if wallet
            else _build_pending_purchase_caption(payload)
        )
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
    messages = [{"chat_id": chat_id, "message_id": msg.message_id} for chat_id, msg in sent]
    await save_notify_meta(session, tx_id, kind=kind, payload=payload, messages=messages)
