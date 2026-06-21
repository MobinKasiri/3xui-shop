"""Subscription profile title for VPN clients (v2Box / v2rayNG Profile-Title header)."""
from __future__ import annotations

import base64

from app.bot.utils.persian import to_persian_digits

_BRAND = "NC VPN"


def parse_subscription_userinfo(header: str) -> dict[str, int]:
    """Parse ``upload=0; download=0; total=0; expire=0`` header."""
    out: dict[str, int] = {}
    for part in header.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip().lower()
        val = val.strip()
        if val.lstrip("-").isdigit():
            out[key] = int(val)
    return out


def format_remaining_traffic(*, upload: int, download: int, total: int) -> str:
    if total <= 0:
        return "∞"
    used = max(0, upload) + max(0, download)
    rem_gb = max(0, total - used) / (1024**3)
    return f"{to_persian_digits(f'{rem_gb:.1f}')} GB"


def build_sub_profile_title(
    service_name: str,
    *,
    upload: int = 0,
    download: int = 0,
    total: int = 0,
) -> str:
    """``NC VPN - {service_name} - {remaining traffic}``"""
    name = (service_name or "").strip() or "—"
    remaining = format_remaining_traffic(upload=upload, download=download, total=total)
    return f"{_BRAND} - {name} - {remaining}"


def profile_title_header_value(title: str) -> str:
    """Telegram / 3X-UI style Profile-Title value."""
    return "base64:" + base64.b64encode(title.encode("utf-8")).decode("ascii")


def profile_title_from_userinfo(service_name: str, userinfo_header: str) -> str:
    info = parse_subscription_userinfo(userinfo_header)
    return build_sub_profile_title(
        service_name,
        upload=info.get("upload", 0),
        download=info.get("download", 0),
        total=info.get("total", 0),
    )
