# AGENT.md — ASI Builders

## Vision

Leaderboard hebdomadaire des top contributeurs open source aux projets ASI (Anthropic, OpenAI, LangChain, DeepSeek, etc.). Pipeline automatisé : scrape GitHub → score Haiku → site statique GitHub Pages. Coût ~$0.20/semaine.

## État actuel

| Composant | Status | Détails |
|---|---|---|
| Scraper | ✅ | 21 repos, ~150 API calls, rate-limit aware |
| Evaluator | ✅ | Haiku scoring 3 axes (impact, complexity, leverage) |
| DB | ✅ | SQLite, 896+ contributeurs trackés |
| Site statique | ✅ | https://domnumb.github.io/asi-builders/ — leaderboard + profils + badges |
| Gamification | ✅ | Achievements, sparklines, week-over-week evolution |
| JSON API | ✅ | `/api/leaderboard.json` ouvert |
| GitHub Actions | ✅ | Weekly lundi 09:00 UTC + manual dispatch |
| Tests | ✅ | pytest, mocked GitHub + Anthropic APIs |
| LinkedIn publish | ❌ | Output stdout seulement, pas d'auto-post |
| Newsletter | ❌ | Pas encore implémenté |

## Autonomy scope

**Peut :**
- Exécuter `scrape`, `evaluate`, `site` (pipeline read-only)
- Proposer nouveaux repos à tracker
- Analyser tendances, générer rapports
- Améliorer le code (site generator, scoring)

**Ne peut pas :**
- Publier sur LinkedIn (humain in the loop)
- Modifier les secrets GitHub Actions
- Ajouter des repos sans validation

## Stack et commandes

```bash
# Pipeline complète
python main.py run

# Étapes séparées
python main.py scrape      # ~2-3 min, ~$0
python main.py evaluate    # ~$0.20
python main.py site        # Génère _site/
python main.py preview     # Dry-run
python main.py status      # Top 10 leaderboard

# Tests
pytest tests/

# Deploy (via GitHub Actions ou manual)
git push origin main       # Trigger GH Pages deploy
```

## Next actions

1. **Automatiser LinkedIn post** — intégrer publisher.py avec API ou draft pour Pax — complétion : post LinkedIn publié chaque lundi
2. **Newsletter email** — Resend ou Buttondown — complétion : subscribers reçoivent le ranking hebdo
3. **Ajouter repos** — évaluer Mistral, Cohere, Google DeepMind — complétion : config.py mis à jour, scoring validé
4. **Activer line stats** — `FETCH_LINE_STATS = True` pour scoring plus précis — complétion : complexity scores améliorés
5. **Cron local Bernard** — `setup_cron.sh` configuré — complétion : pipeline tourne sans GitHub Actions

## Journal agent

| Date | Agent | Action |
|---|---|---|
| 2026-03-03 | cc-cto | Création AGENT.md — système multi-agents v1.0 |
