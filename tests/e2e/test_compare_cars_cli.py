"""End-to-end tests for compare_cars.py - the "what can I get for £X" CLI.

Runs the comparison across two profiles (the single-gen and multi-gen Acme
Bolt fixtures sharing the same listings CSV) and checks both the text
digest and the JSON contract the /compare-cars command consumes.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TIMEOUT = 60


@pytest.fixture(scope="session")
def compare_script(scripts_dir: Path) -> Path:
    return scripts_dir / "compare_cars.py"


def _run(compare_script, cars, subprocess_env, extra=None):
    args = [sys.executable, str(compare_script)]
    for profile, csv in cars:
        args += ["--car", f"{profile}:{csv}"]
    if extra:
        args += extra
    return subprocess.run(
        args, capture_output=True, text=True, env=subprocess_env, timeout=TIMEOUT,
    )


class TestCompareCarsCli:
    def test_two_car_comparison_at_budget(
        self, compare_script, fixture_profile_path, fixture_multigen_profile_path,
        fixture_csv_path, subprocess_env,
    ):
        result = _run(
            compare_script,
            [(fixture_profile_path, fixture_csv_path),
             (fixture_multigen_profile_path, fixture_csv_path)],
            subprocess_env,
            extra=["--budget", "40000"],
        )
        assert result.returncode == 0, f"compare failed: {result.stderr}"
        assert "Comparison at £40,000" in result.stdout
        assert "Acme Bolt EV" in result.stdout
        assert "Newest you can get:" in result.stdout
        assert "Best value:" in result.stdout

    def test_json_contract_for_command_layer(
        self, compare_script, fixture_profile_path, fixture_csv_path, subprocess_env,
    ):
        result = _run(
            compare_script,
            [(fixture_profile_path, fixture_csv_path)],
            subprocess_env,
            extra=["--budget", "40000", "--json"],
        )
        assert result.returncode == 0, f"compare failed: {result.stderr}"
        payload = result.stdout[result.stdout.index("{"):]
        data = json.loads(payload)
        assert data["budget"] == 40000
        car = data["cars"][0]
        assert car["display_name"] == "Acme Bolt EV"
        assert car["under_budget"] > 0
        assert car["under_budget"] <= car["total_listings"]
        assert {"newest_year", "lowest_mileage", "median_price",
                "best_value", "variants_available"} <= set(car)
        bv = car["best_value"]
        assert bv["price"] <= 40000
        assert "value_deviation_pct" in bv

    def test_budget_below_market_reports_entry_point(
        self, compare_script, fixture_profile_path, fixture_csv_path, subprocess_env,
    ):
        result = _run(
            compare_script,
            [(fixture_profile_path, fixture_csv_path)],
            subprocess_env,
            extra=["--budget", "1000"],
        )
        assert result.returncode == 0
        assert "market starts at" in result.stdout

    def test_no_budget_compares_whole_market(
        self, compare_script, fixture_profile_path, fixture_csv_path, subprocess_env,
    ):
        result = _run(
            compare_script,
            [(fixture_profile_path, fixture_csv_path)],
            subprocess_env,
        )
        assert result.returncode == 0
        assert "across the whole market" in result.stdout

    def test_malformed_car_spec_fails_helpfully(
        self, compare_script, subprocess_env, tmp_path,
    ):
        result = subprocess.run(
            [sys.executable, str(compare_script), "--car", "no-colon-here"],
            capture_output=True, text=True, env=subprocess_env, timeout=TIMEOUT,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "PROFILE:CSV" in combined
