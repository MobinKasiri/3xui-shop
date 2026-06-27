#!/usr/bin/env python3
"""Fetch custom emoji IDs from Telegram and write app/bot/i18n/emoji_ids.json.

Requires:
  - BOT_TOKEN in environment or .env (repo root)
  - Bot owner account has Telegram Premium
  - Bot owner added all emoji packs (links printed on failure)

Usage:
    cd /opt/nexoranode-bot
    python3 scripts/sync_emoji_packs.py
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

ADD_LINKS = {
    "adapted_gem_pay": "https://t.me/addemoji/adapted_gem_pay",
    "vector_icons_by_fStikBot": "https://t.me/addemoji/vector_icons_by_fStikBot",
    "IconsPack2": "https://t.me/addemoji/IconsPack2",
    "EmojiTechPack": "https://t.me/addemoji/EmojiTechPack",
}


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


def _print_setup_help() -> None:
    print("\nCustom emoji setup checklist:", file=sys.stderr)
    print("  1. Telegram Premium on the BotFather bot OWNER account (not channel admin)", file=sys.stderr)
    print("  2. Log into that account on phone/desktop and add each pack:", file=sys.stderr)
    for pack, link in ADD_LINKS.items():
        print(f"     {link}", file=sys.stderr)
    print("  3. Re-run: python3 scripts/sync_emoji_packs.py", file=sys.stderr)
    print("  4. Rebuild bot: ./deploy/compose.sh up -d --build bot", file=sys.stderr)


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
            if exc.code == 401:
                print("HTTP 401 Unauthorized — check BOT_TOKEN in .env", file=sys.stderr)
            else:
                print(f"HTTP error for {pack}: {exc}", file=sys.stderr)
            _print_setup_help()
            return 1
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            if "STICKERSET_INVALID" in str(exc) or "not found" in str(exc).lower():
                print(f"Add pack: {ADD_LINKS.get(pack, pack)}", file=sys.stderr)
            _print_setup_help()
            return 1
        ids = [r["id"] for r in rows if r.get("id")]
        if not ids:
            print(
                f"{pack}: 0 custom emoji IDs — bot owner needs Premium + add pack: {ADD_LINKS[pack]}",
                file=sys.stderr,
            )
            _print_setup_help()
            return 1
        result[pack] = rows
        print(f"{pack}: {len(rows)} emoji ({len(ids)} with IDs)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    total = sum(len(v) for v in result.values())
    print(f"Wrote {OUT} ({total} icons)")
    print("Next: git add app/bot/i18n/emoji_ids.json && rebuild bot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
