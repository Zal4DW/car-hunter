#!/usr/bin/env python3
"""
Car Hunter - Dashboard Library

Pure functions extracted from build_dashboard.py for testability.
No I/O, no globals, no argparse. Every function is deterministic given
its inputs and safe to import from tests.

The main builder (`build_dashboard.py`) imports from this module. Keep
anything with side-effects (file loading, HTML generation, printing)
out of here.
"""

import json
from datetime import date


def parse_listing_date(listing_id):
    """Extract a date from the first 8 digits of an AutoTrader listing ID.

    AutoTrader encodes the listing creation date in the first 8 characters
    of the numeric listing ID as YYYYMMDD. Returns a date object, or None
    if the ID is missing, too short, or contains an invalid date.
    """
    if not listing_id or len(listing_id) < 8:
        return None
    ds = listing_id[:8]
    try:
        y, m, d = int(ds[:4]), int(ds[4:6]), int(ds[6:8])
        if d > 31 or m > 12 or d < 1 or m < 1:
            return None
        return date(y, m, d)
    except (ValueError, IndexError):
        return None


def ols_regression(X, y):
    """Ordinary least squares via normal equations with Gaussian elimination.

    Solves b = (X'X)^-1 X'y without any external libraries.
    Returns (coefficients, r_squared). Uses partial pivoting for numerical
    stability. Coefficients for singular/collinear columns are returned as
    zero rather than raising.
    """
    n = len(y)
    k = len(X[0])

    XtX = [[0.0] * k for _ in range(k)]
    for i in range(n):
        for j in range(k):
            for l in range(k):
                XtX[j][l] += X[i][j] * X[i][l]

    Xty = [0.0] * k
    for i in range(n):
        for j in range(k):
            Xty[j] += X[i][j] * y[i]

    aug = [XtX[i][:] + [Xty[i]] for i in range(k)]
    for col in range(k):
        max_row = max(range(col, k), key=lambda r: abs(aug[r][col]))
        aug[col], aug[max_row] = aug[max_row], aug[col]
        pivot = aug[col][col]
        if abs(pivot) < 1e-12:
            continue
        for j in range(col, k + 1):
            aug[col][j] /= pivot
        for row_idx in range(k):
            if row_idx == col:
                continue
            factor = aug[row_idx][col]
            for j in range(col, k + 1):
                aug[row_idx][j] -= factor * aug[col][j]

    coeffs = [aug[i][k] for i in range(k)]

    y_mean = sum(y) / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    ss_res = sum(
        (y[i] - sum(X[i][j] * coeffs[j] for j in range(k))) ** 2
        for i in range(n)
    )
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return coeffs, r_squared


def fit_poly2(points):
    """Fit y = a + bx + cx^2 via OLS over {age_months, price} pairs.

    Returns the three polynomial coefficients [a, b, c].
    """
    X = [[1, p["age_months"], p["age_months"] ** 2] for p in points]
    y = [p["price"] for p in points]
    coeffs, _ = ols_regression(X, y)
    return coeffs


def js_safe(obj):
    """JSON-serialise an object for embedding in the dashboard JS.

    Uses `default=str` so date/datetime values survive without raising.
    """
    return json.dumps(obj, default=str)


def spec_labels(row, spec_options):
    """Return the human-readable labels for every spec option present on a row."""
    return [spec["label"] for spec in spec_options if row.get(spec["key"])]


def spec_score(row, spec_options):
    """Weighted sum of a row's present spec options, used as a regression feature."""
    return sum(
        (1 if row.get(spec["key"]) else 0) * spec["weight"]
        for spec in spec_options
    )


def get_tier_value(row, variant_by_name):
    """Return the numeric tier for a row's variant, or 0 if the variant is unknown."""
    v = variant_by_name.get(row["variant"])
    return v["tier"] if v else 0


def retained_pct(price, new_price):
    """Percentage of the original RRP retained at the current asking price.

    Returns 0 when new_price is zero or missing to avoid divide-by-zero.
    """
    if not new_price or new_price <= 0:
        return 0
    return round((price / new_price) * 100, 1)


def build_feature_matrix(reg_rows, variant_by_name, tier_features):
    """Assemble the OLS feature matrix used by the depreciation regression.

    Each row becomes [intercept, age_months, mileage, spec_score, is_tier_1, is_tier_2, ...].
    The tier_features argument is a list of dicts with a `tier` key, ordered to match
    the columns the builder expects. Returns (X, y).
    """
    X = []
    y = []
    for r in reg_rows:
        tier = get_tier_value(r, variant_by_name)
        features = [1, r["age_months"], r["mileage"], r["spec_score"]]
        for tf in tier_features:
            features.append(1 if tier == tf["tier"] else 0)
        X.append(features)
        y.append(r["price"])
    return X, y
