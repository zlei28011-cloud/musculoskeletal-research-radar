from __future__ import annotations

import html
import json
import os
import re
import smtplib
from collections import Counter
from datetime import date
from email.message import EmailMessage
from pathlib import Path


def _plain_zh_summary(value: str) -> str:
    """Keep the Chinese interpretation separate from the original abstract evidence."""
    return re.split(r"\s*(?:摘要证据|摘要补充)：", value or "", maxsplit=1)[0].strip()


def _abstract_evidence(abstract: str, limit: int = 3) -> list[str]:
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", abstract or "") if x.strip()]
    return sentences[:limit]


def _objective_zh(title: str) -> str:
    lowered = title.casefold()
    if any(term in lowered for term in ["atlas", "mapping", "spatial", "single-cell", "single cell"]):
        return "描绘研究对象在细胞、空间或组织层面的组成与变化，并寻找具有解释力的生物学模式。"
    if any(term in lowered for term in ["model", "clock", "predict", "prediction"]):
        return "构建或验证一种模型，用于表征生物学状态、预测结局或提高研究测量能力。"
    if any(term in lowered for term in ["association", "associated", "correlation", "risk"]):
        return "检验目标因素与疾病、衰老或临床结局之间的关联，并评估其潜在意义。"
    if any(term in lowered for term in ["reveal", "identify", "discover", "mechanism"]):
        return "识别关键现象、标志物或机制线索，并解释它们与研究结局之间的关系。"
    return "回答题目所指向的核心研究问题，并评估其方法学、机制或临床价值。"


def _structured_digest(card: dict) -> dict[str, object]:
    summaries = card.get("summary_zh") or []
    background = _plain_zh_summary(summaries[0]) if summaries else "该研究聚焦题目所述的疾病、衰老或方法学问题。"
    method_summary = _plain_zh_summary(summaries[1]) if len(summaries) > 1 else "摘要未提供足够的方法细节。"
    interpretation = _plain_zh_summary(summaries[2]) if len(summaries) > 2 else "需要结合全文判断其可迁移价值。"
    paradigm = (card.get("new_paradigm") or "未识别出明确的方法标签").strip()
    data_needs = "、".join(card.get("data_needs") or []) or "需阅读全文核对具体数据与样本"
    link = (card.get("musculoskeletal_link") or "需人工判断与骨、肌及骨折研究的具体联系。").strip()
    evidence = _abstract_evidence(card.get("abstract") or "")
    return {
        "background": background,
        "objective": _objective_zh(card.get("title") or ""),
        "methods": f"{method_summary} 方法/范式标签：{paradigm}。涉及的数据或样本：{data_needs}。",
        "findings": "摘要报告了与研究目标相关的主要结果。为避免误译效应方向、数值或因果关系，本邮件不补写摘要中没有明确支持的结论；可核对下方英文原句。",
        "interpretation": f"{interpretation} {link}",
        "limitations": "本卡基于题录与摘要自动生成，尚未核对全文中的样本量、效应值、亚组分析、偏倚控制及作者原始局限。",
        "evidence": evidence,
    }


def _card_html(card: dict) -> str:
    title = html.escape(card["title"])
    url = html.escape(card.get("url") or "#", quote=True)
    track = html.escape(card["track"])
    score = int(card["score_total"])
    digest = _structured_digest(card)
    evidence = "".join(f"<p>{html.escape(x)}</p>" for x in digest["evidence"])
    evidence_block = evidence or "<p>当前记录没有可用摘要，请点击原始链接核对全文。</p>"
    journal = html.escape(card.get("journal") or "期刊待核对")
    published = html.escape(card.get("published_at") or "日期待核对")
    identifier = card.get("doi") or card.get("pmid") or "标识符待核对"
    return f"""<article>
    <div class='meta'>TRACK {track} · OPPORTUNITY SCORE {score}/100 · {html.escape(card['novelty_status'])}</div>
    <div class='badge'>摘要级解读 / Abstract-level review</div>
    <h3><a href='{url}'>{title}</a></h3>
    <p class='source'><b>期刊 / Journal：</b>{journal}　<b>日期 / Date：</b>{published}<br><b>DOI/PMID：</b>{html.escape(str(identifier))}</p>
    <div class='digest'>
      <h4>研究背景 / Background</h4><p>{html.escape(str(digest['background']))}</p>
      <h4>研究目的 / Objective</h4><p>{html.escape(str(digest['objective']))}</p>
      <h4>方法与数据 / Methods &amp; Data</h4><p>{html.escape(str(digest['methods']))}</p>
      <h4>主要发现 / Key Findings</h4><p>{html.escape(str(digest['findings']))}</p>
      <h4>结论与肌骨启示 / Interpretation for Musculoskeletal Research</h4><p>{html.escape(str(digest['interpretation']))}</p>
      <h4>局限 / Limitations</h4><p>{html.escape(str(digest['limitations']))}</p>
      <h4>英文原文证据 / Original Evidence</h4><blockquote>{evidence_block}</blockquote>
    </div>
    <p><a class='source-link' href='{url}'>查看原始记录 / Open source record →</a></p>
    </article>"""


def daily_email(cards: list[dict], threshold: int = 68, must_read: int = 82) -> str:
    high = [x for x in cards if x["score_total"] >= threshold]
    must = [x for x in high if x["score_total"] >= must_read][:3]
    new_play = [x for x in high if x["track"] == "B" and x not in must][:5]
    alerts = [x for x in high if x["competition"]][:3]
    resources = [x for x in high if any(t in (x["title"] + " " + x["new_paradigm"]).casefold() for t in ["resource", "atlas", "database", "data release"])][:3]
    if not high:
        content = "<div class='empty'><b>今日未发现高优先级科研机会</b><br><span>No high-priority research opportunities found today.</span></div>"
    else:
        def section(label: str, items: list[dict]) -> str:
            return f"<h2>{label}</h2>" + ("".join(_card_html(x) for x in items) if items else "<p class='none'>本栏今日无新增 / No new items in this section.</p>")
        content = section("1. 今日必看 / Must Read", must) + section("2. 新玩法 / New Paradigms", new_play) + section("3. 撞车/竞争预警 / Competition Alerts", alerts) + section("4. 新数据库/资源 / Data & Resources", resources)
    return f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'><style>
    body{{font:16px/1.65 system-ui;color:#13233a;background:#eef3f7;margin:0;padding:24px}}main{{max-width:780px;margin:auto;background:white;padding:32px}}
    h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:18px;border-top:1px solid #d9e2ea;padding-top:20px;margin-top:28px}}h3{{font-size:17px;margin:6px 0}}a{{color:#075c66}}
    article{{padding:18px 0 24px;border-bottom:1px solid #e7edf2}}.meta{{font-size:12px;color:#6a7a8a;text-transform:uppercase}}.badge{{display:inline-block;margin:7px 0 3px;padding:2px 8px;border-radius:999px;background:#e8f5f3;color:#075c66;font-size:12px}}
    .source{{font-size:13px;color:#526273}}.digest h4{{font-size:14px;margin:15px 0 3px;color:#075c66}}.digest p{{margin:0}}blockquote{{margin:6px 0;padding:8px 14px;border-left:3px solid #a7c9c5;background:#f6f9f9;color:#435363;font-size:14px}}blockquote p{{margin:5px 0!important}}
    .source-link{{font-weight:650}}.empty{{padding:38px;text-align:center;background:#f4f7f9;margin-top:24px}}.empty span,.none{{color:#6a7a8a}}.intro{{padding:12px 14px;background:#f4f7f9;border-radius:6px}}
    @media(max-width:600px){{body{{padding:0}}main{{padding:20px}}h1{{font-size:21px}}}}</style><main><h1>肌骨科研机会雷达 / Musculoskeletal Research Radar</h1><p>{date.today().isoformat()} · Daily Radar</p><p class='intro'>中文速读在前，英文原始证据在后。内容为题录与摘要级自动解读，重要决策请回到原文核对。<br><span>Chinese briefing first, followed by the original English evidence. This is an abstract-level automated review.</span></p>{content}</main></html>"""


def weekly_brief(cards: list[dict]) -> tuple[str, dict]:
    terms = Counter()
    for card in cards:
        haystack = (card["title"] + " " + card["new_paradigm"]).casefold()
        for term in ["spatial", "single-cell", "foundation model", "longitudinal", "proteomics", "metabolomics", "multimodal", "cell-cell", "perturbation", "atlas"]:
            if term in haystack:
                terms[term] += 1
    hot = [{"term": k, "count": v} for k, v in terms.most_common(6)]
    transfer = [x for x in cards if x["track"] == "B"][:5]
    direct = [x for x in cards if x["track"] == "A"][:5]
    candidates = sorted(cards, key=lambda x: x["score_total"], reverse=True)[:6]
    data = {"generated_at": date.today().isoformat(), "hot_paradigms": hot, "transfer": transfer, "direct": direct, "candidates": candidates}
    hot_text = "、".join(f"{x['term']}（{x['count']}篇）" for x in hot) or "本周尚无明确聚集信号"
    transfer_lines = [f"- {x['title']}（{x['journal']}，{x['score_total']}分）" for x in transfer] or ["- 暂无高置信度信号"]
    direct_lines = [f"- {x['title']}：{x['novelty_status']}" for x in direct] or ["- 本周直接研究样本不足，需延长观察窗口"]
    body = [
        f"# Weekly Frontier Brief · {date.today().isoformat()}",
        "", "## 本周明显升温的研究范式", "", hot_text,
        "", "## 正在向临床迁移的新方法", "",
        *transfer_lines,
        "", "## 骨/肌领域目前做到哪一步", "",
        *direct_lines,
        "", "## 值得人工深查的候选机会", "",
        *[f"- [{x['title']}]({x['url']}) — {x['score_total']}分；{x['new_paradigm']}" for x in candidates],
        "", "> novelty status 表示当前自动检索结果，不等同于系统性综述结论。",
    ]
    return "\n".join(body), data


def weekly_email(data: dict) -> str:
    hot = "".join(f"<li><b>{html.escape(x['term'])}</b>：{x['count']} 篇卡片命中</li>" for x in data["hot_paradigms"]) or "<li>本周尚无明确聚集信号</li>"
    transfer = "".join(_card_html(x) for x in data["transfer"]) or "<p class='none'>暂无高置信度跨学科迁移信号</p>"
    direct = "".join(f"<li>{html.escape(x['title'])} — {html.escape(x['novelty_status'])}</li>" for x in data["direct"]) or "<li>本周直接研究样本不足，需延长观察窗口</li>"
    candidates = "".join(_card_html(x) for x in data["candidates"]) or "<p class='none'>本周无候选需要升级人工深查</p>"
    return f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'><style>
    body{{font:16px/1.65 system-ui;color:#13233a;background:#eef3f7;margin:0;padding:24px}}main{{max-width:780px;margin:auto;background:white;padding:32px}}
    h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:18px;border-top:1px solid #d9e2ea;padding-top:20px;margin-top:28px}}h3{{font-size:17px;margin:6px 0}}a{{color:#075c66}}
    article{{padding:18px 0 24px;border-bottom:1px solid #e7edf2}}.meta{{font-size:12px;color:#6a7a8a;text-transform:uppercase}}.badge{{display:inline-block;margin:7px 0 3px;padding:2px 8px;border-radius:999px;background:#e8f5f3;color:#075c66;font-size:12px}}
    .source{{font-size:13px;color:#526273}}.digest h4{{font-size:14px;margin:15px 0 3px;color:#075c66}}.digest p{{margin:0}}blockquote{{margin:6px 0;padding:8px 14px;border-left:3px solid #a7c9c5;background:#f6f9f9;color:#435363;font-size:14px}}blockquote p{{margin:5px 0!important}}.source-link{{font-weight:650}}.none{{color:#6a7a8a}}.intro{{padding:12px 14px;background:#f4f7f9;border-radius:6px}}ol,ul{{padding-left:22px}}
    @media(max-width:600px){{body{{padding:0}}main{{padding:20px}}h1{{font-size:21px}}}}</style>
    <main><h1>每周前沿简报 / Weekly Frontier Brief</h1><p>{html.escape(data['generated_at'])} · 肌骨科研机会雷达</p><p class='intro'>中文总结在前，英文原始证据在后；文章卡片为摘要级自动解读。<br>Chinese summary first, followed by the original English evidence.</p>
    <h2>1. 本周明显升温的研究范式 / Hot Paradigms</h2><ul>{hot}</ul>
    <h2>2. 正在从其他学科向临床迁移的方法 / Translational Methods</h2>{transfer}
    <h2>3. 骨 / 肌领域目前做到哪一步 / Musculoskeletal Progress</h2><ul>{direct}</ul>
    <h2>4. 值得继续人工深查的候选机会 / Deep-dive Candidates</h2>{candidates}
    <p class='none'>novelty status 仅代表当前自动检索结果，不等同于系统性综述结论。</p></main></html>"""


def write_reports(cards: list[dict], output: Path, config: dict, weekly: bool = False) -> dict[str, Path]:
    report_dir = output / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    daily_path = report_dir / "daily.html"
    daily_path.write_text(daily_email(cards, config["high_value_threshold"], config["must_read_threshold"]), encoding="utf-8")
    paths = {"daily": daily_path}
    if weekly:
        markdown, data = weekly_brief(cards)
        md_path = report_dir / "weekly.md"
        json_path = report_dir / "weekly.json"
        html_path = report_dir / "weekly.html"
        md_path.write_text(markdown, encoding="utf-8")
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        html_path.write_text(weekly_email(data), encoding="utf-8")
        paths.update({"weekly_markdown": md_path, "weekly_json": json_path, "weekly_html": html_path})
    return paths


def send_email(subject: str, html_body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    recipients = [x.strip() for x in os.getenv("EMAIL_TO", "").split(",") if x.strip()]
    if not host or not recipients:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER")
    msg["To"] = ", ".join(recipients)
    msg.set_content("请使用支持 HTML 的邮件客户端查看本期肌骨科研机会雷达。")
    msg.add_alternative(html_body, subtype="html")
    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = os.getenv("SMTP_USE_TLS", "true").casefold() == "true"
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        user, password = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
        if user and password:
            smtp.login(user, password)
        smtp.send_message(msg)
    return True
