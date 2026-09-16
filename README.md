# Musculoskeletal Research Radar / 肌骨科研机会雷达

一个面向骨科、骨质疏松和肌少症研究者的轻量科研监测 MVP。它不是“论文越多越好”的 RSS 聚合器，而是把新论文转成可核查的 **Opportunity Card**，重点寻找新范式、新方法、新数据资源和跨学科迁移机会。

## 项目架构

系统保持为一个 Python 进程和一个静态网页：

```text
PubMed / Crossref / bioRxiv / medRxiv
                 │
                 ▼
     API 适配器（限速、重试、日志）
                 │
                 ▼
  规范化 → DOI/PMID/标题去重 → 预印本关联
                 │
                 ▼
        SQLite（文章、证据、每日快照）
                 │
                 ▼
 双轨分类 → 二次检索 → Opportunity Score
                 │
         ┌───────┴────────┐
         ▼                ▼
  静态 data.json/网页    日报 / 周报 / SMTP
```

- Track A：肌骨直接研究。
- Track B：优先期刊与 bioRxiv/medRxiv 中的前沿迁移信号。
- 数据库：本地 SQLite，保留文章、卡片、证据检索与每日快照。
- 前端：无框架的 HTML/CSS/JavaScript，可直接部署到 GitHub Pages 或 Netlify。
- 自动化：GitHub Actions 每日运行；每周一额外生成 Weekly Frontier Brief。

## 文件结构

```text
.
├─ radar/                 # 采集、数据库、评分、卡片、报告、CLI
├─ config/radar.json      # 双轨关键词、期刊、阈值与权重
├─ data/radar.db          # 运行后生成的 SQLite 历史库
├─ dist/                  # 静态网站与日报/周报产物
├─ tests/                 # 标准库 unittest
├─ docs/                  # 架构与开发计划
├─ .github/workflows/     # 每日/每周定时任务
├─ .env.example           # 环境变量清单（不含密钥）
└─ netlify.toml           # Netlify 静态部署配置
```

## 快速开始

要求 Python 3.11+，第一版无第三方依赖。

```bash
# 先生成离线演示数据与网页
python -m radar demo

# 真实采集；缺少 SMTP 配置时只写报告、不发邮件
python -m radar run --skip-email

# 同时生成 Weekly Frontier Brief
python -m radar run --weekly --skip-email
```

然后用任意静态服务器打开 `dist/`，例如：

```bash
python -m http.server 8000 -d dist
```

访问 `http://localhost:8000`。请勿直接双击 HTML；浏览器会限制本地 `fetch(data.json)`。

## 配置与密钥

复制 `.env.example` 中的变量到本地环境或 GitHub Secrets。建议至少设置：

- `NCBI_EMAIL`：必填，NCBI E-utilities 使用规范要求的开发者联系邮箱；
- `NCBI_API_KEY`：可选，提高 PubMed 限额；
- `CROSSREF_MAILTO`：进入 Crossref polite pool；
- `SMTP_*`、`EMAIL_FROM`、`EMAIL_TO`：可选邮件发送配置。

代码不会把密钥写入数据库、网页或日志。采集只使用官方 API，不抓取付费全文，也不绕过付费墙。

## Opportunity Score

总分 0–100，由配置权重加权：范式新颖性 20%、肌骨空白度 22%、临床意义 18%、数据可行性 15%、机制深度 15%、竞争紧迫度 10%。每张卡片展示分项与理由。

评分是筛选优先级，不是论文质量或临床证据等级。`novelty status` 严格限制为：

- `Directly studied`
- `Adjacent studies exist`
- `No direct match found in current search`
- `Unresolved`

“当前检索未命中”不代表“从未有人做过”。

## 部署

- Netlify：仓库连接后会读取 `netlify.toml`，发布目录为 `dist`。
- GitHub Pages：启用 Actions 作为 Pages source，工作流会上传 `dist`。
- 定时任务产生的 `data/radar.db` 和 `dist/data.json` 会提交回仓库，因此仓库若含未公开研究想法应保持私有。

## MVP 边界

当前中文解释采用可审计的规则模板，不调用外部大模型；它适合做“发现与分流”，不替代全文阅读、系统综述或专家判断。二次竞争检索目前仅使用 PubMed，并对每天检查的候选数设上限，避免 API 浪费。
