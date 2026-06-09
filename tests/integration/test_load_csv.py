"""Unit tests for build_dashboard.load_csv.

In-process tests covering the fatal branches (missing file, missing
columns), the tolerant row-skipping path (bad price/mileage/year cells are
skipped with a reason rather than aborting the build), and boolean
coercion.
"""

import pytest

from build_dashboard import load_csv


_SPEC_OPTIONS = [
    {"key": "has_sunroof", "label": "Sunroof", "weight": 1},
    {"key": "has_audio", "label": "Audio", "weight": 2},
]


class TestLoadCsvFatalBranches:
    """Test Load Csv Fatal Branches test cases."""
    def test_missing_file_raises_systemexit(self, tmp_path):
        """Missing file raises systemexit."""
        with pytest.raises(SystemExit) as exc_info:
            load_csv(str(tmp_path / "nope.csv"), _SPEC_OPTIONS)
        assert "not found" in str(exc_info.value).lower()

    def test_empty_file_raises_missing_columns(self, tmp_path):
        """A truly empty file has no fieldnames - reports missing columns."""
        path = tmp_path / "empty.csv"
        path.write_text("")
        with pytest.raises(SystemExit) as exc_info:
            load_csv(str(path), _SPEC_OPTIONS)
        assert "missing required columns" in str(exc_info.value)

    def test_header_only_file_returns_empty_list(self, tmp_path):
        """Header-only (no data rows) is valid - zero listings."""
        path = tmp_path / "header-only.csv"
        path.write_text("variant,price,year,mileage\n")
        rows, skipped = load_csv(str(path), _SPEC_OPTIONS)
        assert rows == []
        assert skipped == []

    def test_missing_required_column_raises_systemexit(self, tmp_path):
        """Missing required column raises systemexit."""
        path = tmp_path / "bad.csv"
        path.write_text("variant,year,mileage\nBase,2023,15000\n")
        with pytest.raises(SystemExit) as exc_info:
            load_csv(str(path), _SPEC_OPTIONS)
        assert "price" in str(exc_info.value)


class TestLoadCsvTolerantRows:
    """Bad individual rows are skipped with a reason, not fatal."""

    def test_non_numeric_price_skips_row_with_reason(self, tmp_path):
        """Non numeric price skips row with reason."""
        path = tmp_path / "bad-row.csv"
        path.write_text(
            "variant,price,year,mileage\n"
            "Base,35000,2023,15000\n"
            "Sport,TBC,2024,10000\n"
        )
        rows, skipped = load_csv(str(path), _SPEC_OPTIONS)
        assert len(rows) == 1
        assert rows[0]["variant"] == "Base"
        assert len(skipped) == 1
        assert "row 2" in skipped[0]
        assert "TBC" in skipped[0]

    def test_comma_formatted_price_and_mileage_parse(self, tmp_path):
        """Scraped values like "12,995" must not cost the user the row."""
        path = tmp_path / "commas.csv"
        path.write_text(
            'variant,price,year,mileage\n'
            'Base,"42,995",2023,"12,400"\n'
        )
        rows, skipped = load_csv(str(path), _SPEC_OPTIONS)
        assert skipped == []
        assert rows[0]["price"] == 42995
        assert rows[0]["mileage"] == 12400

    def test_bad_year_skips_row(self, tmp_path):
        """Bad year skips row."""
        path = tmp_path / "bad-year.csv"
        path.write_text(
            "variant,price,year,mileage\n"
            "Base,35000,unknown,15000\n"
            "Sport,42000,2024,10000\n"
        )
        rows, skipped = load_csv(str(path), _SPEC_OPTIONS)
        assert len(rows) == 1
        assert rows[0]["variant"] == "Sport"
        assert "year" in skipped[0]

    def test_non_numeric_options_count_defaults_to_zero(self, tmp_path):
        """options_count is derived/cosmetic - garbage falls back to 0."""
        path = tmp_path / "bad-opts.csv"
        path.write_text(
            "variant,price,year,mileage,options_count\n"
            "Base,35000,2023,15000,abc\n"
        )
        rows, skipped = load_csv(str(path), _SPEC_OPTIONS)
        assert skipped == []
        assert rows[0]["options_count"] == 0


class TestLoadCsvHappyPath:
    """Test Load Csv Happy Path test cases."""
    def test_row_count_and_basic_types(self, tmp_path):
        """Row count and basic types."""
        path = tmp_path / "good.csv"
        path.write_text(
            "variant,price,year,mileage\n"
            "Base,35000,2023,15000\n"
            "Sport,42000,2024,10000\n"
        )
        rows, skipped = load_csv(str(path), _SPEC_OPTIONS)
        assert len(rows) == 2
        assert skipped == []
        assert rows[0]["variant"] == "Base"
        assert rows[0]["price"] == 35000
        assert rows[0]["year"] == 2023
        assert rows[0]["mileage"] == 15000

    def test_spec_booleans_coerced_from_string(self, tmp_path):
        """Spec booleans coerced from string."""
        path = tmp_path / "with-specs.csv"
        path.write_text(
            "variant,price,year,mileage,has_sunroof,has_audio\n"
            "Base,35000,2023,15000,True,False\n"
            "Sport,42000,2024,10000,False,True\n"
        )
        rows, _ = load_csv(str(path), _SPEC_OPTIONS)
        assert rows[0]["has_sunroof"] is True
        assert rows[0]["has_audio"] is False
        assert rows[1]["has_sunroof"] is False
        assert rows[1]["has_audio"] is True

    def test_is_brand_new_stock_exact_match_required(self, tmp_path):
        """Only the literal "True" activates the flag."""
        path = tmp_path / "new-stock.csv"
        path.write_text(
            "variant,price,year,mileage,is_brand_new_stock\n"
            "Base,35000,2023,15000,True\n"
            "Sport,42000,2024,10000,False\n"
            "GT,50000,2024,5000,true\n"  # lowercase - not coerced
        )
        rows, _ = load_csv(str(path), _SPEC_OPTIONS)
        assert rows[0]["is_brand_new_stock"] is True
        assert rows[1]["is_brand_new_stock"] is False
        assert rows[2]["is_brand_new_stock"] is False

    def test_empty_optional_fields_default_safely(self, tmp_path):
        """Empty optional fields default safely."""
        path = tmp_path / "sparse.csv"
        path.write_text(
            "variant,price,year,mileage,new_price,depreciation_pa\n"
            "Base,35000,2023,15000,,\n"
        )
        rows, _ = load_csv(str(path), _SPEC_OPTIONS)
        assert rows[0]["new_price"] == 0
        assert rows[0]["depreciation_pa"] == 0
        assert rows[0]["retained_pct"] is None  # unknown new_price -> None
