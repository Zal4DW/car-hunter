"""Unit tests for ingest_lib - the pure derivation layer behind
ingest_listings.py.

The whole point of the ingest script is that the language model never does
arithmetic, so these tests pin the maths: price/mileage parsing of noisy
scraped text, reg-code resolution, generation detection, depreciation
derivation, standard-spec forcing, and cross-source deduplication.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from ingest_lib import (
    apply_standard_specs,
    csv_columns,
    decimal_year,
    dedup_listings,
    derive_listing,
    detect_generation,
    normalise_specs,
    parse_mileage,
    parse_price,
    reg_to_decimal,
    summarise_sources,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(scope="module")
def profile():
    return json.loads((FIXTURES / "acme-bolt.json").read_text())


_CAPTURE_DATE = date(2026, 4, 10)


class TestParsePrice:
    @pytest.mark.parametrize("raw,expected", [
        (42995, 42995),
        (42995.0, 42995),
        ("42995", 42995),
        ("£42,995", 42995),
        ("42,995 GBP", 42995),
        ("From £39,000", 39000),
        ("POA", None),
        ("", None),
        (None, None),
        (True, None),
    ])
    def test_parse_price(self, raw, expected):
        assert parse_price(raw) == expected

    def test_parse_mileage_text(self):
        assert parse_mileage("12,400 miles") == 12400
        assert parse_mileage("Mileage: 8,000") == 8000


class TestDates:
    def test_decimal_year_midpoints(self):
        assert decimal_year(date(2026, 1, 1)) == 2026.0
        assert 2026.49 < decimal_year(date(2026, 7, 1)) < 2026.51

    def test_reg_lookup_beats_year_fallback(self, profile):
        assert reg_to_decimal("74", profile["reg_date_mapping"]) == 2024.75

    def test_unmapped_reg_falls_back_to_mid_year(self, profile):
        assert reg_to_decimal("99", profile["reg_date_mapping"], year=2023) == 2023.5

    def test_no_reg_no_year_returns_none(self, profile):
        assert reg_to_decimal(None, profile["reg_date_mapping"]) is None


class TestDetectGeneration:
    def test_open_ended_generation_matches_recent_year(self, profile):
        gen = detect_generation(2025, profile["generations"])
        assert gen["name"] == "mk1"

    def test_year_before_first_generation_returns_none(self, profile):
        assert detect_generation(2015, profile["generations"]) is None

    def test_bounded_ranges_pick_correct_generation(self):
        gens = [
            {"name": "mk1", "year_from": 2018, "year_to": 2021},
            {"name": "mk2", "year_from": 2022, "year_to": None},
        ]
        assert detect_generation(2021, gens)["name"] == "mk1"
        assert detect_generation(2022, gens)["name"] == "mk2"


class TestSpecs:
    def test_list_shape_normalises(self, profile):
        flags = normalise_specs(["has_sunroof"], profile["spec_options"])
        assert flags == {"has_sunroof": True, "has_premium_audio": False, "has_heated_seats": False}

    def test_dict_shape_normalises(self, profile):
        flags = normalise_specs({"has_premium_audio": True, "has_sunroof": False},
                                profile["spec_options"])
        assert flags["has_premium_audio"] is True
        assert flags["has_sunroof"] is False

    def test_unknown_keys_ignored(self, profile):
        flags = normalise_specs(["has_flux_capacitor"], profile["spec_options"])
        assert all(v is False for v in flags.values())

    def test_standard_specs_forced_true(self, profile):
        sport = profile["variants"][1]
        flags = normalise_specs([], profile["spec_options"])
        apply_standard_specs(flags, sport)
        assert flags["has_heated_seats"] is True


class TestDeriveListing:
    def _raw(self, **overrides):
        raw = {
            "url": "https://www.autotrader.co.uk/car-details/202602170000123",
            "source": "AutoTrader",
            "variant": "Bolt Sport",
            "price": "£42,995",
            "year": 2024,
            "reg": "74",
            "mileage": "12,400 miles",
            "location": "Leeds",
            "specs": ["has_sunroof"],
            "is_brand_new_stock": False,
        }
        raw.update(overrides)
        return raw

    def test_happy_path_derives_all_fields(self, profile):
        row, warning = derive_listing(self._raw(), profile, _CAPTURE_DATE)
        assert warning is None
        assert row["listing_id"] == "202602170000123"
        assert row["price"] == 42995
        assert row["mileage"] == 12400
        assert row["generation"] == "mk1"
        assert row["new_price"] == 58000
        assert row["reg_date"] == 2024.75
        # 2026-04-10 is ~2026.27; age = ~1.52
        assert 1.4 < row["age_years"] < 1.6
        assert row["depreciation_total"] == 58000 - 42995
        assert row["depreciation_pa"] == round(row["depreciation_total"] / row["age_years"])
        assert row["has_sunroof"] is True
        # Standard on Bolt Sport even though the listing didn't mention it.
        assert row["has_heated_seats"] is True
        assert row["options_count"] == 2

    def test_non_autotrader_url_gets_hash_id(self, profile):
        row, _ = derive_listing(
            self._raw(url="https://www.cinch.co.uk/used-cars/12345", source="Cinch"),
            profile, _CAPTURE_DATE,
        )
        assert row["listing_id"].startswith("Cinch:")

    def test_missing_price_skips_with_reason(self, profile):
        row, reason = derive_listing(self._raw(price="POA"), profile, _CAPTURE_DATE)
        assert row is None
        assert "price" in reason

    def test_unknown_variant_warns_but_keeps_row(self, profile):
        row, warning = derive_listing(self._raw(variant="Bolt GT"), profile, _CAPTURE_DATE)
        assert row is not None
        assert "Bolt GT" in warning
        # Unknown variant has no RRP in the generation map.
        assert row["new_price"] == 0
        assert row["depreciation_pa"] == 0

    def test_year_outside_generations_warns(self, profile):
        row, warning = derive_listing(self._raw(year=2015, reg="15"), profile, _CAPTURE_DATE)
        assert row is not None
        assert "generation" in warning
        assert row["generation"] == ""
        assert row["new_price"] == 0

    def test_young_car_has_no_annualised_depreciation(self, profile):
        """Unmapped reg falls back to mid-year; future date clamps age to 0."""
        row, _ = derive_listing(self._raw(reg="", year=2026), profile, _CAPTURE_DATE)
        assert row["age_years"] == 0.0
        assert row["depreciation_pa"] == 0


class TestDedup:
    def _row(self, listing_id, price=42995, year=2024, mileage=12400, location="Leeds"):
        return {
            "listing_id": listing_id, "price": price, "year": year,
            "mileage": mileage, "location": location,
        }

    def test_same_car_two_sources_keeps_canonical_id(self):
        rows = [
            self._row("Cinch:abc123def456"),
            self._row("202602170000123"),
        ]
        deduped, removed = dedup_listings(rows)
        assert removed == 1
        assert len(deduped) == 1
        assert deduped[0]["listing_id"] == "202602170000123"

    def test_canonical_first_is_kept(self):
        rows = [
            self._row("202602170000123"),
            self._row("Cinch:abc123def456"),
        ]
        deduped, _ = dedup_listings(rows)
        assert deduped[0]["listing_id"] == "202602170000123"

    def test_location_match_is_case_insensitive(self):
        rows = [self._row("a:1", location="Leeds"), self._row("202602170000123", location="LEEDS")]
        deduped, removed = dedup_listings(rows)
        assert removed == 1

    def test_different_cars_not_collapsed(self):
        rows = [self._row("a:1", price=42995), self._row("b:2", price=41000)]
        deduped, removed = dedup_listings(rows)
        assert removed == 0
        assert len(deduped) == 2


class TestCsvColumns:
    def test_column_order_matches_builder_contract(self, profile):
        cols = csv_columns(profile["spec_options"])
        assert cols[0] == "listing_id"
        assert "variant" in cols and "price" in cols and "mileage" in cols
        assert "has_sunroof" in cols and "has_heated_seats" in cols
        assert cols.index("options_count") > cols.index("has_heated_seats")
        assert "url" in cols and "source" in cols


class TestSummariseSources:
    def test_fills_missing_status(self):
        out = summarise_sources([{"name": "AutoTrader"}, "garbage", {"name": "Cinch", "status": "ok"}])
        assert out == [
            {"name": "AutoTrader", "status": "unknown"},
            {"name": "Cinch", "status": "ok"},
        ]

    def test_none_yields_empty(self):
        assert summarise_sources(None) == []
