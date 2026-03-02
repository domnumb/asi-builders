"""
ASI Builders — Static site generator

Generates:
  _site/index.html           — Leaderboard page
  _site/u/<username>/index.html — Per-contributor profile
  _site/badge/<username>.svg — Embeddable badge
  _site/api/leaderboard.json — Open data
"""

import json
import html
import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from db import get_conn, get_badge, get_previous_week_ranks, get_builder_history, get_trending_repos, get_total_contributors, get_builder_evolution, get_builder_rank_in_week
from config import TRACKED_REPOS, SCORE_WEIGHTS, BADGES

logger = logging.getLogger(__name__)

SITE_DIR = Path(__file__).parent / "_site"
SITE_NAME = "ASI Builders"
BASE_PATH = "/asi-builders"  # GitHub Pages subpath (empty string for custom domain)
SITE_URL = f"https://domnumb.github.io{BASE_PATH}"


# ─── Helpers ───────────────────────────────────────────────

def _week_start() -> str:
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def _get_all_weeks() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT week_start FROM weekly_scores ORDER BY week_start DESC"
        ).fetchall()
    return [r["week_start"] for r in rows]


def _get_top_builders(week: str, limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                username,
                SUM(commits) AS total_commits,
                SUM(prs_merged) AS total_prs,
                SUM(issues_closed) AS total_issues,
                SUM(review_comments) AS total_reviews,
                AVG(impact) AS avg_impact,
                AVG(complexity) AS avg_complexity,
                AVG(leverage) AS avg_leverage,
                AVG(composite) AS avg_composite,
                COUNT(DISTINCT repo) AS repo_count,
                GROUP_CONCAT(DISTINCT repo) AS repos
            FROM weekly_scores
            WHERE week_start = ?
            GROUP BY username
            ORDER BY avg_composite DESC
            LIMIT ?
        """, (week, limit)).fetchall()
    return [dict(r) for r in rows]


def _get_contributor_detail(username: str) -> dict:
    with get_conn() as conn:
        scores = conn.execute("""
            SELECT * FROM weekly_scores
            WHERE username = ?
            ORDER BY week_start DESC, composite DESC
        """, (username,)).fetchall()
        contributor = conn.execute(
            "SELECT * FROM contributors WHERE username = ?", (username,)
        ).fetchone()
    return {
        "info": dict(contributor) if contributor else {},
        "scores": [dict(s) for s in scores],
    }


def _esc(s: str) -> str:
    return html.escape(str(s))


def _trend_indicator(username: str, current_rank: int, prev_ranks: dict) -> str:
    """Return an HTML span with a trend arrow."""
    if username not in prev_ranks:
        return '<span class="trend new" title="New this week">NEW</span>'
    prev = prev_ranks[username]
    diff = prev - current_rank
    if diff > 0:
        return f'<span class="trend up" title="Up {diff} from #{prev}">+{diff}</span>'
    elif diff < 0:
        return f'<span class="trend down" title="Down {-diff} from #{prev}">{diff}</span>'
    return '<span class="trend same" title="Same rank">=</span>'


def _render_sparkline_css(history: list[dict]) -> str:
    """Render a pure-CSS sparkline from weekly score history."""
    if len(history) < 2:
        return ""
    # history is most-recent-first, reverse for chronological display
    points = list(reversed(history))
    scores = [p["avg_composite"] for p in points]
    lo, hi = min(scores), max(scores)
    span = hi - lo if hi > lo else 1

    bars = []
    for i, p in enumerate(points):
        pct = (p["avg_composite"] - lo) / span * 100
        height = max(pct, 8)  # minimum visible height
        bars.append(
            f'<div class="spark-bar" title="{p["week_start"]}: {p["avg_composite"]:.1f}" '
            f'style="height:{height:.0f}%"></div>'
        )
    return f'<div class="sparkline">{"".join(bars)}</div>'


def _render_history_section(username: str) -> str:
    """Render the weekly score history section with sparkline."""
    history = get_builder_history(username)
    if len(history) < 2:
        return ""
    sparkline = _render_sparkline_css(history)
    oldest = history[-1]["week_start"]
    newest = history[0]["week_start"]
    return f"""<div class="history-section">
    <h2 class="section-title">Score history ({len(history)} weeks)</h2>
    {sparkline}
    <div class="spark-labels"><span>{oldest}</span><span>{newest}</span></div>
  </div>"""


# ─── Achievements & Evolution ─────────────────────────────

def _compute_achievements(evo: dict, rank: int, total: int) -> list[dict]:
    """Compute gamification achievements from evolution data."""
    achievements = []
    streak = evo.get("streak", 0)
    weeks = evo.get("weeks_present", 0)
    delta = evo.get("delta")
    best = evo.get("best_week")
    current = evo.get("current")

    # First week
    if weeks == 1:
        achievements.append({"icon": "🚀", "label": "First Week", "desc": "Welcome to the leaderboard!"})

    # Streak
    if streak >= 2:
        achievements.append({"icon": "🔥", "label": f"{streak}-Week Streak", "desc": f"Active {streak} weeks in a row"})

    # Top 10
    if rank <= 10:
        achievements.append({"icon": "🏆", "label": "Top 10", "desc": f"Ranked #{rank} this week"})
    elif rank <= 50:
        achievements.append({"icon": "⭐", "label": "Top 50", "desc": f"Ranked #{rank} this week"})

    # Climber — rank improved
    if delta:
        prev_rank = get_builder_rank_in_week(current["repos"].split(",")[0] if current else "", "")  # not needed, use prev_ranks
        # Score went up
        if delta["score"] > 0.5:
            achievements.append({"icon": "📈", "label": "Score Up", "desc": f"+{delta['score']:.1f} points vs last week"})
        elif delta["score"] < -0.5:
            achievements.append({"icon": "📉", "label": "Score Dip", "desc": f"{delta['score']:.1f} points vs last week"})

        # More commits
        if delta["commits"] > 0:
            achievements.append({"icon": "⚡", "label": "More Active", "desc": f"+{delta['commits']} commits vs last week"})

        # New repos
        new_repos = evo.get("new_repos", set())
        if new_repos:
            names = ", ".join(r.split("/")[-1] for r in list(new_repos)[:3])
            achievements.append({"icon": "🌐", "label": "Expanding", "desc": f"New repo{'s' if len(new_repos) > 1 else ''}: {names}"})

    # Personal best
    if best and current and current["avg_composite"] >= best["avg_composite"] - 0.01 and weeks > 1:
        achievements.append({"icon": "👑", "label": "Personal Best", "desc": f"Highest score ever: {current['avg_composite']:.1f}"})

    # Top 1%
    if total > 0 and rank <= max(1, total // 100):
        achievements.append({"icon": "💎", "label": "Top 1%", "desc": f"Among the best out of {total} builders"})

    return achievements


def _render_evolution_section(username: str, week: str, rank: int, total: int, prev_ranks: dict) -> str:
    """Render the gamification section: achievements + week-over-week narrative."""
    evo = get_builder_evolution(username, week)
    if not evo.get("current"):
        return ""

    achievements = _compute_achievements(evo, rank, total)
    delta = evo.get("delta")

    # --- Achievements badges ---
    badges_html = ""
    if achievements:
        pills = []
        for a in achievements:
            pills.append(
                f'<div class="achievement" title="{_esc(a["desc"])}">'
                f'<span class="ach-icon">{a["icon"]}</span>'
                f'<span class="ach-label">{_esc(a["label"])}</span>'
                f'</div>'
            )
        badges_html = f'<div class="achievements">{"".join(pills)}</div>'

    # --- Evolution narrative ---
    narrative_html = ""
    if delta:
        cur = evo["current"]
        prev = evo["previous"]
        prev_rank = prev_ranks.get(username)

        lines = []

        # Rank movement
        if prev_rank:
            rank_diff = prev_rank - rank
            if rank_diff > 0:
                lines.append(f'<span class="evo-up">Climbed {rank_diff} spot{"s" if rank_diff > 1 else ""}</span> — from #{prev_rank} to #{rank}')
            elif rank_diff < 0:
                lines.append(f'<span class="evo-down">Dropped {-rank_diff} spot{"s" if -rank_diff > 1 else ""}</span> — from #{prev_rank} to #{rank}')
            else:
                lines.append(f'<span class="evo-same">Held steady</span> at #{rank}')

        # Score change
        if abs(delta["score"]) > 0.1:
            direction = "up" if delta["score"] > 0 else "down"
            lines.append(f'Score: {prev["avg_composite"]:.1f} → {cur["avg_composite"]:.1f} (<span class="evo-{direction}">{delta["score"]:+.1f}</span>)')

        # Activity change
        activity_parts = []
        if delta["commits"] != 0:
            activity_parts.append(f'{delta["commits"]:+d} commits')
        if delta["prs"] != 0:
            activity_parts.append(f'{delta["prs"]:+d} PRs')
        if delta["repos"] != 0:
            activity_parts.append(f'{delta["repos"]:+d} repo{"s" if abs(delta["repos"]) > 1 else ""}')
        if activity_parts:
            lines.append("Activity: " + ", ".join(activity_parts))

        # New repos detail
        new_repos = evo.get("new_repos", set())
        if new_repos:
            names = ", ".join(r.split("/")[-1] for r in list(new_repos)[:5])
            lines.append(f'Started contributing to: <strong>{_esc(names)}</strong>')

        lost_repos = evo.get("lost_repos", set())
        if lost_repos:
            names = ", ".join(r.split("/")[-1] for r in list(lost_repos)[:5])
            lines.append(f'No longer active in: {_esc(names)}')

        if lines:
            items = "".join(f"<li>{l}</li>" for l in lines)
            narrative_html = f'<ul class="evo-list">{items}</ul>'
    elif evo["weeks_present"] == 1:
        narrative_html = '<p class="evo-first">First appearance on the leaderboard — welcome! 🎉</p>'

    if not badges_html and not narrative_html:
        return ""

    return f"""<div class="evolution-section">
    <h2 class="section-title">This week's story</h2>
    {badges_html}
    {narrative_html}
  </div>"""


# ─── CSS ───────────────────────────────────────────────────

COMMON_CSS = """
:root {
  --bg: #0a0a0f;
  --bg2: #12121a;
  --bg3: #1a1a25;
  --border: #2a2a3a;
  --text: #e0e0e8;
  --text2: #8888a0;
  --accent: #6c5ce7;
  --accent2: #a29bfe;
  --gold: #f9ca24;
  --green: #00b894;
  --blue: #0984e3;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}
a { color: var(--accent2); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: 900px; margin: 0 auto; padding: 0 20px; }
header {
  border-bottom: 1px solid var(--border);
  padding: 24px 0;
  margin-bottom: 32px;
}
header .container {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.5px;
}
.logo span { color: var(--accent2); }
.subtitle {
  font-size: 13px;
  color: var(--text2);
}
.meta {
  font-size: 13px;
  color: var(--text2);
  margin-bottom: 24px;
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}
.meta strong { color: var(--text); }
footer {
  border-top: 1px solid var(--border);
  padding: 24px 0;
  margin-top: 48px;
  text-align: center;
  font-size: 13px;
  color: var(--text2);
}
"""

# ─── Trending repos section ────────────────────────────────

def _render_trending_section(trending: list[dict]) -> str:
    if not trending:
        return ""
    rows = []
    for t in trending:
        repo_short = t["repo"].split("/")[-1]
        rows.append(f"""
        <div class="trending-repo">
          <div class="repo-name"><a href="https://github.com/{_esc(t['repo'])}">{_esc(repo_short)}</a></div>
          <div class="repo-stats">
            <span>{t['contributor_count']} contributors</span>
            <span>{t['total_commits']} commits</span>
            <span>{t['total_prs']} PRs</span>
          </div>
        </div>""")
    return f"""<div class="trending-section">
    <h3>Trending repos this week</h3>
    {''.join(rows)}
  </div>"""


# ─── Index page ────────────────────────────────────────────

def _render_index(week: str, builders: list[dict], prev_ranks: dict = None, trending: list[dict] = None, total_contributors: int = 0) -> str:
    prev_ranks = prev_ranks or {}
    rows_html = []
    for i, b in enumerate(builders):
        rank = i + 1
        badge = _esc(get_badge(b["avg_composite"]))
        username = _esc(b["username"])
        repos = b.get("repos", "")
        repo_names = ", ".join(r.split("/")[-1] for r in repos.split(",")[:3]) if repos else ""
        score = b["avg_composite"]
        trend = _trend_indicator(b["username"], rank, prev_ranks)

        bar_width = min(score / 10 * 100, 100)
        rank_class = "top3" if rank <= 3 else ""

        rows_html.append(f"""
        <a href="{BASE_PATH}/u/{username}/" class="row {rank_class}">
          <div class="rank">{'🥇🥈🥉'[rank-1] if rank <= 3 else f'#{rank}'}</div>
          <img class="avatar" src="https://github.com/{username}.png?size=64"
               alt="{username}" loading="lazy" onerror="this.style.display='none'" />
          <div class="info">
            <div class="name">{username} <span class="badge-label">{badge}</span>{trend}</div>
            <div class="repos">{_esc(repo_names)}</div>
          </div>
          <div class="stats">
            <span title="Commits">{b['total_commits']}c</span>
            <span title="PRs merged">{b['total_prs']}pr</span>
          </div>
          <div class="score-col">
            <div class="score-bar"><div class="score-fill" style="width:{bar_width:.0f}%"></div></div>
            <div class="score-num">{score:.1f}</div>
          </div>
        </a>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SITE_NAME} — Weekly Leaderboard</title>
<meta name="description" content="Weekly ranking of top open source contributors to ASI-oriented projects. Scored on Impact, Complexity & Leverage.">
<meta property="og:title" content="{SITE_NAME} — Week of {week}">
<meta property="og:description" content="Top {len(builders)} contributors pushing the ASI frontier this week.">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{COMMON_CSS}
.hero {{
  text-align: center;
  padding: 40px 0 32px;
}}
.hero h1 {{
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -1px;
  margin-bottom: 8px;
}}
.hero h1 span {{ color: var(--accent2); }}
.hero p {{
  color: var(--text2);
  font-size: 15px;
  max-width: 500px;
  margin: 0 auto;
}}
.week-label {{
  display: inline-block;
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 6px 16px;
  font-size: 13px;
  color: var(--text2);
  margin-bottom: 24px;
}}
.leaderboard {{ margin-bottom: 32px; }}
.row {{
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 10px;
  transition: background 0.15s;
  color: var(--text);
  text-decoration: none;
}}
.row:hover {{
  background: var(--bg2);
  text-decoration: none;
}}
.row.top3 {{
  background: var(--bg2);
  border: 1px solid var(--border);
  margin-bottom: 4px;
}}
.rank {{
  width: 40px;
  text-align: center;
  font-weight: 600;
  font-size: 15px;
  color: var(--text2);
  flex-shrink: 0;
}}
.top3 .rank {{ color: var(--gold); font-size: 20px; }}
.avatar {{
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.info {{ flex: 1; min-width: 0; }}
.name {{
  font-weight: 600;
  font-size: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.badge-label {{
  font-weight: 400;
  font-size: 12px;
  color: var(--text2);
  margin-left: 6px;
}}
.repos {{
  font-size: 12px;
  color: var(--text2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.stats {{
  display: flex;
  gap: 10px;
  font-size: 13px;
  color: var(--text2);
  flex-shrink: 0;
}}
.score-col {{
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  width: 120px;
}}
.score-bar {{
  flex: 1;
  height: 6px;
  background: var(--bg3);
  border-radius: 3px;
  overflow: hidden;
}}
.score-fill {{
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  border-radius: 3px;
}}
.score-num {{
  font-weight: 600;
  font-size: 14px;
  width: 32px;
  text-align: right;
}}
.embed-section {{
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-top: 16px;
}}
.embed-section h3 {{
  font-size: 14px;
  margin-bottom: 8px;
}}
.embed-section code {{
  display: block;
  background: var(--bg);
  padding: 10px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--accent2);
  word-break: break-all;
}}
.trend {{
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 6px;
  vertical-align: middle;
}}
.trend.up {{ color: #00b894; background: rgba(0,184,148,0.12); }}
.trend.down {{ color: #d63031; background: rgba(214,48,49,0.12); }}
.trend.new {{ color: var(--gold); background: rgba(249,202,36,0.12); }}
.trend.same {{ color: var(--text2); }}
.trending-section {{
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-top: 32px;
}}
.trending-section h3 {{
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}}
.trending-repo {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
}}
.trending-repo:last-child {{ border-bottom: none; }}
.trending-repo .repo-name {{ flex: 1; font-weight: 500; }}
.trending-repo .repo-stats {{ color: var(--text2); font-size: 13px; display: flex; gap: 12px; }}
@media (max-width: 640px) {{
  .stats {{ display: none; }}
  .score-col {{ width: 80px; }}
  .hero h1 {{ font-size: 24px; }}
}}
</style>
</head>
<body>
<header>
  <div class="container">
    <div class="logo"><span>ASI</span> Builders</div>
    <div class="subtitle">Tracking {len(TRACKED_REPOS)} repos &middot; Scored by Claude</div>
  </div>
</header>
<main class="container">
  <div class="hero">
    <h1>Who's building <span>ASI</span>?</h1>
    <p>Weekly ranking of the top open source contributors pushing the frontier of artificial superintelligence.</p>
  </div>
  <div class="week-label">Week of {week}</div>
  <div class="meta">
    <span><strong>{len(builders)}</strong> ranked this week</span>
    <span><strong>{total_contributors or len(builders)}</strong> tracked all-time</span>
    <span><strong>{len(TRACKED_REPOS)}</strong> repos</span>
    <span>Scored on <strong>Impact &times; Complexity &times; Leverage</strong></span>
  </div>
  <div class="leaderboard">
    {''.join(rows_html)}
  </div>
  {_render_trending_section(trending or [])}
  <div class="embed-section">
    <h3>Embed your badge</h3>
    <code>![ASI Builder]({SITE_URL}/badge/YOUR_USERNAME.svg)</code>
  </div>
</main>
<footer>
  <div class="container">
    Built by <a href="https://github.com/domnumb">@domnumb</a> &middot;
    <a href="{BASE_PATH}/api/leaderboard.json">Open data</a> &middot;
    <a href="https://github.com/domnumb/asi-builders">Source</a>
  </div>
</footer>
</body>
</html>"""


# ─── Profile page ─────────────────────────────────────────

def _render_profile(username: str, detail: dict, week: str, rank: int, total: int, prev_ranks: dict = None) -> str:
    scores = detail["scores"]
    if not scores:
        return ""

    latest = scores[0]
    badge = _esc(get_badge(latest["composite"]))
    badge_svg_url = f"{SITE_URL}/badge/{username}.svg"
    profile_url = f"{SITE_URL}/u/{username}/"

    # Build repo breakdown for latest week
    latest_week_scores = [s for s in scores if s["week_start"] == week]
    repo_rows = []
    for s in sorted(latest_week_scores, key=lambda x: x["composite"], reverse=True):
        repo_short = s["repo"].split("/")[-1]
        repo_rows.append(f"""
        <div class="repo-row">
          <div class="repo-name">
            <a href="https://github.com/{_esc(s['repo'])}">{_esc(repo_short)}</a>
          </div>
          <div class="repo-scores">
            <span class="dim">I:</span>{s['impact']:.0f}
            <span class="dim">C:</span>{s['complexity']:.0f}
            <span class="dim">L:</span>{s['leverage']:.0f}
            <span class="composite">{s['composite']:.1f}</span>
          </div>
          <div class="repo-stats">{s['commits']}c &middot; {s['prs_merged']}pr</div>
          <div class="rationale">{_esc(s.get('rationale') or '')}</div>
        </div>""")

    total_commits = sum(s["commits"] for s in latest_week_scores)
    total_prs = sum(s["prs_merged"] for s in latest_week_scores)
    avg_composite = sum(s["composite"] for s in latest_week_scores) / len(latest_week_scores) if latest_week_scores else 0

    share_text = f"I'm ranked #{rank} on ASI Builders this week! {profile_url}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(username)} — {SITE_NAME}</title>
<meta name="description" content="{_esc(username)} is ranked #{rank} on ASI Builders. Score: {avg_composite:.1f}/10. {badge}">
<meta property="og:title" content="{_esc(username)} — #{rank} ASI Builder">
<meta property="og:description" content="Score: {avg_composite:.1f}/10 &middot; {total_commits} commits &middot; {total_prs} PRs merged &middot; {badge}">
<meta property="og:type" content="profile">
<meta property="og:url" content="{profile_url}">
<meta property="og:image" content="https://github.com/{username}.png?size=256">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{_esc(username)} — #{rank} ASI Builder">
<meta name="twitter:description" content="Score: {avg_composite:.1f}/10 &middot; {badge}">
<meta name="twitter:image" content="https://github.com/{username}.png?size=256">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{COMMON_CSS}
.profile-header {{
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 32px 0;
}}
.profile-avatar {{
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 2px solid var(--border);
}}
.profile-info h1 {{
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.5px;
}}
.profile-info h1 .rank-tag {{
  font-size: 14px;
  font-weight: 500;
  color: var(--accent2);
  background: var(--bg3);
  padding: 2px 10px;
  border-radius: 12px;
  margin-left: 8px;
  vertical-align: middle;
}}
.profile-badge {{
  font-size: 16px;
  color: var(--text2);
}}
.score-card {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 32px;
}}
.score-card .card {{
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}}
.card .label {{
  font-size: 12px;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 4px;
}}
.card .value {{
  font-size: 28px;
  font-weight: 700;
}}
.card .value.accent {{ color: var(--accent2); }}
.section-title {{
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}}
.repo-row {{
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}}
.repo-row:last-child {{ border-bottom: none; }}
.repo-name {{ font-weight: 600; margin-bottom: 4px; }}
.repo-scores {{
  font-size: 14px;
  display: flex;
  gap: 10px;
  margin-bottom: 4px;
}}
.repo-scores .dim {{ color: var(--text2); margin-right: 2px; }}
.repo-scores .composite {{
  color: var(--accent2);
  font-weight: 600;
  margin-left: auto;
}}
.repo-stats {{
  font-size: 12px;
  color: var(--text2);
}}
.rationale {{
  font-size: 13px;
  color: var(--text2);
  font-style: italic;
  margin-top: 4px;
}}
.share-section {{
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-top: 24px;
}}
.share-section h3 {{ font-size: 14px; margin-bottom: 10px; }}
.share-row {{
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}}
.share-btn {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--bg3);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}}
.share-btn:hover {{ background: var(--accent); color: white; text-decoration: none; }}
.badge-code {{
  background: var(--bg);
  padding: 10px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--accent2);
  font-family: monospace;
  word-break: break-all;
}}
.evolution-section {{
  margin-bottom: 32px;
}}
.achievements {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}}
.achievement {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 13px;
  transition: transform 0.15s;
}}
.achievement:hover {{ transform: scale(1.05); }}
.ach-icon {{ font-size: 16px; }}
.ach-label {{ font-weight: 500; }}
.evo-list {{
  list-style: none;
  padding: 0;
}}
.evo-list li {{
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
}}
.evo-list li:last-child {{ border-bottom: none; }}
.evo-up {{ color: #00b894; font-weight: 600; }}
.evo-down {{ color: #d63031; font-weight: 600; }}
.evo-same {{ color: var(--text2); font-weight: 600; }}
.evo-first {{
  color: var(--accent2);
  font-size: 15px;
  padding: 8px 0;
}}
.history-section {{
  margin-bottom: 32px;
}}
.sparkline {{
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 60px;
  padding: 8px 0;
}}
.spark-bar {{
  flex: 1;
  background: linear-gradient(180deg, var(--accent2), var(--accent));
  border-radius: 2px 2px 0 0;
  min-width: 8px;
  transition: opacity 0.15s;
}}
.spark-bar:hover {{
  opacity: 0.7;
}}
.spark-labels {{
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text2);
}}
@media (max-width: 640px) {{
  .profile-header {{ flex-direction: column; text-align: center; }}
  .score-card {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<header>
  <div class="container">
    <a href="{BASE_PATH}/" class="logo"><span>ASI</span> Builders</a>
    <div class="subtitle">Week of {week}</div>
  </div>
</header>
<main class="container">
  <div class="profile-header">
    <img class="profile-avatar" src="https://github.com/{_esc(username)}.png?size=160"
         alt="{_esc(username)}" onerror="this.style.display='none'" />
    <div class="profile-info">
      <h1>
        <a href="https://github.com/{_esc(username)}">{_esc(username)}</a>
        <span class="rank-tag">#{rank} of {total}</span>
      </h1>
      <div class="profile-badge">{badge}</div>
    </div>
  </div>

  <div class="score-card">
    <div class="card">
      <div class="label">Composite</div>
      <div class="value accent">{avg_composite:.1f}</div>
    </div>
    <div class="card">
      <div class="label">Commits</div>
      <div class="value">{total_commits}</div>
    </div>
    <div class="card">
      <div class="label">PRs Merged</div>
      <div class="value">{total_prs}</div>
    </div>
    <div class="card">
      <div class="label">Repos</div>
      <div class="value">{len(latest_week_scores)}</div>
    </div>
  </div>

  {_render_evolution_section(username, week, rank, total, prev_ranks or {})}

  {_render_history_section(username)}

  <h2 class="section-title">Repo breakdown</h2>
  {''.join(repo_rows)}

  <div class="share-section">
    <h3>Share your ranking</h3>
    <div class="share-row">
      <a class="share-btn" href="https://twitter.com/intent/tweet?text={_esc(share_text)}" target="_blank" rel="noopener">Post on X</a>
      <a class="share-btn" href="https://www.linkedin.com/sharing/share-offsite/?url={profile_url}" target="_blank" rel="noopener">Share on LinkedIn</a>
    </div>
    <h3>Embed badge in your README</h3>
    <div class="badge-code">[![ASI Builder]({SITE_URL}/badge/{_esc(username)}.svg)]({SITE_URL}/u/{_esc(username)}/)</div>
  </div>
</main>
<footer>
  <div class="container">
    <a href="{BASE_PATH}/">&larr; Full leaderboard</a> &middot;
    Built by <a href="https://github.com/domnumb">@domnumb</a> &middot;
    <a href="{BASE_PATH}/api/leaderboard.json">Open data</a> &middot;
    <a href="https://github.com/domnumb/asi-builders">Source</a>
  </div>
</footer>
</body>
</html>"""


# ─── Badge SVG ─────────────────────────────────────────────

def _render_badge_svg(username: str, score: float, badge_text: str) -> str:
    # Remove emoji from badge text for SVG
    clean_badge = badge_text
    for char in "🏆⚡🔧🌱👀":
        clean_badge = clean_badge.replace(char, "").strip()

    label = "ASI Builder"
    value = f"{clean_badge} {score:.1f}"
    label_width = len(label) * 7 + 10
    value_width = len(value) * 6.5 + 10
    total_width = label_width + value_width

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {value}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_width}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#333"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="#6c5ce7"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text x="{label_width/2}" y="14">{label}</text>
    <text x="{label_width + value_width/2}" y="14">{value}</text>
  </g>
</svg>"""


# ─── Generator ─────────────────────────────────────────────

def generate_site():
    """Generate the full static site into _site/."""
    week = _week_start()
    builders = _get_top_builders(week, limit=500)

    if not builders:
        logger.warning("No data for week %s — trying previous weeks", week)
        for w in _get_all_weeks():
            builders = _get_top_builders(w, limit=500)
            if builders:
                week = w
                break

    if not builders:
        logger.error("No data found in DB. Run the pipeline first.")
        return

    logger.info("Generating site for week %s — %d builders", week, len(builders))

    # Fetch trends data
    prev_ranks = get_previous_week_ranks(week)
    trending = get_trending_repos(week)
    total_contribs = get_total_contributors()

    # Clean & create output dir
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(parents=True)

    # Index
    index_html = _render_index(week, builders, prev_ranks=prev_ranks, trending=trending, total_contributors=total_contribs)
    (SITE_DIR / "index.html").write_text(index_html)
    logger.info("  index.html")

    # Profile pages
    profiles_dir = SITE_DIR / "u"
    for i, b in enumerate(builders):
        username = b["username"]
        detail = _get_contributor_detail(username)
        user_dir = profiles_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)
        profile_html = _render_profile(username, detail, week, rank=i + 1, total=len(builders), prev_ranks=prev_ranks)
        if profile_html:
            (user_dir / "index.html").write_text(profile_html)
    logger.info("  %d profile pages", len(builders))

    # Badges
    badge_dir = SITE_DIR / "badge"
    badge_dir.mkdir(parents=True)
    for b in builders:
        username = b["username"]
        badge_text = get_badge(b["avg_composite"])
        svg = _render_badge_svg(username, b["avg_composite"], badge_text)
        (badge_dir / f"{username}.svg").write_text(svg)
    logger.info("  %d badges", len(builders))

    # JSON API
    api_dir = SITE_DIR / "api"
    api_dir.mkdir(parents=True)
    api_data = {
        "week": week,
        "generated_at": datetime.utcnow().isoformat(),
        "repo_count": len(TRACKED_REPOS),
        "builders": [
            {
                "rank": i + 1,
                "username": b["username"],
                "score": round(b["avg_composite"], 2),
                "impact": round(b["avg_impact"], 2),
                "complexity": round(b["avg_complexity"], 2),
                "leverage": round(b["avg_leverage"], 2),
                "commits": b["total_commits"],
                "prs_merged": b["total_prs"],
                "repos": b["repo_count"],
                "badge": get_badge(b["avg_composite"]),
                "profile_url": f"{SITE_URL}/u/{b['username']}/",
                "badge_url": f"{SITE_URL}/badge/{b['username']}.svg",
            }
            for i, b in enumerate(builders)
        ],
    }
    (api_dir / "leaderboard.json").write_text(json.dumps(api_data, indent=2))
    logger.info("  api/leaderboard.json")

    # CNAME (for custom domain later)
    # (SITE_DIR / "CNAME").write_text("asibuilders.dev")

    # .nojekyll for GitHub Pages
    (SITE_DIR / ".nojekyll").write_text("")

    logger.info("Site generated: %s", SITE_DIR)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    generate_site()
