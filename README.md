# TrendingStockSkills

可安装的 Agent Skill 仓库。当前包含：

| Skill | 说明 |
|---|---|
| [`skills/shape-similarity`](skills/shape-similarity/) | A 股主板走势形态相似筛选（默认 short，可切 samelen） |

## 目录结构（兼容 c-skills / ChatSkill）

```
README.md
skills/
  shape-similarity/
    SKILL.md
    reference.md
    scripts/
      fetch_kline.py      # 腾讯前复权日 K（标准库，独立可用）
      fetch_batch.py      # 批量取数
      scan_shape.py       # 形态打分
      build_universe.py   # 主板候选池过滤
      profiles.json       # 样本档案
```

用 GitHub Skill 安装工具时，请指向本仓库；工具应识别 `skills/<name>/`。若工具不支持该结构，手动复制 `skills/shape-similarity` 到 Agent 的 skills 目录即可。

## 数据前提

形态扫描**依赖真实日 K**。本仓库已内置腾讯公开前复权拉取，**不依赖** Vibe-Research：

```bash
cd skills/shape-similarity
# codes.txt 每行: 代码,名称
python scripts/fetch_batch.py --codes-file codes.txt --out-root ./data --bars 90
python scripts/scan_shape.py --codes-file codes.txt --out-dir ./out --kline-root ./data/kline-{code}
```

没有成功落盘的 K 线时不要跑扫描，也不要用模型记忆填数。

## 许可与免责

仅供研究复现，不构成证券投资建议。使用公开行情请遵守数据源服务条款。
