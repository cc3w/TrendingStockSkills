#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 codes 文件批量拉取前复权日 K（调用同目录 fetch_kline.py）。

codes 文件每行: code,name
默认 3 并发；一只一个 out-dir。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FETCH = os.path.join(HERE, "fetch_kline.py")


def read_codes(path: str) -> list[tuple[str, str]]:
    out, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            code = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else code
            if code not in seen:
                seen.add(code)
                out.append((code, name))
    return out


def one(code: str, out_root: str, bars: int, timeout: float) -> tuple[str, int, str]:
    out_dir = os.path.join(out_root, f"kline-{code}")
    cmd = [
        sys.executable, FETCH,
        "--symbol", code,
        "--bars", str(bars),
        "--out-dir", out_dir,
        "--timeout", str(timeout),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    msg = (p.stdout or p.stderr or "").strip().splitlines()
    return code, p.returncode, (msg[-1] if msg else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes-file", required=True)
    ap.add_argument("--out-root", default="./data")
    ap.add_argument("--bars", type=int, default=90)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--limit", type=int, default=0, help="只取前 N 只，0=全部")
    args = ap.parse_args()

    stocks = read_codes(args.codes_file)
    if args.limit > 0:
        stocks = stocks[: args.limit]
    os.makedirs(args.out_root, exist_ok=True)

    ok = fail = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(one, code, args.out_root, args.bars, args.timeout) for code, _ in stocks]
        for fut in concurrent.futures.as_completed(futs):
            code, rc, msg = fut.result()
            if rc == 0:
                ok += 1
                print(f"OK  {code}  {msg}")
            else:
                fail += 1
                print(f"FAIL {code}  exit={rc}  {msg}", file=sys.stderr)

    print(f"done ok={ok} fail={fail} total={len(stocks)} out_root={args.out_root}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
