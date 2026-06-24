#!/usr/bin/env bash
# Register Telegram webhook (HTTPS required by Telegram API).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source <(grep -E '^(BOT_TOKEN|BOT_DOMAIN|BOT_USE_HTTPS)=' "$ENV_FILE" | sed 's/^/export /')

BOT_DOMAIN="${BOT_DOMAIN:-bot.nexoranode.xyz:8443}"
BOT_USE_HTTPS="${BOT_USE_HTTPS:-true}"
DOMAIN="${BOT_DOMAIN#https://}"
DOMAIN="${DOMAIN#http://}"

if [[ "$BOT_USE_HTTPS" != "true" ]]; then
  echo "ERROR: Telegram requires HTTPS for webhooks. Set BOT_USE_HTTPS=true and install SSL certs."
  echo "Run: bash ${ROOT}/deploy/setup-ssl.sh"
  exit 1
fi

WEBHOOK_URL="https://${DOMAIN}/webhook"

if [[ -z "${BOT_TOKEN:-}" ]]; then
  echo "BOT_TOKEN not set in $ENV_FILE"
  exit 1
fi

echo "==> Setting webhook: ${WEBHOOK_URL}"
RESP=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")
echo "$RESP" | python3 -m json.tool

OK=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ok', False))")
if [[ "$OK" != "True" ]]; then
  echo ""
  echo "FAIL: webhook not set. Ensure HTTPS works:"
  echo "  bash ${ROOT}/deploy/verify-webhook.sh"
  exit 1
fi

echo ""
echo "==> Webhook info"
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool

echo ""
echo "Done. No bot restart needed — webhook is registered via Telegram API."
echo "If you changed BOT_DOMAIN or SSL certs, restart bot separately:"
echo "  cd ${ROOT}/deploy && docker compose -f docker-compose.prod.yml --env-file ../.env restart bot"
