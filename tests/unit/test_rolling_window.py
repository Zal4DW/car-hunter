"""Unit tests for dashboard_lib.rolling_window."""

from datetime import date

from dashboard_lib import rolling_window


def snap(d, ids, median=0):
    """Snap."""
    return {"date": d, "ids": set(ids), "median_price": median}


class TestRollingWindow:
    """Rolling window test cases."""
    def test_returns_one_entry_per_day(self):
        """Returns one entry per day."""
        today = date(2026, 4, 10)
        series = rolling_window([], today, days=7)
        assert len(series) == 7
        assert series[0]["date"] == "2026-04-04"
        assert series[-1]["date"] == "2026-04-10"

    def test_gap_filling_carries_previous_state(self):
        """Gap filling carries previous state."""
        today = date(2026, 4, 10)
        snaps = [
            snap(date(2026, 4, 8), ["a", "b", "c"], median=30000),
        ]
        series = rolling_window(snaps, today, days=5)
        assert series[0]["active"] == 0
        assert series[2]["date"] == "2026-04-08"
        assert series[2]["active"] == 3
        assert series[3]["active"] == 3
        assert series[3]["new"] == 0
        assert series[4]["active"] == 3
        assert series[4]["median"] == 30000

    def test_new_and_removed_computed_against_previous_snapshot(self):
        """New and removed computed against previous snapshot."""
        today = date(2026, 4, 10)
        snaps = [
            snap(date(2026, 4, 8), ["a", "b"], median=100),
            snap(date(2026, 4, 10), ["b", "c"], median=120),
        ]
        series = rolling_window(snaps, today, days=3)
        last = series[-1]
        assert last["date"] == "2026-04-10"
        assert last["active"] == 2
        assert last["new"] == 1
        assert last["removed"] == 1
        assert last["median"] == 120

    def test_snapshots_older_than_window_seed_prior_state(self):
        """Snapshots older than window seed prior state."""
        today = date(2026, 4, 10)
        snaps = [
            snap(date(2026, 3, 1), ["a", "b", "c"], median=50),
            snap(date(2026, 4, 10), ["a", "b", "c", "d"], median=60),
        ]
        series = rolling_window(snaps, today, days=7)
        last = series[-1]
        assert last["new"] == 1
        assert last["removed"] == 0
        assert last["active"] == 4
