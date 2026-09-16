from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path


def export_site(cards: list[dict], output: Path, assets_dir: Path | None = None) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "cards": cards,
        "stats": {
            "total": len(cards),
            "track_a": sum(x["track"] == "A" for x in cards),
            "track_b": sum(x["track"] == "B" for x in cards),
            "preprints": sum(x["publication_status"] == "preprint" for x in cards),
            "high_value": sum(x["score_total"] >= 68 for x in cards),
        },
        "notice": "novelty status 仅表示当前自动检索结果，不代表系统性综述结论。",
    }
    path = output / "data.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
