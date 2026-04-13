"""Unit tests for dashboard_lib.compute_dep_curves."""

import pytest

from dashboard_lib import compute_dep_curves


def _row(variant, age_months, price, mileage=10000, location="Testville", is_new=False):
    return {
        "variant": variant,
        "age_months": age_months,
        "price": price,
        "mileage": mileage,
        "location": location,
        "is_brand_new_stock": is_new,
    }


class TestComputeDepCurves:
    """Per-variant depreciation curve fitting."""

    def test_excludes_brand_new_stock(self):
        """is_brand_new_stock rows are excluded from the curve points."""
        rows = [_row("A", 6, 45000, is_new=True)]
        rows += [_row("A", m, 40000 - 100 * m) for m in range(6, 60, 6)]
        result = compute_dep_curves(rows)
        assert "A" in result
        # 9 used rows, not 10
        assert len(result["A"]["points"]) == 9

    def test_variant_with_fewer_than_five_points_is_skipped(self):
        """Variants with <5 used rows are dropped (too few to fit)."""
        rows = [_row("A", m, 40000 - 100 * m) for m in range(6, 24, 6)]  # 3 rows
        result = compute_dep_curves(rows)
        assert "A" not in result

    def test_happy_path_returns_curve_poly_and_points(self):
        """Result contains curve, poly, flatten_month, and points for each variant."""
        rows = [_row("A", m, 45000 - 200 * m) for m in range(6, 72, 6)]
        result = compute_dep_curves(rows)
        assert set(result["A"].keys()) == {"points", "curve", "poly", "flatten_month"}
        assert len(result["A"]["poly"]) == 3
        assert len(result["A"]["curve"]) > 0

    def test_multiple_variants_each_get_own_curve(self):
        """A mixed variant list produces one curve per eligible variant."""
        rows = [_row("A", m, 40000 - 200 * m) for m in range(6, 48, 6)]
        rows += [_row("B", m, 60000 - 300 * m) for m in range(6, 48, 6)]
        result = compute_dep_curves(rows)
        assert "A" in result
        assert "B" in result
