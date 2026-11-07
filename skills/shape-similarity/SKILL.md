---
name: shape-similarity
description: A 股主板「走势形态相似」筛选。给定已核对的样本档案,在候选池上按 short(默认,近 5~10 日)或 samelen(等长窗口)算归一化形态距离并输出 Top 30。当用户要形态相似/走势像某几只票/短窗口复筛/等长窗口复筛时使用;不给买卖建议。取数用本 skill 内置腾讯前复权日 K 脚本。
---

# 走势形态相似筛选（shape-similarity）

形态相似 ≠ 投资建议。结论只能来自本轮真实取数与脚本打分；缺数据就写缺口。

## 何时用

- 用户给了（或沿用本 skill 内置的）样本区间，要在沪深**主板**找「形态像」的票
- 需要在 **`short`（默认）** 与 **`samelen`** 之间切换口径
- 不要用于：估值/财报研究、问财条件选股、暗示「即将启动/埋伏」

详细口径对照与样本表见 [reference.md](reference.md)。

## 硬约束

1. 日 K **必须**用本 skill 的 `scripts/fetch_kline.py`（腾讯公开前复权）或兼容的 raw JSON；禁止凭记忆给数、禁止另造未登记爬虫。
2. 最大回撤、上行占比、日均斜率、量能倍数、形态距离 → 用本 skill 公式 / `scripts/scan_shape.py`，禁止目测。
3. 一只股票一个 `--out-dir`（同目录会互相覆盖）。
4. 窗口内任一天停牌或成交量=0 → 剔除。
5. 输出不得含买卖 / 仓位 / 「该买」类语句。

## 默认口径

| 项 | 值 |
|---|---|
| 模式 | **`short`**：最近 5~10 交易日都试，取最高分 |
| 切换 | `--mode samelen`：对每个样本长度 Dᵢ 取最近 Dᵢ 日 |
| 门禁 | `ret>0`；`up≥0.431`；`slope∈[0.527,4.508]` |
| 分档 | MDD≤8%→A；8%<MDD≤15%→B；>15%剔除 |
| 打分 | 同档加权距离；`score=100/(1+d)` |
| 输出 | Top 30；**按窗口长度分组**；附归因分布 |

样本与权重见 `scripts/profiles.json`（603980 区间 = 2026-08-26~2026-10-13）。

## 工作流（单独安装也可跑）

以下路径相对于本 skill 目录。先准备 `codes.txt`（每行 `代码,名称`，主板非 ST）。

### 1) 取 K 线（内置腾讯源）

```bash
# 单只
python scripts/fetch_kline.py --symbol 600573 --bars 90 --out-dir ./data/kline-600573

# 批量（默认 3 并发）
python scripts/fetch_batch.py --codes-file codes.txt --out-root ./data --bars 90 --workers 3
```

`samelen` 的 D_max=72，建议 `--bars 90`。失败退出码非 0 → 记缺口，不要编数。

### 2) 扫描

```bash
python scripts/scan_shape.py \
  --mode short \
  --codes-file codes.txt \
  --out-dir ./out \
  --kline-root ./data/kline-{code}

python scripts/scan_shape.py --mode samelen --codes-file codes.txt --out-dir ./out-samelen --kline-root ./data/kline-{code}
```

产物：`result.md` / `result.csv` / `README.json`。

### 3) 候选池说明

本 skill **不内置全市场名单抓取**。`codes.txt` 可由使用者提供，或用 `scripts/build_universe.py` 从已有代码表过滤主板并剔除 ST。过滤规则：保留 `600/601/603/605`、`000/001/002/003`；剔除创业板/科创板/北交所/名称含 ST。

## 输出与自检

- `result.md`：模式、数据末日、命中数、A/B、归因、Top 表、按窗口长度分组。
- `short` 下 B=0 常见（窗口太短难出深回撤）→ 写明；`samelen` 某一档 Top 为 0 → **停下来报告**。
- 禁止暗示「能识别即将启动」——见 [reference.md](reference.md)。
