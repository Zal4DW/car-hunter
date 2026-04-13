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
    compute_dep_curves,
    compute_spec_premiums,
    row_to_features,
    safe_int_price,
    extract_listing_id,
    snapshot_diff,
    rolling_window,
    validate_watchlist,
)
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

    _REQUIRED_KEYS = (
        "profile_name", "display_name", "variants", "generations",
        "spec_options", "search_filters", "dashboard",
    )
    _missing = [k for k in _REQUIRED_KEYS if k not in profile]
    if _missing:
        raise SystemExit(
            f"Profile {path} is missing required keys: {', '.join(_missing)}. "
            f"See car-profile-schema.md for the expected format."
        )

    # dashboard.theme sub-keys
    _REQUIRED_THEME_KEYS = ("bg", "card_bg", "card_border", "text", "text_muted")
    _theme = profile["dashboard"].get("theme", {})
    if not isinstance(_theme, dict):
        raise SystemExit(
            f"Profile {path}: dashboard.theme must be an object, got {type(_theme).__name__}"
        )
    _missing_theme = [k for k in _REQUIRED_THEME_KEYS if k not in _theme]
    if _missing_theme:
        raise SystemExit(
            f"Profile {path}: dashboard.theme is missing keys: {', '.join(_missing_theme)}. "
            f"See car-profile-schema.md for the expected format."
        )

    # Per-variant shape
    _REQUIRED_VARIANT_KEYS = ("name", "tier", "colour")
    for i, v in enumerate(profile["variants"]):
        if not isinstance(v, dict):
            raise SystemExit(
                f"Profile {path}: variants[{i}] must be an object, got {type(v).__name__}"
            )
        _missing_v = [k for k in _REQUIRED_VARIANT_KEYS if k not in v]
        if _missing_v:
            raise SystemExit(
                f"Profile {path}: variants[{i}] is missing keys: {', '.join(_missing_v)}"
            )

    # Per-spec shape
    _REQUIRED_SPEC_KEYS = ("key", "label", "weight")
    for i, s in enumerate(profile["spec_options"]):
        if not isinstance(s, dict):
            raise SystemExit(
                f"Profile {path}: spec_options[{i}] must be an object, got {type(s).__name__}"
            )
        _missing_s = [k for k in _REQUIRED_SPEC_KEYS if k not in s]
        if _missing_s:
            raise SystemExit(
                f"Profile {path}: spec_options[{i}] is missing keys: {', '.join(_missing_s)}"
            )

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


def enrich_rows(rows, snapshots, watchlist, listing_ids, price_changes, lid_encoding, today, has_listing_ids):
    """Add composite keys, AutoTrader URLs, days-on-market, price changes, watchlist stars.

    Mutates rows in place. Returns the SNAPSHOT_PULSE summary dict used by Market Pulse.
    """
    pulse = {"new": 0, "removed": 0, "price_drops": 0, "previous_date": None}

    for row in rows:
        row["composite_key"] = f"{row['price']}_{row['location']}"
        row["autotrader_url"] = None
        row["days_on_market"] = None
        row["price_change"] = 0
        row["watched"] = False
        row["watch_note"] = ""

    if has_listing_ids:
        rows_by_id = {r["listing_id"]: r for r in rows if r["listing_id"]}

        for row in rows:
            lid = row["listing_id"]
            if not lid:
                continue
            if lid_encoding.get("enabled") and lid.isdigit():
                row["autotrader_url"] = f"https://www.autotrader.co.uk/car-details/{lid}"
                ld = parse_listing_date(lid)
                if ld:
                    row["days_on_market"] = (today - ld).days

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
                row["watch_note"] = wl[row["listing_id"]].get("note", "") if isinstance(wl[row["listing_id"]], dict) else ""
    else:
        for row in rows:
            key = row["composite_key"]
            lid = listing_ids.get(key)
            if lid and lid_encoding.get("enabled"):
                row["autotrader_url"] = f"https://www.autotrader.co.uk/car-details/{lid}"
                ld = parse_listing_date(lid)
                row["days_on_market"] = (today - ld).days if ld else None
            row["price_change"] = price_changes.get(key, 0)

    return pulse


def load_listing_state(explicit_path, csv_dir, profile_name, has_listing_ids):
    """Resolve and load the listing-state sidecar JSON.

    Returns (listing_ids, price_changes) dicts. Both empty if no sidecar found.
    """
    state_path = None
    if explicit_path:
        state_path = explicit_path
    elif not has_listing_ids:
        auto = os.path.join(csv_dir, f"{profile_name}-listing-state.json")
        if os.path.isfile(auto):
            state_path = auto

    if not state_path:
        return {}, {}

    try:
        with open(state_path, "r") as f:
            state = json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Listing state file {state_path} is not valid JSON: {exc}"
        ) from exc

    if not isinstance(state, dict):
        raise SystemExit(
            f"Listing state file {state_path} must contain a JSON object, "
            f"got {type(state).__name__}"
        )
    lids = state.get("listing_ids", {})
    prices = state.get("price_changes", {})
    if not isinstance(lids, dict):
        raise SystemExit(
            f"Listing state file {state_path}: 'listing_ids' must be an object, "
            f"got {type(lids).__name__}"
        )
    if not isinstance(prices, dict):
        raise SystemExit(
            f"Listing state file {state_path}: 'price_changes' must be an object, "
            f"got {type(prices).__name__}"
        )
    for k, v in lids.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise SystemExit(
                f"Listing state file {state_path}: 'listing_ids' entries must map "
                f"string keys to string values, got {k!r}: {v!r}"
            )
    for k, v in prices.items():
        if not isinstance(k, str) or not isinstance(v, (int, float)):
            raise SystemExit(
                f"Listing state file {state_path}: 'price_changes' entries must map "
                f"string keys to numeric values, got {k!r}: {v!r}"
            )

    print(
        f"Loaded listing state from {state_path}: "
        f"{len(lids)} listing IDs, {len(prices)} price changes"
    )
    return lids, prices


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
        median = prices[len(prices) // 2] if prices else 0
        snapshots.append({
            "date": snap_date,
            "path": path,
            "rows": snap_rows,
            "ids": ids,
            "median_price": median,
        })
    return snapshots


def load_csv(path, spec_options):
    """Load and validate listings from a CSV file, returning a list of row dicts."""
    rows = []
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
            try:
                row = {
                    "listing_id": r.get("listing_id", "") or "",
                    "variant": r["variant"],
                    "generation": r.get("generation", ""),
                    "price": int(r["price"]),
                    "year": int(r["year"]),
                    "reg": r.get("reg", ""),
                    "reg_date": float(r.get("reg_date", 0) or 0),
                    "age_years": float(r.get("age_years", 0) or 0),
                    "age_months": round(float(r.get("age_years", 0) or 0) * 12, 1),
                    "mileage": int(r["mileage"]),
                    "new_price": int(r.get("new_price", 0) or 0),
                    "depreciation_total": int(r.get("depreciation_total", 0) or 0),
                    "depreciation_pa": int(r.get("depreciation_pa", 0) or 0),
                    "location": r.get("location", ""),
                    "is_brand_new_stock": r.get("is_brand_new_stock", "False") == "True",
                }
            except (ValueError, KeyError) as exc:
                raise SystemExit(
                    f"CSV row {_row_num}: cannot parse field - {exc}"
                ) from exc

            for spec in spec_options:
                key = spec["key"]
                row[key] = r.get(key, "False") == "True"

            try:
                row["options_count"] = int(r.get("options_count", 0) or 0)
            except ValueError as exc:
                raise SystemExit(
                    f"CSV row {_row_num}: cannot parse field 'options_count' - {exc}"
                ) from exc

            row["retained_pct"] = _retained_pct(row["price"], row["new_price"])

            rows.append(row)
    return rows


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
    regression_warning,
    template_path=None,
):
    """Render the dashboard HTML from explicit keyword arguments.

    `reg_count` is the number of used listings fed into the regression (only
    the count is needed by the template, not the full row list).
    `template_path` overrides the default template location, used by tests.
    """

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
    preferred_text = " &bull; ".join(highlight_specs) if highlight_specs else "No specific preferences set"

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
        html = _template.substitute(
            DISPLAY_NAME=DISPLAY_NAME,
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
            regression_warning_html=(
                f'<div class="regression-warning"><strong>Regression warning</strong>{regression_warning}</div>'
                if regression_warning else ""
            ),
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

    profile_ctx = load_profile(args.profile)
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

    # Today's date
    if args.date:
        try:
            today = date.fromisoformat(args.date)
        except ValueError as exc:
            raise SystemExit(
                f"--date must be YYYY-MM-DD (got {args.date!r}): {exc}"
            ) from exc
    else:
        today = date.today()

    today_str = today.strftime("%d %B %Y")

    print(f"Profile: {DISPLAY_NAME}")
    print(f"Variants: {', '.join(v['name'] for v in VARIANTS)}")
    print(f"Spec options: {', '.join(s['label'] for s in SPEC_OPTIONS)}")
    print(f"Date: {today_str}")

    # ── Load and parse CSV ──────────────────────────────────────────────

    rows = load_csv(args.csv, SPEC_OPTIONS)

    print(f"Loaded {len(rows)} listings")

    has_listing_ids = any(r["listing_id"] for r in rows)

    # ── Glob dated snapshot CSVs for cross-run analysis ─────────────────
    # Scans the CSV directory for sibling snapshot files named
    # {profile_name}-all-listings-YYYY-MM-DD.csv. Any file missing a
    # `listing_id` column is skipped because it cannot be cross-referenced.

    SNAPSHOTS = load_snapshots(csv_dir, PROFILE_NAME)
    print(f"Loaded {len(SNAPSHOTS)} snapshots")

    # ── Capture manifest (optional) ─────────────────────────────────────
    # Records what the search skill actually scraped, so "removed" listings
    # are not confused with coverage gaps.

    CAPTURE_MANIFEST, CAPTURE_BADGE = load_capture_manifest(csv_dir, PROFILE_NAME, today)

    # ── Watchlist ───────────────────────────────────────────────────────
    WATCHLIST = load_watchlist(csv_dir, PROFILE_NAME)

    # ── Listing IDs and price changes ───────────────────────────────────

    LISTING_IDS, PRICE_CHANGES = load_listing_state(
        args.listing_state, csv_dir, PROFILE_NAME, has_listing_ids
    )

    # ── Composite keys, snapshot diffing, listing tracking ─────────────

    SNAPSHOT_PULSE = enrich_rows(
        rows, SNAPSHOTS, WATCHLIST, LISTING_IDS, PRICE_CHANGES,
        LID_ENCODING, today, has_listing_ids,
    )

    # ── Rolling 28-day time series ──────────────────────────────────────
    TIME_SERIES = []
    if SNAPSHOTS:
        TIME_SERIES = rolling_window(
            [{"date": s["date"], "ids": s["ids"], "median_price": s["median_price"]} for s in SNAPSHOTS],
            today,
            days=28,
        )

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

    coeffs, r_squared, reg_data, regression_warning = run_regression(rows, VARIANT_BY_NAME, tier_features)

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
        pm_coeffs, _, pm_singular = ols_regression(pm_X, pm_y)
        if pm_singular:
            print(
                f"WARNING: price-vs-mileage trendline degenerate "
                f"(singular columns {pm_singular}), suppressing"
            )
            pm_trend = []
        else:
            mileages = sorted(set(r["mileage"] for r in all_pm))
            pm_trend = [
                {"x": min(mileages), "y": round(pm_coeffs[0] + pm_coeffs[1] * min(mileages))},
                {"x": max(mileages), "y": round(pm_coeffs[0] + pm_coeffs[1] * max(mileages))},
            ]
    else:
        pm_trend = []

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
        regression_warning=regression_warning,
    )

    with open(OUTPUT_PATH, 'w') as f:
        f.write(html)

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nDashboard written to {OUTPUT_PATH}")
    print(f"File size: {file_size:,} bytes ({file_size // 1024} KB)")


if __name__ == '__main__':
    main()
