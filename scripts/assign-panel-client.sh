#!/usr/bin/env bash
# Run assign_panel_client.py inside the bot Docker container (has aiogram, sqlalchemy, …).
#
# Usage:
#   cd /opt/nexoranode-bot
#   ./scripts/assign-panel-client.sh --tg-id 107177203 --email cuazm8eexy --dry-run
#   ./scripts/assign-panel-client.sh --tg-id 107177203 --email cuazm8eexy
set -euo pipefail

CONTAINER="${BOT_CONTAINER:-nexoranode-bot}"
PY="/app/scripts/assign_panel_client.py"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Bot container '$CONTAINER' is not running." >&2
  echo "Start with: ./deploy/compose.sh up -d bot" >&2
  exit 1
fi

if ! docker exec "$CONTAINER" test -f "$PY"; then
  echo "Missing $PY inside '$CONTAINER'." >&2
  echo "The host script is new but the container image is old. On the server run:" >&2
  echo "  cd /opt/nexoranode-bot && ./deploy/pull.sh && ./deploy/compose.sh up -d --build bot" >&2
  exit 1
fi

exec docker exec -i "$CONTAINER" poetry run python "$PY" "$@"
