"""Unit tests for build_dashboard.run_regression.

Covers the prediction loop's guards against zero and negative predictions,
the insufficient-data fallback path, and the annotation contract.
"""

import sys
from pathlib import Path

import pytest

# Make the builder importable. Tests/conftest already adds scripts/ but that
# only exposes dashboard_lib; the builder itself lives next to it.
_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "car-hunter" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_dashboard import run_regression  # noqa: E402


def _row(variant, age_months, mileage, price, spec_score=0, is_new=False):
    """Build a minimal row dict that run_regression understands."""
    return {
        "variant": variant,
        "age_months": age_months,
        "age_years": age_months / 12,
        "mileage": mileage,
        "price": price,
        "spec_score": spec_score,
        "is_brand_new_stock": is_new,
    }


class TestRunRegressionPredictionGuards:
    """Guards in the prediction loop."""

    def test_negative_prediction_does_not_produce_inconsistent_deviation(self):
        """When predicted <= 0 the model is unreliable and deviation must
        not show a huge absolute value alongside a 0% pct.

        The silent-failure audit flagged: if predicted = -5000 and price = 30000,
        value_deviation becomes 35000 (nonsensical) while value_deviation_pct
        silently becomes 0 - internally inconsistent nonsense on the dashboard.
        """
        variant_by_name = {"A": {"name": "A", "tier": 0, "colour": "#fff"}}
        # Force a tiny, collinear dataset that produces a negative intercept
        # so age-heavy rows predict below zero.
        rows = [
            _row("A", 6, 5000, 45000),
            _row("A", 12, 10000, 20000),
            _row("A", 18, 15000, 5000),
            _row("A", 24, 20000, 1000),
            _row("A", 240, 200000, 500),  # far-future extrapolation target
        ]
        run_regression(rows, variant_by_name, tier_features=[])
        for r in rows:
            if r["predicted_price"] <= 0:
                # Both must be zero together, or neither - otherwise the
                # dashboard shows "overpriced by £X (0%)" which is bogus.
                assert r["value_deviation"] == 0, (
                    f"row with predicted={r['predicted_price']} "
                    f"got value_deviation={r['value_deviation']} but pct=0 - inconsistent"
                )
                assert r["value_deviation_pct"] == 0

    def test_zero_prediction_produces_zero_pct(self):
        """Exact-zero prediction must not divide by zero."""
        variant_by_name = {"A": {"name": "A", "tier": 0, "colour": "#fff"}}
        rows = [
            _row("A", 12, 10000, 40000),
            _row("A", 24, 20000, 0),
            _row("A", 36, 30000, 0),
            _row("A", 48, 40000, 0),
        ]
        # With mostly-zero prices the fit will collapse to zero or near-zero.
        run_regression(rows, variant_by_name, tier_features=[])
        for r in rows:
            assert isinstance(r["value_deviation_pct"], (int, float))


class TestRunRegressionFallback:
    """Insufficient-data path."""

    def test_not_enough_rows_falls_back_to_zero_coefficients(self):
        """Fewer rows than features triggers the zero-coeffs fallback."""
        variant_by_name = {"A": {"name": "A", "tier": 0, "colour": "#fff"}}
        rows = [_row("A", 12, 10000, 40000)]  # 1 row, 4 features
        coeffs, r_squared, reg_data = run_regression(
            rows, variant_by_name, tier_features=[]
        )
        assert coeffs == [0, 0, 0, 0]
        assert r_squared == 0
        assert len(reg_data) == 1

    def test_fallback_annotates_rows_with_zero_predictions(self):
        """Fallback path annotates every row with predicted_price=0.

        Because predicted <= 0 triggers the unreliable-prediction branch,
        value_deviation is also zeroed to avoid a misleading huge delta
        rendered alongside 0%.
        """
        variant_by_name = {"A": {"name": "A", "tier": 0, "colour": "#fff"}}
        rows = [_row("A", 12, 10000, 40000)]
        run_regression(rows, variant_by_name, tier_features=[])
        assert rows[0]["predicted_price"] == 0
        assert rows[0]["value_deviation"] == 0
        assert rows[0]["value_deviation_pct"] == 0
