#!/usr/bin/env bash
set -e

echo "=== man page check ==="
man ./man/pmlogsynth.1 || exit 1

echo "=== ruff check ==="
ruff check .

echo "=== mypy ==="
mypy pmlogsynth/

echo "=== Unit + Integration tests ==="
pytest tests/unit/ tests/integration/ -v

if python3 -c "import pcp.pmi" 2>/dev/null; then
    echo "=== E2E tests (PCP available) ==="
    pytest tests/e2e/ -v
else
    echo "WARNING: PCP library not available — E2E tests skipped"
fi

echo "=== All checks passed ==="
