"""Proxy panel subscription responses with per-user Profile-Title."""
from __future__ import annotations

import logging
import re

import aiohttp
from aiohttp import web
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.utils.sub_profile import profile_title_from_userinfo, profile_title_header_value
from app.config import Config
from app.db.models import VPNConfig

logger = logging.getLogger(__name__)

_PASS_HEADERS = frozenset({
    "subscription-userinfo",
    "profile-update-interval",
    "support-url",
    "profile-web-page-url",
    "announce",
    "routing-enable",
    "routing",
    "content-type",
    "content-disposition",
})


async def handle_subscription_proxy(
    request: web.Request,
    *,
    session_factory: async_sessionmaker,
    config: Config,
) -> web.Response:
    sub_id = request.match_info.get("sub_id", "").strip()
    if not sub_id or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", sub_id):
        return web.Response(status=400, text="invalid subscription id")

    origin_base = config.xui.SUB_ORIGIN_URL.rstrip("/") + "/"
    upstream_url = origin_base + sub_id

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.get(upstream_url, allow_redirects=True) as upstream:
                body = await upstream.read()
                status = upstream.status
                passthrough = _forward_headers(upstream.headers)
                userinfo = upstream.headers.get("Subscription-Userinfo", "")
    except aiohttp.ClientError as exc:
        logger.warning("Subscription upstream failed %s: %s", upstream_url, exc)
        return web.Response(status=502, text="subscription upstream unavailable")

    if status >= 400:
        return web.Response(status=status, body=body, headers=passthrough)

    service_name = sub_id
    async with session_factory() as session:
        cfg = await VPNConfig.get_by_subscription_id(session, sub_id)
        if cfg:
            service_name = cfg.service_name

    title = profile_title_from_userinfo(service_name, userinfo)
    headers = dict(passthrough)
    headers["Profile-Title"] = profile_title_header_value(title)
    if userinfo:
        headers["Subscription-Userinfo"] = userinfo

    content_type = headers.pop("content-type", "text/plain; charset=utf-8")
    return web.Response(status=200, body=body, headers=headers, content_type=content_type)


def _forward_headers(upstream_headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, val in upstream_headers.items():
        if key.lower() in _PASS_HEADERS:
            out[key] = val
    return out
