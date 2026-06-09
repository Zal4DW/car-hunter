#!/usr/bin/env python3
"""
Car Hunter - Compare Cars

Cross-profile comparison anchored on a budget: "what can I get for £40k?"
Each car is scored by its OWN profile's regression (an i4's expected price
comes from i4 data, an e-tron GT's from e-tron GT data), then the
budget-sliced markets are laid side by side.

Usage:
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compare_cars.py \
        --car "${CLAUDE_PLUGIN_DATA}/profiles/bmw-i4.json:bmw-i4-searches/bmw-i4-all-listings-2026-06-09.csv" \
        --car "${CLAUDE_PLUGIN_DATA}/profiles/audi-etron-gt.json:audi-etron-gt-searches/audi-etron-gt-all-listings-2026-06-09.csv" \
        [--budget 40000] [--json]

Each --car is a profile path and a CSV path joined by the LAST colon.
--budget omitted means "compare the whole markets". Works with a single
--car too (what does £X buy within one model's variants).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dashboard import load_profile, load_csv, run_regression  # noqa: E402
from dashboard_lib import (  # noqa: E402
    build_tier_features,
    spec_score as _spec_score,
)
from compare_lib import comparison_summary, summarise_car  # noqa: E402


def analyse_car(profile_path, csv_path, budget):
    """Load one car, score it with its own regression, summarise at budget."""
    ctx = load_profile(profile_path)
    rows, skipped = load_csv(csv_path, ctx["spec_options"])
    for row in rows:
        row["spec_score"] = _spec_score(row, ctx["spec_options"])
    tier_features = build_tier_features(ctx["variants"])
    run_regression(rows, ctx["variant_by_name"], tier_features)
    summary = summarise_car(ctx["display_name"], rows, budget)
    if skipped:
        summary["skipped_rows"] = len(skipped)
    return summary


def print_comparison(result):
    """Render the comparison as a short human-readable digest."""
    budget = result["budget"]
    title = f"at £{budget:,}" if budget is not None else "across the whole market"
    print(f"Comparison {title}:")
    for car in result["cars"]:
        print(f"\n{car['display_name']} - {car['under_budget']}/{car['total_listings']} listings in budget")
        if car.get("message"):
            print(f"  {car['message']}")
            continue
        print(f"  Newest you can get: {car['newest_year']}  "
              f"| lowest mileage: {car['lowest_mileage']:,}")
        if car.get("median_age_years") is not None:
            print(f"  Typical: {car['median_age_years']:.1f} yrs old, "
                  f"{car['median_mileage']:,.0f} miles, £{car['median_price']:,.0f}")
        if car.get("median_retained_pct") is not None:
            print(f"  Median value retained: {car['median_retained_pct']:.0f}% of RRP")
        bv = car.get("best_value")
        if bv:
            print(f"  Best value: {bv['variant']} {bv['year']}, £{bv['price']:,}, "
                  f"{bv['mileage']:,} miles ({bv['value_deviation_pct']:+.1f}% vs expected)")
    if result.get("newest_at_budget"):
        n = result["newest_at_budget"]
        print(f"\nNewest car for the money: {n['display_name']} ({n['year']})")
    if result.get("best_value_retention"):
        b = result["best_value_retention"]
        print(f"Holds value best: {b['display_name']} "
              f"({b['median_retained_pct']:.0f}% of RRP retained)")


def main():
    parser = argparse.ArgumentParser(
        description="Compare tracked cars at a budget: what can I get for £X?"
    )
    parser.add_argument(
        "--car",
        action="append",
        required=True,
        metavar="PROFILE:CSV",
        help="Profile JSON path and listings CSV path joined by the last colon. Repeatable.",
    )
    parser.add_argument("--budget", type=int, default=None,
                        help="Budget cap in GBP (omit to compare whole markets)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    summaries = []
    for spec in args.car:
        profile_path, sep, csv_path = spec.rpartition(":")
        if not sep or not profile_path or not csv_path:
            raise SystemExit(
                f"--car must be PROFILE:CSV (got {spec!r}). "
                f"Join the profile path and CSV path with a colon."
            )
        summaries.append(analyse_car(profile_path, csv_path, args.budget))

    result = comparison_summary(summaries, args.budget)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_comparison(result)


if __name__ == "__main__":
    main()
