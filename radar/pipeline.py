from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from .cards import build_card, detect_methods, secondary_queries
from .db import Database
from .exporter import export_site
from .reports import send_email, write_reports
from .scoring import calculate, classify
from .settings import Settings
from .sources import CrossrefSource, PubMedSource, RxivSource, date_window

LOG = logging.getLogger(__name__)

DEMO_DOIS = {
    "10.0000/demo.001",
    "10.1101/2026.09.15.000001",
    "10.0000/demo.003",
}


@dataclass
class PipelineResult:
    run_id: int
    stats: dict
    errors: list[dict]


def run(settings: Settings, *, weekly: bool = False, skip_email: bool = False) -> PipelineResult:
    db = Database(settings.db_path)
    demo_records_removed = db.remove_articles_by_doi(DEMO_DOIS)
    run_id = db.start_run("weekly" if weekly else "daily")
    config = settings.config
    start, end = date_window(int(config["lookback_days"]))
    limit = int(config["max_results_per_source"])
    pubmed = PubMedSource(settings.ncbi_email, settings.ncbi_api_key)
    sources = {
        "pubmed": lambda: pubmed.fetch(config["track_a_terms"] + config["track_b_terms"], start, end, limit),
        "crossref": lambda: CrossrefSource(settings.crossref_mailto).fetch(
            config["track_a_terms"] + config["track_b_terms"], start, end, limit
        ),
        "biorxiv": lambda: RxivSource("biorxiv").fetch(start, end, limit),
        "medrxiv": lambda: RxivSource("medrxiv").fetch(start, end, limit),
    }
    collected = []
    errors: list[dict] = []
    source_stats: dict[str, int] = {}
    for name, loader in sources.items():
        try:
            batch = loader()
            collected.extend(batch)
            source_stats[name] = len(batch)
            LOG.info("%s: fetched %s records", name, len(batch))
        except Exception as exc:
            LOG.exception("Source failed: %s", name)
            errors.append({"source": name, "error": str(exc)})
            source_stats[name] = 0

    candidates: list[tuple[int, dict, str, list[str]]] = []
    with db.transaction():
        for item in collected:
            classified = classify(item, config)
            if not classified:
                continue
            article_id = db.upsert_article(item)
            track, hits = classified
            candidates.append((article_id, db.article(article_id), track, hits))

    provisional = []
    for article_id, article, track, hits in candidates:
        provisional.append((calculate(article, track, hits, config).total, article_id, article, track, hits))
    provisional.sort(reverse=True, key=lambda x: x[0])
    competition_limit = int(config["max_competition_checks"])
    saved_ids = []
    for rank, (_, article_id, article, track, hits) in enumerate(provisional):
        competition: list[dict] = []
        search_failed = False
        if rank < competition_limit:
            methods = detect_methods(f"{article['title']} {article['abstract']}") or hits[:2]
            queries = secondary_queries(methods, config["transfer_targets"])
            # One combined query per article keeps API usage bounded while cards retain all generated queries.
            combined = " OR ".join(f"({q})" for q in queries[:3])
            try:
                competition = pubmed.search_competition(combined, limit=5)
                db.save_evidence(article_id, combined, "pubmed", competition)
            except Exception as exc:
                search_failed = True
                errors.append({"source": "competition_pubmed", "article_id": article_id, "error": str(exc)})
        card = build_card(article_id, article, track, hits, config, competition, search_failed)
        db.save_card(card)
        saved_ids.append(article_id)
    db.conn.commit()
    linked = db.link_versions()
    cards = db.recent_cards(days=30)
    export_site(cards, settings.output_dir)
    reports = write_reports(cards, settings.output_dir, config, weekly=weekly)
    if not skip_email:
        try:
            report_key = "weekly_html" if weekly else "daily"
            body = reports[report_key].read_text(encoding="utf-8")
            subject = (
                "每周前沿简报 / Weekly Frontier Brief"
                if weekly
                else "肌骨科研机会雷达 / Musculoskeletal Research Radar"
            ) + f" · {date.today().isoformat()}"
            send_email(subject, body)
        except Exception as exc:
            LOG.exception("Email delivery failed")
            errors.append({"source": "email", "error": str(exc)})
    stats = {
        "sources": source_stats, "collected": len(collected), "candidates": len(candidates),
        "cards_saved": len(saved_ids), "version_links": linked, "errors": len(errors),
        "demo_records_removed": demo_records_removed,
    }
    db.snapshot(run_id, date.today().isoformat(), saved_ids, stats)
    db.finish_run(run_id, "partial" if errors else "success", stats, errors)
    db.close()
    return PipelineResult(run_id=run_id, stats=stats, errors=errors)

