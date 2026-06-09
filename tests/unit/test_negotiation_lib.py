"""Unit tests for negotiation_lib - the evidence layer behind the
negotiation coach.

Pins the lever thresholds, the price-history timeline, comparable
selection order, and the offer anchors so the coaching skill always
receives sound numbers.
"""

from datetime import date

from negotiation_lib import (
    find_comparables,
    negotiation_levers,
    price_history,
    suggest_offer_anchors,
)


def _row(listing_id, price, variant="Bolt Sport", year=2024, mileage=12000,
         age=1.5, predicted=None, brand_new=False):
    predicted = price if predicted is None else predicted
    deviation = price - predicted
    return {
        "listing_id": listing_id,
        "price": price,
        "variant": variant,
        "year": year,
        "mileage": mileage,
        "age_years": age,
        "location": "Testville",
        "predicted_price": predicted,
        "value_deviation": deviation,
        "value_deviation_pct": round(deviation / predicted * 100, 1) if predicted else 0,
        "is_brand_new_stock": brand_new,
    }


def _snap(d, rows):
    return {"date": d, "rows": rows}


class TestPriceHistory:
    def test_timeline_records_only_changes(self):
        snaps = [
            _snap(date(2026, 3, 1), [{"listing_id": "X", "price": "45000"}]),
            _snap(date(2026, 3, 15), [{"listing_id": "X", "price": "45000"}]),
            _snap(date(2026, 4, 1), [{"listing_id": "X", "price": "43,500"}]),
        ]
        h = price_history(snaps, "X")
        assert h["first_seen"] == "2026-03-01"
        assert h["days_observed"] == 31
        assert h["prices"] == [
            {"date": "2026-03-01", "price": 45000},
            {"date": "2026-04-01", "price": 43500},
        ]
        assert h["total_change"] == -1500

    def test_unknown_listing_returns_none(self):
        snaps = [_snap(date(2026, 3, 1), [{"listing_id": "Y", "price": "1"}])]
        assert price_history(snaps, "X") is None
        assert price_history(snaps, "") is None


class TestFindComparables:
    def test_same_variant_and_proximity_win(self):
        target = _row("T", 42000, mileage=12000, age=1.5)
        rows = [
            target,
            _row("close", 41000, mileage=13000, age=1.4),
            _row("far", 30000, mileage=60000, age=4.0),
            _row("other-variant", 41500, variant="Bolt Base", mileage=12500, age=1.5),
            _row("new-stock", 41000, brand_new=True),
        ]
        comps = find_comparables(rows, target, max_n=3)
        assert [c["listing_id"] for c in comps] == ["close", "far", "other-variant"]
        assert comps[0]["vs_target"] == -1000
        assert all(c["listing_id"] != "T" for c in comps)


class TestNegotiationLevers:
    def test_overpriced_stale_reduced_and_supply(self):
        target = _row("T", 44000, predicted=40000)
        target["days_on_market"] = 70
        rows = [target] + [_row(f"c{i}", 39000 + i) for i in range(5)]
        history = {"first_seen": "2026-03-01", "total_change": -1500,
                   "days_observed": 70}
        levers = negotiation_levers(target, history, rows)
        names = [l["lever"] for l in levers]
        assert "overpriced_vs_market" in names
        assert "stale_listing" in names
        assert "already_reduced" in names
        assert "cheaper_alternatives" in names
        assert "plentiful_supply" in names
        # 10% over and 70 days are both strong; strong levers sort first.
        assert levers[0]["strength"] == "strong"
        strengths = [l["strength"] for l in levers]
        assert strengths == sorted(strengths, key={"strong": 0, "moderate": 1, "weak": 2}.get)

    def test_underpriced_car_yields_weak_move_fast_lever(self):
        target = _row("T", 38000, predicted=40000)
        levers = negotiation_levers(target, None, [target])
        assert levers[0]["lever"] == "already_good_value"
        assert levers[0]["strength"] == "weak"

    def test_fresh_fair_listing_has_no_false_levers(self):
        target = _row("T", 40000, predicted=40000)
        target["days_on_market"] = 5
        levers = negotiation_levers(target, None, [target])
        assert levers == []


class TestOfferAnchors:
    def test_overpriced_anchors_on_model_price(self):
        target = _row("T", 44000, predicted=40000)
        levers = [{"lever": "a", "strength": "strong"},
                  {"lever": "b", "strength": "strong"}]
        a = suggest_offer_anchors(target, levers)
        assert a["target_price"] == 40000
        assert a["opening_offer"] == round(40000 * 0.96)
        assert a["walk_away"] == round(40000 * 1.03)
        assert a["basis"] == "modelled market price"

    def test_fair_price_anchors_on_modest_discount(self):
        target = _row("T", 40000, predicted=40500)
        a = suggest_offer_anchors(target, [])
        assert a["opening_offer"] == round(40000 * 0.97)
        assert a["walk_away"] == 40000
        assert a["basis"] == "discount from asking"

    def test_anchors_never_exceed_asking(self):
        """A wildly under-priced car must not produce an offer above asking."""
        target = _row("T", 30000, predicted=40000)
        a = suggest_offer_anchors(target, [])
        assert a["opening_offer"] <= 30000
        assert a["target_price"] <= 30000
        assert a["walk_away"] <= 30000
