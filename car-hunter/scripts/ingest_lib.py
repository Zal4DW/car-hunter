#!/usr/bin/env python3
"""
Car Hunter - Ingest Library

Pure functions for turning raw captured listings (as extracted by the
car-search skill) into fully derived CSV rows. No I/O, no globals - every
function is deterministic given its inputs and safe to import from tests.

The design principle: the language model only extracts what it can see on
a listing page (price text, year, mileage text, spec mentions). Everything
computable - listing ids, registration dates, ages, depreciation, generation
detection, deduplication - happens here in Python, where arithmetic is exact
and formats are guaranteed.
"""

import re
from datetime import date

from dashboard_lib import extract_listing_id

_NUMBER_RE = re.compile(r"\d[\d,]*")


def parse_price(raw):
    """Coerce a scraped price value to int pounds, or None if unparseable.

    Accepts ints/floats, plain digit strings, and noisy scraped text such as
    "£42,995", "42,995 GBP", or "From £39,000". "POA", empty strings, and
    None return None.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    match = _NUMBER_RE.search(str(raw))
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def parse_mileage(raw):
    """Coerce a scraped mileage value to int miles, or None if unparseable.

    Accepts ints/floats, digit strings, and text such as "12,400 miles".
    """
    return parse_price(raw)


def decimal_year(d):
    """Convert a date to a decimal year (e.g. 1 July 2026 -> ~2026.5)."""
    start = date(d.year, 1, 1)
    end = date(d.year + 1, 1, 1)
    return d.year + (d - start).days / (end - start).days


def detect_generation(year, generations):
    """Return the first generation whose year range contains ``year``.

    ``year_to`` of null/missing means "still current". Returns None when no
    generation matches (caller should warn, not crash).
    """
    if year is None:
        return None
    for gen in generations:
        year_to = gen.get("year_to") or 9999
        if gen["year_from"] <= year <= year_to:
            return gen
    return None


def reg_to_decimal(reg, reg_map, year=None):
    """Resolve a UK reg plate code to a decimal registration date.

    Looks the code up in the profile's reg_date_mapping. When the code is
    missing or unmapped, falls back to the listing year + 0.5 (mid-year),
    which keeps age estimates within six months. Returns None only when
    neither the reg nor the year is usable.
    """
    if reg is not None:
        entry = reg_map.get(str(reg).strip())
        if entry is not None:
            try:
                return float(entry)
            except (TypeError, ValueError):
                pass
    if year is not None:
        return year + 0.5
    return None


def normalise_specs(raw_specs, spec_options):
    """Return {spec_key: bool} for every profile spec option.

    Accepts either a list of present spec keys (the easiest shape for the
    extraction step to emit) or a dict of key -> truthy value. Unknown keys
    are ignored; missing keys default to False.
    """
    present = set()
    if isinstance(raw_specs, dict):
        present = {k for k, v in raw_specs.items() if v}
    elif isinstance(raw_specs, (list, tuple, set)):
        present = set(raw_specs)
    valid_keys = {s["key"] for s in spec_options}
    return {k: (k in valid_keys and k in present) for k in valid_keys}


def apply_standard_specs(spec_flags, variant):
    """Force specs listed in the variant's standard_specs to True."""
    for key in (variant or {}).get("standard_specs", []):
        if key in spec_flags:
            spec_flags[key] = True
    return spec_flags


def derive_listing(raw, profile, capture_date):
    """Turn one raw captured listing into a fully derived CSV row dict.

    Returns (row, None) on success or (None, reason) when the listing is
    missing something essential (price, year, mileage, variant). The reason
    string names the offending value so the skill can surface it.
    """
    variant_name = (raw.get("variant") or "").strip()
    price = parse_price(raw.get("price"))
    mileage = parse_mileage(raw.get("mileage"))
    try:
        year = int(raw.get("year"))
    except (TypeError, ValueError):
        year = None

    problems = []
    if not variant_name:
        problems.append("variant missing")
    if price is None:
        problems.append(f"price {raw.get('price')!r}")
    if mileage is None:
        problems.append(f"mileage {raw.get('mileage')!r}")
    if year is None:
        problems.append(f"year {raw.get('year')!r}")
    if problems:
        return None, "unparseable " + ", ".join(problems)

    variants_by_name = {v["name"]: v for v in profile["variants"]}
    variant = variants_by_name.get(variant_name)

    gen = detect_generation(year, profile["generations"])
    generation = gen["name"] if gen else ""
    new_price = (gen or {}).get("new_prices", {}).get(variant_name, 0) or 0

    reg = raw.get("reg", "") or ""
    reg_map = profile.get("reg_date_mapping", {})
    reg_decimal = reg_to_decimal(reg, reg_map, year=year)
    captured_decimal = decimal_year(capture_date)
    age_years = max(0.0, round(captured_decimal - reg_decimal, 2)) if reg_decimal else 0.0

    is_new = bool(raw.get("is_brand_new_stock"))

    dep_total = (new_price - price) if new_price > 0 else 0
    dep_pa = round(dep_total / age_years) if (new_price > 0 and age_years >= 0.5) else 0
    dep_pct = round(dep_total / new_price * 100, 1) if new_price > 0 else 0

    spec_flags = normalise_specs(raw.get("specs"), profile["spec_options"])
    apply_standard_specs(spec_flags, variant)

    listing_id = extract_listing_id(raw.get("url", ""), source=raw.get("source"))

    row = {
        "listing_id": listing_id,
        "variant": variant_name,
        "generation": generation,
        "price": price,
        "year": year,
        "reg": reg,
        "reg_date": reg_decimal if reg_decimal is not None else "",
        "age_years": age_years,
        "mileage": mileage,
        "new_price": new_price,
        "depreciation_total": dep_total,
        "depreciation_pa": dep_pa,
        "depreciation_pct": dep_pct,
        "location": (raw.get("location") or "").strip(),
        "is_brand_new_stock": is_new,
        "url": raw.get("url", "") or "",
        "source": raw.get("source", "") or "",
    }
    row.update(spec_flags)
    row["options_count"] = sum(1 for v in spec_flags.values() if v)

    warning = None
    if variant is None:
        warning = f"variant {variant_name!r} not in profile - tier features will treat it as base"
    if gen is None:
        gen_warning = f"year {year} matches no generation - no RRP/depreciation available"
        warning = f"{warning}; {gen_warning}" if warning else gen_warning
    return row, warning


def _is_canonical_id(listing_id):
    """AutoTrader numeric ids beat source-hash fallbacks as the cross-run key."""
    return bool(listing_id) and listing_id.isdigit()


def dedup_listings(rows):
    """Collapse the same physical car captured from multiple sources.

    Cars are considered duplicates when price, year, mileage, and location
    (case-insensitive) all match. The surviving row is the one with a
    canonical (AutoTrader numeric) listing id where available, so the same
    car keeps the same id across runs regardless of which source was walked
    first. Returns (deduped_rows, removed_count).
    """
    by_key = {}
    order = []
    for row in rows:
        key = (row["price"], row["year"], row["mileage"], row["location"].lower())
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = row
            order.append(key)
        elif _is_canonical_id(row["listing_id"]) and not _is_canonical_id(existing["listing_id"]):
            by_key[key] = row
    deduped = [by_key[k] for k in order]
    return deduped, len(rows) - len(deduped)


def csv_columns(spec_options):
    """The exact CSV column order the dashboard builder expects."""
    fixed_front = [
        "listing_id", "variant", "generation", "price", "year", "reg",
        "reg_date", "age_years", "mileage", "new_price",
        "depreciation_total", "depreciation_pa", "depreciation_pct",
    ]
    spec_keys = [s["key"] for s in spec_options]
    fixed_back = ["options_count", "location", "is_brand_new_stock", "url", "source"]
    return fixed_front + spec_keys + fixed_back


def summarise_sources(sources):
    """Normalise the sources list for the capture manifest.

    Fills in a 'status' of 'unknown' where missing so the dashboard badge
    logic always has something to read.
    """
    out = []
    for s in sources or []:
        if not isinstance(s, dict):
            continue
        entry = dict(s)
        entry.setdefault("status", "unknown")
        out.append(entry)
    return out
