"""Build purchase-screen copy from plans.json tier settings."""
from __future__ import annotations

from app.bot.i18n import fa
from app.bot.utils.emoji import flag_i, i, p, resolve_icon

DEFAULT_VIP_LOCATIONS: list[dict[str, str]] = [
    {"code": "de", "name": "آلمان"},
    {"code": "pl", "name": "لهستان"},
    {"code": "sg", "name": "سنگاپور"},
    {"code": "us", "name": "آمریکا"},
]


def _location_flag(loc: dict) -> str:
    code = str(loc.get("code", "")).strip()
    legacy = str(loc.get("flag", "")).strip()
    token = code or legacy
    return flag_i(token) if token else ""


def format_locations_line(locations: list[dict] | None) -> str:
    """One location per line: flag + name (column layout)."""
    rows = locations or DEFAULT_VIP_LOCATIONS
    parts: list[str] = []
    for loc in rows:
        if not isinstance(loc, dict):
            continue
        name = str(loc.get("name", "")).strip()
        if not name:
            continue
        flag = _location_flag(loc)
        parts.append(f"{flag} {name}".strip() if flag else name)
    return "\n".join(parts)


def build_plans_table_header(tier: dict) -> str:
    emoji_key = str(tier.get("emoji_key", "globe")).strip() or "globe"
    name = str(tier.get("name", fa.VIP_TIER_NAME_DEFAULT)).strip() or fa.VIP_TIER_NAME_DEFAULT
    subtitle = str(tier.get("shop_subtitle", fa.VIP_PLANS_TABLE_SUBTITLE_DEFAULT)).strip()
    locations_line = format_locations_line(tier.get("locations"))
    lines = [f"{resolve_icon(emoji_key)} <b>{name}</b>"]
    if subtitle:
        lines.append("")
        lines.append(subtitle)
    if locations_line:
        lines.append(locations_line)
    return "\n".join(lines)


def build_plans_table_footer(tier: dict) -> str:
    custom = str(tier.get("shop_footer", "")).strip()
    if custom:
        return f"\n{p('down')}{custom}"
    return f"\n{fa.VIP_PLANS_TABLE_FOOTER_DEFAULT.strip()}"


def tier_button_label(tier: dict) -> str:
    name = str(tier.get("name", fa.VIP_TIER_NAME_DEFAULT)).strip()
    return name


def _plan_row_prefix(plan: dict) -> str:
    if plan.get("recommended"):
        return f"• {i('star')} "
    key = str(plan.get("emoji_key", "")).strip()
    if key:
        return f"{resolve_icon(key)} "
    return "· "


def render_plans_table(tier: dict, plans: list[dict]) -> str:
    from app.bot.utils.persian import format_toman, to_persian_digits

    rows = [build_plans_table_header(tier), ""]
    for plan in plans:
        prefix = _plan_row_prefix(plan)
        badge = " · (پیشنهادی)" if plan.get("recommended") else ""
        rows.append(
            fa.VIP_PLANS_TABLE_ROW.format(
                emoji=prefix,
                gb=to_persian_digits(plan["gb"]),
                days=to_persian_digits(plan["days"]),
                price=format_toman(plan["price"]),
                badge=badge,
            )
        )
    rows.append(build_plans_table_footer(tier))
    return "\n".join(rows)
