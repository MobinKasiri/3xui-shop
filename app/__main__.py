from __future__ import annotations

import asyncio
import logging
from urllib.parse import urljoin

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.config import Config, load_config
from app.db.database import Database
from app.bot.services.bootstrap import (
    bootstrap_with_retries,
    close_xui,
    get_vpn_service,
    sync_subscription_urls,
    xui_service,
)
from app.bot.filters.is_private import IsPrivate
from app.bot.filters.is_admin import IsAdmin
from app.bot.middlewares import register as register_middlewares

# ── Routers ──────────────────────────────────────────────────────────────────
from app.bot.routers.channel_gate import router as channel_gate_router
from app.bot.routers.main_menu import router as main_menu_router
from app.bot.routers.purchase import router as purchase_router
from app.bot.routers.renew import router as renew_router
from app.bot.routers.my_services import router as my_services_router
from app.bot.routers.wallet import router as wallet_router
from app.bot.routers.referral import router as referral_router
from app.bot.routers.apps import router as apps_router
from app.bot.routers.support import router as support_router
from app.bot.routers.admin import router as admin_router
from app.bot.routers.common import router as common_router
from app.bot.tasks.expiry import run_expiry_check
from app.bot.tasks.traffic import run_traffic_check
from app.bot.tasks.traffic_sync import run_traffic_sync

DEFAULT_BOT_HOST = "0.0.0.0"
TELEGRAM_WEBHOOK = "/webhook"

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, config: Config, db: Database, **kwargs) -> None:
    logger.info("Bot starting up...")
    from app.bot.utils.commands import setup as setup_commands
    from app.bot.utils.emoji import (
        button_vector_icons_enabled,
        count_loaded,
        custom_emoji_ready,
        reload_emoji_cache,
    )

    reload_emoji_cache()
    total, packs = count_loaded()
    if custom_emoji_ready():
        logger.info("Custom emoji ready: %s icons from %s packs", total, packs)
        logger.info(
            "Button vector icons: %s",
            "on" if button_vector_icons_enabled() else "off",
        )
    else:
        logger.warning(
            "No custom emoji IDs loaded — run: python scripts/sync_emoji_packs.py"
        )

    await setup_commands(bot)

    # Fill BOT_USERNAME from API if not configured
    try:
        me = await bot.get_me()
        if me.username:
            config.bot.USERNAME = me.username
    except Exception:
        logger.debug("Could not fetch bot username at startup.")

    await bootstrap_with_retries(config)

    from app.db.schema_ensure import ensure_bot_schema

    await ensure_bot_schema(db)

    await sync_subscription_urls(config, db.session)

    if config.bot.CHANNEL_GATE_ENABLED and config.bot.gate_channels:
        from app.bot.services.required_channels import verify_gate_channels_at_startup

        logger.info(
            "Required channels (%s): %s",
            len(config.bot.gate_channels),
            ", ".join(ch.chat_id for ch in config.bot.gate_channels),
        )
        await verify_gate_channels_at_startup(bot, config.bot.gate_channels)
    else:
        logger.info("Required channels: disabled")

    if config.bot.USE_POLLING:
        # Production may have left a webhook on this token — polling cannot run until it is cleared.
        try:
            info = await bot.get_webhook_info()
            if info.url:
                logger.warning(
                    "Removing active webhook %s so local polling can receive updates.",
                    info.url,
                )
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("Polling mode: webhook cleared.")
        except Exception as e:
            logger.error(
                "Failed to delete webhook before polling: %s. "
                "Run: curl https://api.telegram.org/bot<TOKEN>/deleteWebhook",
                e,
            )
    else:
        webhook_url = urljoin(config.bot.DOMAIN + "/", TELEGRAM_WEBHOOK.lstrip("/"))
        logger.info(f"Setting webhook: {webhook_url}")
        try:
            await bot.set_webhook(webhook_url)
            info = await bot.get_webhook_info()
            logger.info(f"Webhook set: {info.url}")
            if info.last_error_message:
                logger.error(
                    "Telegram webhook delivery error: %s (date=%s). "
                    "If using HTTPS on 8443, ensure deploy/nginx/certs/ exist; "
                    "otherwise set BOT_USE_HTTPS=false and BOT_DOMAIN=bot.nexoranode.xyz",
                    info.last_error_message,
                    info.last_error_date,
                )
        except Exception as e:
            err = str(e)
            logger.error(
                f"Failed to set webhook ({webhook_url}): {e}. "
                "Bot will still start — fix webhook manually."
            )
            if "HTTPS URL must be provided" in err or "bad webhook" in err.lower():
                logger.error(
                    "Telegram requires HTTPS. Run on server: "
                    "bash deploy/setup-ssl.sh && bash deploy/set-webhook.sh"
                )

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_expiry_check, "interval", hours=1,
        kwargs={"session_factory": db.session, "bot": bot},
        id="expiry_check",
    )
    scheduler.add_job(
        run_traffic_check, "interval", hours=1,
        kwargs={"session_factory": db.session, "bot": bot},
        id="traffic_check",
    )
    if xui_service:
        scheduler.add_job(
            run_traffic_sync, "interval", minutes=30,
            kwargs={"session_factory": db.session, "xui": xui_service},
            id="traffic_sync",
        )
    scheduler.start()
    logger.info("APScheduler started.")


async def on_shutdown(bot: Bot, db: Database, **kwargs) -> None:
    logger.info("Bot shutting down...")
    await close_xui()
    await db.close()
    await bot.session.close()
    logger.info("Cleanup done.")


async def _run_app(app: web.Application, host: str, port: int) -> None:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"Webhook server started on {host}:{port}")
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def main() -> None:
    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.logging.LEVEL.upper(), logging.DEBUG),
        format=config.logging.FORMAT,
    )
    logger.info("NC VPN Bot starting...")

    db = Database(config.database)
    storage = RedisStorage.from_url(config.redis.url())

    bot = Bot(
        token=config.bot.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=storage)

    IsAdmin.set_admins(config.bot.ADMINS)
    dispatcher.message.filter(IsPrivate())

    register_middlewares(dispatcher, db.session)

    # NOTE: purchase router includes admin:approve_purchase handlers — register
    # before admin router so its specific F.data.startswith handlers run first.
    dispatcher.include_router(channel_gate_router)
    dispatcher.include_router(main_menu_router)
    dispatcher.include_router(purchase_router)
    dispatcher.include_router(renew_router)
    dispatcher.include_router(my_services_router)
    dispatcher.include_router(wallet_router)
    dispatcher.include_router(referral_router)
    dispatcher.include_router(apps_router)
    dispatcher.include_router(support_router)
    dispatcher.include_router(admin_router)
    dispatcher.include_router(common_router)

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    vpn_service = get_vpn_service(config)
    if not vpn_service and not config.bot.USE_POLLING:
        logger.debug(
            "VPN service not ready at import time — middleware will connect on first update."
        )

    workflow_data = dict(
        config=config,
        db=db,
        vpn_service=vpn_service,
        xui_service=xui_service,
    )

    if config.bot.USE_POLLING:
        logger.info("Starting bot in long-polling mode (local dev).")
        await dispatcher.start_polling(
            bot,
            handle_signals=False,
            **workflow_data,
        )
    else:
        @web.middleware
        async def log_webhook(request: web.Request, handler):
            if request.path == TELEGRAM_WEBHOOK:
                logger.info("Webhook %s from %s", request.method, request.remote)
            return await handler(request)

        app = web.Application(middlewares=[log_webhook])
        app["config"] = config

        async def health_handler(_request: web.Request) -> web.Response:
            return web.Response(text="OK", status=200)

        async def node_sync_version_handler(request: web.Request) -> web.Response:
            from app.bot.services.node_sync_signal import read_node_sync_version

            expected = (config.xui.NODE_SYNC_TRIGGER_TOKEN or "").strip()
            if not expected:
                return web.Response(status=404, text="disabled")
            auth = request.headers.get("Authorization", "")
            token = auth[7:].strip() if auth.startswith("Bearer ") else ""
            if token != expected:
                return web.Response(status=401, text="unauthorized")
            ver = await read_node_sync_version(config)
            return web.Response(text=str(ver), content_type="text/plain")

        app.router.add_get("/health", health_handler)
        app.router.add_get("/internal/node-sync/v", node_sync_version_handler)

        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dispatcher,
            bot=bot,
            **workflow_data,
        )
        webhook_requests_handler.register(app, path=TELEGRAM_WEBHOOK)
        setup_application(app, dispatcher, bot=bot, **workflow_data)
        await _run_app(app, host=DEFAULT_BOT_HOST, port=config.bot.PORT)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by keyboard interrupt.")
