# ASI Builders Leaderboard

Weekly ranking of top open source contributors to ASI-oriented projects, scored by Claude Haiku on **Impact x Complexity x Leverage**.

Tracks 21 repos across agents, reasoning, safety & infra (Anthropic, OpenAI, LangChain, HuggingFace, vLLM, llama.cpp, etc.).

## Setup

```bash
cp .env.example .env
# Fill in GITHUB_TOKEN and ANTHROPIC_API_KEY
pip install -r requirements.txt
```

## Usage

```bash
python main.py scrape      # Scrape GitHub activity (last 7 days)
python main.py evaluate    # Score contributors with Claude Haiku
python main.py preview     # Preview LinkedIn + newsletter output
python main.py publish     # Save publications to DB
python main.py status      # Show current week top 10
python main.py run         # Full pipeline: scrape → evaluate → publish
```

## Architecture

```
main.py        — CLI orchestrator
config.py      — Repos list, prompts, templates, scoring weights
scraper.py     — GitHub API scraper (commits, PRs, reviews, issues)
evaluator.py   — Claude Haiku scoring (impact/complexity/leverage)
publisher.py   — LinkedIn post + newsletter generator
db.py          — SQLite persistence (contributors, weekly_scores, publications)
```

## Cost

- **GitHub API**: ~150 calls per scrape (with `FETCH_LINE_STATS = False`)
- **Anthropic API**: ~$0.20 per evaluation run (Haiku)
