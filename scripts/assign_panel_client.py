#!/usr/bin/env python3
"""Host wrapper — runs inside Docker. Use ./scripts/assign-panel-client.sh instead."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "assign-panel-client.sh"

if __name__ == "__main__":
    if not WRAPPER.is_file():
        print("Missing assign-panel-client.sh", file=sys.stderr)
        sys.exit(1)
    raise SystemExit(subprocess.call([str(WRAPPER), *sys.argv[1:]]))
