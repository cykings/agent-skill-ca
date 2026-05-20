#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /ca skill 主脚本：gmgn 基础数据 + 官网正文 + 6551 推文素材 + Grok 提炼

import argparse
import datetime as _dt
import html as _html
import json
import logging
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import load_dotenv

# 北京时间时区(UTC+8)
CST = _dt.timezone(_dt.timedelta(hours=8))


def _to_cst_str(date_str):
    # 把 Twitter 的 createdAt 转成 "YYYY-MM-DD HH:MM CST" 格式
    # 兼容: "Sat May 18 06:33:56 +0000 2026" 和 ISO "2026-05-19T04:18:55Z"
    if not date_str:
        return ""
    s = date_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+0000"
    for fmt in (
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            dt = _dt.datetime.strptime(s, fmt)
            return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M CST")
        except ValueError:
            continue
    return date_str[:25]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("ca")

GMGN_ENV_PATH = Path.home() / ".config" / "gmgn" / ".env"
GROK_API_URL = "https://api.x.ai/v1/responses"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
OPENTWITTER_BASE = "https://ai.6551.io"
TWITTERAPI_IO_BASE = "https://api.twitterapi.io"

# 模型选择
GROK_DEFAULT = "grok-4-fast"
GROK_DEEP = "grok-4"
DEEPSEEK_DEFAULT = "deepseek-chat"
DEEPSEEK_DEEP = "deepseek-reasoner"

EVM_SNIFF_ORDER = ["bsc", "base", "eth"]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"


# ---------- 6551 OpenTwitter ----------
class OpenTwitter:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict, timeout: int = 30):
        try:
            r = requests.post(f"{OPENTWITTER_BASE}{path}", headers=self.headers,
                              json=body, timeout=timeout)
            if r.status_code != 200:
                logger.warning(f"6551 {path} HTTP {r.status_code}: {r.text[:200]}")
                return None
            payload = r.json()
            return payload.get("data")
        except Exception as e:
            logger.warning(f"6551 {path} 异常: {e}")
            return None

    def user_info(self, username):
        return self._post("/open/twitter_user_info", {"username": username})

    def user_tweets(self, username, max_results=20):
        return self._post("/open/twitter_user_tweets", {
            "username": username, "maxResults": max_results,
            "product": "Latest", "includeReplies": False, "includeRetweets": False,
        })

    def deleted_tweets(self, username, max_results=20):
        return self._post("/open/twitter_deleted_tweets",
                          {"username": username, "maxResults": max_results})

    def kol_followers(self, username):
        return self._post("/open/twitter_kol_followers", {"username": username})

    def search(self, keywords, product="Top", max_results=20):
        return self._post("/open/twitter_search", {
            "keywords": keywords, "maxResults": max_results, "product": product,
        })


# ---------- twitterapi.io（专攻 X Community 内部数据） ----------
class TwitterAPI:
    def __init__(self, api_key: str):
        self.headers = {"x-api-key": api_key}

    def _get(self, path: str, params: dict, timeout: int = 20):
        try:
            r = requests.get(f"{TWITTERAPI_IO_BASE}{path}", headers=self.headers,
                             params=params, timeout=timeout)
            if r.status_code != 200:
                logger.warning(f"twitterapi.io {path} HTTP {r.status_code}: {r.text[:200]}")
                return None
            return r.json()
        except Exception as e:
            logger.warning(f"twitterapi.io {path} 异常: {e}")
            return None

    def community_info(self, community_id: str):
        d = self._get("/twitter/community/info", {"community_id": community_id})
        return (d or {}).get("community_info") or {}

    def community_moderators(self, community_id: str):
        d = self._get("/twitter/community/moderators", {"community_id": community_id})
        return (d or {}).get("moderators") or []

    def community_tweets(self, community_id: str, max_pages: int = 2):
        """拉 N 页 community 推文（每页 20 条），扁平拼起来。"""
        all_tweets = []
        cursor = None
        for _ in range(max_pages):
            params = {"community_id": community_id}
            if cursor:
                params["cursor"] = cursor
            d = self._get("/twitter/community/tweets", params)
            if not d:
                break
            tweets = d.get("tweets") or []
            all_tweets.extend(tweets)
            if not d.get("has_next_page"):
                break
            cursor = d.get("next_cursor")
            if not cursor:
                break
        return all_tweets

    def user_last_tweets(self, username: str, limit: int = 20):
        """反查某用户的最近推文（用于 mods 的项目方声音）"""
        d = self._get("/twitter/user/last_tweets", {"userName": username})
        if not d:
            return []
        # 推文在 data.tweets 或 data 数组下，二者兼容
        data = d.get("data")
        if isinstance(data, dict):
            tweets = data.get("tweets") or []
        elif isinstance(data, list):
            tweets = data
        else:
            tweets = d.get("tweets") or []
        return tweets[:limit]


# ---------- 主类 ----------
class CaAnalyzer:
    def __init__(self, address: str, deep: bool = False, forced_chain: str = None):
        self.address = address.strip()
        self.deep = deep
        self.forced_chain = forced_chain
        self.chain = None
        self.token = None
        self.website_text = ""
        self.tw_data = {}
        self.stat_eval = None
        self.bankr_launch = None  # bankr.bot /token-launches/{ca} 返回的 launch 对象
        self.bankr_fees = None    # bankr.bot /token-launches/{ca}/fees 返回 claim 状态

    # ---------- 链嗅探 ----------
    def detect_chain(self):
        if self.forced_chain:
            self.chain = self.forced_chain
            self.token = self._call_gmgn_info(self.forced_chain)
            if not self.token:
                raise RuntimeError(f"指定的链 {self.forced_chain} 查询失败")
            return

        addr = self.address
        if re.fullmatch(r"0x[a-fA-F0-9]{40}", addr):
            for chain in EVM_SNIFF_ORDER:
                logger.info(f"🔍 嗅探 {chain}...")
                data = self._call_gmgn_info(chain)
                if data and data.get("symbol"):
                    self.chain = chain
                    self.token = data
                    logger.info(f"✅ 命中 {chain}")
                    return
            raise RuntimeError("❌ 0x 地址在 BSC / Base / ETH 上均未找到。请检查地址或手动 --chain 指定。")
        if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", addr):
            data = self._call_gmgn_info("sol")
            if not data or not data.get("symbol"):
                raise RuntimeError(f"❌ Solana 地址在 gmgn 查询失败: {addr}")
            self.chain = "sol"
            self.token = data
            return

        raise ValueError(f"❌ 无效的合约地址: {addr}")

    def _call_gmgn_info(self, chain: str):
        try:
            result = subprocess.run(
                ["gmgn-cli", "token", "info", "--chain", chain,
                 "--address", self.address, "--raw"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
                shell=(os.name == "nt"),
            )
            if result.returncode != 0:
                logger.debug(f"gmgn {chain} 失败: {result.stderr[:200]}")
                return None
            data = json.loads(result.stdout.strip())
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                data = data["data"]
            return data
        except subprocess.TimeoutExpired:
            logger.error(f"gmgn {chain} 超时")
            return None
        except Exception as e:
            logger.error(f"gmgn {chain} 异常: {e}")
            return None

    # ---------- price dict 解析（gmgn token info 里 price 是嵌套对象） ----------
    def _price_dict(self) -> dict:
        p = (self.token or {}).get("price")
        return p if isinstance(p, dict) else {}

    def current_price(self) -> float:
        p = self.token.get("price")
        if isinstance(p, dict):
            return self._to_float(p.get("price"))
        return self._to_float(p)

    def change_pct(self, window: str) -> float:
        """根据 price dict 里的 price_1h / price_24h 等算涨跌（%）。window: '1m'|'5m'|'1h'|'6h'|'24h'"""
        pd = self._price_dict()
        cur = self._to_float(pd.get("price"))
        old = self._to_float(pd.get(f"price_{window}"))
        if cur <= 0 or old <= 0:
            return None
        return (cur - old) / old * 100

    # ---------- 官网正文 ----------
    def fetch_website(self):
        url = (self.token.get("link") or {}).get("website") or ""
        if not url:
            return
        try:
            logger.info(f"🌐 拉取官网 {url}")
            r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
            text = self._html_to_text(r.text)
            self.website_text = text[:2000]
            logger.info(f"✅ 官网 {len(self.website_text)} 字")
        except Exception as e:
            logger.warning(f"官网拉取失败: {e}")

    # ---------- bankr.bot 部署元数据 ----------
    def fetch_bankr_launch(self):
        # 只对 base 链有效;其他链直接跳过避免无谓 404
        if self.chain != "base":
            return
        try:
            url = f"https://api.bankr.bot/token-launches/{self.address.lower()}"
            r = requests.get(url, timeout=10)
            if r.status_code == 404:
                logger.info("📡 bankr: 非 bankr 部署 (404)")
                return
            if r.status_code != 200:
                logger.warning(f"📡 bankr HTTP {r.status_code}: {r.text[:200]}")
                return
            launch = r.json().get("launch") or {}
            if not launch:
                return
            self.bankr_launch = launch
            dep_x = (launch.get("deployer") or {}).get("xUsername")
            fee_x = (launch.get("feeRecipient") or {}).get("xUsername")
            dep_w = ((launch.get("deployer") or {}).get("walletAddress") or "").lower()
            fee_w = ((launch.get("feeRecipient") or {}).get("walletAddress") or "").lower()
            mode = "dev自发" if (dep_w and fee_w and dep_w == fee_w) else "社区代发"
            logger.info(f"📡 bankr: deployer=@{dep_x or '(无X)'} → feeRecipient=@{fee_x or '(无X)'} | {mode}")
        except Exception as e:
            logger.warning(f"📡 bankr 异常: {e}")

    def fetch_bankr_fees(self):
        # 拉 fee claim 状态(累计已领/未领次数+WETH 数量);只对 base 有效
        if self.chain != "base":
            return
        try:
            url = f"https://api.bankr.bot/token-launches/{self.address.lower()}/fees"
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return
            self.bankr_fees = r.json()
            tokens = self.bankr_fees.get("tokens") or []
            if tokens:
                t = tokens[0]
                claimed = t.get("claimed") or {}
                claimable = t.get("claimable") or {}
                # 判断 token0/token1 哪个是 WETH
                if t.get("token0Label") == "WETH":
                    claimed_weth = self._to_float(claimed.get("token0"))
                    claimable_weth = self._to_float(claimable.get("token0"))
                else:
                    claimed_weth = self._to_float(claimed.get("token1"))
                    claimable_weth = self._to_float(claimable.get("token1"))
                cnt = claimed.get("count") or 0
                logger.info(f"💸 bankr fees: claim {cnt} 次 / 已领 {claimed_weth:.3f} WETH / 未领 {claimable_weth:.3f} WETH")
        except Exception as e:
            logger.warning(f"💸 bankr fees 异常: {e}")

    def _extract_fee_stats(self):
        # 从 bankr_fees 提取统一格式 dict(count/claimed_weth/claimable_weth);
        # 若 fees 没拉到或 token 不存在返回 None
        if not self.bankr_fees:
            return None
        tokens = self.bankr_fees.get("tokens") or []
        if not tokens:
            return None
        t = tokens[0]
        claimed = t.get("claimed") or {}
        claimable = t.get("claimable") or {}
        if t.get("token0Label") == "WETH":
            claimed_weth = self._to_float(claimed.get("token0"))
            claimable_weth = self._to_float(claimable.get("token0"))
        else:
            claimed_weth = self._to_float(claimed.get("token1"))
            claimable_weth = self._to_float(claimable.get("token1"))
        return {
            "count": claimed.get("count") or 0,
            "claimed_weth": claimed_weth,
            "claimable_weth": claimable_weth,
        }

    @staticmethod
    def _html_to_text(html: str) -> str:
        html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
        html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", html)
        text = _html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    # ---------- 6551 5+1 endpoint 并发 ----------
    def _parse_official_twitter(self):
        """从 gmgn 拿到的 twitter_username 解析出 handle / community URL / community_id，
        结果写进 self.tw_data。这是后续 fetch_opentwitter / fetch_community 共用的前置。
        """
        raw_handle = (self.token.get("link") or {}).get("twitter_username") or ""
        handle, x_url = self._parse_twitter_link(raw_handle)
        self.tw_data["_handle"] = handle
        self.tw_data["_x_url"] = x_url
        community_id = None
        if x_url and "/communities/" in x_url:
            try:
                community_id = x_url.rsplit("/", 1)[-1]
                self.tw_data["_community_id"] = community_id
            except Exception:
                pass
        return handle, x_url, community_id

    def fetch_opentwitter(self, ot_token: str):
        if not ot_token:
            logger.warning("⚠️ 未配置 OPENTWITTER_TOKEN，跳过 6551 推文素材")
            return
        ot = OpenTwitter(ot_token)
        handle = self.tw_data.get("_handle", "")

        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {
                "search_top": ex.submit(ot.search, self.address, "Top", 20),
                "search_latest": ex.submit(ot.search, self.address, "Latest", 20),
            }
            if handle:
                logger.info(f"🐦 6551 抓 @{handle} 5个endpoint + CA搜索2个")
                futures.update({
                    "user_info": ex.submit(ot.user_info, handle),
                    "user_tweets": ex.submit(ot.user_tweets, handle, 20),
                    "deleted": ex.submit(ot.deleted_tweets, handle, 20),
                    "kol_followers": ex.submit(ot.kol_followers, handle),
                })
            else:
                logger.info("🐦 无官方 handle，只搜 CA")

            for key, fut in futures.items():
                try:
                    self.tw_data[key] = fut.result(timeout=30)
                except Exception as e:
                    logger.warning(f"6551 {key} 失败: {e}")
                    self.tw_data[key] = None

    def fetch_community(self, twitterapi_key: str):
        """检测到 X Community URL 时，调 twitterapi.io 抓：
        1. community 元信息
        2. moderators 列表（项目方核心团队）
        3. 反查每个 mod 的个人最近推文（真正的"项目方在说什么"）
        4. community 内部最近 40 条推文（2 页），脚本侧按 engagement 排序取 top 15
        """
        if not twitterapi_key:
            return
        cid = self.tw_data.get("_community_id")
        if not cid:
            return  # 不是 community 项目，跳过

        api = TwitterAPI(twitterapi_key)
        logger.info(f"🟦 twitterapi.io 抓 community {cid}...")

        # 第一波：info + moderators + community tweets 并行
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_info = ex.submit(api.community_info, cid)
            f_mods = ex.submit(api.community_moderators, cid)
            f_tw = ex.submit(api.community_tweets, cid, 2)  # 2 页 = 40 条
            info = f_info.result(timeout=30) or {}
            mods = f_mods.result(timeout=30) or []
            community_tweets = f_tw.result(timeout=60) or []

        self.tw_data["community_info"] = info
        self.tw_data["community_mods"] = mods
        # community 内部推文按 engagement 排序取 top 15
        self.tw_data["community_top_tweets"] = self._rank_tweets(community_tweets, limit=15)

        # 第二波：反查 mods（+ creator）的个人推文，并发
        mod_handles = []
        creator = info.get("creator") or {}
        creator_handle = creator.get("screen_name")
        if creator_handle:
            mod_handles.append(creator_handle)
        for m in mods:
            sn = m.get("screen_name")
            if sn and sn not in mod_handles:
                mod_handles.append(sn)
        mod_handles = mod_handles[:5]  # 顶多 5 个核心人

        if mod_handles:
            logger.info(f"🟦 反查 mods 个人推文: {', '.join('@' + h for h in mod_handles)}")
            mod_tweets = {}
            with ThreadPoolExecutor(max_workers=min(5, len(mod_handles))) as ex:
                future_map = {h: ex.submit(api.user_last_tweets, h, 20) for h in mod_handles}
                for h, fut in future_map.items():
                    try:
                        mod_tweets[h] = fut.result(timeout=30) or []
                    except Exception as e:
                        logger.warning(f"twitterapi.io @{h} 失败: {e}")
                        mod_tweets[h] = []
            self.tw_data["mod_tweets"] = mod_tweets
        else:
            self.tw_data["mod_tweets"] = {}

    @staticmethod
    def _rank_tweets(tweets, limit=15):
        """按 likes×3 + retweet×5 + views÷100 排序，取 top N"""
        def score(t):
            likes = t.get("likeCount") or 0
            rt = t.get("retweetCount") or 0
            views = t.get("viewCount") or 0
            return likes * 3 + rt * 5 + views / 100
        ranked = sorted(tweets or [], key=score, reverse=True)
        return ranked[:limit]

    @staticmethod
    def _parse_twitter_link(raw: str):
        """返回 (handle, full_url)。
        - handle: 干净的 @username，仅当 raw 是纯 handle 时才有值
        - full_url: 完整 X URL，包括 community/status/search 等链接情形
        gmgn 的 twitter_username 字段格式很乱，常见：
          - "username"                       → handle
          - "username/status/123"            → 推文链接，不是 handle
          - "i/communities/123"              → X Community 链接，不是 handle
          - "search?q=xxx&src=typed_query"   → 搜索 URL，无效
          - "https://x.com/username"         → URL，需剥离前缀
        """
        if not raw:
            return "", ""
        raw = raw.strip().lstrip("@")
        for prefix in ("https://x.com/", "http://x.com/",
                       "https://twitter.com/", "http://twitter.com/"):
            if raw.startswith(prefix):
                raw = raw[len(prefix):]
                break
        # 包含路径分隔（status / communities / search / i/...）→ 不是 handle
        if "/" in raw or "?" in raw:
            return "", f"https://x.com/{raw}"
        # 纯 handle: 字母数字下划线, 1-15 字符
        if re.fullmatch(r"[A-Za-z0-9_]{1,15}", raw):
            return raw, f"https://x.com/{raw}"
        return "", ""

    @staticmethod
    def _extract_handle(raw: str) -> str:
        """向后兼容：只返回 handle 部分"""
        h, _ = CaAnalyzer._parse_twitter_link(raw)
        return h

    # ---------- gmgn stat 风险/信号评估 ----------
    def evaluate_stat(self):
        stat = self.token.get("stat") or {}

        def f(k):
            v = stat.get(k)
            try:
                return float(v) if v is not None else None
            except Exception:
                return None

        warnings = []  # 🚨 / ⚠️
        positives = []  # 💎 / 📊
        info = []  # 中性信息

        # A. 集中度
        top10 = f("top_10_holder_rate")
        if top10 is not None:
            lbl = f"Top10集中度 {top10*100:.1f}%"
            (warnings.append(f"⚠️ {lbl} (>30%)") if top10 > 0.30 else info.append(lbl))

        creator = f("creator_hold_rate")
        if creator is not None and creator > 0:
            lbl = f"部署者持仓 {creator*100:.1f}%"
            (warnings.append(f"⚠️ {lbl} (>5%)") if creator > 0.05 else info.append(lbl))

        dev_team = f("dev_team_hold_rate")
        if dev_team is not None and dev_team > 0:
            lbl = f"Dev团队持仓 {dev_team*100:.1f}%"
            (warnings.append(f"⚠️ {lbl} (>5%)") if dev_team > 0.05 else info.append(lbl))

        private_vault = f("private_vault_hold_rate")
        if private_vault is not None and private_vault > 0:
            lbl = f"私库持仓 {private_vault*100:.1f}%"
            (warnings.append(f"⚠️ {lbl} (>3%)") if private_vault > 0.03 else info.append(lbl))

        sniper = f("top70_sniper_hold_rate")
        if sniper is not None and sniper > 0:
            lbl = f"Top70 Sniper持仓 {sniper*100:.1f}%"
            (warnings.append(f"⚠️ {lbl} (>20%)") if sniper > 0.20 else info.append(lbl))

        # B. 异常行为
        bundler = f("top_bundler_trader_percentage")
        if bundler is not None and bundler > 0:
            lbl = f"Bundler交易者 {bundler*100:.1f}%"
            (warnings.append(f"🚨 {lbl} (>10% 团播嫌疑)") if bundler > 0.10 else info.append(lbl))

        rat = f("top_rat_trader_percentage")
        if rat is not None and rat > 0:
            warnings.append(f"🚨 老鼠仓交易者 {rat*100:.1f}%")

        entrap = f("top_entrapment_trader_percentage")
        if entrap is not None and entrap > 0:
            warnings.append(f"🚨 诱多/拉砸者 {entrap*100:.1f}%")

        fresh = f("fresh_wallet_rate")
        if fresh is not None:
            lbl = f"新钱包占比 {fresh*100:.1f}%"
            (warnings.append(f"⚠️ {lbl} (>30% 疑 raid)") if fresh > 0.30 else info.append(lbl))

        bot = f("top_bot_degen_percentage")
        if bot is not None and bot > 0:
            info.append(f"Bot 占比 {bot*100:.1f}%")

        bot_degen_rate = f("bot_degen_rate")
        if bot_degen_rate is not None and bot_degen_rate > 0:
            info.append(f"Bot Degen率 {bot_degen_rate*100:.1f}%")

        # C. 社交热度
        for key, label in [("signal_count", "信号数"),
                           ("degen_call_count", "Degen喊单"),
                           ("square_mentions", "广场提及")]:
            v = stat.get(key)
            if v:
                positives.append(f"📊 {label} {v}")

        # D. 蓝筹
        bluechip = stat.get("bluechip_owner_count")
        if bluechip:
            pct = f("bluechip_owner_percentage")
            lbl = f"蓝筹钱包持有 {bluechip} 个"
            if pct is not None:
                lbl += f" ({pct*100:.1f}%)"
            positives.append(f"💎 {lbl}")

        # E. 项目方背景
        created = stat.get("creator_created_count")
        if created is not None:
            if created > 10:
                warnings.append(f"⚠️ Dev 已发币 {created} 个 (连环发币嫌疑)")
            elif created > 0:
                info.append(f"Dev 发币数 {created}")

        self.stat_eval = {"warnings": warnings, "positives": positives, "info": info}

    # ---------- LLM 提炼（支持 grok / deepseek） ----------
    def fetch_llm(self, backend: str, key: str):
        system_msg, user_prompt = self._build_prompt()
        if backend == "deepseek":
            text = self._call_deepseek(key, system_msg, user_prompt)
        else:
            text = self._call_grok(key, system_msg, user_prompt)
        return self._strip_self_notes(text) if text else text

    @staticmethod
    def _strip_self_notes(text: str) -> str:
        """LLM 经常在违规内容后加'（按规则不列）/ 粉丝<1000 / 纯回顾'之类的自我解释，
        或者把价格喊单包装成叙事性 KOL 推文。这里强制后处理：
        1. 含元注释关键词的整行删除
        2. KOL 行（📈 开头）含价格喊单关键词的整行删除
        """
        meta_kws = [
            "粉丝<", "粉丝 <", "按规则", "不列）", "不列)", "不列。",
            "thesis 原文未", "thesis原文未", "原文未在素材",
            "thesis 内容未", "thesis内容未",
            "勉强可列", "勉强列",
            "纯回顾", "纯价格喊单", "纯数据陈述", "回顾性吹牛",
            "仅作时间锚", "仅供参考", "仅做时间锚",
            "无 thesis 内容", "无thesis内容",
            "但属数据陈述", "属数据陈述非叙事",
            "（注：", "(注：", "（注:", "(注:",
            "按规则跳过", "按规则不",
            "违反规则但", "违反但",
        ]
        # 价格喊单 / 价格走势预测 / 倍数吹牛关键词（仅对 📈 开头的 KOL 行触发）
        price_kws = [
            "盘整后", "继续走高", "继续上涨", "将冲", "短期冲", "短期内冲",
            "涨超", "涨幅超", "涨了", "已涨",
            "%up", "% up", "%涨", "% 涨",
            "x profit", "X profit", "X 倍 profit",
            "x runner", "X runner", "倍 runner", "x runner",
            "consolidating before", "before going higher",
            "moonshot", "to the moon", "mooning",
            "sending it", "sending higher",
            "next leg", "next 10x", "next 100x",
            "目标 5m", "目标 10m", "目标 100m", "目标 5M", "目标 10M", "目标 100M",
            "下一站", "下一个 10x", "下一个10x",
            "scored hard", "scored big",
            "FOMO", "fomo来了", "fomo 来了",
            "chart sexy", "chart最强", "chart 最强", "图表最强",
            "volume 起飞", "volume起飞", "insane volume",
            "bullish af", "super bullish",
            "no brainer", "no-brainer",
            "early call", "called it early",
            "I told you", "I gave thesis",
            "16x", "32x", "100x", "50x", "20x", "10x ",
            "Nx profit", "倍利润",
        ]
        kept = []
        for line in text.split("\n"):
            # 1. 元注释关键词 → 整行删
            if any(kw in line for kw in meta_kws):
                continue
            # 2. 任何"社交推文行"（含 @handle + 粉丝数标识，可能在叙事演变或 KOL 板块）
            #    含价格喊单关键词 → 整行删
            #    判定条件：行里含 "@" 和 "粉"（X 粉的标记）
            is_social_line = ("@" in line) and ("粉)" in line or "粉，" in line or "粉 " in line or "粉)" in line)
            if is_social_line:
                low = line.lower()
                if any(kw.lower() in low for kw in price_kws):
                    continue
            kept.append(line)
        # 去除连续空行
        out = []
        prev_blank = False
        for line in kept:
            blank = not line.strip()
            if blank and prev_blank:
                continue
            out.append(line)
            prev_blank = blank
        return "\n".join(out).rstrip()

    def _build_prompt(self):
        link = self.token.get("link") or {}
        symbol = self.token.get("symbol") or "?"
        name = self.token.get("name") or "?"
        handle = self.tw_data.get("_handle", "")

        creation_ts = self.token.get("creation_timestamp") or 0
        open_ts = self.token.get("open_timestamp") or 0
        migrated_ts = self.token.get("migrated_timestamp") or 0

        def ts2d(ts):
            # 用 CST 显示日期(UTC 时间戳 -> +8 时区)
            return _dt.datetime.fromtimestamp(ts, tz=CST).strftime("%Y-%m-%d") if ts else "?"

        # 压缩素材
        tw = self.tw_data
        user_info_compact = self._compact_user(tw.get("user_info"))
        user_tweets_compact = self._compact_tweets(tw.get("user_tweets"), limit=20)
        deleted_compact = self._compact_tweets(tw.get("deleted"), limit=20)
        kol_compact = self._compact_kol(tw.get("kol_followers"))
        search_top_compact = self._compact_tweets(tw.get("search_top"), limit=20)
        search_latest_compact = self._compact_tweets(tw.get("search_latest"), limit=20)

        website_block = self.website_text or "（未抓取到官网内容或项目无官网）"
        stat_block = json.dumps(self.stat_eval or {}, ensure_ascii=False, indent=2)

        # 用北京时间作为"今天",素材里所有推文时间也已转成 CST
        cst_now = _dt.datetime.now(CST)
        today = cst_now.strftime("%Y-%m-%d")
        cur_year = cst_now.year
        x_url = self.tw_data.get("_x_url", "")
        twitter_display = f"@{handle}" if handle else (x_url if x_url else "（无）")
        if x_url and not handle:
            if "/communities/" in x_url:
                twitter_display = f"{x_url} （X Community，项目方挂的是社区而非个人账号；社区核心成员/Moderators 的个人推文见素材 10）"
            elif "/status/" in x_url:
                twitter_display = f"{x_url} （某条推文链接，不是项目方账号）"
            elif "search?" in x_url or "/search" in x_url:
                twitter_display = f"{x_url} （X 搜索链接，无效）"

        # 是否有 community 数据
        community_info = self.tw_data.get("community_info") or {}
        community_mods = self.tw_data.get("community_mods") or []
        mod_tweets = self.tw_data.get("mod_tweets") or {}
        community_top = self.tw_data.get("community_top_tweets") or []
        has_community = bool(community_info)

        user_prompt = f"""# 任务
我已经把这个代币所有原始素材都拉好了。**你不需要再检索**（不要调用 x_search），只需要从下面素材里**提炼**报告。

# ⚠️ 时间锚（必读，违反此条视为错误）
- **今天日期**：{today}（CST / UTC+8 北京时间）
- 当前年份是 **{cur_year}**。素材里所有推文 `date` 字段已转成 **CST (UTC+8)** 格式（带"CST"标记）。
- 输出叙事演变板块时,**直接复用素材里的 CST 时间**,不要二次换算成 UTC。
- **不允许把年份写成 {cur_year - 1} 或更早**。

# 代币元数据
- CA: {self.address}
- 链: {self.chain.upper()}
- Symbol: ${symbol}  名称: {name}
- 官方 Twitter: {twitter_display}
- 官网: {link.get('website') or '（无）'}
- Telegram: {link.get('telegram') or '（无）'}
- 合约创建日: {ts2d(creation_ts)}    开盘日: {ts2d(open_ts)}    毕业/迁移日: {ts2d(migrated_ts)}
- 项目自述(gmgn): {link.get('description') or '（无）'}

# 素材 1: 官网正文（已截断 2000 字）
```
{website_block}
```

# 素材 2: 官方 X 账号资料
```json
{json.dumps(user_info_compact, ensure_ascii=False, indent=2)}
```

# 素材 3: 官方账号最近 20 条推文（Latest 排序）
```json
{json.dumps(user_tweets_compact, ensure_ascii=False, indent=2)}
```

# 素材 4: 官方账号删除过的推文
```json
{json.dumps(deleted_compact, ensure_ascii=False, indent=2)}
```

# 素材 5: 关注官方账号的 KOL 列表
```json
{json.dumps(kol_compact, ensure_ascii=False, indent=2)}
```

# 素材 6: X 搜索 CA 的 Top 推文（20 条，热门排序）
```json
{json.dumps(search_top_compact, ensure_ascii=False, indent=2)}
```

# 素材 7: X 搜索 CA 的 Latest 推文（20 条，时间倒序）
```json
{json.dumps(search_latest_compact, ensure_ascii=False, indent=2)}
```

# 素材 8: gmgn 链上数据风险评估（脚本已按阈值标注）
```json
{stat_block}
```

{self._build_bankr_block()}

{self._build_community_blocks(community_info, community_mods, mod_tweets, community_top) if has_community else ''}

# 输出要求

读者是熟练玩 meme 币的 degen，不需要解释什么叫 meme / degen / CTO / 毕业。
**整篇报告控制在 600 字以内**，直接给事实和可操作信号，不要展开复述素材。

# ⚠️ 元规则（最高优先级，违反此条即作废报告）

**输出里禁止出现任何对规则的引用、自我评注或保留说明**：
- ❌ "（注：叙事性弱，但勉强可列）"
- ❌ "（按规则不列，但仅供参考）"
- ❌ "（thesis 原文未找到，跳过）"
- ❌ "（违反规则但保留）" / "（仅为数据陈述）"
- ❌ "**无叙事性 KOL 观点**：社区主流仅..."（如果你上面已经列了 KOL，就不能在底下又说"无")

**正确做法**：内部判断完 → 输出的就是**最终结果**。不符合规则的内容**直接删除整行**，不要写"按规则跳过"，也不要列出来再附"不列"注释。
读者只看输出，不需要看你的筛选过程。**报告必须前后一致**，不能"列了"又说"无"。

# 🌐 语言规则

读者母语是中文。**所有完整英文句子必须先翻译成中文，再用括号附上英文原文**：
- ✅ 正确：`官网称"每枚国家队币的 50% 创建费用于买入并销毁 $WORLDCUP，另 50% 用于营销"（原文：50% of creator fees from every country coin is used to buy and burn $WORLDCUP. The other 50% goes to marketing.）`
- ✅ 正确：`定性"足球是地球上最大的叙事"（原文：Football is the biggest narrative on Earth）`
- ❌ 错误：直接堆英文原文不翻译
- ❌ 错误：只翻译不附原文（用户需要核对原文）

**例外**（这些保留英文原样，不需要翻译）：
- 项目名 / 代币符号：$WORLDCUP / PumpFun / Polymarket / @WorldCupCoinsPF
- 短技术词：CA / MC / ATH / RPC API key / TG / Buy&burn / 50/50
- 单词级英文：sending / bullish / scam / farming / thesis（这些已是 crypto 圈通用词）

**简而言之**：完整英文句子或短语必须"中文翻译 + 括号原文"双写；专有名词和单词缩写保留英文。

**禁止用以下通用模板话**：
- ❌ "绑定 XX 文化"、"XX 爱好者聚集地"、"高风险高回报"、"年轻投机者"
- ❌ "新生阶段"、"早期 CTO"、"meme 驱动"、"社区驱动"、"病毒传播"
- ❌ "看点在于能否突破"、"等待突破"、"继续观察"
- ❌ 罗列链上 stat 数字（"Top10 18%、新钱包 16%、Bot 35%" 这种每个币都差不多的对读者无价值）

**必须给**（每项有具体数字、handle、时间、引文）：

**核心叙事**（2-3 句，开门见山）：
- 这是什么类型（纯 meme / 概念绑定 / 工具类）？绑定哪个具体事件 / IP？
- 有 utility 吗（buy&burn / staking / 奖金池）？引用 1 句官方/官网原文佐证
- 项目方组织形式（个人账号 / X Community / 匿名团队）

**官方账号在说什么**（**全部中文总结 + 按主题分类**，禁止直接堆砌英文原文）：
- 数据源优先级：素材 10（Community mods 个人推文）> 素材 3（官方账号推文）。哪个有用哪个。
- **输出格式**：先一行整体定调（如"项目方在密集推 buy&burn 机制 + 销毁数据 + 危机透明化"），然后按以下主题分类：
  - 💡 **机制/utility 公告**：用中文一句话描述项目方说的机制，**关键数字必须保留**（如 "Buy&burn bot 24/7 远程托管，首阶段 100% 销毁→后续 50/50"）
  - 📊 **数据/进展披露**：销毁数据、用户数、活动进展，**带具体数字**（如 "5/13 累计销毁 5977 万币 ≈ $300K，每 10 分钟约 $1101"）
  - 🚨 **危机/事故**：事故经过 + 处理结果（如 "5/13 12:11 网站泄露 RPC API key，暂停 burn 1 小时，承诺补烧"）
  - 🎁 **预告/承诺**：暗示的新功能或奖励（如 "暗示赢家获世界杯门票/现金奖励，方案'考虑中'"）
  - 🌐 **社区/联动**：被 tag 的大账号、KOL 互动、群组动态
- 仅在主题确实存在时列出；不要硬凑空板块。
- 活跃度一句话带过（如"5/13 单日发推 12 条"）
- 删过推文吗？删了什么（若有，作为单独一条放最后）

**叙事演变**（3-6 条 bullet，正叙，**严格筛选，宁缺勿滥**）：
- 格式：`YYYY-MM-DD HH:MM | @handle (X粉) | 事件 + 中文要点 ≤ 30 字`
- **只列以下类型的真叙事节点**：
  1. 官方机制公告 / 官方危机 / 官方预告
  2. **带具体 thesis 内容**的 KOL call（必须在素材里能找到该 KOL **当时**给出的具体叙事观点）
  3. 联动事件（其他项目方互动、被资讯账号点名）
- **明确禁止进入此板块**：
  - "Nx profit / 100x / sending / bullish af" 这类纯涨幅喊单
  - "I gave you thesis at Xk / Moby traders 在 X 就抓到了" 这类**回顾性吹牛**（无具体观点内容）
  - 单纯发 CA / "early" / "没人讨论这个币" / "Give it 2 seconds" 这类**无内容**推文
  - 粉丝 < 1000 且无独特观点的账号
- **thesis 处理铁律**：KOL 说"我在 70k 时 call 过 / 给了 thesis"，必须在素材里找到他 70k 时的**原始 thesis 推文**并引用具体观点。
  - **找不到原文 → 这条 KOL 在叙事演变板块完全不能出现**
  - **禁止出现任何形式的占位说明**，包括但不限于：
    - ❌ "（thesis 原文未在素材中找到，跳过）"
    - ❌ "（找不到 thesis 内容）"
    - ❌ "（素材中无原文）"
  - 简单说：找不到原文 → **这一行 bullet 整条删除**，不留痕迹

- **单纯发 CA 铁律**：任何推文如果只是"发 CA / 发 CA + 表情 / 发 CA + 无文字描述 / @某账号 + CA"，**禁止进入叙事演变板块**，无论该 KOL 粉丝多高。叙事节点必须有**实质内容**（机制 / 事件 / 观点）。

**关键 KOL**（**只列叙事性 KOL**，纯价格判断不列）：
- **优先级 1 - 反向 KOL**（不卡粉丝数）：任何公开质疑 / 砸盘 / larp 指控 / 揭露 insider 的推文，必列
  - 格式：`🚨 @handle (X粉, ✅若验证) | 日期 | 中文要点：xxx（原话引用 ≤ 25 字）`
- **优先级 2 - 给出叙事性观点的 KOL**（**粉丝必须 ≥ 1000，硬条件，<1000 一律不进**）：发表了**对项目本身的叙事判断 / 机制解读 / 独特视角**的推文
  - 格式：`📈 @handle (X粉, ✅) | 日期 | 观点：xxx`
  - ✅ 算叙事性观点的例子："Polymarket 搬来 meme，有销毁回购" / "世界杯预测飞轮叙事" / "AI 芯片是这十年最强 fundamental" / "dev 来自 $peaceguy" / "$WORLDCUP 是国家队子币的 hub"
  - ❌ **绝对不算叙事性观点（即使包装得再好也不能列）**：
    - **价格走势预测 / 喊单**：
      - "下一站 5M / 10M / 100M"、"目标 X 倍"
      - "盘整后继续走高"、"短期内冲 5M"、"将翻 N 倍"
      - "8 小时涨超 150%"、"sending / pumping / mooning"
      - "150% up in the last 8 hours, consolidating before going higher" 这种**典型 trader 喊单**
    - **回顾价格表现**：
      - "X MC 时抓到了"、"Nx profit"、"没回调过"、"early call"
      - "16x runner / 32x / 100x" 这类倍数吹牛
      - "I told you at X / I gave thesis at Y"（即使配合了 thesis 也不列，因为 thesis 原文要在素材里能找到才算）
    - **纯市场情绪**：
      - "图表最强"、"volume 起飞"、"FOMO 来了"
      - "chart sexy"、"insane volume"、"bullish af"
      - "Moby traders scored hard"、"smart money 进场"
    - **纯数据陈述（无独特解读）**：
      - "持有人 4.5K"、"无 CEX listed"、"流动性 X"
      - 除非这段陈述紧接着给出了一个**独特的判断**（比如"4.5K 持有人但无 CEX = 二次拉升前的低位"——这才算）
  - **铁律**：判断一条 KOL 是否"叙事性"，问自己：**他在告诉读者"为什么这个币会火 / 为什么这个币不一样"，还是"这个币涨了多少 / 接下来涨多少"？** 后者绝对不列，前者列。
  - **粉丝 <1000 的账号即使有好观点也不列**（信号噪音比太低，宁缺勿滥）；唯一例外是反向 KOL（优先级 1）
- **核心检验**：这条推文是否在告诉读者"这个币**为什么会火 / 为什么不一样**"，而不是"这个币**涨了多少 / 接下来涨多少**"。前者列，后者不列。
- 如果筛完没有叙事性 KOL，整个板块写**一句话**："无叙事性 KOL 观点（社区主流仅价格喊单，无 thesis 解读、无反向声音）"，**不要硬凑**

**风险信号**（**最多 3 条**，只列"社交层"硬信号；链上 stat 数据除非极端否则不重复）：
- **任何 KOL 公开质疑 / 砸盘 / 指控 larp**（**不卡粉丝数**，引用原文 ≤ 25 字）
- 官方是否删过敏感推文（看素材 4）
- 是否有钓鱼网站 / 假 dex 拉票 / 碰瓷官方账号（@solana / @pumpfun 等）
- **素材 8 的链上数据，只在极度异常时（如 Dev 已发 >100 个币、Bundler>20%）提 1 条**
- 都干净就一句话："未见社交层负面信号"

禁止输出"现在能做什么"、"总结"、"免责声明"、"市场情绪" 等板块。禁止重复头部已经显示的 MC / 价格 / 24h。"""

        system_msg = (
            "你是给职业 meme 币交易员做情报简报的分析师。"
            "对面读者每天交易十几个币，极度讨厌废话、通用套话、和'什么是 degen 文化'这种初学者解释。"
            "只写事实、数字、具体 handle、具体时间、具体引文。报告必须简短，控制在 600 字以内。"
            "**所有素材已就位**，从素材里提炼即可，不要调用任何外部工具。"
            "如果某项信息素材里没有，直接写'未见'，不要脑补编造。\n\n"
            "🚨 **元规则（违反即作废）**：你的输出是给人类读的最终报告，**不是给你自己看的筛选过程**。\n"
            "禁止在输出中出现任何下面这类内容（无论用什么修辞包装）：\n"
            "1. ❌ '（注：xxx，按规则不列）' '（不符合 thesis 规则）' '（粉丝<1000 不列）' 这类规则注释\n"
            "2. ❌ '@X 说 yyy，但无 thesis 内容，跳过' 这类'列出+解释为何不列'的矛盾结构\n"
            "3. ❌ 在'无叙事性 KOL'之后又补一段'@A 说 X、@B 说 Y、均不列' 的反例陈列\n"
            "4. ❌ '（但仅供参考）' '（叙事性弱但勉强列）' 这类犹豫修辞\n\n"
            "**正确做法**：内部判断后只输出符合规则的结果。不符合的内容**完全消失**，不留任何痕迹。\n"
            "**输出前自检**：扫一遍整篇报告，搜索是否有 '按规则'、'不列'、'但无'、'粉丝<'、'thesis 原文未'、'勉强'、'纯回顾'、'纯数据陈述' 等词，**有任何一个出现就重写那一段**，把对应内容整条删除。\n"
            "报告必须前后一致：列了 = 它符合规则；说'无' = 后面不再出现任何相关内容。"
        )
        return system_msg, user_prompt

    def _call_grok(self, key, system_msg, user_prompt):
        model = GROK_DEEP if self.deep else GROK_DEFAULT
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            logger.info(f"🤖 Grok ({model}) 提炼中...")
            resp = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=240)
            resp.raise_for_status()
            result = resp.json()
            content = self._extract_responses_text(result)
            usage = result.get("usage", {})
            logger.info(f"✅ Grok 返回 {len(content)} 字符，tokens: in={usage.get('input_tokens')} out={usage.get('output_tokens')}")
            return content.strip() if content else None
        except requests.HTTPError as e:
            logger.error(f"Grok HTTP 错误: {e.response.status_code} {e.response.text[:400]}")
            return None
        except Exception as e:
            logger.error(f"Grok 调用失败: {e}")
            return None

    def _call_deepseek(self, key, system_msg, user_prompt):
        model = DEEPSEEK_DEEP if self.deep else DEEPSEEK_DEFAULT
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.4,
        }
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            logger.info(f"🤖 DeepSeek ({model}) 提炼中...")
            resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=240)
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            logger.info(
                f"✅ DeepSeek 返回 {len(content)} 字符，tokens: in={usage.get('prompt_tokens')} out={usage.get('completion_tokens')}"
            )
            return content.strip() if content else None
        except requests.HTTPError as e:
            logger.error(f"DeepSeek HTTP 错误: {e.response.status_code} {e.response.text[:400]}")
            return None
        except Exception as e:
            logger.error(f"DeepSeek 调用失败: {e}")
            return None

    # ---------- bankr.bot 素材块（仅当 base 链 + 是 bankr 部署时使用） ----------
    def _build_bankr_block(self):
        if not self.bankr_launch:
            return ""
        launch = self.bankr_launch
        dep = launch.get("deployer") or {}
        fee = launch.get("feeRecipient") or {}
        dep_name = dep.get("xUsername") or ""
        fee_name = fee.get("xUsername") or ""
        dep_w = (dep.get("walletAddress") or "").lower()
        fee_w = (fee.get("walletAddress") or "").lower()
        # 用钱包地址判定 dev 自发(xUsername 可能 null)
        same = bool(dep_w and fee_w and dep_w == fee_w)
        # 用于叙事文案的显示名:有 X 用 @handle,没 X 用 wallet
        fee_display = f"@{fee_name}" if fee_name else f"钱包 {fee_w}"
        dep_display = f"@{dep_name}" if dep_name else f"钱包 {dep_w}"
        if same:
            mode_text = f"**dev 自发**（部署者本人 = fee 接收者，同一钱包 {fee_w}，项目方主动部署）"
            implication = "项目方有 token 战略,代币是其官方发行。"
        else:
            mode_text = "**社区代发 / bankr 钓鱼模式**（部署者 ≠ fee 接收者）"
            implication = (
                f"**叙事核心**：{fee_display} 是 fee 接收者但不一定是部署者本人，"
                f"通常是 bankr 用户单方面把 fee 路由到该钱包,赌该钱包持有人会公开认领并 claim。\n"
                f"**重点核查**：{fee_display} 是否公开回应/认领/沉默/拉黑？这是该代币的最关键信号。"
            )

        # fee 状态(若 /fees endpoint 也拉到了)
        fee_status_block = ""
        fs = self._extract_fee_stats()
        if fs:
            fee_status_block = f"""
**Fee claim 状态**（{fee_display} 的钱包级累计）:
- 历史 claim **{fs['count']} 次**
- 累计已领 **{fs['claimed_weth']:.3f} WETH**
- 累计未领（可提取）**{fs['claimable_weth']:.3f} WETH**

判断 {fee_display} 的行为模式:
- count=0 + 未领数额大 → 项目方/受赠人 **从未动 fee**(沉默或不知情)
- count>0 → ta **持续 claim**,与公开态度对照看是否一致
"""

        return f"""# 素材 12: Bankr 部署元数据 ⭐⭐⭐
此代币通过 bankr.bot 部署,以下是该部署的元数据:

- 部署者 (deployer): @{dep_name}  钱包 {dep.get('walletAddress') or '?'}
- Fee 接收者 (feeRecipient): @{fee_name}  钱包 {fee.get('walletAddress') or '?'}
- 关联推文: {launch.get('tweetUrl') or '（无）'}
- 部署交易: {launch.get('txHash') or '（无）'}

**判定**: {mode_text}

{implication}
{fee_status_block}
⚠️ 输出时:
- 在"核心叙事"里**明确点出**这是 dev 自发还是社区代发(若是社区代发,必须指出 @{fee_name} 是否认领)。
- 如是社区代发,在"风险信号"里必列一条:fee 接收者 @{fee_name} 的态度(从素材 3/6/7 里找他的相关推文反应,结合 claim 次数对照看)。
"""

    # ---------- community 素材块（仅当有 community 时使用） ----------
    def _build_community_blocks(self, info, mods, mod_tweets, community_top):
        info_compact = {
            "name": info.get("name"),
            "description": info.get("description"),
            "member_count": info.get("member_count"),
            "moderator_count": info.get("moderator_count"),
            "created_at": info.get("created_at"),
            "creator": {
                "screen_name": (info.get("creator") or {}).get("screen_name"),
                "name": (info.get("creator") or {}).get("name"),
                "followers": (info.get("creator") or {}).get("followers_count"),
                "verified": (info.get("creator") or {}).get("isBlueVerified"),
                "bio": (info.get("creator") or {}).get("description"),
            },
        }
        mods_compact = [{
            "screen_name": m.get("screen_name"),
            "name": m.get("name"),
            "followers": m.get("followers_count"),
            "verified": m.get("isBlueVerified"),
            "bio": m.get("description"),
        } for m in (mods or [])]

        mod_tweets_compact = {}
        for h, ts in (mod_tweets or {}).items():
            mod_tweets_compact[f"@{h}"] = self._compact_tweets(ts, limit=15)

        community_top_compact = self._compact_tweets(community_top, limit=15)

        return f"""# 素材 9: X Community 元信息 ⭐
项目方挂的是 X Community，不是个人账号。社区基本信息：
```json
{json.dumps(info_compact, ensure_ascii=False, indent=2)}
```

# 素材 10: Community 创建者 + Moderators 的个人推文 ⭐⭐⭐
这是**项目方真实声音**（X Community 的 creator + moderators 是核心团队，他们的个人 timeline 等价于"官方账号在说什么"）。
Moderators 列表（{len(mods_compact)} 人）：
```json
{json.dumps(mods_compact, ensure_ascii=False, indent=2)}
```

各人最近推文（按用户 handle 分组）：
```json
{json.dumps(mod_tweets_compact, ensure_ascii=False, indent=2)}
```

# 素材 11: Community 内部最热推文（已按 engagement 排序取 top 15）
社区内成员的真实讨论（按 likes×3 + retweet×5 + views÷100 排序）：
```json
{json.dumps(community_top_compact, ensure_ascii=False, indent=2)}
```
"""

    # ---------- 素材压缩 ----------
    @staticmethod
    def _compact_tweets(raw, limit=20):
        if not raw:
            return []
        items = raw if isinstance(raw, list) else (raw.get("data") if isinstance(raw, dict) else [])
        out = []
        for t in (items or [])[:limit]:
            if not isinstance(t, dict):
                continue
            out.append({
                "date": _to_cst_str(t.get("createdAt", "")),
                "user": f"@{t.get('userScreenName', '?')}",
                "followers": t.get("userFollowers"),
                "verified": t.get("userVerified", False),
                "views": t.get("viewCount"),
                "likes": t.get("favoriteCount"),
                "rt": t.get("retweetCount"),
                "reply": t.get("replyCount"),
                "text": (t.get("text") or "")[:500],
            })
        return out

    @staticmethod
    def _compact_user(raw):
        if not raw:
            return {}
        u = raw if isinstance(raw, dict) and "screenName" in raw else (raw.get("data") if isinstance(raw, dict) else {})
        if not isinstance(u, dict):
            return {}
        return {
            "screenName": u.get("screenName"),
            "name": u.get("name"),
            "description": u.get("description"),
            "followers": u.get("followersCount"),
            "following": u.get("friendsCount"),
            "statuses": u.get("statusesCount"),
            "verified": u.get("verified"),
            "createdAt": u.get("createdAt"),
        }

    @staticmethod
    def _compact_kol(raw):
        if not raw:
            return {"totalCount": 0, "users": []}
        if isinstance(raw, dict):
            users = raw.get("users") or []
            total = raw.get("totalCount", len(users))
        else:
            users = raw
            total = len(users)
        compact_users = []
        for u in (users or [])[:20]:
            if not isinstance(u, dict):
                continue
            compact_users.append({
                "screenName": u.get("screenName"),
                "name": u.get("name"),
                "followers": u.get("followersCount") or u.get("followers"),
                "verified": u.get("verified"),
            })
        return {"totalCount": total, "users": compact_users}

    @staticmethod
    def _extract_responses_text(result: dict) -> str:
        if "output" in result and isinstance(result["output"], list):
            texts = []
            for item in result["output"]:
                if item.get("type") == "message":
                    for c in item.get("content", []) or []:
                        if c.get("type") in ("output_text", "text"):
                            texts.append(c.get("text", ""))
            if texts:
                return "\n".join(t for t in texts if t)
        if "output_text" in result:
            return result["output_text"]
        if "choices" in result:
            return result["choices"][0]["message"]["content"]
        return ""

    # ---------- 输出组装 ----------
    def format_output(self, llm_text: str):
        t = self.token
        symbol = t.get("symbol") or "?"
        name = t.get("name") or ""
        price = self.current_price()
        circ = self._to_float(t.get("circulating_supply") or t.get("total_supply"))
        mc = price * circ if price and circ else 0
        ath_price = self._to_float(t.get("ath_price"))
        ath_mc = ath_price * circ if ath_price and circ else 0
        change_24h = self.change_pct("24h")

        mc_str = f"${self._human_num(mc)}" if mc else "?"
        ath_str = f" (ATH ${self._human_num(ath_mc)})" if ath_mc else ""
        ch_str = ""
        if change_24h is not None:
            arrow = "📈" if change_24h >= 0 else "📉"
            ch_str = f" | 24h {change_24h:+.1f}% {arrow}"

        link = t.get("link") or {}
        handle = self.tw_data.get("_handle", "")
        x_url = self.tw_data.get("_x_url", "")

        # 头部一行：项目名 + MC + 24h
        head = f"**${symbol} ({name})** | MC {mc_str}{ath_str}{ch_str}"

        # 元信息一行：CA + 链 + 社交链接
        meta_bits = [f"`{self.address}`", self.chain.upper()]
        if handle:
            meta_bits.append(f"X:@{handle}")
        elif x_url:
            # 没有 handle 但有 X URL（如 community），直接展示完整 URL
            meta_bits.append(f"X:{x_url}")
        if link.get("website"):
            meta_bits.append(link["website"])
        if link.get("telegram"):
            meta_bits.append(f"TG:{link['telegram']}")
        meta = "  |  ".join(meta_bits)

        # bankr 元数据行（仅 base 链 + 是 bankr 部署）
        bankr_line = None
        fee_line = None
        if self.bankr_launch:
            dep_obj = self.bankr_launch.get("deployer") or {}
            fee_obj = self.bankr_launch.get("feeRecipient") or {}
            dep_x = dep_obj.get("xUsername")
            fee_x = fee_obj.get("xUsername")
            dep_w = (dep_obj.get("walletAddress") or "").lower()
            fee_w = (fee_obj.get("walletAddress") or "").lower()
            # 比较钱包地址而不是 xUsername(xUsername 可能 null)
            if dep_w and fee_w:
                same_wallet = (dep_w == fee_w)
                # 显示:有 X 用 @handle,没 X 用钱包短地址
                dep_disp = f"@{dep_x}" if dep_x else f"`{dep_w[:6]}..{dep_w[-4:]}`"
                fee_disp = f"@{fee_x}" if fee_x else f"`{fee_w[:6]}..{fee_w[-4:]}`"
                if same_wallet:
                    mode = "🟢 dev 自发"
                else:
                    catch_target = f"@{fee_x}" if fee_x else fee_disp
                    mode = f"🟡 社区代发 → 赌 {catch_target} 认领"
                bankr_line = f"📡 Bankr | deployer:{dep_disp} → feeRecipient:{fee_disp} | {mode}"

            # fee 状态行
            fs = self._extract_fee_stats()
            if fs:
                fee_line = f"💸 Fee | 已 claim {fs['count']} 次 / 已领 {fs['claimed_weth']:.3f} WETH / 未领 {fs['claimable_weth']:.3f} WETH"

        lines = [head, meta]
        if bankr_line:
            lines.append(bankr_line)
        if fee_line:
            lines.append(fee_line)
        lines.append("")
        if llm_text:
            lines.append(llm_text)
        else:
            lines.append("_（⚠️ LLM 调研失败，仅展示基础信息）_")
        return "\n".join(lines)

    @staticmethod
    def _to_float(v):
        if v is None:
            return 0.0
        try:
            return float(v)
        except Exception:
            return 0.0

    @staticmethod
    def _human_num(n: float) -> str:
        if n >= 1e9: return f"{n/1e9:.2f}B"
        if n >= 1e6: return f"{n/1e6:.1f}M"
        if n >= 1e3: return f"{n/1e3:.1f}K"
        return f"{n:.0f}"

    @staticmethod
    def _fmt_num(n: float) -> str:
        return f"{n:,.0f}" if n >= 1 else f"{n:.6f}"

    @staticmethod
    def _fmt_price(p: float) -> str:
        if p >= 1: return f"{p:,.4f}"
        if p >= 0.0001: return f"{p:.6f}"
        return f"{p:.10f}".rstrip("0").rstrip(".")


def load_keys(backend: str):
    if GMGN_ENV_PATH.exists():
        load_dotenv(GMGN_ENV_PATH, override=False)
    load_dotenv(override=False)

    if backend == "deepseek":
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError(
                f"❌ 未配置 DEEPSEEK_API_KEY。请在 {GMGN_ENV_PATH} 追加：\n"
                f"   DEEPSEEK_API_KEY=sk-...\n"
                f"   申请: https://platform.deepseek.com/"
            )
    else:
        key = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")
        if not key:
            raise RuntimeError(
                f"❌ 未配置 XAI_API_KEY。请在 {GMGN_ENV_PATH} 追加：\n"
                f"   XAI_API_KEY=xai-...\n"
                f"   申请: https://x.ai/api"
            )

    ot = os.environ.get("OPENTWITTER_TOKEN") or os.environ.get("TWITTER_TOKEN")
    if not ot:
        logger.warning(f"⚠️ 未配置 OPENTWITTER_TOKEN，跳过 6551 推文素材")
    tw_io = os.environ.get("TWITTERAPI_IO_KEY")
    if not tw_io:
        logger.warning(f"⚠️ 未配置 TWITTERAPI_IO_KEY，跳过 X Community 数据")
    return key, ot, tw_io


def main():
    parser = argparse.ArgumentParser(description="/ca 代币情报")
    parser.add_argument("address", help="代币合约地址")
    parser.add_argument("--llm", choices=["deepseek", "grok"], default="deepseek",
                        help="LLM 后端 (默认 deepseek)")
    parser.add_argument("--deep", action="store_true", help="深度模式（deepseek-reasoner / grok-4）")
    parser.add_argument("--chain", choices=["sol", "bsc", "base", "eth"], help="手动指定链")
    args = parser.parse_args()

    try:
        llm_key, ot_token, tw_io_key = load_keys(args.llm)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    analyzer = CaAnalyzer(args.address, deep=args.deep, forced_chain=args.chain)

    try:
        analyzer.detect_chain()
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    analyzer.evaluate_stat()
    # 解析官方 twitter（handle / community_id），后续三块 IO 共用
    analyzer._parse_official_twitter()

    # 并行五块 IO：website / 6551 推文 / twitterapi.io community / bankr 元数据 / bankr fee 状态
    with ThreadPoolExecutor(max_workers=5) as ex:
        f_web = ex.submit(analyzer.fetch_website)
        f_tw = ex.submit(analyzer.fetch_opentwitter, ot_token)
        f_cm = ex.submit(analyzer.fetch_community, tw_io_key)
        f_bk = ex.submit(analyzer.fetch_bankr_launch)
        f_bf = ex.submit(analyzer.fetch_bankr_fees)
        f_web.result()
        f_tw.result()
        f_cm.result()
        f_bk.result()
        f_bf.result()

    llm_text = analyzer.fetch_llm(args.llm, llm_key)
    print(analyzer.format_output(llm_text))


if __name__ == "__main__":
    main()
