#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""走势形态相似扫描。默认 short(最近 5~10 日),可切 samelen(等长窗口)。

依赖:已落盘的前复权日 K(腾讯 fqkline raw JSON)。取数请用 data-access 的 fetch_kline.py。
只做形态筛选,不给投资动作建议。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROFILES = os.path.join(HERE, "profiles.json")


def load_profiles(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_bars(code: str, search_roots: list[str]) -> list[dict] | None:
    for root in search_roots:
        base = root.replace("{code}", code)
        files = [p for p in glob.glob(os.path.join(base, "raw", "*.json"))
                 if "extracted" not in os.path.basename(p)]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for fpath in files:
            try:
                payload = json.load(open(fpath, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            data = payload.get("data")
            if not isinstance(data, dict):
                continue
            for key, val in data.items():
                if key == "market" or not isinstance(val, dict):
                    continue
                rows = val.get("qfqday")
                if not isinstance(rows, list) or not rows:
                    continue
                out = []
                for r in rows:
                    try:
                        out.append({
                            "date": r[0], "open": float(r[1]), "close": float(r[2]),
                            "high": float(r[3]), "low": float(r[4]), "vol": float(r[5]),
                        })
                    except (TypeError, ValueError, IndexError):
                        continue
                if out:
                    return out
    return None


def feats(seg: list[dict]) -> dict | None:
    n = len(seg)
    if n < 2 or seg[0]["close"] <= 0:
        return None
    base = seg[0]["close"]
    ret = seg[-1]["close"] / base - 1
    up = sum(1 for a, b in zip(seg, seg[1:]) if b["close"] > a["close"])
    lim = sum(1 for a, b in zip(seg, seg[1:]) if a["close"] > 0 and b["close"] / a["close"] - 1 >= 0.098)
    peak, mdd = -1.0, 0.0
    for b in seg:
        peak = max(peak, b["close"])
        mdd = min(mdd, b["close"] / peak - 1)
    vols = [b["vol"] for b in seg]
    avg = sum(vols) / n
    return {
        "days": n, "ret": ret, "slope": ret / n * 100, "mdd": abs(mdd) * 100,
        "up": up / (n - 1), "limit_up": lim,
        "volx": (avg / vols[0]) if vols[0] > 0 else 0.0,
        "start": seg[0]["date"], "end": seg[-1]["date"],
        "first": base, "last": seg[-1]["close"],
    }


def sigma_for(tier: str, profiles: list[dict], floors: dict) -> dict:
    pool = [p for p in profiles if p["tier"] == tier]
    out = {}
    for key, field in (("slope", "slope"), ("mdd", "mdd_pct"), ("up", "up"), ("volx", "volx")):
        vals = [p[field] for p in pool]
        out[key] = max((max(vals) - min(vals)) / 2.0, floors[key])
    return out


def distance(f: dict, p: dict, sig: dict, w: dict) -> float:
    d2 = (
        w["slope"] * ((f["slope"] - p["slope"]) / sig["slope"]) ** 2
        + w["mdd"] * ((f["mdd"] - p["mdd_pct"]) / sig["mdd"]) ** 2
        + w["up"] * ((f["up"] - p["up"]) / sig["up"]) ** 2
        + w["volx"] * ((f["volx"] - p["volx"]) / sig["volx"]) ** 2
    )
    return math.sqrt(d2)


def candidate_lengths(mode: str, profiles: list[dict]) -> list[int]:
    if mode == "short":
        return list(range(5, 11))
    if mode == "samelen":
        return sorted({int(p["days"]) for p in profiles})
    raise ValueError(f"unknown mode: {mode}")


def read_codes(path: str) -> list[tuple[str, str]]:
    stocks = []
    seen = set()
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
                stocks.append((code, name))
    return stocks


def scan(mode: str, stocks: list[tuple[str, str]], cfg: dict, search_roots: list[str], top_n: int) -> tuple[list[dict], dict]:
    profiles = cfg["profiles"]
    gates = cfg["gates"]
    weights = cfg["weights"]
    floors = cfg["sigma_floor"]
    sig = {t: sigma_for(t, profiles, floors) for t in ("A", "B")}
    lengths = candidate_lengths(mode, profiles)

    hits: list[dict] = []
    attr = {"no_data": 0, "ret_le0": 0, "up_fail": 0, "slope_fail": 0, "tier_fail": 0, "ok": 0}
    for code, name in stocks:
        bars = load_bars(code, search_roots)
        if not bars or len(bars) < max(lengths) + 1:
            attr["no_data"] += 1
            continue
        best = None
        reason = "ret_le0"
        for L in lengths:
            if len(bars) < L:
                continue
            seg = bars[-L:]
            if any(b["vol"] <= 0 for b in seg):
                continue
            f = feats(seg)
            if not f:
                continue
            if f["ret"] <= 0:
                reason = "ret_le0"
                continue
            if f["up"] < gates["up_min"]:
                reason = "up_fail"
                continue
            if not (gates["slope_lo"] <= f["slope"] <= gates["slope_hi"]):
                reason = "slope_fail"
                continue
            if f["mdd"] <= gates["mdd_a_max"]:
                tier = "A"
            elif f["mdd"] <= gates["mdd_b_max"]:
                tier = "B"
            else:
                reason = "tier_fail"
                continue
            pool = [p for p in profiles if p["tier"] == tier]
            if mode == "samelen":
                pool = [p for p in pool if int(p["days"]) == L] or pool
            if not pool:
                reason = "tier_fail"
                continue
            d, prof = min(((distance(f, p, sig[tier], weights), p) for p in pool), key=lambda t: t[0])
            sc = 100.0 / (1.0 + d)
            if best is None or sc > best["score"]:
                best = {
                    "code": code, "name": name, "tier": tier, "score": sc, "L": L,
                    "matched": f"{prof['code']} {prof['name']}", **f,
                }
        if best:
            attr["ok"] += 1
            hits.append(best)
        else:
            attr[reason] = attr.get(reason, 0) + 1

    hits.sort(key=lambda h: (-h["score"], abs(h["mdd"] - (4.0 if h["tier"] == "A" else 11.0))))
    return hits[:top_n], {"attr": attr, "hits_total": len(hits), "mode": mode, "lengths": lengths}


def write_outputs(top: list[dict], meta: dict, out_dir: str, cfg: dict) -> None:
    os.makedirs(out_dir, exist_ok=True)
    data_end = max((h["end"] for h in top), default="unknown")
    a_n = sum(1 for h in top if h["tier"] == "A")
    b_n = sum(1 for h in top if h["tier"] == "B")
    lines = [
        f"mode={meta['mode']}  data_end={data_end}",
        f"profiles={cfg.get('version')}  top={len(top)}  A={a_n} B={b_n}",
        f"attr={meta['attr']}  hits_total={meta['hits_total']}",
        "NOTE: shape similarity screen only; not investment advice.",
        "",
        f"{'rank':>4} {'code':<8}{'name':<12}{'tier':<3}{'score':>6}{'window':>16}"
        f"{'ret%':>9}{'slope':>9}{'mdd%':>8}{'up%':>7}{'lim':>5}{'volx':>6}  matched",
    ]
    for i, h in enumerate(top, 1):
        win = f"{h['start']}+{h['L']}d"
        lines.append(
            f"{i:>4} {h['code']:<8}{h['name']:<12}{h['tier']:<3}{h['score']:>6.1f}{win:>16}"
            f"{h['ret']*100:>8.2f}%{h['slope']:>9.2f}{h['mdd']:>7.2f}%"
            f"{h['up']*100:>6.1f}%{h['limit_up']:>5}{h['volx']:>6.2f}  {h['matched']}"
        )
    lines.append("")
    lines.append("--- group by window length ---")
    for L in meta["lengths"]:
        grp = [h for h in top if h["L"] == L]
        if not grp:
            continue
        lines.append(f"\n{L}d ({len(grp)}):")
        for h in grp:
            lines.append(
                f"  {h['code']} {h['name']}  score={h['score']:.1f}  "
                f"ret={h['ret']*100:.1f}% mdd={h['mdd']:.1f}%  {h['matched']}"
            )

    txt_path = os.path.join(out_dir, "result.md")
    open(txt_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    csv_path = os.path.join(out_dir, "result.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "code", "name", "tier", "score", "window", "ret_pct",
                    "slope", "mdd_pct", "up_pct", "limit_up", "volx", "matched"])
        for i, h in enumerate(top, 1):
            w.writerow([
                i, h["code"], h["name"], h["tier"], f"{h['score']:.1f}",
                f"{h['start']}+{h['L']}d", f"{h['ret']*100:.2f}", f"{h['slope']:.2f}",
                f"{h['mdd']:.2f}", f"{h['up']*100:.1f}", h["limit_up"],
                f"{h['volx']:.2f}", h["matched"],
            ])
    readme = {
        "mode": meta["mode"],
        "data_end": data_end,
        "profiles_version": cfg.get("version"),
        "gates": cfg["gates"],
        "attr": meta["attr"],
        "hits_total": meta["hits_total"],
        "top": len(top),
        "A": a_n,
        "B": b_n,
        "disclaimer": "shape similarity only; not investment advice",
    }
    with open(os.path.join(out_dir, "README.json"), "w", encoding="utf-8") as f:
        json.dump(readme, f, ensure_ascii=False, indent=2)
    print(f"written {txt_path}")
    print(f"written {csv_path}")
    if meta["mode"] == "samelen" and (a_n == 0 or b_n == 0):
        print("WARNING: samelen delivered a zero tier in Top N; do not treat as complete.")
    if meta["mode"] == "short" and b_n == 0:
        print("NOTE: short mode often yields few/zero B-tier hits (window too short for deep drawdowns).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Shape-similarity stock screen")
    ap.add_argument("--mode", choices=["short", "samelen"], default="short",
                    help="short=recent 5..10 days (default); samelen=match each sample length")
    ap.add_argument("--codes-file", required=True, help="CSV lines: code,name[,...]")
    ap.add_argument("--profiles", default=DEFAULT_PROFILES)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--out-dir", default=".local/runs/shape-scan")
    ap.add_argument(
        "--kline-root", action="append", default=None,
        help="Search root with {code} placeholder. Repeatable. "
             "Default: .local/runs/latest-{code} then .local/runs/ambush-{code}",
    )
    args = ap.parse_args()
    roots = args.kline_root or [
        "./data/kline-{code}",
        ".local/runs/shape-scan/kline-{code}",
        ".local/runs/latest-{code}",
        ".local/runs/ambush-{code}",
        ".local/runs/pilot-{code}",
        ".local/runs/verify-{code}",
    ]
    cfg = load_profiles(args.profiles)
    stocks = read_codes(args.codes_file)
    top, meta = scan(args.mode, stocks, cfg, roots, args.top)
    write_outputs(top, meta, args.out_dir, cfg)


if __name__ == "__main__":
    main()
