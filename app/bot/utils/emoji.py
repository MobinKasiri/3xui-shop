"""Telegram custom emoji: vector icons when synced, Unicode emoji fallback otherwise."""
from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_I18N = Path(__file__).resolve().parent.parent / "i18n"
REGISTRY_PATH = _I18N / "emoji_registry.json"
IDS_PATH = _I18N / "emoji_ids.json"

_TG_EMOJI_RE = re.compile(r"<tg-emoji[^>]*>.*?</tg-emoji>", re.DOTALL)


def _enabled() -> bool:
    raw = os.environ.get("USE_CUSTOM_EMOJI", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


@lru_cache(maxsize=1)
def _registry() -> dict:
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Invalid emoji_registry.json")
        return {"icons": {}}


@lru_cache(maxsize=1)
def _ids() -> dict[str, list[dict]]:
    try:
        return json.loads(IDS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Invalid emoji_ids.json — run scripts/sync_emoji_packs.py")
        return {}


def reload_emoji_cache() -> None:
    _registry.cache_clear()
    _ids.cache_clear()


def count_loaded() -> tuple[int, int]:
    data = _ids()
    total = sum(len(v) for v in data.values() if isinstance(v, list))
    packs = sum(1 for v in data.values() if isinstance(v, list) and v)
    return total, packs


def custom_emoji_ready() -> bool:
    total, _ = count_loaded()
    return _enabled() and total > 0


def _icon_spec(key: str) -> dict | None:
    data = _registry()
    spec = data.get(key)
    if isinstance(spec, dict) and "pack" in spec:
        return spec
    icons = data.get("icons")
    if isinstance(icons, dict):
        spec = icons.get(key)
        if isinstance(spec, dict):
            return spec
    return None


def icon_id(key: str) -> str | None:
    if not _enabled():
        return None
    spec = _icon_spec(key)
    if not spec:
        return None
    pack = spec.get("pack")
    idx = spec.get("index")
    if pack is None or idx is None:
        return None
    rows = _ids().get(pack, [])
    if not isinstance(rows, list) or idx >= len(rows):
        return None
    eid = rows[idx].get("id")
    return eid if eid else None


def icon_fallback(key: str) -> str:
    spec = _icon_spec(key)
    if not spec:
        return ""
    return spec.get("fallback") or spec.get("btn_fallback") or ""


def btn_icon_fallback(key: str) -> str:
    spec = _icon_spec(key)
    if not spec:
        return ""
    return spec.get("btn_fallback") or spec.get("fallback") or ""


def u(key: str) -> str:
    """Unicode emoji for buttons (never HTML)."""
    if key.startswith("btn_"):
        return btn_icon_fallback(key)
    return icon_fallback(key)


def i(key: str) -> str:
    """Inline custom emoji in HTML messages, or Unicode fallback."""
    fb = icon_fallback(key)
    eid = icon_id(key)
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{fb or "⭐"}</tg-emoji>'
    return fb


def p(key: str) -> str:
    """Paragraph prefix: custom emoji + space, or Unicode + space."""
    fb = icon_fallback(key)
    eid = icon_id(key)
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{fb or "⭐"}</tg-emoji> '
    return f"{fb} " if fb else ""


def strip_html_emoji(text: str) -> str:
    return _TG_EMOJI_RE.sub("", text).strip()


def _strip_leading_emoji(text: str, marker: str) -> str:
    if not marker:
        return text.strip()
    t = text.strip()
    if t.startswith(marker):
        return t[len(marker) :].strip()
    return t


def btn_label(key: str | None, text: str) -> str:
    """Button text: vector icon when synced, Unicode emoji prefix otherwise."""
    text = text.strip()
    if not key:
        return text
    fb = btn_icon_fallback(key) if key.startswith("btn_") else icon_fallback(key)
    use_vector = (
        button_vector_icons_enabled()
        and custom_emoji_ready()
        and bool(icon_id(key))
    )
    if use_vector:
        return _strip_leading_emoji(text, fb)
    plain = _strip_leading_emoji(text, fb)
    if fb:
        return f"{fb} {plain}".strip()
    return text


def button_vector_icons_enabled() -> bool:
    """Auto-on when emoji IDs are synced; set USE_BUTTON_VECTOR_ICONS=0 to disable."""
    raw = os.environ.get("USE_BUTTON_VECTOR_ICONS", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return custom_emoji_ready()
