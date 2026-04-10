"""Unit tests for dashboard_lib.ols_regression."""

import math

import pytest

from dashboard_lib import ols_regression


class TestPerfectFits:
    def test_recovers_known_coefficients_for_simple_linear_model(self):
        # y = 3 + 2x with no noise
        X = [[1, x] for x in range(1, 11)]
        y = [3 + 2 * x for x in range(1, 11)]
        coeffs, r2 = ols_regression(X, y)
        assert coeffs[0] == pytest.approx(3.0, abs=1e-9)
        assert coeffs[1] == pytest.approx(2.0, abs=1e-9)
        assert r2 == pytest.approx(1.0, abs=1e-9)

    def test_recovers_multivariate_coefficients(self):
        # y = 10 - 0.5*x1 + 3*x2
        points = [
            (1, 4),
            (2, 7),
            (3, 1),
            (4, 9),
            (5, 2),
            (6, 8),
            (7, 5),
            (8, 3),
        ]
        X = [[1, x1, x2] for x1, x2 in points]
        y = [10 - 0.5 * x1 + 3 * x2 for x1, x2 in points]
        coeffs, r2 = ols_regression(X, y)
        assert coeffs[0] == pytest.approx(10.0, abs=1e-6)
        assert coeffs[1] == pytest.approx(-0.5, abs=1e-6)
        assert coeffs[2] == pytest.approx(3.0, abs=1e-6)
        assert r2 == pytest.approx(1.0, abs=1e-9)


class TestNoisyFits:
    def test_r_squared_between_zero_and_one_for_noisy_data(self):
        X = [[1, x] for x in range(1, 21)]
        y = [2 * x + (1 if x % 2 == 0 else -1) for x in range(1, 21)]
        _, r2 = ols_regression(X, y)
        assert 0 < r2 < 1

    def test_intercept_only_model_returns_mean(self):
        X = [[1], [1], [1], [1]]
        y = [5, 7, 9, 11]
        coeffs, r2 = ols_regression(X, y)
        assert coeffs[0] == pytest.approx(8.0)
        assert r2 == pytest.approx(0.0)


class TestEdgeCases:
    def test_zero_variance_y_returns_r_squared_zero(self):
        X = [[1, x] for x in range(1, 6)]
        y = [5, 5, 5, 5, 5]
        coeffs, r2 = ols_regression(X, y)
        assert coeffs[0] == pytest.approx(5.0, abs=1e-9)
        assert coeffs[1] == pytest.approx(0.0, abs=1e-9)
        assert r2 == 0

    def test_collinear_column_does_not_crash(self):
        # x2 = 2*x1 - perfectly collinear
        X = [[1, 1, 2], [1, 2, 4], [1, 3, 6], [1, 4, 8]]
        y = [5, 10, 15, 20]
        coeffs, _ = ols_regression(X, y)
        # Should return finite values, not NaN or raise
        assert all(math.isfinite(c) for c in coeffs)

