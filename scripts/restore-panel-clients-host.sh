#!/usr/bin/env bash
# Restore deleted 3X-UI clients from bot vpn_configs — runs on Germany HOST (not Docker).
# Uses curl → 127.0.0.1:2057. No Telegram, no bot DB writes.
#
# Usage:
#   cd /opt/nexoranode-bot
#   ./scripts/restore-panel-clients-host.sh --list-missing
#   ./scripts/restore-panel-clients-host.sh --config-id 53 --config-id 54 --dry-run
#   ./scripts/restore-panel-clients-host.sh --config-id 53 --config-id 54 --config-id 55 --config-id 56
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
PG_CONTAINER="${PG_CONTAINER:-nexoranode-postgres}"
PG_USER="${PG_USER:-nexora}"
PG_DB="${PG_DB:-nexorabot}"

DRY_RUN=0
LIST_MISSING=0
CONFIG_IDS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config-id) CONFIG_IDS+=("$2"); shift 2 ;;
    --list-missing) LIST_MISSING=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE" >&2; exit 1; }

# shellcheck disable=SC1090
source "$ENV_FILE"

export XUI_TOKEN="${XUI_TOKEN:-}"
export XUI_PATH="${XUI_PATH:-${XUI_BASE_PATH:-/}}"
export XUI_HOST="${XUI_HOST:-https://127.0.0.1:2057}"
export PANEL_BASE="${XUI_HOST%/}${XUI_PATH%/}/"
export MS_PER_DAY=86400000
export PG_CONTAINER PG_USER PG_DB DRY_RUN LIST_MISSING

[[ -n "$XUI_TOKEN" ]] || { echo "XUI_TOKEN missing in $ENV_FILE" >&2; exit 1; }

fetch_configs_json() {
  local ids_csv="${1:-}"
  local where_clause=""
  if [[ -n "$ids_csv" ]]; then
    where_clause="WHERE id IN ($ids_csv)"
  fi
  docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -t -A -c "
    SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.id DESC), '[]'::json)
    FROM (
      SELECT id, user_id, service_name, panel_email, panel_uuid, subscription_id,
             traffic_limit_bytes, expiry_date, is_active, plan_days
      FROM vpn_configs
      $where_clause
    ) x;
  "
}

run_python() {
  python3 - "${CONFIG_IDS[@]}" <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PANEL_BASE = os.environ["PANEL_BASE"]
TOKEN = os.environ["XUI_TOKEN"]
MS_PER_DAY = int(os.environ["MS_PER_DAY"])
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
LIST_MISSING = os.environ.get("LIST_MISSING", "0") == "1"
CONFIG_IDS = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else []

configs_json = os.environ.get("CONFIGS_JSON", "[]")
configs = json.loads(configs_json)


def api(method: str, path: str, body: dict | None = None) -> dict:
    url = PANEL_BASE + path.lstrip("/")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        raw = resp.read().decode()
    if not raw.strip():
        raise SystemExit(f"Empty API response from {url}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit(f"Non-JSON from {url}: {raw[:200]!r}")
    return data


def client_exists(email: str) -> bool:
    enc = urllib.parse.quote(email, safe="")
    try:
        data = api("GET", f"panel/api/clients/get/{enc}")
    except SystemExit:
        return False
    msg = str(data.get("msg", ""))
    if "not found" in msg.lower() or "یافت نشد" in msg:
        return False
    return bool(data.get("success"))


def expiry_ms(cfg: dict) -> int:
    expiry = cfg.get("expiry_date")
    plan_days = int(cfg.get("plan_days") or 30)
    if expiry:
        # psql json: "2026-07-29T21:23:17.017" or "2026-07-29 21:23:17.017"
        s = str(expiry).replace(" ", "T")
        if s.endswith("+00"):
            s += ":00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    return -plan_days * MS_PER_DAY


def load_inbound_ids() -> list[int]:
    data = api("GET", "panel/api/inbounds/list")
    ids = [int(x["id"]) for x in (data.get("obj") or []) if x.get("enable")]
    if not ids:
        raise SystemExit("No enabled inbounds")
    print(f"Using inbounds: {','.join(str(i) for i in ids)}")
    return ids


def restore_one(cfg: dict, inbound_ids: list[int]) -> bool:
    cid = cfg["id"]
    email = cfg["panel_email"]
    if client_exists(email):
        print(f"SKIP id={cid} ({email}) — already on panel")
        return True

    exp_ms = expiry_ms(cfg)
    body = {
        "client": {
            "email": email,
            "uuid": cfg["panel_uuid"],
            "subId": cfg["subscription_id"],
            "totalGB": int(cfg["traffic_limit_bytes"]),
            "expiryTime": exp_ms,
            "tgId": int(cfg["user_id"]),
            "limitIp": 0,
            "enable": bool(cfg["is_active"]),
            "comment": cfg["service_name"],
            "reset": 0,
        },
        "inboundIds": inbound_ids,
    }
    print(
        f"Restore id={cid} email={email} sub={cfg['subscription_id']} "
        f"uuid={cfg['panel_uuid']} expiry_ms={exp_ms} inbounds={inbound_ids}"
    )
    if DRY_RUN:
        print("  (dry-run — no panel write)")
        return True

    data = api("POST", "panel/api/clients/add", body)
    if not data.get("success"):
        print(f"FAIL id={cid}: {data.get('msg', data)}", file=sys.stderr)
        return False
    print(f"OK id={cid} ({email})")
    return True


if LIST_MISSING:
    print("Missing on panel:")
    for cfg in configs:
        if not client_exists(cfg["panel_email"]):
            print(
                f"  id={cfg['id']}  user={cfg['user_id']}  "
                f"name={cfg['service_name']!r}  email={cfg['panel_email']!r}  "
                f"sub={cfg['subscription_id']}"
            )
    sys.exit(0)

if not CONFIG_IDS:
    raise SystemExit("Provide --config-id and/or --list-missing")

inbound_ids = load_inbound_ids()
by_id = {int(c["id"]): c for c in configs}
fail = False
for cid in CONFIG_IDS:
    cfg = by_id.get(cid)
    if not cfg:
        print(f"Config id={cid} not in bot DB", file=sys.stderr)
        fail = True
        continue
    if not restore_one(cfg, inbound_ids):
        fail = True

sys.exit(1 if fail else 0)
PY
}

if [[ "$LIST_MISSING" -eq 1 ]]; then
  export CONFIGS_JSON
  CONFIGS_JSON="$(fetch_configs_json "")"
  LIST_MISSING=1 DRY_RUN=0 run_python
  exit $?
fi

[[ ${#CONFIG_IDS[@]} -gt 0 ]] || {
  echo "Provide --config-id and/or --list-missing" >&2
  exit 1
}

export CONFIGS_JSON
ids_csv="$(IFS=,; echo "${CONFIG_IDS[*]}")"
CONFIGS_JSON="$(fetch_configs_json "$ids_csv")"
run_python
exit_code=$?

if [[ "$DRY_RUN" -eq 0 && "$exit_code" -eq 0 ]]; then
  echo ""
  echo "Triggering node sync (optional)..."
  if [[ -x "$ROOT/../scripts/repair-direct-nodes.sh" ]]; then
    bash "$ROOT/../scripts/repair-direct-nodes.sh" 2>/dev/null || true
  elif [[ -f /opt/VPN_project/scripts/repair-direct-nodes.sh ]]; then
    bash /opt/VPN_project/scripts/repair-direct-nodes.sh 2>/dev/null || true
  else
    echo "  (repair-direct-nodes.sh not found — sync nodes manually if needed)"
  fi
fi

exit "$exit_code"
