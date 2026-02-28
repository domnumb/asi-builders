"""
ASI Builders Leaderboard — Claude Haiku evaluator
"""

import os
import json
import logging
import time

import anthropic

from config import EVAL_PROMPT, SCORE_WEIGHTS

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def evaluate_contributor(username: str, repo: str, stats: dict) -> dict:
    """
    Ask Claude Haiku to score a contributor.
    Returns {impact, complexity, leverage, composite, rationale, raw}.
    """
    prompt = EVAL_PROMPT.format(
        username=username,
        repo=repo,
        commits=stats.get("commits", 0),
        prs_merged=stats.get("prs_merged", 0),
        issues_closed=stats.get("issues_closed", 0),
        lines_added=stats.get("lines_added", 0),
        lines_deleted=stats.get("lines_deleted", 0),
        review_comments=stats.get("review_comments", 0),
    )

    for attempt in range(3):
        try:
            message = _get_client().messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = message.content[0].text.strip()
            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            scores = json.loads(raw_text)
            impact = float(scores.get("impact", 0))
            complexity = float(scores.get("complexity", 0))
            leverage = float(scores.get("leverage", 0))
            composite = (
                impact * SCORE_WEIGHTS["impact"]
                + complexity * SCORE_WEIGHTS["complexity"]
                + leverage * SCORE_WEIGHTS["leverage"]
            )
            return {
                "impact": impact,
                "complexity": complexity,
                "leverage": leverage,
                "composite": round(composite, 2),
                "rationale": scores.get("rationale", ""),
                "raw": scores,
            }
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error for %s/%s (attempt %d): %s", username, repo, attempt + 1, exc)
            time.sleep(1)
        except anthropic.APIError as exc:
            logger.warning("Anthropic API error for %s/%s (attempt %d): %s", username, repo, attempt + 1, exc)
            time.sleep(2 ** attempt)

    # Fallback: zero scores
    logger.error("Evaluation failed for %s/%s after 3 attempts", username, repo)
    return {"impact": 0, "complexity": 0, "leverage": 0, "composite": 0, "rationale": "evaluation failed", "raw": {}}


def evaluate_all(scrape_results: dict[str, dict[str, dict]]) -> dict[str, dict[str, dict]]:
    """
    Evaluate all contributors across all repos.
    Returns {repo: {username: scores}}.
    Skip contributors with zero activity (nothing to score).
    """
    evaluated = {}
    total = sum(len(v) for v in scrape_results.values())
    done = 0
    for repo, contributors in scrape_results.items():
        evaluated[repo] = {}
        for username, stats in contributors.items():
            if not any(stats.values()):
                continue
            logger.info("[%d/%d] Evaluating %s @ %s", done + 1, total, username, repo)
            evaluated[repo][username] = evaluate_contributor(username, repo, stats)
            done += 1
            time.sleep(0.2)  # gentle throttle
    return evaluated
