#!/usr/bin/env bash
# Verify bot webhook path: nginx → bot container → Telegram webhook URL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE="docker compose -f $ROOT/deploy/docker-compose.prod.yml --env-file $ENV_FILE"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source <(grep -E '^(BOT_DOMAIN|BOT_USE_HTTPS|BOT_TOKEN|NGINX_HTTP_PORT|NGINX_HTTPS_PORT)=' "$ENV_FILE" | sed 's/^/export /')
fi

BOT_DOMAIN="${BOT_DOMAIN:-bot.nexoranode.xyz}"
BOT_USE_HTTPS="${BOT_USE_HTTPS:-false}"
NGINX_HTTP_PORT="${NGINX_HTTP_PORT:-80}"
NGINX_HTTPS_PORT="${NGINX_HTTPS_PORT:-8443}"

DOMAIN="${BOT_DOMAIN#https://}"
DOMAIN="${DOMAIN#http://}"

if [[ "$BOT_USE_HTTPS" == "true" ]]; then
  WEBHOOK_SCHEME="https"
  LOCAL_PORT="${NGINX_HTTPS_PORT}"
  PUBLIC_HEALTH="https://${DOMAIN}/health"
  LOCAL_HEALTH="https://127.0.0.1:${LOCAL_PORT}/health"
  LOCAL_CURL=(curl -sk)
else
  WEBHOOK_SCHEME="http"
  LOCAL_PORT="${NGINX_HTTP_PORT}"
  PUBLIC_HEALTH="http://${DOMAIN}/health"
  LOCAL_HEALTH="http://127.0.0.1:${LOCAL_PORT}/health"
  LOCAL_CURL=(curl -s)
fi

WEBHOOK_URL="${WEBHOOK_SCHEME}://${DOMAIN}/webhook"

echo "==> Configured webhook base: ${WEBHOOK_SCHEME}://${DOMAIN}"

echo
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
  echo "  cd $ROOT/deploy && $COMPOSE up -d --force-recreate bot nginx"
  exit 1
}
echo "OK"

echo
echo "==> Local nginx health (from host — avoids DNS hairpin)"
if "${LOCAL_CURL[@]}" --connect-timeout 5 "$LOCAL_HEALTH" 2>/dev/null | grep -q OK; then
  "${LOCAL_CURL[@]}" -o /dev/null -w "local nginx: HTTP %{http_code}\n" "$LOCAL_HEALTH"
else
  echo "FAIL: local ${WEBHOOK_SCHEME} on port ${LOCAL_PORT} — check nginx/certs and BOT_USE_HTTPS"
  if [[ "$BOT_USE_HTTPS" == "true" ]]; then
    echo
    echo "TIP: Port 8443 needs SSL certs in deploy/nginx/certs/."
    echo "     Until certs work, use HTTP webhook on port 80:"
    echo "       BOT_DOMAIN=bot.nexoranode.xyz"
    echo "       BOT_USE_HTTPS=false"
    echo "     Then: cd $ROOT/deploy && $COMPOSE up -d --force-recreate bot"
  fi
fi

echo
echo "==> Public health URL (may fail from this server due to DNS hairpin — OK if local works)"
if curl -sk --connect-timeout 8 "$PUBLIC_HEALTH" 2>/dev/null | grep -q OK; then
  curl -sk -o /dev/null -w "public: HTTP %{http_code}\n" "$PUBLIC_HEALTH"
else
  echo "public: unreachable from this host (test from outside or use local check above)"
fi

echo
echo "==> Webhook POST test (local nginx)"
WH_CODE=$("${LOCAL_CURL[@]}" -o /dev/null -w "%{http_code}" --connect-timeout 5 \
  -X POST "${WEBHOOK_SCHEME}://127.0.0.1:${LOCAL_PORT}/webhook" \
  -H "Host: ${DOMAIN%%:*}" \
  -H "Content-Type: application/json" \
  -d '{}' 2>/dev/null || echo "000")
echo "webhook POST local: HTTP ${WH_CODE}"

echo
echo "==> Telegram webhook info"
if [[ -n "${BOT_TOKEN:-}" ]]; then
  INFO=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")
  echo "$INFO" | python3 -m json.tool
  URL=$(echo "$INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'].get('url',''))")
  ERR=$(echo "$INFO" | python3 -c "import sys,json; r=json.load(sys.stdin)['result']; print(r.get('last_error_message') or '')")
  if [[ -n "$URL" && "$URL" != "$WEBHOOK_URL" ]]; then
    echo
    echo "WARN: Telegram webhook URL ($URL) does not match .env ($WEBHOOK_URL)"
    echo "Fix: cd $ROOT/deploy && $COMPOSE up -d --force-recreate bot"
  fi
  if [[ -n "$ERR" ]]; then
    echo
    echo "WARN: Telegram last webhook error: $ERR"
    if [[ "$BOT_USE_HTTPS" == "true" && "$ERR" == *"SSL"* || "$ERR" == *"Connection"* ]]; then
      echo "Fix: set BOT_USE_HTTPS=false and BOT_DOMAIN=bot.nexoranode.xyz (no :8443), recreate bot"
    fi
  fi
else
  echo "Set BOT_TOKEN in $ENV_FILE to check webhook info."
fi
