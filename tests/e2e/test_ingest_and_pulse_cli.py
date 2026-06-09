"""End-to-end tests for ingest_listings.py and market_pulse.py.

The ingest test chains into the dashboard builder: the CSV the ingest
script emits must be consumed by build_dashboard.py without warnings about
unparseable rows. That chain is the core reliability contract of the
plugin - raw capture in, valid dashboard out, no LLM arithmetic between.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TIMEOUT = 60


@pytest.fixture(scope="session")
def ingest_script(scripts_dir: Path) -> Path:
    return scripts_dir / "ingest_listings.py"


@pytest.fixture(scope="session")
def pulse_script(scripts_dir: Path) -> Path:
    return scripts_dir / "market_pulse.py"


def _raw_capture():
    return {
        "captured": "2026-04-10",
        "sources": [
            {"name": "AutoTrader", "url": "https://example.invalid/at",
             "expected_pages": 2, "captured_pages": 2, "status": "ok"},
            {"name": "Cinch", "url": "https://example.invalid/cinch",
             "expected_pages": 1, "captured_pages": 0, "status": "failed"},
        ],
        "listings": [
            {
                "url": "https://www.autotrader.co.uk/car-details/202602170000123",
                "source": "AutoTrader", "variant": "Bolt Sport",
                "price": "£42,995", "year": 2024, "reg": "74",
                "mileage": "12,400 miles", "location": "Leeds",
                "specs": ["has_sunroof"], "is_brand_new_stock": False,
            },
            {
                # Same physical car captured on Cinch - must be deduplicated.
                "url": "https://www.cinch.co.uk/used-cars/9999",
                "source": "Cinch", "variant": "Bolt Sport",
                "price": 42995, "year": 2024, "reg": "74",
                "mileage": 12400, "location": "leeds",
                "specs": ["has_sunroof"],
            },
            {
                "url": "https://www.autotrader.co.uk/car-details/202601050000456",
                "source": "AutoTrader", "variant": "Bolt Base",
                "price": "£35,000", "year": 2023, "reg": "23",
                "mileage": "28,000 miles", "location": "Bristol",
                "specs": [],
            },
            {
                # Unusable price - must be skipped with a reason, not crash.
                "url": "https://www.autotrader.co.uk/car-details/202603010000789",
                "source": "AutoTrader", "variant": "Bolt Base",
                "price": "POA", "year": 2023, "mileage": "30,000 miles",
                "location": "York", "specs": [],
            },
        ],
    }


class TestIngestCli:
    def _run_ingest(self, ingest_script, profile, capture_path, outdir, subprocess_env):
        return subprocess.run(
            [sys.executable, str(ingest_script),
             "--profile", str(profile),
             "--capture", str(capture_path),
             "--outdir", str(outdir)],
            capture_output=True, text=True, env=subprocess_env, timeout=TIMEOUT,
        )

    def test_ingest_writes_csv_and_manifest(
        self, tmp_path, ingest_script, fixture_profile_path, subprocess_env,
    ):
        capture_path = tmp_path / "raw.json"
        capture_path.write_text(json.dumps(_raw_capture()))
        result = self._run_ingest(
            ingest_script, fixture_profile_path, capture_path, tmp_path, subprocess_env)
        assert result.returncode == 0, f"ingest failed: {result.stderr}"
        # 4 raw - 1 duplicate - 1 unparseable = 2 rows
        assert "Ingested 2 listings (1 cross-source duplicates collapsed)" in result.stdout
        assert "POA" in result.stdout  # skipped row reason is visible

        csv_path = tmp_path / "acme-bolt-all-listings-2026-04-10.csv"
        manifest_path = tmp_path / "acme-bolt-capture-2026-04-10.json"
        assert csv_path.is_file()
        assert manifest_path.is_file()

        manifest = json.loads(manifest_path.read_text())
        assert manifest["total_captured"] == 2
        assert any(s["status"] == "failed" for s in manifest["sources"])

        csv_text = csv_path.read_text()
        # Canonical AutoTrader id won the dedup, not the Cinch hash.
        assert "202602170000123" in csv_text
        assert "Cinch:" not in csv_text
        # Derived fields are present: Bolt Sport mk1 RRP is 58000.
        assert "58000" in csv_text

    def test_ingest_output_feeds_builder_cleanly(
        self, tmp_path, ingest_script, builder_script, fixture_profile_path, subprocess_env,
    ):
        """The chained contract: ingest output builds a dashboard without
        any skipped-row warnings."""
        capture_path = tmp_path / "raw.json"
        capture_path.write_text(json.dumps(_raw_capture()))
        result = self._run_ingest(
            ingest_script, fixture_profile_path, capture_path, tmp_path, subprocess_env)
        assert result.returncode == 0, f"ingest failed: {result.stderr}"

        csv_path = tmp_path / "acme-bolt-all-listings-2026-04-10.csv"
        build = subprocess.run(
            [sys.executable, str(builder_script),
             "--profile", str(fixture_profile_path),
             "--csv", str(csv_path)],
            capture_output=True, text=True, env=subprocess_env, timeout=TIMEOUT,
        )
        assert build.returncode == 0, f"builder failed: {build.stderr}"
        assert "Loaded 2 listings" in build.stdout
        assert "skipping CSV" not in build.stdout
        # Capture badge picks up the manifest the ingest script wrote.
        assert "Capture: failed" in build.stdout
        assert (tmp_path / "acme-bolt-dashboard.html").is_file()

    def test_missing_capture_file_fails_helpfully(
        self, tmp_path, ingest_script, fixture_profile_path, subprocess_env,
    ):
        result = self._run_ingest(
            ingest_script, fixture_profile_path, tmp_path / "nope.json", tmp_path, subprocess_env)
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "not found" in combined.lower()

    def test_malformed_capture_json_fails_helpfully(
        self, tmp_path, ingest_script, fixture_profile_path, subprocess_env,
    ):
        capture_path = tmp_path / "bad.json"
        capture_path.write_text("{not json")
        result = self._run_ingest(
            ingest_script, fixture_profile_path, capture_path, tmp_path, subprocess_env)
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "not valid json" in combined.lower()


class TestMarketPulseCli:
    def _stage_snapshots(self, tmp_path, fixture_dated_csvs):
        for p in fixture_dated_csvs:
            (tmp_path / p.name).write_bytes(p.read_bytes())

    def test_pulse_text_digest(
        self, tmp_path, pulse_script, fixture_profile_path, fixture_dated_csvs, subprocess_env,
    ):
        self._stage_snapshots(tmp_path, fixture_dated_csvs)
        result = subprocess.run(
            [sys.executable, str(pulse_script),
             "--profile", str(fixture_profile_path),
             "--dir", str(tmp_path)],
            capture_output=True, text=True, env=subprocess_env, timeout=TIMEOUT,
        )
        assert result.returncode == 0, f"pulse failed: {result.stderr}"
        assert "Comparing 2026-03-27 -> 2026-04-10" in result.stdout
        assert "New arrivals:" in result.stdout
        assert "Price drops:" in result.stdout

    def test_pulse_json_shape(
        self, tmp_path, pulse_script, fixture_profile_path, fixture_dated_csvs, subprocess_env,
    ):
        self._stage_snapshots(tmp_path, fixture_dated_csvs)
        result = subprocess.run(
            [sys.executable, str(pulse_script),
             "--profile", str(fixture_profile_path),
             "--dir", str(tmp_path), "--json"],
            capture_output=True, text=True, env=subprocess_env, timeout=TIMEOUT,
        )
        assert result.returncode == 0, f"pulse failed: {result.stderr}"
        # stdout may carry loader warnings before the JSON; parse from the
        # first opening brace.
        payload = result.stdout[result.stdout.index("{"):]
        pulse = json.loads(payload)
        assert pulse["latest_date"] == "2026-04-10"
        assert pulse["previous_date"] == "2026-03-27"
        assert isinstance(pulse["new_listings"], list)
        assert isinstance(pulse["price_drops"], list)

    def test_pulse_with_no_snapshots_explains(
        self, tmp_path, pulse_script, fixture_profile_path, subprocess_env,
    ):
        result = subprocess.run(
            [sys.executable, str(pulse_script),
             "--profile", str(fixture_profile_path),
             "--dir", str(tmp_path)],
            capture_output=True, text=True, env=subprocess_env, timeout=TIMEOUT,
        )
        assert result.returncode == 0
        assert "run /search-cars first" in result.stdout
