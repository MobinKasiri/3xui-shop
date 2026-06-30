# Disaster recovery — restore Germany master in ~30 minutes

If **Germany** (`91.107.177.122`) dies, UK/US/SG **real nodes keep running**. Users lose subscriptions, bot sales, and panel until the master is restored. This runbook gets you back in about **30 minutes**.

---

## Two backup layers (use both)

| Layer | What | RPO | Use when |
|-------|------|-----|----------|
| **Panel Telegram** (every 6h) | Panel DB snapshot (`.dump` on PostgreSQL, `x-ui.db` on SQLite) + `config.json` | up to 6h | Quick panel rollback on same server |
| **Full server backup** (`nc-vpn-backup`) | Panel PG + bot PG + `/opt/nexoranode-*` + x-ui + certs + nginx + UFW | daily (+ Mac copy) | **New VPS restore** |

Panel Telegram backup is **not** enough for DR. Enable **full backup** below.

---

## One-time setup (do this now)

### A — Germany server

```bash
cd /opt/nexoranode-bot
git pull
sudo bash deploy/backup/install-local-backup.sh
sudo nano /etc/nc-vpn/backup.env
```

Set at minimum:

- `XUI_PG_PASSWORD` — from 3X-UI panel → Settings → Database  
- Optional: `SCRIPTS_ROOT=/opt/VPN_project` if deploy repo is on the server  
- Optional: `BACKUP_EXTRA_PATHS=/path/to/sub-bridge` for anything custom  

Test:

```bash
sudo /usr/local/lib/nc-vpn-backup/run-local-backup.sh
ls -la /var/lib/nc-vpn-backup/export/latest/{dumps,meta,config,files}
cat /var/lib/nc-vpn-backup/export/latest/meta/dr-inventory.txt
```

Server also runs a **daily export at 02:30 UTC** (cron).

### B — Your Mac (off-site copy)

```bash
cd bot/3xui-shop
bash deploy/backup/mac/install-mac-backup.sh
nano ~/.config/nc-vpn/mac-backup.env
```

Set `SERVER_HOST=91.107.177.122`, `SERVER_SSH_PORT=2222`, SSH key.

Test pull:

```bash
bash deploy/backup/mac/pull-backup-to-mac.sh
ls -la ~/NCBackups/latest/
```

Daily **3:00 AM** Mac pull keeps **2 dated copies** under `~/NCBackups/`.

### C — Password manager (required for restore)

Save **outside** the backup bundle:

| Item | Where |
|------|--------|
| `/etc/nc-vpn/backup.env` | Full copy (contains `XUI_PG_PASSWORD`) |
| Germany SSH key | Mac `~/.ssh/...` |
| Node SSH / panel tokens | Only if not already in restored DB |
| Arvan CDN login | Origin IP for Iran WS path |
| Domain registrar / Cloudflare | DNS for `*.nexoranode.xyz`, `sub.manchesterchocolates.ir` |

Also keep **`scripts/xui-nodes.conf`** in git (already in repo).

---

## What full backup includes

- 3X-UI binary + systemd unit (`/usr/local/x-ui`, `/etc/x-ui`)
- 3X-UI PostgreSQL dump (`xui`) — clients, inbounds, **node registry**
- Bot PostgreSQL dump (`nexorabot`) — orders, users, plans
- `/opt/nexoranode-bot`, `/opt/nexoranode-panel`, `/opt/nexoranode-data`
- TLS: `/root/cert`, `/root/.acme.sh`, bot nginx certs in deploy tree
- Host nginx (`/etc/nginx`) if manage panel uses it
- UFW, fail2ban, SSH config snapshots
- Meta: public IP, docker state, `dr-inventory.txt`, optional `xui-nodes.conf`

**Not on master:** UK/US/SG node VPS configs — those servers stay up; master reconnects via restored DB.

---

## 30-minute restore timeline

| Min | Step |
|-----|------|
| 0–5 | Order Ubuntu 24.04 VPS, open ports 2222, 80, 443, 2057, 8443, 8880 |
| 5–10 | Copy backup + `backup.env` to new server |
| 10–25 | Run `restore-full-server.sh` |
| 25–30 | Update DNS + Arvan CDN origin if IP changed; smoke test |

---

## Restore procedure (new VPS)

### 1. Copy backup from Mac

```bash
# On Mac
scp -P 2222 -r ~/NCBackups/latest root@NEW_IP:/root/restore/latest
scp -P 2222 /path/to/backup.env root@NEW_IP:/etc/nc-vpn/backup.env
```

Or use the most recent dated folder under `~/NCBackups/`.

### 2. Clone bot repo on new server

```bash
ssh root@NEW_IP
apt-get update && apt-get install -y git
git clone <your-repo-url> /opt/nexoranode-bot
# Or rsync /opt/nexoranode-bot from backup tar if already in files/
```

### 3. Run restore

```bash
chmod 600 /etc/nc-vpn/backup.env
cd /opt/nexoranode-bot
sudo bash deploy/backup/restore-full-server.sh \
  --confirm-new-server \
  --from-dir /root/restore/latest
```

This reinstalls packages, extracts file archives, imports both databases, starts Docker (bot + panel + nginx), and restarts `x-ui`.

### 4. DNS (only if IP changed)

Point A records to **NEW_IP**:

- Panel host (e.g. `p.nexoranode.xyz` or your panel domain)
- `bot.nexoranode.xyz`
- `manage.nexoranode.xyz`
- Subscription host (`sub.manchesterchocolates.ir` or bridge domain)

**Arvan CDN:** If inbound **2** (Germany WS for Iran) uses Arvan, update **origin** to NEW_IP (port 8880 or your WS port).

Real nodes: **no DNS change** — they keep their own domains (`uk-n1.nexoranode.xyz`, etc.).

### 5. Smoke test

```bash
systemctl status x-ui
docker ps
curl -k -I https://bot.nexoranode.xyz:8443/health
```

Telegram:

- `/start` on sell bot
- Open subscription link for one client
- Connect VPN on **UK** and **Germany WS** profiles
- Panel → Clients → check **Online** on a connected client

---

## Quarterly DR drill (recommended)

1. Spin up a cheap test VPS.
2. Restore from `~/NCBackups/latest` (do **not** point production DNS at it).
3. Confirm panel login, bot webhook, one sub URL.
4. Destroy test VPS.

---

## If Mac backup is missing

1. Use latest on server: `/var/lib/nc-vpn-backup/export/` (keep 3 versions).
2. Or panel Telegram backup (`.dump` + `config.json` — panel only, no bot orders; see `scripts/PANEL-TELEGRAM-BACKUP.md`).
3. Worst case: rebuild from `scripts/xui-nodes.conf` + manual client re-import.

---

## Related docs

- [BACKUP.md](./BACKUP.md) — install & Mac pull
- [../../../../scripts/PANEL-TELEGRAM-BACKUP.md](../../../../scripts/PANEL-TELEGRAM-BACKUP.md) — panel-only 6h backup
- [../../../../scripts/README.md](../../../../scripts/README.md) — architecture & node deploy
