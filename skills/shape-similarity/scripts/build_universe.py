#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从通达信盘后包 / codes 文本生成主板候选池(沪深主板非 ST)。

不新取数:输入需已落盘。全市场名单唯一来源是 tdx_daily_package 上游函数。
输出:一行一只 `code,name`。
"""
from __future__ import annotations

import argparse
import json
import os
import re


MAIN_SH = re.compile(r"^sh(600|601|603|605)\d{3}$", re.I)
MAIN_SZ = re.compile(r"^sz(000|001|002|003)\d{3}$", re.I)


def is_mainboard(market_code: str) -> bool:
    s = market_code.strip().lower()
    return bool(MAIN_SH.match(s) or MAIN_SZ.match(s))


def load_st_set(path: str | None) -> set[str]:
    if not path or not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    out = set()
    # fetch_endpoint 结构化结果常见形态: data.rows / data.list / 顶层 list
    rows = payload
    if isinstance(payload, dict):
        data = payload.get("data") or payload
        rows = data.get("rows") or data.get("list") or data.get("stocks") or []
    if isinstance(rows, dict):
        rows = rows.values()
    for r in rows:
        if isinstance(r, dict):
            code = str(r.get("code") or r.get("symbol") or "").zfill(6)[-6:]
            name = str(r.get("name") or "")
            if code.isdigit():
                out.add(code)
            if "ST" in name.upper():
                out.add(code)
        elif isinstance(r, str) and r.isdigit():
            out.add(r.zfill(6)[-6:])
    return out


def from_codes_json(path: str) -> list[tuple[str, str]]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    rows = payload
    if isinstance(payload, dict):
        data = payload.get("data") or payload
        rows = data.get("rows") or data.get("list") or data.get("codes") or []
    out = []
    for r in rows:
        if isinstance(r, dict):
            code = str(r.get("code") or r.get("symbol") or "")
            name = str(r.get("name") or code)
            mkt = str(r.get("market") or r.get("exchange") or "").lower()
            full = f"{mkt}{code}" if mkt and not code.lower().startswith(("sh", "sz")) else code
            if is_mainboard(full if full.lower().startswith(("sh", "sz")) else f"sh{code}"):
                # 若无市场前缀,用代码规则判断
                c6 = re.sub(r"\D", "", code)[-6:]
                if c6.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
                    out.append((c6, name))
            else:
                c6 = re.sub(r"\D", "", str(code))[-6:]
                if c6.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
                    out.append((c6, name))
        elif isinstance(r, str):
            c6 = re.sub(r"\D", "", r)[-6:]
            if c6.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
                out.append((c6, c6))
    return out


def from_plain(path: str) -> list[tuple[str, str]]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            code = re.sub(r"\D", "", parts[0])[-6:]
            name = parts[1].strip() if len(parts) > 1 else code
            if code.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
                out.append((code, name))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", required=True, help="codes JSON or code,name text")
    ap.add_argument("--st-json", default=None, help="optional st_stock_list fetch JSON")
    ap.add_argument("--out", required=True, help="output code,name file")
    args = ap.parse_args()

    if args.codes.lower().endswith(".json"):
        stocks = from_codes_json(args.codes)
    else:
        stocks = from_plain(args.codes)

    st = load_st_set(args.st_json)
    seen = set()
    kept = []
    for code, name in stocks:
        if code in seen:
            continue
        seen.add(code)
        if code in st or "ST" in name.upper():
            continue
        kept.append((code, name))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for code, name in kept:
            f.write(f"{code},{name}\n")
    print(f"wrote {len(kept)} codes -> {args.out} (st_filtered={len(st)})")


if __name__ == "__main__":
    main()
