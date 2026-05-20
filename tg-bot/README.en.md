# 📲 Telegram bot (optional module)

[简体中文](README.md) · **English**

Bring `/ca` to Telegram. **Send a contract address in your group — the bot auto-returns the full intel report**.

Reuses the parent directory's `analyze.py`, no code duplication.

---

## Effect

```
You (in group): 0x38298138dd4389013962d8492feaa5879408dba3

bot (~15s later):
$openhuman | MC $1.9M | 24h +363% | (full Chinese intel report...)
```

## Features

- **Whitelist**: only responds in designated groups/DMs, ignores everything else (anti-abuse)
- **Cache**: same CA within 5 minutes returns cached report (saves API costs)
- **Rate limit**: max 5 queries per user per minute
- **Logging**: SQLite tracks every query, `/stats` shows 24h statistics
- **Auto-split**: reports exceeding Telegram's 4096-char limit split into multiple messages

---

## 4-step setup

### 1️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

Installs `python-telegram-bot[ext]>=21.0`.

### 2️⃣ Create a Telegram bot

Go to [@BotFather](https://t.me/BotFather) and send:
- `/newbot`
- Pick a display name (any language)
- Pick a username (must end in `_bot`, globally unique)
- Receive your **Bot Token**, looks like: `1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` (yours will differ)

**Critical setting**: send `/setprivacy` → pick your bot → **Disable**
(Without this, the bot can only see messages where it's @-mentioned in groups, not plain text with contract addresses.)

### 3️⃣ Copy config + fill token

```bash
# Mac/Linux
cp config.example.py config.py

# Windows
copy config.example.py config.py
```

Edit `config.py`:

```python
BOT_TOKEN = "paste your token here"
BOT_USERNAME = "your_bot_username"     # without @, log display only

ALLOWED_CHAT_IDS = [
    123456789,         # your own user_id (for DM)
    -1001234567890,    # group chat_id (for group use)
]
```

**How to get user_id / chat_id**:
- Your user_id: send `/start` to [@userinfobot](https://t.me/userinfobot), it'll tell you
- Group chat_id: add bot to group → start the bot → send any message in the group → bot's console prints `[chat_id] @xxx ...`, that number is the chat_id

### 4️⃣ Launch

```bash
python bot.py
```

Or on Windows, double-click `start.bat`.

When you see `✅ Bot started @your_bot`, it's working. **Keep the window open** — the bot listens as long as the process runs.

---

## Usage

Just send a contract address directly in your group (no prefix needed):
```
0x38298138dd4389013962d8492feaa5879408dba3
9uQ9rdUE1AJpd3mFa9patGCy3Xi2tSp8qDyRwebqpump
```

You can also use `/ca` prefix (consistent with Claude Code):
```
/ca 0x38298138dd4389013962d8492feaa5879408dba3
```

Bot commands:
- `/start` — help message
- `/stats` — last 24h query stats (total / cache hit rate / unique CAs / unique users)

---

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `❌ config.py not found` | Haven't copied config yet | `cp config.example.py config.py` |
| `❌ BOT_TOKEN is empty` | config.py token not filled | Edit config.py, fill the token |
| `Conflict: terminated by other getUpdates` | Same token running in another process | Kill all python.exe in Task Manager, wait 30 seconds, restart |
| Sending in group, no response | privacy mode not disabled | @BotFather → /setprivacy → pick your bot → Disable |
| Sending in DM, no response | Your user_id not in ALLOWED_CHAT_IDS | Get your user_id from @userinfobot, add it |
| `analyze.py failed` | Parent `analyze.py` not set up | Follow the main README to install gmgn-cli + Python deps + API keys |

---

## Deployment tips

- **Local** (simplest): keep computer on + start.bat running
- **Background** (Mac/Linux): `nohup python bot.py > bot.log 2>&1 &`
- **As a service** (recommended): wrap with systemd / pm2 / Windows Service
- **24/7 on cloud**: deploy to VPS (Hetzner / Vultr / DigitalOcean $5/mo, CPU/RAM is more than enough)

---

## File listing

```
tg-bot/
├── README.md / README.en.md  Documentation (Chinese / English)
├── bot.py                    Entry point
├── config.example.py         Config template (git-tracked)
├── config.py                 Actual config (git-ignored, you create it)
├── handlers.py               Message handler + CA detection + analyze.py invocation
├── cache.py                  SQLite cache + query log
├── requirements.txt          Python dependencies
├── start.bat                 Windows double-click launch
└── ca_cache.db               Created at runtime (git-ignored)
```
