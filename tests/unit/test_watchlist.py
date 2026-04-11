"""Unit tests for dashboard_lib.load_watchlist."""

import json

import pytest

from dashboard_lib import load_watchlist


class TestMissing:
    def test_none_path_returns_empty(self):
        assert load_watchlist(None) == {"listings": {}}

    def test_nonexistent_path_returns_empty(self, tmp_path):
        assert load_watchlist(str(tmp_path / "nope.json")) == {"listings": {}}


class TestHappy:
    def test_loads_valid_watchlist(self, tmp_path):
        p = tmp_path / "wl.json"
        p.write_text(json.dumps({
            "listings": {
                "202601150000001": {"note": "example", "added": "2026-04-01"},
            }
        }))
        result = load_watchlist(str(p))
        assert "202601150000001" in result["listings"]

    def test_missing_listings_key_defaults_to_empty(self, tmp_path):
        p = tmp_path / "wl.json"
        p.write_text("{}")
        assert load_watchlist(str(p)) == {"listings": {}}


class TestMalformed:
    @pytest.mark.parametrize(
        "content,needle",
        [
            ("[]", "must contain a JSON object"),
            ('{"listings": "not-a-dict"}', "'listings' must be an object"),
            ('{"listings": {"abc": "not-a-dict"}}', "must be an object"),
            ('{"listings": {"123": {"note": 1}}}', None),
        ],
    )
    def test_bad_shapes_fail_loudly(self, tmp_path, content, needle):
        p = tmp_path / "wl.json"
        p.write_text(content)
        if needle is None:
            load_watchlist(str(p))
        else:
            with pytest.raises(SystemExit) as exc:
                load_watchlist(str(p))
            assert needle in str(exc.value)
