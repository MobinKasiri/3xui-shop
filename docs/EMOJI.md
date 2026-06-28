# Custom emoji guide (NC VPN bot)

The bot uses these Telegram sticker packs (animated vector emoji):

| Pack | Add link | Used for |
|------|----------|----------|
| **EmojiStatus** | https://t.me/addemoji/EmojiStatus | Welcome text, home, status |
| **NewsEmoji** | https://t.me/addemoji/NewsEmoji | Buy button (☄️), news-style icons |
| **tgmacicons** | https://t.me/addemoji/tgmacicons | Mac-style UI icons |
| **vector_icons_by_fStikBot** | https://t.me/addemoji/vector_icons_by_fStikBot | Colorful UI icons |
| **FlagsPack** | https://t.me/addemoji/FlagsPack | Country flags (VIP locations) |

**Requirements:** Telegram Premium on the **BotFather bot owner** account. Add **all** packs on that account, then sync.

---

## One-time server setup

```bash
cd /opt/nexoranode-bot

# 1) Add every pack link above on the bot-owner Telegram app
# 2) Sync sticker IDs → /opt/nexoranode-data/emoji_ids.json
python3 scripts/sync_emoji_packs.py

# 3) Rebuild
./deploy/compose.sh up -d --build bot
```

Startup log should show: `Custom emoji ready: N icons from 5 packs`

**Deploy / pull:** `./deploy/pull.sh` (resets local registry edits, pulls git, syncs IDs).

---

## How to assign a pack & icon yourself

This is the full workflow — same steps whether you change one icon or add a whole new pack.

### 1. Add the pack on Telegram

Open the link (e.g. https://t.me/addemoji/NewsEmoji) **on the BotFather owner account** → **Add**.

### 2. Register the pack in the bot (new packs only)

Edit `scripts/sync_emoji_packs.py`:

```python
PACKS = (
    "EmojiStatus",
    ...
    "NewsEmoji",   # ← add short name exactly as in t.me/addemoji/NewsEmoji
)

ADD_LINKS = {
    ...
    "NewsEmoji": "https://t.me/addemoji/NewsEmoji",
}
```

Also add `"NewsEmoji": []` to `app/bot/i18n/emoji_ids.example.json`.

### 3. Sync IDs from Telegram

```bash
python3 scripts/sync_emoji_packs.py
```

This writes `emoji_ids.json` (live copy: `/opt/nexoranode-data/emoji_ids.json` on server).

### 4. Find the index for the sticker you want

```bash
# List whole pack
python3 scripts/list_emoji_packs.py --pack NewsEmoji

# Filter by Unicode preview (what Telegram stores as alt)
python3 scripts/list_emoji_packs.py --pack EmojiStatus --grep 1⃣
python3 scripts/list_emoji_packs.py --pack NewsEmoji --grep ☄
```

Note the **`idx`** column (0-based). Example:

```
 idx  alt       id
--------------------------------------------------------
   8  1⃣        5794113621940246933    ← use index 8
  32  ⭐️        5807752501042089473    ← use index 32
  88  🔧         5823268688874179761    ← use index 88
   3  ☄️        …                      ← buy button (NewsEmoji)
```

### 5. Map a semantic key → pack + index

Edit **`app/bot/i18n/emoji_registry.json`** (or `scripts/verified_emoji_indices.json` then run `apply_verified_emoji_map.py`):

```json
"wave": {
   "pack": "EmojiStatus",
   "index": 8,
   "fallback": "1⃣",
   "alt": "1⃣",
   "locked": true
},
"btn_buy": {
   "pack": "NewsEmoji",
   "index": 3,
   "fallback": "☄️",
   "btn_fallback": "☄️",
   "locked": true
}
```

| Field | Meaning |
|-------|---------|
| `pack` | Sticker set name (`NewsEmoji`, `EmojiStatus`, …) |
| `index` | Position in that pack (from step 4) |
| `fallback` | Unicode placeholder in **messages** before sync / inside `<tg-emoji>` |
| `btn_fallback` | Unicode placeholder for **buttons** (optional; defaults to `fallback`) |
| `locked` | Optional — prevents `auto_map` from overwriting your pick |

Apply curated map:

```bash
python3 scripts/apply_verified_emoji_map.py
```

### 6. Use the key in code

**Messages** (`app/bot/i18n/fa.py`) — animated emoji in message text:

```python
from app.bot.utils.emoji import i, p

WELCOME = (
    f"خوش اومدی! {i('wave')}\n\n"      # inline icon (1⃣)
    f"{p('globe')}اینجا VPN می‌گیری\n"  # icon + space at line start (⭐️)
    f"{p('handshake')}پشتیبانی 24/7\n"  # last line icon (🔧)
)
```

| Function | When to use |
|----------|-------------|
| `i('key')` | Icon **inside** a sentence |
| `p('key')` | Icon at the **start of a line** (adds trailing space) |

**Buttons** (`keyboards.py` / handlers) — vector icon on inline keyboard:

```python
.btn(fa.MAIN_BTN_BUY, callback_data="menu:buy", icon="btn_buy")  # ☄️ from NewsEmoji
```

Button label text stays plain Persian; Telegram draws the animated icon separately.

### 7. Deploy

```bash
git pull   # or push from dev first
python3 scripts/sync_emoji_packs.py
./deploy/compose.sh up -d --build bot
```

---

## Current home-page mapping (example)

| Line in welcome | Registry key | Pack | Index | Sticker |
|-----------------|--------------|------|-------|---------|
| End of title | `wave` | EmojiStatus | 8 | 1⃣ |
| VPN line | `globe` | EmojiStatus | 32 | ⭐️ |
| Support line | `handshake` | EmojiStatus | 88 | 🔧 |
| **Buy button** (not message) | `btn_buy` | NewsEmoji | 3 | ☄️ |

Middle line (`bolt` / ⚡) unchanged unless you edit `bolt` in the registry the same way.

---

## How icons are wired (3 files)

```
emoji_registry.json   ← YOU edit: semantic key → pack + index
emoji_ids.json        ← AUTO: pack → list of {index, alt, id} from Telegram
fa.py / handlers      ← i('wave'), p('globe'), icon='btn_buy'
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Plain Unicode instead of animated | Run `sync_emoji_packs.py` + rebuild; Premium on bot owner |
| Wrong icon (block, heart, book…) | **Wrong index** — re-run `list_emoji_packs.py`, fix `index` |
| New pack missing | Add to `PACKS` in sync script + add on Telegram + sync |
| STICKERSET_INVALID | Open addemoji link on **bot owner** account |
| Git pull blocked on server | `./deploy/pull.sh` (resets local registry edits) |

**Do not** rely on blind `auto_map --write` — many stickers have empty or mismatched `alt` text.  
Use `list_emoji_packs.py` + manual index, or `verified_emoji_indices.json`.

---

## Other notes

- **Callback alerts** (`show_alert=True`) — plain text only; use `u('key')` Unicode fallback.
- **Flags in plans.json:** `"code": "de"` not `"flag": "🇩🇪"`.
- **Plan button icons:** `"emoji_key": "star"` in `plans.json` → key in registry.
