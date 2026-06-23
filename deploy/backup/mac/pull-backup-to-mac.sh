#!/usr/bin/env bash
# Pull full-server backup from Germany VPS to this Mac.
#
# 1. SSH: run remote export on server
# 2. rsync: server export/latest -> ~/NCBackups/YYYY-MM-DD/
# 3. Keep only the last 4 dated backups (oldest removed when 5th is added)
#
# Usage:
#   bash deploy/backup/mac/pull-backup-to-mac.sh
#   bash deploy/backup/mac/pull-backup-to-mac.sh --skip-remote   # rsync only
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${NC_MAC_BACKUP_ENV:-$HOME/.config/nc-vpn/mac-backup.env}"
# Legacy config path
[[ -f "$CONFIG" ]] || CONFIG="$HOME/.config/nexora/mac-backup.env"

SKIP_REMOTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-remote) SKIP_REMOTE=1; shift ;;
    -h|--help)
      echo "Usage: pull-backup-to-mac.sh [--skip-remote]"
      exit 0
      ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

[[ -f "$CONFIG" ]] || {
  echo "Missing $CONFIG"
  echo "  mkdir -p ~/.config/nc-vpn"
  echo "  cp deploy/backup/mac/mac-backup.env.example ~/.config/nc-vpn/mac-backup.env"
  echo "  nano ~/.config/nc-vpn/mac-backup.env"
  exit 1
}

# shellcheck disable=SC1090
source "$CONFIG"

SERVER_HOST="${SERVER_HOST:?}"
SERVER_SSH_PORT="${SERVER_SSH_PORT:-2222}"
SERVER_SSH_USER="${SERVER_SSH_USER:-root}"
SSH_IDENTITY_FILE="${SSH_IDENTITY_FILE:-}"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-$HOME/NCBackups}"
REMOTE_BACKUP_SCRIPT="${REMOTE_BACKUP_SCRIPT:-/usr/local/lib/nc-vpn-backup/run-local-backup.sh}"
REMOTE_EXPORT_DIR="${REMOTE_EXPORT_DIR:-/var/lib/nc-vpn-backup/export/latest}"
KEEP_LOCAL_VERSIONS="${KEEP_LOCAL_VERSIONS:-4}"

LOG_DIR="${LOCAL_BACKUP_DIR}/logs"
mkdir -p "$LOCAL_BACKUP_DIR" "$LOG_DIR"
LOG_FILE="${LOG_DIR}/pull-$(date +%Y%m%d).log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

ssh_opts=(-p "$SERVER_SSH_PORT" -o BatchMode=yes -o ConnectTimeout=30)
[[ -n "$SSH_IDENTITY_FILE" && -f "$SSH_IDENTITY_FILE" ]] && ssh_opts+=(-i "$SSH_IDENTITY_FILE")

ssh_cmd() {
  ssh "${ssh_opts[@]}" "${SERVER_SSH_USER}@${SERVER_HOST}" "$@"
}

rsync_cmd() {
  local dest="$1"
  local ssh_rsh="ssh -p ${SERVER_SSH_PORT}"
  [[ -n "$SSH_IDENTITY_FILE" && -f "$SSH_IDENTITY_FILE" ]] && ssh_rsh+=" -i ${SSH_IDENTITY_FILE}"
  rsync -az --delete \
    -e "$ssh_rsh" \
    "${SERVER_SSH_USER}@${SERVER_HOST}:${REMOTE_EXPORT_DIR}/" \
    "${dest}/"
}

prune_mac_backups() {
  local keep="$1"
  local dirs=() d
  while IFS= read -r d; do
    [[ -n "$d" ]] && dirs+=("$d")
  done < <(find "$LOCAL_BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d ! -name logs | sort)
  local n=${#dirs[@]} i
  if (( n > keep )); then
    for ((i = 0; i < n - keep; i++)); do
      log "Removing old Mac backup (keep ${keep}): ${dirs[$i]}"
      rm -rf "${dirs[$i]}"
    done
  fi
}

DATE_TAG="$(date +%Y-%m-%d)"
DEST="${LOCAL_BACKUP_DIR}/${DATE_TAG}"

log "=== NC VPN Mac pull start ==="
log "Server: ${SERVER_SSH_USER}@${SERVER_HOST}:${SERVER_SSH_PORT}"
log "Dest:   ${DEST}"

if [[ "$SKIP_REMOTE" -eq 0 ]]; then
  log "Running remote export ..."
  ssh_cmd "${REMOTE_BACKUP_SCRIPT}" 2>&1 | tee -a "$LOG_FILE"
fi

mkdir -p "$DEST"
log "Rsync from ${REMOTE_EXPORT_DIR} ..."
rsync_cmd "$DEST" 2>&1 | tee -a "$LOG_FILE"

rm -f "${LOCAL_BACKUP_DIR}/latest"
ln -sfn "$DATE_TAG" "${LOCAL_BACKUP_DIR}/latest"

prune_mac_backups "$KEEP_LOCAL_VERSIONS"

SIZE="$(du -sh "$DEST" | cut -f1)"
log "=== Mac pull OK (${SIZE}) -> ${DEST} (keeping ${KEEP_LOCAL_VERSIONS} versions) ==="
