<div align="center">

[简体中文](README.md) · **English**

# 🔍 `/ca` — Token Contract Intel Skill

**Understand any token in one minute** — `gmgn on-chain data` + `bankr metadata` + `X posts` + `LLM distillation` = a concise intel report

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Standard-purple.svg)](https://agentskills.io) [![Chains](https://img.shields.io/badge/Chains-SOL%20·%20BSC%20·%20BASE%20·%20ETH-green.svg)]() [![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)]()

```
┌──────────────────────────────────────────────────────────┐
│  📥  You: /ca 0x38298138dd4389013962d8492feaa5879408dba3 │
│                                                          │
│  ⚙️   gmgn ──┐                                            │
│       6551 ──┼─► LLM distillation ─► narrative report     │
│       bankr ─┘                                            │
│                                                          │
│  📤  $openhuman │ MC $1.9M │ 24h +363% │ 7 dimensions    │
└──────────────────────────────────────────────────────────┘
```

**🔗 Supported chains**: Solana · BSC · Base · ETH (auto-detected)

**🤝 Compatible tools**: [Claude Code](https://claude.com/code) · [OpenClaw](https://github.com/openclaw/openclaw) · [OpenAI Codex CLI](https://github.com/openai/codex) (and theoretically any tool that supports the [Agent Skills open standard](https://agentskills.io) — 40+ AI tools)

> ⚠️ **Note on language**: The default LLM (DeepSeek) outputs reports in **Chinese**. The skill is most useful if you can read Chinese, OR if you pipe the output to a translation tool. To get English output, you can edit the LLM prompt in `analyze.py` (search for the `_build_prompt` method) and change the language instructions.

</div>

---

## Sample Output

```
**$openhuman (openhuman)** | MC $1.9M (ATH $3.0M) | 24h +363.3% 📈
`0x38298138dd4389013962d8492feaa5879408dba3`  |  BASE  |  X:...  |  https://openhuman.lol
📡 Bankr | deployer:@Thirsty4P → feeRecipient:@senamakel | 🟡 community-deployed → betting on @senamakel to claim
💸 Fee | claimed 0 times / claimed 0.000 WETH / unclaimed 5.943 WETH

# $openhuman Intel Brief | 2026-05-19

## Core Narrative
- Type: community-deployed (bankr phishing pattern), tied to @senamakel's open-source GitHub project OpenHuman ...

## Narrative Timeline
- 2026-05-16 14:30 | @tiger_web3 (21.9K,✅) | "bought some openhuman on base, the upgraded open-source lobster"
- 2026-05-19 13:06 | @OrdzWorld (22.3K,✅) | "upgraded lobster, more local + persistent memory"
- ...

## Risk Signals
- 🚨 Fee recipient @senamakel hasn't publicly acknowledged, 5.94 WETH unclaimed
- ...
```

---

## Quick Start (3 steps)

### 1. Install to your AI tool

```bash
python install.py
```

Pick from the prompt:
- `1` Claude Code → installs to `~/.claude/skills/ca/`
- `2` OpenClaw → installs to `~/.openclaw/workspace/skills/ca/`
- `3` Codex CLI → installs to `~/.agents/skills/ca/`
- `4` Install to all three

### 2. Install dependencies

```bash
# Python deps
pip install -r requirements.txt

# Core data source (Node.js)
npm install -g gmgn-cli@1.0.1
```

### 3. Configure API keys

Copy `.env.example` to `~/.config/gmgn/.env` (Linux/Mac) or `C:\Users\<you>\.config\gmgn\.env` (Windows), then fill in:

**Required** (cannot skip):
- `GMGN_API_KEY` — get from https://gmgn.ai/ai
- `DEEPSEEK_API_KEY` — get from https://platform.deepseek.com/ (default LLM, cheapest at ~$0.002/call)

**Strongly recommended** (without these, all X social signals are missing and narrative quality drops sharply):
- `OPENTWITTER_TOKEN` — get from https://6551.io/mcp
- `TWITTERAPI_IO_KEY` — get from https://twitterapi.io

**Optional** (only needed for `--llm grok`):
- `XAI_API_KEY` — get from https://x.ai/api

---

## Usage

### Claude Code / OpenClaw (trigger with `/`)

```
/ca 0x38298138dd4389013962d8492feaa5879408dba3
/ca 9uQ9rdUE1AJpd3mFa9patGCy3Xi2tSp8qDyRwebqpump
/ca 0xabc... --llm grok --deep
/ca 0xabc... --chain bsc
```

### OpenAI Codex CLI (trigger with `$`)

```
$ca 0x38298138dd4389013962d8492feaa5879408dba3
```

### Optional flags

| flag | meaning | per-call cost |
|---|---|---|
| (none) | default deepseek-chat | ~$0.002 |
| `--deep` | deepseek-reasoner (reasoning mode) | ~$0.01 |
| `--llm grok` | grok-4-fast | ~$0.05 |
| `--llm grok --deep` | grok-4 | ~$0.15 |
| `--chain bsc\|base\|eth\|sol` | force chain (skip auto-detection) | — |

---

## Bonus tool: `claim_history.py`

Query the precise fee claim timeline (which second how much WETH was withdrawn) for any Base bankr token.

```bash
python claim_history.py 0x4c433f4ef87fe506a7eed2fd1d822cbed411eba3 --lookback 30000
```

Outputs a markdown table:
```
| # | Time (UTC) | block | WETH | TOKEN | TX |
|---|---|---|---|---|---|
| 1 | 2026-05-19 04:18:55 | 46187494 | 0.0669 | 432.23M | 0x953c... |
| ...
```

Data source: Base mainnet public RPC (`mainnet.base.org`), no API key needed.

---

## 📲 Optional module: Telegram bot

Bring `/ca` to Telegram — **send a contract address in your group, the bot replies with the full intel report**.

```
You: 0x38298138dd4389013962d8492feaa5879408dba3
bot (~15s later):
  $openhuman | MC $1.9M | 24h +363% | ... (full report)
```

Features:
- 🛡️ **Whitelist**: only responds in designated groups/DMs (anti-abuse)
- 💾 **Cache**: same CA within 5 minutes uses cache, saves API costs
- 🚦 **Rate limit**: 5 queries per user per minute
- 📊 **`/stats`** for 24h query stats
- 📏 Auto-splits messages longer than Telegram's 4096-char limit

Reuses the bundle's `analyze.py`, no code duplication. Detailed setup at [`tg-bot/README.en.md`](tg-bot/README.en.md).

Quick 4-step:
```bash
cd tg-bot
pip install -r requirements.txt              # installs python-telegram-bot
cp config.example.py config.py                # copy config
# edit config.py with your BOT_TOKEN and ALLOWED_CHAT_IDS
python bot.py
```

---

## 🏗️ Architecture

Three entry points sharing one core engine:

```
         ┌──────────────────────────────────────────────┐
         │     analyze.py (core engine, ~1100 lines)    │
         │                                              │
         │   gmgn + website + 6551 + bankr + LLM        │
         │              └──► Chinese intel report (stdout)│
         └──────▲─────────────▲─────────────▲───────────┘
                │             │             │
        ┌───────┴────┐ ┌──────┴──────┐ ┌────┴────────┐
        │ 🤖 AI tool │ │ 🐍 CLI       │ │ 📱 Telegram  │
        │  /ca <CA>  │ │ python ...  │ │  send CA in  │
        │            │ │             │ │  group      │
        └────────────┘ └─────────────┘ └─────────────┘
        SKILL.md +     direct subprocess  tg-bot/bot.py
        install.py                       +cache+limit+log
```

**Files per usage mode**:

| Entry point | Files used | Who converts user input to `analyze.py` call |
|---|---|---|
| AI tools (Claude Code / OpenClaw / Codex CLI) | `SKILL.template.md` + `install.py` | AI reads SKILL.md and uses its Bash tool |
| Direct CLI | `analyze.py` alone | You type it manually |
| Telegram group/DM | `tg-bot/` folder | `tg-bot/bot.py` subprocesses it, adds cache + rate limit |

**Key design**:

- ✅ **Single source of truth**: upgrade `analyze.py` once, all three usage modes benefit
- ✅ **Centralized data API keys**: all in `~/.config/gmgn/.env` (gmgn / DeepSeek / OpenTwitter / twitterapi.io / Grok)
- ✅ **tg-bot has separate config**: `tg-bot/config.py` only stores Telegram stuff (BOT_TOKEN / whitelist), decoupled from data keys — leaking one doesn't affect the other
- ✅ **Fully local**: data flows directly between `your machine ↔ data sources`, no third-party relay

**Data flow sharing**:

`tg-bot/bot.py` calls `subprocess.run([config.PYTHON_EXE, config.ANALYZE_PY, ca])`, where `config.ANALYZE_PY` is the `../analyze.py` in the parent directory. So:
- Want a new field in the report → only edit `analyze.py`
- All three AI tools + CLI + Telegram bot **instantly get the new field**, no separate update needed

---

## How it works (data pipeline)

1. **gmgn-cli chain sniffer + base data**: subprocess call, gets symbol / MC / 24h / top10 / risk scores
2. **Fetch website body**: HTML → plain text, truncated to 2000 chars
3. **6551 OpenTwitter API** (5 endpoints in parallel): user profile / latest 20 tweets / deleted tweets / KOL followers / CA search Top+Latest
4. **twitterapi.io X Community** (if project has a community): community info / moderators / mod tweets / top community tweets
5. **bankr.bot API** (Base only): `/token-launches/{ca}` for deployer + feeRecipient X handles; `/token-launches/{ca}/fees` for claim count + cumulative WETH
6. **DeepSeek / Grok distillation**: all raw materials sent to LLM, outputs Chinese report

The whole process runs **in parallel**, wall-clock time ~15-20 seconds (LLM is 10-15s of that).

---

## File listing

```
ca-skill-bundle/
├── README.md / README.en.md        # Chinese / English
├── LICENSE                         # MIT License
├── install.py                      # One-click installer (for AI tools)
├── SKILL.template.md               # skill template ({{SKILL_DIR}} replaced at install)
├── analyze.py                      # Main analysis script (~1100 lines Python)
├── claim_history.py                # Standalone tool: fee claim timeline
├── requirements.txt                # Python deps (requests + python-dotenv)
├── .env.example                    # API key template
└── tg-bot/                         # Optional module: Telegram bot
    ├── README.md / README.en.md    # tg-bot specific docs
    ├── bot.py                      # Entry point
    ├── config.example.py           # Config template (git-tracked)
    ├── handlers.py                 # Message handler + CA detection
    ├── cache.py                    # SQLite cache
    ├── requirements.txt            # python-telegram-bot
    └── start.bat                   # Windows one-click launch
```

---

## FAQ

**Q: What if I don't have `gmgn-cli` installed?**
A: The report will fail (gmgn is the core data source). Install first: `npm install -g gmgn-cli@1.0.1`.

**Q: Can I run with only `DEEPSEEK_API_KEY`?**
A: Yes, but narrative quality will be poor (all X social signals missing). **Strongly recommend at least adding `OPENTWITTER_TOKEN`**.

**Q: Is `$ca` in Codex CLI the same as `/ca`?**
A: Same functionality, just different trigger symbol. Codex uses `$skill-name`, Claude Code/OpenClaw use `/skill-name`.

**Q: I'm on Windows, will it work?**
A: Fully cross-platform. `install.py` auto-detects path separators. On Windows, `~/.claude/` resolves to `C:\Users\<you>\.claude\`.

**Q: Will installing the same skill to all 3 tools conflict?**
A: No. The three tools read different directories and don't interfere. Pick `4` in `install.py` to install to all three at once.

**Q: I want to customize the SKILL.md, add something?**
A: Edit `SKILL.template.md` (use `{{SKILL_DIR}}` as the placeholder), then re-run `install.py`.

**Q: How do I make the LLM output English instead of Chinese?**
A: Open `analyze.py`, search for the `_build_prompt` method. The Chinese language directives are explicitly inline — change them to English instructions and rebuild. (We may add a `--lang en` flag in a future PR. Issue welcome.)

---

## Acknowledgments & License

**Data sources**: [gmgn.ai](https://gmgn.ai) · [bankr.bot](https://bankr.bot) · [6551 OpenTwitter](https://6551.io) · [twitterapi.io](https://twitterapi.io) · [DeepSeek](https://platform.deepseek.com) · [xAI Grok](https://x.ai)

**Standard**: built on the [Agent Skills](https://agentskills.io) open standard (originated by Anthropic, 40+ AI tools support it).

**License**: [MIT License](LICENSE) — free to fork / modify / use commercially, just keep the copyright notice.

**Privacy**: this skill ships **no API keys** — you apply for all keys yourself, all data flows go directly between your machine and the data sources, never through any third-party relay.

---

<div align="center">

If this is useful, give it a ⭐ Star so more people can find it 🙏

[Report bug](https://github.com/cykings/agent-skill-ca/issues) · [Request feature](https://github.com/cykings/agent-skill-ca/issues) · [Fork](https://github.com/cykings/agent-skill-ca/fork)

</div>
