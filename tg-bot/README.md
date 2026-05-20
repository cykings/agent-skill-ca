# 📲 Telegram bot 推送（可选模块）

**简体中文** · [English](README.en.md)

把 `/ca` 功能搬到 Telegram。**直接在 TG 群里发合约地址，bot 自动返回完整情报报告**。

跟主目录的 `/ca` skill 共用同一个 `analyze.py`，没有任何代码重复。

---

## 效果

```
你在群里发: 0x38298138dd4389013962d8492feaa5879408dba3

bot ~15s 后回复:
$openhuman | MC $1.9M | 24h +363% | (完整中文情报报告...)
```

## 特性

- **白名单**: 只在你指定的群/私聊里响应，其他一律忽略（防滥用）
- **缓存**: 同一 CA 5 分钟内重复查询直接走缓存，省 API 钱
- **限速**: 每用户每分钟最多 5 次查询
- **日志**: SQLite 记录每次查询，`/stats` 查看 24h 统计
- **多消息拆分**: 报告超过 Telegram 4096 字符限制时自动拆分

---

## 4 步设置

### 1️⃣ 装依赖

```bash
pip install -r requirements.txt
```

会装 `python-telegram-bot[ext]>=21.0`。

### 2️⃣ 在 Telegram 上建 bot

去 [@BotFather](https://t.me/BotFather) 发：
- `/newbot`
- 取个名字（显示名，可中可英）
- 取个 username（必须 `_bot` 结尾，全网唯一）
- 拿到 **Bot Token**，长这样：`1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`（你自己的会不同）

**关键设置**：再发 `/setprivacy` → 选你 bot → **Disable**
（不关掉的话 bot 在群里只能看到 @它 的消息，看不到普通文本里的合约地址）

### 3️⃣ 复制配置 + 填 token

```bash
# Mac/Linux
cp config.example.py config.py

# Windows
copy config.example.py config.py
```

编辑 `config.py`：

```python
BOT_TOKEN = "粘贴你的 token"
BOT_USERNAME = "你的_bot_username"     # 不带 @, 仅 log 显示用

ALLOWED_CHAT_IDS = [
    123456789,         # 你自己的 user_id (私聊用)
    -1001234567890,    # 群 chat_id (群里用)
]
```

**拿 user_id / chat_id**：
- 你自己的 user_id：去 [@userinfobot](https://t.me/userinfobot) 发 `/start`，会告诉你
- 群 chat_id：把 bot 加进群 → 启动 bot → 在群里随便发条消息 → bot console 会打印 `[chat_id] @xxx ...`，那个数字就是 chat_id

### 4️⃣ 启动

```bash
python bot.py
```

或者 Windows 双击 `start.bat`。

看到 `✅ Bot 启动 @你的bot` 就成功了。**保持窗口开着，bot 就在监听**。

---

## 使用

群里直接发合约地址（无前缀也行）：
```
0x38298138dd4389013962d8492feaa5879408dba3
9uQ9rdUE1AJpd3mFa9patGCy3Xi2tSp8qDyRwebqpump
```

也可以用 `/ca` 前缀（跟 Claude Code 里一致）：
```
/ca 0x38298138dd4389013962d8492feaa5879408dba3
```

bot 命令：
- `/start` —— 帮助信息
- `/stats` —— 近 24 小时查询统计（总数、缓存命中率、独立 CA、独立用户）

---

## 常见报错

| 现象 | 原因 | 解决 |
|---|---|---|
| `❌ 没找到 config.py` | 还没复制配置 | `cp config.example.py config.py` |
| `❌ BOT_TOKEN 还是空的` | config.py 没填 token | 编辑 config.py 填 token |
| `Conflict: terminated by other getUpdates` | 同一 token 在别处也在跑 | 任务管理器杀掉所有 python.exe 进程，等 30 秒再启动 |
| 群里发消息 bot 没反应 | privacy mode 没关 | @BotFather → /setprivacy → 选你 bot → Disable |
| 私聊 bot 没反应 | 没把自己 user_id 加 ALLOWED_CHAT_IDS | 去 @userinfobot 拿 user_id 填进去 |
| `analyze.py 失败` | 主目录 analyze.py 没装好 | 先按主 README 装 gmgn-cli + Python 依赖 + 配 API keys |

---

## 部署建议

- **本地运行**（最简单）：电脑开机 + start.bat 跑着就行
- **后台运行**（Mac/Linux）：`nohup python bot.py > bot.log 2>&1 &`
- **服务化**（推荐）：用 systemd / pm2 / Windows service 包一层
- **云上 7x24**：VPS 上跑（Hetzner / Vultr / DigitalOcean $5/月即可，CPU/内存够用）

---

## 文件清单

```
tg-bot/
├── README.md            本文件
├── bot.py               入口
├── config.example.py    配置模板（git 跟踪）
├── config.py            实际配置（git 忽略,你自己创建）
├── handlers.py          消息处理 + CA 识别 + 调 analyze.py
├── cache.py             SQLite 缓存 + 查询日志
├── requirements.txt     Python 依赖
├── start.bat            Windows 双击启动
└── ca_cache.db          运行后产生(git 忽略)
```
