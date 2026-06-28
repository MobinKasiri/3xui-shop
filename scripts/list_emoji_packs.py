#!/usr/bin/env python3
"""Print every sticker in the configured emoji packs (index → alt → custom_emoji_id).

Use this to pick the right `index` when editing emoji_registry.json.

Usage:
    cd /opt/nexoranode-bot
    python3 scripts/sync_emoji_packs.py      # fetch IDs first
    python3 scripts/list_emoji_packs.py
    python3 scripts/list_emoji_packs.py --pack FlagsPack --grep 🇩🇪
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from auto_map_emoji_registry import _load_ids  # noqa: E402

PACKS = (
    "EmojiStatus",
    "tgmacicons",
    "vector_icons_by_fStikBot",
    "FlagsPack",
    "NewsEmoji",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="List synced custom emoji packs")
    parser.add_argument("--pack", choices=PACKS, help="Show only one pack")
    parser.add_argument("--grep", help="Filter rows where alt contains this text")
    args = parser.parse_args()

    try:
        data, ids_path = _load_ids()
    except SystemExit:
        print("Missing emoji_ids.json — run: python3 scripts/sync_emoji_packs.py", file=sys.stderr)
        return 1

    print(f"Source: {ids_path}\n")
    packs = [args.pack] if args.pack else PACKS
    needle = (args.grep or "").strip()

    total = 0
    for pack in packs:
        rows = data.get(pack, [])
        if not isinstance(rows, list) or not rows:
            print(f"\n## {pack}\n  (empty — add pack on bot owner account + re-sync)\n")
            continue
        print(f"\n## {pack} ({len(rows)} icons)")
        print(f"{'idx':>4}  {'alt':<8}  id")
        print("-" * 56)
        for row in rows:
            alt = str(row.get("alt", ""))
            if needle and needle not in alt:
                continue
            idx = row.get("index", "?")
            eid = row.get("id", "")
            print(f"{idx:>4}  {alt:<8}  {eid}")
            total += 1

    if total == 0 and needle:
        print(f"\nNo rows matched {needle!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
