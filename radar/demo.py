from __future__ import annotations

from datetime import date, timedelta

from .cards import build_card
from .db import Database
from .exporter import export_site
from .models import Article
from .reports import write_reports
from .settings import Settings


DEMO = [
    Article(
        source="pubmed", title="A spatial single-cell atlas of human skeletal aging reveals osteocyte–immune niches",
        abstract="Spatial transcriptomics and single-cell profiling map age-associated osteocyte and immune cell states. The study identifies cell-cell communication programs linked to cortical porosity and fracture risk.",
        journal="Nature Aging", published_date=date.today().isoformat(), doi="10.0000/demo.001", pmid="99900001",
        url="https://pubmed.ncbi.nlm.nih.gov/99900001/", status="peer-reviewed", authors=["Demo Research Consortium"],
    ),
    Article(
        source="biorxiv", title="A multimodal foundation model for longitudinal multi-organ aging trajectories",
        abstract="A foundation model integrates imaging, proteomics and metabolomics across a longitudinal biobank. The model predicts organ-specific aging trajectories and supports perturbation analysis.",
        journal="bioRxiv", published_date=(date.today() - timedelta(days=1)).isoformat(), doi="10.1101/2026.09.15.000001",
        url="https://www.biorxiv.org/", status="preprint", authors=["Example Team"],
    ),
    Article(
        source="crossref", title="Proteomic signatures of frailty and sarcopenia preceding incident fracture",
        abstract="Longitudinal proteomics in a clinical cohort identifies pathways associated with frailty, sarcopenia and fracture. Findings are validated with CT muscle measures and DXA.",
        journal="Aging Cell", published_date=(date.today() - timedelta(days=2)).isoformat(), doi="10.0000/demo.003",
        url="https://doi.org/10.0000/demo.003", status="peer-reviewed", authors=["Example Clinical Network"],
    ),
]


def seed(settings: Settings) -> int:
    db = Database(settings.db_path)
    run_id = db.start_run("demo")
    cards = []
    for index, item in enumerate(DEMO):
        article_id = db.upsert_article(item)
        track = "A" if index in {0, 2} else "B"
        hits = ["spatial transcriptomics", "single-cell aging"] if index == 0 else (["foundation model", "longitudinal trajectory"] if index == 1 else ["sarcopenia", "fracture"])
        competition = [] if index == 1 else [{"title": "Related proof-of-concept study in bone", "journal": "Bone", "date": "2025", "url": "https://pubmed.ncbi.nlm.nih.gov/", "pmid": ""}]
        card = build_card(article_id, db.article(article_id), track, hits, settings.config, competition)
        db.save_card(card)
        cards.append(article_id)
    db.conn.commit()
    items = db.recent_cards(days=30)
    export_site(items, settings.output_dir)
    write_reports(items, settings.output_dir, settings.config, weekly=True)
    stats = {"demo": len(cards)}
    db.snapshot(run_id, date.today().isoformat(), cards, stats)
    db.finish_run(run_id, "success", stats, [])
    db.close()
    return len(cards)

