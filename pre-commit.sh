#!/usr/bin/env bash

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

QUIET=false
[[ "${1:-}" == "-q" ]] && QUIET=true

PASSED=()

# Runs a named check silently.  On failure: dumps captured output (unless -q)
# and exits.  On success: records label for the summary.
run_check() {
    local label="$1"; shift
    local out rc
    out=$("$@" 2>&1)
    rc=$?
    if [ $rc -ne 0 ]; then
        $QUIET || printf '%s\n' "$out"
        exit $rc
    fi
    PASSED+=("✓ $label")
}

print_summary() {
    $QUIET && return
    printf 'pre-commit passed\n'
    for line in "${PASSED[@]}"; do
        printf '  %s\n' "$line"
    done
}

check_prerequisites() {
    local MISSING=()
    local platform
    platform=$(uname -s)

    if [ -z "$VIRTUAL_ENV" ]; then
        MISSING+=("MISSING: no virtualenv active
  Fix:  ./setup-venv.sh && source .venv/bin/activate")
    fi

    for tool in ruff mypy pytest; do
        if ! command -v "$tool" > /dev/null 2>&1; then
            MISSING+=("MISSING: $tool not found
  Fix:  pip install -e \".[dev]\"")
        fi
    done

    if ! command -v pmpython > /dev/null 2>&1; then
        if [ "$platform" = "Darwin" ]; then
            MISSING+=("MISSING: pmpython not on PATH
  PCP is a hard dependency. Install it first.
  Fix (macOS):  brew install pcp")
        else
            MISSING+=("MISSING: pmpython not on PATH
  PCP is a hard dependency. Install it first.
  Fix (Debian/Ubuntu):  sudo apt-get install pcp python3-pcp
  Fix (RHEL/Fedora):    sudo dnf install pcp python3-pcp")
        fi
    fi

    if ! python3 -c "import cpmapi" > /dev/null 2>&1; then
        MISSING+=("MISSING: cpmapi not importable
  Fix:  deactivate && ./setup-venv.sh && source .venv/bin/activate")
    fi

    if ! python3 -c "import pcp.pmi" > /dev/null 2>&1; then
        MISSING+=("MISSING: pcp.pmi not importable
  Fix:  deactivate && ./setup-venv.sh && source .venv/bin/activate")
    fi

    if [ ${#MISSING[@]} -gt 0 ]; then
        echo "=== prerequisite check failed ==="
        echo ""
        for item in "${MISSING[@]}"; do
            echo "$item"
            echo ""
        done
        exit 1
    fi
}

check_man_page() {
    local man_file="$SCRIPT_DIR/man/pmlogsynth.1"

    if [ ! -f "$man_file" ]; then
        echo "ERROR: man/pmlogsynth.1 not found" >&2
        return 1
    fi

    if command -v mandoc > /dev/null 2>&1; then
        mandoc -T lint "$man_file" > /dev/null 2>&1
        return $?
    fi

    if command -v groff > /dev/null 2>&1; then
        local groff_stderr
        groff_stderr=$(groff -man -T utf8 "$man_file" 2>&1 > /dev/null)
        if echo "$groff_stderr" | grep -qi "error"; then
            echo "$groff_stderr" >&2
            return 1
        fi
        return 0
    fi

    return 0
}

check_prerequisites

run_check "man page"                  check_man_page
run_check "ruff"                      ruff check .
run_check "mypy"                      mypy pmlogsynth/
run_check "unit + integration tests"  pytest tests/unit/ tests/integration/

if python3 -c "import pcp.pmi" 2>/dev/null; then
    run_check "E2E tests" pytest tests/e2e/
else
    PASSED+=("- E2E skipped (no pcp.pmi)")
fi

print_summary
