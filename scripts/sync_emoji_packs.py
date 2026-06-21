#!/usr/bin/env python3
"""Fetch custom emoji IDs from Telegram and write app/bot/i18n/emoji_ids.json.

Requires BOT_TOKEN in environment or .env (repo root).

Usage:
    cd /opt/nexoranode-bot
    python scripts/sync_emoji_packs.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "bot" / "i18n" / "emoji_ids.json"

PACKS = (
    "adapted_gem_pay",
    "vector_icons_by_fStikBot",
    "IconsPack2",
    "EmojiTechPack",
)


def _load_token() -> str:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        return token
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key.strip() == "BOT_TOKEN":
                return val.strip().strip('"').strip("'")
    return ""


def fetch_pack(token: str, name: str) -> list[dict]:
    url = f"https://api.telegram.org/bot{token}/getStickerSet?name={name}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = json.load(resp)
    if not data.get("ok"):
        raise RuntimeError(f"{name}: {data.get('description', data)}")
    stickers = data["result"]["stickers"]
    rows: list[dict] = []
    for i, sticker in enumerate(stickers):
        rows.append(
            {
                "index": i,
                "alt": sticker.get("emoji", ""),
                "id": sticker.get("custom_emoji_id", ""),
            }
        )
    return rows


def main() -> int:
    token = _load_token()
    if not token:
        print("BOT_TOKEN not set", file=sys.stderr)
        return 1

    result: dict[str, list[dict]] = {}
    for pack in PACKS:
        try:
            rows = fetch_pack(token, pack)
        except urllib.error.HTTPError as exc:
            print(f"HTTP error for {pack}: {exc}", file=sys.stderr)
            return 1
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 1
        result[pack] = rows
        print(f"{pack}: {len(rows)} emoji")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
