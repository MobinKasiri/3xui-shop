#!/usr/bin/env python3
"""Apply server-verified pack+index into emoji_registry.json (keeps fallback/alt fields).

    python3 scripts/apply_verified_emoji_map.py
    python3 scripts/apply_verified_emoji_map.py --check   # validate against synced ids
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG_PATH = ROOT / "app" / "bot" / "i18n" / "emoji_registry.json"
VERIFIED_PATH = ROOT / "scripts" / "verified_emoji_indices.json"

# Reuse auto_map id loader
sys.path.insert(0, str(ROOT / "scripts"))
from auto_map_emoji_registry import _load_ids, _normalize_alt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Validate indices exist in synced ids")
    args = parser.parse_args()

    verified = json.loads(VERIFIED_PATH.read_text(encoding="utf-8"))
    reg = json.loads(REG_PATH.read_text(encoding="utf-8"))
    ids = None
    if args.check:
        ids, ids_path = _load_ids()
        print(f"Checking against {ids_path}")

    updated = 0
    for key, vi in verified.items():
        if key.startswith("_") or not isinstance(vi, dict):
            continue
        if key not in reg or not isinstance(reg[key], dict):
            continue
        pack = vi["pack"]
        index = vi["index"]
        for field in ("fallback", "alt", "btn_fallback", "search"):
            if field in vi:
                reg[key][field] = vi[field]
        if args.check and ids is not None:
            rows = ids.get(pack, [])
            if index >= len(rows) or not rows[index].get("id"):
                print(f"  MISSING: {key} → {pack}[{index}]", file=sys.stderr)
                continue
            alt = str(rows[index].get("alt", ""))
            spec = reg[key]
            expected = [
                spec.get("fallback"),
                spec.get("btn_fallback"),
                spec.get("alt"),
                *(spec.get("search") or []),
            ]
            norms = {_normalize_alt(str(x)) for x in expected if x}
            if alt and norms and _normalize_alt(alt) not in norms:
                print(f"  NOTE: {key} → {pack}[{index}] alt={alt!r} (visual pick, not unicode match)")
        if reg[key].get("pack") != pack or reg[key].get("index") != index:
            reg[key]["pack"] = pack
            reg[key]["index"] = index
            updated += 1
            print(f"  {key}: {pack}[{index}]")
        if not reg[key].get("locked"):
            reg[key]["locked"] = True
            updated += 1

    REG_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=3) + "\n", encoding="utf-8")
    print(f"\nUpdated {updated} keys in {REG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
