---
name: shape-similarity
description: A 股主板「走势形态相似」筛选。给定已核对的样本档案,在候选池上按 short(默认,近 5~10 日)或 samelen(等长窗口)算归一化形态距离并输出 Top 30。当用户要形态相似/走势像某几只票/短窗口复筛/等长窗口复筛时使用;不给买卖建议。取数必须走 data-access 登记脚本。
---

# 走势形态相似筛选（shape-similarity）

形态相似 ≠ 投资建议。结论只能来自本轮真实取数与脚本打分；缺数据就写缺口。

## 何时用

- 用户给了（或沿用本 skill 内置的）样本区间，要在沪深**主板**找「形态像」的票
- 需要在 **`short`（默认）** 与 **`samelen`** 之间切换口径
- 不要用于：估值/财报研究、问财条件选股、暗示「即将启动/埋伏」

详细口径对照与样本表见 [reference.md](reference.md)。

## 硬约束

1. 行情 / 名单 / ST / 交易日只能来自本仓库 `.agents/skills/data-access/scripts/`；禁止凭记忆给数、禁止自造爬虫。
2. 最大回撤、上行占比、日均斜率、量能倍数、形态距离：`calc/` 无契约 → 必须用本 skill 公式 / `scripts/scan_shape.py`，禁止目测。
3. 一只股票一个 `--out-dir`（`fetch_kline` 文件名固定，同目录会互相覆盖）。
4. 窗口内任一天停牌或成交量=0 → 剔除。
5. 输出不得含买卖 / 仓位 / 「该买」类语句。

## 默认口径

| 项 | 值 |
|---|---|
| 模式 | **`short`**：最近 5~10 交易日都试，取最高分 |
| 切换 | `--mode samelen`：对每个样本长度 Dᵢ 取最近 Dᵢ 日 |
| 门禁 | `ret>0`；`up≥0.431`；`slope∈[0.527,4.508]` |
| 分档 | MDD≤8%→A；8%<MDD≤15%→B；>15%剔除 |
| 打分 | 同档加权距离；`score=100/(1+d)`；σ 用该档全档案极差÷2（有下限） |
| 输出 | Top 30；**按窗口长度分组**；附归因分布 |

权重与 σ 下限见 `scripts/profiles.json`。样本数字以该文件为准（603980 区间已收窄为 2026-08-26~2026-10-13）。

## 工作流

### 1) 候选池

```bash
# 通达信盘后包(全市场名单唯一可靠来源;codes 空时注册表只给指数→需直接调上游全量)
python .agents/skills/data-access/scripts/fetch_endpoint.py \
  --endpoint tdx_daily_package --out-dir .local/runs/shape-scan/universe

python .agents/skills/data-access/scripts/fetch_endpoint.py \
  --endpoint st_stock_list --out-dir .local/runs/shape-scan/st

python .agents/skills/shape-similarity/scripts/build_universe.py \
  --codes <主板代码表或 code,name 文本> \
  --st-json .local/runs/shape-scan/st/fetch/st_stock_list.json \
  --out .local/runs/shape-scan/codes.txt
```

过滤：保留 `600/601/603/605`、`000/001/002/003`；剔除创业板/科创板/北交所/ST（名单 + 名称含 ST）。量级约 3000 只。

### 2) 取 K 线

```bash
python .agents/skills/data-access/scripts/fetch_kline.py \
  --symbol <6位> --bars 90 --out-dir .local/runs/shape-scan/kline-<代码>
```

`samelen` 的 D_max=72，建议 `--bars 90`。可 3 并发；必须一只一个目录。非 0 退出码如实记缺口。

### 3) 扫描

```bash
# 默认 short
python .agents/skills/shape-similarity/scripts/scan_shape.py \
  --codes-file .local/runs/shape-scan/codes.txt \
  --out-dir .local/runs/shape-scan-<YYYYMMDD> \
  --kline-root .local/runs/shape-scan/kline-{code}

# 等长窗口
python .agents/skills/shape-similarity/scripts/scan_shape.py \
  --mode samelen \
  --codes-file .local/runs/shape-scan/codes.txt \
  --out-dir .local/runs/shape-scan-<YYYYMMDD>-samelen \
  --kline-root .local/runs/shape-scan/kline-{code}
```

也可指向已有缓存：`--kline-root .local/runs/latest-{code}`（可重复传多次）。

产物：`result.md` / `result.csv` / `README.json`。

## 输出要求

`result.md` 至少含：模式、数据末日、候选/命中/Top 数、A/B 档数、归因（下跌/上行不足/斜率越界/无数据等）、Top 表、按窗口长度分组。

一句话说明写「像在哪 / 不像在哪」（数字对比），禁止空形容词。

## 完工自检

1. 候选池是否约主板三千量级？差太多先查过滤。
2. `short` 下 B=0 常见 → 在结论里写明窗口限制；`samelen` 下某一档 Top 为 0 → **停下来报告**，不交付残缺榜。
3. 正对照：区间终点紧邻最新交易日的样本，其「最近窗口」才可能排前列；区间早已结束的样本未命中属正常。
4. 禁止暗示「能识别即将启动」——见 [reference.md](reference.md) §2。

## 独立使用

本目录可整夹作为 GitHub Skill 仓库。取数仍依赖 [Vibe-Research](https://github.com/simonlin1212/Vibe-Research) 的 `data-access`，或自备等价前复权日 K raw JSON（腾讯 `qfqday`）。安装：复制到 Agent 的 skills 目录并命名为 `shape-similarity`。
