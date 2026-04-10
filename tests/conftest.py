"""Shared pytest fixtures for Car Hunter tests.

Adds the `scripts/` directory to sys.path so tests can import `dashboard_lib`
directly without installing anything. Provides path fixtures pointing at the
synthetic Acme Bolt EV fixture profile and CSV used throughout the suite.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def scripts_dir() -> Path:
    return SCRIPTS_DIR


@pytest.fixture(scope="session")
def builder_script(scripts_dir: Path) -> Path:
    return scripts_dir / "build_dashboard.py"


@pytest.fixture(scope="session")
def fixture_profile_path() -> Path:
    return FIXTURES_DIR / "acme-bolt.json"


@pytest.fixture(scope="session")
def fixture_csv_path() -> Path:
    return FIXTURES_DIR / "acme-bolt-listings.csv"


@pytest.fixture(scope="session")
def loaded_profile(fixture_profile_path: Path) -> dict:
    with fixture_profile_path.open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def spec_options(loaded_profile: dict) -> list:
    return loaded_profile["spec_options"]


@pytest.fixture(scope="session")
def variant_by_name(loaded_profile: dict) -> dict:
    return {v["name"]: v for v in loaded_profile["variants"]}

