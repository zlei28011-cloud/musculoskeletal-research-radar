import json
import shutil
import unittest
import uuid
from pathlib import Path

from radar.cards import build_card, secondary_queries
from radar.db import Database, normalize_doi, normalize_title
from radar.models import Article
from radar.scoring import calculate, classify


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

    def test_card_status_is_constrained(self):
        article = {"title": "A foundation model for aging", "abstract": "A longitudinal biobank foundation model.", "journal": "Nature Aging", "source": "crossref"}
        card = build_card(1, article, "B", ["foundation model"], CONFIG, [])
        self.assertEqual(card.novelty_status, "No direct match found in current search")
        self.assertEqual(len(card.summary_zh), 3)
        self.assertEqual(len(secondary_queries(["foundation model"], ["bone"])), 1)


if __name__ == "__main__":
    unittest.main()
