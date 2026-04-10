"""Unit tests for dashboard_lib.fit_poly2."""

import pytest

from dashboard_lib import fit_poly2


def _points(pairs):
    return [{"age_months": am, "price": p} for am, p in pairs]


class TestPoly2Fit:
    def test_recovers_quadratic_coefficients(self):
        # price = 50000 - 500 * months + 5 * months^2
        pairs = [(m, 50000 - 500 * m + 5 * m * m) for m in range(6, 61, 6)]
        a, b, c = fit_poly2(_points(pairs))
        assert a == pytest.approx(50000, abs=1e-3)
        assert b == pytest.approx(-500, abs=1e-3)
        assert c == pytest.approx(5, abs=1e-4)

    def test_linear_data_yields_near_zero_quadratic_term(self):
        pairs = [(m, 40000 - 300 * m) for m in range(6, 61, 6)]
        _, _, c = fit_poly2(_points(pairs))
        assert abs(c) < 1e-6

    def test_monotonically_decreasing_price_gives_negative_slope(self):
        pairs = [
            (6, 45000),
            (12, 42000),
            (18, 39000),
            (24, 36000),
            (30, 33000),
            (36, 30000),
        ]
        _, b, _ = fit_poly2(_points(pairs))
        assert b < 0
