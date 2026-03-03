#!/usr/bin/env bash
# Creates a virtualenv with PCP bindings accessible, then installs dev dependencies.
# Usage: ./setup-venv.sh [venv-dir]   (default: .venv)

set -euo pipefail

VENV_DIR="${1:-.venv}"
platform=$(uname -s)

echo "=== setup-venv: creating ${VENV_DIR} ==="

if [ "$platform" = "Darwin" ]; then
    if ! command -v pmpython > /dev/null 2>&1; then
        echo "ERROR: pmpython not found. PCP is a hard dependency." >&2
        echo "  Install:  brew install pcp" >&2
        exit 1
    fi
    PYTHON=$(pmpython -c "import sys; print(sys.executable)")
else
    PYTHON=python3
fi

"$PYTHON" -m venv --system-site-packages "$VENV_DIR"

echo "=== Installing dev dependencies ==="
"$VENV_DIR/bin/pip" install --quiet -e ".[dev]"

echo ""
echo "=== Done! Activate with: source ${VENV_DIR}/bin/activate ==="
