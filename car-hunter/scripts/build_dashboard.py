#!/usr/bin/env python3
"""
Car Hunter — Buyer Intelligence Dashboard Builder

Config-driven dashboard generator. Reads a car-profile.json and CSV data file,
runs OLS regression, computes value scores and spec premiums, and generates
a self-contained HTML dashboard with Chart.js.

Usage:
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py --profile <path_to_profile.json> --csv <path_to_csv> [--output <path_to_html>]

If --output is omitted, writes to {profile_name}-dashboard.html in the same
directory as the CSV file.
"""

import argparse
import csv
import json
import math
import os
import sys
from datetime import date

# Pure functions live in dashboard_lib so they can be unit-tested without
# running the whole builder.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashboard_lib import (  # noqa: E402
    parse_listing_date,
    ols_regression,
    fit_poly2,
    js_safe,
    spec_labels as _spec_labels,
    spec_score as _spec_score,
    get_tier_value as _get_tier_value,
    retained_pct as _retained_pct,
    build_feature_matrix,
)

# ── Argument parsing ────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Build car value dashboard from profile and CSV data")
parser.add_argument("--profile", required=True, help="Path to car-profile.json")
parser.add_argument("--csv", required=True, help="Path to CSV data file")
parser.add_argument("--output", default=None, help="Output HTML path (default: auto-generated)")
parser.add_argument("--date", default=None, help="Override today's date (YYYY-MM-DD)")
parser.add_argument(
    "--listing-state",
    default=None,
    help="Path to a JSON file with listing_ids and price_changes dictionaries. "
    "If omitted, auto-detects {profile_name}-listing-state.json next to the CSV.",
)
args = parser.parse_args()

# ── Load profile ────────────────────────────────────────────────────

with open(args.profile, "r") as f:
    profile = json.load(f)

PROFILE_NAME = profile["profile_name"]
DISPLAY_NAME = profile["display_name"]
VARIANTS = profile["variants"]
GENERATIONS = profile["generations"]
SPEC_OPTIONS = profile["spec_options"]
SEARCH_FILTERS = profile["search_filters"]
DASHBOARD = profile["dashboard"]
REG_MAP = profile.get("reg_date_mapping", {})
LID_ENCODING = profile.get("listing_id_date_encoding", {"enabled": False})

# Build variant lookup
VARIANT_BY_NAME = {v["name"]: v for v in VARIANTS}
VARIANT_COLOURS = {v["name"]: v["colour"] for v in VARIANTS}

# Build generation new price lookup: {variant_name: new_price}
# Uses the first matching generation for each variant
NEW_PRICES = {}
for gen in GENERATIONS:
    for vname, price in gen.get("new_prices", {}).items():
        if vname not in NEW_PRICES:
            NEW_PRICES[vname] = price

# Output path
if args.output:
    OUTPUT_PATH = args.output
else:
    csv_dir = os.path.dirname(os.path.abspath(args.csv))
    OUTPUT_PATH = os.path.join(csv_dir, f"{PROFILE_NAME}-dashboard.html")

# Today's date
if args.date:
    y, m, d = map(int, args.date.split("-"))
    today = date(y, m, d)
else:
    today = date.today()

today_str = today.strftime("%d %B %Y")

# Decimal date for age calculations
TODAY_DECIMAL = today.year + (today.month - 1) / 12 + (today.day - 1) / 365.25

print(f"Profile: {DISPLAY_NAME}")
print(f"Variants: {', '.join(v['name'] for v in VARIANTS)}")
print(f"Spec options: {', '.join(s['label'] for s in SPEC_OPTIONS)}")
print(f"Date: {today_str}")

# ── Load and parse CSV ──────────────────────────────────────────────

rows = []
with open(args.csv, "r") as f:
    reader = csv.DictReader(f)
    for r in reader:
        row = {
            "variant": r["variant"],
            "generation": r.get("generation", ""),
            "price": int(r["price"]),
            "year": int(r["year"]),
            "reg": r.get("reg", ""),
            "reg_date": float(r.get("reg_date", 0)),
            "age_years": float(r.get("age_years", 0)),
            "age_months": round(float(r.get("age_years", 0)) * 12, 1),
            "mileage": int(r["mileage"]),
            "new_price": int(r.get("new_price", 0)),
            "depreciation_total": int(r.get("depreciation_total", 0)),
            "depreciation_pa": int(r.get("depreciation_pa", 0)),
            "location": r.get("location", ""),
            "is_brand_new_stock": r.get("is_brand_new_stock", "False") == "True",
        }

        # Load spec option booleans dynamically from profile
        for spec in SPEC_OPTIONS:
            key = spec["key"]
            row[key] = r.get(key, "False") == "True"

        # Options count
        row["options_count"] = int(r.get("options_count", 0))

        row["retained_pct"] = _retained_pct(row["price"], row["new_price"])

        rows.append(row)

print(f"Loaded {len(rows)} listings")

# ── Listing IDs and price changes ───────────────────────────────────
# Loaded from an optional sidecar JSON keyed by composite key {price}_{location}.
# The sidecar is resolved in this order:
#   1. --listing-state <path> CLI argument, if provided
#   2. {csv_dir}/{profile_name}-listing-state.json, if it exists
#   3. Neither - LISTING_IDS and PRICE_CHANGES stay empty (no trend arrows,
#      no days-on-market)
#
# Expected sidecar shape:
#   { "listing_ids":    { "42500_Testville": "20251202...", ... },
#     "price_changes":  { "42500_Testville": -500,          ... } }

LISTING_IDS = {}
PRICE_CHANGES = {}

_state_path = None
if args.listing_state:
    _state_path = args.listing_state
else:
    _csv_dir = os.path.dirname(os.path.abspath(args.csv))
    _auto = os.path.join(_csv_dir, f"{PROFILE_NAME}-listing-state.json")
    if os.path.isfile(_auto):
        _state_path = _auto

if _state_path:
    with open(_state_path, "r") as f:
        _state = json.load(f)

    # Fail loudly on malformed sidecars. Silent fallback to empty dicts
    # would hide typos in the file and leave the user wondering why
    # days-on-market never appears in their dashboard.
    if not isinstance(_state, dict):
        raise SystemExit(
            f"Listing state file {_state_path} must contain a JSON object, "
            f"got {type(_state).__name__}"
        )
    _lids = _state.get("listing_ids", {})
    _prices = _state.get("price_changes", {})
    if not isinstance(_lids, dict):
        raise SystemExit(
            f"Listing state file {_state_path}: 'listing_ids' must be an object, "
            f"got {type(_lids).__name__}"
        )
    if not isinstance(_prices, dict):
        raise SystemExit(
            f"Listing state file {_state_path}: 'price_changes' must be an object, "
            f"got {type(_prices).__name__}"
        )
    # Validate listing_ids values are strings (AutoTrader IDs are digit strings).
    for _k, _v in _lids.items():
        if not isinstance(_k, str) or not isinstance(_v, str):
            raise SystemExit(
                f"Listing state file {_state_path}: 'listing_ids' entries must map "
                f"string keys to string values, got {_k!r}: {_v!r}"
            )
    # price_changes values should be numeric (signed GBP delta).
    for _k, _v in _prices.items():
        if not isinstance(_k, str) or not isinstance(_v, (int, float)):
            raise SystemExit(
                f"Listing state file {_state_path}: 'price_changes' entries must map "
                f"string keys to numeric values, got {_k!r}: {_v!r}"
            )

    LISTING_IDS = _lids
    PRICE_CHANGES = _prices
    print(
        f"Loaded listing state from {_state_path}: "
        f"{len(LISTING_IDS)} listing IDs, {len(PRICE_CHANGES)} price changes"
    )

# ── Composite keys and listing tracking ─────────────────────────────

for row in rows:
    key = f"{row['price']}_{row['location']}"
    row["composite_key"] = key

    lid = LISTING_IDS.get(key)
    if lid and LID_ENCODING.get("enabled"):
        row["autotrader_url"] = f"https://www.autotrader.co.uk/car-details/{lid}"
        ld = parse_listing_date(lid)
        row["days_on_market"] = (today - ld).days if ld else None
    else:
        row["autotrader_url"] = None
        row["days_on_market"] = None

    row["price_change"] = PRICE_CHANGES.get(key, 0)

# ── Spec labels and scores ──────────────────────────────────────────

for row in rows:
    row["spec_labels"] = _spec_labels(row, SPEC_OPTIONS)
    row["spec_text"] = ", ".join(row["spec_labels"]) if row["spec_labels"] else "Base"
    row["spec_score"] = _spec_score(row, SPEC_OPTIONS)

# ── Determine variant tier features ─────────────────────────────────
# Build a list of tier feature names for tiers > 0

tier_features = []
for v in VARIANTS:
    if v["tier"] > 0:
        tier_features.append({
            "name": f"is_tier_{v['tier']}",
            "tier": v["tier"],
            "variant_name": v["name"],
        })

print(f"Tier features: {[tf['name'] for tf in tier_features]}")

# ── Multivariate regression ─────────────────────────────────────────
# price = b0 + b1*age_months + b2*mileage + b3*spec_score + b4*tier_1 + b5*tier_2 + ...

reg_data = [r for r in rows if not r["is_brand_new_stock"] and r["age_years"] >= 0.5]
print(f"Regression on {len(reg_data)} used listings (age >= 6 months)")


# Build feature matrix: [intercept, age_months, mileage, spec_score, tier_1, tier_2, ...]
feature_names = ["intercept", "age_months", "mileage", "spec_score"] + [
    tf["name"] for tf in tier_features
]

X, y = build_feature_matrix(reg_data, VARIANT_BY_NAME, tier_features)

if len(X) >= len(feature_names):
    coeffs, r_squared = ols_regression(X, y)
    print(f"Regression R² = {r_squared:.4f}")
    print(f"Features: {feature_names}")
    print(f"Coefficients: {[f'{c:.2f}' for c in coeffs]}")
else:
    print(f"WARNING: Not enough data for regression ({len(X)} rows, {len(feature_names)} features)")
    coeffs = [0] * len(feature_names)
    r_squared = 0

# Predict and compute residuals for ALL used cars
for r in rows:
    tier = _get_tier_value(r, VARIANT_BY_NAME)
    features = [1, r["age_months"], r["mileage"], r["spec_score"]]
    for tf in tier_features:
        features.append(1 if tier == tf["tier"] else 0)
    predicted = sum(f * c for f, c in zip(features, coeffs))
    r["predicted_price"] = round(predicted)
    r["value_deviation"] = round(r["price"] - predicted)
    r["value_deviation_pct"] = (
        round((r["price"] - predicted) / predicted * 100, 1) if predicted > 0 else 0
    )

# ── Spec premium calculation ────────────────────────────────────────

spec_premiums = []
for spec in SPEC_OPTIONS:
    field = spec["key"]
    label = spec["label"]
    with_spec = [r["value_deviation"] for r in reg_data if r.get(field)]
    without_spec = [r["value_deviation"] for r in reg_data if not r.get(field)]
    if len(with_spec) >= 3 and len(without_spec) >= 3:
        avg_with = sum(with_spec) / len(with_spec)
        avg_without = sum(without_spec) / len(without_spec)
        premium = round(avg_with - avg_without)
        spec_premiums.append({
            "label": label,
            "premium": premium,
            "count_with": len(with_spec),
            "count_without": len(without_spec),
        })
    else:
        spec_premiums.append({
            "label": label,
            "premium": 0,
            "count_with": len(with_spec),
            "count_without": len(without_spec),
            "insufficient": True,
        })

print("\nSpec Premiums:")
for sp in spec_premiums:
    insuf = " (insufficient data)" if sp.get("insufficient") else ""
    print(f"  {sp['label']}: £{sp['premium']:+,}{insuf} (n={sp['count_with']})")

# ── Depreciation curve data ─────────────────────────────────────────

dep_curve_data = {}
for r in rows:
    if r["is_brand_new_stock"]:
        continue
    v = r["variant"]
    if v not in dep_curve_data:
        dep_curve_data[v] = []
    dep_curve_data[v].append({
        "age_months": r["age_months"],
        "price": r["price"],
        "location": r["location"],
        "mileage": r["mileage"],
    })


dep_curves = {}
for variant, points in dep_curve_data.items():
    if len(points) < 5:
        continue
    poly = fit_poly2(points)
    ages = sorted(set(p["age_months"] for p in points))
    min_age = min(ages)
    max_age = max(ages)
    curve_points = []
    step = max(1, (max_age - min_age) / 50)
    a = min_age
    while a <= max_age:
        predicted = poly[0] + poly[1] * a + poly[2] * a * a
        curve_points.append({"x": round(a, 1), "y": round(predicted)})
        a += step

    # Flattening point: where slope drops to half initial
    flatten_month = None
    if abs(poly[2]) > 0.001:
        flatten_month = round(-poly[1] / (4 * poly[2]), 0)
        if flatten_month < min_age or flatten_month > max_age:
            flatten_month = None

    dep_curves[variant] = {
        "points": [
            {"x": p["age_months"], "y": p["price"], "location": p["location"], "mileage": p["mileage"]}
            for p in points
        ],
        "curve": curve_points,
        "poly": poly,
        "flatten_month": flatten_month,
    }

for v, d in dep_curves.items():
    fm = d["flatten_month"]
    if fm:
        print(f"\n{v}: poly=[{d['poly'][0]:.0f}, {d['poly'][1]:.1f}, {d['poly'][2]:.3f}], flattening ~{fm} months")
    else:
        print(f"\n{v}: no clear flattening point")

# ── Serialise data for JS ───────────────────────────────────────────


# Table data (all used cars, sorted by value_deviation ascending)
table_data = []
for r in rows:
    if r["is_brand_new_stock"]:
        continue
    table_data.append({
        "variant": r["variant"],
        "year": r["year"],
        "age": r["age_years"],
        "age_months": r["age_months"],
        "price": r["price"],
        "mileage": r["mileage"],
        "predicted": r["predicted_price"],
        "deviation": r["value_deviation"],
        "deviation_pct": r["value_deviation_pct"],
        "retained_pct": r["retained_pct"],
        "dep_pa": r["depreciation_pa"] if r["age_years"] >= 0.5 else None,
        "days_on_market": r["days_on_market"],
        "price_change": r["price_change"],
        "spec_text": r["spec_text"],
        "spec_labels": r["spec_labels"],
        "location": r["location"],
        "autotrader_url": r["autotrader_url"],
        "composite_key": r["composite_key"],
    })

# Lollipop chart data
lollipop_data = sorted(
    [r for r in table_data],
    key=lambda r: r["deviation"],
)

# Negotiation radar data
negotiation_data = [r for r in table_data if r["days_on_market"] is not None]

# Price vs mileage
price_mileage_data = {}
for r in table_data:
    v = r["variant"]
    if v not in price_mileage_data:
        price_mileage_data[v] = []
    price_mileage_data[v].append({"x": r["mileage"], "y": r["price"], "location": r["location"]})

# Fit trendline for price vs mileage
all_pm = [{"mileage": r["mileage"], "price": r["price"]} for r in table_data]
if len(all_pm) > 5:
    pm_X = [[1, r["mileage"]] for r in all_pm]
    pm_y = [r["price"] for r in all_pm]
    pm_coeffs, _ = ols_regression(pm_X, pm_y)
    mileages = sorted(set(r["mileage"] for r in all_pm))
    pm_trend = [
        {"x": min(mileages), "y": round(pm_coeffs[0] + pm_coeffs[1] * min(mileages))},
        {"x": max(mileages), "y": round(pm_coeffs[0] + pm_coeffs[1] * max(mileages))},
    ]
else:
    pm_trend = []

print(f"\nTable data: {len(table_data)} used listings")
print(f"Negotiation radar: {len(negotiation_data)} with days-on-market")

# ── Build highlight spec keys for JS ────────────────────────────────

highlight_specs = [s["label"] for s in SPEC_OPTIONS if s.get("highlight")]

# ── Build HTML ──────────────────────────────────────────────────────

theme = DASHBOARD["theme"]
bg = theme["bg"]
card_bg = theme["card_bg"]
card_border = theme["card_border"]
text_colour = theme["text"]
text_muted = theme["text_muted"]

# Build variant filter options
variant_options_html = '<option value="all">All variants</option>'
for v in VARIANTS:
    variant_options_html += f'\n                <option value="{v["name"]}">{v["name"]}</option>'

# Build generation filter options
gen_options_html = '<option value="all">All</option>'
for g in GENERATIONS:
    gen_options_html += f'\n                <option value="{g["name"]}">{g["label"]}</option>'

# Build mileage filter options
mileage_options_html = '<option value="999999">Any</option>'
for m in DASHBOARD.get("mileage_filter_options", [20000, 50000, 100000]):
    selected = ' selected' if m == DASHBOARD.get("mileage_filter_default") else ''
    mileage_options_html += f'\n                <option value="{m}"{selected}>{m:,}</option>'

# Build budget filter options
budget_options_html = '<option value="999999">Any</option>'
for b in DASHBOARD.get("budget_filter_options", [50000, 100000]):
    selected = ' selected' if b == DASHBOARD.get("budget_filter_default") else ''
    budget_options_html += f'\n                <option value="{b}"{selected}>Up to &pound;{b//1000}k</option>'

# Search criteria text
criteria_text = (
    f"Max &pound;{SEARCH_FILTERS['max_price']:,} &bull; "
    f"Under {SEARCH_FILTERS['max_mileage']:,} miles &bull; "
    f"Within {SEARCH_FILTERS['max_distance']} miles of {SEARCH_FILTERS['postcode']}"
)
if SEARCH_FILTERS.get("exclude_write_offs"):
    criteria_text += " &bull; Exclude Cat S/N"

# Preferred spec text
preferred_specs = [s["label"] for s in SPEC_OPTIONS if s.get("highlight")]
preferred_text = " &bull; ".join(preferred_specs) if preferred_specs else "No specific preferences set"

# Generation filter JS logic
gen_filter_js = "true"  # Default: pass everything
if len(GENERATIONS) > 1:
    # Build a mapping of generation name to year ranges
    gen_filter_js = """(() => {
        const genMap = """ + js_safe({
        g["name"]: {"year_from": g["year_from"], "year_to": g.get("year_to") or 2099}
        for g in GENERATIONS
    }) + """;
        const genFilter = document.getElementById('filterGen').value;
        if (genFilter === 'all') return true;
        const gm = genMap[genFilter];
        if (!gm) return true;
        return row.year >= gm.year_from && row.year <= gm.year_to;
    })()"""

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{DISPLAY_NAME} &mdash; Buyer Intelligence Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: {bg}; color: {text_colour}; line-height: 1.5; }}
.header {{ background: linear-gradient(135deg, {card_bg} 0%, #16213e 100%); padding: 24px 32px; border-bottom: 1px solid {card_border}; }}
.header h1 {{ font-size: 24px; font-weight: 600; color: #fff; }}
.header p {{ color: {text_muted}; font-size: 14px; margin-top: 4px; }}
.criteria {{ margin: 16px 32px 0; padding: 16px 20px; background: linear-gradient(135deg, rgba(59,130,246,0.1), rgba(139,92,246,0.1)); border: 1px solid rgba(59,130,246,0.25); border-radius: 12px; display: flex; flex-wrap: wrap; gap: 24px; align-items: center; }}
.criteria-section {{ flex: 1; min-width: 200px; }}
.criteria-label {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
.criteria-text {{ font-size: 13px; color: #d1d5db; }}
.kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; padding: 24px 32px; }}
.kpi {{ background: {card_bg}; border: 1px solid {card_border}; border-radius: 12px; padding: 20px; }}
.kpi-label {{ font-size: 12px; color: {text_muted}; text-transform: uppercase; letter-spacing: 0.05em; }}
.kpi-value {{ font-size: 28px; font-weight: 700; color: #fff; margin-top: 4px; }}
.kpi-sub {{ font-size: 12px; color: #6b7280; margin-top: 2px; }}
.content {{ padding: 0 32px 32px; }}
.filters {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; padding: 16px; background: {card_bg}; border-radius: 12px; border: 1px solid {card_border}; }}
.filter-group {{ display: flex; flex-direction: column; gap: 4px; }}
.filter-group label {{ font-size: 11px; color: {text_muted}; text-transform: uppercase; letter-spacing: 0.05em; }}
.filter-group select {{ background: {bg}; border: 1px solid {card_border}; color: {text_colour}; padding: 6px 10px; border-radius: 6px; font-size: 13px; }}
.market-pulse {{ background: linear-gradient(135deg, rgba(34,195,94,0.08), rgba(59,130,246,0.08)); border: 1px solid rgba(59,130,246,0.2); border-radius: 12px; padding: 20px; margin-bottom: 24px; }}
.market-pulse h3 {{ color: #4ade80; font-size: 15px; margin-bottom: 12px; }}
.pulse-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
.pulse-item {{ background: rgba(26,26,46,0.5); border-left: 3px solid #4ade80; padding: 10px 12px; border-radius: 4px; }}
.pulse-item-label {{ font-size: 11px; color: {text_muted}; text-transform: uppercase; }}
.pulse-item-value {{ font-size: 18px; font-weight: 700; color: #fff; margin-top: 2px; }}
.pulse-item-sub {{ font-size: 11px; color: #6b7280; margin-top: 2px; }}
.chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
.chart-card {{ background: {card_bg}; border: 1px solid {card_border}; border-radius: 12px; padding: 20px; min-height: 0; }}
.chart-card.full {{ grid-column: 1 / -1; }}
.chart-card h3 {{ font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 4px; }}
.chart-card p {{ font-size: 12px; color: {text_muted}; margin-bottom: 16px; }}
.chart-container {{ position: relative; width: 100%; }}
.annotation {{ font-size: 12px; color: #fbbf24; margin-top: 8px; padding: 8px 12px; background: rgba(245,158,11,0.1); border-left: 3px solid #fbbf24; border-radius: 4px; }}
.table-wrapper {{ background: {card_bg}; border: 1px solid {card_border}; border-radius: 12px; padding: 20px; margin-bottom: 24px; overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 10px 12px; background: #16213e; color: {text_muted}; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid {card_border}; cursor: pointer; user-select: none; white-space: nowrap; }}
th:hover {{ color: {text_colour}; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #1f1f2e; white-space: nowrap; }}
tr:hover td {{ background: rgba(59,130,246,0.05); }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }}
.tag-green {{ background: rgba(34,197,94,0.15); color: #4ade80; }}
.tag-blue {{ background: rgba(59,130,246,0.15); color: #60a5fa; }}
.tag-amber {{ background: rgba(245,158,11,0.15); color: #fbbf24; }}
.tag-red {{ background: rgba(239,68,68,0.15); color: #f87171; }}
.tag-purple {{ background: rgba(139,92,246,0.15); color: #a78bfa; }}
a.listing-link {{ color: #60a5fa; text-decoration: none; }}
a.listing-link:hover {{ text-decoration: underline; }}
.spec-tag {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; margin-right: 3px; background: rgba(100,116,139,0.2); color: #94a3b8; }}
.spec-tag.highlight {{ background: rgba(139,92,246,0.2); color: #a78bfa; }}
.model-info {{ font-size: 11px; color: #6b7280; margin-top: 8px; padding: 8px; background: rgba(100,116,139,0.1); border-radius: 4px; }}
@media (max-width: 900px) {{
    .chart-grid {{ grid-template-columns: 1fr; }}
    .kpi-row {{ grid-template-columns: repeat(2, 1fr); }}
    .filters {{ flex-direction: column; }}
    .criteria {{ flex-direction: column; gap: 12px; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>{DISPLAY_NAME} &mdash; Buyer Intelligence Dashboard</h1>
    <p>{len(table_data)} used listings &bull; Data collected {today_str} &bull; Regression model R&sup2; = {r_squared:.3f}</p>
</div>

<div class="criteria">
    <div class="criteria-section">
        <div class="criteria-label" style="color: #60a5fa;">Search Criteria</div>
        <div class="criteria-text">{criteria_text}</div>
    </div>
    <div class="criteria-section">
        <div class="criteria-label" style="color: #a78bfa;">Preferred Specification</div>
        <div class="criteria-text">{preferred_text}</div>
    </div>
</div>

<div class="kpi-row" id="kpiRow"></div>

<div class="content">
    <div class="filters">
        <div class="filter-group">
            <label>Variant</label>
            <select id="filterVariant" onchange="updateAll()">
                {variant_options_html}
            </select>
        </div>
        <div class="filter-group">
            <label>Generation</label>
            <select id="filterGen" onchange="updateAll()">
                {gen_options_html}
            </select>
        </div>
        <div class="filter-group">
            <label>Max Mileage</label>
            <select id="filterMileage" onchange="updateAll()">
                {mileage_options_html}
            </select>
        </div>
        <div class="filter-group">
            <label>Budget</label>
            <select id="filterBudget" onchange="updateAll()">
                {budget_options_html}
            </select>
        </div>
        <div class="filter-group">
            <label>Value</label>
            <select id="filterValue" onchange="updateAll()">
                <option value="all">All</option>
                <option value="under">Undervalued only</option>
                <option value="over">Overpriced only</option>
            </select>
        </div>
    </div>

    <div class="market-pulse">
        <h3>Market Pulse</h3>
        <div class="pulse-grid" id="pulseGrid"></div>
    </div>

    <div class="chart-grid">
        <div class="chart-card full">
            <h3>Depreciation Curve &mdash; When Does It Flatten?</h3>
            <p>Asking price by age in months, with fitted polynomial trend per variant.</p>
            <div class="chart-container">
                <canvas id="depCurveChart"></canvas>
            </div>
            <div class="annotation" id="depCurveAnnotation"></div>
        </div>

        <div class="chart-card full">
            <h3>Deal Score &mdash; Value vs Expected Price</h3>
            <p>Each bar shows how much a car is priced above or below the regression model prediction. Green = undervalued.</p>
            <div class="chart-container">
                <canvas id="dealScoreChart"></canvas>
            </div>
            <div class="model-info">Model: price = f(age, mileage, spec score, variant tier) &bull; R&sup2; = {r_squared:.3f} &bull; Based on {len(reg_data)} used listings</div>
        </div>

        <div class="chart-card">
            <h3>Spec Premium Analysis</h3>
            <p>Average price premium each option commands after controlling for age, mileage, and variant.</p>
            <div class="chart-container">
                <canvas id="specPremiumChart"></canvas>
            </div>
        </div>

        <div class="chart-card">
            <h3>Negotiation Radar</h3>
            <p>Days listed vs price deviation. Top-right = overpriced &amp; stale. Bottom-left = undervalued &amp; fresh.</p>
            <div class="chart-container">
                <canvas id="negotiationChart"></canvas>
            </div>
        </div>

        <div class="chart-card full">
            <h3>Price vs Mileage</h3>
            <p>Scatter with fitted trendline. Points below the line = lower price for the mileage.</p>
            <div class="chart-container">
                <canvas id="priceMileageChart"></canvas>
            </div>
        </div>
    </div>

    <div class="table-wrapper">
        <h3 style="color: #fff; font-size: 15px; margin-bottom: 12px;">All Listings</h3>
        <table id="dataTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Variant</th>
                    <th onclick="sortTable(1)">Age</th>
                    <th onclick="sortTable(2)">Price</th>
                    <th onclick="sortTable(3)">Expected</th>
                    <th onclick="sortTable(4)">Value</th>
                    <th onclick="sortTable(5)">Mileage</th>
                    <th onclick="sortTable(6)">Dep/yr</th>
                    <th onclick="sortTable(7)">Days</th>
                    <th onclick="sortTable(8)">Trend</th>
                    <th onclick="sortTable(9)">Spec</th>
                    <th onclick="sortTable(10)">Location</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>
</div>

<script>
const ALL_DATA = {js_safe(table_data)};
const DEP_CURVES = {js_safe(dep_curves)};
const SPEC_PREMIUMS = {js_safe(spec_premiums)};
const NEGOTIATION_DATA = {js_safe(negotiation_data)};
const PM_TREND = {js_safe(pm_trend)};
const VARIANT_COLOURS = {js_safe(VARIANT_COLOURS)};
const HIGHLIGHT_SPECS = {js_safe(highlight_specs)};

let charts = {{}};

function getFilteredData() {{
    const variant = document.getElementById('filterVariant').value;
    const mileage = parseInt(document.getElementById('filterMileage').value);
    const budget = parseInt(document.getElementById('filterBudget').value);
    const value = document.getElementById('filterValue').value;

    return ALL_DATA.filter(row => {{
        if (variant !== 'all' && row.variant !== variant) return false;
        if (!({gen_filter_js})) return false;
        if (row.mileage > mileage) return false;
        if (row.price > budget) return false;
        if (value === 'under' && row.deviation >= 0) return false;
        if (value === 'over' && row.deviation < 0) return false;
        return true;
    }});
}}

function updateKPIs() {{
    const data = getFilteredData();
    const kpiRow = document.getElementById('kpiRow');
    const undervalued = data.filter(r => r.deviation < 0).length;
    const avgDev = data.length > 0 ? Math.round(data.reduce((s, r) => s + r.deviation, 0) / data.length) : 0;
    const avgPrice = data.length > 0 ? Math.round(data.reduce((s, r) => s + r.price, 0) / data.length) : 0;
    const withDays = data.filter(r => r.days_on_market !== null);
    const avgDays = withDays.length > 0 ? Math.round(withDays.reduce((s, r) => s + r.days_on_market, 0) / withDays.length) : null;

    kpiRow.innerHTML = `
        <div class="kpi">
            <div class="kpi-label">Listings</div>
            <div class="kpi-value">${{data.length}}</div>
            <div class="kpi-sub">${{undervalued}} undervalued</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Average Price</div>
            <div class="kpi-value">&pound;${{avgPrice.toLocaleString('en-GB')}}</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Avg Value Score</div>
            <div class="kpi-value" style="color: ${{avgDev < 0 ? '#4ade80' : '#f87171'}}">&pound;${{avgDev.toLocaleString('en-GB')}}</div>
            <div class="kpi-sub">vs expected price</div>
        </div>
        <div class="kpi">
            <div class="kpi-label">Avg Days Listed</div>
            <div class="kpi-value">${{avgDays !== null ? avgDays : 'N/A'}}</div>
            <div class="kpi-sub">${{withDays.length}} tracked</div>
        </div>
    `;
}}

function updateMarketPulse() {{
    const data = getFilteredData();
    const withDays = data.filter(r => r.days_on_market !== null);
    const avgDays = withDays.length > 0 ? Math.round(withDays.reduce((s, r) => s + r.days_on_market, 0) / withDays.length) : 'N/A';
    const priceDrops = data.filter(r => r.price_change < 0);
    const avgDrop = priceDrops.length > 0 ? Math.round(priceDrops.reduce((s, r) => s + Math.abs(r.price_change), 0) / priceDrops.length) : 0;
    const sorted = [...data].sort((a, b) => a.price - b.price);
    const median = sorted.length > 0 ? sorted[Math.floor(sorted.length / 2)].price : 0;

    document.getElementById('pulseGrid').innerHTML = `
        <div class="pulse-item">
            <div class="pulse-item-label">Filtered Listings</div>
            <div class="pulse-item-value">${{data.length}}</div>
            <div class="pulse-item-sub">Matching filters</div>
        </div>
        <div class="pulse-item">
            <div class="pulse-item-label">Price Reductions</div>
            <div class="pulse-item-value">${{priceDrops.length}}</div>
            <div class="pulse-item-sub">${{priceDrops.length > 0 ? 'Avg &darr;&pound;' + avgDrop.toLocaleString('en-GB') : 'None in filter'}}</div>
        </div>
        <div class="pulse-item">
            <div class="pulse-item-label">Avg Days Listed</div>
            <div class="pulse-item-value">${{avgDays}}</div>
            <div class="pulse-item-sub">Tracked listings</div>
        </div>
        <div class="pulse-item">
            <div class="pulse-item-label">Median Price</div>
            <div class="pulse-item-value">&pound;${{median.toLocaleString('en-GB')}}</div>
            <div class="pulse-item-sub">Filtered</div>
        </div>
    `;
}}

function updateDepCurveChart() {{
    const ctx = document.getElementById('depCurveChart').getContext('2d');
    if (charts.depCurve) charts.depCurve.destroy();

    const datasets = [];
    const annotations = [];

    Object.entries(DEP_CURVES).forEach(([variant, data]) => {{
        const vc = VARIANT_COLOURS[variant];
        if (!vc) return;

        datasets.push({{
            label: variant,
            data: data.points.map(p => ({{x: p.x, y: p.y}})),
            backgroundColor: vc.bg,
            borderColor: vc.border,
            pointRadius: 4,
            pointHoverRadius: 7,
            type: 'scatter',
            order: 2
        }});

        datasets.push({{
            label: variant + ' (trend)',
            data: data.curve,
            borderColor: vc.border,
            borderWidth: 3,
            borderDash: [6, 3],
            pointRadius: 0,
            fill: false,
            type: 'line',
            order: 1,
            tension: 0.4
        }});

        if (data.flatten_month) {{
            const fy = data.poly[0] + data.poly[1] * data.flatten_month + data.poly[2] * data.flatten_month * data.flatten_month;
            annotations.push(`${{variant}}: curve flattens around ${{Math.round(data.flatten_month)}} months (~&pound;${{Math.round(fy).toLocaleString('en-GB')}})`);
        }}
    }});

    charts.depCurve = new Chart(ctx, {{
        data: {{ datasets }},
        options: {{
            responsive: true, maintainAspectRatio: true, aspectRatio: 2.5,
            interaction: {{ mode: 'nearest', intersect: true }},
            plugins: {{
                legend: {{ display: true, labels: {{ color: '{text_colour}', filter: item => !item.text.includes('(trend)') }} }},
                tooltip: {{ callbacks: {{ label: function(ctx) {{ const d = ctx.raw; return `\\u00a3${{d.y?.toLocaleString('en-GB')}} at ${{d.x}} months`; }} }} }}
            }},
            scales: {{
                x: {{ type: 'linear', title: {{ display: true, text: 'Age (months)', color: '{text_muted}' }}, grid: {{ color: '{card_border}' }}, ticks: {{ color: '{text_muted}' }} }},
                y: {{ title: {{ display: true, text: 'Asking Price (\\u00a3)', color: '{text_muted}' }}, grid: {{ color: '{card_border}' }}, ticks: {{ color: '{text_muted}', callback: v => '\\u00a3' + v.toLocaleString('en-GB') }} }}
            }}
        }}
    }});

    document.getElementById('depCurveAnnotation').innerHTML = annotations.length > 0
        ? annotations.join('<br>')
        : 'Insufficient data to determine flattening point.';
}}

function updateDealScoreChart() {{
    const ctx = document.getElementById('dealScoreChart').getContext('2d');
    if (charts.dealScore) charts.dealScore.destroy();

    const data = getFilteredData()
        .filter(r => r.age >= 0.5)
        .sort((a, b) => a.deviation - b.deviation)
        .slice(0, 40);

    const labels = data.map(r => `${{r.location}} (${{r.variant}}, ${{r.age.toFixed(1)}}yr, ${{(r.mileage/1000).toFixed(0)}}k mi)`);
    const values = data.map(r => r.deviation);
    const bgColours = values.map(v => v < 0 ? 'rgba(34,197,94,0.6)' : 'rgba(239,68,68,0.5)');
    const borderColours = values.map(v => v < 0 ? '#22c55e' : '#ef4444');

    charts.dealScore = new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: labels,
            datasets: [{{ label: 'Price vs Expected', data: values, backgroundColor: bgColours, borderColor: borderColours, borderWidth: 1, borderRadius: 3, barThickness: 14 }}]
        }},
        options: {{
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {{
                legend: {{ display: false }},
                tooltip: {{ callbacks: {{ label: function(ctx) {{ const r = data[ctx.dataIndex]; return [`${{ctx.raw < 0 ? 'Under' : 'Over'}}priced by \\u00a3${{Math.abs(ctx.raw).toLocaleString('en-GB')}}`, `Asking: \\u00a3${{r.price.toLocaleString('en-GB')}} | Expected: \\u00a3${{r.predicted.toLocaleString('en-GB')}}`, `Spec: ${{r.spec_text}}`]; }} }} }}
            }},
            scales: {{
                x: {{ title: {{ display: true, text: '\\u00a3 vs Expected Price (negative = undervalued)', color: '{text_muted}' }}, grid: {{ color: '{card_border}' }}, ticks: {{ color: '{text_muted}', callback: v => (v < 0 ? '-' : '+') + '\\u00a3' + Math.abs(v).toLocaleString('en-GB') }} }},
                y: {{ grid: {{ display: false }}, ticks: {{ color: '#d1d5db', font: {{ size: 11 }} }} }}
            }}
        }}
    }});

    document.getElementById('dealScoreChart').parentElement.style.height = Math.max(400, data.length * 22 + 80) + 'px';
}}

function updateSpecPremiumChart() {{
    const ctx = document.getElementById('specPremiumChart').getContext('2d');
    if (charts.specPremium) charts.specPremium.destroy();

    const premiums = SPEC_PREMIUMS.filter(s => !s.insufficient);
    const sorted = premiums.sort((a, b) => b.premium - a.premium);

    charts.specPremium = new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: sorted.map(s => s.label),
            datasets: [{{ label: 'Price Premium', data: sorted.map(s => s.premium), backgroundColor: sorted.map(s => s.premium > 0 ? 'rgba(139,92,246,0.5)' : 'rgba(100,116,139,0.4)'), borderColor: sorted.map(s => s.premium > 0 ? '#a78bfa' : '#64748b'), borderWidth: 1, borderRadius: 4 }}]
        }},
        options: {{
            indexAxis: 'y', responsive: true, maintainAspectRatio: true, aspectRatio: 1.3,
            plugins: {{
                legend: {{ display: false }},
                tooltip: {{ callbacks: {{ label: function(ctx) {{ const s = sorted[ctx.dataIndex]; return `${{ctx.raw > 0 ? '+' : ''}}\\u00a3${{ctx.raw.toLocaleString('en-GB')}} premium (n=${{s.count_with}} with, ${{s.count_without}} without)`; }} }} }}
            }},
            scales: {{
                x: {{ title: {{ display: true, text: 'Price Premium (\\u00a3)', color: '{text_muted}' }}, grid: {{ color: '{card_border}' }}, ticks: {{ color: '{text_muted}', callback: v => (v >= 0 ? '+\\u00a3' : '-\\u00a3') + Math.abs(v).toLocaleString('en-GB') }} }},
                y: {{ grid: {{ display: false }}, ticks: {{ color: '#d1d5db' }} }}
            }}
        }}
    }});
}}

function updateNegotiationChart() {{
    const ctx = document.getElementById('negotiationChart').getContext('2d');
    if (charts.negotiation) charts.negotiation.destroy();

    const data = getFilteredData().filter(r => r.days_on_market !== null);
    const datasets = {{}};
    data.forEach(r => {{
        const v = r.variant;
        if (!datasets[v]) {{
            const vc = VARIANT_COLOURS[v];
            datasets[v] = {{
                label: v,
                data: [],
                backgroundColor: vc ? vc.bg : 'rgba(100,116,139,0.3)',
                borderColor: vc ? vc.border : '#64748b',
                borderWidth: 1, pointRadius: 6, pointHoverRadius: 9
            }};
        }}
        datasets[v].data.push({{ x: r.days_on_market, y: r.deviation_pct, price: r.price, location: r.location, spec: r.spec_text }});
    }});

    charts.negotiation = new Chart(ctx, {{
        type: 'scatter',
        data: {{ datasets: Object.values(datasets) }},
        options: {{
            responsive: true, maintainAspectRatio: true, aspectRatio: 1.3,
            plugins: {{
                legend: {{ display: true, labels: {{ color: '{text_colour}' }} }},
                tooltip: {{ callbacks: {{ label: function(ctx) {{ const d = ctx.raw; return [`${{d.location}}: \\u00a3${{d.price.toLocaleString('en-GB')}}`, `${{d.y > 0 ? '+' : ''}}${{d.y.toFixed(1)}}% vs expected`, `${{d.x}} days listed`, `Spec: ${{d.spec}}`]; }} }} }}
            }},
            scales: {{
                x: {{ title: {{ display: true, text: 'Days Listed', color: '{text_muted}' }}, grid: {{ color: '{card_border}' }}, ticks: {{ color: '{text_muted}' }} }},
                y: {{ title: {{ display: true, text: '% Above/Below Expected', color: '{text_muted}' }}, grid: {{ color: '{card_border}' }}, ticks: {{ color: '{text_muted}', callback: v => (v >= 0 ? '+' : '') + v + '%' }} }}
            }}
        }}
    }});
}}

function updatePriceMileageChart() {{
    const ctx = document.getElementById('priceMileageChart').getContext('2d');
    if (charts.priceMileage) charts.priceMileage.destroy();

    const data = getFilteredData();
    const datasets = {{}};
    data.forEach(r => {{
        const v = r.variant;
        if (!datasets[v]) {{
            const vc = VARIANT_COLOURS[v];
            datasets[v] = {{
                label: v, data: [],
                backgroundColor: vc ? vc.bg : 'rgba(100,116,139,0.3)',
                borderColor: vc ? vc.border : '#64748b',
                borderWidth: 1, pointRadius: 5, pointHoverRadius: 8,
                type: 'scatter', order: 2
            }};
        }}
        datasets[v].data.push({{x: r.mileage, y: r.price, location: r.location, age: r.age}});
    }});

    const allDs = Object.values(datasets);
    if (PM_TREND.length === 2) {{
        allDs.push({{ label: 'Trendline (all used)', data: PM_TREND, borderColor: '#fbbf24', borderWidth: 2, borderDash: [8, 4], pointRadius: 0, fill: false, type: 'line', order: 1 }});
    }}

    charts.priceMileage = new Chart(ctx, {{
        data: {{ datasets: allDs }},
        options: {{
            responsive: true, maintainAspectRatio: true, aspectRatio: 2.5,
            plugins: {{
                legend: {{ display: true, labels: {{ color: '{text_colour}' }} }},
                tooltip: {{ callbacks: {{ label: function(ctx) {{ const d = ctx.raw; if (!d.location) return ''; return `${{d.location}}: \\u00a3${{d.y.toLocaleString('en-GB')}}, ${{d.x.toLocaleString('en-GB')}} mi, ${{d.age?.toFixed(1) || '?'}}yr`; }} }} }}
            }},
            scales: {{
                x: {{ title: {{ display: true, text: 'Mileage (miles)', color: '{text_muted}' }}, grid: {{ color: '{card_border}' }}, ticks: {{ color: '{text_muted}' }} }},
                y: {{ title: {{ display: true, text: 'Price (\\u00a3)', color: '{text_muted}' }}, grid: {{ color: '{card_border}' }}, ticks: {{ color: '{text_muted}', callback: v => '\\u00a3' + v.toLocaleString('en-GB') }} }}
            }}
        }}
    }});
}}

function getValueTag(dev) {{
    if (dev < -3000) return `<span class="tag tag-green">&pound;${{Math.abs(dev).toLocaleString('en-GB')}} under</span>`;
    if (dev < -1000) return `<span class="tag tag-blue">&pound;${{Math.abs(dev).toLocaleString('en-GB')}} under</span>`;
    if (dev < 1000) return `<span class="tag tag-amber">Fair</span>`;
    return `<span class="tag tag-red">&pound;${{dev.toLocaleString('en-GB')}} over</span>`;
}}

function getDaysTag(days) {{
    if (days === null) return '<span style="color:#6b7280;">&mdash;</span>';
    if (days <= 7) return `<span class="tag tag-green">${{days}}d</span>`;
    if (days <= 21) return `<span class="tag tag-blue">${{days}}d</span>`;
    if (days <= 42) return `<span class="tag tag-amber">${{days}}d</span>`;
    return `<span class="tag tag-red">${{days}}d</span>`;
}}

function getTrendTag(change) {{
    if (change === 0) return '<span style="color:#6b7280;">&mdash;</span>';
    if (change < 0) return `<span style="color:#f87171;font-weight:600;">&darr;&pound;${{Math.abs(change).toLocaleString('en-GB')}}</span>`;
    return `<span style="color:#4ade80;font-weight:600;">&uarr;&pound;${{change.toLocaleString('en-GB')}}</span>`;
}}

function getSpecHtml(row) {{
    if (!row.spec_labels || row.spec_labels.length === 0) return '<span style="color:#6b7280;">Base</span>';
    return row.spec_labels.map(s => {{
        const cls = HIGHLIGHT_SPECS.includes(s) ? 'spec-tag highlight' : 'spec-tag';
        return `<span class="${{cls}}">${{s}}</span>`;
    }}).join('');
}}

function renderRow(r) {{
    const loc = r.autotrader_url
        ? `<a href="${{r.autotrader_url}}" target="_blank" class="listing-link">${{r.location}}</a>`
        : r.location;
    const depYr = r.dep_pa !== null ? '&pound;' + r.dep_pa.toLocaleString('en-GB') : '<span style="color:#6b7280;">N/A</span>';

    return `<td>${{r.variant}}</td>
        <td>${{r.age.toFixed(1)}}yr</td>
        <td>&pound;${{r.price.toLocaleString('en-GB')}}</td>
        <td>&pound;${{r.predicted.toLocaleString('en-GB')}}</td>
        <td>${{getValueTag(r.deviation)}}</td>
        <td>${{r.mileage.toLocaleString('en-GB')}}</td>
        <td>${{depYr}}</td>
        <td>${{getDaysTag(r.days_on_market)}}</td>
        <td>${{getTrendTag(r.price_change)}}</td>
        <td>${{getSpecHtml(r)}}</td>
        <td>${{loc}}</td>`;
}}

function updateTable() {{
    const data = getFilteredData().sort((a, b) => a.deviation - b.deviation);
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';
    data.forEach(r => {{
        const tr = document.createElement('tr');
        tr.innerHTML = renderRow(r);
        tbody.appendChild(tr);
    }});
}}

let sortCol = -1, sortAsc = true;
function sortTable(col) {{
    const cols = ['variant', 'age', 'price', 'predicted', 'deviation', 'mileage', 'dep_pa', 'days_on_market', 'price_change', 'spec_text', 'location'];
    if (sortCol === col) sortAsc = !sortAsc;
    else {{ sortCol = col; sortAsc = true; }}

    const colName = cols[col];
    if (!colName) return;

    const data = getFilteredData();
    data.sort((a, b) => {{
        let av = a[colName], bv = b[colName];
        if (av === null && bv === null) return 0;
        if (av === null) return 1;
        if (bv === null) return -1;
        if (typeof av === 'string') return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
        return sortAsc ? av - bv : bv - av;
    }});

    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';
    data.forEach(r => {{
        const tr = document.createElement('tr');
        tr.innerHTML = renderRow(r);
        tbody.appendChild(tr);
    }});
}}

function updateAll() {{
    updateKPIs();
    updateMarketPulse();
    updateDepCurveChart();
    updateDealScoreChart();
    updateSpecPremiumChart();
    updateNegotiationChart();
    updatePriceMileageChart();
    updateTable();
}}

updateAll();
</script>
</body>
</html>'''

with open(OUTPUT_PATH, 'w') as f:
    f.write(html)

file_size = os.path.getsize(OUTPUT_PATH)
print(f"\nDashboard written to {OUTPUT_PATH}")
print(f"File size: {file_size:,} bytes ({file_size // 1024} KB)")
