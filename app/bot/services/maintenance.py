"""Shared maintenance state (written by admin panel to app/data/maintenance.json)."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MAINTENANCE_FILE = Path("/app/data/maintenance.json")

PRESETS: dict[str, str] = {
    "developing": (
        "🔧 <b>ربات در حال توسعه است</b>\n\n"
        "در حال اضافه کردن قابلیت‌های جدید هستیم. لطفاً کمی بعد دوباره سر بزنید."
    ),
    "updating": (
        "⬆️ <b>بروزرسانی ربات</b>\n\n"
        "نسخه جدید ربات در حال نصب است. به‌زودی با امکانات بهتر برمی‌گردیم."
    ),
    "servers": (
        "🖥 <b>بروزرسانی سرورها</b>\n\n"
        "سرورها در حال ارتقا هستند تا اتصال پایدارتر و سریع‌تری داشته باشید."
    ),
    "bugfix": (
        "🛠 <b>رفع مشکل فنی</b>\n\n"
        "یک مشکل فنی شناسایی شده و در حال رفع آن هستیم. از صبر شما سپاسگزاریم."
    ),
    "maintenance": (
        "⏸ <b>غیرفعال موقت</b>\n\n"
        "ربات به‌صورت موقت غیرفعال شده است. لطفاً بعداً دوباره تلاش کنید."
    ),
}


def _remaining_persian(ends_at: str | None) -> str | None:
    if not ends_at:
        return None
    try:
        ends = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
        if ends.tzinfo:
            ends = ends.replace(tzinfo=None)
        delta = ends - datetime.utcnow()
        if delta.total_seconds() <= 0:
            return None
        minutes = int(delta.total_seconds() // 60)
        if minutes < 60:
            return f"{minutes} دقیقه"
        hours = minutes // 60
        rem = minutes % 60
        if rem:
            return f"{hours} ساعت و {rem} دقیقه"
        return f"{hours} ساعت"
    except ValueError:
        return None


def load_state() -> dict:
    if not MAINTENANCE_FILE.is_file():
        return {"enabled": False}
    try:
        with MAINTENANCE_FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {"enabled": False}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("maintenance.json unreadable: %s", exc)
        return {"enabled": False}

    if data.get("enabled") and data.get("ends_at"):
        try:
            ends = datetime.fromisoformat(str(data["ends_at"]).replace("Z", "+00:00"))
            if ends.tzinfo:
                ends = ends.replace(tzinfo=None)
            if ends <= datetime.utcnow():
                return {"enabled": False}
        except ValueError:
            pass
    return data


def is_maintenance_active() -> bool:
    return bool(load_state().get("enabled"))


def user_message() -> str:
    state = load_state()
    if not state.get("enabled"):
        return ""
    reason = state.get("reason") or "maintenance"
    base = state.get("custom_message") or PRESETS.get(reason, PRESETS["maintenance"])
    remaining = _remaining_persian(state.get("ends_at"))
    if remaining:
        return f"{base}\n\n⏱ زمان تقریبی: <b>{remaining}</b>"
    return base
