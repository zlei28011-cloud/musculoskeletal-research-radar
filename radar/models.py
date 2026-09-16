from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Article:
    source: str
    title: str
    abstract: str = ""
    journal: str = ""
    published_date: str = ""
    doi: str = ""
    pmid: str = ""
    url: str = ""
    status: str = "peer-reviewed"
    authors: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Score:
    total: int
    components: dict[str, int]
    reasons: dict[str, str]


@dataclass(slots=True)
class OpportunityCard:
    article_id: int
    track: str
    summary_zh: list[str]
    new_paradigm: str
    why_now: str
    musculoskeletal_link: str
    secondary_queries: list[str]
    competition: list[dict[str, str]]
    unresolved_questions: list[str]
    transfer_questions: list[str]
    data_needs: list[str]
    novelty_status: str
    score: Score

