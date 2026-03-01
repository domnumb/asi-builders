# ASI Builders — CTO Brief

## What

Weekly leaderboard ranking top open source contributors to ASI-oriented projects.
Scrapes GitHub activity, scores with Claude Haiku, outputs LinkedIn post + newsletter.

## Architecture

```
GitHub API (21 repos) → scraper.py → .scrape_cache.json
                                          ↓
                        evaluator.py (Haiku) → SQLite (asi_builders.db)
                                                    ↓
                              publisher.py → LinkedIn post + newsletter (stdout)
```

Single-process Python pipeline. No server, no queue, no infra.
SQLite local, pas de cloud DB.

## Stack

| Composant | Choix | Pourquoi |
|-----------|-------|----------|
| Scraping | `requests` + GitHub REST API | Simple, rate-limit aware, paginated |
| Scoring | Claude Haiku (`claude-haiku-4-5-20251001`) | Cheap (~$0.20/run), structured JSON output |
| Storage | SQLite | Zero config, single file, suffisant pour MVP |
| Config | python-dotenv | `.env` pour secrets |

## Repos trackés (21)

Anthropic (3), OpenAI (3), LangChain (2), CrewAI (1), LlamaIndex (1), DeepSeek (1), Unsloth (1), HuggingFace (2), LiteLLM (1), EleutherAI (1), vLLM (1), llama.cpp (1), brainlid/langchain (1), anthropics/evals (1).

## Scoring

Haiku évalue chaque contributeur par repo sur 3 axes :
- **Impact** (40%) — avance-t-il réellement l'AI ?
- **Complexity** (30%) — sophistication technique
- **Leverage** (30%) — multiplicateur pour les autres builders

Score composite = weighted average → badge :
- 9.0+ : ASI Pioneer
- 7.5+ : Core Builder
- 6.0+ : Active Contributor
- 4.0+ : Emerging Builder
- 0.0+ : On the Radar

## Coûts par run

| Ressource | Volume | Coût |
|-----------|--------|------|
| GitHub API | ~150 calls | Gratuit (token auth) |
| Anthropic Haiku | ~800 calls | ~$0.20 |
| Total | | **~$0.20/semaine** |

Note : `FETCH_LINE_STATS = False` — on skip le fetch individuel de chaque commit (économise ~5K API calls). Les line stats sont à 0, Haiku score sur commits/PRs/reviews.

## Données premier run (2026-02-23)

896 contributeurs scrappés, top 3 :
1. **ggerganov** (llama.cpp) — 8.4/10, Core Builder
2. **WoosukKwon** (vllm) — 7.7/10, Core Builder
3. **danielhanchen** (unsloth) — 7.7/10, Core Builder

## Limitations actuelles

1. **Pas d'automation** — run manuel, `setup_cron.sh` existe mais pas configuré
2. **Pas de publication auto** — output stdout, pas de posting LinkedIn/email
3. **Line stats désactivées** — scoring moins précis sur la complexité
4. **Pas de dédup usernames** — un contributeur actif sur 5 repos = 5 évaluations séparées (agrégé en DB par AVG)
5. **Pas de cache inter-runs** — chaque scrape repart de zéro
6. **GitHub REST API only** — GraphQL serait plus efficient pour les gros repos

## Next steps suggérés

| Priorité | Action | Effort |
|----------|--------|--------|
| P1 | Cron hebdo (lundi 8h) | 15 min |
| P1 | Brancher sur pipeline LinkedIn de Maël | 30 min |
| P2 | Newsletter email (Resend/Buttondown) | 2h |
| P2 | Landing page statique avec le leaderboard | 2h |
| P3 | Activer line stats (+ budget API) | 10 min |
| P3 | Migrer vers GitHub GraphQL | 4h |
| P3 | Historique multi-semaines + trends | 3h |

## Files

```
main.py           — CLI (run/scrape/evaluate/publish/preview/status)
config.py         — 21 repos, prompts, templates, weights
scraper.py        — GitHub REST scraper
evaluator.py      — Haiku scoring
publisher.py      — LinkedIn + newsletter formatting
db.py             — SQLite CRUD
setup_cron.sh     — Cron template (pas configuré)
.env              — GITHUB_TOKEN + ANTHROPIC_API_KEY
.scrape_cache.json — Dernier scrape (gitignored)
asi_builders.db   — SQLite DB (gitignored)
```
