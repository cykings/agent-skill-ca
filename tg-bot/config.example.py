# -*- coding: utf-8 -*-
# tg-ca-bot 配置模板
# 用法: 复制本文件为 config.py, 然后填入你自己的 token 和 chat_id
#   cp config.example.py config.py     (Mac/Linux)
#   copy config.example.py config.py   (Windows)

import os
import sys


# ===== 必填 =====

# Telegram Bot Token, 去 https://t.me/BotFather 创建 bot 拿到
# 格式: 数字:字母数字混合, 形如 "1234567:AAAA-bbbb-cccc..."
BOT_TOKEN = ""

# Bot 用户名(不带 @), 仅用于 log 显示, 可留空
BOT_USERNAME = ""

# 白名单 chat_id (只在这些群/私聊里响应,其他一律忽略)
# 群 id 是负数, private chat id = user_id 是正数
# 拿 user_id: 去 https://t.me/userinfobot 发 /start
# 拿群 chat_id: 把 bot 加进群,在群里发消息,bot 启动后 console 会打印实际 chat_id
ALLOWED_CHAT_IDS = [
    # 123456789,        # 你自己的 user_id (用于私聊测试)
    # -1001234567890,   # 你的群 chat_id (supergroup 是 -100xxx... 格式)
]


# ===== 路径(默认值通常不用改) =====

# analyze.py 路径 - 默认指向同 bundle 里上一级的 analyze.py
# 如果你单独把 tg-bot 复制到别处了, 改成 analyze.py 的绝对路径
ANALYZE_PY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "analyze.py"))

# Python 解释器(默认用启动 bot 的那个 Python, 通常无需修改)
PYTHON_EXE = sys.executable

# SQLite 缓存数据库位置(默认在 tg-bot/ 目录下, 不会污染分发包根目录)
DB_PATH = os.path.join(os.path.dirname(__file__), "ca_cache.db")


# ===== 行为参数(可调) =====

# 同一 CA 在多少秒内重复查询直接走缓存(省 API 钱)
CACHE_TTL_SECONDS = 300  # 5 分钟

# 每用户每分钟最多查询次数(防滥用)
RATE_LIMIT_PER_MIN = 5

# 单次 analyze.py 超时(秒)
ANALYZE_TIMEOUT = 120
