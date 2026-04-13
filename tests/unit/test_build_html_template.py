"""Contract test for the dashboard HTML template.

The template is a string.Template with $placeholder substitutions. A typo
like $$foo (literal dollar escape) or an unused kwarg both produce silently
broken HTML. This test asserts template identifiers and builder kwargs are
in perfect agreement, so any drift between them fails the suite.
"""

import string
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "car-hunter" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_dashboard import build_html  # noqa: E402

_TEMPLATE_PATH = _SCRIPTS / "templates" / "dashboard.html"

# The full set of kwargs the builder passes to string.Template.substitute().
# Keep in sync with build_dashboard.py:main() and build_html().
_EXPECTED_PLACEHOLDERS = {
    "DISPLAY_NAME",
    "bg",
    "card_bg",
    "card_border",
    "text_colour",
    "text_muted",
    "today_str",
    "variant_options_html",
    "gen_options_html",
    "mileage_options_html",
    "budget_options_html",
    "criteria_text",
    "preferred_text",
    "gen_filter_js",
    "r_squared_formatted",
    "capture_colour",
    "capture_label",
    "table_count",
    "regression_warning_html",
    "all_data_json",
    "dep_curves_json",
    "spec_premiums_json",
    "pm_trend_json",
    "variant_colours_json",
    "highlight_specs_json",
    "watchlist_json",
    "time_series_json",
    "snapshot_pulse_json",
    "capture_json",
    "reg_count",
}


class TestTemplateIdentifiers:
    """The template file's placeholders must match the builder's kwargs exactly."""

    def test_template_identifiers_match_builder_kwargs(self):
        """Every $name in the template must have a matching builder kwarg, and
        every builder kwarg must be referenced at least once in the template.

        A typo like $$reg_count (literal-dollar escape) makes the placeholder
        disappear from the parsed identifier set while the builder still
        passes the kwarg. This test catches that.

        Walks `Template.pattern` directly instead of calling get_identifiers()
        so the test works on Python 3.10 (the method was only added in 3.11).
        """
        text = _TEMPLATE_PATH.read_text()
        template = string.Template(text)
        template_ids = set()
        invalid = []
        for m in template.pattern.finditer(template.template):
            if m.group("named"):
                template_ids.add(m.group("named"))
            elif m.group("braced"):
                template_ids.add(m.group("braced"))
            elif m.group("invalid"):
                invalid.append(m.group(0))
        assert not invalid, f"Invalid template placeholders found: {invalid}"

        missing_from_template = _EXPECTED_PLACEHOLDERS - template_ids
        unused_in_builder = template_ids - _EXPECTED_PLACEHOLDERS

        assert not missing_from_template, (
            f"Builder passes these kwargs but template never uses them "
            f"(check for $$ escapes or typos): {sorted(missing_from_template)}"
        )
        assert not unused_in_builder, (
            f"Template uses placeholders the builder does not supply: "
            f"{sorted(unused_in_builder)}"
        )

    def test_no_unresolved_placeholders_in_rendered_output(self):
        """End-to-end: render the template with stub values and assert the
        output contains no literal $name substrings outside known-safe places.

        Serves as a smoke test for the full string.Template pipeline - a
        broken escape leaves $name visible in the final HTML.
        """
        import re

        text = _TEMPLATE_PATH.read_text()
        template = string.Template(text)
        stubs = {name: "STUB" for name in _EXPECTED_PLACEHOLDERS}
        rendered = template.substitute(stubs)

        # After substitution, no $name patterns should remain for keys we know
        # about. Any `$word` in the output is either a JS template literal
        # `${...}` (already escaped to `${...}` pre-substitution) or a bug.
        unresolved = re.findall(r'\$([A-Za-z_][A-Za-z_0-9]*)', rendered)
        for name in unresolved:
            assert name not in _EXPECTED_PLACEHOLDERS, (
                f"Template placeholder ${name} survived substitution - "
                f"likely wrapped in $$ by mistake"
            )


def _minimal_build_html_kwargs():
    """Build the minimum set of valid kwargs to call build_html()."""
    return dict(
        DISPLAY_NAME="Test Car",
        DASHBOARD={"theme": {
            "bg": "#000", "card_bg": "#111", "card_border": "#222",
            "text": "#fff", "text_muted": "#888",
        }, "mileage_filter_options": [20000], "mileage_filter_default": 20000,
           "budget_filter_options": [50000], "budget_filter_default": 50000},
        VARIANTS=[{"name": "Base", "tier": 0, "colour": "#abc"}],
        GENERATIONS=[{"name": "gen1", "label": "Gen 1", "year_from": 2020}],
        SEARCH_FILTERS={"max_price": 100000, "max_mileage": 50000,
                        "max_distance": 200, "postcode": "SW1A 1AA"},
        SPEC_OPTIONS=[],
        VARIANT_COLOURS={"Base": "#abc"},
        highlight_specs=[],
        table_data=[],
        dep_curves={},
        spec_premiums=[],
        pm_trend=[],
        WATCHLIST={"listings": {}},
        TIME_SERIES=[],
        SNAPSHOT_PULSE={"new": 0, "removed": 0, "price_drops": 0, "previous_date": None},
        CAPTURE_BADGE={"status": "unknown", "colour": "grey", "label": "No capture"},
        r_squared=0.0,
        today_str="12 April 2026",
        reg_count=0,
        regression_warning=None,
    )


class TestBuildHtmlErrorHandling:
    """build_html() must surface template I/O and substitution errors clearly."""

    def test_missing_template_file_gives_clear_error(self, tmp_path):
        """Pointing at a non-existent template must raise SystemExit with a
        clear 'reinstall plugin' style message, not a raw FileNotFoundError.
        """
        kwargs = _minimal_build_html_kwargs()
        kwargs["template_path"] = str(tmp_path / "does-not-exist.html")
        with pytest.raises(SystemExit) as exc_info:
            build_html(**kwargs)
        msg = str(exc_info.value)
        assert "template" in msg.lower()
        assert "does-not-exist" in msg

    def test_template_with_unknown_placeholder_gives_clear_error(self, tmp_path):
        """A template that references a placeholder the builder doesn't supply
        must raise SystemExit naming the offending placeholder.
        """
        bad_template = tmp_path / "bad.html"
        bad_template.write_text("<html>$missing_placeholder</html>")
        kwargs = _minimal_build_html_kwargs()
        kwargs["template_path"] = str(bad_template)
        with pytest.raises(SystemExit) as exc_info:
            build_html(**kwargs)
        msg = str(exc_info.value)
        assert "missing_placeholder" in msg or "unknown placeholder" in msg.lower()

    def test_happy_path_renders_without_raising(self):
        """Smoke test: the real template file rendered with valid stubs works."""
        kwargs = _minimal_build_html_kwargs()
        html = build_html(**kwargs)
        assert "<!DOCTYPE html>" in html
        assert "Test Car" in html
