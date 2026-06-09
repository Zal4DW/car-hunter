#!/usr/bin/env python3
"""
Car Hunter - Negotiation Brief

Computes the evidence pack for negotiating one specific listing: market
position from the regression, days on market, price-drop history across
the snapshot archive, the closest comparables, supply pressure, and
suggested offer anchors. The negotiation-coach skill turns this into
strategy and scripts - this tool only does the numbers.

Usage:
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/negotiation_brief.py \
        --profile "${CLAUDE_PLUGIN_DATA}/profiles/{name}.json" \
        --dir {profile}-searches \
        --listing <listing_id>

Output is JSON on stdout.
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dashboard import (  # noqa: E402
    enrich_rows,
    load_csv,
    load_profile,
    load_snapshots,
    run_regression,
)
from dashboard_lib import build_tier_features, spec_score as _spec_score  # noqa: E402
from negotiation_lib import (  # noqa: E402
    find_comparables,
    negotiation_levers,
    price_history,
    suggest_offer_anchors,
)


def main():
    parser = argparse.ArgumentParser(
        description="Evidence pack for negotiating a specific listing"
    )
    parser.add_argument("--profile", required=True, help="Path to car-profile.json")
    parser.add_argument("--dir", required=True, help="Searches folder with dated CSVs")
    parser.add_argument("--listing", required=True, help="listing_id of the target car")
    args = parser.parse_args()

    ctx = load_profile(args.profile)
    profile_name = ctx["profile_name"]

    pattern = os.path.join(args.dir, f"{profile_name}-all-listings-*.csv")
    dated = sorted(glob.glob(pattern))
    if not dated:
        raise SystemExit(
            f"No dated CSVs found in {args.dir} for {profile_name}. "
            f"Run /search-cars first."
        )
    latest_csv = dated[-1]

    rows, _ = load_csv(latest_csv, ctx["spec_options"])
    for row in rows:
        row["spec_score"] = _spec_score(row, ctx["spec_options"])
    tier_features = build_tier_features(ctx["variants"])
    run_regression(rows, ctx["variant_by_name"], tier_features)

    snapshots = load_snapshots(args.dir, profile_name)
    if snapshots:
        enrich_rows(rows, snapshots, {"listings": {}}, ctx["lid_encoding"],
                    snapshots[-1]["date"])

    target = next((r for r in rows if r["listing_id"] == args.listing), None)
    if target is None:
        available = [r["listing_id"] for r in rows if r["listing_id"]][:10]
        raise SystemExit(
            f"Listing {args.listing!r} is not in the latest snapshot ({latest_csv}). "
            f"It may have sold. Example ids present: {', '.join(available)}"
        )

    history = price_history(snapshots, args.listing)
    levers = negotiation_levers(target, history, rows)
    anchors = suggest_offer_anchors(target, levers)
    comparables = find_comparables(rows, target)

    brief = {
        "profile": profile_name,
        "display_name": ctx["display_name"],
        "snapshot": os.path.basename(latest_csv),
        "target": {
            "listing_id": target["listing_id"],
            "variant": target["variant"],
            "year": target["year"],
            "price": target["price"],
            "mileage": target["mileage"],
            "age_years": target["age_years"],
            "location": target["location"],
            "predicted_price": target.get("predicted_price"),
            "value_deviation": target.get("value_deviation"),
            "value_deviation_pct": target.get("value_deviation_pct"),
            "retained_pct": target.get("retained_pct"),
            "new_price": target.get("new_price"),
            "days_on_market": target.get("days_on_market"),
            "url": target.get("autotrader_url") or target.get("url") or "",
        },
        "price_history": history,
        "levers": levers,
        "offer_anchors": anchors,
        "comparables": comparables,
    }
    print(json.dumps(brief, indent=2))


if __name__ == "__main__":
    main()
