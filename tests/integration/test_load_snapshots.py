"""Unit tests for build_dashboard.load_snapshots.

Covers the median calculation path (odd, even, empty) and the warning
branches for non-parseable prices and filename edge cases.
"""

from build_dashboard import load_snapshots


def _write_snapshot(tmp_path, date_tag, rows):
    path = tmp_path / f"acme-all-listings-{date_tag}.csv"
    header = "listing_id,price\n"
    body = "\n".join(f"{lid},{price}" for lid, price in rows)
    path.write_text(header + body + "\n")
    return path


class TestLoadSnapshotsMedian:
    def test_odd_length_picks_middle(self, tmp_path):
        _write_snapshot(tmp_path, "2026-04-01", [
            ("a", 10000), ("b", 20000), ("c", 30000),
        ])
        snapshots = load_snapshots(str(tmp_path), "acme")
        assert len(snapshots) == 1
        assert snapshots[0]["median_price"] == 20000

    def test_even_length_averages_two_middles(self, tmp_path):
        # Bug: previously returned prices[2] == 30000 for even length.
        # Correct median of [10, 20, 30, 40] is 25.
        _write_snapshot(tmp_path, "2026-04-02", [
            ("a", 10000), ("b", 20000), ("c", 30000), ("d", 40000),
        ])
        snapshots = load_snapshots(str(tmp_path), "acme")
        assert snapshots[0]["median_price"] == 25000

    def test_even_length_with_non_uniform_middles(self, tmp_path):
        _write_snapshot(tmp_path, "2026-04-03", [
            ("a", 15000), ("b", 22000), ("c", 28000), ("d", 40000),
        ])
        snapshots = load_snapshots(str(tmp_path), "acme")
        assert snapshots[0]["median_price"] == 25000

    def test_empty_snapshot_returns_zero(self, tmp_path):
        path = tmp_path / "acme-all-listings-2026-04-04.csv"
        path.write_text("listing_id,price\n")
        snapshots = load_snapshots(str(tmp_path), "acme")
        assert snapshots[0]["median_price"] == 0

    def test_unparseable_prices_excluded_and_warned(self, tmp_path, capsys):
        _write_snapshot(tmp_path, "2026-04-05", [
            ("a", 10000), ("b", "junk"), ("c", 20000),
        ])
        snapshots = load_snapshots(str(tmp_path), "acme")
        assert snapshots[0]["median_price"] == 15000
        out = capsys.readouterr().out
        assert "unparseable" in out
