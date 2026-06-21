#!/usr/bin/env bash
# Safe git pull — never lose panel-edited plans.json / maintenance.json.
# Usage (from repo root or deploy/):
#   ./deploy/pull.sh
#   cd /opt/nexoranode-bot && ./deploy/pull.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-${ROOT}/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

DATA_DIR="${BOT_DATA_HOST:-}"

if [[ -n "$DATA_DIR" && -d "$DATA_DIR" ]]; then
  git pull "$@"
  if command -v python3 >/dev/null 2>&1; then
    python3 "${ROOT}/scripts/sync_emoji_packs.py" || true
  fi
  echo "Git pull OK — live config is outside the repo: ${DATA_DIR}"
  exit 0
fi

LIVE_FILES=(app/data/plans.json app/data/maintenance.json)
BACKUP="/tmp/nexora-live-config-$$"
mkdir -p "$BACKUP"

for f in "${LIVE_FILES[@]}"; do
  if [[ -f "$f" ]]; then
    cp -a "$f" "${BACKUP}/$(basename "$f")"
  fi
done

for f in "${LIVE_FILES[@]}"; do
  if git ls-files --error-unmatch "$f" &>/dev/null; then
    git checkout HEAD -- "$f" 2>/dev/null || rm -f "$f"
  fi
done

git pull "$@"

if command -v python3 >/dev/null 2>&1; then
  python3 "${ROOT}/scripts/sync_emoji_packs.py" || echo "Note: emoji sync skipped (run manually if icons missing)"
fi

mkdir -p app/data
for name in plans.json maintenance.json; do
  if [[ -f "${BACKUP}/${name}" ]]; then
    cp -a "${BACKUP}/${name}" "app/data/${name}"
  fi
done
rm -rf "$BACKUP"

git rm --cached -f app/data/plans.json 2>/dev/null || true
git rm --cached -f app/data/maintenance.json 2>/dev/null || true

echo ""
echo "Git pull OK — live plans restored."
echo "Run once to stop git conflicts forever:"
echo "  sudo bash ${ROOT}/deploy/setup-data-dir.sh"
