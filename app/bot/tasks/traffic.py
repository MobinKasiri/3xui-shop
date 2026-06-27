"""
Hourly: find configs ≥80% traffic usage, send warning.
Dedupes per (config_id, "80pct") bucket.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.i18n import fa
from app.bot.routers.renew.handler import notif_action_keyboard
from app.bot.services.renewal_settings import load_renewal_settings
from app.bot.utils.persian import to_persian_digits
from app.bot.utils.renewal_pricing import SERVICE_MAX_DAYS
from app.db.models import VPNConfig
from app.db.models.notification_log import NOTIF_TRAFFIC, NotificationLog

logger = logging.getLogger(__name__)

TRAFFIC_WARN_PCT = 80.0


async def run_traffic_check(
    session_factory: async_sessionmaker,
    bot: Bot,
    **_kwargs,
) -> None:
    logger.info("Running traffic usage check...")
    sent = 0

    async with session_factory() as session:
        configs = await VPNConfig.get_active(session)
        for config in configs:
            if config.traffic_limit_bytes == 0:
                continue
            pct = config.usage_percent
            if pct < TRAFFIC_WARN_PCT:
                continue

            bucket = "80pct"
            already = await NotificationLog.already_sent(
                session, config.id, NOTIF_TRAFFIC, bucket
            )
            if already:
                continue

            used_gb = config.traffic_used_gb
            total_gb = config.traffic_limit_gb

            renewal_pct = int(load_renewal_settings().get("discount_percent", 10))
            text = fa.NOTIF_TRAFFIC_WARNING.format(
                name=config.service_name,
                used_gb=to_persian_digits(f"{used_gb:.1f}"),
                total_gb=to_persian_digits(f"{total_gb:.1f}"),
                pct=to_persian_digits(int(pct)),
                discount_pct=to_persian_digits(renewal_pct),
                max_days=to_persian_digits(SERVICE_MAX_DAYS),
            )
            markup = notif_action_keyboard(config.id, discount_pct=renewal_pct)

            try:
                await bot.send_message(
                    config.user_id, text, parse_mode="HTML", reply_markup=markup
                )
                await NotificationLog.create(
                    session,
                    user_id=config.user_id,
                    config_id=config.id,
                    type=NOTIF_TRAFFIC,
                    bucket=bucket,
                )
                sent += 1
            except Exception as e:
                logger.debug(f"Failed to notify user {config.user_id}: {e}")

    logger.info(f"Traffic check complete. Sent {sent} warnings.")
