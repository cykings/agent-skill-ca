#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Base 链 bankr 代币的 fee claim 时间表
# 用法: python claim_history.py <CA>
# 输出每次 claim 的精确 UTC 时间 + WETH 数量 + token 数量 + tx hash

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

RPC = "https://mainnet.base.org"
WETH = "0x4200000000000000000000000000000000000006"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def get_bankr_launch(ca):
    r = requests.get(f"https://api.bankr.bot/token-launches/{ca.lower()}", timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("launch")


def rpc_call(method, params, timeout=15):
    r = requests.post(RPC, json={"jsonrpc":"2.0","method":method,"params":params,"id":1}, timeout=timeout)
    return r.json().get("result")


def get_logs(contract, from_block, to_block, to_topic):
    # 注意:mainnet.base.org 公共节点单次 getLogs 限制 10,000 block
    r = requests.post(RPC, json={
        "jsonrpc":"2.0","method":"eth_getLogs","id":1,
        "params":[{
            "address": contract,
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "topics": [TRANSFER_TOPIC, None, to_topic],
        }]
    }, timeout=30)
    d = r.json()
    if "error" in d:
        # 不静默,抛出让上层 retry 或减小范围
        raise RuntimeError(f"getLogs {from_block}-{to_block}: {d['error'].get('message')}")
    return d.get("result") or []


def get_block_ts(block_num):
    b = rpc_call("eth_getBlockByNumber", [hex(block_num), False])
    return int(b["timestamp"], 16) if b else None


def query_claim_history(token_ca, fee_wallet, max_lookback=200000):
    # max_lookback 是要往回查的 block 数量,base 出块 ~2s,200000 block ≈ 4.6 天
    # 公共 RPC 单次 getLogs 上限通常 50000,所以要分批
    latest = int(rpc_call("eth_blockNumber", []) or "0x0", 16)
    if not latest:
        raise RuntimeError("拿不到最新区块")
    earliest = max(0, latest - max_lookback)
    to_topic = "0x" + "0" * 24 + fee_wallet[2:].lower()

    # 分批查 — 公共节点单次范围限制 10000 block,我们用 9500 留余量
    all_logs = []
    batch = 9500
    for ca in [token_ca.lower(), WETH.lower()]:
        start = earliest
        while start <= latest:
            end = min(start + batch, latest)
            try:
                logs = get_logs(ca, start, end, to_topic)
                for log in logs:
                    log["_kind"] = "WETH" if ca == WETH.lower() else "TOKEN"
                all_logs.extend(logs)
            except Exception as e:
                print(f"⚠️ getLogs {ca[:10]} 批 {start}-{end} 失败: {e}", file=sys.stderr)
            start = end + 1

    if not all_logs:
        return []

    # 合并同一笔 tx 的两条 Transfer(WETH + TOKEN 一笔交易里通常成对出现)
    by_tx = {}
    for log in all_logs:
        tx = log["transactionHash"]
        block = int(log["blockNumber"], 16)
        kind = log["_kind"]
        value = int(log["data"], 16) / 1e18
        from_addr = "0x" + log["topics"][1][-40:]
        if tx not in by_tx:
            by_tx[tx] = {"tx": tx, "block": block, "from": from_addr, "weth": 0.0, "token": 0.0}
        if kind == "WETH":
            by_tx[tx]["weth"] += value
        else:
            by_tx[tx]["token"] += value

    # 拿每个 block 的 timestamp(并发)
    unique_blocks = sorted({c["block"] for c in by_tx.values()})
    ts_cache = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(get_block_ts, b): b for b in unique_blocks}
        for fut, b in futures.items():
            try:
                ts = fut.result(timeout=30)
                if ts:
                    ts_cache[b] = ts
            except Exception:
                pass
    for c in by_tx.values():
        c["ts"] = ts_cache.get(c["block"])
        if c["ts"]:
            c["time"] = datetime.fromtimestamp(c["ts"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            c["time"] = "?"

    return sorted(by_tx.values(), key=lambda x: x["block"])


def main():
    parser = argparse.ArgumentParser(description="查 Base 上 bankr 代币的 fee claim 时间表")
    parser.add_argument("ca", help="代币合约地址")
    parser.add_argument("--lookback", type=int, default=200000,
                        help="往回查多少 block (默认 200000 ≈ 4.6 天)")
    args = parser.parse_args()

    ca = args.ca.strip()
    print(f"🔍 查询 {ca} ...", file=sys.stderr)
    launch = get_bankr_launch(ca)
    if not launch:
        print(f"❌ 该 CA 不是 bankr 部署 (或 bankr API 找不到)", file=sys.stderr)
        sys.exit(1)

    fee_wallet = (launch.get("feeRecipient") or {}).get("walletAddress")
    fee_x = (launch.get("feeRecipient") or {}).get("xUsername") or "?"
    dep_x = (launch.get("deployer") or {}).get("xUsername") or "?"
    symbol = launch.get("tokenSymbol") or "?"

    if not fee_wallet:
        print(f"❌ 拿不到 feeRecipient wallet", file=sys.stderr)
        sys.exit(1)

    print(f"📡 deployer:@{dep_x} → feeRecipient:@{fee_x}  wallet: {fee_wallet}", file=sys.stderr)
    print(f"⛓️  查 ${symbol} ({ca}) 的 token+WETH transfer 到 fee wallet ...", file=sys.stderr)

    claims = query_claim_history(ca, fee_wallet, args.lookback)
    if not claims:
        print(f"⚠️ lookback {args.lookback} block 内未找到 claim 记录", file=sys.stderr)
        sys.exit(0)

    # 输出 markdown 表格
    print()
    print(f"# ${symbol} Fee Claim 历史")
    print(f"- CA: `{ca}`")
    print(f"- feeRecipient: @{fee_x}  `{fee_wallet}`")
    print(f"- 共 {len(claims)} 次 claim")
    print()
    print("| # | 时间 (UTC) | block | WETH | TOKEN | TX |")
    print("|---|---|---|---|---|---|")
    total_weth = 0.0
    total_token = 0.0
    for i, c in enumerate(claims, 1):
        total_weth += c["weth"]
        total_token += c["token"]
        print(f"| {i} | {c['time']} | {c['block']} | {c['weth']:.4f} | {c['token']:,.2f} | `{c['tx'][:14]}...` |")
    print()
    print(f"**累计**: {total_weth:.4f} WETH + {total_token:,.2f} {symbol}")


if __name__ == "__main__":
    main()
