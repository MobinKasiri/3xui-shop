#!/usr/bin/env bash
# Shared helpers for NC VPN backup scripts.
set -euo pipefail

BACKUP_ENV="${BACKUP_ENV:-/etc/nc-vpn/backup.env}"
# Legacy path (migrated by install-local-backup.sh)
[[ -f "$BACKUP_ENV" ]] || BACKUP_ENV="/etc/nexora/backup.env"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
  local msg="[$(date -Iseconds)] $*"
  echo "$msg"
  if [[ -n "${LOG_FILE:-}" ]]; then
    echo "$msg" >>"$LOG_FILE"
  fi
}

die() {
  log "ERROR: $*"
  exit 1
}

load_server_config() {
  if [[ ! -f "$BACKUP_ENV" ]]; then
    die "Missing $BACKUP_ENV — run: sudo bash ${SCRIPT_DIR}/install-local-backup.sh"
  fi
  # shellcheck disable=SC1090
  set -a
  source "$BACKUP_ENV"
  set +a

  BOT_ROOT="${BOT_ROOT:-/opt/nexoranode-bot}"
  PANEL_ROOT="${PANEL_ROOT:-/opt/nexoranode-panel}"
  DATA_DIR="${DATA_DIR:-/opt/nexoranode-data}"
  XUI_DIR="${XUI_DIR:-/usr/local/x-ui}"
  XUI_CERT_DIR="${XUI_CERT_DIR:-/root/cert}"
  ACME_DIR="${ACME_DIR:-/root/.acme.sh}"
  LOCAL_EXPORT_DIR="${LOCAL_EXPORT_DIR:-/var/lib/nc-vpn-backup/export}"
  KEEP_LOCAL_VERSIONS="${KEEP_LOCAL_VERSIONS:-4}"
  LOG_FILE="${LOG_FILE:-/var/log/nc-vpn-backup.log}"
  XUI_PG_HOST="${XUI_PG_HOST:-127.0.0.1}"
  XUI_PG_PORT="${XUI_PG_PORT:-5432}"
  XUI_PG_USER="${XUI_PG_USER:-}"
  XUI_PG_DB="${XUI_PG_DB:-xui}"
  BOT_PG_CONTAINER="${BOT_PG_CONTAINER:-nexoranode-postgres}"
  BOT_PG_USER="${BOT_PG_USER:-nexora}"
  BOT_PG_DB="${BOT_PG_DB:-nexorabot}"
  SCRIPTS_ROOT="${SCRIPTS_ROOT:-}"

  mkdir -p "$(dirname "$LOG_FILE")" "$LOCAL_EXPORT_DIR"
}

read_bot_env_var() {
  local key="$1"
  local file="${BOT_ROOT}/.env"
  [[ -f "$file" ]] || return 1
  grep -E "^${key}=" "$file" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'"
}

bot_postgres_password() {
  if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    echo "$POSTGRES_PASSWORD"
    return 0
  fi
  read_bot_env_var POSTGRES_PASSWORD
}

notify_failure() {
  local msg="$1"
  local token="${NOTIFY_BOT_TOKEN:-}"
  local chat="${NOTIFY_TG_CHAT_ID:-}"
  if [[ -z "$token" ]]; then
    token="$(read_bot_env_var BOT_TOKEN 2>/dev/null || true)"
  fi
  if [[ -z "$chat" ]]; then
    chat="$(read_bot_env_var ADMIN_CHAT_ID 2>/dev/null || true)"
  fi
  if [[ -z "$token" || -z "$chat" ]]; then
    return 0
  fi
  curl -fsS -X POST "https://api.telegram.org/bot${token}/sendMessage" \
    -d "chat_id=${chat}" \
    --data-urlencode "text=⚠️ NC VPN backup FAILED on $(hostname): ${msg}" \
    >/dev/null 2>&1 || true
}

require_cmd() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || die "Required command not found: $c"
  done
}

collect_backup_paths() {
  local snap="${1:-}"
  local -a paths=()
  [[ -n "$snap" && -d "$snap" ]] && paths+=("$snap")
  local p
  for p in \
    "$BOT_ROOT" \
    "$PANEL_ROOT" \
    "$DATA_DIR" \
    "$XUI_DIR" \
    "$XUI_CERT_DIR" \
    "$ACME_DIR" \
    /etc/ufw \
    /etc/fail2ban \
    /etc/docker \
    /etc/ssh/sshd_config \
    /etc/systemd/system/x-ui.service \
    ; do
    [[ -e "$p" ]] && paths+=("$p")
  done
  [[ -d /etc/ssh/sshd_config.d ]] && paths+=("/etc/ssh/sshd_config.d")
  [[ -d /etc/systemd/system/x-ui.service.d ]] && paths+=("/etc/systemd/system/x-ui.service.d")
  [[ -d /etc/postgresql ]] && paths+=("/etc/postgresql")
  [[ -n "$SCRIPTS_ROOT" && -d "$SCRIPTS_ROOT" ]] && paths+=("$SCRIPTS_ROOT")
  if [[ -n "${BACKUP_EXTRA_PATHS:-}" ]]; then
    local IFS=',' extra
    read -ra extra <<<"${BACKUP_EXTRA_PATHS}"
    for p in "${extra[@]}"; do
      p="${p#"${p%%[![:space:]]*}"}"
      p="${p%"${p##*[![:space:]]}"}"
      [[ -n "$p" && -e "$p" ]] && paths+=("$p")
    done
  fi
  printf '%s\n' "${paths[@]}"
}

export_system_state() {
  local meta="${1:?}"
  mkdir -p "$meta"
  {
    echo "timestamp_utc=$(date -u +%Y%m%dT%H%M%SZ)"
    echo "hostname=$(hostname)"
    echo "kernel=$(uname -r)"
    echo "public_ip=$(curl -4 -fsS --max-time 10 https://ifconfig.me/ip 2>/dev/null || hostname -I | awk '{print $1}')"
  } >"${meta}/host.txt"
  hostnamectl 2>/dev/null >"${meta}/hostnamectl.txt" || true
  ip -4 addr >"${meta}/ip-addr.txt" 2>/dev/null || true
  crontab -l >"${meta}/root-crontab.txt" 2>/dev/null || true
  ufw status numbered >"${meta}/ufw-status.txt" 2>/dev/null || true
  systemctl list-unit-files --type=service >"${meta}/systemd-services.txt" 2>/dev/null || true
  docker ps -a --format '{{.Names}}\t{{.Status}}' 2>/dev/null >"${meta}/docker-ps.txt" || true
  docker network ls 2>/dev/null >"${meta}/docker-networks.txt" || true
  docker volume ls 2>/dev/null >"${meta}/docker-volumes.txt" || true
  dpkg --get-selections 2>/dev/null >"${meta}/dpkg-selections.txt" || true
  if command -v x-ui >/dev/null 2>&1; then
    x-ui version 2>/dev/null >"${meta}/x-ui-version.txt" || true
  fi
  if [[ -d "${BOT_ROOT}/.git" ]]; then
    git -C "$BOT_ROOT" rev-parse HEAD 2>/dev/null >"${meta}/bot-git-rev.txt" || true
  fi
  if [[ -d "${PANEL_ROOT}/.git" ]]; then
    git -C "$PANEL_ROOT" rev-parse HEAD 2>/dev/null >"${meta}/panel-git-rev.txt" || true
  fi
  collect_backup_paths | sort -u >"${meta}/backup-paths.txt"
}

find_latest_dump() {
  local name="$1"
  local root="${2:-/var/lib/nc-vpn-backup/export/latest}"
  find "$root" -type f -name "${name}-*.sql.gz" 2>/dev/null | sort | tail -1
}

read_meta_public_ip() {
  local root="${1:-/var/lib/nc-vpn-backup/export/latest}"
  local f="${root}/meta/host.txt"
  [[ -f "$f" ]] || f="$(find /var/lib/nc-vpn-backup -path '*/meta/host.txt' 2>/dev/null | sort | tail -1)"
  [[ -f "$f" ]] || return 0
  grep '^public_ip=' "$f" | cut -d= -f2-
}

path_slug() {
  echo "$1" | sed 's|^/||; s|/|_|g'
}

dump_xui_db() {
  local dumps="${1:?}" ts="${2:?}"
  local out="${dumps}/xui-${ts}.sql.gz"
  [[ -n "${XUI_PG_PASSWORD:-}" ]] || die "XUI_PG_PASSWORD is not set"
  log "Dumping 3X-UI PostgreSQL (${XUI_PG_DB}) ..."
  PGPASSWORD="$XUI_PG_PASSWORD" pg_dump \
    -h "${XUI_PG_HOST:-127.0.0.1}" \
    -p "${XUI_PG_PORT:-5432}" \
    -U "${XUI_PG_USER}" \
    -d "${XUI_PG_DB}" \
    --no-owner --no-acl \
    | gzip -9 >"$out"
  log "  -> $(du -h "$out" | cut -f1)"
}

dump_bot_db() {
  local dumps="${1:?}" ts="${2:?}"
  local out="${dumps}/nexorabot-${ts}.sql.gz"
  local pw
  pw="$(bot_postgres_password)" || die "Could not read POSTGRES_PASSWORD"
  docker ps --format '{{.Names}}' | grep -qx "$BOT_PG_CONTAINER" \
    || die "Container $BOT_PG_CONTAINER is not running"
  log "Dumping bot PostgreSQL (${BOT_PG_DB}) ..."
  docker exec -e PGPASSWORD="$pw" "$BOT_PG_CONTAINER" \
    pg_dump -U "$BOT_PG_USER" -d "$BOT_PG_DB" --no-owner --no-acl \
    | gzip -9 >"$out"
  log "  -> $(du -h "$out" | cut -f1)"
}

copy_config_snapshots() {
  local config="${1:?}"
  log "Copying .env snapshots ..."
  if [[ -f "${BOT_ROOT}/.env" ]]; then
    install -D -m 600 "${BOT_ROOT}/.env" "${config}/bot.env"
  fi
  if [[ -f "${PANEL_ROOT}/.env" ]]; then
    install -D -m 600 "${PANEL_ROOT}/.env" "${config}/panel.env"
  fi
}

archive_backup_paths() {
  local files_dir="${1:?}"
  mkdir -p "$files_dir"
  log "Archiving server paths ..."
  local p slug parent base
  while IFS= read -r p; do
    [[ -n "$p" && -e "$p" ]] || continue
    parent="$(dirname "$p")"
    base="$(basename "$p")"
    slug="$(path_slug "$p")"
    log "  tar: $p"
    tar czf "${files_dir}/${slug}.tar.gz" \
      --exclude='node_modules' \
      --exclude='.git' \
      --exclude='__pycache__' \
      --exclude='*.log' \
      -C "$parent" "$base"
  done < <(collect_backup_paths)
}

prune_local_exports() {
  local keep="${KEEP_LOCAL_VERSIONS:-4}"
  mapfile -t old < <(find "$LOCAL_EXPORT_DIR" -mindepth 1 -maxdepth 1 -type d ! -name latest | sort)
  local n=${#old[@]}
  if (( n > keep )); then
    local i
    for ((i = 0; i < n - keep; i++)); do
      log "Removing old export (keep ${keep}): ${old[$i]}"
      rm -rf "${old[$i]}"
    done
  fi
}

link_latest_export() {
  local bundle="${1:?}"
  rm -f "${LOCAL_EXPORT_DIR}/latest"
  ln -sfn "$(basename "$bundle")" "${LOCAL_EXPORT_DIR}/latest"
  log "latest -> $(basename "$bundle")"
}

prune_versioned_dirs() {
  local root="${1:?}" keep="${2:-4}" exclude="${3:-logs}"
  mapfile -t dirs < <(find "$root" -mindepth 1 -maxdepth 1 -type d ! -name "$exclude" | sort)
  local n=${#dirs[@]} i
  if (( n > keep )); then
    for ((i = 0; i < n - keep; i++)); do
      log "Removing old backup (keep ${keep}): ${dirs[$i]}"
      rm -rf "${dirs[$i]}"
    done
  fi
}
