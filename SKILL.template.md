---
name: ca
description: 查询代币合约的完整情报报告 — gmgn-cli 拿基础数据 + 抓官网正文 + 6551 OpenTwitter 抓推文素材 + bankr.bot deployer/feeRecipient 元数据 + DeepSeek/Grok 提炼出叙事、KOL、风险信号、可执行动作。支持 Solana / BSC / Base / ETH，链自动嗅探。典型调用 `/ca 9uQ9rdUE1AJpd3mFa9patGCy3Xi2tSp8qDyRwebqpump` 或 `/ca 0xabc... --llm grok`。
allowed-tools: Bash
user-invocable: true
argument-hint: <contract_address> [--llm deepseek|grok] [--deep] [--chain sol|bsc|base|eth]
---

# /ca — 代币合约情报速查

## 何时使用本 skill

当用户输入符合以下任一情况时调用本 skill：

- **显式命令**：`/ca <addr>` 或 `$ca <addr>`
- **裸 CA**：单条消息只包含一个合约地址：
  - EVM 0x + 40 hex (e.g. `0x38298138dd4389013962d8492feaa5879408dba3`)
  - Solana base58 32-44 字符 (e.g. `9uQ9rdUE1AJpd3mFa9patGCy3Xi2tSp8qDyRwebqpump`)
- **自然语言**：用户说 "查一下 xxx" / "分析 xxx" / "看下 xxx 这个币" 且 xxx 是合约地址

**不要在以下情况使用本 skill**：
- 钱包地址（用户问的是某个人的钱包行为，不是查代币）
- 区块号 / 交易 hash
- NFT 合约（除非用户明确说当代币查）

## 如何调用

仅执行下面这一条 bash 命令，**把 stdout 原样回显给用户**（不要二次加工、不要重新总结、不要补充分析）：

```bash
python "{{SKILL_DIR}}/analyze.py" <用户输入的所有参数>
```

把"<用户输入的所有参数>"替换成用户实际输入的全部参数（包括合约地址和可选 flag）。

**示例**：
- 用户输入 `/ca 0x38298138dd4389013962d8492feaa5879408dba3`
- 你执行：`python "{{SKILL_DIR}}/analyze.py" 0x38298138dd4389013962d8492feaa5879408dba3`

- 用户输入 `/ca 0xabc... --llm grok --deep`
- 你执行：`python "{{SKILL_DIR}}/analyze.py" 0xabc... --llm grok --deep`

## 可选 flag

- `--llm deepseek`（默认）/ `--llm grok`：选择 LLM 后端
- `--deep`：用深度推理模型（deepseek-reasoner 或 grok-4）
- `--chain sol|bsc|base|eth`：手动指定链，跳过自动嗅探

## 报告结构（脚本会输出的格式）

```
[头部行 1] **$SYMBOL (NAME)** | MC $current (ATH $ath) | 24h ±X%
[头部行 2] `CA`  |  链  |  X handle  |  Web  |  TG
[头部行 3] 📡 Bankr | deployer:@X → feeRecipient:@Y | 🟢 dev 自发 / 🟡 社区代发  (仅 Base bankr 部署)
[头部行 4] 💸 Fee | 已 claim N 次 / 已领 X WETH / 未领 Y WETH  (仅 Base bankr 部署)

# $SYMBOL 情报简报 | YYYY-MM-DD

## 核心叙事
## 官方账号在说什么
## 叙事演变
## 关键 KOL
## 风险信号
```

## 数据流（脚本内部逻辑，仅供参考，不需要你执行）

1. **链嗅探**：0x → bsc → base → eth 顺序探测；base58 → sol
2. **gmgn-cli token info**：symbol / MC / 价格 / 24h 涨跌 / 流动性 / Top10 集中度 / Bundler / 老鼠仓 / Twitter handle / 官网 URL
3. **fetch 官网正文**：HTML → 纯文本，截断 2000 字
4. **6551 OpenTwitter API 并发 5+2 个 endpoint**：用户资料 / 最近推文 / 删除推文 / KOL 关注者 / CA 搜索 Top + Latest
5. **twitterapi.io X Community**（仅当 gmgn 挂的是 `/i/communities/<id>` 时）：community info / moderators / mods 个人推文 / community 内部 top tweets
6. **bankr.bot 元数据**（仅 base 链）：`/token-launches/{ca}` 拿 deployer + feeRecipient X handle；`/token-launches/{ca}/fees` 拿 claim 状态
7. **DeepSeek / Grok 提炼**：把所有原始素材塞给 LLM 提炼出中文报告

## 故障处理

- **"未配置 DEEPSEEK_API_KEY"**：让用户去 https://platform.deepseek.com/ 申请，加到 `~/.config/gmgn/.env`
- **"未配置 OPENTWITTER_TOKEN"**：报告会跳过 X 推文素材（叙事质量下降），建议补 token
- **"未配置 TWITTERAPI_IO_KEY"**：报告会跳过 X Community 数据，建议补 key
- **0x 地址 BSC / Base / ETH 都查不到**：地址可能错或太新，让用户去 dexscreener 核对后用 `--chain` 手动指定
- **LLM 调研失败但 gmgn 成功**：脚本会输出基础数据 + "⚠️ LLM 调研失败" 提示

## 成本参考

| 模式 | LLM | 单次成本 |
|---|---|---|
| 默认 | deepseek-chat | ~$0.002 |
| `--deep` | deepseek-reasoner | ~$0.01 |
| `--llm grok` | grok-4-fast | ~$0.05 |
| `--llm grok --deep` | grok-4 | ~$0.15 |

## 重要约束

- 本 skill 是"工具调用"型，**脚本 stdout 已经是最终报告**，**直接原样回显**给用户即可
- **不要做额外分析**，不要重新总结，不要追加"我的看法"
- 如果用户**追问**某个细节（如"这个 KOL 现在还在喊单吗"），才需要你基于报告补充调研
- DeepSeek/Grok 输出已经是纯中文 + 自动分类（反向 KOL / 拉盘 KOL），无需后处理
