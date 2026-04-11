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

import hashlib
import json
import re
from datetime import date, timedelta

_AUTOTRADER_ID_RE = re.compile(r"^\d{10,20}$")


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


def extract_listing_id(url, source=None):
    """Return a stable, cross-run identifier for a listing URL.

    AutoTrader URLs contain a long numeric id after ``/car-details/`` that is
    the canonical listing id; strip any trailing slash or query string and
    return it verbatim. For any other source, return ``{source}:{sha1(url)[:12]}``
    so unknown sites still yield a stable id that survives re-scrapes. Returns
    an empty string for empty or missing input.
    """
    if not url:
        return ""
    if "autotrader.co.uk/car-details/" in url:
        tail = url.split("/car-details/", 1)[1]
        tail = tail.split("?", 1)[0].split("#", 1)[0].strip("/")
        segment = tail.split("/", 1)[0]
        if segment and _AUTOTRADER_ID_RE.match(segment):
            return segment
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    label = source if source else "url"
    return f"{label}:{digest}"


def snapshot_diff(previous_rows, current_rows):
    """Diff two snapshots by listing id.

    Each input is an iterable of dict rows with at least ``listing_id`` and
    ``price`` keys. Rows without a listing id are ignored (fallback path for
    legacy CSVs). Returns a dict with three keys:

    * ``new`` - listing ids present in current but not previous
    * ``removed`` - listing ids present in previous but not current
    * ``price_changed`` - list of ``{id, old, new, delta}`` for rows whose
      price differs between snapshots
    """
    prev_by_id = {r["listing_id"]: r for r in previous_rows if r.get("listing_id")}
    curr_by_id = {r["listing_id"]: r for r in current_rows if r.get("listing_id")}

    new_ids = [lid for lid in curr_by_id if lid not in prev_by_id]
    removed_ids = [lid for lid in prev_by_id if lid not in curr_by_id]

    price_changed = []
    for lid, curr in curr_by_id.items():
        prev = prev_by_id.get(lid)
        if not prev:
            continue
        old_price = int(prev.get("price", 0) or 0)
        new_price = int(curr.get("price", 0) or 0)
        if old_price != new_price and old_price and new_price:
            price_changed.append({
                "id": lid,
                "old": old_price,
                "new": new_price,
                "delta": new_price - old_price,
            })

    return {"new": new_ids, "removed": removed_ids, "price_changed": price_changed}


def rolling_window(dated_snapshots, today, days=28):
    """Build a day-by-day time series over the last ``days`` days ending ``today``.

    ``dated_snapshots`` is a list of ``{date, ids, median_price}`` dicts, where
    ``ids`` is a set of listing ids active on that date. The function walks
    day by day from ``today - days + 1`` up to ``today``. On a day with no
    snapshot, the previous known state carries forward (active count and
    median). On a day with a snapshot, ``new`` and ``removed`` are computed
    against the previous known id set. Returns a list of
    ``{date, active, new, removed, median}`` dicts, one per day.
    """
    by_date = {s["date"]: s for s in dated_snapshots}
    ordered_dates = sorted(by_date.keys())

    prior_ids = set()
    prior_median = 0
    for d in ordered_dates:
        if d < today - timedelta(days=days - 1):
            prior_ids = set(by_date[d]["ids"])
            prior_median = by_date[d].get("median_price", 0)
        else:
            break

    series = []
    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        snap = by_date.get(day)
        if snap is not None:
            curr_ids = set(snap["ids"])
            new_count = len(curr_ids - prior_ids) if prior_ids or series else 0
            removed_count = len(prior_ids - curr_ids) if prior_ids else 0
            active = len(curr_ids)
            median = snap.get("median_price", prior_median)
            prior_ids = curr_ids
            prior_median = median
        else:
            active = len(prior_ids)
            new_count = 0
            removed_count = 0
            median = prior_median
        series.append({
            "date": day.isoformat(),
            "active": active,
            "new": new_count,
            "removed": removed_count,
            "median": median,
        })
    return series


def load_watchlist(path):
    """Load a watchlist JSON file and validate its shape.

    Returns ``{"listings": {}}`` when ``path`` is None or does not exist.
    Raises ``SystemExit`` with a descriptive message when the file exists but
    is malformed, mirroring the loud-validation pattern used for the listing
    state sidecar in build_dashboard.py.
    """
    import os

    if not path or not os.path.isfile(path):
        return {"listings": {}}
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit(
            f"Watchlist file {path} must contain a JSON object, "
            f"got {type(data).__name__}"
        )
    listings = data.get("listings", {})
    if not isinstance(listings, dict):
        raise SystemExit(
            f"Watchlist file {path}: 'listings' must be an object, "
            f"got {type(listings).__name__}"
        )
    for k, v in listings.items():
        if not isinstance(k, str):
            raise SystemExit(
                f"Watchlist file {path}: 'listings' keys must be strings, "
                f"got {k!r}"
            )
        if not isinstance(v, dict):
            raise SystemExit(
                f"Watchlist file {path}: 'listings[{k}]' must be an object, "
                f"got {type(v).__name__}"
            )
    return {"listings": listings}


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
