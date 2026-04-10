"""Unit tests for dashboard_lib.parse_listing_date."""

from datetime import date

import pytest

from dashboard_lib import parse_listing_date


class TestValidIds:
    def test_extracts_date_from_valid_listing_id(self):
        assert parse_listing_date("202602179980029") == date(2026, 2, 17)

    def test_accepts_exactly_eight_digits(self):
        assert parse_listing_date("20250101") == date(2025, 1, 1)

    def test_ignores_trailing_characters(self):
        assert parse_listing_date("20240615ABC123") == date(2024, 6, 15)


class TestInvalidIds:
    @pytest.mark.parametrize("bad_input", [None, "", "1234567"])
    def test_returns_none_for_short_or_missing_id(self, bad_input):
        assert parse_listing_date(bad_input) is None

    def test_returns_none_for_non_numeric_prefix(self):
        assert parse_listing_date("ABCDEFGH12345") is None

    def test_returns_none_for_invalid_month(self):
        assert parse_listing_date("20251301000000") is None

    def test_returns_none_for_invalid_day(self):
        assert parse_listing_date("20250132000000") is None

    def test_returns_none_for_day_zero(self):
        assert parse_listing_date("20250100000000") is None

    def test_returns_none_for_month_zero(self):
        assert parse_listing_date("20250001000000") is None
