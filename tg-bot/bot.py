# -*- coding: utf-8 -*-
# tg-ca-bot 入口
# 双击 start.bat 启动,Ctrl+C 退出

import logging
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# 检测 config.py 是否存在 + 关键字段是否填了
if not (_HERE / "config.py").exists():
    print("=" * 60)
    print("❌ 没找到 config.py")
    print("=" * 60)
    print()
    print("请按以下步骤设置:")
    print("  1. 复制 config.example.py 为 config.py:")
    print("     Mac/Linux: cp config.example.py config.py")
    print("     Windows:   copy config.example.py config.py")
    print("  2. 编辑 config.py 填入你的 BOT_TOKEN 和 ALLOWED_CHAT_IDS")
    print("  3. 详细教程见 README.md")
    print()
    sys.exit(1)

import config

if not getattr(config, "BOT_TOKEN", "").strip():
    print("❌ config.py 里 BOT_TOKEN 还是空的")
    print("   请去 https://t.me/BotFather 创建 bot 拿到 token,填到 config.py")
    sys.exit(1)

if not config.ALLOWED_CHAT_IDS:
    print("⚠️  config.py 里 ALLOWED_CHAT_IDS 为空")
    print("   bot 不会响应任何消息(白名单空 = 拒绝所有)")
    print("   去 https://t.me/userinfobot 拿你的 user_id 或群 chat_id 填进去")
    sys.exit(1)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import cache
import handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger("bot")


def main():
    cache.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("stats", handlers.cmd_stats))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
    )

    logger.info(f"✅ Bot 启动 @{config.BOT_USERNAME or '<unnamed>'}")
    logger.info(f"   白名单 chat_ids: {config.ALLOWED_CHAT_IDS}")
    logger.info(f"   缓存 TTL: {config.CACHE_TTL_SECONDS}s | rate limit: {config.RATE_LIMIT_PER_MIN}/min")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
