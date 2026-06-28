#!/usr/bin/env bash
# Full offline purchase: assign panel client + record transaction (or either alone).
#
# New customer (panel client + tx + notify):
#   ./scripts/manual-purchase.sh --tg-id ID --email NAME --amount 370000 --plan-id vip_30g_30d
#
# Assign only:
#   ./scripts/manual-purchase.sh --assign-only --tg-id ID --email NAME
#
# Transaction only (already assigned — your case):
#   ./scripts/manual-purchase.sh --tx-only --tg-id ID --email NAME --amount 370000 --plan-id vip_30g_30d
set -euo pipefail

CONTAINER="${BOT_CONTAINER:-nexoranode-bot}"
PY="/app/scripts/manual_purchase.py"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Bot container '$CONTAINER' is not running." >&2
  exit 1
fi

if ! docker exec "$CONTAINER" test -f "$PY"; then
  echo "Missing $PY inside '$CONTAINER'." >&2
  echo "The host script is new but the container image is old. On the server run:" >&2
  echo "  cd /opt/nexoranode-bot && ./deploy/pull.sh && ./deploy/compose.sh up -d --build bot" >&2
  exit 1
fi

exec docker exec -i "$CONTAINER" poetry run python "$PY" "$@"
