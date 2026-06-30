from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.bot.services.bootstrap import ensure_vpn_service
from app.config import Config

logger = logging.getLogger(__name__)


class VPNServiceMiddleware(BaseMiddleware):
    """Inject a live VPNService on every update (panel may connect after startup)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        config: Config | None = data.get("config")
        if config and not data.get("vpn_service"):
            data["vpn_service"] = await ensure_vpn_service(config)
        return await handler(event, data)
