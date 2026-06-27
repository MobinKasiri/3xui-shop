"""Renewal pricing — automatic discount on extend-existing-sub flows."""
from __future__ import annotations

from dataclasses import dataclass

from app.bot.services.renewal_settings import DEFAULT_RENEWAL_DISCOUNT_PERCENT

# Back-compat alias — prefer renewal_settings.load / RenewalSettingsView.
RENEWAL_DISCOUNT_PERCENT = DEFAULT_RENEWAL_DISCOUNT_PERCENT
# All subscriptions use a fixed 1-month window; renew adds traffic and resets duration (first-use when enabled).
SERVICE_MAX_DAYS = 30


@dataclass(frozen=True)
class RenewalQuote:
    base_amount: int
    renewal_discount: int
    final_amount: int
    discount_percent: int


def renewal_quote(plan_price: int, discount_percent: int | None = None) -> RenewalQuote:
    """Apply renewal discount to a plan list price (Toman)."""
    base = max(0, int(plan_price))
    pct = DEFAULT_RENEWAL_DISCOUNT_PERCENT if discount_percent is None else max(0, min(100, int(discount_percent)))
    discount = base * pct // 100
    final = max(0, base - discount)
    return RenewalQuote(
        base_amount=base,
        renewal_discount=discount,
        final_amount=final,
        discount_percent=pct,
    )
