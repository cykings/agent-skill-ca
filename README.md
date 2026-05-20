# /ca — 代币合约情报速查 skill

跨平台 Agent Skill。输入一个代币 CA，一分钟内拿到一份精简的中文情报报告：核心叙事 + 官方账号在说什么 + 叙事演变时间线 + 关键 KOL（含反向砸盘信号） + Bankr 部署元数据 + Fee claim 状态 + 风险信号。

**支持链**：Solana / BSC / Base / ETH（自动嗅探）

**支持的 AI 工具**：
- ✅ [Claude Code](https://claude.com/code)
- ✅ [OpenClaw](https://github.com/openclaw/openclaw)
- ✅ [OpenAI Codex CLI](https://github.com/openai/codex)
- 理论上兼容所有支持 [Agent Skills 标准](https://agentskills.io) 的工具

---

## 报告示例

```
**$openhuman (openhuman)** | MC $1.9M (ATH $3.0M) | 24h +363.3% 📈
`0x38298138dd4389013962d8492feaa5879408dba3`  |  BASE  |  X:...  |  https://openhuman.lol
📡 Bankr | deployer:@Thirsty4P → feeRecipient:@senamakel | 🟡 社区代发 → 赌 @senamakel 认领
💸 Fee | 已 claim 0 次 / 已领 0.000 WETH / 未领 5.943 WETH

# $openhuman 情报简报 | 2026-05-19

## 核心叙事
- 类型: 社区代发(bankr 钓鱼模式),绑定 @senamakel 的开源 GitHub 项目 OpenHuman ...

## 叙事演变
- 2026-05-16 14:30 | @tiger_web3 (21.9K,✅) | "买了点 base 上的 openhuman, 龙虾的升级开源版"
- 2026-05-19 13:06 | @OrdzWorld (22.3K,✅) | "升级版小龙虾, 更本地+长期记忆"
- ...

## 风险信号
- 🚨 fee 接收者 @senamakel 未公开认领,累计 5.94 WETH 未领
- ...
```

---

## 快速开始（3 步）

### 1. 一键安装到你的 AI 工具

```bash
python install.py
```

按提示选择目标工具：
- `1` Claude Code → 装到 `~/.claude/skills/ca/`
- `2` OpenClaw → 装到 `~/.openclaw/workspace/skills/ca/`
- `3` Codex CLI → 装到 `~/.agents/skills/ca/`
- `4` 全部装一遍

### 2. 装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# 核心数据源 (Node.js)
npm install -g gmgn-cli@1.0.1
```

### 3. 配 API keys

复制 `.env.example` 到 `~/.config/gmgn/.env` (Linux/Mac) 或 `C:\Users\<你>\.config\gmgn\.env` (Windows)，填入：

**必填**（缺一不可）：
- `GMGN_API_KEY` — 申请：https://gmgn.ai/ai
- `DEEPSEEK_API_KEY` — 申请：https://platform.deepseek.com/ （默认 LLM，最便宜 ~$0.002/次）

**强烈建议**（缺了报告里 X 推文素材就没了，叙事质量大幅下降）：
- `OPENTWITTER_TOKEN` — 申请：https://6551.io/mcp
- `TWITTERAPI_IO_KEY` — 申请：https://twitterapi.io

**可选**（仅当用 `--llm grok` 时）：
- `XAI_API_KEY` — 申请：https://x.ai/api

---

## 使用

### Claude Code / OpenClaw（用 `/` 触发）

```
/ca 0x38298138dd4389013962d8492feaa5879408dba3
/ca 9uQ9rdUE1AJpd3mFa9patGCy3Xi2tSp8qDyRwebqpump
/ca 0xabc... --llm grok --deep
/ca 0xabc... --chain bsc
```

### OpenAI Codex CLI（用 `$` 触发）

```
$ca 0x38298138dd4389013962d8492feaa5879408dba3
```

### 可选 flag

| flag | 含义 | 单次成本 |
|---|---|---|
| (无) | 默认 deepseek-chat | ~$0.002 |
| `--deep` | deepseek-reasoner（推理模式） | ~$0.01 |
| `--llm grok` | grok-4-fast | ~$0.05 |
| `--llm grok --deep` | grok-4 | ~$0.15 |
| `--chain bsc\|base\|eth\|sol` | 手动指定链，跳过自动嗅探 | — |

---

## 附赠工具：`claim_history.py`

查任意 Base bankr 代币的精确 fee claim 时间表（哪一秒提了多少 WETH）。

```bash
python claim_history.py 0x4c433f4ef87fe506a7eed2fd1d822cbed411eba3 --lookback 30000
```

输出 markdown 表格：
```
| # | 时间 (UTC) | block | WETH | TOKEN | TX |
|---|---|---|---|---|---|
| 1 | 2026-05-19 04:18:55 | 46187494 | 0.0669 | 432.23M | 0x953c... |
| ...
```

数据源：Base 主网公共 RPC (`mainnet.base.org`)，免费无 key。

---

## 工作原理（脚本数据流）

1. **gmgn-cli 嗅探链 + 拿基础数据**：subprocess 调用，得到 symbol / MC / 24h / top10 / 风险评分
2. **抓官网正文**：HTML → 纯文本截断 2000 字
3. **6551 OpenTwitter API**（5 个 endpoint 并发）：用户资料 / 最近 20 条推文 / 删除推文 / KOL 关注者 / CA 搜索 Top+Latest
4. **twitterapi.io X Community**（如果挂 community）：community info / moderators / mods 个人推文 / 内部 top tweets
5. **bankr.bot API**（仅 Base）：`/token-launches/{ca}` 拿 deployer / feeRecipient X handle；`/token-launches/{ca}/fees` 拿 claim 次数 + 累计 WETH
6. **DeepSeek / Grok** 提炼：把所有原始素材塞给 LLM 输出中文报告

整个过程**并发执行**，墙钟时间约 15-20 秒，其中 LLM 占 10-15 秒。

---

## 文件清单

```
ca-skill-bundle/
├── README.md              # 本文件
├── install.py             # 一键安装脚本
├── SKILL.template.md      # skill 模板(install 时把 {{SKILL_DIR}} 替换成绝对路径)
├── analyze.py             # 主分析脚本(1100+ 行 Python)
├── claim_history.py       # 独立工具:查 fee claim 时间表
├── requirements.txt       # Python 依赖(requests + python-dotenv)
└── .env.example           # API key 模板
```

---

## 常见问题

**Q: `gmgn-cli` 没装会怎样？**
A: 报告全炸（gmgn 是核心数据源）。先 `npm install -g gmgn-cli@1.0.1`。

**Q: 只有 `DEEPSEEK_API_KEY` 能跑吗？**
A: 能跑但叙事质量很差（X 推文素材全缺）。**强烈建议至少补 `OPENTWITTER_TOKEN`**。

**Q: Codex CLI 的 `$ca` 跟 `/ca` 一样吗？**
A: 一样的功能，只是触发符不同。Codex 用 `$skill-name`，Claude Code/OpenClaw 用 `/skill-name`。

**Q: 我朋友是 Windows 怎么办？**
A: 全部跨平台。`install.py` 自动检测路径分隔符。Windows 上 `~/.claude/` 实际是 `C:\Users\<你>\.claude\`。

**Q: 一份 skill 同时装到 3 个工具会冲突吗？**
A: 不会。3 个工具读不同目录，互不干扰。`install.py` 选 `4` 即可一键三装。

**Q: 想自己改 SKILL.md 加点东西？**
A: 改 `SKILL.template.md`（用 `{{SKILL_DIR}}` 占位符），重跑 `install.py`。

---

## 致谢与许可

数据源：[gmgn.ai](https://gmgn.ai) / [bankr.bot](https://bankr.bot) / [6551 OpenTwitter](https://6551.io) / [twitterapi.io](https://twitterapi.io) / [DeepSeek](https://platform.deepseek.com) / [xAI Grok](https://x.ai)

标准：[Agent Skills (agentskills.io)](https://agentskills.io)，开放标准，Anthropic 主导。

本 skill 不附带任何 API key —— 所有 key 你自己申请，所有数据流不经过我们的服务器。
