"""
Hourly: find configs expiring in ≤3 days, send Persian warning.
Uses notification_logs to deduplicate per (config_id, days-left bucket).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from app.bot.utils.keyboards import K
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.i18n import fa
from app.bot.utils.jalali import days_until, to_jalali
from app.bot.utils.persian import to_persian_digits
from app.bot.utils.progress import format_gb
from app.db.models import VPNConfig
from app.db.models.notification_log import NOTIF_EXPIRY, NotificationLog

logger = logging.getLogger(__name__)

WARNING_DAYS = 3


async def run_expiry_check(
    session_factory: async_sessionmaker,
    bot: Bot,
    **_kwargs,
) -> None:
    logger.info("Running expiry check...")
    now = datetime.now(tz=timezone.utc)
    threshold = now + timedelta(days=WARNING_DAYS)
    sent = 0

    async with session_factory() as session:
        configs = await VPNConfig.get_active(session)
        for config in configs:
            expiry = config.expiry_date
            if expiry is None:
                continue
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry > threshold:
                continue

            days_left = days_until(expiry)
            if days_left < 0:
                continue

            bucket = str(days_left)
            already = await NotificationLog.already_sent(
                session, config.id, NOTIF_EXPIRY, bucket
            )
            if already:
                continue

            remaining_gb = config.traffic_remaining_bytes / (1024 ** 3)
            text = fa.NOTIF_EXPIRY_WARNING.format(
                name=config.service_name,
                expiry=to_jalali(expiry),
                days=to_persian_digits(days_left),
                remaining_gb=to_persian_digits(f"{remaining_gb:.1f}"),
            )
            markup = K().success(fa.NOTIF_NEW_CONFIG_BTN, callback_data="menu:buy", icon="btn_buy").as_markup()

            try:
                await bot.send_message(
                    config.user_id, text, parse_mode="HTML", reply_markup=markup
                )
                await NotificationLog.create(
                    session,
                    user_id=config.user_id,
                    config_id=config.id,
                    type=NOTIF_EXPIRY,
                    bucket=bucket,
                )
                sent += 1
            except Exception as e:
                logger.debug(f"Failed to notify user {config.user_id}: {e}")

    logger.info(f"Expiry check complete. Sent {sent} warnings.")
