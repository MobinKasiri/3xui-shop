"""
Hourly: find configs ≥80% traffic usage, send warning.
Dedupes per (config_id, "80pct") bucket.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from sqlalchemy import select
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
        renewal_pct = int(load_renewal_settings().get("discount_percent", 10))

        warn_configs = [
            c for c in configs
            if c.traffic_limit_bytes > 0 and c.usage_percent >= TRAFFIC_WARN_PCT
        ]
        sent_ids: set[int] = set()
        if warn_configs:
            config_ids = [c.id for c in warn_configs]
            result = await session.execute(
                select(NotificationLog.config_id).where(
                    NotificationLog.config_id.in_(config_ids),
                    NotificationLog.type == NOTIF_TRAFFIC,
                    NotificationLog.bucket == "80pct",
                )
            )
            sent_ids = {row[0] for row in result.all()}

        for config in warn_configs:
            if config.id in sent_ids:
                continue

            used_gb = config.traffic_used_gb
            total_gb = config.traffic_limit_gb
            pct = config.usage_percent
            bucket = "80pct"

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
