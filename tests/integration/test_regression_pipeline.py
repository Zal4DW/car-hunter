"""Integration tests that combine multiple dashboard_lib functions.

These drive the same regression pipeline the builder uses, over the synthetic
Acme Bolt EV fixture, and assert the results are sensible. No subprocess, no
HTML output - that belongs in the e2e layer.
"""

import csv

import pytest

from dashboard_lib import (
    build_feature_matrix,
    fit_poly2,
    ols_regression,
    spec_score,
)


def _load_rows(csv_path, spec_options):
    """Load rows."""
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for r in reader:
            row = {
                "variant": r["variant"],
                "price": int(r["price"]),
                "age_years": float(r["age_years"]),
                "age_months": round(float(r["age_years"]) * 12, 1),
                "mileage": int(r["mileage"]),
                "is_brand_new_stock": r["is_brand_new_stock"] == "True",
            }
            for spec in spec_options:
                row[spec["key"]] = r[spec["key"]] == "True"
            row["spec_score"] = spec_score(row, spec_options)
            rows.append(row)
    return rows


def _tier_features(variants):
    """Tier features."""
    return [
        {"name": f"is_tier_{v['tier']}", "tier": v["tier"], "variant_name": v["name"]}
        for v in variants
        if v["tier"] > 0
    ]


@pytest.fixture
def rows(fixture_csv_path, spec_options):
    """Rows."""
    return _load_rows(fixture_csv_path, spec_options)


@pytest.fixture
def reg_rows(rows):
    """Reg rows."""
    return [r for r in rows if not r["is_brand_new_stock"] and r["age_years"] >= 0.5]


class TestFixtureIntegrity:
    """Fixture integrity test cases."""
    def test_fixture_contains_expected_row_count(self, rows):
        """Fixture contains expected row count."""
        assert len(rows) == 19

    def test_fixture_separates_new_stock_from_used(self, rows, reg_rows):
        """Fixture separates new stock from used."""
        assert len(reg_rows) == 18
        new_stock = [r for r in rows if r["is_brand_new_stock"]]
        assert len(new_stock) == 1

    def test_both_variants_present_in_regression_data(self, reg_rows):
        """Both variants present in regression data."""
        variants = {r["variant"] for r in reg_rows}
        assert variants == {"Bolt Base", "Bolt Sport"}


class TestDepreciationRegression:
    """Depreciation regression test cases."""
    def test_regression_produces_sensible_coefficients(
        self, reg_rows, loaded_profile, variant_by_name
    ):
        """Regression produces sensible coefficients."""
        tier_features = _tier_features(loaded_profile["variants"])
        X, y = build_feature_matrix(reg_rows, variant_by_name, tier_features)
        coeffs, r_squared, _ = ols_regression(X, y)

        intercept, age_coef, mileage_coef, spec_coef, tier1_coef = coeffs

        assert r_squared > 0.95, f"R² = {r_squared:.3f} is unexpectedly low for synthetic data"
        assert age_coef < 0, "age coefficient should be negative (older = cheaper)"
        assert mileage_coef < 0, "mileage coefficient should be negative (higher mileage = cheaper)"
        assert tier1_coef > 0, "Sport tier should command a price premium over Base"
        assert 30000 < intercept < 70000, "intercept should sit roughly within observed price range"

    def test_feature_matrix_shape_matches_inputs(
        self, reg_rows, loaded_profile, variant_by_name
    ):
        """Feature matrix shape matches inputs."""
        tier_features = _tier_features(loaded_profile["variants"])
        X, y = build_feature_matrix(reg_rows, variant_by_name, tier_features)
        assert len(X) == len(reg_rows)
        assert len(y) == len(reg_rows)
        # [intercept, age_months, mileage, spec_score] + 1 tier feature
        assert len(X[0]) == 5


class TestDepreciationCurvePerVariant:
    """Depreciation curve per variant test cases."""
    def test_base_variant_depreciation_curve_slopes_downward(self, reg_rows):
        """Base variant depreciation curve slopes downward."""
        base_points = [
            {"age_months": r["age_months"], "price": r["price"]}
            for r in reg_rows
            if r["variant"] == "Bolt Base"
        ]
        _, linear_term, _ = fit_poly2(base_points)
        assert linear_term < 0

    def test_sport_variant_depreciation_curve_slopes_downward(self, reg_rows):
        """Sport variant depreciation curve slopes downward."""
        sport_points = [
            {"age_months": r["age_months"], "price": r["price"]}
            for r in reg_rows
            if r["variant"] == "Bolt Sport"
        ]
        _, linear_term, _ = fit_poly2(sport_points)
        assert linear_term < 0
