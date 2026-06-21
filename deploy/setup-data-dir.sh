#!/usr/bin/env bash
# Move live bot/panel data OUTSIDE the git repo (recommended for production).
# Usage: sudo bash deploy/setup-data-dir.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${BOT_DATA_HOST:-/opt/nexoranode-data}"
ENV_FILE="${ENV_FILE:-${ROOT}/.env}"

echo "Using data directory: ${DATA_DIR}"
mkdir -p "${DATA_DIR}/receipts"
chmod 755 "${DATA_DIR}" "${DATA_DIR}/receipts"

copy_if_missing() {
  local name="$1"
  if [[ -f "${ROOT}/app/data/${name}" && ! -f "${DATA_DIR}/${name}" ]]; then
    cp -a "${ROOT}/app/data/${name}" "${DATA_DIR}/${name}"
    echo "  migrated ${name}"
  elif [[ -f "${DATA_DIR}/${name}" ]]; then
    echo "  kept existing ${DATA_DIR}/${name}"
  elif [[ -f "${ROOT}/app/data/plans.example.json" && "${name}" == "plans.json" ]]; then
    cp -a "${ROOT}/app/data/plans.example.json" "${DATA_DIR}/plans.json"
    echo "  seeded plans.json from example"
  fi
}

copy_if_missing plans.json
copy_if_missing maintenance.json

if [[ -d "${ROOT}/app/data/receipts" ]]; then
  shopt -s nullglob
  for f in "${ROOT}/app/data/receipts/"*; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f")"
    if [[ ! -f "${DATA_DIR}/receipts/${base}" ]]; then
      cp -a "$f" "${DATA_DIR}/receipts/${base}"
    fi
  done
  echo "  receipts synced"
fi

set_env_var() {
  local key="$1"
  local val="$2"
  if [[ -f "$ENV_FILE" ]] && grep -q "^${key}=" "$ENV_FILE"; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

set_env_var BOT_DATA_HOST "${DATA_DIR}"
echo "Updated ${ENV_FILE}: BOT_DATA_HOST=${DATA_DIR}"

PANEL_ENV="/opt/nexoranode-panel/.env"
if [[ -f "$PANEL_ENV" ]]; then
  if grep -q "^PLANS_DIR_HOST=" "$PANEL_ENV"; then
    sed -i.bak "s|^PLANS_DIR_HOST=.*|PLANS_DIR_HOST=${DATA_DIR}|" "$PANEL_ENV"
  else
    echo "PLANS_DIR_HOST=${DATA_DIR}" >> "$PANEL_ENV"
  fi
  if grep -q "^BOT_DATA_DIR=" "$PANEL_ENV"; then
    sed -i.bak "s|^BOT_DATA_DIR=.*|BOT_DATA_DIR=/data/plans|" "$PANEL_ENV"
  else
    echo "BOT_DATA_DIR=/data/plans" >> "$PANEL_ENV"
  fi
  echo "Updated ${PANEL_ENV}: PLANS_DIR_HOST=${DATA_DIR}"
fi

cd "$ROOT"
git rm --cached -f app/data/plans.json 2>/dev/null || true
git rm --cached -f app/data/maintenance.json 2>/dev/null || true

echo ""
echo "Done. Restart services:"
echo "  cd ${ROOT} && ./deploy/compose.sh up -d --build bot"
echo "  cd /opt/nexoranode-panel && docker compose up -d --build backend frontend"
