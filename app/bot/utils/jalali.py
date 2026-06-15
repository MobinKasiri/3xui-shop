"""Jalali (Persian/Shamsi) calendar utilities."""
from __future__ import annotations

from datetime import datetime, timezone

import jdatetime

from app.bot.utils.persian import to_persian_digits


def to_jalali(dt: datetime) -> str:
    """Convert datetime to Jalali date string like ۱۴۰۳/۰۵/۲۸."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    jd = jdatetime.datetime.fromgregorian(datetime=dt)
    raw = f"{jd.year}/{jd.month:02d}/{jd.day:02d}"
    return to_persian_digits(raw)


def to_jalali_full(dt: datetime) -> str:
    """Convert datetime to full Jalali datetime string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    jd = jdatetime.datetime.fromgregorian(datetime=dt)
    raw = f"{jd.year}/{jd.month:02d}/{jd.day:02d} {jd.hour:02d}:{jd.minute:02d}"
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


def add_days_ms(base_ms: int, days: int) -> int:
    """Add `days` to a millisecond timestamp. base_ms=0 means 'from now'."""
    from datetime import timedelta
    if base_ms == 0:
        base = datetime.now(tz=timezone.utc)
    else:
        base = datetime.fromtimestamp(base_ms / 1000, tz=timezone.utc)
    result = base + timedelta(days=days)
    return datetime_to_ms(result)
