"""Unit tests for build_dashboard.enrich_rows.

Covers the two branches (has_listing_ids / legacy sidecar) and specifically
the lid_encoding-enabled path which is effectively dead in e2e tests because
the acme-bolt fixture ships with listing_id_date_encoding disabled.
"""

from datetime import date

import pytest

from build_dashboard import enrich_rows


def _row(listing_id="", price=40000, location="Testville"):
    return {
        "listing_id": listing_id,
        "price": price,
        "location": location,
    }


_TODAY = date(2026, 4, 13)


class TestEnrichRowsInit:
    """Every row gets the same skeleton fields regardless of branch."""

    def test_all_rows_get_default_composite_and_flags(self):
        rows = [_row(price=35000, location="Bristol"), _row(price=42000, location="Leeds")]
        enrich_rows(
            rows, snapshots=[], watchlist={"listings": {}},
            listing_ids={}, price_changes={},
            lid_encoding={"enabled": False}, today=_TODAY,
            has_listing_ids=False,
        )
        assert rows[0]["composite_key"] == "35000_Bristol"
        assert rows[1]["composite_key"] == "42000_Leeds"
        for r in rows:
            assert r["autotrader_url"] is None
            assert r["days_on_market"] is None
            assert r["price_change"] == 0
            assert r["watched"] is False
            assert r["watch_note"] == ""


class TestEnrichRowsLidEncodedBranch:
    """Exercises the hot path that ships dead in the existing e2e suite."""

    def test_encoded_digit_listing_id_becomes_autotrader_url(self):
        """lid_encoding.enabled + digit-only listing_id builds the URL."""
        # 20260401... = April 1, 2026 - 12 days before _TODAY
        rows = [_row(listing_id="202604010000123", price=40000)]
        enrich_rows(
            rows, snapshots=[], watchlist={"listings": {}},
            listing_ids={}, price_changes={},
            lid_encoding={"enabled": True}, today=_TODAY,
            has_listing_ids=True,
        )
        assert rows[0]["autotrader_url"] == (
            "https://www.autotrader.co.uk/car-details/202604010000123"
        )
        assert rows[0]["days_on_market"] == 12

    def test_non_digit_listing_id_does_not_build_url(self):
        """Opaque (hashed) listing IDs skip the URL rewrite cleanly."""
        rows = [_row(listing_id="cinch:abc123def456", price=30000)]
        enrich_rows(
            rows, snapshots=[], watchlist={"listings": {}},
            listing_ids={}, price_changes={},
            lid_encoding={"enabled": True}, today=_TODAY,
            has_listing_ids=True,
        )
        assert rows[0]["autotrader_url"] is None
        assert rows[0]["days_on_market"] is None

    def test_empty_listing_id_row_is_left_untouched(self):
        rows = [_row(listing_id="", price=25000)]
        enrich_rows(
            rows, snapshots=[], watchlist={"listings": {}},
            listing_ids={}, price_changes={},
            lid_encoding={"enabled": True}, today=_TODAY,
            has_listing_ids=True,
        )
        assert rows[0]["autotrader_url"] is None
        assert rows[0]["days_on_market"] is None


class TestEnrichRowsWatchlist:
    """Watchlist join in the listing_id path."""

    def test_matching_listing_id_gets_watched_flag(self):
        rows = [_row(listing_id="202604010000123", price=40000)]
        watchlist = {"listings": {"202604010000123": {"note": "Check this"}}}
        enrich_rows(
            rows, snapshots=[], watchlist=watchlist,
            listing_ids={}, price_changes={},
            lid_encoding={"enabled": False}, today=_TODAY,
            has_listing_ids=True,
        )
        assert rows[0]["watched"] is True
        assert rows[0]["watch_note"] == "Check this"

    def test_non_dict_watchlist_entry_yields_empty_note(self):
        """String-valued watchlist entries are tolerated (defensive coding)."""
        rows = [_row(listing_id="202604010000123")]
        watchlist = {"listings": {"202604010000123": "legacy format"}}
        enrich_rows(
            rows, snapshots=[], watchlist=watchlist,
            listing_ids={}, price_changes={},
            lid_encoding={"enabled": False}, today=_TODAY,
            has_listing_ids=True,
        )
        assert rows[0]["watched"] is True
        assert rows[0]["watch_note"] == ""


class TestEnrichRowsLegacySidecar:
    """Legacy path: has_listing_ids=False, uses composite-key sidecar."""

    def test_sidecar_listing_id_populates_url_when_encoded(self):
        rows = [_row(price=40000, location="Bristol")]
        listing_ids = {"40000_Bristol": "202604010000123"}
        enrich_rows(
            rows, snapshots=[], watchlist={"listings": {}},
            listing_ids=listing_ids, price_changes={},
            lid_encoding={"enabled": True}, today=_TODAY,
            has_listing_ids=False,
        )
        assert rows[0]["autotrader_url"] == (
            "https://www.autotrader.co.uk/car-details/202604010000123"
        )
        assert rows[0]["days_on_market"] == 12

    def test_sidecar_price_changes_populate(self):
        rows = [_row(price=40000, location="Bristol")]
        enrich_rows(
            rows, snapshots=[], watchlist={"listings": {}},
            listing_ids={}, price_changes={"40000_Bristol": -500},
            lid_encoding={"enabled": False}, today=_TODAY,
            has_listing_ids=False,
        )
        assert rows[0]["price_change"] == -500


class TestEnrichRowsSnapshotDiff:
    """Snapshot diff populates pulse and per-row price_change."""

    def test_prior_snapshot_diff_populates_pulse(self):
        prev_date = date(2026, 4, 10)
        rows = [_row(listing_id="lid-a", price=40000)]
        snapshots = [
            {
                "date": prev_date,
                "rows": [
                    {"listing_id": "lid-a", "price": "42000"},
                    {"listing_id": "lid-removed", "price": "30000"},
                ],
                "ids": {"lid-a", "lid-removed"},
                "median_price": 36000,
            },
            {
                "date": _TODAY,
                "rows": [{"listing_id": "lid-a", "price": "40000"}],
                "ids": {"lid-a"},
                "median_price": 40000,
            },
        ]
        pulse = enrich_rows(
            rows, snapshots=snapshots, watchlist={"listings": {}},
            listing_ids={}, price_changes={},
            lid_encoding={"enabled": False}, today=_TODAY,
            has_listing_ids=True,
        )
        assert pulse["new"] == 0
        assert pulse["removed"] == 1
        assert pulse["price_drops"] == 1
        assert pulse["previous_date"] == "2026-04-10"
        assert rows[0]["price_change"] == -2000

    def test_no_prior_snapshot_returns_default_pulse(self):
        rows = [_row(listing_id="lid-a")]
        pulse = enrich_rows(
            rows, snapshots=[], watchlist={"listings": {}},
            listing_ids={}, price_changes={},
            lid_encoding={"enabled": False}, today=_TODAY,
            has_listing_ids=True,
        )
        assert pulse == {"new": 0, "removed": 0, "price_drops": 0, "previous_date": None}
