"""Jalali (Persian/Shamsi) calendar utilities."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import jdatetime

from app.bot.utils.persian import to_persian_digits

TEHRAN = ZoneInfo("Asia/Tehran")


def _to_tehran(dt: datetime) -> datetime:
    """Normalize any datetime to naive wall-clock time in Asia/Tehran."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).replace(tzinfo=None)


def to_jalali(dt: datetime) -> str:
    """Convert datetime to Jalali date string like 1403/05/28 (Tehran timezone)."""
    local = _to_tehran(dt)
    jd = jdatetime.datetime.fromgregorian(datetime=local)
    raw = f"{jd.year}/{jd.month:02d}/{jd.day:02d}"
    return to_persian_digits(raw)


def to_jalali_full(dt: datetime) -> str:
    """Convert datetime to full Jalali datetime string (Tehran timezone)."""
    local = _to_tehran(dt)
    jd = jdatetime.datetime.fromgregorian(datetime=local)
    raw = f"{jd.year}/{jd.month:02d}/{jd.day:02d} {local.hour:02d}:{local.minute:02d}"
    return to_persian_digits(raw)


def days_until(dt: datetime) -> int:
    """Return number of calendar days until dt (negative if in the past)."""
    now = datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = dt - now
    return delta.days


def ms_to_datetime(ms: int) -> datetime | None:
    """Convert millisecond Unix timestamp to naive UTC datetime for DB storage."""
    if ms == 0:
        return None
    return datetime.utcfromtimestamp(ms / 1000)


def datetime_to_ms(dt: datetime) -> int:
    """Convert datetime to millisecond Unix timestamp."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


MS_PER_DAY = 86_400_000


def start_after_first_use_ms(days: int) -> int:
    """3X-UI delayed start: negative ms = duration counted after first connection."""
    return -days * MS_PER_DAY


def is_delayed_start(expiry_ms: int) -> bool:
    return expiry_ms < 0


def delayed_start_days(expiry_ms: int) -> int:
    return abs(expiry_ms) // MS_PER_DAY


def add_days_ms(base_ms: int, days: int) -> int:
    """Add `days` to a millisecond timestamp. base_ms=0 means 'from now'."""
    from datetime import timedelta
    if base_ms == 0:
        base = datetime.now(tz=timezone.utc)
    else:
        base = datetime.fromtimestamp(base_ms / 1000, tz=timezone.utc)
    result = base + timedelta(days=days)
    return datetime_to_ms(result)


def extend_expiry_ms(current_ms: int, days: int, *, delayed_start: bool) -> int:
    """Extend panel expiry — negative values stay delayed until first use."""
    if delayed_start and current_ms <= 0:
        base = current_ms if current_ms < 0 else start_after_first_use_ms(days)
        if current_ms < 0:
            return current_ms - days * MS_PER_DAY
        return base
    return add_days_ms(max(current_ms, now_ms()), days)
