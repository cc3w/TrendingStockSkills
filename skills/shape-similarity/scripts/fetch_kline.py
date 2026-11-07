#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""前复权日 K（腾讯 fqkline，仅标准库）。

落盘形态与 scan_shape.py 兼容：
  <out-dir>/raw/tencent_fqkline.json   # 上游原响应
  <out-dir>/fetch/fetch_kline.json     # 简要元数据

退出码: 0 ok / 3 failed
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date

UA = "Mozilla/5.0 (compatible; shape-similarity/1.0)"
EP = "web.ifzq.gtimg.cn/fqkline"


def infer_market(digits: str) -> str:
    if digits.startswith(("5", "6", "9")):
        return "SH"
    if digits.startswith(("0", "1", "2", "3")):
        return "SZ"
    raise ValueError(f"无法从代码推断市场: {digits}")


def parse_symbol(raw: str) -> tuple[str, str]:
    s = raw.strip().upper().replace(".SH", "").replace(".SZ", "").replace("SH", "").replace("SZ", "")
    digits = re.sub(r"\D", "", s)[-6:]
    if len(digits) != 6:
        raise ValueError(f"代码须为 6 位: {raw}")
    # 显式前缀优先
    u = raw.strip().upper()
    if u.startswith("SH") or u.endswith(".SH"):
        return digits, "SH"
    if u.startswith("SZ") or u.endswith(".SZ"):
        return digits, "SZ"
    return digits, infer_market(digits)


def tencent_code(digits: str, market: str) -> str:
    return f"{'sh' if market == 'SH' else 'sz'}{digits}"


def validate(rows: list) -> list:
    good = []
    for r in rows:
        if len(r) < 6:
            continue
        try:
            date.fromisoformat(str(r[0])[:10])
            float(r[1]); float(r[2]); float(r[3]); float(r[4]); float(r[5])
        except (ValueError, TypeError):
            continue
        good.append([str(r[0])[:10], str(r[1]), str(r[2]), str(r[3]), str(r[4]), str(r[5])])
    if len(good) >= 2 and any(good[i][0] >= good[i + 1][0] for i in range(len(good) - 1)):
        raise ValueError("K 线日期非升序")
    return good


def fetch_tencent(digits: str, market: str, bars: int, timeout: float) -> tuple[bytes, list]:
    code = tencent_code(digits, market)
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{bars},qfq"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://gu.qq.com/"})
    content = urllib.request.urlopen(req, timeout=timeout).read()
    payload = json.loads(content)
    block = (payload.get("data") or {}).get(code) or {}
    kl = block.get("qfqday") or block.get("day") or []
    if not kl:
        raise ValueError("腾讯 K 线为空")
    rows = [[k[0], k[1], k[2], k[3], k[4], k[5]] for k in kl]
    return content, rows


def save(out_dir: str, digits: str, market: str, bars: int, raw: bytes, rows: list) -> dict:
    raw_dir = os.path.join(out_dir, "raw")
    fetch_dir = os.path.join(out_dir, "fetch")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(fetch_dir, exist_ok=True)
    raw_name = "tencent_fqkline.json"
    raw_path = os.path.join(raw_dir, raw_name)
    with open(raw_path, "wb") as f:
        f.write(raw)
    # 供 scan_shape 直接读: 保留腾讯 data.<code>.qfqday 结构
    meta = {
        "script": "fetch_kline",
        "status": "ok",
        "symbol": digits,
        "market": market,
        "bars_requested": bars,
        "bars": len(rows),
        "start": rows[0][0],
        "end": rows[-1][0],
        "source": "tencent",
        "endpoint": EP,
        "adjustment": "qfq",
        "raw_ref": f"raw/{raw_name}",
    }
    with open(os.path.join(fetch_dir, "fetch_kline.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="前复权日 K（腾讯公开源，标准库）")
    ap.add_argument("--symbol", required=True, help="6 位代码，可带 sh/sz 前缀")
    ap.add_argument("--bars", type=int, default=90)
    ap.add_argument("--out-dir", required=True, help="一只股票一个目录")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()
    try:
        digits, market = parse_symbol(args.symbol)
        raw, rows = fetch_tencent(digits, market, args.bars, args.timeout)
        good = validate(rows)
        if not good:
            raise ValueError("无合格 K 线行")
        meta = save(args.out_dir, digits, market, args.bars, raw, good)
        print(json.dumps(meta, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001
        err = {"script": "fetch_kline", "status": "failed", "error": str(e)}
        if args.out_dir:
            os.makedirs(os.path.join(args.out_dir, "fetch"), exist_ok=True)
            with open(os.path.join(args.out_dir, "fetch", "fetch_kline.json"), "w", encoding="utf-8") as f:
                json.dump(err, f, ensure_ascii=False, indent=2)
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
