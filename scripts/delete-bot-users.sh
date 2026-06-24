#!/usr/bin/env bash
# Remove bot users by Telegram ID — next /start is treated as a first-time signup.
# Usage:
#   ./scripts/delete-bot-users.sh 123456789 987654321
#   ./scripts/delete-bot-users.sh 123456789   # single user
#
# Does NOT remove clients from 3X-UI — delete services in manage panel first if needed.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <telegram_user_id> [telegram_user_id ...]"
  echo ""
  echo "Find IDs in manage panel → Users (or search @username)."
  exit 1
fi

CONTAINER="${POSTGRES_CONTAINER:-nexoranode-postgres}"
DB_USER="${POSTGRES_USER:-nexora}"
DB_NAME="${POSTGRES_DB:-nexorabot}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Postgres container '$CONTAINER' is not running."
  exit 1
fi

IDS=""
for id in "$@"; do
  if ! [[ "$id" =~ ^[0-9]+$ ]]; then
    echo "Invalid Telegram ID (digits only): $id"
    exit 1
  fi
  IDS="${IDS:+$IDS,}$id"
done

echo "This will PERMANENTLY delete these bot users and all their data:"
echo "  Telegram IDs: $IDS"
echo ""
echo "Removed from DB: user row, wallet, transactions, VPN configs, referrals, discount usage."
echo "NOT removed: 3X-UI panel clients (delete in manage panel → سرویس‌ها if needed)."
echo ""
read -r -p "Type DELETE to continue: " confirm
if [[ "$confirm" != "DELETE" ]]; then
  echo "Aborted."
  exit 1
fi

docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" <<EOSQL
BEGIN;

DELETE FROM notification_logs
WHERE user_id IN (${IDS});

DELETE FROM referrals
WHERE referred_id IN (${IDS})
   OR referrer_id IN (${IDS});

DELETE FROM users
WHERE tg_id IN (${IDS});

COMMIT;

SELECT COUNT(*) AS users_still_present
FROM users
WHERE tg_id IN (${IDS});
EOSQL

echo ""
echo "Done. On each account open the bot and send /start — they will register as new users."
echo ""
echo "Referral test order:"
echo "  1) Account A → /start → menu → دعوت دوستان → copy ref link"
echo "  2) Account B → open ref link (must be first /start on that account)"
echo "  3) B should get welcome discount code; after B buys, A gets referrer bonus"
