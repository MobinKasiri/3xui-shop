"""Telegram custom emoji helpers (HTML + button icons)."""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_I18N = Path(__file__).resolve().parent.parent / "i18n"
REGISTRY_PATH = _I18N / "emoji_registry.json"
IDS_PATH = _I18N / "emoji_ids.json"


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
    """Return (total icons, pack count) from emoji_ids.json."""
    packs = _pack_ids()
    return sum(len(v) for v in packs.values()), len(packs)


def icon_id(key: str) -> str | None:
    """Custom emoji ID for inline-keyboard icon_custom_emoji_id."""
    if not _enabled():
        return None
    spec = _registry().get(key)
    if not spec or key.startswith("_"):
        return None
    pack = spec.get("pack", "")
    index = int(spec.get("index", -1))
    rows = _pack_ids().get(pack, [])
    if index < 0 or index >= len(rows):
        return None
    eid = rows[index].get("id") or ""
    return eid or None


def icon(key: str, fallback: str | None = None) -> str:
    """HTML fragment: custom emoji or Unicode fallback."""
    spec = _registry().get(key, {})
    fb = fallback if fallback is not None else spec.get("fallback", "⭐")
    eid = icon_id(key)
    if not eid:
        return fb
    return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'


def btn_label(key: str, text: str) -> str:
    """Button caption without duplicate Unicode icon (icon goes in icon_custom_emoji_id)."""
    if icon_id(key):
        return text
    spec = _registry().get(key, {})
    fb = spec.get("fallback", "")
    if fb and text.startswith(fb):
        return text[len(fb) :].lstrip()
    return text


class _Emoji:
    """Attribute access: E.rocket → icon HTML."""

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        return icon(name)


E = _Emoji()

# Short alias for fa.py string building
i = icon
