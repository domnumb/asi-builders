"""
ASI Builders Leaderboard — Publisher
Generates LinkedIn post + newsletter content. Saving to DB + printing to stdout.
Actual LinkedIn posting: plug into Maël's existing automation pipeline.
"""

import logging
from datetime import datetime

from config import (
    LINKEDIN_POST_TEMPLATE,
    NEWSLETTER_TEMPLATE,
    TOP_N,
    TRACKED_REPOS,
)
from db import get_top_builders, get_badge, save_publication, mark_published

logger = logging.getLogger(__name__)

LEADERBOARD_URL = "https://github.com/maelvanderlinden/asi-builders"


def _format_ranking_linkedin(builders: list[dict], rank_offset: int = 1) -> str:
    lines = []
    for i, b in enumerate(builders):
        rank = rank_offset + i
        badge = get_badge(b["avg_composite"])
        score = b["avg_composite"]
        repos = b.get("repos", "")
        short_repos = ", ".join(r.split("/")[-1] for r in repos.split(", ")[:2])
        lines.append(
            f"{rank}. @{b['username']} — {badge} ({score:.1f}/10)\n"
            f"   {b['total_commits']}c · {b['total_prs']}pr · {short_repos}"
        )
    return "\n\n".join(lines)


def _format_ranking_newsletter(builders: list[dict], rank_offset: int = 1) -> str:
    lines = []
    for i, b in enumerate(builders):
        rank = rank_offset + i
        badge = get_badge(b["avg_composite"])
        score = b["avg_composite"]
        lines.append(
            f"### {rank}. [{b['username']}](https://github.com/{b['username']}) — {badge}\n"
            f"**Score**: {score:.1f}/10  "
            f"| **Commits**: {b['total_commits']}  "
            f"| **PRs**: {b['total_prs']}  "
            f"| **Repos**: {b.get('repo_count', 0)}\n\n"
            f"> {b.get('rationale', '')}"
        )
    return "\n\n".join(lines)


def _week_label() -> str:
    return datetime.utcnow().strftime("Week of %b %d, %Y")


def generate_linkedin_post(week_start: str) -> str:
    builders = get_top_builders(week_start, TOP_N)
    if not builders:
        logger.warning("No builders found for week %s", week_start)
        return ""
    rankings = _format_ranking_linkedin(builders)
    post = LINKEDIN_POST_TEMPLATE.format(
        week_date=_week_label(),
        top_n=len(builders),
        rankings=rankings,
        repo_count=len(TRACKED_REPOS),
    )
    return post


def generate_newsletter(week_start: str) -> str:
    builders = get_top_builders(week_start, TOP_N)
    if not builders:
        return ""

    # Attach rationale from DB — get_top_builders doesn't aggregate it, add a best-effort one
    rankings_detailed = _format_ranking_newsletter(builders)
    newsletter = NEWSLETTER_TEMPLATE.format(
        week_date=_week_label(),
        top_n=len(builders),
        rankings_detailed=rankings_detailed,
        repo_count=len(TRACKED_REPOS),
        leaderboard_url=LEADERBOARD_URL,
    )
    return newsletter


def publish(week_start: str, dry_run: bool = False) -> dict[str, str]:
    """
    Generate and persist both posts.
    Returns {"linkedin": post_text, "newsletter": newsletter_text}.
    Set dry_run=True to preview without saving to DB.
    """
    linkedin_post = generate_linkedin_post(week_start)
    newsletter = generate_newsletter(week_start)

    if not linkedin_post:
        logger.error("Nothing to publish for week %s", week_start)
        return {}

    if not dry_run:
        save_publication(week_start, "linkedin", linkedin_post)
        save_publication(week_start, "newsletter", newsletter)
        logger.info("Saved publications to DB for week %s", week_start)

    print("\n" + "=" * 60)
    print("LINKEDIN POST")
    print("=" * 60)
    print(linkedin_post)
    print("\n" + "=" * 60)
    print("NEWSLETTER")
    print("=" * 60)
    print(newsletter)

    return {"linkedin": linkedin_post, "newsletter": newsletter}
