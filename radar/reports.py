from __future__ import annotations

import html
import json
import os
import smtplib
from collections import Counter
from datetime import date
from email.message import EmailMessage
from pathlib import Path


def _card_html(card: dict) -> str:
    title = html.escape(card["title"])
    url = html.escape(card.get("url") or "#", quote=True)
    track = html.escape(card["track"])
    score = int(card["score_total"])
    summary = "".join(f"<li>{html.escape(x)}</li>" for x in card["summary_zh"])
    return f"<article><div class='meta'>TRACK {track} · {score}/100 · {html.escape(card['novelty_status'])}</div><h3><a href='{url}'>{title}</a></h3><ol>{summary}</ol></article>"


def daily_email(cards: list[dict], threshold: int = 68, must_read: int = 82) -> str:
    high = [x for x in cards if x["score_total"] >= threshold]
    must = [x for x in high if x["score_total"] >= must_read][:3]
    new_play = [x for x in high if x["track"] == "B" and x not in must][:5]
    alerts = [x for x in high if x["competition"]][:3]
    resources = [x for x in high if any(t in (x["title"] + " " + x["new_paradigm"]).casefold() for t in ["resource", "atlas", "database", "data release"])][:3]
    if not high:
        content = "<div class='empty'>今日未发现高优先级科研机会</div>"
    else:
        def section(label: str, items: list[dict]) -> str:
            return f"<h2>{label}</h2>" + ("".join(_card_html(x) for x in items) if items else "<p class='none'>本栏今日无新增</p>")
        content = section("1. 今日必看", must) + section("2. 新玩法", new_play) + section("3. 撞车/竞争预警", alerts) + section("4. 新数据库/资源", resources)
    return f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'><style>
    body{{font:16px/1.65 system-ui;color:#13233a;background:#eef3f7;margin:0;padding:24px}}main{{max-width:760px;margin:auto;background:white;padding:32px}}
    h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:18px;border-top:1px solid #d9e2ea;padding-top:20px;margin-top:28px}}h3{{font-size:17px;margin:6px 0}}a{{color:#075c66}}
    article{{padding:14px 0}}.meta{{font-size:12px;color:#6a7a8a;text-transform:uppercase}}.empty{{padding:38px;text-align:center;background:#f4f7f9;margin-top:24px}}
    .none{{color:#6a7a8a}}ol{{padding-left:22px}}</style><main><h1>肌骨科研机会雷达</h1><p>{date.today().isoformat()} · Daily Radar</p>{content}</main></html>"""


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
    body{{font:16px/1.65 system-ui;color:#13233a;background:#eef3f7;margin:0;padding:24px}}main{{max-width:760px;margin:auto;background:white;padding:32px}}
    h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:18px;border-top:1px solid #d9e2ea;padding-top:20px;margin-top:28px}}h3{{font-size:17px;margin:6px 0}}a{{color:#075c66}}
    article{{padding:14px 0}}.meta{{font-size:12px;color:#6a7a8a;text-transform:uppercase}}.none{{color:#6a7a8a}}ol,ul{{padding-left:22px}}</style>
    <main><h1>Weekly Frontier Brief</h1><p>{html.escape(data['generated_at'])} · 肌骨科研机会雷达</p>
    <h2>1. 本周明显升温的研究范式</h2><ul>{hot}</ul>
    <h2>2. 正在从其他学科向临床迁移的方法</h2>{transfer}
    <h2>3. 骨 / 肌领域目前做到哪一步</h2><ul>{direct}</ul>
    <h2>4. 值得继续人工深查的候选机会</h2>{candidates}
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
