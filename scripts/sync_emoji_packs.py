#!/usr/bin/env python3
"""Fetch custom emoji IDs from Telegram and write app/bot/i18n/emoji_ids.json.

Allowed packs (bot owner must add all via t.me/addemoji/…):
  - EmojiStatus
  - tgmacicons
  - vector_icons_by_fStikBot
  - FlagsPack

Requires BOT_TOKEN + Telegram Premium on the BotFather bot owner account.

Usage:
    cd /opt/nexoranode-bot
    python3 scripts/sync_emoji_packs.py
    python3 scripts/auto_map_emoji_registry.py --write
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
    "EmojiStatus",
    "tgmacicons",
    "vector_icons_by_fStikBot",
    "FlagsPack",
)

ADD_LINKS = {
    "EmojiStatus": "https://t.me/addemoji/EmojiStatus",
    "tgmacicons": "https://t.me/addemoji/tgmacicons",
    "vector_icons_by_fStikBot": "https://t.me/addemoji/vector_icons_by_fStikBot",
    "FlagsPack": "https://t.me/addemoji/FlagsPack",
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


def _load_data_host() -> Path | None:
    host = os.environ.get("BOT_DATA_HOST", "").strip()
    if host:
        return Path(host)
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key.strip() == "BOT_DATA_HOST":
                v = val.strip().strip('"').strip("'")
                return Path(v) if v else None
    return None


def _write_outputs(result: dict) -> list[Path]:
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    paths = [OUT]
    data_host = _load_data_host()
    if data_host:
        live = data_host / "emoji_ids.json"
        paths.append(live)
    written: list[Path] = []
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        written.append(path)
    return written


def _print_setup_help() -> None:
    print("\nCustom emoji setup checklist:", file=sys.stderr)
    print("  1. Telegram Premium on the BotFather bot OWNER account", file=sys.stderr)
    print("  2. Add each pack on that account:", file=sys.stderr)
    for link in ADD_LINKS.values():
        print(f"     {link}", file=sys.stderr)
    print("  3. python3 scripts/sync_emoji_packs.py", file=sys.stderr)
    print("  4. python3 scripts/auto_map_emoji_registry.py --write", file=sys.stderr)
    print("  5. ./deploy/compose.sh up -d --build bot", file=sys.stderr)


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
            if "STICKERSET_INVALID" in str(exc):
                print(f"Add pack: {ADD_LINKS.get(pack, pack)}", file=sys.stderr)
            _print_setup_help()
            return 1
        ids = [r["id"] for r in rows if r.get("id")]
        if not ids:
            print(
                f"{pack}: 0 custom emoji IDs — add: {ADD_LINKS[pack]}",
                file=sys.stderr,
            )
            _print_setup_help()
            return 1
        result[pack] = rows
        print(f"{pack}: {len(rows)} emoji ({len(ids)} with IDs)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    written = _write_outputs(result)
    total = sum(len(v) for v in result.values())
    for path in written:
        print(f"Wrote {path} ({total} icons)")
    print("Next: python3 scripts/auto_map_emoji_registry.py --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
