from __future__ import annotations

import argparse
import json
import logging

from .demo import seed
from .pipeline import run
from .settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="radar", description="Musculoskeletal Research Radar")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="Collect sources and build the daily radar")
    run_parser.add_argument("--weekly", action="store_true", help="Also write Weekly Frontier Brief")
    run_parser.add_argument("--skip-email", action="store_true", help="Build reports without SMTP delivery")
    sub.add_parser("demo", help="Build the site with deterministic demo records")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.getLevelName(__import__("os").getenv("RADAR_LOG_LEVEL", "INFO")),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.load()
    if args.command == "demo":
        print(json.dumps({"demo_cards": seed(settings)}, ensure_ascii=False))
    else:
        result = run(settings, weekly=args.weekly, skip_email=args.skip_email)
        print(json.dumps({"run_id": result.run_id, "stats": result.stats, "errors": result.errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()

