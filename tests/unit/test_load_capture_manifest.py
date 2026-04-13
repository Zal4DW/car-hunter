"""Unit tests for build_dashboard.load_capture_manifest.

Exercises every SystemExit branch and every badge status classification
(ok/partial/failed/unknown) in-process instead of via subprocess.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "car-hunter" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_dashboard import load_capture_manifest  # noqa: E402


_TODAY = date(2026, 4, 13)


def _write_manifest(tmp_path, profile_name, today, payload):
    """Helper: write a capture manifest JSON to the conventional path."""
    path = tmp_path / f"{profile_name}-capture-{today.isoformat()}.json"
    path.write_text(json.dumps(payload))
    return path


class TestLoadCaptureManifestHappyPaths:
    """Badge classification matches source status aggregation."""

    def test_no_file_returns_grey_unknown_badge(self, tmp_path):
        manifest, badge = load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert manifest is None
        assert badge["status"] == "unknown"
        assert badge["colour"] == "grey"

    def test_all_ok_sources_produce_green_badge(self, tmp_path):
        _write_manifest(tmp_path, "acme", _TODAY, {
            "sources": [
                {"name": "autotrader", "status": "ok"},
                {"name": "cinch", "status": "ok"},
            ]
        })
        _, badge = load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert badge["status"] == "ok"
        assert badge["colour"] == "green"
        assert "sources" in badge

    def test_one_partial_source_produces_amber_badge(self, tmp_path):
        _write_manifest(tmp_path, "acme", _TODAY, {
            "sources": [
                {"name": "autotrader", "status": "ok"},
                {"name": "cinch", "status": "partial"},
            ]
        })
        _, badge = load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert badge["status"] == "partial"
        assert badge["colour"] == "amber"

    def test_any_failed_source_produces_red_badge(self, tmp_path):
        _write_manifest(tmp_path, "acme", _TODAY, {
            "sources": [
                {"name": "autotrader", "status": "ok"},
                {"name": "cinch", "status": "failed"},
            ]
        })
        _, badge = load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert badge["status"] == "failed"
        assert badge["colour"] == "red"

    def test_failed_wins_over_partial(self, tmp_path):
        """Failed is the most severe status and must take precedence."""
        _write_manifest(tmp_path, "acme", _TODAY, {
            "sources": [
                {"name": "a", "status": "partial"},
                {"name": "b", "status": "failed"},
            ]
        })
        _, badge = load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert badge["status"] == "failed"


class TestLoadCaptureManifestValidation:
    """Every SystemExit branch."""

    def test_malformed_json_raises_systemexit(self, tmp_path):
        path = tmp_path / "acme-capture-2026-04-13.json"
        path.write_text("{not json")
        with pytest.raises(SystemExit) as exc_info:
            load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert "not valid JSON" in str(exc_info.value)

    def test_non_dict_root_raises_systemexit(self, tmp_path):
        _write_manifest(tmp_path, "acme", _TODAY, ["not", "a", "dict"])
        with pytest.raises(SystemExit) as exc_info:
            load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert "must contain a JSON object" in str(exc_info.value)

    def test_non_list_sources_raises_systemexit(self, tmp_path):
        _write_manifest(tmp_path, "acme", _TODAY, {"sources": "not a list"})
        with pytest.raises(SystemExit) as exc_info:
            load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert "'sources' must be a list" in str(exc_info.value)

    def test_non_dict_source_entry_raises_systemexit(self, tmp_path):
        _write_manifest(tmp_path, "acme", _TODAY, {
            "sources": [{"name": "ok"}, "not a dict"]
        })
        with pytest.raises(SystemExit) as exc_info:
            load_capture_manifest(str(tmp_path), "acme", _TODAY)
        assert "sources[1]" in str(exc_info.value)
