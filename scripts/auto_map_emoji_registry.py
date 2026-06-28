#!/usr/bin/env python3
"""Match emoji_registry.json entries to synced emoji_ids.json.

Prefers colorful packs (EmojiStatus, vector_icons_by_fStikBot) over white tgmacicons.

    python3 scripts/sync_emoji_packs.py
    python3 scripts/auto_map_emoji_registry.py          # dry run
    python3 scripts/auto_map_emoji_registry.py --write  # save (usually on dev, not server)

On the server: keep emoji_registry.json from git; only emoji_ids.json is generated live.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS_PATH = ROOT / "app" / "bot" / "i18n" / "emoji_ids.json"
REG_PATH = ROOT / "app" / "bot" / "i18n" / "emoji_registry.json"
VERIFIED_PATH = ROOT / "scripts" / "verified_emoji_indices.json"

PACKS = (
    "EmojiStatus",
    "vector_icons_by_fStikBot",
    "tgmacicons",
    "FlagsPack",
    "NewsEmoji",
    "EmojiAirdrops",
)

KEY_PACK_HINTS: dict[str, str] = {
    "flag_": "FlagsPack",
    "os_": "EmojiStatus",
    "btn_": "EmojiStatus",
    "home": "EmojiStatus",
    "back": "EmojiStatus",
}


def _normalize_alt(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.strip())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


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


def _load_ids() -> tuple[dict, Path]:
    candidates: list[Path] = []
    data_host = _load_data_host()
    if data_host:
        candidates.append(data_host / "emoji_ids.json")
    candidates.append(IDS_PATH)
    candidates.append(Path("/opt/nexoranode-data/emoji_ids.json"))

    best: dict = {}
    best_path = IDS_PATH
    best_count = -1
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        count = sum(len(v) for v in data.values() if isinstance(v, list))
        if count > best_count:
            best_count = count
            best = data
            best_path = path

    if best_count <= 0:
        print("No emoji IDs found — run: python3 scripts/sync_emoji_packs.py", file=sys.stderr)
        sys.exit(1)
    return best, best_path


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
        rest = [p for p in PACKS if p != prefer]
        return (prefer, *rest)
    return PACKS


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


def _existing_valid(spec: dict, ids: dict, alts: list[str]) -> tuple[str, int] | None:
    pack = spec.get("pack")
    idx = spec.get("index")
    if not pack or idx is None:
        return None
    rows = ids.get(pack, [])
    if not isinstance(rows, list) or idx >= len(rows):
        return None
    row = rows[idx]
    if not row.get("id"):
        return None
    # Reject stale mappings: index must still match a known fallback/search alt
    if alts:
        sticker_alt = str(row.get("alt", ""))
        if sticker_alt:
            normalized_alts = {_normalize_alt(a) for a in alts if a}
            if _normalize_alt(sticker_alt) not in normalized_alts:
                return None
    return pack, int(idx)


def _find_match(ids: dict, alts: list[str], pack_order: tuple[str, ...]) -> tuple[str, int] | None:
    normalized_alts = [_normalize_alt(a) for a in alts if a]
    for pack in pack_order:
        for row in ids.get(pack, []):
            raw_alt = str(row.get("alt", ""))
            if not raw_alt:
                continue
            norm = _normalize_alt(raw_alt)
            if raw_alt in alts or norm in normalized_alts:
                return pack, int(row["index"])
    # Fallback: any pack, any alt match
    for alt in alts:
        norm = _normalize_alt(alt)
        for pack in PACKS:
            for row in ids.get(pack, []):
                raw_alt = str(row.get("alt", ""))
                if raw_alt == alt or _normalize_alt(raw_alt) == norm:
                    return pack, int(row["index"])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Save emoji_registry.json")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Write registry even when nothing changed (default: skip if 0 updates)",
    )
    args = parser.parse_args()

    ids, ids_path = _load_ids()
    total = sum(len(v) for v in ids.values() if isinstance(v, list))
    print(f"Using {ids_path} ({total} icons)")

    reg = json.loads(REG_PATH.read_text(encoding="utf-8"))
    locked_keys: set[str] = set()
    if VERIFIED_PATH.is_file():
        verified = json.loads(VERIFIED_PATH.read_text(encoding="utf-8"))
        locked_keys = {k for k, v in verified.items() if isinstance(v, dict) and not k.startswith("_")}

    missing: list[str] = []
    updated = 0
    kept = 0

    for key, spec in reg.items():
        if key.startswith("_") or not isinstance(spec, dict):
            continue
        if spec.get("locked") or key in locked_keys:
            kept += 1
            continue
        alts = _alts_for(spec)
        if not alts:
            continue

        existing = _existing_valid(spec, ids, alts)
        if existing:
            pack, index = existing
            if spec.get("pack") != pack or spec.get("index") != index:
                spec["pack"] = pack
                spec["index"] = index
                updated += 1
            else:
                kept += 1
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
        print(f"\nNot found ({len(missing)}) — will keep registry fallback / prior index:", file=sys.stderr)
        for line in missing[:15]:
            print(f"  - {line}", file=sys.stderr)
        if len(missing) > 15:
            print(f"  ... and {len(missing) - 15} more", file=sys.stderr)

    print(f"\nKept {kept} existing mappings, updated {updated}, missing {len(missing)}")

    if args.write:
        if updated == 0 and not args.force:
            print("No changes — registry not written (use --force to save anyway)")
        else:
            REG_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=3) + "\n", encoding="utf-8")
            print(f"Wrote {REG_PATH}")
    else:
        print("Dry run — re-run with --write to save")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
