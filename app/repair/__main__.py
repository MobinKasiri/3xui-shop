"""
Webhook gateway — ALL Telegram traffic enters here first.

Scenario 1 (repair mode OFF, main bot down):
  Forward to main bot → on failure, send configurable default offline message.

Scenario 2 (repair mode ON from panel):
  Always send planned repair message — main bot is not used for users.
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.repair.gateway import handle_webhook

TELEGRAM_WEBHOOK = "/webhook"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8091

logger = logging.getLogger(__name__)


async def _run() -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is required for repair-bot")

    port = int(os.environ.get("REPAIR_PORT", DEFAULT_PORT))

    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format=os.environ.get(
            "LOG_FORMAT", "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        ),
    )

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    app = web.Application()

    async def health_handler(_request: web.Request) -> web.Response:
        return web.Response(text="OK", status=200)

    async def webhook_handler(request: web.Request) -> web.Response:
        body = await request.read()
        status, resp_body = await handle_webhook(bot, body, request.headers)
        return web.Response(
            body=resp_body,
            status=status,
            content_type="application/json",
        )

    app.router.add_get("/health", health_handler)
    app.router.add_post(TELEGRAM_WEBHOOK, webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, DEFAULT_HOST, port)
    await site.start()
    logger.info(
        "Repair gateway listening on %s:%s (webhook entry → main bot or repair reply)",
        DEFAULT_HOST,
        port,
    )

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Repair gateway stopped.")
