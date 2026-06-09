"""Unit tests for compare_lib - the budget-anchored cross-car comparison.

Pins the "what can I get for £X" maths: budget slicing, per-car summaries
(newest/lowest-mileage/medians/best value), the empty-budget message, and
the cross-car headline picks.
"""

from compare_lib import budget_slice, comparison_summary, summarise_car


def _row(price, year=2023, mileage=20000, variant="Base", age=2.0,
         predicted=None, dev_pct=None, retained=None, brand_new=False):
    """Row."""
    return {
        "listing_id": f"id-{price}",
        "price": price,
        "year": year,
        "mileage": mileage,
        "variant": variant,
        "age_years": age,
        "location": "Testville",
        "predicted_price": predicted if predicted is not None else price,
        "value_deviation_pct": dev_pct if dev_pct is not None else 0.0,
        "retained_pct": retained,
        "is_brand_new_stock": brand_new,
    }


class TestBudgetSlice:
    """Test Budget Slice test cases."""
    def test_filters_over_budget_and_brand_new(self):
        """Filters over budget and brand new."""
        rows = [
            _row(35000),
            _row(45000),
            _row(30000, brand_new=True),
        ]
        sliced = budget_slice(rows, 40000)
        assert [r["price"] for r in sliced] == [35000]

    def test_none_budget_keeps_all_used(self):
        """None budget keeps all used."""
        rows = [_row(35000), _row(95000), _row(30000, brand_new=True)]
        assert len(budget_slice(rows, None)) == 2


class TestSummariseCar:
    """Test Summarise Car test cases."""
    def test_empty_budget_reports_entry_point(self):
        """Empty budget reports entry point."""
        rows = [_row(52000), _row(55000)]
        s = summarise_car("Acme Bolt", rows, 40000)
        assert s["under_budget"] == 0
        assert "52,000" in s["message"]
        assert s["cheapest_price"] == 52000

    def test_what_the_budget_buys(self):
        """What the budget buys."""
        rows = [
            _row(38000, year=2024, mileage=8000, dev_pct=2.0, retained=80),
            _row(35000, year=2022, mileage=30000, dev_pct=-6.5, retained=70),
            _row(33000, year=2021, mileage=42000, dev_pct=1.0, retained=65),
            _row(45000, year=2025, mileage=2000),  # over budget
        ]
        s = summarise_car("Acme Bolt", rows, 40000)
        assert s["under_budget"] == 3
        assert s["newest_year"] == 2024
        assert s["lowest_mileage"] == 8000
        assert s["median_price"] == 35000
        assert s["median_retained_pct"] == 70
        assert s["best_value"]["price"] == 35000
        assert s["best_value"]["value_deviation_pct"] == -6.5
        assert s["newest"]["year"] == 2024
        assert s["lowest_mileage_pick"]["mileage"] == 8000

    def test_unscored_rows_excluded_from_best_value(self):
        """Rows whose regression prediction is unusable cannot be 'best value'."""
        rows = [
            _row(30000, predicted=0, dev_pct=-99.0),
            _row(36000, dev_pct=-3.0),
        ]
        s = summarise_car("Acme Bolt", rows, 40000)
        assert s["best_value"]["price"] == 36000


class TestComparisonSummary:
    """Test Comparison Summary test cases."""
    def test_headline_picks_across_cars(self):
        """Headline picks across cars."""
        car_a = summarise_car("Car A", [_row(38000, year=2024, retained=62)], 40000)
        car_b = summarise_car("Car B", [_row(39000, year=2022, retained=78)], 40000)
        result = comparison_summary([car_a, car_b], 40000)
        assert result["newest_at_budget"]["display_name"] == "Car A"
        assert result["best_value_retention"]["display_name"] == "Car B"

    def test_no_stock_anywhere_yields_no_headlines(self):
        """No stock anywhere yields no headlines."""
        car_a = summarise_car("Car A", [_row(52000)], 40000)
        result = comparison_summary([car_a], 40000)
        assert "newest_at_budget" not in result
        assert result["cars"][0]["under_budget"] == 0
