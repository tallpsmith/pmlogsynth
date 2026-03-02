#!/usr/bin/env bash
set -e

echo "=== ruff check ==="
ruff check .

echo "=== mypy ==="
mypy pmlogsynth/

echo "=== Tier 1 + Tier 2 tests ==="
pytest tests/tier1/ tests/tier2/ -v

if python3 -c "import pcp.pmi" 2>/dev/null; then
    echo "=== Tier 3 E2E tests (PCP available) ==="
    pytest tests/tier3/ -v
else
    echo "WARNING: PCP library not available — E2E tests skipped"
fi

echo "=== All checks passed ==="
