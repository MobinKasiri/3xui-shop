#!/usr/bin/env bash
# deploy.sh — Deploy Nexoranode VPN Bot to production server.
# Usage: ./deploy/deploy.sh <ssh_key_path>
# Example: ./deploy/deploy.sh ~/.ssh/nexora_key

set -euo pipefail

SSH_KEY="${1:-~/.ssh/id_rsa}"
REMOTE_HOST="91.107.187.178"
REMOTE_PORT="2222"
REMOTE_USER="root"
REMOTE_DIR="/opt/nexoranode-bot"
BOT_TOKEN_VAR="BOT_TOKEN"

# ─── Color helpers ────────────────────────────────────────────────────────────
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Validate env file ────────────────────────────────────────────────────────
[[ -f .env.production ]] || error ".env.production not found. Copy .env.production.example and fill it."
source .env.production
[[ -n "${BOT_TOKEN:-}" ]] || error "BOT_TOKEN is empty in .env.production"

info "Connecting to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT} ..."

SSH_CMD="ssh -p ${REMOTE_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST}"

# ─── 1. Pull latest code ──────────────────────────────────────────────────────
info "Pulling latest code..."
$SSH_CMD "mkdir -p ${REMOTE_DIR} && cd ${REMOTE_DIR} && git pull || git clone https://github.com/YOUR_REPO/nexoranode-bot.git ."

# ─── 2. Copy environment file ─────────────────────────────────────────────────
info "Uploading .env.production ..."
scp -P ${REMOTE_PORT} -i ${SSH_KEY} .env.production ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/.env

# ─── 3. Build & start containers ─────────────────────────────────────────────
info "Building and starting containers..."
$SSH_CMD "cd ${REMOTE_DIR} && docker compose -f deploy/docker-compose.prod.yml pull && docker compose -f deploy/docker-compose.prod.yml up -d --build"

# ─── 4. Run Alembic migrations ───────────────────────────────────────────────
info "Running database migrations..."
$SSH_CMD "cd ${REMOTE_DIR} && docker exec nexoranode-bot poetry run alembic -c /app/db/alembic.ini upgrade head"

# ─── 5. Set Telegram webhook ─────────────────────────────────────────────────
WEBHOOK_URL="https://${BOT_DOMAIN}/webhook"
info "Setting Telegram webhook to ${WEBHOOK_URL} ..."
curl -sS "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}" | python3 -m json.tool

# ─── 6. Health check loop ────────────────────────────────────────────────────
info "Health checking..."
for i in {1..12}; do
    STATUS=$(curl -o /dev/null -sk -w "%{http_code}" "https://${BOT_DOMAIN}/health" 2>/dev/null || echo "000")
    if [[ "$STATUS" == "200" ]]; then
        info "✅ Bot is healthy!"
        break
    fi
    warn "Health check attempt $i/12 — HTTP ${STATUS}. Waiting 10s..."
    sleep 10
done

info "✅ Deployment complete!"
