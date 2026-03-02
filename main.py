"""
ASI Builders Leaderboard — Orchestrator

Usage:
    python main.py run          # full pipeline (scrape → evaluate → publish)
    python main.py scrape       # scrape only
    python main.py evaluate     # evaluate last scrape (re-run Haiku scoring)
    python main.py publish      # publish last results
    python main.py preview      # dry-run publish (stdout only, no DB write)
    python main.py status       # show current week top 10
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config import SCRAPE_WINDOW_DAYS, TOP_N, TRACKED_REPOS
from db import init_db, upsert_contributor, upsert_score, get_top_builders, get_badge
from scraper import scrape_all
from evaluator import evaluate_all
from publisher import publish
from site_generator import generate_site

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).parent / ".scrape_cache.json"


def week_start() -> str:
    """ISO date of the Monday of the current week."""
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def _check_env():
    missing = []
    if not os.environ.get("GITHUB_TOKEN"):
        missing.append("GITHUB_TOKEN")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        logger.error("Missing environment variables: %s", ", ".join(missing))
        logger.error("Copy .env.example to .env and fill in your keys.")
        sys.exit(1)


def cmd_scrape() -> dict:
    _check_env()
    logger.info("Starting scrape — tracking %d repos, window=%d days", len(TRACKED_REPOS), SCRAPE_WINDOW_DAYS)
    results = scrape_all()
    CACHE_FILE.write_text(json.dumps(results, default=str))
    logger.info("Scrape complete. Cache saved to %s", CACHE_FILE)
    return results


def cmd_evaluate(scrape_results: dict = None) -> dict:
    _check_env()
    if scrape_results is None:
        if not CACHE_FILE.exists():
            logger.error("No scrape cache found. Run `python main.py scrape` first.")
            sys.exit(1)
        scrape_results = json.loads(CACHE_FILE.read_text())

    logger.info("Starting evaluation ...")
    evaluated = evaluate_all(scrape_results)

    ws = week_start()
    for repo, contributors in scrape_results.items():
        for username, stats in contributors.items():
            upsert_contributor(username)
            scores = evaluated.get(repo, {}).get(username, {})
            if scores:
                upsert_score(ws, username, repo, stats, scores)

    logger.info("Evaluation complete. Results saved to DB.")
    return evaluated


def cmd_publish(dry_run: bool = False):
    ws = week_start()
    publish(ws, dry_run=dry_run)


def cmd_status():
    ws = week_start()
    builders = get_top_builders(ws, TOP_N)
    if not builders:
        print(f"No data for week {ws}. Run the pipeline first.")
        return
    print(f"\nASI Builders Leaderboard — {ws}\n{'─'*50}")
    for i, b in enumerate(builders):
        badge = get_badge(b["avg_composite"])
        print(
            f"{i+1:2}. {b['username']:<25} {badge:<22} {b['avg_composite']:.1f}/10"
            f"  ({b['total_commits']}c / {b['total_prs']}pr)"
        )


def cmd_site():
    """Generate static site into _site/."""
    generate_site()


def cmd_run():
    """Full pipeline: scrape → evaluate → publish → site."""
    scrape_results = cmd_scrape()
    cmd_evaluate(scrape_results)
    cmd_publish()
    cmd_site()


def main():
    init_db()

    parser = argparse.ArgumentParser(description="ASI Builders Leaderboard")
    parser.add_argument(
        "command",
        choices=["run", "scrape", "evaluate", "publish", "preview", "status", "site"],
        help="Command to execute",
    )
    args = parser.parse_args()

    commands = {
        "run": cmd_run,
        "scrape": cmd_scrape,
        "evaluate": cmd_evaluate,
        "publish": cmd_publish,
        "preview": lambda: cmd_publish(dry_run=True),
        "status": cmd_status,
        "site": cmd_site,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
