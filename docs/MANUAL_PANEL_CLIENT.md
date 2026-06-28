# Manual panel client → bot user

Use this when you **create a client directly in 3X-UI** and want it to appear in the bot under a specific user — with the same **QR + subscription link** message as an approved purchase.

---

## When to use

- Client already exists on the panel (manual / migration / support gift)
- You know the user's **Telegram ID** from the admin manage panel
- You do **not** need a fake purchase transaction

The bot only adds a `vpn_configs` row and (optionally) notifies the user. It does **not** create the panel client.

---

## Prerequisites

1. Client exists in **3X-UI** with:
   - **Email** = service name (`ali123` — lowercase, 3–30 chars, `a-z0-9`)
   - **Subscription ID** (`subId`) set
   - **Traffic limit** and **expiry** configured
   - **Inbounds** attached (same as bot-created clients)

2. User has **`/start`** the bot at least once (row in `users` table).

3. Run from server repo (same `.env` as the bot):

```bash
cd /opt/nexoranode-bot
```

---

## Quick start

```bash
# 1) Dry run — checks panel + user, no changes
python3 scripts/assign_panel_client.py \
  --tg-id 123456789 \
  --email ali123 \
  --dry-run

# 2) Assign + send activation message (QR + sub link)
python3 scripts/assign_panel_client.py \
  --tg-id 123456789 \
  --email ali123
```

The user receives the same photo message as after **admin approves a purchase receipt**.

---

## Options

| Flag | Description |
|------|-------------|
| `--tg-id` | User Telegram ID (required) |
| `--email` / `--service-name` | Panel client email (required) |
| `--plan-gb` | GB shown in message if panel total is 0 |
| `--plan-days` | Days for “starts after first connection” text |
| `--plan-id` | Stored in DB (default: `manual`) |
| `--plan-name` | Label in message (default: `VIP`) |
| `--no-send` | DB only — no Telegram message |
| `--no-sync-tg-id` | Do not set panel `tgId` to user |
| `--dry-run` | Validate only |

---

## Examples

```bash
# VIP 30 GB — explicit plan metadata
python3 scripts/assign_panel_client.py \
  --tg-id 987654321 \
  --email user42 \
  --plan-gb 30 \
  --plan-days 30 \
  --plan-id vip_30gb \
  --plan-name VIP

# Link silently (user already has the link)
python3 scripts/assign_panel_client.py \
  --tg-id 987654321 \
  --email user42 \
  --no-send
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `User tg_id=… not found` | User must `/start` the bot first |
| `Panel client … not found` | Create client in 3X-UI; email must match `--email` |
| `has no subId` | Set subscription ID on panel client |
| `already linked` | Client already in `vpn_configs` — use another name or delete old row |
| `Panel bootstrap failed` | Check `XUI_*` / token in `.env` |

---

## What the script does

1. Reads client from panel API (`get` + `traffic`)
2. Optionally sets panel `tgId` to the bot user
3. Ensures client is on configured inbounds
4. Inserts `vpn_configs` for that user
5. Sends `send_service_activated` (QR caption + copy/open buttons) unless `--no-send`

No bot restart required. User sees the service under **مدیریت کانفیگ‌ها** immediately.
