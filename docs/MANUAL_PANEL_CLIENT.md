# Manual panel client → bot user

Use when a client was created **directly in 3X-UI** (offline card payment, user not technical).

---

## Three scripts (independent)

| Script | What it does |
|--------|----------------|
| `./scripts/assign-panel-client.sh` | Link panel client → user + send QR/sub (no transaction) |
| `./scripts/record-purchase-transaction.sh` | **Confirmed purchase tx only** → manage panel revenue (no panel/bot create) |
| `./scripts/manual-purchase.sh` | Both, or `--assign-only` / `--tx-only` |

All run **inside Docker** (not host `python3`):

```bash
cd /opt/nexoranode-bot
git pull && ./deploy/compose.sh up -d --build bot
```

---

## Your case: client already assigned, payment missing from panel

User paid to your wallet; you created client on panel and ran assign. **Only record the transaction:**

```bash
./scripts/record-purchase-transaction.sh \
  --tg-id 107177203 \
  --email cuazm8eexy \
  --amount 370000 \
  --plan-id vip_30g_30d
```

Dry run first:

```bash
./scripts/record-purchase-transaction.sh \
  --tg-id 107177203 \
  --email cuazm8eexy \
  --amount 370000 \
  --plan-id vip_30g_30d \
  --dry-run
```

This adds a **confirmed** `purchase` row linked to `vpn_configs` — shows in manage panel revenue. **Does not** create a duplicate panel client.

If duplicate warning: add `--force` (same user paid twice intentionally).

---

## New offline customer (full flow)

```bash
# 1) Create client on 3X-UI panel manually
# 2) One command: assign + transaction + notify user
./scripts/manual-purchase.sh \
  --tg-id 107177203 \
  --email cuazm8eexy \
  --amount 370000 \
  --plan-id vip_30g_30d
```

Or step by step:

```bash
./scripts/assign-panel-client.sh --tg-id ID --email NAME
./scripts/record-purchase-transaction.sh --tg-id ID --email NAME --amount N --plan-id PLAN
```

`manual-purchase.sh` with default (no flags) runs assign then tx; **skips assign** if already linked, then records tx.

---

## Assign only

```bash
./scripts/assign-panel-client.sh --tg-id ID --email PANEL_EMAIL [--service-name DISPLAY]
```

- `--email` = **3X-UI client email** (e.g. `u123@nexora.vpn` or legacy `ali123`)
- `--service-name` = optional bot label (default: panel **comment**)

User gets the same QR + subscription message as an approved purchase. No transaction row.

---

## Transaction-only flags

| Flag | Description |
|------|-------------|
| `--amount` | Paid amount in Toman (required) |
| `--plan-id` | From `plans.json` e.g. `vip_30g_30d` (required) |
| `--payment-method` | `card` (default) or `wallet` |
| `--config-id` | Optional `vpn_configs.id` if email lookup fails |
| `--force` | Allow duplicate confirmed tx |
| `--dry-run` | Validate only |

---

## Assign flags

| Flag | Description |
|------|-------------|
| `--plan-gb` / `--plan-days` | Shown in activation message |
| `--plan-name` | Label in activation message (default: tier name from plans.json) |
| `--no-send` | No Telegram message |
| `--no-sync-tg-id` | Do not set panel tgId |

---

## Prerequisites

- Client on 3X-UI with email, subId, traffic, inbounds
- User has `/start` the bot
- `plan-id` must exist in live `/opt/nexoranode-data/plans.json`

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No bot config for …` | Run assign first, or pass `--config-id` |
| `Duplicate confirmed purchase` | Tx already recorded; use `--force` if intentional |
| `Plan … not found` | Check plan id in plans.json |
| `ModuleNotFoundError: aiogram` | Use `.sh` wrappers, not host `python3` |
| `User tg_id=… not found` | User must `/start` the bot first |
| `already linked` | Use `record-purchase-transaction.sh` only — do not assign again |
| `Panel client … not found` | `--email` must be the exact 3X-UI client email |
| `service name taken` (bot) | Same user picked a name they already use — choose another label |
