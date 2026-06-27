# Custom emoji guide (NC VPN bot)

The bot uses **only these Telegram sticker packs** (animated vector emoji):

| Pack | Add link | Used for |
|------|----------|----------|
| **EmojiStatus** | https://t.me/addemoji/EmojiStatus | Status, payment, badges |
| **tgmacicons** | https://t.me/addemoji/tgmacicons | Mac-style UI icons |
| **vector_icons_by_fStikBot** | https://t.me/addemoji/vector_icons_by_fStikBot | General UI + home buttons |
| **FlagsPack** | https://t.me/addemoji/FlagsPack | Country flags (VIP locations) |

**Requirements:** Telegram Premium on the **BotFather bot owner** account. Add all four packs on that account before syncing.

---

## One-time server setup

```bash
cd /opt/nexoranode-bot

# 1) Sync sticker IDs from Telegram → emoji_ids.json
python3 scripts/sync_emoji_packs.py

# 2) Match registry indices by Unicode alt (🇩🇪, 🛒, …)
python3 scripts/auto_map_emoji_registry.py --write

# 3) Rebuild bot
./deploy/compose.sh up -d --build bot
```

Startup log should show: `Custom emoji ready: N icons from 4 packs`

---

## How icons are wired (3 files)

```
emoji_registry.json   ← YOU edit: semantic key → pack + index
emoji_ids.json        ← AUTO: pack → list of {index, alt, id} from Telegram
fa.py / handlers      ← use i('wave'), p('wallet'), icon='btn_buy' in keyboards
```

### Semantic keys (examples)

| Key | Where used |
|-----|------------|
| `wave`, `globe`, `wallet` | Welcome text, errors (`p('wallet')`) |
| `btn_buy`, `btn_configs` | Main menu inline buttons |
| `flag_de`, `flag_us` | VIP location line in shop |
| `confirm`, `reject` | Admin approve/reject |

Full list: `app/bot/i18n/emoji_registry.json`

---

## How to change an icon

### Step 1 — Browse the pack

After sync, list every sticker with its **index** and **alt** (the small Unicode preview Telegram stores):

```bash
python3 scripts/list_emoji_packs.py

# One pack only:
python3 scripts/list_emoji_packs.py --pack vector_icons_by_fStikBot

# Find Germany flag:
python3 scripts/list_emoji_packs.py --pack FlagsPack --grep 🇩🇪
```

Example output:

```
## FlagsPack (195 icons)
 idx  alt       id
--------------------------------------------------------
   0  🇩🇪       1234567890123456789
   1  🇵🇱       9876543210987654321
```

### Step 2 — Edit `emoji_registry.json`

Change the **`index`** (and **`pack`** if needed) for the semantic key:

```json
"btn_buy": {
   "pack": "vector_icons_by_fStikBot",
   "index": 16,
   "fallback": "🛒",
   "btn_fallback": "🛒"
}
```

- **`index`** = row number from `list_emoji_packs.py` (0-based, same order as `getStickerSet`)
- **`fallback`** / **`btn_fallback`** = Unicode shown **before sync** and inside `<tg-emoji>` as placeholder; auto_map matches by this character

Or re-run auto-map after changing only `fallback`:

```bash
python3 scripts/auto_map_emoji_registry.py --write
```

### Step 3 — Rebuild

```bash
./deploy/compose.sh up -d --build bot
```

No second sync needed unless the pack itself changed on Telegram.

---

## Using icons in code

| Function | Use in |
|----------|--------|
| `p('wallet')` | Start of a line in HTML messages → animated icon + space |
| `i('wave')` | Inline animated icon in HTML |
| `u('confirm')` | Plain Unicode (popup alerts, button fallback text) |
| `flag_i('de')` | Flag in HTML (`FlagsPack`) |
| `icon='btn_buy'` | Vector icon on inline keyboard button |

**Messages** (`fa.py`): always use `p()` / `i()` — never paste raw 🛒 in strings.

**Buttons** (`keyboards.py`): pass `icon="btn_buy"`; label text stays plain Persian.

**Flags in plans.json** (live file on server):

```json
"locations": [
  { "code": "de", "name": "آلمان" },
  { "code": "us", "name": "آمریکا" }
]
```

Add new countries in `emoji_registry.json` as `flag_xx` + run auto_map.

**Plan row icons** in `plans.json`:

```json
{ "emoji_key": "star", "recommended": true }
```

Keys must exist in `emoji_registry.json` (`star`, `medal`, `diamond`, …).

---

## What is *not* customizable

- **Callback popup alerts** (`show_alert=True`) — Telegram allows **plain text only** (no animated emoji). Those use `u()` Unicode fallback.
- **Button label font** — Telegram renders keyboard text in its own style; you can add vector icons via `icon_custom_emoji_id`, not bold/HTML.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Plain Unicode instead of animated | Run sync + auto_map + rebuild; check Premium on bot owner |
| Wrong icon | Fix `index` in registry or re-run `auto_map --write` |
| Flag missing | Add `flag_xx` to registry; `list_emoji_packs --pack FlagsPack --grep 🇩🇪` |
| STICKERSET_INVALID | Open addemoji links on **bot owner** account |
