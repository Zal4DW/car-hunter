"""Unit tests for dashboard_lib.js_safe."""

import json
from datetime import date

from dashboard_lib import js_safe


class TestJsSafe:
    """Js safe test cases."""
    def test_serialises_basic_types(self):
        """Serialises basic types."""
        result = js_safe({"a": 1, "b": "two", "c": [3, 4]})
        assert json.loads(result) == {"a": 1, "b": "two", "c": [3, 4]}

    def test_handles_none_values(self):
        """Handles none values."""
        result = js_safe({"missing": None})
        assert json.loads(result) == {"missing": None}

    def test_coerces_dates_to_strings(self):
        """Coerces dates to strings."""
        result = js_safe({"reg_date": date(2024, 6, 15)})
        assert json.loads(result) == {"reg_date": "2024-06-15"}

    def test_serialises_empty_collections(self):
        """Serialises empty collections."""
        assert json.loads(js_safe([])) == []
        assert json.loads(js_safe({})) == {}
