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
    return raw not in {"0", "false", "no", "off"}


@lru_cache(maxsize=1)
def _registry() -> dict[str, dict]:
    if not REGISTRY_PATH.is_file():
        return {}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _pack_ids() -> dict[str, list[dict]]:
    if not IDS_PATH.is_file():
        return {}
    try:
        return json.loads(IDS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid emoji_ids.json — run scripts/sync_emoji_packs.py")
        return {}


def reload_emoji_cache() -> None:
    _registry.cache_clear()
    _pack_ids.cache_clear()


def count_loaded() -> tuple[int, int]:
    packs = _pack_ids()
    return sum(len(v) for v in packs.values()), len(packs)


def _spec(key: str) -> dict:
    spec = _registry().get(key, {})
    if key.startswith("_") or not spec:
        return {}
    return spec


def icon_fallback(key: str) -> str:
    return str(_spec(key).get("fallback", ""))


def btn_icon_fallback(key: str) -> str:
    """Minimal emoji for main-menu buttons when vector icons are not synced."""
    spec = _spec(key)
    if not spec:
        return ""
    return str(spec.get("btn_fallback") or spec.get("fallback", ""))


def icon_id(key: str) -> str | None:
    if not _enabled():
        return None
    spec = _spec(key)
    if not spec:
        return None
    pack = spec.get("pack", "")
    index = int(spec.get("index", -1))
    rows = _pack_ids().get(pack, [])
    if index < 0 or index >= len(rows):
        return None
    eid = rows[index].get("id") or ""
    return eid or None


def i(key: str, fallback: str | None = None) -> str:
    """HTML vector emoji when synced; otherwise one Unicode emoji (or empty)."""
    fb = fallback if fallback is not None else icon_fallback(key)
    eid = icon_id(key)
    if eid:
        alt = str(_spec(key).get("alt") or fb or "·")
        return f'<tg-emoji emoji-id="{eid}">{alt}</tg-emoji>'
    return fb


def p(key: str) -> str:
    """Prefix for messages: icon + space, or empty."""
    s = i(key)
    return f"{s} " if s else ""


def strip_html_emoji(text: str) -> str:
    """Remove tg-emoji HTML — invalid inside inline-keyboard button labels."""
    return _TG_EMOJI_RE.sub("", text).strip()


def plain_share_text(text: str) -> str:
    """Plain text for t.me/share/url — Telegram shows HTML tags literally there."""
    return plain_alert_text(text)


def plain_alert_text(text: str) -> str:
    """Telegram callback alerts are plain text only — strip HTML and custom emoji tags."""
    import html

    text = re.sub(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def u(key: str) -> str:
    """Unicode emoji for buttons (never HTML)."""
    spec = _spec(key)
    if not spec:
        return ""
    if key.startswith("btn_"):
        return str(spec.get("fallback") or spec.get("btn_fallback") or "")
    return str(spec.get("fallback") or "")


def btn_label(key: str | None, text: str) -> str:
    """Plain button text + Unicode emoji at end (RTL). Never emits HTML."""
    plain = strip_html_emoji(text)
    if not key:
        return plain
    emoji = u(key)
    if not emoji:
        return plain
    if plain.endswith(emoji):
        return plain
    if plain.startswith(emoji):
        plain = plain[len(emoji) :].strip()
    return f"{plain} {emoji}"


def button_vector_icons_enabled() -> bool:
    """Vector icons on inline buttons (Bot API 9.4). Off by default."""
    raw = os.environ.get("USE_BUTTON_VECTOR_ICONS", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class _Emoji:
    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        return i(name)


E = _Emoji()
