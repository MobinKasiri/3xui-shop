"""Resolve referral ready-to-forward post image (photo + caption)."""
from __future__ import annotations

from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_IMAGE_NAMES = ("referral_post.jpg", "referral_post.png", "referral_post.webp")


def resolve_referral_post_image(
    explicit: Path | None = None,
    *,
    data_dir: Path | None = None,
) -> Path | None:
    """First existing file wins: env path → data dir → bundled assets."""
    if explicit is not None:
        path = explicit.expanduser()
        if path.is_file():
            return path
    if data_dir is not None:
        for name in _IMAGE_NAMES:
            path = data_dir / name
            if path.is_file():
                return path
    for name in _IMAGE_NAMES:
        path = _ASSETS_DIR / name
        if path.is_file():
            return path
    return None
