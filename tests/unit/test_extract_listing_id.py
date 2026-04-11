"""Unit tests for dashboard_lib.extract_listing_id."""

import pytest

from dashboard_lib import extract_listing_id


class TestAutotrader:
    def test_extracts_numeric_id_from_clean_url(self):
        url = "https://www.autotrader.co.uk/car-details/202601150000001"
        assert extract_listing_id(url) == "202601150000001"

    def test_strips_trailing_slash(self):
        url = "https://www.autotrader.co.uk/car-details/202601150000001/"
        assert extract_listing_id(url) == "202601150000001"

    def test_strips_query_string(self):
        url = "https://www.autotrader.co.uk/car-details/202601150000001?sort=price"
        assert extract_listing_id(url) == "202601150000001"

    def test_strips_fragment(self):
        url = "https://www.autotrader.co.uk/car-details/202601150000001#gallery"
        assert extract_listing_id(url) == "202601150000001"


class TestFallback:
    def test_unknown_url_yields_stable_hash(self):
        url = "https://cazoo.co.uk/used-cars/acme-bolt/xyz"
        first = extract_listing_id(url, source="cazoo")
        second = extract_listing_id(url, source="cazoo")
        assert first == second
        assert first.startswith("cazoo:")
        assert len(first.split(":", 1)[1]) == 12

    def test_different_urls_yield_different_hashes(self):
        a = extract_listing_id("https://example.com/a", source="x")
        b = extract_listing_id("https://example.com/b", source="x")
        assert a != b

    def test_missing_source_uses_url_label(self):
        result = extract_listing_id("https://example.com/x")
        assert result.startswith("url:")


class TestEmpty:
    @pytest.mark.parametrize("bad", [None, ""])
    def test_returns_empty_string(self, bad):
        assert extract_listing_id(bad) == ""
