"""Unit tests for dashboard_lib.compute_pm_trend."""

import pytest

from dashboard_lib import compute_pm_trend


def _row(mileage, price):
    return {"mileage": mileage, "price": price}


class TestComputePmTrend:
    def test_too_few_rows_returns_empty(self):
        """5 or fewer rows produces no trendline."""
        rows = [_row(m, 30000 - m) for m in range(5)]
        trend, singular = compute_pm_trend(rows)
        assert trend == []
        assert singular == []

    def test_enough_rows_returns_two_endpoints(self):
        """A valid fit returns two points at min/max mileage."""
        rows = [_row(m * 1000, 40000 - m * 100) for m in range(10)]
        trend, singular = compute_pm_trend(rows)
        assert len(trend) == 2
        assert trend[0]["x"] == 0
        assert trend[1]["x"] == 9000
        assert singular == []

    def test_singular_mileage_reports_singular_and_empty_trend(self):
        """All listings at identical mileage → singular, return empty trend
        plus the singular column list so the caller can warn.
        """
        rows = [_row(15000, 40000 - i * 100) for i in range(10)]
        trend, singular = compute_pm_trend(rows)
        assert trend == []
        assert len(singular) >= 1

    def test_empty_rows_returns_empty(self):
        trend, singular = compute_pm_trend([])
        assert trend == []
        assert singular == []
