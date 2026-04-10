"""End-to-end tests that invoke build_dashboard.py as a subprocess.

These are the only tests that exercise the full builder binary including
argparse, file I/O, and HTML generation. Slower than unit/integration but
catch regressions in the orchestration layer no other test layer sees.

Subprocess coverage: the `subprocess_env` fixture enables coverage tracing
inside the spawned interpreter by setting COVERAGE_PROCESS_START and adding
the tests/coverage_support directory (containing sitecustomize.py) to
PYTHONPATH. `coverage combine` afterwards merges the subprocess datafiles
with the in-process ones so the final report covers build_dashboard.py too.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Hard upper bound for any builder subprocess call. The full builder
# typically completes in under a second against the fixture data;
# anything approaching this limit indicates a hang rather than slow
# execution.
BUILDER_TIMEOUT_SECONDS = 60


@pytest.fixture
def dashboard_output(
    tmp_path: Path,
    builder_script: Path,
    fixture_profile_path: Path,
    fixture_csv_path: Path,
    subprocess_env: dict,
):
    output_html = tmp_path / "acme-bolt-dashboard.html"
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
    return result, output_html


class TestBuilderExitStatus:
    def test_builder_exits_cleanly(self, dashboard_output):
        result, _ = dashboard_output
        assert result.returncode == 0, (
            f"Builder failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestBuilderStdout:
    def test_reports_loaded_listing_count(self, dashboard_output):
        result, _ = dashboard_output
        assert "Loaded 19 listings" in result.stdout

    def test_reports_regression_r_squared(self, dashboard_output):
        result, _ = dashboard_output
        assert "Regression R" in result.stdout

    def test_reports_profile_display_name(self, dashboard_output):
        result, _ = dashboard_output
        assert "Acme Bolt EV" in result.stdout

    def test_excludes_brand_new_stock_from_regression(self, dashboard_output):
        # Fixture has 19 total, 1 brand new, 18 used with age >= 0.5
        result, _ = dashboard_output
        assert "Regression on 18 used listings" in result.stdout


class TestBuilderOutput:
    def test_writes_html_file(self, dashboard_output):
        _, output_html = dashboard_output
        assert output_html.exists(), "dashboard HTML was not written"
        assert output_html.stat().st_size > 0

    def test_html_contains_profile_title(self, dashboard_output):
        _, output_html = dashboard_output
        html = output_html.read_text()
        assert "Acme Bolt EV" in html

    def test_html_includes_chartjs(self, dashboard_output):
        _, output_html = dashboard_output
        html = output_html.read_text()
        assert "chart.js" in html.lower() or "chart.umd" in html.lower()

    def test_html_renders_both_variants(self, dashboard_output):
        _, output_html = dashboard_output
        html = output_html.read_text()
        assert "Bolt Base" in html
        assert "Bolt Sport" in html


class TestBuilderFailsHelpfully:
    def test_missing_profile_returns_nonzero(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
    ):
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(tmp_path / "nonexistent.json"),
                "--csv",
                str(fixture_csv_path),
            ],
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0

    def test_missing_csv_returns_nonzero(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(fixture_profile_path),
                "--csv",
                str(tmp_path / "nonexistent.csv"),
            ],
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0


class TestBuilderEdgeCases:
    """Cover conditional branches the main happy path doesn't exercise.

    The primary fixture (acme-bolt) is a single-generation profile with a
    full dataset, listing_id_date_encoding disabled, and no sidecar state.
    These tests use additional fixtures to hit the remaining branches in
    build_dashboard.py without regressing the main-path coverage.
    """

    def _run(self, builder_script, profile, csv, tmp_path, subprocess_env, extra_args=None):
        output_html = tmp_path / "edge-dashboard.html"
        args = [
            sys.executable,
            str(builder_script),
            "--profile",
            str(profile),
            "--csv",
            str(csv),
            "--output",
            str(output_html),
            "--date",
            "2026-04-10",
        ]
        if extra_args:
            args.extend(extra_args)
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        return result, output_html

    def test_sparse_csv_triggers_regression_fallback(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        fixture_sparse_csv_path: Path,
        subprocess_env: dict,
    ):
        """Three-row CSV: fewer rows than regression features, so the builder
        must fall back to zero-coefficients without crashing.

        Also covers:
          - `continue` branch when a variant has <5 depreciation-curve points
          - `pm_trend = []` branch when there are <=5 total used listings
          - "insufficient data" branch in the spec-premium calculation
        """
        result, output_html = self._run(
            builder_script,
            fixture_profile_path,
            fixture_sparse_csv_path,
            tmp_path,
            subprocess_env,
        )
        assert result.returncode == 0, f"builder failed: {result.stderr}"
        assert "Loaded 3 listings" in result.stdout
        assert "WARNING: Not enough data for regression" in result.stdout
        assert output_html.exists()
        assert output_html.stat().st_size > 0

    def test_multigen_profile_emits_generation_filter_js(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_multigen_profile_path: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
    ):
        """Multi-generation profile (>1 entry in `generations[]`) triggers
        the dashboard's generation-filter JavaScript emission branch.

        The fixture CSV only contains mk1 rows but that is fine - the branch
        fires on the profile shape, not the CSV contents.
        """
        result, output_html = self._run(
            builder_script,
            fixture_multigen_profile_path,
            fixture_csv_path,
            tmp_path,
            subprocess_env,
        )
        assert result.returncode == 0, f"builder failed: {result.stderr}"
        html = output_html.read_text()
        # Both generation names from the multigen profile should appear in
        # the embedded filter map.
        assert "mk1" in html
        assert "mk2" in html
        # Both gen labels should also be present somewhere in the page chrome.
        assert "Mk1" in html
        assert "Mk2" in html

    def test_listing_state_sidecar_populates_autotrader_urls(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_multigen_profile_path: Path,
        fixture_csv_path: Path,
        fixture_listing_state_path: Path,
        subprocess_env: dict,
    ):
        """The multigen fixture has listing_id_date_encoding enabled. When
        a --listing-state sidecar provides matching composite keys the
        builder must construct AutoTrader URLs and calculate days-on-market
        for those rows.
        """
        result, output_html = self._run(
            builder_script,
            fixture_multigen_profile_path,
            fixture_csv_path,
            tmp_path,
            subprocess_env,
            extra_args=["--listing-state", str(fixture_listing_state_path)],
        )
        assert result.returncode == 0, f"builder failed: {result.stderr}"
        assert "Loaded listing state" in result.stdout
        assert "5 listing IDs" in result.stdout
        assert "4 price changes" in result.stdout
        html = output_html.read_text()
        # The AutoTrader URL for at least one listing should appear in the
        # embedded table data.
        assert "autotrader.co.uk/car-details/202601150000001" in html

    def test_listing_state_sidecar_auto_detected_by_profile_name(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_multigen_profile_path: Path,
        fixture_csv_path: Path,
        fixture_listing_state_path: Path,
        subprocess_env: dict,
    ):
        """If --listing-state is not passed, the builder auto-detects a
        sidecar named `{profile_name}-listing-state.json` next to the CSV.
        This test stages both the CSV and the sidecar in a tmp directory
        with the expected filename and runs the builder without the flag.
        """
        staged_csv = tmp_path / "acme-bolt-listings.csv"
        staged_csv.write_bytes(fixture_csv_path.read_bytes())
        staged_sidecar = tmp_path / "acme-bolt-multigen-listing-state.json"
        staged_sidecar.write_bytes(fixture_listing_state_path.read_bytes())

        result, output_html = self._run(
            builder_script,
            fixture_multigen_profile_path,
            staged_csv,
            tmp_path,
            subprocess_env,
        )
        assert result.returncode == 0, f"builder failed: {result.stderr}"
        assert "Loaded listing state" in result.stdout, (
            "auto-detected sidecar was not picked up"
        )
        assert "5 listing IDs" in result.stdout
        html = output_html.read_text()
        assert "autotrader.co.uk/car-details/202601150000001" in html

    @pytest.mark.parametrize(
        "bad_content,expected_token",
        [
            # _state itself not a dict (JSON array instead)
            ('["not", "an", "object"]', "must contain a JSON object"),
            # listing_ids is not a dict
            ('{"listing_ids": "not-a-dict"}', "listing_ids"),
            # price_changes is not a dict
            ('{"listing_ids": {}, "price_changes": [1, 2, 3]}', "price_changes"),
            # listing_ids has a non-string value
            ('{"listing_ids": {"42500_Testville": 12345}}', "listing_ids"),
            # price_changes has a non-numeric value
            (
                '{"listing_ids": {}, "price_changes": {"42500_Testville": "wat"}}',
                "price_changes",
            ),
        ],
        ids=[
            "state-not-object",
            "listing-ids-not-dict",
            "price-changes-not-dict",
            "listing-ids-non-string-value",
            "price-changes-non-numeric-value",
        ],
    )
    def test_malformed_listing_state_fails_loudly(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_multigen_profile_path: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
        bad_content: str,
        expected_token: str,
    ):
        """Every validation branch in the sidecar loader should exit
        non-zero with a descriptive error message. Covers the four
        `raise SystemExit` checks added to fail loudly on malformed
        sidecars instead of silently falling back to empty dicts.
        """
        bad_sidecar = tmp_path / "bad-state.json"
        bad_sidecar.write_text(bad_content)

        result, _ = self._run(
            builder_script,
            fixture_multigen_profile_path,
            fixture_csv_path,
            tmp_path,
            subprocess_env,
            extra_args=["--listing-state", str(bad_sidecar)],
        )
        assert result.returncode != 0
        assert expected_token in (result.stderr + result.stdout)
