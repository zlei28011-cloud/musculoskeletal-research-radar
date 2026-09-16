# 架构与数据流程

## 数据流程

1. GitHub Actions 触发日任务，按 `lookback_days` 形成日期窗口。
2. 四个官方 API 适配器独立采集元数据；失败会指数退避并记录来源级错误，其他来源继续运行。
3. 记录统一为 `Article`，规范化 DOI 与标题，以 DOI → PMID → 规范化标题的顺序去重。
4. 规则分类器把肌骨关键词命中的记录送入 Track A；把前沿方法词且满足重点期刊或预印本条件的记录送入 Track B。
5. 先计算初始分，仅对排名靠前的有限候选执行 PubMed 二次检索；检索式会保留在卡片和 evidence 表中。
6. 生成 Opportunity Card、分项评分和受限 novelty status；标题完全一致的预印本与正式论文建立关联。
7. 写入 SQLite 与 `daily_snapshots`，导出最近 30 天的 `dist/data.json`。
8. 生成每日邮件 HTML；周任务额外聚合趋势并生成 Weekly Frontier Brief。

## 关键设计决定

- API 适配器：`urllib` + 指数退避，无额外依赖。
- PubMed：无 key 时最多约 3 requests/s；有 key 时约 8 requests/s，低于官方 10 requests/s 上限。
- Crossref：polite pool + 约 9 requests/s 上限。
- bioRxiv/medRxiv：共用官方 API，约 1 request/s；按官方 30 条分页持续推进 cursor。
- SQLite 索引只覆盖 DOI、PMID、标题键、日期与卡片分数这些实际查询路径。
- 静态站不直连 SQLite，而是读取去敏后的 JSON 导出；SQLite 仍是历史事实源。

## 降级策略

- 单个 API 失败：运行标记为 `partial`，保留其他来源结果。
- 二次检索失败：novelty status 为 `Unresolved`，绝不推断“无人做过”。
- SMTP 未配置：仍写出 `dist/reports/daily.html`，任务成功。
- 当天无高分卡片：邮件明确显示“今日未发现高优先级科研机会”。
