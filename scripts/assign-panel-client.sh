#!/usr/bin/env bash
# Run assign_panel_client.py inside the bot Docker container (has aiogram, sqlalchemy, …).
#
# Usage:
#   cd /opt/nexoranode-bot
#   ./scripts/assign-panel-client.sh --tg-id 107177203 --email cuazm8eexy --dry-run
#   ./scripts/assign-panel-client.sh --tg-id 107177203 --email cuazm8eexy
set -euo pipefail

CONTAINER="${BOT_CONTAINER:-nexoranode-bot}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Bot container '$CONTAINER' is not running." >&2
  echo "Start with: ./deploy/compose.sh up -d bot" >&2
  exit 1
fi

exec docker exec -i "$CONTAINER" poetry run python /app/scripts/assign_panel_client.py "$@"
