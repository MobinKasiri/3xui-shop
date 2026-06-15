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
    ensure_vpn_service,
    get_vpn_service,
    xui_service,
)
from app.bot.services.vpn import VPNService
from app.bot.filters.is_private import IsPrivate
from app.bot.filters.is_admin import IsAdmin
from app.bot.middlewares import register as register_middlewares

# ── Routers ──────────────────────────────────────────────────────────────────
from app.bot.routers.main_menu import router as main_menu_router
from app.bot.routers.trial import router as trial_router
from app.bot.routers.purchase import router as purchase_router
from app.bot.routers.my_services import router as my_services_router
from app.bot.routers.wallet import router as wallet_router
from app.bot.routers.renewal import router as renewal_router
from app.bot.routers.referral import router as referral_router
from app.bot.routers.bulk import router as bulk_router
from app.bot.routers.pricing import router as pricing_router
from app.bot.routers.guide import router as guide_router
from app.bot.routers.agency import router as agency_router
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
    await setup_commands(bot)
    await bootstrap_with_retries(config)
    if not config.bot.USE_POLLING:
        webhook_url = urljoin(config.bot.DOMAIN + "/", TELEGRAM_WEBHOOK.lstrip("/"))
        logger.info(f"Setting webhook: {webhook_url}")
        try:
            await bot.set_webhook(webhook_url)
            info = await bot.get_webhook_info()
            logger.info(f"Webhook set: {info.url}")
        except Exception as e:
            logger.error(
                f"Failed to set webhook ({webhook_url}): {e}. "
                "Bot will still start — set webhook manually once nginx/SSL is ready."
            )

    # ── APScheduler ───────────────────────────────────────────────────────────
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone="UTC")
    plans = config.pricing.PLANS

    scheduler.add_job(
        run_expiry_check, "interval", hours=1,
        kwargs={"session_factory": db.session, "bot": bot, "plans": plans},
        id="expiry_check",
    )
    scheduler.add_job(
        run_traffic_check, "interval", hours=1,
        kwargs={"session_factory": db.session, "bot": bot, "plans": plans},
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
    logger.info("Nexoranode VPN Bot starting...")

    db = Database(config.database)
    storage = RedisStorage.from_url(config.redis.url())

    bot = Bot(
        token=config.bot.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=storage)

    # ── Register filters ──────────────────────────────────────────────────────
    IsAdmin.set_admins(config.bot.ADMINS)
    # Only restrict messages to private chats — callback queries are allowed everywhere
    # (admin may need to approve receipts from group forwards)
    dispatcher.message.filter(IsPrivate())

    # ── Register middlewares ──────────────────────────────────────────────────
    register_middlewares(dispatcher, db.session)

    # ── Register routers ──────────────────────────────────────────────────────
    dispatcher.include_router(main_menu_router)
    dispatcher.include_router(trial_router)
    dispatcher.include_router(purchase_router)
    dispatcher.include_router(my_services_router)
    dispatcher.include_router(wallet_router)
    dispatcher.include_router(renewal_router)
    dispatcher.include_router(referral_router)
    dispatcher.include_router(bulk_router)
    dispatcher.include_router(pricing_router)
    dispatcher.include_router(guide_router)
    dispatcher.include_router(agency_router)
    dispatcher.include_router(admin_router)
    dispatcher.include_router(common_router)

    # ── Wire lifecycle hooks ──────────────────────────────────────────────────
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    # ── Start ─────────────────────────────────────────────────────────────────
    vpn_service = get_vpn_service(config)
    if not vpn_service and not config.bot.USE_POLLING:
        logger.warning(
            "VPN service unavailable — trial/purchase will fail until XUI panel connects."
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
        app = web.Application()

        async def health_handler(_request: web.Request) -> web.Response:
            return web.Response(text="OK", status=200)

        app.router.add_get("/health", health_handler)

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
