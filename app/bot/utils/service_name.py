"""Validate, generate and check uniqueness of user-chosen service names."""
from __future__ import annotations

import random
import re
import string

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import VPNConfig

NAME_PATTERN = re.compile(r"^[a-z0-9]{3,30}$")
PANEL_EMAIL_DOMAIN = "nexora.vpn"


def validate(name: str) -> bool:
    """True iff name is 3-30 chars of [a-z0-9]."""
    return bool(NAME_PATTERN.match(name))


def random_name(prefix: str = "user") -> str:
    """Generate a random suffixed name like user193847."""
    return prefix + "".join(random.choices(string.digits, k=6))


def panel_email(service_name: str) -> str:
    """Panel client identifier — plain service name (no @domain suffix)."""
    return service_name.strip().lower()


async def is_taken(session: AsyncSession, service_name: str) -> bool:
    """True iff the service name is already used by any config."""
    return await VPNConfig.name_exists(session, service_name)


async def suggest_alternatives(
    session: AsyncSession, base: str, *, count: int = 3
) -> list[str]:
    """Return up to `count` available alternatives derived from `base`."""
    out: list[str] = []
    attempts = 0
    while len(out) < count and attempts < 30:
        attempts += 1
        candidate = f"{base}{random.randint(10, 99)}"[:30]
        if validate(candidate) and not await is_taken(session, candidate):
            if candidate not in out:
                out.append(candidate)
    return out


def numbered_name(base: str, index: int) -> str:
    """Return `base-index` clamped to 30 chars (used for bulk purchases)."""
    suffix = f"-{index}"
    head = base[: max(1, 30 - len(suffix))]
    return f"{head}{suffix}"
