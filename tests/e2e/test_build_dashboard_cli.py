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

import re
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
    """Dashboard output."""
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
    """Builder exit status test cases."""
    def test_builder_exits_cleanly(self, dashboard_output):
        """Builder exits cleanly."""
        result, _ = dashboard_output
        assert result.returncode == 0, (
            f"Builder failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestBuilderStdout:
    """Builder stdout test cases."""
    def test_reports_loaded_listing_count(self, dashboard_output):
        """Reports loaded listing count."""
        result, _ = dashboard_output
        assert "Loaded 19 listings" in result.stdout

    def test_reports_regression_r_squared(self, dashboard_output):
        """Reports regression r squared."""
        result, _ = dashboard_output
        assert "Regression R" in result.stdout

    def test_reports_profile_display_name(self, dashboard_output):
        """Reports profile display name."""
        result, _ = dashboard_output
        assert "Acme Bolt EV" in result.stdout

    def test_excludes_brand_new_stock_from_regression(self, dashboard_output):
        """Excludes brand new stock from regression."""
        # Fixture has 19 total, 1 brand new, 18 used with age >= 0.5
        result, _ = dashboard_output
        assert "Regression on 18 used listings" in result.stdout


class TestBuilderOutput:
    """Builder output test cases."""
    def test_writes_html_file(self, dashboard_output):
        """Writes html file."""
        _, output_html = dashboard_output
        assert output_html.exists(), "dashboard HTML was not written"
        assert output_html.stat().st_size > 0

    def test_html_contains_profile_title(self, dashboard_output):
        """Html contains profile title."""
        _, output_html = dashboard_output
        html = output_html.read_text()
        assert "Acme Bolt EV" in html

    def test_html_includes_chartjs(self, dashboard_output):
        """Html includes chartjs."""
        _, output_html = dashboard_output
        html = output_html.read_text()
        assert "chart.js" in html.lower() or "chart.umd" in html.lower()

    def test_html_renders_both_variants(self, dashboard_output):
        """Html renders both variants."""
        _, output_html = dashboard_output
        html = output_html.read_text()
        assert "Bolt Base" in html
        assert "Bolt Sport" in html


class TestBuilderFailsHelpfully:
    """Builder fails helpfully test cases."""
    def test_missing_profile_returns_nonzero(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
    ):
        """Missing profile returns nonzero with a helpful message, not a raw traceback."""
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
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "not found" in combined.lower() or "no such file" in combined.lower()

    def test_malformed_json_profile(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
    ):
        """Profile with invalid JSON gives a clear error, not a raw traceback."""
        bad_profile = tmp_path / "corrupt.json"
        bad_profile.write_text("{not json,")
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(bad_profile),
                "--csv",
                str(fixture_csv_path),
            ],
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "not valid json" in combined.lower() or "invalid json" in combined.lower()

    def test_missing_csv_returns_nonzero(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        """Missing csv returns nonzero with a helpful message, not a raw traceback."""
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
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "not found" in combined.lower() or "no such file" in combined.lower()

    def test_profile_generations_not_a_list(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        """Profile with non-list generations gives a clear error, not AttributeError."""
        import json
        base = json.loads(fixture_profile_path.read_text())
        base["generations"] = "not a list"
        bad_profile = tmp_path / "bad-gens.json"
        bad_profile.write_text(json.dumps(base))
        result = subprocess.run(
            [sys.executable, str(builder_script),
             "--profile", str(bad_profile),
             "--csv", str(fixture_csv_path)],
            capture_output=True, text=True, env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "generations" in combined.lower()

    def test_profile_dashboard_not_a_dict(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        """Profile with non-dict dashboard gives a clear error."""
        import json
        base = json.loads(fixture_profile_path.read_text())
        base["dashboard"] = "should be a dict"
        bad_profile = tmp_path / "bad-dashboard.json"
        bad_profile.write_text(json.dumps(base))
        result = subprocess.run(
            [sys.executable, str(builder_script),
             "--profile", str(bad_profile),
             "--csv", str(fixture_csv_path)],
            capture_output=True, text=True, env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "dashboard" in combined.lower()

    def test_profile_missing_theme_subkey(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        """Profile whose dashboard.theme is missing a key gives a clear error."""
        import json
        base = json.loads(fixture_profile_path.read_text())
        del base["dashboard"]["theme"]["text_muted"]
        bad_profile = tmp_path / "bad-theme.json"
        bad_profile.write_text(json.dumps(base))
        result = subprocess.run(
            [sys.executable, str(builder_script),
             "--profile", str(bad_profile),
             "--csv", str(fixture_csv_path)],
            capture_output=True, text=True, env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "text_muted" in combined or "theme" in combined.lower()

    def test_profile_variant_missing_tier(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        """Profile with a variant missing 'tier' gives a clear error."""
        import json
        base = json.loads(fixture_profile_path.read_text())
        del base["variants"][0]["tier"]
        bad_profile = tmp_path / "bad-variant.json"
        bad_profile.write_text(json.dumps(base))
        result = subprocess.run(
            [sys.executable, str(builder_script),
             "--profile", str(bad_profile),
             "--csv", str(fixture_csv_path)],
            capture_output=True, text=True, env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "tier" in combined.lower()

    def test_profile_spec_option_missing_weight(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        """Profile with a spec option missing 'weight' gives a clear error."""
        import json
        base = json.loads(fixture_profile_path.read_text())
        del base["spec_options"][0]["weight"]
        bad_profile = tmp_path / "bad-spec.json"
        bad_profile.write_text(json.dumps(base))
        result = subprocess.run(
            [sys.executable, str(builder_script),
             "--profile", str(bad_profile),
             "--csv", str(fixture_csv_path)],
            capture_output=True, text=True, env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "weight" in combined.lower()

    def test_profile_missing_required_key(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
    ):
        """Profile missing a required key gives a clear error message."""
        import json

        bad_profile = tmp_path / "bad-profile.json"
        bad_profile.write_text(json.dumps({
            "profile_name": "test",
            "display_name": "Test",
            # "variants" deliberately omitted
            "generations": [],
            "spec_options": [],
            "search_filters": {},
            "dashboard": {},
        }))
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(bad_profile),
                "--csv",
                str(fixture_csv_path),
            ],
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        # Must be a clear message, not a raw KeyError traceback
        assert "missing required" in combined.lower()
        assert "variants" in combined

    def test_csv_missing_required_column(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        """CSV missing a required column gives a clear error message."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("variant,year,mileage\nBolt Base,2023,15000\n")
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(fixture_profile_path),
                "--csv",
                str(bad_csv),
            ],
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "missing required" in combined.lower()
        assert "price" in combined

    def test_csv_row_with_non_numeric_price(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        subprocess_env: dict,
    ):
        """CSV row with non-numeric price gives a clear error naming the row and field."""
        bad_csv = tmp_path / "bad-row.csv"
        bad_csv.write_text(
            "variant,price,year,mileage\n"
            "Bolt Base,35000,2023,15000\n"
            "Bolt Sport,TBC,2024,10000\n"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(fixture_profile_path),
                "--csv",
                str(bad_csv),
            ],
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "row 2" in combined.lower() or "row 2" in combined
        assert "TBC" in combined

    def test_bad_date_argument(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
    ):
        """Invalid --date gives a clear error, not a raw ValueError traceback."""
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(fixture_profile_path),
                "--csv",
                str(fixture_csv_path),
                "--date",
                "yesterday",
            ],
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "--date" in combined or "YYYY-MM-DD" in combined

    def test_malformed_listing_state_json(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
    ):
        """Corrupt listing-state JSON gives a clear error, not a raw traceback."""
        bad_state = tmp_path / "bad-state.json"
        bad_state.write_text("{not json")
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(fixture_profile_path),
                "--csv",
                str(fixture_csv_path),
                "--listing-state",
                str(bad_state),
            ],
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "listing state" in combined.lower() or "invalid json" in combined.lower()


class TestBuilderEdgeCases:
    """Cover conditional branches the main happy path doesn't exercise.

    The primary fixture (acme-bolt) is a single-generation profile with a
    full dataset, listing_id_date_encoding disabled, and no sidecar state.
    These tests use additional fixtures to hit the remaining branches in
    build_dashboard.py without regressing the main-path coverage.
    """

    def _run(self, builder_script, profile, csv, tmp_path, subprocess_env, extra_args=None):
        """Run."""
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

    def test_skipped_snapshots_produce_warnings(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        fixture_csv_path: Path,
        subprocess_env: dict,
    ):
        """Snapshot files that can't be used must produce visible warnings.

        Silently dropping a snapshot is how users lose data without knowing.
        Skipped files must be named in stdout.
        """
        # Simulate a user workspace by copying the fixture CSV with the expected
        # dated filename, plus two bad siblings.
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        profile_name = "acme-bolt"

        # Today's snapshot (needed for the builder to find a usable one)
        today_csv = workspace / f"{profile_name}-all-listings-2026-04-10.csv"
        today_csv.write_text(fixture_csv_path.read_text())

        # Bad date: Feb 30
        bad_date_csv = workspace / f"{profile_name}-all-listings-2026-02-30.csv"
        bad_date_csv.write_text(fixture_csv_path.read_text())

        # No listing_id column
        no_id_csv = workspace / f"{profile_name}-all-listings-2026-03-15.csv"
        no_id_csv.write_text("variant,price,year,mileage\nBolt Base,35000,2023,15000\n")

        output_html = workspace / f"{profile_name}-dashboard.html"
        result = subprocess.run(
            [
                sys.executable,
                str(builder_script),
                "--profile",
                str(fixture_profile_path),
                "--csv",
                str(today_csv),
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
        combined = result.stderr + result.stdout
        # Both skipped files should be named in a warning so the user knows.
        assert "2026-02-30" in combined, (
            "Feb 30 snapshot must be reported as skipped, not silently dropped"
        )
        assert "2026-03-15" in combined, (
            "snapshot without listing_id must be reported as skipped"
        )

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
        # The dashboard itself must surface the fallback - a stdout-only
        # warning is invisible to anyone opening the HTML file.
        html = output_html.read_text()
        assert 'class="regression-warning"' in html or 'id="regression-warning"' in html, (
            "fallback path must render a prominent regression-warning element"
        )

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


class TestSnapshotPipeline:
    """Exercise the snapshot glob + watchlist + capture manifest pipeline.

    Stages three dated CSVs containing a listing_id column into a tmp
    directory and runs the builder against the latest. The builder should
    load all three snapshots, diff today against the previous snapshot,
    emit a 28-entry rolling time series, pick up the watchlist, and render
    the capture badge.
    """

    def _run(self, builder_script, profile, csv, tmp_path, subprocess_env, extra=None):
        """Run."""
        output_html = tmp_path / "snap-dash.html"
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
        if extra:
            args.extend(extra)
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            env=subprocess_env,
            timeout=BUILDER_TIMEOUT_SECONDS,
        )
        return result, output_html

    def _stage(self, tmp_path: Path, fixture_dated_csvs) -> Path:
        """Stage."""
        for p in fixture_dated_csvs:
            (tmp_path / p.name).write_bytes(p.read_bytes())
        latest = max(fixture_dated_csvs, key=lambda p: p.name)
        return tmp_path / latest.name

    def test_builder_loads_all_snapshots(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        fixture_dated_csvs: list,
        subprocess_env: dict,
    ):
        """Builder loads all snapshots."""
        latest = self._stage(tmp_path, fixture_dated_csvs)
        result, output_html = self._run(
            builder_script, fixture_profile_path, latest, tmp_path, subprocess_env
        )
        assert result.returncode == 0, f"builder failed: {result.stderr}"
        assert "Loaded 3 snapshots" in result.stdout
        assert "Snapshot diff vs 2026-03-27" in result.stdout

    def test_time_series_has_28_entries(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        fixture_dated_csvs: list,
        subprocess_env: dict,
    ):
        """Time series has 28 entries."""
        latest = self._stage(tmp_path, fixture_dated_csvs)
        result, output_html = self._run(
            builder_script, fixture_profile_path, latest, tmp_path, subprocess_env
        )
        assert result.returncode == 0
        html = output_html.read_text()
        match = re.search(r"const TIME_SERIES\s*=\s*", html)
        assert match, "TIME_SERIES constant missing from generated HTML"
        import json as _json
        value, _ = _json.JSONDecoder().raw_decode(html[match.end():])
        assert isinstance(value, list)
        assert len(value) == 28
        assert value[-1]["date"] == "2026-04-10"

    def test_watchlist_marks_matching_row(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        fixture_dated_csvs: list,
        fixture_watchlist_path: Path,
        subprocess_env: dict,
    ):
        """Watchlist marks matching row."""
        latest = self._stage(tmp_path, fixture_dated_csvs)
        (tmp_path / "acme-bolt-watchlist.json").write_bytes(
            fixture_watchlist_path.read_bytes()
        )
        result, output_html = self._run(
            builder_script, fixture_profile_path, latest, tmp_path, subprocess_env
        )
        assert result.returncode == 0, f"builder failed: {result.stderr}"
        assert "Loaded watchlist: 1" in result.stdout
        html = output_html.read_text()
        # The ALL_DATA row for the watched listing_id should have watched: true
        match = re.search(r"const ALL_DATA\s*=\s*", html)
        assert match, "ALL_DATA constant missing from generated HTML"
        import json as _json
        data, _ = _json.JSONDecoder().raw_decode(html[match.end():])
        watched = [r for r in data if r.get("listing_id") == "202601150000000"]
        assert len(watched) == 1
        assert watched[0]["watched"] is True

    def test_capture_manifest_amber_badge(
        self,
        tmp_path: Path,
        builder_script: Path,
        fixture_profile_path: Path,
        fixture_dated_csvs: list,
        fixture_capture_manifest_path: Path,
        subprocess_env: dict,
    ):
        """Capture manifest amber badge."""
        latest = self._stage(tmp_path, fixture_dated_csvs)
        (tmp_path / "acme-bolt-capture-2026-04-10.json").write_bytes(
            fixture_capture_manifest_path.read_bytes()
        )
        result, output_html = self._run(
            builder_script, fixture_profile_path, latest, tmp_path, subprocess_env
        )
        assert result.returncode == 0, f"builder failed: {result.stderr}"
        assert "Capture: partial" in result.stdout
        html = output_html.read_text()
        assert "capture-badge-amber" in html
