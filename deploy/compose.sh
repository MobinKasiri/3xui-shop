#!/usr/bin/env bash
# Run docker compose with the project .env (parent of deploy/).
# Compose reads .env from the compose file directory by default — that breaks
# POSTGRES_PASSWORD interpolation when .env lives in /opt/nexoranode-bot/.env
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT}/.env}"
COMPOSE_FILE="${ROOT}/deploy/docker-compose.prod.yml"

[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE"; exit 1; }

exec docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
