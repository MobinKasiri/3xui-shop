#!/usr/bin/env bash
# Build full-server backup bundle on Germany VPS (for Mac pull).
#
# Output: /var/lib/nc-vpn-backup/export/latest/
#   dumps/  meta/  config/  files/*.tar.gz
#
# Usage:
#   sudo bash deploy/backup/run-local-backup.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

main() {
  load_server_config
  require_cmd gzip pg_dump docker curl tar

  local ts bundle
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  bundle="${LOCAL_EXPORT_DIR}/${ts}"

  log "=== NC VPN local export start ($ts) ==="
  mkdir -p "${bundle}/dumps" "${bundle}/meta" "${bundle}/config" "${bundle}/files"

  export_system_state "${bundle}/meta"
  dump_xui_db "${bundle}/dumps" "$ts"
  dump_bot_db "${bundle}/dumps" "$ts"
  copy_config_snapshots "${bundle}/config"
  archive_backup_paths "${bundle}/files"

  echo "$ts" >"${bundle}/timestamp.txt"
  du -sh "${bundle}" | awk '{print "total_size=" $1}' >"${bundle}/meta/size.txt"

  link_latest_export "$bundle"
  prune_local_exports

  log "=== Local export OK: ${LOCAL_EXPORT_DIR}/latest ($(du -sh "${bundle}" | cut -f1)) ==="
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  trap 'notify_failure "local export failed"; exit 1' ERR
  main "$@"
fi
