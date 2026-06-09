#!/usr/bin/env python3
"""
Car Hunter - Listing Ingest

Turns a raw capture JSON (written by the car-search skill during scraping)
into the dated listings CSV and capture manifest that the dashboard builder
consumes. All arithmetic, id extraction, generation detection, and
deduplication happens here so the search skill never has to compute derived
fields or hand-format CSV.

Usage:
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ingest_listings.py \
        --profile "${CLAUDE_PLUGIN_DATA}/profiles/{name}.json" \
        --capture {profile}-searches/{profile}-raw-capture-{YYYY-MM-DD}.json \
        [--outdir {profile}-searches]

Raw capture shape (see car-search SKILL.md):
    {
      "captured": "YYYY-MM-DD",
      "sources": [{"name", "url", "expected_pages", "captured_pages", "status"}],
      "listings": [
        {"url", "source", "variant", "price", "year", "reg", "mileage",
         "location", "specs": ["has_x", ...] or {"has_x": true},
         "is_brand_new_stock": false}
      ]
    }

Price and mileage may be raw scraped text ("£42,995", "12,400 miles").
"""

import argparse
import csv
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dashboard import load_profile  # noqa: E402
from ingest_lib import (  # noqa: E402
    csv_columns,
    dedup_listings,
    derive_listing,
    summarise_sources,
)


def main():
    parser = argparse.ArgumentParser(
        description="Derive the dated listings CSV from a raw capture JSON"
    )
    parser.add_argument("--profile", required=True, help="Path to car-profile.json")
    parser.add_argument("--capture", required=True, help="Path to raw capture JSON")
    parser.add_argument(
        "--outdir",
        default=None,
        help="Output directory (default: the directory containing the capture file)",
    )
    args = parser.parse_args()

    profile_ctx = load_profile(args.profile)
    profile = profile_ctx["profile"]
    profile_name = profile_ctx["profile_name"]
    spec_options = profile_ctx["spec_options"]

    try:
        with open(args.capture, "r") as f:
            capture = json.load(f)
    except FileNotFoundError as exc:
        raise SystemExit(f"Capture file not found: {args.capture}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Capture file {args.capture} is not valid JSON: {exc}") from exc

    if not isinstance(capture, dict):
        raise SystemExit(
            f"Capture file {args.capture} must contain a JSON object, "
            f"got {type(capture).__name__}"
        )
    listings = capture.get("listings", [])
    if not isinstance(listings, list):
        raise SystemExit(
            f"Capture file {args.capture}: 'listings' must be a list, "
            f"got {type(listings).__name__}"
        )

    raw_date = capture.get("captured")
    try:
        capture_date = date.fromisoformat(raw_date) if raw_date else date.today()
    except ValueError as exc:
        raise SystemExit(
            f"Capture file {args.capture}: 'captured' must be YYYY-MM-DD "
            f"(got {raw_date!r})"
        ) from exc

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.capture))
    os.makedirs(outdir, exist_ok=True)

    # ── Derive rows ─────────────────────────────────────────────────────

    rows = []
    skipped = []
    warnings = []
    for i, raw in enumerate(listings):
        if not isinstance(raw, dict):
            skipped.append(f"listings[{i}]: not an object")
            continue
        row, warning = derive_listing(raw, profile, capture_date)
        if row is None:
            skipped.append(f"listings[{i}]: {warning}")
            continue
        if warning:
            warnings.append(f"listings[{i}]: {warning}")
        rows.append(row)

    rows, removed = dedup_listings(rows)

    # ── Write CSV ───────────────────────────────────────────────────────

    csv_path = os.path.join(
        outdir, f"{profile_name}-all-listings-{capture_date.isoformat()}.csv"
    )
    columns = csv_columns(spec_options)
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # ── Write capture manifest ──────────────────────────────────────────

    manifest_path = os.path.join(
        outdir, f"{profile_name}-capture-{capture_date.isoformat()}.json"
    )
    manifest = {
        "sources": summarise_sources(capture.get("sources")),
        "total_captured": len(rows),
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # ── Report ──────────────────────────────────────────────────────────

    print(f"Profile: {profile_ctx['display_name']}")
    print(f"Capture date: {capture_date.isoformat()}")
    print(f"Ingested {len(rows)} listings ({removed} cross-source duplicates collapsed)")
    for w in warnings:
        print(f"WARNING: {w}")
    for s in skipped:
        print(f"WARNING: skipped {s}")
    print(f"CSV written to {csv_path}")
    print(f"Capture manifest written to {manifest_path}")
    if skipped:
        print(
            f"\n{len(skipped)} listing(s) were skipped - re-check those pages "
            f"or correct the capture JSON and re-run."
        )


if __name__ == "__main__":
    main()
