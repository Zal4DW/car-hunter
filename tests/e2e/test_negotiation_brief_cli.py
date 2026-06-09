"""End-to-end tests for negotiation_brief.py.

Stages the dated snapshot fixtures and asks for a brief on a listing that
appears in them, asserting the JSON contract the negotiation-coach skill
consumes: target position, levers, offer anchors, and comparables.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TIMEOUT = 60


@pytest.fixture(scope="session")
def brief_script(scripts_dir: Path) -> Path:
    return scripts_dir / "negotiation_brief.py"


def _stage(tmp_path, fixture_dated_csvs):
    for p in fixture_dated_csvs:
        (tmp_path / p.name).write_bytes(p.read_bytes())


def _run(brief_script, profile, searches_dir, listing_id, subprocess_env):
    return subprocess.run(
        [sys.executable, str(brief_script),
         "--profile", str(profile),
         "--dir", str(searches_dir),
         "--listing", listing_id],
        capture_output=True, text=True, env=subprocess_env, timeout=TIMEOUT,
    )


class TestNegotiationBriefCli:
    def test_brief_json_contract(
        self, tmp_path, brief_script, fixture_profile_path,
        fixture_dated_csvs, subprocess_env,
    ):
        _stage(tmp_path, fixture_dated_csvs)
        result = _run(brief_script, fixture_profile_path, tmp_path,
                      "202601150000000", subprocess_env)
        assert result.returncode == 0, f"brief failed: {result.stderr}"
        payload = result.stdout[result.stdout.index("{"):]
        brief = json.loads(payload)

        assert brief["profile"] == "acme-bolt"
        target = brief["target"]
        assert target["listing_id"] == "202601150000000"
        assert target["price"] > 0
        assert "predicted_price" in target

        assert isinstance(brief["levers"], list)
        for lever in brief["levers"]:
            assert lever["strength"] in ("strong", "moderate", "weak")
            assert lever["detail"]

        anchors = brief["offer_anchors"]
        assert anchors["opening_offer"] <= anchors["asking_price"]
        assert anchors["target_price"] <= anchors["asking_price"]
        assert anchors["asking_price"] == target["price"]

        assert isinstance(brief["comparables"], list)
        assert len(brief["comparables"]) > 0
        assert all(c["listing_id"] != target["listing_id"]
                   for c in brief["comparables"])

        history = brief["price_history"]
        assert history is not None
        assert history["prices"][0]["price"] > 0

    def test_sold_listing_fails_helpfully(
        self, tmp_path, brief_script, fixture_profile_path,
        fixture_dated_csvs, subprocess_env,
    ):
        _stage(tmp_path, fixture_dated_csvs)
        result = _run(brief_script, fixture_profile_path, tmp_path,
                      "999999999999999", subprocess_env)
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "not in the latest snapshot" in combined

    def test_no_snapshots_fails_helpfully(
        self, tmp_path, brief_script, fixture_profile_path, subprocess_env,
    ):
        result = _run(brief_script, fixture_profile_path, tmp_path,
                      "202601150000000", subprocess_env)
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Traceback" not in combined
        assert "run /search-cars" in combined.lower()
