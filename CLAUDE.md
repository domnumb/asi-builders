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

## Pipeline contenu

### Classification des dossiers

```
drafts/internal/   → Notes internes, stratégie, données sensibles. JAMAIS publié.
drafts/review/     → Prêt pour self-review. Pas encore validé.
drafts/publish/    → Validé, prêt à publier. Requiert frontmatter type: public_content.
published/         → Déjà publié (archivé avec date).
```

### Règles pipeline

1. Tout contenu commence dans `drafts/internal/` ou `drafts/review/` — jamais directement dans `drafts/publish/`
2. Self-review obligatoire avant passage `drafts/review/` → `drafts/publish/`
3. Validation Pax requise pour : LinkedIn publish, dépenses, tout irréversible
4. Pas de fichiers .md loose dans `drafts/` — toujours dans un sous-dossier

### Données interdites

Ne jamais fabriquer : scores, rankings, contributor stats non sourcés par GitHub API, engagement metrics.

### Output gates

- Contenu dans `drafts/publish/` → frontmatter `type: public_content` obligatoire
- Scripts → `--dry-run` par défaut
