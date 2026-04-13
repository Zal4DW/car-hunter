"""Unit tests for dashboard_lib.compute_spec_premiums."""

import pytest

from dashboard_lib import compute_spec_premiums


class TestComputeSpecPremiums:
    """Premium derivation from value deviation with/without each spec."""

    def test_returns_one_entry_per_spec(self):
        """One result per spec option."""
        rows = [
            {"has_sunroof": True, "value_deviation": 2000},
            {"has_sunroof": True, "value_deviation": 1500},
            {"has_sunroof": True, "value_deviation": 1700},
            {"has_sunroof": False, "value_deviation": -500},
            {"has_sunroof": False, "value_deviation": -300},
            {"has_sunroof": False, "value_deviation": -700},
        ]
        spec_options = [{"key": "has_sunroof", "label": "Sunroof", "weight": 1}]
        result = compute_spec_premiums(rows, spec_options)
        assert len(result) == 1
        assert result[0]["label"] == "Sunroof"

    def test_premium_is_delta_of_average_deviation(self):
        """Premium = avg(with) - avg(without) rounded to int."""
        rows = [
            {"has_sunroof": True, "value_deviation": 2000},
            {"has_sunroof": True, "value_deviation": 1000},
            {"has_sunroof": True, "value_deviation": 1500},
            {"has_sunroof": False, "value_deviation": 0},
            {"has_sunroof": False, "value_deviation": 0},
            {"has_sunroof": False, "value_deviation": 0},
        ]
        spec_options = [{"key": "has_sunroof", "label": "Sunroof", "weight": 1}]
        result = compute_spec_premiums(rows, spec_options)
        assert result[0]["premium"] == 1500  # (2000+1000+1500)/3 - 0

    def test_insufficient_data_flags_the_spec(self):
        """Fewer than 3 with or 3 without flags 'insufficient'."""
        rows = [
            {"has_sunroof": True, "value_deviation": 2000},
            {"has_sunroof": True, "value_deviation": 1500},
            {"has_sunroof": False, "value_deviation": -500},
            {"has_sunroof": False, "value_deviation": -300},
            {"has_sunroof": False, "value_deviation": -700},
        ]
        spec_options = [{"key": "has_sunroof", "label": "Sunroof", "weight": 1}]
        result = compute_spec_premiums(rows, spec_options)
        assert result[0].get("insufficient") is True
        assert result[0]["premium"] == 0

    def test_empty_rows_flags_every_spec_insufficient(self):
        """Zero rows means every spec is insufficient."""
        spec_options = [
            {"key": "has_sunroof", "label": "Sunroof", "weight": 1},
            {"key": "has_audio", "label": "Audio", "weight": 2},
        ]
        result = compute_spec_premiums([], spec_options)
        assert len(result) == 2
        assert all(r.get("insufficient") for r in result)
