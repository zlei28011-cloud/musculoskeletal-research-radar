import json
import shutil
import unittest
import uuid
from pathlib import Path

from radar.cards import build_card, secondary_queries
from radar.db import Database, normalize_doi, normalize_title
from radar.models import Article
from radar.reports import daily_email
from radar.scoring import calculate, classify
from radar.sources import PubMedSource


CONFIG = json.loads(Path("config/radar.json").read_text(encoding="utf-8"))


class CoreTests(unittest.TestCase):
    def test_normalizers(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1000/ABC. "), "10.1000/abc")
        self.assertEqual(normalize_title("Bone-aging: A Study!"), "boneagingastudy")

    def test_classification_and_score(self):
        item = Article(source="crossref", title="Spatial transcriptomics of osteoporosis", journal="Nature Aging")
        track, hits = classify(item, CONFIG)
        self.assertEqual(track, "A")
        score = calculate(item.as_dict(), track, hits, CONFIG)
        self.assertTrue(0 <= score.total <= 100)
        self.assertEqual(set(score.components), set(CONFIG["score_weights"]))

    def test_database_deduplicates_doi(self):
        tmp = Path("work") / f"test-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True)
        try:
            db = Database(tmp / "radar.db")
            a = Article(source="crossref", title="First title", doi="10.1/X", status="peer-reviewed")
            b = Article(source="pubmed", title="Updated title", doi="https://doi.org/10.1/x", status="peer-reviewed")
            self.assertEqual(db.upsert_article(a), db.upsert_article(b))
            count = db.conn.execute("SELECT count(*) FROM articles").fetchone()[0]
            self.assertEqual(count, 1)
            db.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_database_removes_only_explicit_demo_dois(self):
        tmp = Path("work") / f"test-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True)
        try:
            db = Database(tmp / "radar.db")
            demo = Article(source="crossref", title="Demo", doi="10.0000/demo.001", status="peer-reviewed")
            live = Article(source="crossref", title="Live", doi="10.1000/live", status="peer-reviewed")
            db.upsert_article(demo)
            db.upsert_article(live)
            db.conn.commit()
            self.assertEqual(db.remove_articles_by_doi({"10.0000/demo.001"}), 1)
            remaining = db.conn.execute("SELECT doi FROM articles").fetchall()
            self.assertEqual([row[0] for row in remaining], ["10.1000/live"])
            db.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_card_status_is_constrained(self):
        article = {"title": "A foundation model for aging", "abstract": "A longitudinal biobank foundation model.", "journal": "Nature Aging", "source": "crossref"}
        card = build_card(1, article, "B", ["foundation model"], CONFIG, [])
        self.assertEqual(card.novelty_status, "No direct match found in current search")
        self.assertEqual(len(card.summary_zh), 3)
        self.assertEqual(len(secondary_queries(["foundation model"], ["bone"])), 1)

    def test_pubmed_omits_empty_api_key(self):
        without_key = PubMedSource("researcher@example.com")
        self.assertNotIn("api_key", without_key.base_params)
        with_key = PubMedSource("researcher@example.com", "test-key")
        self.assertEqual(with_key.base_params["api_key"], "test-key")

    def test_daily_email_is_bilingual_and_structured(self):
        card = {
            "title": "A spatial atlas of skeletal aging",
            "url": "https://example.org/article",
            "track": "B",
            "score_total": 88,
            "novelty_status": "Adjacent studies exist",
            "journal": "Nature Aging",
            "published_at": "2026-09-16",
            "doi": "10.1000/example",
            "pmid": None,
            "abstract": "We generated a spatial atlas of aging tissues. The atlas revealed distinct cellular neighborhoods. These findings support future mechanistic studies.",
            "summary_zh": [
                "这项研究聚焦空间衰老图谱。",
                "作者主要使用了空间转录组学来回答研究问题。 摘要证据：We generated a spatial atlas.",
                "它可能帮助重构骨与肌肉衰老机制。 摘要补充：The atlas revealed distinct cellular neighborhoods.",
            ],
            "new_paradigm": "空间转录组学",
            "data_needs": ["human tissue", "omics"],
            "musculoskeletal_link": "可评估骨髓微环境中的空间细胞互作。",
            "competition": [],
        }
        rendered = daily_email([card])
        self.assertIn("今日必看 / Must Read", rendered)
        self.assertIn("摘要级解读 / Abstract-level review", rendered)
        self.assertIn("研究背景 / Background", rendered)
        self.assertIn("方法与数据 / Methods &amp; Data", rendered)
        self.assertIn("英文原文证据 / Original Evidence", rendered)
        self.assertIn("We generated a spatial atlas of aging tissues.", rendered)
        self.assertIn("本卡基于题录与摘要自动生成", rendered)


if __name__ == "__main__":
    unittest.main()

