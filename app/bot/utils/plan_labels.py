"""Display names for plan tiers — user-facing strings only (not plan/tier ids)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.bot.i18n import fa

if TYPE_CHECKING:
    from app.config import PricingConfig

DEFAULT_TIER_DISPLAY_NAME = fa.TIER_NAME_DEFAULT


def tier_display_name(
    plan: dict | None = None,
    *,
    tier: dict | None = None,
    fallback: str | None = None,
) -> str:
    """Resolve tier label from a plan dict (tier_name) or tier dict (name)."""
    if plan:
        name = str(plan.get("tier_name") or "").strip()
        if name:
            return name
    if tier:
        name = str(tier.get("name") or "").strip()
        if name:
            return name
    return fallback or DEFAULT_TIER_DISPLAY_NAME


def tier_display_for_plan_id(
    pricing: PricingConfig | None,
    plan_id: str | None,
    *,
    fallback: str | None = None,
) -> str:
    if pricing and plan_id:
        plan = pricing.get_plan(plan_id)
        if plan:
            return tier_display_name(plan, fallback=fallback)
    return fallback or DEFAULT_TIER_DISPLAY_NAME
