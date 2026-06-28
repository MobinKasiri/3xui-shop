#!/usr/bin/env bash
# Record offline card payment as confirmed purchase (manage panel revenue).
#
# Usage (client already assigned):
#   ./scripts/record-purchase-transaction.sh \
#     --tg-id 107177203 --email cuazm8eexy \
#     --amount 370000 --plan-id vip_30g_30d
set -euo pipefail

CONTAINER="${BOT_CONTAINER:-nexoranode-bot}"
PY="/app/scripts/record_purchase_transaction.py"

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
