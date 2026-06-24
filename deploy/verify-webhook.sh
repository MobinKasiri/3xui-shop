#!/usr/bin/env bash
# Verify bot webhook path: nginx → bot container → Telegram webhook URL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE="docker compose -f $ROOT/deploy/docker-compose.prod.yml --env-file $ENV_FILE"

DOMAIN="${BOT_DOMAIN:-bot.nexoranode.xyz:8443}"
DOMAIN="${DOMAIN#https://}"
DOMAIN="${DOMAIN#http://}"
HEALTH_URL="https://${DOMAIN}/health"

echo "==> Stack status"
$COMPOSE ps

echo
echo "==> Bot health (inside container)"
docker exec nexoranode-bot python -c \
  "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3); print('bot internal:', r.status, r.read().decode())"

echo
echo "==> Nginx → bot (inside nginx container)"
docker exec nexoranode-nginx wget -qO- http://bot:8090/health || {
  echo "FAIL: nginx cannot reach bot:8090 — recreate the full stack on nexora_net:"
  echo "  cd $ROOT/deploy && $COMPOSE up -d --force-recreate"
  exit 1
}

echo
echo "==> Public health URL"
curl -sk "$HEALTH_URL" | head -c 80 || true
echo
curl -sk -o /dev/null -w "HTTP %{http_code}\n" "$HEALTH_URL"

echo
echo "==> Telegram webhook info"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source <(grep -E '^BOT_TOKEN=' "$ENV_FILE" | sed 's/^/export /')
fi
if [[ -n "${BOT_TOKEN:-}" ]]; then
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
else
  echo "Set BOT_TOKEN in $ENV_FILE to check webhook info."
fi
