"""
ASI Builders Leaderboard — GitHub scraper
"""

import os
import time
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import requests

from config import TRACKED_REPOS, SCRAPE_WINDOW_DAYS, FETCH_LINE_STATS

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url: str, params: dict = None) -> dict | list:
    """GET with simple rate-limit retry."""
    for attempt in range(3):
        resp = requests.get(url, headers=_headers(), params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - int(time.time()), 1)
            logger.warning("Rate limited, sleeping %ds", wait)
            time.sleep(min(wait, 120))
            continue
        if resp.status_code == 404:
            logger.warning("404 for %s", url)
            return []
        logger.error("GitHub API error %d: %s", resp.status_code, url)
        return []
    return []


def _paginate(url: str, params: dict = None, max_pages: int = 10) -> list:
    """Collect all pages from a paginated GitHub endpoint."""
    params = params or {}
    params["per_page"] = 100
    results = []
    page = 1
    while page <= max_pages:
        params["page"] = page
        data = _get(url, params)
        if not isinstance(data, list) or not data:
            break
        results.extend(data)
        if len(data) < 100:
            break
        page += 1
    return results


def scrape_repo(repo: str, since: datetime) -> dict[str, dict]:
    """
    Scrape one repo for the given time window.
    Returns {username: stats_dict}.
    """
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    stats: dict[str, dict] = defaultdict(lambda: {
        "commits": 0, "prs_merged": 0, "issues_closed": 0,
        "lines_added": 0, "lines_deleted": 0, "review_comments": 0,
    })

    # --- Commits ---
    commits = _paginate(
        f"{GITHUB_API}/repos/{repo}/commits",
        {"since": since_iso},
    )
    for c in commits:
        author = (c.get("author") or {}).get("login")
        if not author:
            author = (c.get("commit", {}).get("author") or {}).get("name", "unknown")
        if author in ("unknown", "", None):
            continue
        stats[author]["commits"] += 1
        if FETCH_LINE_STATS:
            detail = _get(f"{GITHUB_API}/repos/{repo}/commits/{c['sha']}")
            if isinstance(detail, dict):
                s = detail.get("stats", {})
                stats[author]["lines_added"] += s.get("additions", 0)
                stats[author]["lines_deleted"] += s.get("deletions", 0)

    # --- Merged PRs ---
    prs = _paginate(
        f"{GITHUB_API}/repos/{repo}/pulls",
        {"state": "closed", "sort": "updated", "direction": "desc"},
    )
    for pr in prs:
        merged_at = pr.get("merged_at")
        if not merged_at:
            continue
        merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        if merged_dt < since:
            continue
        author = (pr.get("user") or {}).get("login", "unknown")
        if author in ("unknown", "", None):
            continue
        stats[author]["prs_merged"] += 1

    # --- Review comments ---
    reviews = _paginate(
        f"{GITHUB_API}/repos/{repo}/pulls/comments",
        {"since": since_iso},
    )
    for r in reviews:
        author = (r.get("user") or {}).get("login", "unknown")
        if author in ("unknown", "", None, "ghost"):
            continue
        stats[author]["review_comments"] += 1

    # --- Issues closed ---
    issues = _paginate(
        f"{GITHUB_API}/repos/{repo}/issues",
        {"state": "closed", "since": since_iso},
    )
    for issue in issues:
        if issue.get("pull_request"):
            continue  # skip PRs listed as issues
        closed_by = (issue.get("closed_by") or {}).get("login", "unknown")
        if closed_by in ("unknown", "", None):
            continue
        stats[closed_by]["issues_closed"] += 1

    return dict(stats)


def scrape_all(window_days: int = SCRAPE_WINDOW_DAYS) -> dict[str, dict[str, dict]]:
    """
    Scrape all tracked repos.
    Returns {repo: {username: stats}}.
    """
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    results = {}
    for repo in TRACKED_REPOS:
        logger.info("Scraping %s ...", repo)
        try:
            results[repo] = scrape_repo(repo, since)
            logger.info("  → %d contributors found", len(results[repo]))
        except Exception as exc:
            logger.error("Failed scraping %s: %s", repo, exc)
            results[repo] = {}
    return results
