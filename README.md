# shape-similarity

A 股主板「走势形态相似」筛选 Skill（给 Claude Code / Codex / Cursor 等 Agent 用）。

- **默认口径**：`short`（最近 5~10 个交易日）
- **可切换**：`samelen`（按样本等长窗口）
- **产物**：Top 30 + 按窗口长度分组 + 归因分布
- **不是**投资建议；不识别「即将启动 / 埋伏」

## 目录

```
SKILL.md              # Agent 入口（必读）
reference.md          # 口径对照、样本表、实测边界
scripts/
  profiles.json       # 样本档案 + 门禁/权重（v1.2）
  scan_shape.py       # 扫描打分
  build_universe.py   # 主板候选池过滤
```

## 依赖

本包**只做形态打分**，不内置爬虫。

| 需要 | 来源 |
|---|---|
| 前复权日 K | [Vibe-Research](https://github.com/simonlin1212/Vibe-Research) 的 `.agents/skills/data-access/scripts/fetch_kline.py`，或自备等价 raw JSON（腾讯 `qfqday` 形态） |
| 全市场名单 | `tdx_daily_package`（同 data-access）；注册表 `codes` 空时只给指数，全量需上游函数 |
| ST 名单 | `st_stock_list`（可能 partial） |
| Python | ≥ 3.11，标准库即可跑扫描脚本 |

把本目录放到任意 Agent 的 skills 路径（例如 `.agents/skills/shape-similarity/` 或 `~/.claude/skills/shape-similarity/`），并保证能调用到 data-access 或你自己的 K 线缓存。

## 快速用（已有 K 线缓存时）

```bash
# codes.txt 每行: 代码,名称
python scripts/scan_shape.py \
  --mode short \
  --codes-file codes.txt \
  --out-dir ./out \
  --kline-root /path/to/kline-{code}
```

等长窗口：

```bash
python scripts/scan_shape.py --mode samelen --codes-file codes.txt --out-dir ./out-samelen --kline-root /path/to/kline-{code}
```

`--kline-root` 可重复传入；`{code}` 会被替换为 6 位代码。默认也会试 VibeResearch 常见路径 `latest-{code}` / `ambush-{code}`。

## 门禁摘要

- `ret > 0`
- `up ≥ 0.431`
- `slope ∈ [0.527, 4.508]`
- MDD ≤ 8% → A 档；8% < MDD ≤ 15% → B 档；否则剔除
- 同档加权距离打分；不要求涨停；量能只进距离、不做硬过滤

细节与「为何不能暗示埋伏」见 `reference.md`。

## 许可与免责

形态筛选结果仅供研究复现，不构成任何证券投资建议。使用公开行情数据时请自行遵守数据源服务条款。
