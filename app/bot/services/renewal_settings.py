"""Renewal discount settings — loaded from shared renewal.json (panel-editable)."""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_RENEWAL_DISCOUNT_PERCENT = 10

DEFAULT_RENEWAL: dict[str, Any] = {
    "discount_percent": DEFAULT_RENEWAL_DISCOUNT_PERCENT,
}


def resolve_renewal_file(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return data_dir / "renewal.json"
    return Path(__file__).resolve().parents[2] / "data" / "renewal.json"


def _merge_defaults(raw: dict | None) -> dict[str, Any]:
    base = deepcopy(DEFAULT_RENEWAL)
    if not isinstance(raw, dict):
        return base
    if "discount_percent" in raw:
        pct = int(raw.get("discount_percent") or 0)
        base["discount_percent"] = max(0, min(100, pct))
    return base


def resolve_data_dir(data_dir: Path | None = None) -> Path | None:
    """Shared bot/panel data directory (parent of plans.json)."""
    if data_dir is not None:
        return data_dir
    import os

    pf = os.environ.get("PLANS_FILE", "").strip()
    if pf:
        return Path(pf).parent
    return None


def load_renewal_settings(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = resolve_data_dir(data_dir)
    path = resolve_renewal_file(data_dir)
    if not path.is_file():
        example = path.parent / "renewal.example.json"
        if example.is_file():
            try:
                with example.open(encoding="utf-8") as fh:
                    return _merge_defaults(json.load(fh))
            except (OSError, json.JSONDecodeError):
                pass
        return deepcopy(DEFAULT_RENEWAL)
    try:
        with path.open(encoding="utf-8") as fh:
            return _merge_defaults(json.load(fh))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load renewal settings from %s: %s", path, exc)
        return deepcopy(DEFAULT_RENEWAL)


def save_renewal_settings(data: dict, data_dir: Path | None = None) -> Path:
    path = resolve_renewal_file(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = _merge_defaults(data)
    tmp = path.parent / f".{path.name}.tmp"
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
        fh.flush()
    tmp.replace(path)
    return path


@dataclass
class RenewalSettingsView:
    data: dict[str, Any] = field(default_factory=lambda: deepcopy(DEFAULT_RENEWAL))
    data_dir: Path | None = None
    _mtime: float = 0.0

    def reload_if_changed(self) -> None:
        path = resolve_renewal_file(self.data_dir)
        if not path.is_file():
            return
        try:
            mtime = path.stat().st_mtime
            if mtime == self._mtime and self.data:
                return
            self.data = load_renewal_settings(self.data_dir)
            self._mtime = mtime
        except OSError:
            pass

    @property
    def discount_percent(self) -> int:
        self.reload_if_changed()
        return int(self.data.get("discount_percent") or DEFAULT_RENEWAL_DISCOUNT_PERCENT)


def renewal_settings_for_config(config) -> RenewalSettingsView:
    data_dir = resolve_data_dir(None)
    if config and getattr(config, "pricing", None):
        pf = getattr(config.pricing, "plans_file", None)
        if pf is not None:
            data_dir = Path(pf).parent
    view = RenewalSettingsView(data=load_renewal_settings(data_dir), data_dir=data_dir)
    if data_dir:
        path = resolve_renewal_file(data_dir)
        if path.is_file():
            try:
                view._mtime = path.stat().st_mtime
            except OSError:
                pass
    return view
