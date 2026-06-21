"""
Subscription title proxy — runs on the panel/origin server (not the bot domain).

Public URL (users):  https://sub.manchesterchocolates.ir/s/{prefix}/{subId}
This service:        listens locally, fetches panel sub upstream, adds Profile-Title.

Env:
  DATABASE_URL          — bot postgres (service_name lookup)
  SUB_UPSTREAM_URL      — panel sub server base, e.g. http://127.0.0.1:2096/s/iir2lk4umjoejg69/
  SUB_PROXY_HOST        — default 0.0.0.0
  SUB_PROXY_PORT        — default 8092
"""
from __future__ import annotations

import asyncio
import logging
import os
import re

import aiohttp
from aiohttp import web
from environs import Env
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.bot.services.subscription_proxy import proxy_subscription_response
from app.db.models import VPNConfig

logger = logging.getLogger(__name__)

_SUB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _load_session_factory() -> async_sessionmaker[AsyncSession]:
    env = Env()
    env.read_env()
    db_url = env.str("DATABASE_URL")
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _lookup_service_name(
    session_factory: async_sessionmaker[AsyncSession], sub_id: str
) -> str | None:
    async with session_factory() as session:
        cfg = await VPNConfig.get_by_subscription_id(session, sub_id)
        return cfg.service_name if cfg else None


def _extract_sub_id(path: str) -> str | None:
    """`/s/iir2lk4umjoejg69/abc123` → `abc123`"""
    part = path.rstrip("/").rsplit("/", 1)[-1]
    if not part or not _SUB_ID_RE.fullmatch(part):
        return None
    return part


async def _handle(request: web.Request) -> web.Response:
    session_factory: async_sessionmaker = request.app["session_factory"]
    upstream_base: str = request.app["upstream_base"]

    sub_id = _extract_sub_id(request.path)
    if not sub_id:
        return web.Response(status=404, text="not found")

    upstream_url = upstream_base.rstrip("/") + "/" + sub_id
    service_name = await _lookup_service_name(session_factory, sub_id)
    return await proxy_subscription_response(
        upstream_url,
        service_name=service_name or sub_id,
    )


async def _health(_request: web.Request) -> web.Response:
    return web.Response(text="OK")


async def main() -> None:
    env = Env()
    env.read_env()

    logging.basicConfig(
        level=env.str("LOG_LEVEL", default="INFO").upper(),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    upstream = env.str(
        "SUB_UPSTREAM_URL",
        default="http://127.0.0.1:2096/s/iir2lk4umjoejg69/",
    )
    host = env.str("SUB_PROXY_HOST", default="0.0.0.0")
    port = env.int("SUB_PROXY_PORT", default=8092)

    app = web.Application()
    app["session_factory"] = _load_session_factory()
    app["upstream_base"] = upstream
    app.router.add_get("/health", _health)
    app.router.add_route("*", "/s/{prefix}/{sub_id}", _handle)
    # Some clients hit without trailing structure — catch remaining /s/... paths
    app.router.add_route("*", "/s/{prefix}/{sub_id}/", _handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Sub title proxy listening on %s:%s → upstream %s", host, port, upstream)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
