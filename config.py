"""
ASI Builders Leaderboard — Configuration
"""

# Repos tracked (24 top ASI-oriented open source projects)
TRACKED_REPOS = [
    # Anthropic ecosystem
    "anthropics/anthropic-sdk-python",
    "anthropics/anthropic-sdk-typescript",
    "anthropics/claude-code",
    # OpenAI / frontier labs
    "openai/openai-python",
    "openai/evals",
    "openai/swarm",
    # Agents & orchestration
    "langchain-ai/langchain",
    "langchain-ai/langgraph",
    "microsoft/autogen",
    "crewAIInc/crewAI",
    "run-llama/llama_index",
    # Reasoning / inference
    "deepseek-ai/DeepSeek-R1",
    "unslothai/unsloth",
    "huggingface/transformers",
    "huggingface/trl",
    # Tooling & evals
    "brainlid/langchain",
    "BerriAI/litellm",
    "arc-evals/arc-evals",
    "EleutherAI/lm-evaluation-harness",
    # Safety & alignment
    "anthropics/evals",
    "openai/safety-eval",
    "alignmentforum/alignmentforum",
    # Infra
    "vllm-project/vllm",
    "ggerganov/llama.cpp",
]

# Time window for scraping (days)
SCRAPE_WINDOW_DAYS = 7

# Haiku evaluation prompt
EVAL_PROMPT = """You are evaluating an open source contributor to ASI-oriented projects.

Contributor: {username}
Repository: {repo}
Stats (last 7 days):
- Commits: {commits}
- PRs merged: {prs_merged}
- Issues closed: {issues_closed}
- Code lines added: {lines_added}
- Code lines deleted: {lines_deleted}
- PR review comments: {review_comments}

Score each dimension from 0 to 10 (integer only):

IMPACT: Does this work meaningfully advance AI capabilities, safety, or infrastructure?
Consider: repo strategic importance, PR descriptions, commit messages quality.

COMPLEXITY: How technically sophisticated is this contribution?
Consider: lines changed, architectural changes, new abstractions introduced.

LEVERAGE: Could this work accelerate other builders or be built upon?
Consider: PRs to core libs, tooling, APIs, documentation quality.

Respond ONLY with valid JSON, no explanation:
{{"impact": <0-10>, "complexity": <0-10>, "leverage": <0-10>, "rationale": "<1 sentence>"}}"""

# Scoring weights
SCORE_WEIGHTS = {
    "impact": 0.40,
    "complexity": 0.30,
    "leverage": 0.30,
}

# Badge thresholds (composite score)
BADGES = [
    (9.0, "🏆 ASI Pioneer"),
    (7.5, "⚡ Core Builder"),
    (6.0, "🔧 Active Contributor"),
    (4.0, "🌱 Emerging Builder"),
    (0.0, "👀 On the Radar"),
]

# Publishing
TOP_N = 10  # builders in the leaderboard post
PUBLICATION_DAY = "monday"  # weekly cadence

LINKEDIN_POST_TEMPLATE = """🚀 ASI Builders Leaderboard — Week of {week_date}

Top {top_n} contributors pushing the frontier this week:

{rankings}

---
Tracking {repo_count} repos across agents, reasoning, safety & infra.
Scored by Claude on Impact × Complexity × Leverage.

Follow for weekly updates 👇
#ASI #OpenSource #AI #MachineLearning"""

NEWSLETTER_TEMPLATE = """# ASI Builders Leaderboard — {week_date}

> Auto-generated weekly ranking of top open source contributors to ASI-oriented projects.

## Top {top_n} This Week

{rankings_detailed}

---

## Methodology
- **Repos tracked**: {repo_count}
- **Time window**: last 7 days
- **Scoring**: Claude Haiku evaluates Impact (40%) × Complexity (30%) × Leverage (30%)
- **Data source**: GitHub API

[View all contributors]({leaderboard_url})
"""
