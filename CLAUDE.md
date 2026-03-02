# ASI Builders — CLAUDE.md

## Commands

```bash
python main.py scrape      # GitHub scrape (~2-3 min)
python main.py evaluate    # Haiku scoring (~$0.20)
python main.py preview     # Dry-run output
python main.py status      # Top 10 leaderboard
python main.py site        # Generate static site → _site/
python main.py run         # Full pipeline (scrape+eval+publish+site)
```

## Key files

- `config.py` — repos list, eval prompt, templates, `FETCH_LINE_STATS` flag
- `scraper.py` — GitHub API calls (rate-limit aware)
- `evaluator.py` — Anthropic Haiku calls
- `publisher.py` — LinkedIn + newsletter formatting
- `db.py` — SQLite (asi_builders.db)
- `site_generator.py` — Static site generator → `_site/`

## Conventions

- SQLite DB in repo root (`asi_builders.db`, gitignored)
- Scrape cache in `.scrape_cache.json` (gitignored)
- `FETCH_LINE_STATS = False` by default (skip per-commit detail API calls)
- All env vars via `.env` (python-dotenv)
