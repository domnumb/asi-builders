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

from db import get_conn, get_badge
from config import TRACKED_REPOS, SCORE_WEIGHTS, BADGES

logger = logging.getLogger(__name__)

SITE_DIR = Path(__file__).parent / "_site"
SITE_NAME = "ASI Builders"
SITE_URL = "https://asi-builders.github.io"


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

# ─── Index page ────────────────────────────────────────────

def _render_index(week: str, builders: list[dict]) -> str:
    rows_html = []
    for i, b in enumerate(builders):
        rank = i + 1
        badge = _esc(get_badge(b["avg_composite"]))
        username = _esc(b["username"])
        repos = b.get("repos", "")
        repo_names = ", ".join(r.split("/")[-1] for r in repos.split(",")[:3]) if repos else ""
        score = b["avg_composite"]

        bar_width = min(score / 10 * 100, 100)
        rank_class = "top3" if rank <= 3 else ""

        rows_html.append(f"""
        <a href="/u/{username}/" class="row {rank_class}">
          <div class="rank">{'🥇🥈🥉'[rank-1] if rank <= 3 else f'#{rank}'}</div>
          <img class="avatar" src="https://github.com/{username}.png?size=64"
               alt="{username}" loading="lazy" onerror="this.style.display='none'" />
          <div class="info">
            <div class="name">{username} <span class="badge-label">{badge}</span></div>
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
    <span><strong>{len(builders)}</strong> ranked contributors</span>
    <span><strong>{len(TRACKED_REPOS)}</strong> tracked repos</span>
    <span>Scored on <strong>Impact &times; Complexity &times; Leverage</strong></span>
  </div>
  <div class="leaderboard">
    {''.join(rows_html)}
  </div>
  <div class="embed-section">
    <h3>Embed your badge</h3>
    <code>![ASI Builder](https://asi-builders.github.io/badge/YOUR_USERNAME.svg)</code>
  </div>
</main>
<footer>
  <div class="container">
    {SITE_NAME} &middot; Open data &middot;
    <a href="/api/leaderboard.json">JSON API</a> &middot;
    <a href="https://github.com/domnumb/asi-builders">Source</a>
  </div>
</footer>
</body>
</html>"""


# ─── Profile page ─────────────────────────────────────────

def _render_profile(username: str, detail: dict, week: str, rank: int, total: int) -> str:
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
@media (max-width: 640px) {{
  .profile-header {{ flex-direction: column; text-align: center; }}
  .score-card {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<header>
  <div class="container">
    <a href="/" class="logo"><span>ASI</span> Builders</a>
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

  <h2 class="section-title">Repo breakdown</h2>
  {''.join(repo_rows)}

  <div class="share-section">
    <h3>Share your ranking</h3>
    <div class="share-row">
      <a class="share-btn" href="https://twitter.com/intent/tweet?text={_esc(share_text)}" target="_blank" rel="noopener">Post on X</a>
      <a class="share-btn" href="https://www.linkedin.com/sharing/share-offsite/?url={profile_url}" target="_blank" rel="noopener">Share on LinkedIn</a>
    </div>
    <h3>Embed badge in your README</h3>
    <div class="badge-code">[![ASI Builder](https://asi-builders.github.io/badge/{_esc(username)}.svg)](https://asi-builders.github.io/u/{_esc(username)}/)</div>
  </div>
</main>
<footer>
  <div class="container">
    <a href="/">&larr; Full leaderboard</a> &middot;
    <a href="/api/leaderboard.json">JSON API</a> &middot;
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

    # Clean & create output dir
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir(parents=True)

    # Index
    index_html = _render_index(week, builders)
    (SITE_DIR / "index.html").write_text(index_html)
    logger.info("  index.html")

    # Profile pages
    profiles_dir = SITE_DIR / "u"
    for i, b in enumerate(builders):
        username = b["username"]
        detail = _get_contributor_detail(username)
        user_dir = profiles_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)
        profile_html = _render_profile(username, detail, week, rank=i + 1, total=len(builders))
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
