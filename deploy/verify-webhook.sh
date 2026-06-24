#!/usr/bin/env bash
# Verify bot webhook path: nginx → bot container → Telegram webhook URL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE="docker compose -f $ROOT/deploy/docker-compose.prod.yml --env-file $ENV_FILE"
WAIT_SECS="${WAIT_SECS:-90}"
CERT_DIR="$ROOT/deploy/nginx/certs"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source <(grep -E '^(BOT_DOMAIN|BOT_USE_HTTPS|BOT_TOKEN|NGINX_HTTP_PORT|NGINX_HTTPS_PORT)=' "$ENV_FILE" | sed 's/^/export /')
fi

BOT_DOMAIN="${BOT_DOMAIN:-bot.nexoranode.xyz:8443}"
BOT_USE_HTTPS="${BOT_USE_HTTPS:-true}"
NGINX_HTTP_PORT="${NGINX_HTTP_PORT:-80}"
NGINX_HTTPS_PORT="${NGINX_HTTPS_PORT:-8443}"

DOMAIN="${BOT_DOMAIN#https://}"
DOMAIN="${DOMAIN#http://}"
HOST="${DOMAIN%%:*}"

if [[ "$BOT_USE_HTTPS" == "true" ]]; then
  WEBHOOK_SCHEME="https"
  LOCAL_PORT="${NGINX_HTTPS_PORT}"
  PUBLIC_HEALTH="https://${DOMAIN}/health"
  LOCAL_CURL=(curl -sf --resolve "${HOST}:${LOCAL_PORT}:127.0.0.1")
else
  echo "WARN: BOT_USE_HTTPS=false — Telegram API rejects HTTP webhooks."
  echo "      Use HTTPS: bash $ROOT/deploy/setup-ssl.sh"
  WEBHOOK_SCHEME="http"
  LOCAL_PORT="${NGINX_HTTP_PORT}"
  PUBLIC_HEALTH="http://${DOMAIN}/health"
  LOCAL_CURL=(curl -sf)
fi

WEBHOOK_URL="${WEBHOOK_SCHEME}://${DOMAIN}/webhook"

bot_internal_health() {
  docker exec nexoranode-bot python -c \
    "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3); print('bot internal:', r.status, r.read().decode())" \
    2>/dev/null
}

wait_for_bot() {
  local elapsed=0
  echo "==> Waiting for bot to listen on :8090 (up to ${WAIT_SECS}s)..."
  while (( elapsed < WAIT_SECS )); do
    if bot_internal_health; then
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
    printf "."
  done
  echo
  echo "FAIL: bot not ready after ${WAIT_SECS}s"
  docker logs nexoranode-bot --tail 40 2>&1 || true
  return 1
}

echo "==> Configured webhook: ${WEBHOOK_URL}"

if [[ "$BOT_USE_HTTPS" == "true" ]]; then
  if [[ -f "${CERT_DIR}/fullchain.pem" && -f "${CERT_DIR}/privkey.pem" ]]; then
    echo "==> SSL certs: found in deploy/nginx/certs/"
  else
    echo "==> SSL certs: MISSING — run: bash $ROOT/deploy/setup-ssl.sh"
  fi
fi

echo
echo "==> Stack status"
$COMPOSE ps

echo
wait_for_bot

echo
echo "==> Repair gateway health (webhook entry — all Telegram traffic)"
if docker exec nexoranode-repair-bot python -c \
  "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8091/health', timeout=3); exit(0 if r.status==200 else 1)" \
  2>/dev/null; then
  echo "OK"
else
  echo "FAIL: repair gateway not healthy — users will get no response"
  echo "  cd $ROOT/deploy && $COMPOSE up -d --build repair-bot nginx"
fi

echo
echo "==> Repair gateway → main bot"
if docker exec nexoranode-nginx wget -qO- http://bot:8090/health 2>/dev/null | grep -q OK; then
  echo "OK"
else
  echo "FAIL: nginx cannot reach bot:8090"
  exit 1
fi

echo
echo "==> Local nginx health"
if "${LOCAL_CURL[@]}" "https://${HOST}:${LOCAL_PORT}/health" 2>/dev/null | grep -q OK || \
   curl -sf "http://127.0.0.1:${NGINX_HTTP_PORT}/health" 2>/dev/null | grep -q OK; then
  echo "OK"
else
  echo "FAIL: nginx health check failed"
  if [[ "$BOT_USE_HTTPS" == "true" ]]; then
    echo "Run: bash $ROOT/deploy/setup-ssl.sh && docker compose -f $ROOT/deploy/docker-compose.prod.yml restart nginx"
  fi
fi

echo
echo "==> Webhook POST test (via local nginx HTTPS)"
WH_CODE=$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 10 \
  -X POST "https://${HOST}:${LOCAL_PORT}/webhook" \
  --resolve "${HOST}:${LOCAL_PORT}:127.0.0.1" \
  -H "Content-Type: application/json" \
  -d '{"update_id":1,"message":{"message_id":1,"date":1,"chat":{"id":1,"type":"private"},"from":{"id":1,"is_bot":false,"first_name":"t"},"text":"/start"}}' \
  2>/dev/null)
WH_CODE="${WH_CODE:-000}"
echo "webhook POST local: HTTP ${WH_CODE}"
WEBHOOK_POST_OK=0
[[ "$WH_CODE" == "200" ]] && WEBHOOK_POST_OK=1

echo
echo "==> Telegram webhook info"
FAIL=0
if [[ -n "${BOT_TOKEN:-}" ]]; then
  INFO=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")
  echo "$INFO" | python3 -m json.tool
  URL=$(echo "$INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'].get('url',''))")
  PENDING=$(echo "$INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'].get('pending_update_count',0))")
  ERR=$(echo "$INFO" | python3 -c "import sys,json; r=json.load(sys.stdin)['result']; print(r.get('last_error_message') or '')")
  if [[ -z "$URL" ]]; then
    echo
    echo "CRITICAL: Webhook URL is empty — bot will not receive /start"
    echo "Fix: bash $ROOT/deploy/setup-ssl.sh && bash $ROOT/deploy/set-webhook.sh"
    FAIL=1
  elif [[ "$URL" != "$WEBHOOK_URL" ]]; then
    echo
    echo "WARN: Telegram has '$URL' but .env expects '$WEBHOOK_URL'"
    echo "Fix: bash $ROOT/deploy/set-webhook.sh"
    FAIL=1
  else
    echo
    echo "OK: webhook registered (${PENDING} pending updates)"
  fi
  if [[ -n "$ERR" ]]; then
    if [[ "$WEBHOOK_POST_OK" == "1" ]]; then
      echo "NOTE: stale Telegram error (from an earlier failed delivery): $ERR"
      echo "      Webhook POST test passed now — send /start to confirm."
    else
      echo "WARN: last Telegram error: $ERR"
      FAIL=1
    fi
  fi
else
  echo "Set BOT_TOKEN in $ENV_FILE"
  FAIL=1
fi

exit $FAIL
