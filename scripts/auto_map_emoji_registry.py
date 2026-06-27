#!/usr/bin/env python3
"""Match emoji_registry.json entries to synced packs by Unicode `alt` / `fallback`.

Run after sync when indices are unknown or you switched sticker packs:

    python3 scripts/sync_emoji_packs.py
    python3 scripts/auto_map_emoji_registry.py
    python3 scripts/auto_map_emoji_registry.py --write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS_PATH = ROOT / "app" / "bot" / "i18n" / "emoji_ids.json"
REG_PATH = ROOT / "app" / "bot" / "i18n" / "emoji_registry.json"

PACKS = (
    "EmojiStatus",
    "tgmacicons",
    "vector_icons_by_fStikBot",
    "FlagsPack",
)

# Prefer these packs when the same alt exists in multiple sets
PACK_ORDER = {
    "flag_": "FlagsPack",
    "btn_": "vector_icons_by_fStikBot",
}


def _prefer_pack(key: str, current: str | None) -> str | None:
    for prefix, pack in PACK_ORDER.items():
        if key.startswith(prefix):
            return pack
    return current


def _find_match(ids: dict, alt: str, prefer: str | None) -> tuple[str, int] | None:
    search = [prefer] if prefer else []
    search += [p for p in PACKS if p != prefer]
    for pack in search:
        if not pack:
            continue
        for row in ids.get(pack, []):
            if str(row.get("alt", "")) == alt:
                return pack, int(row["index"])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Save emoji_registry.json")
    args = parser.parse_args()

    if not IDS_PATH.is_file():
        print(f"Missing {IDS_PATH} — run sync first", file=sys.stderr)
        return 1

    ids = json.loads(IDS_PATH.read_text(encoding="utf-8"))
    reg = json.loads(REG_PATH.read_text(encoding="utf-8"))

    missing: list[str] = []
    updated = 0

    for key, spec in reg.items():
        if key.startswith("_") or not isinstance(spec, dict):
            continue
        alt = str(spec.get("btn_fallback") or spec.get("fallback") or spec.get("alt") or "")
        if not alt:
            continue
        prefer = _prefer_pack(key, spec.get("pack"))
        hit = _find_match(ids, alt, prefer)
        if not hit:
            missing.append(f"{key} ({alt!r})")
            continue
        pack, index = hit
        if spec.get("pack") != pack or spec.get("index") != index:
            spec["pack"] = pack
            spec["index"] = index
            updated += 1
            print(f"  {key}: {pack}[{index}] ← {alt}")

    if missing:
        print("\nNot found in any pack (add fallback alt or pick index manually):", file=sys.stderr)
        for line in missing:
            print(f"  - {line}", file=sys.stderr)

    if args.write:
        REG_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=3) + "\n", encoding="utf-8")
        print(f"\nWrote {REG_PATH} ({updated} updated)")
    else:
        print(f"\nDry run: {updated} would update. Re-run with --write to save.")

    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
