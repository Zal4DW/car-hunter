"""Unit tests for dashboard_lib.compute_pm_trend."""

import pytest

from dashboard_lib import compute_pm_trend


def _row(mileage, price):
    return {"mileage": mileage, "price": price}


class TestComputePmTrend:
    def test_too_few_rows_returns_empty(self):
        """5 or fewer rows produces no trendline."""
        rows = [_row(m, 30000 - m) for m in range(5)]
        assert compute_pm_trend(rows) == []

    def test_enough_rows_returns_two_endpoints(self):
        """A valid fit returns two points at min/max mileage."""
        rows = [_row(m * 1000, 40000 - m * 100) for m in range(10)]
        result = compute_pm_trend(rows)
        assert len(result) == 2
        assert result[0]["x"] == 0
        assert result[1]["x"] == 9000

    def test_singular_mileage_returns_empty(self):
        """All listings at identical mileage → singular, return empty."""
        rows = [_row(15000, 40000 - i * 100) for i in range(10)]
        result = compute_pm_trend(rows)
        assert result == []

    def test_empty_rows_returns_empty(self):
        assert compute_pm_trend([]) == []
