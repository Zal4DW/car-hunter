#!/usr/bin/env python3
"""
Car Hunter - Negotiation Library

Pure functions behind negotiation_brief.py. Given a target listing, the
regression-annotated market rows, and the dated snapshot archive, compute
the EVIDENCE a buyer can take into a dealer negotiation: how the asking
price compares to the model, how long the car has sat, whether the price
has already moved, which cheaper comparables exist, and how much supply
the dealer is competing against.

No advice text lives here - turning evidence into strategy is the skill's
job. No I/O, no globals.
"""


def price_history(snapshots, listing_id):
    """Track one listing across the dated snapshot archive.

    Returns {first_seen, last_seen, days_observed, prices: [{date, price}],
    total_change} using only snapshots where the listing appears. Prices are
    recorded only when they change, so the list reads as a price timeline.
    Returns None when the listing appears in no snapshot.
    """
    if not listing_id:
        return None
    timeline = []
    for snap in snapshots:
        for row in snap["rows"]:
            if row.get("listing_id") == listing_id:
                raw = str(row.get("price", "")).replace(",", "").strip()
                try:
                    price = int(raw)
                except ValueError:
                    continue
                if not timeline or timeline[-1]["price"] != price:
                    timeline.append({"date": snap["date"].isoformat(), "price": price})
                break
    if not timeline:
        return None
    first = next(s for s in snapshots
                 if any(r.get("listing_id") == listing_id for r in s["rows"]))
    last = next(s for s in reversed(snapshots)
                if any(r.get("listing_id") == listing_id for r in s["rows"]))
    return {
        "first_seen": first["date"].isoformat(),
        "last_seen": last["date"].isoformat(),
        "days_observed": (last["date"] - first["date"]).days,
        "prices": timeline,
        "total_change": timeline[-1]["price"] - timeline[0]["price"],
    }


def find_comparables(rows, target, max_n=5):
    """Closest alternatives to the target, nearest age/mileage first.

    Same variant beats same tier beats anything else; within a band,
    proximity is scored on age (1 year ~ 12k miles). Each comparable is
    returned as a brief with the price difference against the target, so
    the negotiation case ("the same car is £2k less in Leeds") is ready
    to cite. Brand-new stock and the target itself are excluded.
    """
    candidates = [
        r for r in rows
        if not r.get("is_brand_new_stock")
        and r.get("listing_id") != target.get("listing_id")
        and r.get("price") is not None
    ]

    def closeness(r):
        same_variant = 0 if r.get("variant") == target.get("variant") else 1
        age_gap = abs((r.get("age_years") or 0) - (target.get("age_years") or 0))
        mileage_gap = abs((r.get("mileage") or 0) - (target.get("mileage") or 0)) / 12000
        return (same_variant, age_gap + mileage_gap)

    comparables = []
    for r in sorted(candidates, key=closeness)[:max_n]:
        comparables.append({
            "listing_id": r.get("listing_id", ""),
            "variant": r.get("variant", ""),
            "year": r.get("year"),
            "price": r["price"],
            "mileage": r.get("mileage"),
            "location": r.get("location", ""),
            "value_deviation_pct": r.get("value_deviation_pct"),
            "vs_target": r["price"] - target["price"],
            "url": r.get("autotrader_url") or r.get("url") or "",
        })
    return comparables


def negotiation_levers(target, history, rows):
    """Distil the quantified levers a buyer holds over this listing.

    Returns a list of {lever, detail, strength} dicts ordered strongest
    first. Strength is 'strong'/'moderate'/'weak' based on simple
    thresholds; the skill decides how to phrase and deploy them.
    """
    levers = []

    deviation = target.get("value_deviation")
    deviation_pct = target.get("value_deviation_pct")
    if deviation and (target.get("predicted_price") or 0) > 0:
        if deviation > 0:
            strength = "strong" if deviation_pct >= 5 else "moderate"
            levers.append({
                "lever": "overpriced_vs_market",
                "detail": f"Asking £{deviation:,} ({deviation_pct:+.1f}%) above the "
                          f"modelled market price of £{target['predicted_price']:,}",
                "strength": strength,
            })
        else:
            levers.append({
                "lever": "already_good_value",
                "detail": f"Priced £{-deviation:,} ({deviation_pct:+.1f}%) below the "
                          f"modelled market price - limited room, move fast instead",
                "strength": "weak",
            })

    days = target.get("days_on_market")
    if days is None and history:
        days = history["days_observed"]
    if days is not None and days >= 30:
        levers.append({
            "lever": "stale_listing",
            "detail": f"On sale for {days} days - holding stock costs the dealer money",
            "strength": "strong" if days >= 60 else "moderate",
        })

    if history and history["total_change"] < 0:
        levers.append({
            "lever": "already_reduced",
            "detail": f"Price already cut by £{-history['total_change']:,} since "
                      f"{history['first_seen']} - the dealer is motivated",
            "strength": "moderate",
        })

    cheaper_similar = [
        r for r in rows
        if not r.get("is_brand_new_stock")
        and r.get("variant") == target.get("variant")
        and r.get("listing_id") != target.get("listing_id")
        and (r.get("price") or 0) < (target.get("price") or 0)
    ]
    if cheaper_similar:
        cheapest = min(cheaper_similar, key=lambda r: r["price"])
        levers.append({
            "lever": "cheaper_alternatives",
            "detail": f"{len(cheaper_similar)} cheaper {target.get('variant')} listing(s) "
                      f"on the market, from £{cheapest['price']:,}",
            "strength": "strong" if len(cheaper_similar) >= 3 else "moderate",
        })

    same_variant_supply = sum(
        1 for r in rows
        if not r.get("is_brand_new_stock") and r.get("variant") == target.get("variant")
    )
    if same_variant_supply >= 5:
        levers.append({
            "lever": "plentiful_supply",
            "detail": f"{same_variant_supply} {target.get('variant')} listings currently "
                      f"for sale - the buyer can walk away",
            "strength": "moderate",
        })

    order = {"strong": 0, "moderate": 1, "weak": 2}
    levers.sort(key=lambda l: order[l["strength"]])
    return levers


def suggest_offer_anchors(target, levers):
    """Numeric anchors for the negotiation: opening offer, target, walk-away.

    Anchored on the modelled market price when the listing is overpriced,
    or on modest discounts from asking when it is already fair. These are
    starting points for the skill to present, not commandments.
    """
    price = target.get("price") or 0
    predicted = target.get("predicted_price") or 0
    overpriced = predicted > 0 and price > predicted

    strong = sum(1 for l in levers if l["strength"] == "strong")
    if overpriced:
        target_price = predicted
        opening = round(predicted * (0.96 if strong >= 2 else 0.98))
        walk_away = round(predicted * 1.03)
    else:
        discount = 0.05 if strong >= 2 else 0.03
        opening = round(price * (1 - discount))
        target_price = round(price * (1 - discount / 2))
        walk_away = price
    return {
        "opening_offer": min(opening, price),
        "target_price": min(round(target_price), price),
        "walk_away": min(walk_away, price),
        "asking_price": price,
        "basis": "modelled market price" if overpriced else "discount from asking",
    }
