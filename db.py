"""
ASI Builders Leaderboard — SQLite persistence
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import BADGES

DB_PATH = Path(__file__).parent / "asi_builders.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS contributors (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT NOT NULL,
                avatar_url  TEXT,
                profile_url TEXT,
                first_seen  TEXT NOT NULL,
                last_seen   TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_contributors_username
                ON contributors(username);

            CREATE TABLE IF NOT EXISTS weekly_scores (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT NOT NULL,
                week_start   TEXT NOT NULL,
                repo         TEXT NOT NULL,
                commits      INTEGER DEFAULT 0,
                prs_merged   INTEGER DEFAULT 0,
                issues_closed INTEGER DEFAULT 0,
                lines_added  INTEGER DEFAULT 0,
                lines_deleted INTEGER DEFAULT 0,
                review_comments INTEGER DEFAULT 0,
                impact       REAL DEFAULT 0,
                complexity   REAL DEFAULT 0,
                leverage     REAL DEFAULT 0,
                composite    REAL DEFAULT 0,
                rationale    TEXT,
                raw_response TEXT,
                created_at   TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_scores_unique
                ON weekly_scores(username, week_start, repo);
            CREATE INDEX IF NOT EXISTS idx_weekly_scores_week_start
                ON weekly_scores(week_start);

            CREATE TABLE IF NOT EXISTS publications (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start   TEXT NOT NULL,
                platform     TEXT NOT NULL,
                content      TEXT NOT NULL,
                published_at TEXT,
                status       TEXT DEFAULT 'pending'
            );
        """)


def upsert_contributor(username: str, avatar_url: str = "", profile_url: str = ""):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO contributors (username, avatar_url, profile_url, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                avatar_url  = excluded.avatar_url,
                profile_url = excluded.profile_url,
                last_seen   = excluded.last_seen
        """, (username, avatar_url, profile_url, now, now))


def upsert_score(week_start: str, username: str, repo: str, stats: dict, scores: dict):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO weekly_scores
                (username, week_start, repo, commits, prs_merged, issues_closed,
                 lines_added, lines_deleted, review_comments,
                 impact, complexity, leverage, composite, rationale, raw_response, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(username, week_start, repo) DO UPDATE SET
                commits         = excluded.commits,
                prs_merged      = excluded.prs_merged,
                issues_closed   = excluded.issues_closed,
                lines_added     = excluded.lines_added,
                lines_deleted   = excluded.lines_deleted,
                review_comments = excluded.review_comments,
                impact          = excluded.impact,
                complexity      = excluded.complexity,
                leverage        = excluded.leverage,
                composite       = excluded.composite,
                rationale       = excluded.rationale,
                raw_response    = excluded.raw_response
        """, (
            username, week_start, repo,
            stats.get("commits", 0), stats.get("prs_merged", 0),
            stats.get("issues_closed", 0), stats.get("lines_added", 0),
            stats.get("lines_deleted", 0), stats.get("review_comments", 0),
            scores.get("impact", 0), scores.get("complexity", 0),
            scores.get("leverage", 0), scores.get("composite", 0),
            scores.get("rationale", ""), json.dumps(scores.get("raw", {})),
            now,
        ))


def get_top_builders(week_start: str, top_n: int = 10) -> list[dict]:
    """Aggregate scores per contributor for a given week, return top N."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                username,
                SUM(commits)       AS total_commits,
                SUM(prs_merged)    AS total_prs,
                SUM(issues_closed) AS total_issues,
                AVG(impact)        AS avg_impact,
                AVG(complexity)    AS avg_complexity,
                AVG(leverage)      AS avg_leverage,
                AVG(composite)     AS avg_composite,
                COUNT(DISTINCT repo) AS repo_count,
                GROUP_CONCAT(repo, ', ') AS repos
            FROM weekly_scores
            WHERE week_start = ?
            GROUP BY username
            ORDER BY avg_composite DESC
            LIMIT ?
        """, (week_start, top_n)).fetchall()
    return [dict(r) for r in rows]


def get_badge(score: float) -> str:
    for threshold, badge in BADGES:
        if score >= threshold:
            return badge
    return BADGES[-1][1]


def save_publication(week_start: str, platform: str, content: str):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO publications (week_start, platform, content, published_at, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (week_start, platform, content, now))


def mark_published(week_start: str, platform: str):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute("""
            UPDATE publications SET status = 'published', published_at = ?
            WHERE week_start = ? AND platform = ?
        """, (now, week_start, platform))


def get_builder_history(username: str, limit: int = 12) -> list[dict]:
    """Get a builder's composite score per week (most recent first)."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT week_start, AVG(composite) AS avg_composite
            FROM weekly_scores
            WHERE username = ?
            GROUP BY week_start
            ORDER BY week_start DESC
            LIMIT ?
        """, (username, limit)).fetchall()
    return [dict(r) for r in rows]


def get_previous_week_ranks(week_start: str) -> dict[str, int]:
    """Get {username: rank} for the week before the given week_start."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT week_start FROM weekly_scores
            WHERE week_start < ?
            GROUP BY week_start
            ORDER BY week_start DESC
            LIMIT 1
        """, (week_start,)).fetchone()
    if not rows:
        return {}
    prev_week = rows["week_start"]
    with get_conn() as conn:
        ranked = conn.execute("""
            SELECT username, AVG(composite) AS avg_composite
            FROM weekly_scores
            WHERE week_start = ?
            GROUP BY username
            ORDER BY avg_composite DESC
        """, (prev_week,)).fetchall()
    return {r["username"]: i + 1 for i, r in enumerate(ranked)}


def get_trending_repos(week_start: str, limit: int = 5) -> list[dict]:
    """Get repos with most activity this week."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                repo,
                COUNT(DISTINCT username) AS contributor_count,
                SUM(commits) AS total_commits,
                SUM(prs_merged) AS total_prs,
                AVG(composite) AS avg_score
            FROM weekly_scores
            WHERE week_start = ?
            GROUP BY repo
            ORDER BY contributor_count DESC, total_commits DESC
            LIMIT ?
        """, (week_start, limit)).fetchall()
    return [dict(r) for r in rows]


def get_total_contributors() -> int:
    """Get total unique contributors tracked historically."""
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM contributors").fetchone()
    return row["cnt"] if row else 0


def get_builder_evolution(username: str, week_start: str) -> dict:
    """
    Get week-over-week evolution for a builder.
    Returns dict with current/previous week stats and deltas.
    """
    with get_conn() as conn:
        # Current week stats
        cur = conn.execute("""
            SELECT
                AVG(composite) AS avg_composite,
                SUM(commits) AS total_commits,
                SUM(prs_merged) AS total_prs,
                SUM(review_comments) AS total_reviews,
                COUNT(DISTINCT repo) AS repo_count,
                GROUP_CONCAT(DISTINCT repo) AS repos
            FROM weekly_scores WHERE username = ? AND week_start = ?
        """, (username, week_start)).fetchone()

        # Previous week
        prev_week_row = conn.execute("""
            SELECT week_start FROM weekly_scores
            WHERE week_start < ? GROUP BY week_start
            ORDER BY week_start DESC LIMIT 1
        """, (week_start,)).fetchone()

        prev = None
        if prev_week_row:
            prev = conn.execute("""
                SELECT
                    AVG(composite) AS avg_composite,
                    SUM(commits) AS total_commits,
                    SUM(prs_merged) AS total_prs,
                    SUM(review_comments) AS total_reviews,
                    COUNT(DISTINCT repo) AS repo_count,
                    GROUP_CONCAT(DISTINCT repo) AS repos
                FROM weekly_scores WHERE username = ? AND week_start = ?
            """, (username, prev_week_row["week_start"])).fetchone()

        # Count total weeks present
        weeks_present = conn.execute("""
            SELECT COUNT(DISTINCT week_start) AS cnt
            FROM weekly_scores WHERE username = ?
        """, (username,)).fetchone()

        # Best ever score
        best = conn.execute("""
            SELECT week_start, AVG(composite) AS avg_composite
            FROM weekly_scores WHERE username = ?
            GROUP BY week_start ORDER BY avg_composite DESC LIMIT 1
        """, (username,)).fetchone()

        # Streak: consecutive weeks present (from current week backwards)
        all_weeks = conn.execute("""
            SELECT DISTINCT week_start FROM weekly_scores
            ORDER BY week_start DESC
        """).fetchall()
        user_weeks = set(
            r["week_start"] for r in conn.execute(
                "SELECT DISTINCT week_start FROM weekly_scores WHERE username = ?",
                (username,)
            ).fetchall()
        )

    all_week_list = [r["week_start"] for r in all_weeks]
    streak = 0
    for w in all_week_list:
        if w in user_weeks:
            streak += 1
        else:
            break

    result = {
        "current": dict(cur) if cur and cur["avg_composite"] else None,
        "previous": dict(prev) if prev and prev["avg_composite"] else None,
        "weeks_present": weeks_present["cnt"] if weeks_present else 0,
        "streak": streak,
        "best_week": dict(best) if best else None,
    }

    # Compute deltas
    if result["current"] and result["previous"]:
        c, p = result["current"], result["previous"]
        result["delta"] = {
            "score": c["avg_composite"] - p["avg_composite"],
            "commits": c["total_commits"] - p["total_commits"],
            "prs": c["total_prs"] - p["total_prs"],
            "repos": c["repo_count"] - p["repo_count"],
        }
        # New repos this week
        cur_repos = set(c["repos"].split(",")) if c["repos"] else set()
        prev_repos = set(p["repos"].split(",")) if p["repos"] else set()
        result["new_repos"] = cur_repos - prev_repos
        result["lost_repos"] = prev_repos - cur_repos
    else:
        result["delta"] = None
        result["new_repos"] = set()
        result["lost_repos"] = set()

    return result


def get_builder_rank_in_week(username: str, week_start: str) -> int | None:
    """Get a builder's rank for a specific week."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT username FROM weekly_scores
            WHERE week_start = ?
            GROUP BY username
            ORDER BY AVG(composite) DESC
        """, (week_start,)).fetchall()
    for i, r in enumerate(rows):
        if r["username"] == username:
            return i + 1
    return None
