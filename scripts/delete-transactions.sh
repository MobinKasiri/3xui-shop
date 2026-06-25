#!/usr/bin/env bash
# Remove specific transactions from the manage panel DB (fake / test rows).
#
# Usage:
#   ./scripts/delete-transactions.sh 12 34 56
#   TX_IDS="12,34,56" ./scripts/delete-transactions.sh
#   ./scripts/delete-transactions.sh --dry-run 12 34
#
# Does NOT reverse wallet debits/credits or delete VPN configs created by approve.
# Safe for pending/rejected test txs. Review output if any row is "confirmed".
set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-nexoranode-postgres}"
DB_USER="${POSTGRES_USER:-nexora}"
DB_NAME="${POSTGRES_DB:-nexorabot}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DRY_RUN=0
IDS=()

usage() {
  echo "Usage: $0 [--dry-run] <transaction_id> [transaction_id ...]"
  echo "   or: TX_IDS=\"1,2,3\" $0"
  echo ""
  echo "Removes rows from transactions + related audit_logs + local receipt images."
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-n)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      if [[ "$1" =~ ^[0-9]+$ ]]; then
        IDS+=("$1")
      else
        echo "Invalid transaction ID (digits only): $1"
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ ${#IDS[@]} -eq 0 && -n "${TX_IDS:-}" ]]; then
  IFS=',' read -r -a _raw <<< "$TX_IDS"
  for id in "${_raw[@]}"; do
    id="${id//[[:space:]]/}"
    [[ -z "$id" ]] && continue
    if [[ "$id" =~ ^[0-9]+$ ]]; then
      IDS+=("$id")
    else
      echo "Invalid transaction ID in TX_IDS: $id"
      exit 1
    fi
  done
fi

if [[ ${#IDS[@]} -eq 0 ]]; then
  usage
fi

# Unique, stable order
mapfile -t IDS < <(printf '%s\n' "${IDS[@]}" | sort -nu)
ID_LIST=$(IFS=,; echo "${IDS[*]}")

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Postgres container '$CONTAINER' is not running."
  exit 1
fi

echo "Transaction IDs to remove: $ID_LIST"
echo ""

echo "=== Preview (current rows) ==="
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<EOSQL
SELECT id, user_id, type, status, payment_amount, amount, payment_method,
       LEFT(COALESCE(description, ''), 40) AS description,
       created_at::text
FROM transactions
WHERE id IN (${ID_LIST})
ORDER BY id;

SELECT COUNT(*) AS missing_ids
FROM (VALUES $(printf "(%s)," "${IDS[@]}" | sed 's/,$//')) AS v(id)
WHERE NOT EXISTS (SELECT 1 FROM transactions t WHERE t.id = v.id);
EOSQL

CONFIRMED_COUNT=$(
  docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM transactions WHERE id IN (${ID_LIST}) AND status = 'confirmed';"
)

if [[ "$CONFIRMED_COUNT" -gt 0 ]]; then
  echo ""
  echo "WARNING: ${CONFIRMED_COUNT} transaction(s) are confirmed."
  echo "  Deleting them only removes the panel record — wallet balances and VPN configs are NOT adjusted."
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "Dry run — nothing deleted."
  exit 0
fi

echo ""
read -r -p "Type DELETE to remove these transactions: " confirm
if [[ "$confirm" != "DELETE" ]]; then
  echo "Aborted."
  exit 1
fi

docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<EOSQL
BEGIN;

DELETE FROM audit_logs
WHERE target_type = 'transaction'
  AND target_id IN ($(printf "'%s'," "${IDS[@]}" | sed 's/,$//'));

DELETE FROM transactions
WHERE id IN (${ID_LIST});

COMMIT;

SELECT COUNT(*) AS transactions_left
FROM transactions
WHERE id IN (${ID_LIST});
EOSQL

# Receipt images (bot + panel mount paths)
RECEIPT_DIRS=(
  "$BOT_ROOT/app/data/receipts"
  "/opt/nexoranode-data/receipts"
  "/opt/nexoranode-bot/app/data/receipts"
)
removed_receipts=0
for tx_id in "${IDS[@]}"; do
  for base in "${RECEIPT_DIRS[@]}"; do
    [[ -d "$base" ]] || continue
    for ext in jpg jpeg png webp; do
      f="$base/${tx_id}.${ext}"
      if [[ -f "$f" ]]; then
        rm -f "$f"
        removed_receipts=$((removed_receipts + 1))
        echo "Removed receipt: $f"
      fi
    done
  done
done

echo ""
echo "Done. Removed transaction IDs: $ID_LIST"
if [[ "$removed_receipts" -eq 0 ]]; then
  echo "No local receipt files found for these IDs."
fi
echo "Refresh the manage panel transactions page."
