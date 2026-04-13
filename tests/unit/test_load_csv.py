"""Unit tests for build_dashboard.load_csv.

In-process tests covering error branches that the e2e subprocess suite
only reaches slowly: missing column, empty file, non-numeric price,
options_count parse failure, and boolean coercion.
"""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "car-hunter" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_dashboard import load_csv  # noqa: E402


_SPEC_OPTIONS = [
    {"key": "has_sunroof", "label": "Sunroof", "weight": 1},
    {"key": "has_audio", "label": "Audio", "weight": 2},
]


class TestLoadCsvErrorBranches:
    def test_missing_file_raises_systemexit(self, tmp_path):
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
        rows = load_csv(str(path), _SPEC_OPTIONS)
        assert rows == []

    def test_missing_required_column_raises_systemexit(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("variant,year,mileage\nBase,2023,15000\n")
        with pytest.raises(SystemExit) as exc_info:
            load_csv(str(path), _SPEC_OPTIONS)
        assert "price" in str(exc_info.value)

    def test_non_numeric_price_raises_with_row_number(self, tmp_path):
        path = tmp_path / "bad-row.csv"
        path.write_text(
            "variant,price,year,mileage\n"
            "Base,35000,2023,15000\n"
            "Sport,TBC,2024,10000\n"
        )
        with pytest.raises(SystemExit) as exc_info:
            load_csv(str(path), _SPEC_OPTIONS)
        msg = str(exc_info.value)
        assert "row 2" in msg.lower() or "row 2" in msg
        assert "TBC" in msg

    def test_non_numeric_options_count_raises_with_row_number(self, tmp_path):
        path = tmp_path / "bad-opts.csv"
        path.write_text(
            "variant,price,year,mileage,options_count\n"
            "Base,35000,2023,15000,abc\n"
        )
        with pytest.raises(SystemExit) as exc_info:
            load_csv(str(path), _SPEC_OPTIONS)
        assert "options_count" in str(exc_info.value)


class TestLoadCsvHappyPath:
    def test_row_count_and_basic_types(self, tmp_path):
        path = tmp_path / "good.csv"
        path.write_text(
            "variant,price,year,mileage\n"
            "Base,35000,2023,15000\n"
            "Sport,42000,2024,10000\n"
        )
        rows = load_csv(str(path), _SPEC_OPTIONS)
        assert len(rows) == 2
        assert rows[0]["variant"] == "Base"
        assert rows[0]["price"] == 35000
        assert rows[0]["year"] == 2023
        assert rows[0]["mileage"] == 15000

    def test_spec_booleans_coerced_from_string(self, tmp_path):
        path = tmp_path / "with-specs.csv"
        path.write_text(
            "variant,price,year,mileage,has_sunroof,has_audio\n"
            "Base,35000,2023,15000,True,False\n"
            "Sport,42000,2024,10000,False,True\n"
        )
        rows = load_csv(str(path), _SPEC_OPTIONS)
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
        rows = load_csv(str(path), _SPEC_OPTIONS)
        assert rows[0]["is_brand_new_stock"] is True
        assert rows[1]["is_brand_new_stock"] is False
        assert rows[2]["is_brand_new_stock"] is False

    def test_empty_optional_fields_default_safely(self, tmp_path):
        path = tmp_path / "sparse.csv"
        path.write_text(
            "variant,price,year,mileage,new_price,depreciation_pa\n"
            "Base,35000,2023,15000,,\n"
        )
        rows = load_csv(str(path), _SPEC_OPTIONS)
        assert rows[0]["new_price"] == 0
        assert rows[0]["depreciation_pa"] == 0
        assert rows[0]["retained_pct"] is None  # unknown new_price -> None
