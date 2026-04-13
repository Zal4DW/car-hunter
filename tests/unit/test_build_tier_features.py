"""Unit tests for dashboard_lib.build_tier_features."""

import pytest

from dashboard_lib import build_tier_features


class TestBuildTierFeatures:
    def test_tier_zero_variants_excluded(self):
        variants = [
            {"name": "Base", "tier": 0, "colour": "#000"},
            {"name": "Sport", "tier": 1, "colour": "#f00"},
        ]
        result = build_tier_features(variants)
        assert len(result) == 1
        assert result[0]["variant_name"] == "Sport"

    def test_feature_name_is_is_tier_N(self):
        variants = [
            {"name": "Sport", "tier": 1, "colour": "#f00"},
            {"name": "GT", "tier": 2, "colour": "#0f0"},
        ]
        result = build_tier_features(variants)
        assert result[0]["name"] == "is_tier_1"
        assert result[1]["name"] == "is_tier_2"

    def test_empty_variants_returns_empty(self):
        assert build_tier_features([]) == []

    def test_all_tier_zero_returns_empty(self):
        variants = [{"name": "Base", "tier": 0, "colour": "#000"}]
        assert build_tier_features(variants) == []

    def test_duplicate_tiers_are_deduplicated(self):
        """Two variants sharing the same tier must yield ONE feature column.

        Otherwise the regression sees duplicate columns (is_tier_1, is_tier_1)
        which makes X'X singular and falsely triggers the collinearity warning.
        """
        variants = [
            {"name": "Sport", "tier": 1, "colour": "#f00"},
            {"name": "Sport Plus", "tier": 1, "colour": "#a00"},
            {"name": "GT", "tier": 2, "colour": "#0f0"},
        ]
        result = build_tier_features(variants)
        names = [f["name"] for f in result]
        assert names == ["is_tier_1", "is_tier_2"]
        # First-seen variant wins as the representative
        assert result[0]["variant_name"] == "Sport"
