"""Shared pytest fixtures for Car Hunter tests.

Adds the plugin `scripts/` directory to sys.path so tests can import
`dashboard_lib` directly without installing anything. Provides path fixtures
pointing at the synthetic Acme Bolt EV fixture profile and CSV used throughout
the suite.

The plugin lives in a `car-hunter/` subdirectory at the repo root so the
marketplace manifest at `.claude-plugin/marketplace.json` can source it. Tests
stay at the repo root.
"""

import os
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = PROJECT_ROOT / "car-hunter"
SCRIPTS_DIR = PLUGIN_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Project root."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def plugin_dir() -> Path:
    """Plugin dir."""
    return PLUGIN_DIR


@pytest.fixture(scope="session")
def scripts_dir() -> Path:
    """Scripts dir."""
    return SCRIPTS_DIR


@pytest.fixture(scope="session")
def builder_script(scripts_dir: Path) -> Path:
    """Builder script."""
    return scripts_dir / "build_dashboard.py"


@pytest.fixture(scope="session")
def fixture_profile_path() -> Path:
    """Fixture profile path."""
    return FIXTURES_DIR / "acme-bolt.json"


@pytest.fixture(scope="session")
def fixture_csv_path() -> Path:
    """Fixture csv path."""
    return FIXTURES_DIR / "acme-bolt-listings.csv"


@pytest.fixture(scope="session")
def fixture_multigen_profile_path() -> Path:
    """Fixture multigen profile path."""
    return FIXTURES_DIR / "acme-bolt-multigen.json"


@pytest.fixture(scope="session")
def fixture_sparse_csv_path() -> Path:
    """Fixture sparse csv path."""
    return FIXTURES_DIR / "acme-bolt-sparse.csv"


@pytest.fixture(scope="session")
def fixture_listing_state_path() -> Path:
    """Fixture listing state path."""
    return FIXTURES_DIR / "acme-bolt-listing-state.json"


@pytest.fixture(scope="session")
def fixture_dated_csvs() -> list[Path]:
    """Fixture dated csvs."""
    return [
        FIXTURES_DIR / "acme-bolt-all-listings-2026-03-13.csv",
        FIXTURES_DIR / "acme-bolt-all-listings-2026-03-27.csv",
        FIXTURES_DIR / "acme-bolt-all-listings-2026-04-10.csv",
    ]


@pytest.fixture(scope="session")
def fixture_watchlist_path() -> Path:
    """Fixture watchlist path."""
    return FIXTURES_DIR / "acme-bolt-watchlist.json"


@pytest.fixture(scope="session")
def fixture_capture_manifest_path() -> Path:
    """Fixture capture manifest path."""
    return FIXTURES_DIR / "acme-bolt-capture-2026-04-10.json"


@pytest.fixture(scope="session")
def loaded_profile(fixture_profile_path: Path) -> dict:
    """Loaded profile."""
    with fixture_profile_path.open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def spec_options(loaded_profile: dict) -> list:
    """Spec options."""
    return loaded_profile["spec_options"]


@pytest.fixture(scope="session")
def variant_by_name(loaded_profile: dict) -> dict:
    """Variant by name."""
    return {v["name"]: v for v in loaded_profile["variants"]}


@pytest.fixture(scope="session")
def subprocess_env(project_root: Path) -> dict:
    """Env vars to pass to builder subprocesses so coverage traces them.

    Sets COVERAGE_PROCESS_START and adds tests/coverage_support to
    PYTHONPATH so the subprocess picks up sitecustomize.py and starts
    recording coverage before build_dashboard.py imports anything.
    """
    env = os.environ.copy()
    coverage_support = project_root / "tests" / "coverage_support"
    coverage_config = project_root / "pyproject.toml"
    if coverage_support.is_dir() and coverage_config.is_file():
        env["COVERAGE_PROCESS_START"] = str(coverage_config)
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{coverage_support}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(coverage_support)
        )
    return env
