#!/usr/bin/env python3
"""Match emoji_registry.json entries to synced packs (prefer colorful EmojiStatus / vector).

    python3 scripts/sync_emoji_packs.py
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

# Colorful animated first; tgmacicons (often white) last
PACKS_COLORFUL = (
    "EmojiStatus",
    "vector_icons_by_fStikBot",
    "tgmacicons",
    "FlagsPack",
)

KEY_PACK_HINTS: dict[str, str] = {
    "flag_": "FlagsPack",
    "os_": "EmojiStatus",
    "btn_": "EmojiStatus",
    "home": "EmojiStatus",
    "back": "EmojiStatus",
}


def _ids_path() -> Path:
    data = Path("/opt/nexoranode-data/emoji_ids.json")
    if data.is_file():
        return data
    live = IDS_PATH
    if live.is_file() and json.loads(live.read_text()).get("EmojiStatus"):
        return live
    return IDS_PATH


def _pack_order(key: str, spec: dict) -> tuple[str, ...]:
    prefer = spec.get("pack_prefer") or KEY_PACK_HINTS.get(key)
    if not prefer:
        for prefix, pack in KEY_PACK_HINTS.items():
            if prefix.endswith("_") and key.startswith(prefix):
                prefer = pack
                break
            if key == prefix:
                prefer = pack
                break
    if prefer:
        rest = [p for p in PACKS_COLORFUL if p != prefer]
        return (prefer, *rest)
    return PACKS_COLORFUL


def _alts_for(spec: dict) -> list[str]:
    seen: list[str] = []
    for raw in (
        spec.get("btn_fallback"),
        spec.get("fallback"),
        spec.get("alt"),
        *(spec.get("search") or []),
    ):
        s = str(raw or "").strip()
        if s and s not in seen:
            seen.append(s)
    return seen


def _find_match(ids: dict, alts: list[str], pack_order: tuple[str, ...]) -> tuple[str, int] | None:
    for alt in alts:
        for pack in pack_order:
            for row in ids.get(pack, []):
                if str(row.get("alt", "")) == alt:
                    return pack, int(row["index"])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Save emoji_registry.json")
    args = parser.parse_args()

    path = _ids_path()
    if not path.is_file():
        print(f"Missing {path} — run sync first", file=sys.stderr)
        return 1

    ids = json.loads(path.read_text(encoding="utf-8"))
    reg = json.loads(REG_PATH.read_text(encoding="utf-8"))

    missing: list[str] = []
    updated = 0

    for key, spec in reg.items():
        if key.startswith("_") or not isinstance(spec, dict):
            continue
        alts = _alts_for(spec)
        if not alts:
            continue
        order = _pack_order(key, spec)
        hit = _find_match(ids, alts, order)
        if not hit:
            missing.append(f"{key} ({alts[0]!r})")
            continue
        pack, index = hit
        if spec.get("pack") != pack or spec.get("index") != index:
            spec["pack"] = pack
            spec["index"] = index
            updated += 1
            print(f"  {key}: {pack}[{index}] ← {alts[0]}")

    if missing:
        print("\nNot found (add search[] alt or set index manually):", file=sys.stderr)
        for line in missing:
            print(f"  - {line}", file=sys.stderr)

    if args.write:
        REG_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=3) + "\n", encoding="utf-8")
        print(f"\nWrote {REG_PATH} ({updated} updated)")
    else:
        print(f"\nDry run: {updated} would update. Re-run with --write to save.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
