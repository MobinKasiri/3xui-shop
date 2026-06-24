"""Festival / promotion campaign settings — panel-editable festival.json."""
from __future__ import annotations

import json
import logging
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DELIVERY_ON_START = "on_start"
DELIVERY_AT_PURCHASE = "at_purchase"

DEFAULT_FESTIVAL: dict[str, Any] = {
    "enabled": False,
    "campaign_id": None,
    "title": "جشنواره ویژه",
    "max_users": 20,
    "discount_percent": 50,
    "discount_amount": None,
    "valid_days": 14,
    "code_prefix": "JSH",
    "delivery_mode": DELIVERY_ON_START,
    "new_users_only": False,
    "starts_at": None,
    "ends_at": None,
    "texts": {
        "welcome_granted": (
            "🎉 <b>{title}</b>\n\n"
            "شما جزو <b>{slot}</b> کاربر اول هستید!\n"
            "کد تخفیف اختصاصی شما:\n"
            "<code>{code}</code>\n\n"
            "🎁 <b>{discount_label}</b> — تا <b>{valid_days}</b> روز اعتبار دارد.\n"
            "در مرحله خرید این کد را وارد کنید."
        ),
        "welcome_pending": (
            "🎉 <b>{title}</b>\n\n"
            "شما جزو <b>{slot}</b> کاربر اول هستید!\n"
            "🎁 <b>{discount_label}</b> برای شما رزرو شده.\n\n"
            "هنگام خرید سرویس، در مرحله «کد تخفیف» می‌توانید از تخفیف جشنواره استفاده کنید."
        ),
        "purchase_hint": (
            "🎉 <b>تخفیف جشنواره شما</b>\n\n"
            "کد: <code>{code}</code>\n"
            "🎁 {discount_label}\n\n"
            "برای اعمال خودکار دکمه زیر را بزنید."
        ),
    },
}


def resolve_festival_file(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return data_dir / "festival.json"
    return Path(__file__).resolve().parents[2] / "data" / "festival.json"


def _merge_defaults(raw: dict | None) -> dict[str, Any]:
    base = deepcopy(DEFAULT_FESTIVAL)
    if not isinstance(raw, dict):
        return base

    for key in (
        "enabled",
        "campaign_id",
        "title",
        "max_users",
        "discount_percent",
        "discount_amount",
        "valid_days",
        "code_prefix",
        "delivery_mode",
        "new_users_only",
        "starts_at",
        "ends_at",
    ):
        if key in raw:
            base[key] = raw[key]

    if base.get("delivery_mode") not in (DELIVERY_ON_START, DELIVERY_AT_PURCHASE):
        base["delivery_mode"] = DELIVERY_ON_START

    texts = raw.get("texts")
    if isinstance(texts, dict):
        for key, val in texts.items():
            if isinstance(val, str) and val.strip():
                base["texts"][key] = val

    return base


def load_festival_settings(data_dir: Path | None = None) -> dict[str, Any]:
    path = resolve_festival_file(data_dir)
    if not path.is_file():
        example = path.parent / "festival.example.json"
        if example.is_file():
            try:
                with example.open(encoding="utf-8") as fh:
                    return _merge_defaults(json.load(fh))
            except (OSError, json.JSONDecodeError):
                pass
        return deepcopy(DEFAULT_FESTIVAL)
    try:
        with path.open(encoding="utf-8") as fh:
            return _merge_defaults(json.load(fh))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load festival settings from %s: %s", path, exc)
        return deepcopy(DEFAULT_FESTIVAL)


def save_festival_settings(data: dict, data_dir: Path | None = None) -> Path:
    path = resolve_festival_file(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = _merge_defaults(data)
    tmp = path.parent / f".{path.name}.tmp"
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
        fh.flush()
    tmp.replace(path)
    return path


def new_campaign_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class FestivalSettingsView:
    data: dict[str, Any] = field(default_factory=lambda: deepcopy(DEFAULT_FESTIVAL))
    data_dir: Path | None = None
    _mtime: float = 0.0

    def reload_if_changed(self) -> None:
        path = resolve_festival_file(self.data_dir)
        if not path.is_file():
            return
        try:
            mtime = path.stat().st_mtime
            if mtime == self._mtime and self.data:
                return
            self.data = load_festival_settings(self.data_dir)
            self._mtime = mtime
        except OSError:
            pass

    @property
    def enabled(self) -> bool:
        self.reload_if_changed()
        return bool(self.data.get("enabled"))

    @property
    def campaign_id(self) -> str | None:
        self.reload_if_changed()
        cid = self.data.get("campaign_id")
        return str(cid).strip() if cid else None

    @property
    def max_users(self) -> int:
        self.reload_if_changed()
        return max(1, int(self.data.get("max_users") or 20))

    @property
    def delivery_mode(self) -> str:
        self.reload_if_changed()
        mode = self.data.get("delivery_mode") or DELIVERY_ON_START
        return mode if mode in (DELIVERY_ON_START, DELIVERY_AT_PURCHASE) else DELIVERY_ON_START

    @property
    def new_users_only(self) -> bool:
        self.reload_if_changed()
        return bool(self.data.get("new_users_only"))

    def discount_label(self) -> str:
        self.reload_if_changed()
        amount = self.data.get("discount_amount")
        if amount:
            return f"{int(amount):,} تومان تخفیف"
        pct = int(self.data.get("discount_percent") or 0)
        return f"{pct}٪ تخفیف"

    def is_within_schedule(self) -> bool:
        self.reload_if_changed()
        now = datetime.utcnow()
        starts = self.data.get("starts_at")
        ends = self.data.get("ends_at")
        if starts:
            try:
                start_dt = datetime.fromisoformat(str(starts).replace("Z", "+00:00"))
                if start_dt.tzinfo:
                    start_dt = start_dt.replace(tzinfo=None)
                if now < start_dt:
                    return False
            except ValueError:
                pass
        if ends:
            try:
                end_dt = datetime.fromisoformat(str(ends).replace("Z", "+00:00"))
                if end_dt.tzinfo:
                    end_dt = end_dt.replace(tzinfo=None)
                if now > end_dt:
                    return False
            except ValueError:
                pass
        return True

    def is_active(self) -> bool:
        return self.enabled and bool(self.campaign_id) and self.is_within_schedule()

    def text(self, key: str, **kwargs: Any) -> str:
        self.reload_if_changed()
        template = (self.data.get("texts") or {}).get(key) or DEFAULT_FESTIVAL["texts"].get(key, "")
        payload = {
            "title": self.data.get("title") or "جشنواره",
            "discount_label": self.discount_label(),
            "valid_days": int(self.data.get("valid_days") or 14),
            **kwargs,
        }
        try:
            return template.format(**payload)
        except KeyError as exc:
            logger.warning("Missing festival template key %s in %s", exc, key)
            return template


def festival_settings_for_config(config) -> FestivalSettingsView:
    data_dir = None
    if config and getattr(config, "pricing", None):
        pf = getattr(config.pricing, "plans_file", None)
        if pf is not None:
            data_dir = Path(pf).parent
    view = FestivalSettingsView(data=load_festival_settings(data_dir), data_dir=data_dir)
    if data_dir:
        path = resolve_festival_file(data_dir)
        if path.is_file():
            try:
                view._mtime = path.stat().st_mtime
            except OSError:
                pass
    return view
