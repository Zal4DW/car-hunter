#!/usr/bin/env python3
"""
Car Hunter - Compare Library

Pure functions behind compare_cars.py. Given several cars' enriched listing
rows (each car scored by its own profile's regression), produce a
budget-anchored comparison that answers questions like "what can I get for
£40k?" across every car the user tracks.

No I/O, no globals - testable in isolation, same rules as dashboard_lib.
"""


def _median(values):
    """Median of a numeric list, or None when empty."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def _listing_brief(row):
    """The fields worth relaying about a single listing in a comparison."""
    return {
        "listing_id": row.get("listing_id", ""),
        "variant": row.get("variant", ""),
        "year": row.get("year"),
        "price": row.get("price"),
        "mileage": row.get("mileage"),
        "age_years": row.get("age_years"),
        "location": row.get("location", ""),
        "predicted_price": row.get("predicted_price"),
        "value_deviation_pct": row.get("value_deviation_pct"),
        "retained_pct": row.get("retained_pct"),
        "url": row.get("autotrader_url") or row.get("url") or "",
    }


def budget_slice(rows, budget):
    """Used listings at or under the budget. None budget means no cap."""
    used = [r for r in rows if not r.get("is_brand_new_stock")]
    if budget is None:
        return used
    return [r for r in used if r.get("price") is not None and r["price"] <= budget]


def summarise_car(display_name, rows, budget):
    """Build one car's side of the comparison.

    ``rows`` must already carry the per-car regression annotations
    (predicted_price, value_deviation_pct) and retained_pct. Returns a dict
    with market shape (counts, cheapest entry point), what the budget buys
    (newest year, lowest mileage, medians), and the standout picks (best
    value, newest, lowest mileage).
    """
    used = [r for r in rows if not r.get("is_brand_new_stock")]
    affordable = budget_slice(rows, budget)

    summary = {
        "display_name": display_name,
        "total_listings": len(used),
        "under_budget": len(affordable),
        "cheapest_price": min((r["price"] for r in used), default=None),
        "budget": budget,
    }
    if not affordable:
        summary["message"] = (
            "Nothing at this budget"
            + (f" - market starts at £{summary['cheapest_price']:,}"
               if summary["cheapest_price"] else "")
        )
        return summary

    scored = [r for r in affordable if (r.get("predicted_price") or 0) > 0]
    best_value = min(scored, key=lambda r: r["value_deviation_pct"]) if scored else None

    summary.update({
        "newest_year": max(r["year"] for r in affordable),
        "lowest_mileage": min(r["mileage"] for r in affordable),
        "median_age_years": _median([r.get("age_years") for r in affordable]),
        "median_mileage": _median([r.get("mileage") for r in affordable]),
        "median_price": _median([r.get("price") for r in affordable]),
        "median_retained_pct": _median([r.get("retained_pct") for r in affordable]),
        "variants_available": sorted({r["variant"] for r in affordable if r.get("variant")}),
        "best_value": _listing_brief(best_value) if best_value else None,
        "newest": _listing_brief(max(affordable, key=lambda r: (r["year"], -r["mileage"]))),
        "lowest_mileage_pick": _listing_brief(min(affordable, key=lambda r: r["mileage"])),
    })
    return summary


def comparison_summary(car_summaries, budget):
    """Assemble the cross-car comparison envelope.

    Adds a 'headline' hint naming which car offers the newest example and
    which retains value best at this budget - the seeds of "what can I get
    for £X" - while leaving interpretation to the caller.
    """
    result = {"budget": budget, "cars": car_summaries}

    with_stock = [c for c in car_summaries if c.get("under_budget")]
    if with_stock:
        newest = max(with_stock, key=lambda c: c["newest_year"])
        result["newest_at_budget"] = {
            "display_name": newest["display_name"],
            "year": newest["newest_year"],
        }
        retainers = [c for c in with_stock if c.get("median_retained_pct") is not None]
        if retainers:
            best_retainer = max(retainers, key=lambda c: c["median_retained_pct"])
            result["best_value_retention"] = {
                "display_name": best_retainer["display_name"],
                "median_retained_pct": best_retainer["median_retained_pct"],
            }
    return result
