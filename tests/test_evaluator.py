"""
Tests for evaluator.py — mocks Anthropic API calls.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from evaluator import evaluate_contributor, evaluate_all


STATS = {
    "commits": 5,
    "prs_merged": 2,
    "issues_closed": 1,
    "lines_added": 100,
    "lines_deleted": 20,
    "review_comments": 3,
}


def _mock_message(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def _mock_client(text: str):
    client = MagicMock()
    client.messages.create.return_value = _mock_message(text)
    return client


# ---------------------------------------------------------------------------
# evaluate_contributor — happy path
# ---------------------------------------------------------------------------

@patch("evaluator._get_client")
def test_evaluate_contributor_valid_json(mock_get_client):
    payload = json.dumps({"impact": 8, "complexity": 6, "leverage": 7, "rationale": "solid work"})
    mock_get_client.return_value = _mock_client(payload)

    result = evaluate_contributor("alice", "anthropic/sdk", STATS)

    assert result["impact"] == 8.0
    assert result["complexity"] == 6.0
    assert result["leverage"] == 7.0
    assert result["rationale"] == "solid work"
    # composite = 8*0.4 + 6*0.3 + 7*0.3 = 3.2 + 1.8 + 2.1 = 7.1
    assert result["composite"] == pytest.approx(7.1, abs=0.01)


@patch("evaluator._get_client")
def test_evaluate_contributor_strips_code_fences(mock_get_client):
    payload = "```json\n" + json.dumps({"impact": 5, "complexity": 5, "leverage": 5, "rationale": "ok"}) + "\n```"
    mock_get_client.return_value = _mock_client(payload)

    result = evaluate_contributor("bob", "openai/evals", STATS)
    assert result["impact"] == 5.0
    assert result["composite"] == pytest.approx(5.0, abs=0.01)


# ---------------------------------------------------------------------------
# evaluate_contributor — failure paths
# ---------------------------------------------------------------------------

@patch("evaluator.time.sleep")
@patch("evaluator._get_client")
def test_evaluate_contributor_json_error_retries_then_fallback(mock_get_client, mock_sleep):
    mock_get_client.return_value = _mock_client("not valid json")

    result = evaluate_contributor("bad", "some/repo", STATS)

    assert result["impact"] == 0
    assert result["composite"] == 0
    assert result["rationale"] == "evaluation failed"
    assert mock_sleep.call_count == 3  # 3 attempts


@patch("evaluator.time.sleep")
@patch("evaluator._get_client")
def test_evaluate_contributor_api_error_fallback(mock_get_client, mock_sleep):
    import anthropic
    client = MagicMock()
    client.messages.create.side_effect = anthropic.APIError("rate limit", request=MagicMock(), body=None)
    mock_get_client.return_value = client

    result = evaluate_contributor("broken", "some/repo", STATS)
    assert result["composite"] == 0


# ---------------------------------------------------------------------------
# evaluate_all
# ---------------------------------------------------------------------------

@patch("evaluator._get_client")
def test_evaluate_all_skips_zero_activity(mock_get_client):
    payload = json.dumps({"impact": 7, "complexity": 5, "leverage": 6, "rationale": "fine"})
    mock_get_client.return_value = _mock_client(payload)

    scrape_results = {
        "org/repo": {
            "active_user": {"commits": 3, "prs_merged": 1, "issues_closed": 0,
                            "lines_added": 0, "lines_deleted": 0, "review_comments": 0},
            "inactive_user": {"commits": 0, "prs_merged": 0, "issues_closed": 0,
                              "lines_added": 0, "lines_deleted": 0, "review_comments": 0},
        }
    }

    result = evaluate_all(scrape_results)

    assert "active_user" in result["org/repo"]
    assert "inactive_user" not in result["org/repo"]


@patch("evaluator._get_client")
def test_evaluate_all_empty_repos(mock_get_client):
    result = evaluate_all({})
    assert result == {}
    mock_get_client.assert_not_called()
