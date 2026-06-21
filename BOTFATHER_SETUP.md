# NC VPN — New Telegram Bot (BotFather)

Use this when switching from the old Nexora bot to a new **NC VPN** bot.

## 1. Create bot in BotFather

1. Open [@BotFather](https://t.me/BotFather)
2. `/newbot`
3. **Display name:** `NC VPN` (or `NC VPN Bot`)
4. **Username:** must end with `bot`, e.g. `@nc_vpn_bot` (pick an available name)
5. Copy the **HTTP API token**

Optional in BotFather (bot also sets these on startup from `fa.py`):

- `/setdescription` — long “What can this bot do?” text
- `/setabouttext` — short subtitle
- `/setuserpic` — NC VPN logo

## 2. Update server `.env`

On Germany (`/opt/nexoranode-bot/.env`):

```env
BOT_TOKEN=123456:ABC...your-new-token...
BOT_USERNAME=nc_vpn_bot          # without @ — must match BotFather username
SUPPORT_USERNAME=your_support    # e.g. ncvpn_support
CARD_OWNER=NC VPN                # shown on card-to-card screen
```

Keep existing `XUI_*`, `DATABASE_*`, `REDIS_*`, webhook domain unchanged unless you move the bot URL.

## 3. Deploy

```bash
cd /opt/nexoranode-bot
docker compose --env-file .env -f deploy/docker-compose.prod.yml up -d --build bot
```

On startup the bot calls `setMyDescription` / `setMyShortDescription` with **NC VPN** text from `app/bot/i18n/fa.py`.

## 4. Webhook (new token)

```bash
source /opt/nexoranode-bot/.env
curl "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://bot.nexoranode.xyz:8443/webhook"
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

## 5. Verify

- `/start` → welcome says **NC VPN**
- Bot profile in Telegram → NC VPN description
- Old bot (`@vpn_nexora_bot`) can stay online or be disabled in BotFather (`/deletebot`) when you no longer need it

## What was rebranded in code

| Area | File |
|------|------|
| All user messages & buttons | `app/bot/i18n/fa.py` |
| Bot profile (auto on start) | `app/bot/utils/commands.py` + `fa.py` |
| Logs | `app/__main__.py` |

Infrastructure names (Docker, DB, `bot.nexoranode.xyz`, panel URLs) are unchanged — only customer-facing **NC VPN** branding.
