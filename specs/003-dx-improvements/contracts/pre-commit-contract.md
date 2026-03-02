# Contract: pre-commit.sh

**Type**: CLI script (local quality gate)
**Branch**: `003-dx-improvements` | **Date**: 2026-03-02

---

## Exit Code Contract

| Condition | Exit Code | Side Effects |
|-----------|-----------|--------------|
| All prerequisites satisfied, all quality gates pass | 0 | Prints "=== All checks passed ===" |
| One or more prerequisites missing | 1 | Prints all missing items to stdout; quality gates DO NOT run |
| Quality gate fails (ruff/mypy/pytest/man page) | Non-zero | Standard tool error output |

---

## Prerequisite Check Output Contract

When prerequisites are missing, `pre-commit.sh` MUST:

1. Print `=== prerequisite check failed ===` to stdout
2. Print each missing item as a distinct block:
   ```
   MISSING: <short label>
     <explanation>
     Fix: <exact command>
   ```
3. Print all missing items before exiting — never stop at the first failure
4. Exit 1 without running any quality gate

### Prerequisite Labels and Remediation Messages

| Check | Label | Remediation message |
|-------|-------|---------------------|
| `$VIRTUAL_ENV` empty | `no virtualenv active` | `$(readlink -f $(which pmpython)) -m venv .venv && source .venv/bin/activate` (macOS) or `python3 -m venv .venv && source .venv/bin/activate` (Linux) |
| `ruff` not on PATH | `ruff not found` | `pip install -e ".[dev]"` |
| `mypy` not on PATH | `mypy not found` | `pip install -e ".[dev]"` |
| `pytest` not on PATH | `pytest not found` | `pip install -e ".[dev]"` |
| `pmpython` not on PATH | `pmpython not on PATH` | `sudo apt-get install pcp python3-pcp` (Linux) or `brew install pcp` (macOS) |
| `cpmapi` not importable | `cpmapi not importable` | Create venv from pmpython: `$(readlink -f $(which pmpython)) -m venv .venv` |
| `pcp.pmi` not importable | `pcp.pmi not importable` | Create venv from pmpython: `$(readlink -f $(which pmpython)) -m venv .venv` |

---

## Man Page Check Contract

Invoked as a named quality gate step (`=== man page check ===`).

| Condition | Exit Code | Stdout | Stderr |
|-----------|-----------|--------|--------|
| File absent | 1 | — | `ERROR: man/pmlogsynth.1 not found` |
| File present, valid roff, mandoc available | 0 | — | — |
| File present, invalid roff, mandoc available | 1 | — | mandoc lint output |
| File present, valid roff, groff available | 0 | — | — |
| File present, invalid roff, groff available | 1 | — | captured groff stderr |
| File present, no formatter | 0 | — | `WARNING: mandoc/groff not found — skipping roff syntax check` |

**MUST NOT**: open a pager, block on user input, invoke `man` command, or require a terminal.

---

## Quality Gate Ordering Contract

Gates run in this sequence, and ONLY after prerequisite check passes:

1. `=== man page check ===`
2. `=== ruff check ===`
3. `=== mypy ===`
4. `=== Unit + Integration tests ===`
5. `=== E2E tests (PCP available) ===` (conditional; skipped with visible WARNING if `pcp.pmi` not importable)

---

## Stability Contract

- `pre-commit.sh` remains a bash script; no language rewrite
- Script MUST NOT auto-create virtualenvs, auto-install packages, or modify the environment
- Script MUST work when invoked from the repository root
- Path resolution for `man/pmlogsynth.1` is relative to the script's directory (use
  `$(cd "$(dirname "$0")" && pwd)` to make it robust to invocation from any directory)
