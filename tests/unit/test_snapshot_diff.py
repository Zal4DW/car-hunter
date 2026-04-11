"""Unit tests for dashboard_lib.snapshot_diff."""

from dashboard_lib import snapshot_diff


def row(lid, price):
    """Row."""
    return {"listing_id": lid, "price": price}


class TestBasicDiff:
    """Basic diff test cases."""
    def test_disjoint_sets_all_new_and_removed(self):
        """Disjoint sets all new and removed."""
        prev = [row("a", 100), row("b", 200)]
        curr = [row("c", 300), row("d", 400)]
        result = snapshot_diff(prev, curr)
        assert sorted(result["new"]) == ["c", "d"]
        assert sorted(result["removed"]) == ["a", "b"]
        assert result["price_changed"] == []

    def test_identical_sets_no_change(self):
        """Identical sets no change."""
        prev = [row("a", 100), row("b", 200)]
        curr = [row("a", 100), row("b", 200)]
        result = snapshot_diff(prev, curr)
        assert result == {"new": [], "removed": [], "price_changed": []}

    def test_one_removed(self):
        """One removed."""
        prev = [row("a", 100), row("b", 200)]
        curr = [row("a", 100)]
        result = snapshot_diff(prev, curr)
        assert result["removed"] == ["b"]
        assert result["new"] == []

    def test_one_price_changed(self):
        """One price changed."""
        prev = [row("a", 100), row("b", 200)]
        curr = [row("a", 100), row("b", 180)]
        result = snapshot_diff(prev, curr)
        assert result["new"] == []
        assert result["removed"] == []
        assert len(result["price_changed"]) == 1
        ch = result["price_changed"][0]
        assert ch == {"id": "b", "old": 200, "new": 180, "delta": -20}


class TestEdgeCases:
    """Edge cases test cases."""
    def test_rows_without_listing_id_are_skipped(self):
        """Rows without listing id are skipped."""
        prev = [row("", 100), row("a", 200)]
        curr = [row("", 100), row("a", 150)]
        result = snapshot_diff(prev, curr)
        assert result["new"] == []
        assert result["removed"] == []
        assert len(result["price_changed"]) == 1
        assert result["price_changed"][0]["id"] == "a"

    def test_new_id_with_price_change_reports_only_new(self):
        """New id with price change reports only new."""
        prev = []
        curr = [row("z", 500)]
        result = snapshot_diff(prev, curr)
        assert result["new"] == ["z"]
        assert result["price_changed"] == []
