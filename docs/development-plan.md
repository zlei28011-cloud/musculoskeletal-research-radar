# 第一版开发计划

## Phase 1 — 可运行骨架（已完成）

- Python CLI、配置、SQLite schema、离线 demo。
- 静态仪表盘的七个指定入口与移动端适配。

## Phase 2 — 四源采集（已完成）

- PubMed E-utilities、Crossref REST、bioRxiv、medRxiv。
- 重试、日志、限速、来源级失败隔离。

## Phase 3 — 机会判断（已完成）

- 双轨分类、DOI/PMID/标题去重、预印本标题关联。
- 自动二次检索词、PubMed 竞争检索、受限 novelty status。
- 0–100 Opportunity Score 分项与理由。

## Phase 4 — 交付与自动化（已完成）

- 每日邮件、Weekly Frontier Brief、历史快照。
- GitHub Actions、GitHub Pages、Netlify 配置。

## 人工验收建议

连续运行 2–4 周后再调权重与阈值。重点抽查：漏掉的真正高价值文章、误报来源、二次检索的词法质量、Track B 的迁移判断、日报长度。MVP 不建议在此之前增加数据源或模型复杂度。

