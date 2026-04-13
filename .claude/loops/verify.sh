#!/usr/bin/env bash
# Quick verification script for the TDD refactoring loop.
# Run between every change to confirm green state.
#
# Usage:
#   .claude/loops/verify.sh          # full suite
#   .claude/loops/verify.sh unit     # unit tests only (fast)
#   .claude/loops/verify.sh coverage # full suite + coverage report

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

case "${1:-all}" in
    unit)
        echo "=== Unit tests ==="
        python3 -m pytest tests/unit -q
        ;;
    e2e)
        echo "=== E2E tests ==="
        python3 -m pytest tests/e2e -q
        ;;
    coverage)
        echo "=== Full suite + coverage ==="
        make coverage
        ;;
    all)
        echo "=== Full test suite ==="
        python3 -m pytest -q
        ;;
    *)
        echo "ERROR: unknown mode '${1}'. Use: all | unit | e2e | coverage" >&2
        exit 2
        ;;
esac

echo ""
echo "GREEN - all tests passed"
