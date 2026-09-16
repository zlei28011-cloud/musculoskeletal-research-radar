from __future__ import annotations

from .models import Article, Score


CLINICAL_TERMS = {"patient", "clinical", "fracture", "mortality", "risk", "diagnosis", "therapy", "treatment", "cohort", "trial"}
MECHANISM_TERMS = {"mechanism", "pathway", "causal", "perturbation", "knockout", "cell-cell", "signaling", "receptor", "senescence"}
FEASIBLE_TERMS = {"nhanes", "uk biobank", "biobank", "ct", "dxa", "imaging", "cohort", "proteomics", "metabolomics"}
PARADIGM_TERMS = {"foundation model", "digital twin", "spatial", "single-cell", "longitudinal", "multi-organ", "perturbation", "clock", "atlas", "resource"}


def _hits(text: str, terms: set[str] | list[str]) -> list[str]:
    low = text.casefold()
    return [term for term in terms if term.casefold() in low]


def classify(article: Article | dict, config: dict) -> tuple[str, list[str]] | None:
    title = article.title if isinstance(article, Article) else article.get("title", "")
    abstract = article.abstract if isinstance(article, Article) else article.get("abstract", "")
    journal = article.journal if isinstance(article, Article) else article.get("journal", "")
    text = f"{title} {abstract}"
    direct = _hits(text, config["track_a_terms"])
    frontier = _hits(text, config["track_b_terms"])
    journal_match = journal.casefold() in {j.casefold() for j in config["frontier_journals"]}
    if direct:
        return "A", direct
    if frontier and (journal_match or (article.source if isinstance(article, Article) else article.get("source")) in {"biorxiv", "medrxiv"}):
        return "B", frontier
    return None


def calculate(article: dict, track: str, hits: list[str], config: dict, competition_count: int = 0) -> Score:
    text = f"{article.get('title', '')} {article.get('abstract', '')}".casefold()
    paradigm_hits = _hits(text, PARADIGM_TERMS)
    clinical_hits = _hits(text, CLINICAL_TERMS)
    mechanism_hits = _hits(text, MECHANISM_TERMS)
    feasible_hits = _hits(text, FEASIBLE_TERMS)
    direct_targets = _hits(text, config["transfer_targets"])

    components = {
        "paradigm_novelty": min(100, 38 + len(set(paradigm_hits)) * 13 + (12 if track == "B" else 0)),
        "musculoskeletal_gap": max(20, min(100, 92 - len(set(direct_targets)) * 14 if track == "B" else 58)),
        "clinical_significance": min(100, 35 + len(set(clinical_hits)) * 10),
        "data_feasibility": min(100, 42 + len(set(feasible_hits)) * 11),
        "mechanistic_depth": min(100, 32 + len(set(mechanism_hits)) * 12),
        "competition_urgency": min(100, 42 + competition_count * 13),
    }
    weights = config["score_weights"]
    total = round(sum(components[key] * float(weights[key]) for key in components))
    reasons = {
        "paradigm_novelty": f"识别到 {len(set(paradigm_hits))} 个范式信号：{', '.join(paradigm_hits[:4]) or '以问题创新为主'}。",
        "musculoskeletal_gap": "骨/肌直接命中较少，迁移空间较大。" if track == "B" else "研究对象已在肌骨领域，重点看是否形成方法学增量。",
        "clinical_significance": f"临床相关线索 {len(set(clinical_hits))} 个。",
        "data_feasibility": f"可获得数据/技术线索 {len(set(feasible_hits))} 个。",
        "mechanistic_depth": f"机制或因果线索 {len(set(mechanism_hits))} 个。",
        "competition_urgency": f"当前二次检索返回 {competition_count} 条潜在竞争记录。",
    }
    return Score(total=total, components=components, reasons=reasons)

