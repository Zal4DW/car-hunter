#!/usr/bin/env python3
"""
Car Hunter - Market Pulse

Answers "anything new, anything dropped in price?" without rebuilding the
full dashboard. Globs the dated snapshot CSVs in the searches folder, diffs
the two most recent by listing_id, and prints a short human-readable digest
(or JSON with --json) for the /car-pulse command to relay.

Usage:
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/market_pulse.py \
        --profile "${CLAUDE_PLUGIN_DATA}/profiles/{name}.json" \
        --dir {profile}-searches [--json]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dashboard import load_profile, load_snapshots  # noqa: E402
from dashboard_lib import safe_int_price, snapshot_diff  # noqa: E402


def build_pulse(snapshots):
    """Diff the two latest snapshots into a pulse summary dict.

    Returns a dict with latest/previous dates, counts, price moves, and
    median movement. With fewer than two snapshots the diff fields are None
    and 'message' explains why.
    """
    if not snapshots:
        return {"message": "No dated snapshot CSVs found - run /search-cars first."}
    latest = snapshots[-1]
    pulse = {
        "latest_date": latest["date"].isoformat(),
        "active_listings": len(latest["ids"]),
        "median_price": latest["median_price"],
    }
    if len(snapshots) < 2:
        pulse["message"] = (
            "Only one snapshot so far - run /search-cars again on another day "
            "to see what changed."
        )
        return pulse

    prev = snapshots[-2]
    diff = snapshot_diff(
        [{"listing_id": r.get("listing_id", ""), "price": safe_int_price(r.get("price")) or 0}
         for r in prev["rows"]],
        [{"listing_id": r.get("listing_id", ""), "price": safe_int_price(r.get("price")) or 0}
         for r in latest["rows"]],
    )
    drops = [c for c in diff["price_changed"] if c["delta"] < 0]
    rises = [c for c in diff["price_changed"] if c["delta"] > 0]
    latest_by_id = {r.get("listing_id"): r for r in latest["rows"] if r.get("listing_id")}

    def _describe(change):
        row = latest_by_id.get(change["id"], {})
        return {
            "listing_id": change["id"],
            "variant": row.get("variant", ""),
            "year": row.get("year", ""),
            "mileage": row.get("mileage", ""),
            "location": row.get("location", ""),
            "old": change["old"],
            "new": change["new"],
            "delta": change["delta"],
        }

    new_rows = [latest_by_id[lid] for lid in diff["new"] if lid in latest_by_id]
    pulse.update({
        "previous_date": prev["date"].isoformat(),
        "new_count": len(diff["new"]),
        "removed_count": len(diff["removed"]),
        "price_drops": sorted((_describe(c) for c in drops), key=lambda c: c["delta"]),
        "price_rises": [_describe(c) for c in rises],
        "median_move": latest["median_price"] - prev["median_price"],
        "new_listings": [
            {
                "listing_id": r.get("listing_id", ""),
                "variant": r.get("variant", ""),
                "year": r.get("year", ""),
                "price": safe_int_price(r.get("price")) or 0,
                "mileage": r.get("mileage", ""),
                "location": r.get("location", ""),
            }
            for r in new_rows
        ],
    })
    return pulse


def print_pulse(pulse, display_name):
    """Render the pulse dict as a short human-readable digest."""
    print(f"Market pulse: {display_name}")
    if "message" in pulse and "previous_date" not in pulse:
        print(pulse["message"])
        if "active_listings" in pulse:
            print(f"Active listings on {pulse['latest_date']}: {pulse['active_listings']} "
                  f"(median £{pulse['median_price']:,.0f})")
        return
    print(f"Comparing {pulse['previous_date']} -> {pulse['latest_date']}")
    print(f"Active listings: {pulse['active_listings']} (median £{pulse['median_price']:,.0f}, "
          f"moved £{pulse['median_move']:+,.0f})")
    print(f"New arrivals: {pulse['new_count']}")
    for r in pulse["new_listings"][:10]:
        print(f"  + {r['variant']} {r['year']}, £{r['price']:,}, {r['mileage']} miles, {r['location']}")
    print(f"Removed (sold or delisted): {pulse['removed_count']}")
    print(f"Price drops: {len(pulse['price_drops'])}")
    for c in pulse["price_drops"][:10]:
        print(f"  - {c['variant']} {c['year']}: £{c['old']:,} -> £{c['new']:,} ({c['delta']:+,})")
    if pulse["price_rises"]:
        print(f"Price rises: {len(pulse['price_rises'])}")


def main():
    parser = argparse.ArgumentParser(description="Quick what-changed digest from snapshot CSVs")
    parser.add_argument("--profile", required=True, help="Path to car-profile.json")
    parser.add_argument("--dir", required=True, help="Searches folder containing dated CSVs")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    profile_ctx = load_profile(args.profile)
    snapshots = load_snapshots(args.dir, profile_ctx["profile_name"])
    pulse = build_pulse(snapshots)

    if args.json:
        print(json.dumps(pulse, indent=2))
    else:
        print_pulse(pulse, profile_ctx["display_name"])


if __name__ == "__main__":
    main()
