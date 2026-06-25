"""3X-UI connection settings — no Telegram/aiogram imports."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


def normalize_xui_host(host: str) -> str:
    """
    Bot runs in Docker; .env often uses 127.0.0.1 for co-located x-ui on the host.
    Rewrite to host.docker.internal (requires extra_hosts in docker-compose).
    """
    raw = (host or "").strip()
    if not raw:
        return raw
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    netloc = parsed.netloc
    if parsed.port == 2087:
        logger.warning("XUI_HOST port 2087 is wrong — using 2057 for 3X-UI panel")
        netloc = netloc.replace(":2087", ":2057", 1)
    if parsed.hostname in ("127.0.0.1", "localhost"):
        netloc = netloc.replace(parsed.hostname, "host.docker.internal", 1)
    if netloc != parsed.netloc:
        normalized = urlunparse(parsed._replace(netloc=netloc))
        logger.info("XUI_HOST normalized for Docker: %s -> %s", raw, normalized)
        return normalized
    return raw


@dataclass
class XUIConfig:
    HOST: str
    PATH: str
    USERNAME: str
    PASSWORD: str
    TOKEN: str | None
    SUB_BASE_URL: str
    INBOUND_FILTER: tuple[str, ...] = ()
    START_AFTER_FIRST_USE: bool = True
    DEFAULT_DURATION_DAYS: int = 30
    NODE_SYNC_ENABLED: bool = False
    NODE_SSH_USER: str = "root"
    NODE_SSH_PORT: int = 22
    NODE_SSH_IDENTITY: str = ""
    NODE_SYNC_TRIGGER_TOKEN: str = ""

    @property
    def base_url(self) -> str:
        return self.HOST.rstrip("/") + "/" + self.PATH.strip("/")
