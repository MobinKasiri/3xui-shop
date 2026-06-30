"""Validate, generate and check uniqueness of user-chosen service names."""
from __future__ import annotations

import random
import re
import secrets
import string

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.utils.ids import make_panel_email
from app.db.models import VPNConfig

if TYPE_CHECKING:
    from app.bot.services.xui_api import XUIApiService

NAME_PATTERN = re.compile(r"^[a-z0-9]{3,30}$")
PANEL_EMAIL_DOMAIN = "nexora.vpn"


def validate(name: str) -> bool:
    """True iff name is 3-30 chars of [a-z0-9]."""
    return bool(NAME_PATTERN.match(name))


def random_name(prefix: str = "user") -> str:
    """Generate a random suffixed name like user193847."""
    return prefix + "".join(random.choices(string.digits, k=6))


def resolve_display_service_name(
    panel_email: str,
    panel_record: dict,
    *,
    explicit: str | None = None,
) -> str:
    """
    Bot-facing service name from user input, panel comment, or legacy panel email.
    """
    if explicit:
        name = explicit.strip().lower()
        if validate(name):
            return name

    comment = str(panel_record.get("comment") or "").strip().lower()
    if comment and validate(comment):
        return comment

    legacy = panel_email.strip().lower()
    if validate(legacy):
        return legacy

    local = legacy.split("@", 1)[0]
    if validate(local):
        return local

    return random_name("svc")


async def allocate_panel_email(
    session: AsyncSession,
    xui: "XUIApiService",
    tg_id: int,
    *,
    max_attempts: int = 12,
) -> str:
    """Reserve a panel client email that is free in bot DB and on 3X-UI."""
    from app.bot.services.xui_api import XUIError, XUINotFound

    for _ in range(max_attempts):
        email = make_panel_email(tg_id)
        if await VPNConfig.get_by_email(session, email):
            continue
        try:
            await xui.get_client(email)
        except XUINotFound:
            return email
        except XUIError:
            return email
    raise RuntimeError(f"Could not allocate unique panel email for tg_id={tg_id}")


async def is_taken(
    session: AsyncSession,
    user_id: int,
    service_name: str,
) -> bool:
    """True if this user already has a config with the given display name."""
    existing = await VPNConfig.get_by_name(session, user_id, service_name.strip().lower())
    return existing is not None


async def suggest_alternatives(
    session: AsyncSession,
    user_id: int,
    base: str,
    *,
    count: int = 3,
) -> list[str]:
    """Return up to `count` available alternatives derived from `base`."""
    out: list[str] = []
    attempts = 0
    while len(out) < count and attempts < 30:
        attempts += 1
        candidate = f"{base}{random.randint(10, 99)}"[:30]
        if validate(candidate) and not await is_taken(session, user_id, candidate):
            if candidate not in out:
                out.append(candidate)
    return out


def numbered_name(base: str, index: int) -> str:
    """Return `base-index` clamped to 30 chars (used for bulk purchases)."""
    suffix = f"-{index}"
    head = base[: max(1, 30 - len(suffix))]
    return f"{head}{suffix}"
