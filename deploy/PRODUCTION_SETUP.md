# NC VPN Bot — Production Deployment Checklist

## Phase 5 — Pre-Deploy Steps (Human Actions Required)

### 1. Fill Production Secrets

Copy the template and fill every value:
```bash
cp .env.production.example .env.production
nano .env.production
```

Required fields:
- `BOT_TOKEN` — BotFather token for `@nc_vpn_bot` (see [BOTFATHER_SETUP.md](../BOTFATHER_SETUP.md))
- `BOT_ADMINS` — your Telegram numeric ID (e.g. `503376556`)
- `BOT_DOMAIN` — `bot.nexoranode.xyz:8443` (port 8443 because 443 is used by Reality)
- `NGINX_HTTPS_PORT` — `8443`
- `NGINX_HTTP_PORT` — `8080` (change if 80/8080 is also taken)
- `XUI_USERNAME` / `XUI_PASSWORD` — 3X-UI panel admin credentials
- `DATABASE_URL` — `postgresql+asyncpg://nexora:STRONG_PASS@nexoranode-postgres:5432/nexorabot`
- `POSTGRES_PASSWORD` — same strong password
- `REDIS_HOST` — `nexoranode-redis`
- `CARD_NUMBER` / `CARD_OWNER` — Iranian bank card for payments
- `ADMIN_CHAT_ID` — your Telegram ID (receives payment receipts)
- `AGENCY_ADMIN_CHAT_ID` — your Telegram ID (receives agency requests)
- `SUPPORT_USERNAME` — `@your_support_username`
- `BOT_USE_POLLING` — set to `false`

### 2. DNS Configuration

In Cloudflare (or your DNS provider):
1. Create A-record: `bot.nexoranode.xyz → 91.107.187.178`
2. **IMPORTANT:** Set Cloudflare proxy to **OFF** (grey cloud) — not orange.
   Orange cloud breaks Let's Encrypt HTTP-01 challenge.
3. Wait for DNS propagation (usually < 5 min with Cloudflare).

### 3. SSL Certificate

**Option A — Certbot (recommended):**
```bash
# On server (after DNS propagates):
apt install certbot
certbot certonly --standalone -d bot.nexoranode.xyz
# Certs land at: /etc/letsencrypt/live/bot.nexoranode.xyz/
mkdir -p deploy/nginx/certs
cp /etc/letsencrypt/live/bot.nexoranode.xyz/fullchain.pem deploy/nginx/certs/
cp /etc/letsencrypt/live/bot.nexoranode.xyz/privkey.pem deploy/nginx/certs/
```

**Option B — Pre-issued cert:** Place your `fullchain.pem` and `privkey.pem` in `deploy/nginx/certs/`.

### 4. Deploy

**First time — move live config outside git (recommended):**
```bash
cd /opt/nexoranode-bot
sudo bash deploy/setup-data-dir.sh   # creates /opt/nexoranode-data, updates .env files
```

**Updates (safe pull — never conflicts with panel-edited plans.json):**
```bash
cd /opt/nexoranode-bot
./deploy/pull.sh
./deploy/compose.sh up -d --build bot
```

Or manually:
```bash
cd /opt/nexoranode-bot
git pull   # only safe after setup-data-dir.sh OR deploy/pull.sh
cp .env.production .env   # first deploy only
./deploy/compose.sh up -d --build
docker exec nexoranode-bot poetry run alembic -c /app/db/alembic.ini upgrade head
```

### 5. Set Telegram Webhook

After deploy, set the webhook:
```bash
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://bot.nexoranode.xyz:8443/webhook"
```

Expected response: `{"ok":true,"result":true,"description":"Webhook was set"}`

### 6. Health Check

```bash
curl -k https://bot.nexoranode.xyz:8443/health
# Expected: 200 OK
```

Check bot logs:
```bash
docker logs nexoranode-bot -f
# Should show: "Webhook set: https://bot.nexoranode.xyz:8443/webhook"
# Should show: "✅ Inbound bootstrap OK — WS: X, Reality: Y"
```

### 7. End-to-End Smoke Test

Test each flow in production:
- [ ] Send `/start` → Persian welcome + 10 buttons appear
- [ ] Click "سرویس رایگان" → confirm trial → service created (requires real panel creds)
- [ ] Click "خرید سرویس" → choose plan → card-to-card → upload receipt → admin receives forward
- [ ] Admin taps ✅ → user receives subscription URL
- [ ] Click "سرویس‌های من" → shows services with live traffic bar
- [ ] Click "کیف پول" → shows balance, top-up flow works
- [ ] Click "تمدید سرویس" → renewal with wallet works
- [ ] Click "معرفی به دوستان" → referral link shown
- [ ] Click "راهنمای استفاده" → all 5 sub-pages work
- [ ] Click "درخواست نمایندگی" → message captured, admin forwarded
- [ ] `/admin` command → dashboard with stats

### 8. 24h Soak

Leave the bot running for 24 hours. Watch for:
- APScheduler logs every 30 min (traffic sync)
- APScheduler logs every hour (expiry + traffic checks)
- No crashed containers (`docker ps`)

## Maintenance Notes

- Renew Let's Encrypt cert every 90 days:
  ```bash
  certbot renew
  cp /etc/letsencrypt/live/bot.nexoranode.xyz/*.pem deploy/nginx/certs/
  docker restart nexoranode-nginx
  ```
- Update bot:
  ```bash
  cd /opt/nexoranode-bot && ./deploy/pull.sh && ./deploy/compose.sh up -d --build bot
  ```
- **Do not** edit `plans.json` in git — use the admin panel. Live file lives in `/opt/nexoranode-data/`.
- View logs: `docker logs nexoranode-bot -f --tail=100`
- DB backup: `docker exec nexoranode-postgres pg_dump -U nexora nexorabot > backup.sql`
