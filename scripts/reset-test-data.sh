#!/usr/bin/env bash
# Wipe test transactions + reset all wallet balances. Safe for a fresh production start.
# Does NOT remove users, VPN services (DB or 3X-UI panel), or admin panel logins.
set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-nexoranode-postgres}"
DB_USER="${POSTGRES_USER:-nexora}"
DB_NAME="${POSTGRES_DB:-nexorabot}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Postgres container '$CONTAINER' is not running."
  exit 1
fi

echo "This will:"
echo "  - DELETE all rows in transactions"
echo "  - SET all user wallet balances to 0"
echo "  - RESET referral bonus counters and discount usage"
echo "  - CLEAR panel audit_logs (if present)"
echo ""
echo "This will NOT delete users or vpn_configs rows."
echo ""
read -r -p "Type RESET to continue: " confirm
if [[ "$confirm" != "RESET" ]]; then
  echo "Aborted."
  exit 1
fi

docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$SCRIPT_DIR/reset-test-data.sql"

# Optional receipt images from test card payments
BOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -d "$BOT_ROOT/app/data/receipts" ]]; then
  rm -f "$BOT_ROOT/app/data/receipts/"*.jpg "$BOT_ROOT/app/data/receipts/"*.png 2>/dev/null || true
  echo "Cleared receipt images in app/data/receipts/"
fi

echo ""
echo "Done. Refresh the admin panel — today's revenue should be 0."
echo "Your bot wallet balance is also 0; top up again for real purchases."
