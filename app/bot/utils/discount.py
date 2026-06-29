"""Discount-code validation and application."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiscountCode, DiscountUsage
from app.bot.utils.discount_limits import is_overall_exhausted, is_user_exhausted


@dataclass
class DiscountResult:
    code: DiscountCode | None
    error: str | None  # i18n error key
    discount_amount: int
    final_amount: int


async def validate_and_apply(
    session: AsyncSession,
    code_str: str,
    user_id: int,
    base_amount: int,
) -> DiscountResult:
    """
    Lookup the code, validate, and return the resulting amount.
    On failure, `code` is None and `error` is set to an i18n key inside `fa.ERRORS`.
    NOTE: This function does NOT mark the code as used — call `record_usage()` after the
    purchase actually succeeds.
    """
    if not code_str or not code_str.strip():
        return DiscountResult(None, "invalid_discount", 0, base_amount)

    code = await DiscountCode.get_by_code(session, code_str.strip())
    if code is None or not code.is_active:
        return DiscountResult(None, "invalid_discount", 0, base_amount)

    if code.expires_at and code.expires_at < datetime.utcnow():
        return DiscountResult(None, "invalid_discount", 0, base_amount)

    if is_overall_exhausted(code.used_count, code.max_uses):
        return DiscountResult(None, "invalid_discount", 0, base_amount)

    user_uses = await DiscountUsage.count_for_user(session, code.id, user_id)
    per_user_limit = getattr(code, "max_uses_per_user", 1)
    if is_user_exhausted(user_uses, per_user_limit):
        return DiscountResult(None, "discount_used", 0, base_amount)

    discount_amount = 0
    if code.discount_percent:
        discount_amount = base_amount * code.discount_percent // 100
    elif code.discount_amount:
        discount_amount = min(code.discount_amount, base_amount)
    final = max(0, base_amount - discount_amount)
    return DiscountResult(code, None, discount_amount, final)


async def record_usage(
    session: AsyncSession, code_id: int, user_id: int
) -> None:
    """Insert a discount_usage row and bump the code's used_count."""
    await DiscountUsage.create(session, code_id=code_id, user_id=user_id)
    await DiscountCode.bump_used(session, code_id)


def is_full_discount(result: DiscountResult, base_amount: int) -> bool:
    """True when the code fully covers base_amount (final payable is 0)."""
    return (
        result.code is not None
        and result.error is None
        and base_amount > 0
        and result.final_amount == 0
        and result.discount_amount >= base_amount
    )


def purchase_data_qualifies_for_free_claim(data: dict, *, base_amount: int) -> bool:
    """FSM snapshot check before showing the free-claim screen (not authoritative)."""
    if not data.get("discount_code") or not data.get("discount_id"):
        return False
    if base_amount <= 0:
        return False
    discount_amount = int(data.get("discount_amount", 0))
    final_amount = int(data.get("final_amount", base_amount))
    return final_amount == 0 and discount_amount >= base_amount


async def revalidate_free_claim(
    session: AsyncSession,
    *,
    code_str: str,
    user_id: int,
    base_amount: int,
    expected_code_id: int,
) -> DiscountResult:
    """
    Re-validate discount at claim time. Only succeeds for a still-valid 100% (or
    over-covering) code matching expected_code_id.
    """
    result = await validate_and_apply(session, code_str, user_id, base_amount)
    if result.error or result.code is None:
        return result
    if result.code.id != expected_code_id:
        return DiscountResult(None, "invalid_discount", 0, base_amount)
    if not is_full_discount(result, base_amount):
        return DiscountResult(None, "invalid_discount", result.discount_amount, result.final_amount)
    return result
