from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    config: dict
    db_path: Path
    output_dir: Path
    ncbi_api_key: str
    ncbi_email: str
    crossref_mailto: str

    @classmethod
    def load(cls) -> "Settings":
        config_path = Path(os.getenv("RADAR_CONFIG", "config/radar.json"))
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return cls(
            config=config,
            db_path=Path(os.getenv("RADAR_DB", "data/radar.db")),
            output_dir=Path(os.getenv("RADAR_OUTPUT", "dist")),
            ncbi_api_key=os.getenv("NCBI_API_KEY", ""),
            ncbi_email=os.getenv("NCBI_EMAIL", ""),
            crossref_mailto=os.getenv("CROSSREF_MAILTO", os.getenv("NCBI_EMAIL", "")),
        )

