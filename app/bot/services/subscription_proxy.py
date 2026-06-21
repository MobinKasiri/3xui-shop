"""Fetch panel subscription body and inject per-user Profile-Title."""
from __future__ import annotations

import logging

import aiohttp
from aiohttp import web

from app.bot.utils.sub_profile import profile_title_from_userinfo, profile_title_header_value

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


async def proxy_subscription_response(
    upstream_url: str,
    *,
    service_name: str,
) -> web.Response:
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
