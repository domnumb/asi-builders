"""
Tests for scraper.py — mocks all GitHub API calls.
"""

import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from scraper import _get, _paginate, scrape_repo


# ---------------------------------------------------------------------------
# _get
# ---------------------------------------------------------------------------

def _mock_resp(status, data, headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data
    resp.headers = headers or {}
    return resp


@patch("scraper.requests.get")
def test_get_success(mock_get):
    mock_get.return_value = _mock_resp(200, {"key": "value"})
    result = _get("https://api.github.com/test")
    assert result == {"key": "value"}


@patch("scraper.requests.get")
def test_get_404_returns_empty_list(mock_get):
    mock_get.return_value = _mock_resp(404, {})
    result = _get("https://api.github.com/missing")
    assert result == []


@patch("scraper.time.sleep")
@patch("scraper.requests.get")
def test_get_rate_limit_retries(mock_get, mock_sleep):
    future_reset = str(int(time.time()) + 2)
    rate_resp = _mock_resp(403, {}, {"X-RateLimit-Reset": future_reset})
    ok_resp = _mock_resp(200, [{"id": 1}])
    mock_get.side_effect = [rate_resp, ok_resp]

    result = _get("https://api.github.com/repos/x/y/commits")
    assert result == [{"id": 1}]
    assert mock_sleep.called


@patch("scraper.requests.get")
def test_get_unknown_error_returns_empty(mock_get):
    mock_get.return_value = _mock_resp(500, {})
    result = _get("https://api.github.com/broken")
    assert result == []


# ---------------------------------------------------------------------------
# _paginate
# ---------------------------------------------------------------------------

@patch("scraper._get")
def test_paginate_single_page(mock_get):
    mock_get.return_value = [{"id": i} for i in range(10)]
    result = _paginate("https://api.github.com/repos/x/y/commits")
    assert len(result) == 10
    mock_get.assert_called_once()


@patch("scraper._get")
def test_paginate_stops_on_empty(mock_get):
    mock_get.side_effect = [
        [{"id": i} for i in range(100)],
        [],
    ]
    result = _paginate("https://api.github.com/repos/x/y/commits")
    assert len(result) == 100


@patch("scraper._get")
def test_paginate_respects_max_pages(mock_get):
    mock_get.return_value = [{"id": i} for i in range(100)]
    result = _paginate("https://api.github.com/repos/x/y/commits", max_pages=2)
    assert len(result) == 200
    assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# scrape_repo
# ---------------------------------------------------------------------------

SINCE = datetime(2026, 2, 1, tzinfo=timezone.utc)

COMMITS_PAYLOAD = [
    {"author": {"login": "alice"}, "commit": {"author": {"name": "Alice"}}, "sha": "abc"},
    {"author": {"login": "bob"}, "commit": {"author": {"name": "Bob"}}, "sha": "def"},
    {"author": None, "commit": {"author": {"name": "unknown"}}, "sha": "ghi"},   # filtered
]

PRS_PAYLOAD = [
    {"merged_at": "2026-02-10T10:00:00Z", "user": {"login": "alice"}},
    {"merged_at": None, "user": {"login": "bob"}},          # not merged
    {"merged_at": "2026-01-01T00:00:00Z", "user": {"login": "carol"}},  # too old
]

REVIEWS_PAYLOAD = [
    {"user": {"login": "bob"}},
    {"user": {"login": "ghost"}},   # filtered
]

ISSUES_PAYLOAD = [
    {"pull_request": None, "closed_by": {"login": "carol"}},
    {"pull_request": {}, "closed_by": {"login": "alice"}},  # PR, skipped
]


@patch("scraper._paginate")
def test_scrape_repo_counts(mock_paginate):
    def side_effect(url, params=None, **kwargs):
        if "commits" in url:
            return COMMITS_PAYLOAD
        if "pulls/comments" in url:
            return REVIEWS_PAYLOAD
        if "pulls" in url:
            return PRS_PAYLOAD
        if "issues" in url:
            return ISSUES_PAYLOAD
        return []

    mock_paginate.side_effect = side_effect

    result = scrape_repo("some/repo", SINCE)

    assert result["alice"]["commits"] == 1
    assert result["alice"]["prs_merged"] == 1
    assert result["bob"]["commits"] == 1
    assert result["bob"]["review_comments"] == 1
    assert result["carol"]["issues_closed"] == 1
    assert "unknown" not in result
    assert "ghost" not in result


@patch("scraper._paginate")
def test_scrape_repo_empty_repo(mock_paginate):
    mock_paginate.return_value = []
    result = scrape_repo("org/nonexistent", SINCE)
    assert result == {}
