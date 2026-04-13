"""Unit tests for build_dashboard.load_listing_state.

Six SystemExit branches and the happy path, run in-process to replace
subprocess-level coverage.
"""

import json

import pytest

from build_dashboard import load_listing_state


def _write(tmp_path, payload):
    path = tmp_path / "state.json"
    path.write_text(json.dumps(payload))
    return str(path)


class TestLoadListingStateResolution:
    """Path resolution rules."""

    def test_no_explicit_path_and_has_listing_ids_returns_empty(self, tmp_path):
        """When the CSV has listing_ids, the legacy sidecar is skipped."""
        # Auto-detect path would exist but must be ignored.
        (tmp_path / "acme-listing-state.json").write_text('{"listing_ids": {}, "price_changes": {}}')
        ids, prices = load_listing_state(
            explicit_path=None, csv_dir=str(tmp_path),
            profile_name="acme", has_listing_ids=True,
        )
        assert ids == {}
        assert prices == {}

    def test_no_explicit_path_and_no_auto_file_returns_empty(self, tmp_path):
        ids, prices = load_listing_state(
            explicit_path=None, csv_dir=str(tmp_path),
            profile_name="acme", has_listing_ids=False,
        )
        assert ids == {}
        assert prices == {}

    def test_explicit_path_overrides_auto_detection(self, tmp_path):
        explicit = _write(tmp_path, {
            "listing_ids": {"40000_Bristol": "202601010000123"},
            "price_changes": {"40000_Bristol": -500},
        })
        ids, prices = load_listing_state(
            explicit_path=explicit, csv_dir=str(tmp_path),
            profile_name="acme", has_listing_ids=True,
        )
        assert ids == {"40000_Bristol": "202601010000123"}
        assert prices == {"40000_Bristol": -500}

    def test_auto_detected_path_when_no_listing_ids(self, tmp_path):
        (tmp_path / "acme-listing-state.json").write_text(json.dumps({
            "listing_ids": {"35000_Leeds": "202602020000456"},
            "price_changes": {},
        }))
        ids, prices = load_listing_state(
            explicit_path=None, csv_dir=str(tmp_path),
            profile_name="acme", has_listing_ids=False,
        )
        assert "35000_Leeds" in ids


class TestLoadListingStatePathErrors:
    def test_missing_explicit_file_raises_systemexit(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            load_listing_state(
                str(tmp_path / "nope.json"), str(tmp_path), "acme", False,
            )
        msg = str(exc_info.value)
        assert "not found" in msg.lower() or "no such file" in msg.lower()


class TestLoadListingStateValidation:
    """Every SystemExit branch for malformed inputs."""

    def test_invalid_json_raises_systemexit(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{not json")
        with pytest.raises(SystemExit) as exc_info:
            load_listing_state(str(path), str(tmp_path), "acme", False)
        assert "not valid JSON" in str(exc_info.value)

    def test_non_dict_root_raises_systemexit(self, tmp_path):
        path = _write(tmp_path, ["list", "not", "dict"])
        with pytest.raises(SystemExit) as exc_info:
            load_listing_state(path, str(tmp_path), "acme", False)
        assert "must contain a JSON object" in str(exc_info.value)

    def test_non_dict_listing_ids_raises_systemexit(self, tmp_path):
        path = _write(tmp_path, {"listing_ids": "not a dict", "price_changes": {}})
        with pytest.raises(SystemExit) as exc_info:
            load_listing_state(path, str(tmp_path), "acme", False)
        assert "listing_ids" in str(exc_info.value)
        assert "must be an object" in str(exc_info.value)

    def test_non_dict_price_changes_raises_systemexit(self, tmp_path):
        path = _write(tmp_path, {"listing_ids": {}, "price_changes": [1, 2, 3]})
        with pytest.raises(SystemExit) as exc_info:
            load_listing_state(path, str(tmp_path), "acme", False)
        assert "price_changes" in str(exc_info.value)
        assert "must be an object" in str(exc_info.value)

    def test_non_string_listing_id_value_raises_systemexit(self, tmp_path):
        path = _write(tmp_path, {
            "listing_ids": {"40000_Bristol": 12345},  # int not str
            "price_changes": {},
        })
        with pytest.raises(SystemExit) as exc_info:
            load_listing_state(path, str(tmp_path), "acme", False)
        assert "listing_ids" in str(exc_info.value)

    def test_non_numeric_price_change_value_raises_systemexit(self, tmp_path):
        path = _write(tmp_path, {
            "listing_ids": {},
            "price_changes": {"40000_Bristol": "not a number"},
        })
        with pytest.raises(SystemExit) as exc_info:
            load_listing_state(path, str(tmp_path), "acme", False)
        assert "price_changes" in str(exc_info.value)
