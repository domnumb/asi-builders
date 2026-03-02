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
