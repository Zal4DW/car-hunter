"""Unit tests for dashboard_lib.validate_watchlist."""

import pytest

from dashboard_lib import validate_watchlist


class TestHappy:
    """Happy test cases."""
    def test_validates_full_watchlist(self):
        """Validates full watchlist."""
        data = {
            "listings": {
                "202601150000001": {"note": "example", "added": "2026-04-01"},
            }
        }
        result = validate_watchlist(data)
        assert "202601150000001" in result["listings"]

    def test_missing_listings_key_defaults_to_empty(self):
        """Missing listings key defaults to empty."""
        assert validate_watchlist({}) == {"listings": {}}


class TestMalformed:
    """Malformed test cases."""
    @pytest.mark.parametrize(
        "data,needle",
        [
            ([], "must contain a JSON object"),
            ({"listings": "not-a-dict"}, "'listings' must be an object"),
            ({"listings": {"abc": "not-a-dict"}}, "must be an object"),
        ],
    )
    def test_bad_shapes_fail_loudly(self, data, needle):
        """Bad shapes fail loudly."""
        with pytest.raises(SystemExit) as exc:
            validate_watchlist(data, source="fixture")
        assert needle in str(exc.value)
        assert "fixture" in str(exc.value)

    def test_valid_value_with_arbitrary_payload(self):
        """Valid value with arbitrary payload."""
        # listings[k] is a dict, even if its inner shape is freeform.
        result = validate_watchlist({"listings": {"123": {"note": 1}}})
        assert result == {"listings": {"123": {"note": 1}}}
