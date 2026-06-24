"""Forward webhooks to main bot or deliver repair messages."""
from __future__ import annotations

import json
import logging
import os

import aiohttp
from aiogram import Bot
from aiogram.types import Update

from app.repair.message import (
    default_offline_message,
    is_planned_repair_active,
    load_state,
    planned_repair_message,
)

logger = logging.getLogger(__name__)

MAIN_BOT_WEBHOOK_URL = os.environ.get(
    "MAIN_BOT_WEBHOOK_URL", "http://bot:8090/webhook"
)
FORWARD_TIMEOUT_SEC = float(os.environ.get("REPAIR_FORWARD_TIMEOUT", "25"))


async def forward_to_main_bot(body: bytes, request_headers) -> tuple[int, bytes]:
    headers = {"Content-Type": "application/json"}
    secret = request_headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret

    timeout = aiohttp.ClientTimeout(total=FORWARD_TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(MAIN_BOT_WEBHOOK_URL, data=body, headers=headers) as resp:
            return resp.status, await resp.read()


async def deliver_repair_reply(bot: Bot, body: bytes, text: str) -> None:
    try:
        data = json.loads(body)
        update = Update.model_validate(data)
    except Exception:
        logger.exception("Repair gateway: invalid Telegram update")
        return

    chat_id: int | None = None
    callback_id: str | None = None

    if update.message:
        chat_id = update.message.chat.id
    elif update.edited_message:
        chat_id = update.edited_message.chat.id
    elif update.callback_query:
        callback_id = update.callback_query.id
        if update.callback_query.message:
            chat_id = update.callback_query.message.chat.id

    if callback_id:
        try:
            await bot.answer_callback_query(
                callback_id,
                "ربات موقتاً در دسترس نیست.",
                show_alert=True,
            )
        except Exception:
            logger.debug("Could not answer callback %s", callback_id)

    if chat_id is None:
        logger.debug("Repair gateway: no chat_id in update — skip reply")
        return

    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("Repair gateway: failed to send message to chat %s", chat_id)


async def handle_webhook(bot: Bot, body: bytes, request_headers) -> tuple[int, bytes]:
    state = load_state()

    if is_planned_repair_active(state):
        text = planned_repair_message(state)
        logger.info("Planned repair active — replying to user")
        await deliver_repair_reply(bot, body, text)
        return 200, b"{}"

    try:
        status, resp_body = await forward_to_main_bot(body, request_headers)
        if status == 200:
            return status, resp_body
        logger.warning("Main bot returned HTTP %s — using default offline message", status)
    except aiohttp.ClientError as exc:
        logger.warning("Main bot unreachable (%s) — using default offline message", exc)
    except Exception:
        logger.exception("Main bot forward failed — using default offline message")

    text = default_offline_message(state)
    await deliver_repair_reply(bot, body, text)
    return 200, b"{}"
