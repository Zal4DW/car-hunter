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
    js_safe,
    spec_labels as _spec_labels,
    spec_score as _spec_score,
    retained_pct as _retained_pct,
    build_feature_matrix,
    build_tier_features,
    build_time_series,
    compute_dep_curves,
    compute_pm_trend,
    compute_spec_premiums,
    row_to_features,
    safe_int_price,
    snapshot_diff,
    validate_profile,
    validate_watchlist,
)
import html as _html
import glob as _glob
import re as _re


def load_profile(path):
    """Load and validate a car profile JSON, returning derived lookups."""
    try:
        with open(path, "r") as f:
            profile = json.load(f)
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Profile file not found: {path}. "
            f"Run /setup-car to create one, or check ${{CLAUDE_PLUGIN_DATA}}/profiles/."
        ) from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Profile {path} is not valid JSON: {exc}"
        ) from exc

    validate_profile(profile, source=path)

    variants = profile["variants"]
    generations = profile["generations"]

    variant_by_name = {v["name"]: v for v in variants}
    variant_colours = {v["name"]: v["colour"] for v in variants}

    new_prices = {}
    for gen in generations:
        for vname, price in gen.get("new_prices", {}).items():
            if vname not in new_prices:
                new_prices[vname] = price

    return {
        "profile": profile,
        "profile_name": profile["profile_name"],
        "display_name": profile["display_name"],
        "variants": variants,
        "generations": generations,
        "spec_options": profile["spec_options"],
        "search_filters": profile["search_filters"],
        "dashboard": profile["dashboard"],
        "reg_map": profile.get("reg_date_mapping", {}),
        "lid_encoding": profile.get("listing_id_date_encoding", {"enabled": False}),
        "variant_by_name": variant_by_name,
        "variant_colours": variant_colours,
        "new_prices": new_prices,
    }


def run_regression(rows, variant_by_name, tier_features):
    """Fit a multivariate OLS model over used listings, then annotate all rows.

    Mutates rows in place with `predicted_price`, `value_deviation`, and
    `value_deviation_pct`. Returns (coeffs, r_squared, reg_data, warning)
    where warning is either None (healthy model) or a human-readable string
    explaining why the model is unreliable (insufficient rows, singular
    features). Callers should surface the warning in the dashboard HTML
    because a stdout-only message is invisible once the file is opened.
    """
    reg_data = [r for r in rows if not r["is_brand_new_stock"] and r["age_years"] >= 0.5]
    print(f"Regression on {len(reg_data)} used listings (age >= 6 months)")

    feature_names = ["intercept", "age_months", "mileage", "spec_score"] + [
        tf["name"] for tf in tier_features
    ]

    X, y = build_feature_matrix(reg_data, variant_by_name, tier_features)

    warning = None
    if len(X) >= len(feature_names):
        coeffs, r_squared, singular_cols = ols_regression(X, y)
        print(f"Regression R² = {r_squared:.4f}")
        print(f"Features: {feature_names}")
        print(f"Coefficients: {[f'{c:.2f}' for c in coeffs]}")
        if singular_cols:
            dropped = [feature_names[i] for i in singular_cols]
            print(f"WARNING: singular columns detected - dropped from model: {dropped}")
            warning = (
                f"Model unreliable: features {', '.join(dropped)} were collinear "
                f"with other columns and dropped. Value scores may be skewed."
            )
    else:
        print(f"WARNING: Not enough data for regression ({len(X)} rows, {len(feature_names)} features)")
        coeffs = [0] * len(feature_names)
        r_squared = 0
        warning = (
            f"Insufficient data for regression: {len(X)} used listings available, "
            f"{len(feature_names)} features required. Value scores and deal rankings "
            f"are not meaningful below this threshold."
        )

    for r in rows:
        features = row_to_features(r, variant_by_name, tier_features)
        predicted = sum(f * c for f, c in zip(features, coeffs))
        r["predicted_price"] = round(predicted)
        if predicted > 0:
            r["value_deviation"] = round(r["price"] - predicted)
            r["value_deviation_pct"] = round((r["price"] - predicted) / predicted * 100, 1)
        else:
            # Model produced a zero or negative prediction - unreliable. Don't
            # emit an absolute deviation that would render as "overpriced by
            # £X (0%)" on the dashboard.
            r["value_deviation"] = 0
            r["value_deviation_pct"] = 0

    return coeffs, r_squared, reg_data, warning


def _init_enrichment_fields(rows):
    """Set every row's enrichment columns to their default values."""
    for row in rows:
        row["composite_key"] = f"{row['price']}_{row['location']}"
        row["autotrader_url"] = None
        row["days_on_market"] = None
        row["price_change"] = 0
        row["watched"] = False
        row["watch_note"] = ""


def enrich_rows(rows, snapshots, watchlist, lid_encoding, today):
    """Add composite keys, AutoTrader URLs, days-on-market, price changes, watchlist stars.

    Mutates rows in place. Populates autotrader_url/days_on_market from
    encoded listing IDs, diffs against the most recent prior snapshot for
    price_change, joins the watchlist, and returns the SNAPSHOT_PULSE dict
    for Market Pulse. Rows without a listing_id keep their default
    enrichment values.
    """
    _init_enrichment_fields(rows)
    pulse = {"new": 0, "removed": 0, "price_drops": 0, "previous_date": None}
    rows_by_id = {r["listing_id"]: r for r in rows if r["listing_id"]}

    # Track how many encoded IDs successfully yielded a date so we can
    # warn if almost all parses failed (typically a scraper regression).
    attempted = 0
    parsed = 0
    for row in rows:
        lid = row["listing_id"]
        if not lid:
            continue
        if lid_encoding.get("enabled") and lid.isdigit():
            row["autotrader_url"] = f"https://www.autotrader.co.uk/car-details/{lid}"
            attempted += 1
            ld = parse_listing_date(lid)
            if ld:
                parsed += 1
                row["days_on_market"] = (today - ld).days
        elif row.get("url"):
            # Non-AutoTrader sources: link straight to the captured URL so
            # every row in the table is clickable, not just AutoTrader ones.
            row["autotrader_url"] = row["url"]
    if attempted and parsed < attempted:
        print(
            f"WARNING: parsed {parsed}/{attempted} listing IDs as encoded dates; "
            f"{attempted - parsed} could not be decoded. Days-on-market may be incomplete."
        )

    today_snap = next((s for s in snapshots if s["date"] == today), None)
    prior = [s for s in snapshots if s["date"] < today]
    if today_snap and prior:
        prev = prior[-1]
        diff = snapshot_diff(
            [{"listing_id": r.get("listing_id", ""), "price": safe_int_price(r.get("price")) or 0} for r in prev["rows"]],
            [{"listing_id": r.get("listing_id", ""), "price": safe_int_price(r.get("price")) or 0} for r in today_snap["rows"]],
        )
        for ch in diff["price_changed"]:
            r = rows_by_id.get(ch["id"])
            if r is not None:
                r["price_change"] = ch["delta"]
        pulse = {
            "new": len(diff["new"]),
            "removed": len(diff["removed"]),
            "price_drops": sum(1 for c in diff["price_changed"] if c["delta"] < 0),
            "previous_date": prev["date"].isoformat(),
        }
        print(
            f"Snapshot diff vs {prev['date'].isoformat()}: "
            f"+{pulse['new']} new, -{pulse['removed']} removed, "
            f"{pulse['price_drops']} price drops"
        )

    wl = watchlist["listings"]
    for row in rows:
        if row["listing_id"] in wl:
            row["watched"] = True
            entry = wl[row["listing_id"]]
            row["watch_note"] = entry.get("note", "") if isinstance(entry, dict) else ""

    return pulse


_SNAPSHOT_DATE_RE = _re.compile(r"-(\d{4}-\d{2}-\d{2})\.csv$")


def project_table_data(rows):
    """Project enriched rows into the flat dict shape the JS table consumes.

    Excludes brand-new stock. Each entry carries only the columns the
    dashboard table renders.
    """
    table = []
    for r in rows:
        if r["is_brand_new_stock"]:
            continue
        table.append({
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
            "listing_id": r["listing_id"],
            "watched": r["watched"],
            "watch_note": r["watch_note"],
        })
    return table


def load_watchlist(csv_dir, profile_name):
    """Load the {profile_name}-watchlist.json sidecar if present.

    Returns a dict shaped {"listings": {...}}. Missing file yields an empty
    watchlist. Malformed JSON or shape raises SystemExit with a clear message.
    """
    path = os.path.join(csv_dir, f"{profile_name}-watchlist.json")
    if not os.path.isfile(path):
        return {"listings": {}}

    try:
        with open(path, "r") as wf:
            data = json.load(wf)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Watchlist file {path} is not valid JSON: {exc}"
        ) from exc
    watchlist = validate_watchlist(data, source=path)
    if watchlist["listings"]:
        print(f"Loaded watchlist: {len(watchlist['listings'])} starred listings")
    return watchlist


def load_capture_manifest(csv_dir, profile_name, today):
    """Load and validate the capture manifest for today's run.

    Returns (manifest, badge). manifest is None when no file exists; badge is
    always populated with at least the 'unknown' grey default so callers can
    hand it to the template unconditionally.
    """
    manifest = None
    badge = {"status": "unknown", "colour": "grey", "label": "No capture manifest"}
    path = os.path.join(csv_dir, f"{profile_name}-capture-{today.isoformat()}.json")
    if not os.path.isfile(path):
        return manifest, badge

    try:
        with open(path, "r") as cf:
            manifest = json.load(cf)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Capture manifest {path} is not valid JSON: {exc}"
        ) from exc

    if not isinstance(manifest, dict):
        raise SystemExit(
            f"Capture manifest {path} must contain a JSON object, "
            f"got {type(manifest).__name__}"
        )
    sources = manifest.get("sources", [])
    if not isinstance(sources, list):
        raise SystemExit(
            f"Capture manifest {path}: 'sources' must be a list, "
            f"got {type(sources).__name__}"
        )
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            raise SystemExit(
                f"Capture manifest {path}: 'sources[{i}]' must be an object, "
                f"got {type(s).__name__}"
            )
    statuses = [s.get("status", "unknown") for s in sources]
    if any(s == "failed" for s in statuses):
        badge = {"status": "failed", "colour": "red", "label": "Capture: failed"}
    elif any(s == "partial" for s in statuses):
        badge = {"status": "partial", "colour": "amber", "label": "Capture: partial"}
    elif statuses and all(s == "ok" for s in statuses):
        badge = {"status": "ok", "colour": "green", "label": "Capture: complete"}
    badge["sources"] = sources
    print(f"Capture manifest: {badge['label']} ({len(sources)} sources)")
    return manifest, badge


def load_snapshots(csv_dir, profile_name):
    """Scan csv_dir for {profile_name}-all-listings-YYYY-MM-DD.csv snapshots.

    Returns a list of {date, path, rows, ids, median_price} dicts. Files with
    missing/invalid date tags or no listing_id column emit a WARNING to stdout
    and are excluded from the result.
    """
    snapshots = []
    pattern = os.path.join(csv_dir, f"{profile_name}-all-listings-*.csv")
    for path in sorted(_glob.glob(pattern)):
        match = _SNAPSHOT_DATE_RE.search(path)
        if not match:
            print(f"WARNING: skipping snapshot {path}: filename has no date tag")
            continue
        try:
            ys, ms, ds = match.group(1).split("-")
            snap_date = date(int(ys), int(ms), int(ds))
        except ValueError as exc:
            print(f"WARNING: skipping snapshot {path}: invalid date in filename ({exc})")
            continue
        with open(path, "r") as sf:
            reader = csv.DictReader(sf)
            if reader.fieldnames is None or "listing_id" not in reader.fieldnames:
                print(f"WARNING: skipping snapshot {path}: no listing_id column, cannot cross-reference")
                continue
            snap_rows = list(reader)
        ids = {r.get("listing_id", "") for r in snap_rows if r.get("listing_id")}
        prices = []
        dropped = 0
        for r in snap_rows:
            raw = r.get("price")
            if raw in (None, ""):
                continue
            parsed = safe_int_price(raw)
            if parsed is None:
                dropped += 1
            else:
                prices.append(parsed)
        if dropped:
            print(
                f"WARNING: snapshot {path}: {dropped} row(s) had unparseable "
                f"price values, excluded from median"
            )
        prices.sort()
        if not prices:
            median = 0
        else:
            mid = len(prices) // 2
            median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2
        snapshots.append({
            "date": snap_date,
            "path": path,
            "rows": snap_rows,
            "ids": ids,
            "median_price": median,
        })
    return snapshots


def load_csv(path, spec_options):
    """Load listings from a CSV file.

    Returns (rows, skipped) where skipped is a list of human-readable
    reasons for rows that could not be parsed. A missing file or missing
    required columns is still fatal (the data is unusable), but individual
    bad rows are skipped and reported rather than aborting the whole build -
    one mangled price cell should not cost the user the day's dashboard.
    """
    rows = []
    skipped = []
    try:
        f = open(path, "r")
    except FileNotFoundError as exc:
        raise SystemExit(
            f"CSV file not found: {path}. "
            f"Check the path or run /search-cars to generate one."
        ) from exc
    with f:
        reader = csv.DictReader(f)
        _REQUIRED_CSV_COLS = {"variant", "price", "year", "mileage"}
        if reader.fieldnames:
            _missing_cols = _REQUIRED_CSV_COLS - set(reader.fieldnames)
        else:
            _missing_cols = _REQUIRED_CSV_COLS
        if _missing_cols:
            raise SystemExit(
                f"CSV {path} is missing required columns: {', '.join(sorted(_missing_cols))}"
            )
        for _row_num, r in enumerate(reader, start=1):
            price = safe_int_price(r.get("price"))
            mileage = safe_int_price(r.get("mileage"))
            problems = []
            if price is None:
                problems.append(f"price {r.get('price')!r}")
            if mileage is None:
                problems.append(f"mileage {r.get('mileage')!r}")
            try:
                year = int(r["year"])
            except (ValueError, KeyError, TypeError):
                problems.append(f"year {r.get('year')!r}")
                year = None
            try:
                age_years = float(r.get("age_years", 0) or 0)
                reg_date = float(r.get("reg_date", 0) or 0)
            except ValueError:
                problems.append(f"age_years/reg_date {r.get('age_years')!r}")
                age_years = reg_date = None
            if problems:
                reason = f"row {_row_num}: unparseable {', '.join(problems)}"
                print(f"WARNING: skipping CSV {reason}")
                skipped.append(reason)
                continue

            row = {
                "listing_id": r.get("listing_id", "") or "",
                "variant": r.get("variant", "") or "",
                "generation": r.get("generation", ""),
                "price": price,
                "year": year,
                "reg": r.get("reg", ""),
                "reg_date": reg_date,
                "age_years": age_years,
                "age_months": round(age_years * 12, 1),
                "mileage": mileage,
                "new_price": safe_int_price(r.get("new_price")) or 0,
                "depreciation_total": safe_int_price(r.get("depreciation_total")) or 0,
                "depreciation_pa": safe_int_price(r.get("depreciation_pa")) or 0,
                "location": r.get("location", ""),
                "url": r.get("url", "") or "",
                "is_brand_new_stock": r.get("is_brand_new_stock", "False") == "True",
            }

            for spec in spec_options:
                key = spec["key"]
                row[key] = r.get(key, "False") == "True"

            row["options_count"] = safe_int_price(r.get("options_count")) or 0

            row["retained_pct"] = _retained_pct(row["price"], row["new_price"])

            rows.append(row)
    return rows, skipped


def build_html(
    *,
    DISPLAY_NAME,
    DASHBOARD,
    VARIANTS,
    GENERATIONS,
    SEARCH_FILTERS,
    SPEC_OPTIONS,
    VARIANT_COLOURS,
    highlight_specs,
    table_data,
    dep_curves,
    spec_premiums,
    pm_trend,
    WATCHLIST,
    TIME_SERIES,
    SNAPSHOT_PULSE,
    CAPTURE_BADGE,
    r_squared,
    today_str,
    reg_count,
    warnings,
    template_path=None,
    profile_name="",
):
    """Render the dashboard HTML from explicit keyword arguments.

    `reg_count` is the number of used listings fed into the regression (only
    the count is needed by the template, not the full row list).
    `warnings` is a list of human-readable data-quality warning strings
    rendered as a banner at the top of the dashboard.
    `template_path` overrides the default template location, used by tests.
    """

    # ── Build HTML ──────────────────────────────────────────────────────

    theme = DASHBOARD["theme"]
    bg = theme["bg"]
    card_bg = theme["card_bg"]
    card_border = theme["card_border"]
    text_colour = theme["text"]
    text_muted = theme["text_muted"]

    esc = _html.escape

    # Build variant filter options
    variant_options_html = '<option value="all">All variants</option>'
    for v in VARIANTS:
        variant_options_html += f'\n                <option value="{esc(v["name"], quote=True)}">{esc(v["name"])}</option>'

    # Build generation filter options
    gen_options_html = '<option value="all">All</option>'
    for g in GENERATIONS:
        gen_options_html += f'\n                <option value="{esc(g["name"], quote=True)}">{esc(g["label"])}</option>'

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
        f"Within {esc(str(SEARCH_FILTERS['max_distance']))} miles of {esc(str(SEARCH_FILTERS['postcode']))}"
    )
    if SEARCH_FILTERS.get("exclude_write_offs"):
        criteria_text += " &bull; Exclude Cat S/N"

    # Preferred spec text
    preferred_text = (
        " &bull; ".join(esc(s) for s in highlight_specs)
        if highlight_specs else "No specific preferences set"
    )

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

    # Load and render the HTML template. Pre-compute js_safe() and other
    # non-trivial expressions so the template can use plain string.Template
    # $name placeholders without needing f-string machinery.
    import string as _string
    if template_path is None:
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "templates", "dashboard.html"
        )
    try:
        with open(template_path, "r") as _tf:
            _template = _string.Template(_tf.read())
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Dashboard template not found at {template_path}. "
            f"This indicates a corrupt plugin install - reinstall car-hunter from the marketplace."
        ) from exc
    except OSError as exc:
        raise SystemExit(
            f"Cannot read dashboard template {template_path}: {exc}"
        ) from exc
    try:
        warning_html = "".join(
            f'<div class="regression-warning"><strong>Data warning</strong>{esc(w)}</div>'
            for w in warnings
        )
        html = _template.substitute(
            DISPLAY_NAME=esc(DISPLAY_NAME),
            profile_name=js_safe(profile_name),
            bg=bg,
            card_bg=card_bg,
            card_border=card_border,
            text_colour=text_colour,
            text_muted=text_muted,
            today_str=today_str,
            variant_options_html=variant_options_html,
            gen_options_html=gen_options_html,
            mileage_options_html=mileage_options_html,
            budget_options_html=budget_options_html,
            criteria_text=criteria_text,
            preferred_text=preferred_text,
            gen_filter_js=gen_filter_js,
            r_squared_formatted=f"{r_squared:.3f}",
            capture_colour=CAPTURE_BADGE["colour"],
            capture_label=CAPTURE_BADGE["label"],
            table_count=len(table_data),
            reg_count=reg_count,
            regression_warning_html=warning_html,
            all_data_json=js_safe(table_data),
            dep_curves_json=js_safe(dep_curves),
            spec_premiums_json=js_safe(spec_premiums),
            pm_trend_json=js_safe(pm_trend),
            variant_colours_json=js_safe(VARIANT_COLOURS),
            highlight_specs_json=js_safe(highlight_specs),
            watchlist_json=js_safe(WATCHLIST),
            time_series_json=js_safe(TIME_SERIES),
            snapshot_pulse_json=js_safe(SNAPSHOT_PULSE),
            capture_json=js_safe(CAPTURE_BADGE),
        )
    except KeyError as exc:
        raise SystemExit(
            f"Dashboard template {template_path} references unknown placeholder {exc}. "
            f"Template and builder are out of sync - check your plugin version."
        ) from exc
    except ValueError as exc:
        raise SystemExit(
            f"Dashboard template {template_path} has malformed $-substitution: {exc}"
        ) from exc
    return html


def main():
    # ── Argument parsing ────────────────────────────────────────────────

    """Main."""
    parser = argparse.ArgumentParser(description="Build car value dashboard from profile and CSV data")
    parser.add_argument("--profile", required=True, help="Path to car-profile.json")
    parser.add_argument("--csv", default=None, help="Path to CSV data file")
    parser.add_argument("--output", default=None, help="Output HTML path (default: auto-generated)")
    parser.add_argument(
        "--date",
        default=None,
        help="Override the build date (YYYY-MM-DD). Defaults to the date in the "
        "CSV filename so snapshot diffing works when the dashboard is rebuilt "
        "after the search day; falls back to today.",
    )
    parser.add_argument(
        "--summary-json",
        default=None,
        help="Also write a machine-readable run summary (key findings, top deals, "
        "warnings) to this path.",
    )
    parser.add_argument(
        "--validate-profile",
        action="store_true",
        help="Validate the profile JSON and exit without building. Use after "
        "/setup-car so schema mistakes surface immediately.",
    )
    args = parser.parse_args()

    # ── Load profile ────────────────────────────────────────────────────

    profile_ctx = load_profile(args.profile)

    if args.validate_profile:
        print(f"Profile {args.profile} is valid: {profile_ctx['display_name']} "
              f"({len(profile_ctx['variants'])} variants, "
              f"{len(profile_ctx['generations'])} generations, "
              f"{len(profile_ctx['spec_options'])} spec options)")
        return

    if not args.csv:
        parser.error("--csv is required unless --validate-profile is used")
    PROFILE_NAME = profile_ctx["profile_name"]
    DISPLAY_NAME = profile_ctx["display_name"]
    VARIANTS = profile_ctx["variants"]
    GENERATIONS = profile_ctx["generations"]
    SPEC_OPTIONS = profile_ctx["spec_options"]
    SEARCH_FILTERS = profile_ctx["search_filters"]
    DASHBOARD = profile_ctx["dashboard"]
    LID_ENCODING = profile_ctx["lid_encoding"]
    VARIANT_BY_NAME = profile_ctx["variant_by_name"]
    VARIANT_COLOURS = profile_ctx["variant_colours"]

    csv_dir = os.path.dirname(os.path.abspath(args.csv))
    OUTPUT_PATH = args.output or os.path.join(csv_dir, f"{PROFILE_NAME}-dashboard.html")

    # Build date. Snapshot diffing and the capture badge are keyed to the
    # search date, so when the dashboard is rebuilt a day or two later the
    # date embedded in the CSV filename is the right anchor - not the wall
    # clock. Priority: --date flag > CSV filename tag > today.
    if args.date:
        try:
            today = date.fromisoformat(args.date)
        except ValueError as exc:
            raise SystemExit(
                f"--date must be YYYY-MM-DD (got {args.date!r}): {exc}"
            ) from exc
    else:
        match = _SNAPSHOT_DATE_RE.search(os.path.basename(args.csv))
        if match:
            today = date.fromisoformat(match.group(1))
            print(f"Using CSV snapshot date {today.isoformat()} as build date")
        else:
            today = date.today()

    today_str = today.strftime("%d %B %Y")

    print(f"Profile: {DISPLAY_NAME}")
    print(f"Variants: {', '.join(v['name'] for v in VARIANTS)}")
    print(f"Spec options: {', '.join(s['label'] for s in SPEC_OPTIONS)}")
    print(f"Date: {today_str}")

    # ── Load and parse CSV ──────────────────────────────────────────────

    rows, skipped_rows = load_csv(args.csv, SPEC_OPTIONS)

    print(f"Loaded {len(rows)} listings")

    # ── Glob dated snapshot CSVs for cross-run analysis ─────────────────
    # Scans the CSV directory for sibling snapshot files named
    # {profile_name}-all-listings-YYYY-MM-DD.csv. Any file missing a
    # `listing_id` column is skipped because it cannot be cross-referenced.

    SNAPSHOTS = load_snapshots(csv_dir, PROFILE_NAME)
    print(f"Loaded {len(SNAPSHOTS)} snapshots")

    # ── Capture manifest (optional) ─────────────────────────────────────
    # Records what the search skill actually scraped, so "removed" listings
    # are not confused with coverage gaps.

    _, CAPTURE_BADGE = load_capture_manifest(csv_dir, PROFILE_NAME, today)

    # ── Watchlist ───────────────────────────────────────────────────────
    WATCHLIST = load_watchlist(csv_dir, PROFILE_NAME)

    # ── Composite keys, snapshot diffing, listing tracking ─────────────

    SNAPSHOT_PULSE = enrich_rows(rows, SNAPSHOTS, WATCHLIST, LID_ENCODING, today)

    # ── Rolling 28-day time series ──────────────────────────────────────
    TIME_SERIES = build_time_series(SNAPSHOTS, today, days=28)

    # ── Spec labels and scores ──────────────────────────────────────────

    for row in rows:
        row["spec_labels"] = _spec_labels(row, SPEC_OPTIONS)
        row["spec_text"] = ", ".join(row["spec_labels"]) if row["spec_labels"] else "Base"
        row["spec_score"] = _spec_score(row, SPEC_OPTIONS)

    # ── Determine variant tier features ─────────────────────────────────
    # Build a list of tier feature names for tiers > 0

    tier_features = build_tier_features(VARIANTS)
    print(f"Tier features: {[tf['name'] for tf in tier_features]}")

    # ── Multivariate regression ─────────────────────────────────────────
    # price = b0 + b1*age_months + b2*mileage + b3*spec_score + b4*tier_1 + b5*tier_2 + ...

    coeffs, r_squared, reg_data, regression_warning = run_regression(rows, VARIANT_BY_NAME, tier_features)

    warnings = []
    if skipped_rows:
        warnings.append(
            f"{len(skipped_rows)} CSV row(s) could not be parsed and were "
            f"excluded: {'; '.join(skipped_rows[:3])}"
            + (" (and more)" if len(skipped_rows) > 3 else "")
        )
    if regression_warning:
        warnings.append(regression_warning)

    # ── Spec premium calculation ────────────────────────────────────────

    spec_premiums = compute_spec_premiums(reg_data, SPEC_OPTIONS)

    print("\nSpec Premiums:")
    for sp in spec_premiums:
        insuf = " (insufficient data)" if sp.get("insufficient") else ""
        print(f"  {sp['label']}: £{sp['premium']:+,}{insuf} (n={sp['count_with']})")

    # ── Depreciation curve data ─────────────────────────────────────────

    dep_curves = compute_dep_curves(rows)

    for v, d in dep_curves.items():
        fm = d["flatten_month"]
        if fm:
            print(f"\n{v}: poly=[{d['poly'][0]:.0f}, {d['poly'][1]:.1f}, {d['poly'][2]:.3f}], flattening ~{fm} months")
        else:
            print(f"\n{v}: no clear flattening point")

    # ── Serialise data for JS ───────────────────────────────────────────


    # Table data (all used cars, sorted by value_deviation ascending)
    table_data = project_table_data(rows)


    # Fit trendline for price vs mileage. Per-variant scatter is derived on
    # the JS side from ALL_DATA; only the trendline comes from Python.
    pm_trend, pm_singular = compute_pm_trend(table_data)
    if pm_singular:
        print(
            f"WARNING: price-vs-mileage trendline degenerate "
            f"(singular columns {pm_singular}), suppressing"
        )

    print(f"\nTable data: {len(table_data)} used listings")

    # ── Build highlight spec keys for JS ────────────────────────────────

    highlight_specs = [s["label"] for s in SPEC_OPTIONS if s.get("highlight")]

    # ── Build HTML ──────────────────────────────────────────────────────

    html = build_html(
        DISPLAY_NAME=DISPLAY_NAME,
        DASHBOARD=DASHBOARD,
        VARIANTS=VARIANTS,
        GENERATIONS=GENERATIONS,
        SEARCH_FILTERS=SEARCH_FILTERS,
        SPEC_OPTIONS=SPEC_OPTIONS,
        VARIANT_COLOURS=VARIANT_COLOURS,
        highlight_specs=highlight_specs,
        table_data=table_data,
        dep_curves=dep_curves,
        spec_premiums=spec_premiums,
        pm_trend=pm_trend,
        WATCHLIST=WATCHLIST,
        TIME_SERIES=TIME_SERIES,
        SNAPSHOT_PULSE=SNAPSHOT_PULSE,
        CAPTURE_BADGE=CAPTURE_BADGE,
        r_squared=r_squared,
        today_str=today_str,
        reg_count=len(reg_data),
        warnings=warnings,
        profile_name=PROFILE_NAME,
    )

    with open(OUTPUT_PATH, 'w') as f:
        f.write(html)

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nDashboard written to {OUTPUT_PATH}")
    print(f"File size: {file_size:,} bytes ({file_size // 1024} KB)")

    # ── Machine-readable run summary ────────────────────────────────────
    # Lets the dashboard skill present key findings from structured data
    # instead of re-parsing stdout.

    if args.summary_json:
        top_deals = sorted(
            (r for r in table_data if r["predicted"] > 0),
            key=lambda r: r["deviation_pct"],
        )[:5]
        summary = {
            "profile": PROFILE_NAME,
            "display_name": DISPLAY_NAME,
            "date": today.isoformat(),
            "dashboard_path": OUTPUT_PATH,
            "listings": len(table_data),
            "regression": {"r_squared": round(r_squared, 4), "rows": len(reg_data)},
            "top_deals": [
                {
                    "listing_id": r["listing_id"],
                    "variant": r["variant"],
                    "year": r["year"],
                    "price": r["price"],
                    "predicted": r["predicted"],
                    "deviation": r["deviation"],
                    "deviation_pct": r["deviation_pct"],
                    "mileage": r["mileage"],
                    "location": r["location"],
                }
                for r in top_deals
            ],
            "spec_premiums": spec_premiums,
            "flattening_points": {
                v: d["flatten_month"] for v, d in dep_curves.items()
            },
            "pulse": SNAPSHOT_PULSE,
            "capture": {"status": CAPTURE_BADGE["status"], "label": CAPTURE_BADGE["label"]},
            "warnings": warnings,
        }
        with open(args.summary_json, "w") as sf:
            json.dump(summary, sf, indent=2)
        print(f"Run summary written to {args.summary_json}")


if __name__ == '__main__':
    main()
