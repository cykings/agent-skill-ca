# -*- coding: utf-8 -*-
# 消息处理 + CA 识别 + 调用 analyze.py + 格式化发送

import asyncio
import html
import logging
import re
import subprocess
import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import cache
import config

logger = logging.getLogger("handlers")

# EVM 地址 0x + 40 hex
EVM_RE = re.compile(r"\b(0x[a-fA-F0-9]{40})\b")
# Solana base58, 32-44 字符 (起码 32 字符,避免误抓短串)
SOL_RE = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b")

# rate limit: user_id -> [ts, ts, ...]
_user_calls = {}


def _check_rate(user_id):
    now = time.time()
    if user_id not in _user_calls:
        _user_calls[user_id] = []
    _user_calls[user_id] = [t for t in _user_calls[user_id] if now - t < 60]
    if len(_user_calls[user_id]) >= config.RATE_LIMIT_PER_MIN:
        return False
    _user_calls[user_id].append(now)
    return True


def extract_ca(text):
    # 优先 EVM,再 Solana
    m = EVM_RE.search(text)
    if m:
        return m.group(1)
    m = SOL_RE.search(text)
    if m:
        s = m.group(1)
        # 排除全大写或全小写的纯单词
        if not (s.isalpha() and (s.isupper() or s.islower())):
            return s
    return None


def markdown_to_html(text):
    # 1. HTML 转义
    text = html.escape(text, quote=False)
    # 2. **bold** → <b>bold</b>
    text = re.sub(r"\*\*([^*\n]+?)\*\*", r"<b>\1</b>", text)
    # 3. ### / ## / # heading → <b>...</b>
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # 4. `code` → <code>code</code>
    text = re.sub(r"`([^`\n]+?)`", r"<code>\1</code>", text)
    # 5. _italic_ → <i>italic</i> (谨慎,容易跟普通下划线冲突。这里只匹配两边都有空格/标点的)
    text = re.sub(r"(?<=\s)_([^_\n]+?)_(?=\s|$|[.,;!?\)])", r"<i>\1</i>", text)
    # 6. @username → X 链接(覆盖 telegram 默认的 mention 行为,直接跳 X)
    #    负向后断言: @ 前面不能是字母数字下划线斜杠(避免 email/URL 里的 @)
    text = re.sub(
        r"(?<![A-Za-z0-9_/])@([A-Za-z0-9_]{1,15})\b",
        r'<a href="https://x.com/\1">@\1</a>',
        text,
    )
    return text


def split_text(text, max_len=3800):
    # 留点余量给 HTML tag 和签名
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        cut = text.rfind("\n\n", 0, max_len)
        if cut < 100:
            cut = text.rfind("\n", 0, max_len)
        if cut < 100:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    return chunks


def run_analyze(ca):
    # 同步调 analyze.py;在 to_thread 里跑,不阻塞 event loop
    result = subprocess.run(
        [config.PYTHON_EXE, config.ANALYZE_PY, ca],
        capture_output=True,
        text=True,
        timeout=config.ANALYZE_TIMEOUT,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "")[:500]
        raise RuntimeError(f"analyze.py 失败: {err}")
    return (result.stdout or "").strip()


async def send_report(target_msg, raw_text, from_cache=False, elapsed=None):
    chunks = split_text(raw_text)
    for i, chunk in enumerate(chunks):
        html_text = markdown_to_html(chunk)
        # 最后一段加 footer
        if i == len(chunks) - 1:
            footer_parts = []
            if from_cache:
                footer_parts.append("📦 缓存命中")
            elif elapsed:
                footer_parts.append(f"⏱️ {elapsed:.1f}s")
            if footer_parts:
                html_text += f"\n\n<i>{' · '.join(footer_parts)}</i>"
        try:
            await target_msg.reply_text(
                html_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            # HTML 解析失败 fallback 纯文本
            logger.warning(f"HTML 解析失败,fallback plain: {e}")
            await target_msg.reply_text(chunk, disable_web_page_preview=True)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    chat = update.effective_chat
    user = update.effective_user
    text = msg.text

    # 1. chat 白名单
    if chat.id not in config.ALLOWED_CHAT_IDS:
        logger.info(f"忽略非白名单 chat: {chat.id} (来自 @{user.username or user.id})")
        return

    # 2. 提取 CA
    ca = extract_ca(text)
    if not ca:
        return

    user_name = user.username or user.full_name or str(user.id)
    logger.info(f"[{chat.id}] @{user_name} 查询: {ca}")

    # 3. rate limit
    if not _check_rate(user.id):
        await msg.reply_text(f"⚠️ 慢一点哦,每分钟最多 {config.RATE_LIMIT_PER_MIN} 次")
        return

    # 4. 查缓存
    cached = cache.get_cached(ca, config.CACHE_TTL_SECONDS)
    if cached:
        cache.log_query(user.id, user_name, chat.id, ca, cache_hit=True)
        await send_report(msg, cached, from_cache=True)
        return

    # 5. 发占位
    placeholder = None
    try:
        placeholder = await msg.reply_text(
            f"🔍 查询 <code>{html.escape(ca[:10])}...</code> 中,约 15-20s",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    # 6. 跑 analyze.py
    t0 = time.time()
    try:
        report = await asyncio.to_thread(run_analyze, ca)
        elapsed = time.time() - t0
        cache.set_cached(ca, report)
        cache.log_query(user.id, user_name, chat.id, ca, cache_hit=False)
    except Exception as e:
        logger.error(f"analyze 失败: {e}")
        if placeholder:
            try:
                await placeholder.edit_text(f"❌ 查询失败: {str(e)[:200]}")
            except Exception:
                pass
        return

    # 删占位
    if placeholder:
        try:
            await placeholder.delete()
        except Exception:
            pass

    await send_report(msg, report, from_cache=False, elapsed=elapsed)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in config.ALLOWED_CHAT_IDS:
        return
    await update.message.reply_text(
        "👋 直接把 CA 发到群里就会自动查询\n\n"
        f"• 支持: EVM (0x...) / Solana (base58)\n"
        f"• 缓存: {config.CACHE_TTL_SECONDS}s\n"
        f"• 限速: {config.RATE_LIMIT_PER_MIN}/min/user\n\n"
        "也可以用 /stats 看近 24h 统计"
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in config.ALLOWED_CHAT_IDS:
        return
    s = cache.get_stats(24)
    await update.message.reply_text(
        f"📊 <b>近 24h 统计</b>\n\n"
        f"查询总数: <b>{s['total']}</b>\n"
        f"缓存命中: <b>{s['hit']}</b> ({s['hit_rate']:.0%})\n"
        f"独立 CA: <b>{s['unique']}</b>\n"
        f"独立用户: <b>{s['users']}</b>",
        parse_mode=ParseMode.HTML,
    )
