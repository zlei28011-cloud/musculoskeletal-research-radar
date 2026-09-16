from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .models import Article, OpportunityCard


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY,
  run_type TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  stats_json TEXT NOT NULL DEFAULT '{}',
  errors_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  title TEXT NOT NULL,
  title_key TEXT NOT NULL,
  abstract TEXT NOT NULL DEFAULT '',
  journal TEXT NOT NULL DEFAULT '',
  published_date TEXT NOT NULL DEFAULT '',
  doi TEXT,
  pmid TEXT,
  url TEXT NOT NULL DEFAULT '',
  publication_status TEXT NOT NULL CHECK(publication_status IN ('peer-reviewed','preprint')),
  authors_json TEXT NOT NULL DEFAULT '[]',
  raw_json TEXT NOT NULL DEFAULT '{}',
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi) WHERE doi IS NOT NULL AND doi != '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_pmid ON articles(pmid) WHERE pmid IS NOT NULL AND pmid != '';
CREATE INDEX IF NOT EXISTS idx_articles_title_key ON articles(title_key);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(published_date);
CREATE TABLE IF NOT EXISTS article_links (
  preprint_article_id INTEGER NOT NULL REFERENCES articles(id),
  published_article_id INTEGER NOT NULL REFERENCES articles(id),
  confidence REAL NOT NULL,
  reason TEXT NOT NULL,
  PRIMARY KEY(preprint_article_id, published_article_id)
);
CREATE TABLE IF NOT EXISTS cards (
  article_id INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
  track TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  new_paradigm TEXT NOT NULL,
  why_now TEXT NOT NULL,
  musculoskeletal_link TEXT NOT NULL,
  secondary_queries_json TEXT NOT NULL,
  competition_json TEXT NOT NULL,
  unresolved_json TEXT NOT NULL,
  transfer_questions_json TEXT NOT NULL,
  data_needs_json TEXT NOT NULL,
  novelty_status TEXT NOT NULL CHECK(novelty_status IN ('Directly studied','Adjacent studies exist','No direct match found in current search','Unresolved')),
  score_total INTEGER NOT NULL,
  score_components_json TEXT NOT NULL,
  score_reasons_json TEXT NOT NULL,
  generated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_score ON cards(score_total DESC);
CREATE TABLE IF NOT EXISTS evidence_searches (
  id INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  query TEXT NOT NULL,
  source TEXT NOT NULL,
  results_json TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  UNIQUE(article_id, query, source)
);
CREATE TABLE IF NOT EXISTS daily_snapshots (
  snapshot_date TEXT PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  card_ids_json TEXT NOT NULL,
  stats_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ideas (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  article_id INTEGER REFERENCES articles(id),
  created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def normalize_doi(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    return value.rstrip(" .")


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute("PRAGMA optimize")

    def close(self) -> None:
        self.conn.close()

    def remove_articles_by_doi(self, dois: set[str]) -> int:
        """Remove explicitly identified seed/demo records without touching live data."""
        normalized = sorted({normalize_doi(value) for value in dois if value})
        if not normalized:
            return 0
        placeholders = ",".join("?" for _ in normalized)
        rows = self.conn.execute(
            f"SELECT id FROM articles WHERE doi IN ({placeholders})", normalized
        ).fetchall()
        article_ids = [int(row["id"]) for row in rows]
        if not article_ids:
            return 0
        id_placeholders = ",".join("?" for _ in article_ids)
        self.conn.execute(
            f"DELETE FROM article_links WHERE preprint_article_id IN ({id_placeholders}) "
            f"OR published_article_id IN ({id_placeholders})",
            article_ids + article_ids,
        )
        self.conn.execute(
            f"DELETE FROM articles WHERE id IN ({id_placeholders})", article_ids
        )
        self.conn.commit()
        return len(article_ids)

    @contextmanager
    def transaction(self):
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def start_run(self, run_type: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs(run_type, started_at) VALUES (?, ?)", (run_type, now_iso())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, stats: dict, errors: list[dict]) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at=?, status=?, stats_json=?, errors_json=? WHERE id=?",
            (now_iso(), status, json.dumps(stats), json.dumps(errors), run_id),
        )
        self.conn.commit()

    def upsert_article(self, item: Article) -> int:
        item.doi = normalize_doi(item.doi)
        title_key = normalize_title(item.title)
        now = now_iso()
        row = None
        if item.doi:
            row = self.conn.execute("SELECT id FROM articles WHERE doi=?", (item.doi,)).fetchone()
        if not row and item.pmid:
            row = self.conn.execute("SELECT id FROM articles WHERE pmid=?", (item.pmid,)).fetchone()
        if not row:
            row = self.conn.execute(
                "SELECT id FROM articles WHERE title_key=? AND title_key != '' ORDER BY id LIMIT 1", (title_key,)
            ).fetchone()
        values = (
            item.source, item.title, title_key, item.abstract, item.journal, item.published_date,
            item.doi or None, item.pmid or None, item.url, item.status,
            json.dumps(item.authors, ensure_ascii=False), json.dumps(item.raw, ensure_ascii=False), now,
        )
        if row:
            article_id = int(row["id"])
            self.conn.execute(
                """UPDATE articles SET source=?, title=?, title_key=?, abstract=CASE WHEN length(?)>length(abstract) THEN ? ELSE abstract END,
                journal=?, published_date=?, doi=COALESCE(?, doi), pmid=COALESCE(?, pmid), url=?,
                publication_status=CASE WHEN ?='peer-reviewed' THEN 'peer-reviewed' ELSE publication_status END,
                authors_json=?, raw_json=?, last_seen_at=? WHERE id=?""",
                (item.source, item.title, title_key, item.abstract, item.abstract, item.journal, item.published_date,
                 item.doi or None, item.pmid or None, item.url, item.status,
                 json.dumps(item.authors, ensure_ascii=False), json.dumps(item.raw, ensure_ascii=False), now, article_id),
            )
        else:
            cur = self.conn.execute(
                """INSERT INTO articles(source,title,title_key,abstract,journal,published_date,doi,pmid,url,
                publication_status,authors_json,raw_json,first_seen_at,last_seen_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values + (now,)
            )
            article_id = int(cur.lastrowid)
        return article_id

    def save_card(self, card: OpportunityCard) -> None:
        self.conn.execute(
            """INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(article_id) DO UPDATE SET
              track=excluded.track, summary_json=excluded.summary_json, new_paradigm=excluded.new_paradigm,
              why_now=excluded.why_now, musculoskeletal_link=excluded.musculoskeletal_link,
              secondary_queries_json=excluded.secondary_queries_json, competition_json=excluded.competition_json,
              unresolved_json=excluded.unresolved_json, transfer_questions_json=excluded.transfer_questions_json,
              data_needs_json=excluded.data_needs_json, novelty_status=excluded.novelty_status,
              score_total=excluded.score_total, score_components_json=excluded.score_components_json,
              score_reasons_json=excluded.score_reasons_json, generated_at=excluded.generated_at""",
            (
                card.article_id, card.track, json.dumps(card.summary_zh, ensure_ascii=False), card.new_paradigm,
                card.why_now, card.musculoskeletal_link, json.dumps(card.secondary_queries, ensure_ascii=False),
                json.dumps(card.competition, ensure_ascii=False), json.dumps(card.unresolved_questions, ensure_ascii=False),
                json.dumps(card.transfer_questions, ensure_ascii=False), json.dumps(card.data_needs, ensure_ascii=False),
                card.novelty_status, card.score.total, json.dumps(card.score.components, ensure_ascii=False),
                json.dumps(card.score.reasons, ensure_ascii=False), now_iso(),
            ),
        )

    def save_evidence(self, article_id: int, query: str, source: str, results: list[dict]) -> None:
        self.conn.execute(
            """INSERT INTO evidence_searches(article_id,query,source,results_json,checked_at) VALUES(?,?,?,?,?)
            ON CONFLICT(article_id,query,source) DO UPDATE SET results_json=excluded.results_json, checked_at=excluded.checked_at""",
            (article_id, query, source, json.dumps(results, ensure_ascii=False), now_iso()),
        )

    def article(self, article_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        return dict(row) if row else {}

    def recent_cards(self, days: int = 30) -> list[dict]:
        rows = self.conn.execute(
            """SELECT a.*, c.* FROM cards c JOIN articles a ON a.id=c.article_id
            WHERE date(CASE WHEN length(a.published_date) >= 10 THEN substr(a.published_date,1,10) ELSE a.first_seen_at END) >= date('now', ?)
            ORDER BY c.score_total DESC, a.published_date DESC""",
            (f"-{days} days",),
        ).fetchall()
        result = []
        json_cols = {
            "authors_json": "authors", "summary_json": "summary_zh", "secondary_queries_json": "secondary_queries",
            "competition_json": "competition", "unresolved_json": "unresolved_questions",
            "transfer_questions_json": "transfer_questions", "data_needs_json": "data_needs",
            "score_components_json": "score_components", "score_reasons_json": "score_reasons",
        }
        for row in rows:
            item = dict(row)
            for source, dest in json_cols.items():
                item[dest] = json.loads(item.get(source) or "[]")
            result.append(item)
        return result

    def snapshot(self, run_id: int, date: str, card_ids: list[int], stats: dict) -> None:
        self.conn.execute(
            """INSERT INTO daily_snapshots VALUES(?,?,?,?) ON CONFLICT(snapshot_date) DO UPDATE SET
            run_id=excluded.run_id, card_ids_json=excluded.card_ids_json, stats_json=excluded.stats_json""",
            (date, run_id, json.dumps(card_ids), json.dumps(stats)),
        )
        self.conn.commit()

    def link_versions(self) -> int:
        preprints = self.conn.execute("SELECT id,title_key,raw_json FROM articles WHERE publication_status='preprint'").fetchall()
        published = self.conn.execute("SELECT id,title_key,doi FROM articles WHERE publication_status='peer-reviewed'").fetchall()
        count = 0
        for pre in preprints:
            for pub in published:
                raw = json.loads(pre["raw_json"] or "{}")
                declared_doi = normalize_doi(raw.get("published_doi", ""))
                doi_match = bool(declared_doi and declared_doi == normalize_doi(pub["doi"] or ""))
                title_match = len(pre["title_key"]) >= 24 and pre["title_key"] == pub["title_key"]
                if doi_match or title_match:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO article_links VALUES(?,?,?,?)",
                        (pre["id"], pub["id"], 1.0 if doi_match else 0.96,
                         "bioRxiv/medRxiv published DOI" if doi_match else "normalized title match"),
                    )
                    count += 1
        self.conn.commit()
        return count

