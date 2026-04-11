"""Unit tests for the spec helpers, tier lookup, and retained-pct helper."""

import pytest

from dashboard_lib import (
    get_tier_value,
    retained_pct,
    spec_labels,
    spec_score,
)


class TestSpecLabels:
    """Spec labels test cases."""
    def test_returns_labels_for_present_specs_only(self, spec_options):
        """Returns labels for present specs only."""
        row = {"has_sunroof": True, "has_premium_audio": False, "has_heated_seats": True}
        assert spec_labels(row, spec_options) == ["Panoramic Sunroof", "Heated Seats"]

    def test_empty_when_no_specs_present(self, spec_options):
        """Empty when no specs present."""
        row = {"has_sunroof": False, "has_premium_audio": False, "has_heated_seats": False}
        assert spec_labels(row, spec_options) == []

    def test_missing_keys_treated_as_absent(self, spec_options):
        """Missing keys treated as absent."""
        assert spec_labels({}, spec_options) == []


class TestSpecScore:
    """Spec score test cases."""
    def test_weighted_sum_matches_profile_weights(self, spec_options):
        """Weighted sum matches profile weights."""
        # sunroof=1, premium_audio=2, heated_seats=1
        row = {"has_sunroof": True, "has_premium_audio": True, "has_heated_seats": False}
        assert spec_score(row, spec_options) == 3

    def test_empty_row_scores_zero(self, spec_options):
        """Empty row scores zero."""
        assert spec_score({}, spec_options) == 0

    def test_all_specs_present_gives_maximum(self, spec_options):
        """All specs present gives maximum."""
        row = {"has_sunroof": True, "has_premium_audio": True, "has_heated_seats": True}
        assert spec_score(row, spec_options) == 4


class TestGetTierValue:
    """Get tier value test cases."""
    def test_returns_tier_for_known_variant(self, variant_by_name):
        """Returns tier for known variant."""
        assert get_tier_value({"variant": "Bolt Base"}, variant_by_name) == 0
        assert get_tier_value({"variant": "Bolt Sport"}, variant_by_name) == 1

    def test_unknown_variant_defaults_to_zero(self, variant_by_name):
        """Unknown variant defaults to zero."""
        assert get_tier_value({"variant": "Phantom GT"}, variant_by_name) == 0


class TestRetainedPct:
    """Retained pct test cases."""
    def test_computes_percentage_rounded_to_one_decimal(self):
        """Computes percentage rounded to one decimal."""
        assert retained_pct(30000, 45000) == pytest.approx(66.7)

    def test_returns_zero_when_new_price_missing(self):
        """Returns zero when new price missing."""
        assert retained_pct(30000, 0) == 0
        assert retained_pct(30000, None) == 0

    def test_negative_new_price_returns_zero(self):
        """Negative new price returns zero."""
        assert retained_pct(30000, -1000) == 0

    def test_full_retention_returns_one_hundred(self):
        """Full retention returns one hundred."""
        assert retained_pct(45000, 45000) == 100.0
