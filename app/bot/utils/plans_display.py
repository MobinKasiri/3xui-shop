"""Build purchase-screen copy from plans.json tier settings."""
from __future__ import annotations

from app.bot.i18n import fa


def format_locations_line(locations: list[dict] | None) -> str:
    if not locations:
        return fa.VIP_PLANS_TABLE_LOCATIONS_DEFAULT
    parts: list[str] = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        flag = str(loc.get("flag", "")).strip()
        name = str(loc.get("name", "")).strip()
        if not name:
            continue
        parts.append(f"{flag} {name}".strip())
    return " · ".join(parts) if parts else fa.VIP_PLANS_TABLE_LOCATIONS_DEFAULT


def build_plans_table_header(tier: dict) -> str:
    emoji = str(tier.get("emoji", "🌍")).strip() or "🌍"
    name = str(tier.get("name", fa.VIP_TIER_NAME_DEFAULT)).strip() or fa.VIP_TIER_NAME_DEFAULT
    subtitle = str(tier.get("shop_subtitle", fa.VIP_PLANS_TABLE_SUBTITLE_DEFAULT)).strip()
    locations_line = format_locations_line(tier.get("locations"))
    lines = [f"{emoji} <b>{name}</b>"]
    if subtitle:
        lines.append("")
        lines.append(subtitle)
    if locations_line:
        lines.append(locations_line)
    return "\n".join(lines)


def build_plans_table_footer(tier: dict) -> str:
    footer = str(tier.get("shop_footer", fa.VIP_PLANS_TABLE_FOOTER_DEFAULT)).strip()
    return f"\n{footer}" if footer else ""


def tier_button_label(tier: dict) -> str:
    emoji = str(tier.get("emoji", "🌍")).strip()
    name = str(tier.get("name", fa.VIP_TIER_NAME_DEFAULT)).strip()
    return f"{emoji} {name}".strip()


def render_plans_table(tier: dict, plans: list[dict]) -> str:
    from app.bot.utils.persian import format_toman, to_persian_digits

    rows = [build_plans_table_header(tier), ""]
    for plan in plans:
        emoji = plan.get("emoji", "")
        if plan.get("recommended"):
            prefix = "⭐ "
            badge = " · (پیشنهادی)"
        elif emoji:
            prefix = f"{emoji} "
            badge = ""
        else:
            prefix = "▫️ "
            badge = ""
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
