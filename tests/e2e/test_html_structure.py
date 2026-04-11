"""End-to-end structural tests for the generated dashboard HTML.

Two layers:

1. Stdlib `html.parser.HTMLParser` walk: catches wholesale malformed HTML
   without any third-party dependency. If the builder ever emits something
   that a vanilla HTML parser cannot tokenise, this fails loudly.

2. BeautifulSoup CSS-selector assertions: check that every landmark the
   dashboard depends on is actually present in the output - 5 named
   `<canvas>` elements, 5 filter `<select>` elements, a Chart.js CDN
   `<script>` tag, the profile's display name in the title and `<h1>`,
   the data table tbody container, etc.

3. Embedded JSON blob validation: the builder pre-serialises listing data
   into seven `const XXX = {...};` JavaScript declarations via `js_safe`
   (which is a thin wrapper over `json.dumps`). Each one should therefore
   be parseable as JSON. A regression in `js_safe` or a template string
   corruption would surface here instantly.

All three layers share the same subprocess-built HTML via a session-scoped
fixture so we only pay the builder cost once per test session.
"""

from __future__ import annotations

import html.parser
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

# See test_build_dashboard_cli.BUILDER_TIMEOUT_SECONDS - same rationale.
BUILDER_TIMEOUT_SECONDS = 60


# ── Shared builder output fixture ──────────────────────────────────────────


@pytest.fixture(scope="session")
def built_html(
    tmp_path_factory: pytest.TempPathFactory,
    builder_script: Path,
    fixture_profile_path: Path,
    fixture_csv_path: Path,
    subprocess_env: dict,
) -> str:
    """Run the builder once per session and return the HTML text."""
    output_dir = tmp_path_factory.mktemp("html-structure")
    output_html = output_dir / "acme-bolt-dashboard.html"
    result = subprocess.run(
        [
            sys.executable,
            str(builder_script),
            "--profile",
            str(fixture_profile_path),
            "--csv",
            str(fixture_csv_path),
            "--output",
            str(output_html),
            "--date",
            "2026-04-10",
        ],
        capture_output=True,
        text=True,
        env=subprocess_env,
        timeout=BUILDER_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, f"builder failed: {result.stderr}"
    return output_html.read_text()


@pytest.fixture(scope="session")
def soup(built_html: str) -> BeautifulSoup:
    return BeautifulSoup(built_html, "html.parser")


# ── Tier 1: stdlib HTMLParser - is it well-formed at all? ──────────────────


class TestStdlibHtmlParse:
    """Zero-dependency sanity checks using only the standard library."""

    def test_stdlib_parser_walks_without_exception(self, built_html: str):
        """A vanilla HTMLParser should be able to tokenise the entire
        document without raising. Catches truly broken output."""

        class NullParser(html.parser.HTMLParser):
            pass

        parser = NullParser()
        parser.feed(built_html)
        parser.close()

    def test_has_html5_doctype(self, built_html: str):
        assert built_html.lstrip().lower().startswith("<!doctype html>")

    def test_has_opening_and_closing_html_tags(self, built_html: str):
        assert "<html" in built_html
        assert "</html>" in built_html.rstrip()

    def test_has_head_and_body_blocks(self, built_html: str):
        assert "<head>" in built_html and "</head>" in built_html
        assert "<body>" in built_html and "</body>" in built_html

    def test_no_python_format_string_leaks(self, built_html: str):
        """If a template f-string placeholder ever fails to substitute,
        literal curly-brace references like `{DISPLAY_NAME}` or
        `{profile_name}` would end up in the output."""
        leaked = [
            "{DISPLAY_NAME}",
            "{PROFILE_NAME}",
            "{profile_name}",
            "{display_name}",
            "{bg}",
            "{card_bg}",
            "{text_colour}",
            "{today_str}",
        ]
        for marker in leaked:
            assert marker not in built_html, f"unsubstituted placeholder leaked: {marker}"


# ── Tier 2: BeautifulSoup selector-based structural assertions ─────────────


class TestDocumentChrome:
    """High-level page structure and metadata."""

    def test_title_contains_display_name(self, soup: BeautifulSoup):
        title = soup.find("title")
        assert title is not None
        assert "Acme Bolt EV" in title.get_text()

    def test_h1_contains_display_name(self, soup: BeautifulSoup):
        h1 = soup.find("h1")
        assert h1 is not None
        assert "Acme Bolt EV" in h1.get_text()

    def test_lang_attribute_set(self, soup: BeautifulSoup):
        html_el = soup.find("html")
        assert html_el is not None
        assert html_el.get("lang") == "en"

    def test_viewport_meta_tag_present(self, soup: BeautifulSoup):
        viewport = soup.find("meta", attrs={"name": "viewport"})
        assert viewport is not None, "missing viewport meta tag"
        assert "width=device-width" in (viewport.get("content") or "")


class TestChartJsIntegration:
    """Chart.js CDN script and canvas elements must be wired up correctly."""

    EXPECTED_CANVAS_IDS = frozenset(
        {
            "timeSeriesChart",
            "depCurveChart",
            "dealScoreChart",
            "specPremiumChart",
            "negotiationChart",
            "priceMileageChart",
        }
    )

    def test_chartjs_script_tag_present(self, soup: BeautifulSoup):
        scripts = soup.find_all("script", src=True)
        chartjs = [s for s in scripts if "chart" in (s.get("src") or "").lower()]
        assert chartjs, "no Chart.js script tag found"

    def test_chartjs_loaded_from_remote_cdn(self, soup: BeautifulSoup):
        """Chart.js must be loaded from a remote HTTP(S) URL whose path
        mentions 'chart'. We deliberately do not lock this to a specific
        CDN host - switching from cdnjs to jsdelivr, unpkg, or any other
        should not break the test."""
        scripts = soup.find_all("script", src=True)
        srcs = [s.get("src") or "" for s in scripts]
        remote_chart_srcs = [
            src
            for src in srcs
            if (src.startswith("http://") or src.startswith("https://"))
            and "chart" in src.lower()
        ]
        assert remote_chart_srcs, (
            f"no remote Chart.js script tag found; srcs: {srcs}"
        )

    def test_exactly_six_canvases_present(self, soup: BeautifulSoup):
        canvases = soup.find_all("canvas")
        assert len(canvases) == 6, (
            f"expected exactly 6 canvases, found {len(canvases)}: "
            f"{[c.get('id') for c in canvases]}"
        )

    def test_all_canvas_ids_match_expected_set(self, soup: BeautifulSoup):
        canvases = soup.find_all("canvas")
        found_ids = {c.get("id") for c in canvases}
        assert found_ids == self.EXPECTED_CANVAS_IDS, (
            f"canvas IDs mismatch. Expected {self.EXPECTED_CANVAS_IDS}, "
            f"got {found_ids}"
        )


class TestFilterControls:
    """The dashboard exposes six filter dropdowns that cascade through
    every chart, KPI card, and table row."""

    EXPECTED_SELECT_IDS = frozenset(
        {
            "filterVariant",
            "filterGen",
            "filterMileage",
            "filterBudget",
            "filterValue",
            "filterWatch",
        }
    )

    def test_all_six_filter_selects_present(self, soup: BeautifulSoup):
        selects = soup.find_all("select")
        found_ids = {s.get("id") for s in selects}
        assert self.EXPECTED_SELECT_IDS.issubset(found_ids), (
            f"missing filter selects. Expected {self.EXPECTED_SELECT_IDS}, "
            f"got {found_ids}"
        )

    def test_filter_selects_have_onchange_handlers(self, soup: BeautifulSoup):
        for select_id in self.EXPECTED_SELECT_IDS:
            sel = soup.find("select", id=select_id)
            assert sel is not None
            assert sel.get("onchange"), f"{select_id} has no onchange handler"


class TestDataContainers:
    """KPI grid, market pulse panel, and sortable data table containers."""

    def test_kpi_row_container_present(self, soup: BeautifulSoup):
        assert soup.find("div", id="kpiRow") is not None

    def test_pulse_grid_container_present(self, soup: BeautifulSoup):
        assert soup.find("div", id="pulseGrid") is not None

    def test_data_table_and_tbody_present(self, soup: BeautifulSoup):
        table = soup.find("table", id="dataTable")
        assert table is not None
        tbody = soup.find("tbody", id="tableBody")
        assert tbody is not None


# ── Tier 2b: Embedded JSON blob validation ────────────────────────────────


class TestEmbeddedJsonBlocks:
    """The builder pre-serialises data as `const XXX = {...};` in an inline
    <script>. Each blob is produced by `js_safe` which wraps json.dumps,
    so every blob must be valid JSON when extracted."""

    EXPECTED_CONSTANTS = (
        "ALL_DATA",
        "DEP_CURVES",
        "SPEC_PREMIUMS",
        "NEGOTIATION_DATA",
        "PM_TREND",
        "VARIANT_COLOURS",
        "HIGHLIGHT_SPECS",
        "WATCHLIST",
        "TIME_SERIES",
        "PULSE_SINCE",
        "CAPTURE",
    )

    def _extract_blob(self, html_text: str, name: str) -> str:
        """Return the literal right-hand-side of `const NAME = ...;`.

        Uses Python's JSON decoder in streaming mode (raw_decode) to find
        where the JSON value ends. This correctly handles edge cases that a
        naive brace-balanced scan would miss - most importantly, braces or
        brackets appearing inside string literals - because raw_decode does
        proper JSON tokenisation with string escaping.
        """
        match = re.search(rf"const {re.escape(name)}\s*=\s*", html_text)
        assert match, f"const {name} declaration not found in HTML"
        start = match.end()
        decoder = json.JSONDecoder()
        try:
            _value, consumed = decoder.raw_decode(html_text[start:])
        except (json.JSONDecodeError, ValueError) as exc:
            pytest.fail(f"unterminated or invalid {name} literal: {exc}")
        return html_text[start : start + consumed]

    def test_every_expected_constant_is_declared(self, built_html: str):
        for name in self.EXPECTED_CONSTANTS:
            assert f"const {name}" in built_html, f"const {name} missing"

    @pytest.mark.parametrize(
        "name",
        [
            "ALL_DATA",
            "DEP_CURVES",
            "SPEC_PREMIUMS",
            "NEGOTIATION_DATA",
            "PM_TREND",
            "VARIANT_COLOURS",
            "HIGHLIGHT_SPECS",
            "WATCHLIST",
            "TIME_SERIES",
            "PULSE_SINCE",
            "CAPTURE",
        ],
    )
    def test_blob_parses_as_json(self, built_html: str, name: str):
        blob = self._extract_blob(built_html, name)
        try:
            json.loads(blob)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{name} is not valid JSON: {exc}\n{blob[:200]}")

    def test_all_data_is_non_empty_list_of_rows(self, built_html: str):
        blob = self._extract_blob(built_html, "ALL_DATA")
        data = json.loads(blob)
        assert isinstance(data, list)
        assert len(data) > 0, "ALL_DATA is empty - no listings rendered"
        # Each row should at least have a variant and a price.
        for row in data:
            assert "variant" in row
            assert "price" in row

    def test_dep_curves_has_one_entry_per_variant(self, built_html: str):
        blob = self._extract_blob(built_html, "DEP_CURVES")
        curves = json.loads(blob)
        # Fixture has 2 variants (Bolt Base, Bolt Sport) with enough points
        # to fit a curve for each.
        assert set(curves.keys()) == {"Bolt Base", "Bolt Sport"}, (
            f"expected both variant curves, got {list(curves.keys())}"
        )

    def test_variant_colours_match_profile(self, built_html: str, loaded_profile: dict):
        blob = self._extract_blob(built_html, "VARIANT_COLOURS")
        colours = json.loads(blob)
        for v in loaded_profile["variants"]:
            assert v["name"] in colours, f"variant {v['name']} missing from colours"
            assert colours[v["name"]] == v["colour"]
