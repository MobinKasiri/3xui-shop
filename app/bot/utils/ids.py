"""Unique identifier generators for 3X-UI clients."""
from __future__ import annotations

import secrets
import time
import uuid

# Internal 3X-UI client id domain (not user-facing; brand: NC Network)
PANEL_EMAIL_DOMAIN = "ncbot"


def make_panel_email(tg_id: int) -> str:
    """Generate a unique 3X-UI client email (not user-facing)."""
    ts = int(time.time())
    token = secrets.token_hex(4)
    return f"u{tg_id}_{ts}_{token}@{PANEL_EMAIL_DOMAIN}"


def make_uuid() -> str:
    return str(uuid.uuid4())
