"""Unit tests for build_dashboard.load_watchlist.

Most shape validation lives in dashboard_lib.validate_watchlist (separately
tested). This file just covers the IO shell: missing file, malformed JSON,
and the happy path.
"""

import json

import pytest

from build_dashboard import load_watchlist


class TestLoadWatchlist:
    def test_missing_file_returns_empty_listings(self, tmp_path):
        result = load_watchlist(str(tmp_path), "acme")
        assert result == {"listings": {}}

    def test_malformed_json_raises_systemexit(self, tmp_path):
        path = tmp_path / "acme-watchlist.json"
        path.write_text("{not json")
        with pytest.raises(SystemExit) as exc_info:
            load_watchlist(str(tmp_path), "acme")
        assert "not valid JSON" in str(exc_info.value)

    def test_happy_path_returns_listings(self, tmp_path):
        path = tmp_path / "acme-watchlist.json"
        path.write_text(json.dumps({
            "listings": {
                "lid-1": {"note": "Check dealer"},
                "lid-2": {"note": ""},
            }
        }))
        result = load_watchlist(str(tmp_path), "acme")
        assert "lid-1" in result["listings"]
        assert result["listings"]["lid-1"]["note"] == "Check dealer"
