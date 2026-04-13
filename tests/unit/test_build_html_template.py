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
        disappear from get_identifiers() while the builder still passes the
        kwarg. This test catches that.
        """
        text = _TEMPLATE_PATH.read_text()
        template = string.Template(text)
        template_ids = set(template.get_identifiers())

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
