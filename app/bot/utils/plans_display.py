"""Build purchase-screen copy from plans.json tier settings."""
from __future__ import annotations

from app.bot.i18n import fa
from app.bot.utils.emoji import flag_i, p, resolve_icon

DEFAULT_VIP_LOCATIONS: list[dict[str, str]] = [
    {"code": "de", "name": "آلمان"},
    {"code": "pl", "name": "لهستان"},
    {"code": "sg", "name": "سنگاپور"},
    {"code": "us", "name": "آمریکا"},
]

VIP_FOOTER_TEXT = "پلن مورد نظر را انتخاب کنید:"


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


def build_plans_picker_footer(tier: dict) -> str:
    """Single down icon + footer line (plans are chosen via buttons only)."""
    custom = str(tier.get("shop_footer", "")).strip()
    line = custom or VIP_FOOTER_TEXT
    for ch in ("👇", "⬇", "⬇️", "🔽"):
        if line.startswith(ch):
            line = line[len(ch) :].strip()
    return f"\n{p('down')}{line}"


def render_plans_picker_text(tier: dict) -> str:
    """VIP / renew plan picker — header + locations + footer; no plan rows in message."""
    return build_plans_table_header(tier) + build_plans_picker_footer(tier)


def render_plans_table(tier: dict, plans: list[dict]) -> str:
    """Legacy full table (admin/debug); purchase UI uses render_plans_picker_text."""
    return render_plans_picker_text(tier)
