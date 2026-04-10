"""Bootstrap coverage measurement in Python subprocesses spawned by e2e tests.

Python imports `sitecustomize` automatically at interpreter startup if it is
discoverable on sys.path. The e2e test fixture adds this directory to
PYTHONPATH and sets COVERAGE_PROCESS_START, which causes `coverage.process_startup`
to attach the coverage tracer before the builder script runs.

This file is only active during test runs - normal users invoking
build_dashboard.py directly never have this directory on their PYTHONPATH,
so production behaviour is unchanged.
"""

try:
    import coverage
    coverage.process_startup()
except ImportError:
    pass
