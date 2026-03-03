#!/usr/bin/env bash

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# Auto-activate the project venv if one exists and nothing is currently active.
# This means `./pre-commit.sh` works straight after `./setup-venv.sh` without
# a separate `source .venv/bin/activate` step.
if [ -z "$VIRTUAL_ENV" ] && [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

QUIET=false
[[ "${1:-}" == "-q" ]] && QUIET=true

# Prints a progress line before running, then ✓ on success so the user sees
# live activity instead of silence during long-running checks.
#
# In non-quiet mode: run the command with direct stdout/stderr so writes go
# straight to the TTY — no pipe buffering, no batched terminal rendering.
# In quiet mode: capture output and suppress it on success; dump on failure.
run_check() {
    local label="$1"; shift
    $QUIET || printf '  → %s...\n' "$label"
    local rc
    if $QUIET; then
        local out
        out=$("$@" 2>&1)
        rc=$?
        [ $rc -ne 0 ] && printf '%s\n' "$out"
    else
        "$@" 2>&1
        rc=$?
    fi
    [ $rc -ne 0 ] && exit $rc
    $QUIET || printf '  ✓ %s\n' "$label"
}

print_summary() {
    $QUIET && return
    printf 'pre-commit passed\n'
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
        mandoc -T lint "$man_file"
        return $?
    fi

    if command -v groff > /dev/null 2>&1; then
        groff -man -T utf8 "$man_file" > /dev/null
        return $?
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
    $QUIET || printf '  - E2E skipped (no pcp.pmi)\n'
fi

print_summary
