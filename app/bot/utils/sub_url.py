"""Subscription URL helpers — standard /s/ only."""
from __future__ import annotations

DEFAULT_ROUTING_RULES = """GEOSITE,category-ir,DIRECT
GEOIP,ir,DIRECT
GEOIP,private,DIRECT
MATCH,PROXY"""


def resolve_sub_base(standard_base: str) -> str:
    return (standard_base or "").rstrip("/") + "/"


def normalize_subscription_url(url: str) -> str:
    """Fix legacy /clash/ rows when shown to users (migrated on bot restart)."""
    if "/clash/" in (url or ""):
        return url.replace("/clash/", "/s/", 1)
    return url or ""
