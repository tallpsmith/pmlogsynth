# Research: Developer Experience Improvements

**Branch**: `003-dx-improvements` | **Date**: 2026-03-02

---

## Decision 1: Man Page Syntax Validation Tool

**Decision**: Use `mandoc -T lint` as primary validator; fall back to `groff` with stderr error
grep; fall back to file-existence-only with warning if neither is available.

**Rationale**:
- `mandoc -T lint` reliably exits non-zero on syntax errors — it is purpose-built for validation
- `groff` is pre-installed on ubuntu-latest and available via Homebrew, but **does not reliably
  exit non-zero on roff syntax errors** — it emits warnings to stderr and exits 0. A stderr
  grep for "error" is required when using groff.
- `nroff` is a groff wrapper and has the same unreliable exit-code behaviour.
- `mandoc` is NOT pre-installed on ubuntu-latest; it requires `apt install mandoc`. Adding it
  to the CI `quality` job is trivial and gives the most reliable validation.

**Tool availability matrix**:

| Tool | ubuntu-latest (CI) | macOS (Homebrew) | Exit non-zero on syntax error? |
|------|-------------------|-------------------|-------------------------------|
| mandoc | Needs `apt install mandoc` | `brew install mandoc` | Yes (exit 3+) |
| groff | Pre-installed | `brew install groff` | No (exits 0; errors to stderr) |
| nroff | Pre-installed (wraps groff) | Via groff | No |

**Recommended invocations**:
```bash
# Primary (mandoc)
mandoc -T lint man/pmlogsynth.1 >/dev/null 2>&1

# Fallback (groff — capture stderr and grep for "error")
groff -man -T utf8 man/pmlogsynth.1 2>&1 >/dev/null | grep -qi "error"

# Existence-only fallback (warn, exit 0 — per FR-009)
echo "WARNING: mandoc/groff not found — skipping roff syntax check (file exists)"
```

**CI impact**: Add `sudo apt-get install -y mandoc` to the `quality` job in `ci.yml`.

**Alternatives considered**:
- groff only, grepping stderr: fragile; "error" pattern may not catch all malformed input
- mandoc only, no fallback: fails cleanly on developer machines without mandoc; acceptable
  but degrades the local experience on fresh macOS setups before Homebrew is fully configured

---

## Decision 2: Bash Script Testing Strategy

**Decision**: pytest + subprocess. Test the prerequisite check and man page check by invoking
`pre-commit.sh` (or an extracted `check-prereqs.sh`) from Python tests with a manipulated
environment — no new test frameworks (no bats-core).

**Rationale**:
- The project already runs pytest for all test tiers; introducing bats adds a second test
  runner, a new CI step, and an additional installation requirement on developer machines.
- Python's `subprocess.run` with `env=` argument gives clean, readable isolation.
- `tmp_path` fixture and stub executables (fake `ruff` that exits 1) provide reliable mocking
  without relying on the developer's actual PATH.
- Stubs live in `tmp_path/bin/` and are prepended to PATH for the subprocess call.

**Key testing patterns**:
```python
# Stub a missing tool
stub = tmp_path / "bin" / "ruff"
stub.write_text("#!/bin/bash\nexit 127")
stub.chmod(0o755)
env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"

result = subprocess.run(["bash", str(pre_commit_script)], env=env, ...)
assert result.returncode != 0
assert "ruff" in result.stdout
```

**Testability constraint**: `pre-commit.sh` must be structured so prerequisite checks run
completely and produce their output before any quality gate command executes. If the script
uses `set -e`, it must NOT `set -e` during the prereq check accumulation loop, or the
prereq check must be extracted into a function/subshell that collects failures without
short-circuiting.

**Alternatives considered**:
- bats-core: better shell-native syntax; but adds new tooling with zero gain over subprocess
  for this feature's scope
- Shell DIY assertions: fragile, hard to maintain, no fixture support

**Tier assignment for pre-commit.sh tests**: Tier 1 (unit tier directory) — these tests have
no PCP dependency. The `pre-commit.sh` invocation under test never reaches the quality gates;
it exits at the prereq check step.

---

## Decision 3: Prerequisite Check Architecture

**Decision**: Single `check_prerequisites()` bash function at the top of `pre-commit.sh`.
Collect all failures into a `MISSING` array; print all failures at end; exit non-zero if array
is non-empty. No extraction to a separate script.

**Rationale**:
- Keeping the check in `pre-commit.sh` avoids a new file dependency and keeps the script
  self-contained.
- An array-based accumulator (`MISSING+=("message")`) cleanly implements the collect-all
  behaviour required by FR-005.
- `set -e` must be removed from or guarded around the prerequisite check to allow accumulation
  without early exit. Replace top-level `set -e` with explicit `|| exit 1` on each quality
  gate command instead.

**Prerequisite check order** (matches user story scenarios):
1. venv active? (`$VIRTUAL_ENV` non-empty)
2. `ruff`, `mypy`, `pytest` on PATH?
3. `pmpython` on PATH?
4. `cpmapi` importable from active Python?
5. `pcp.pmi` importable from active Python?

**macOS guidance**: When `$VIRTUAL_ENV` is empty, the error message includes the macOS-specific
venv creation command using `$(readlink -f $(which pmpython)) -m venv .venv`.

**Alternatives considered**:
- Separate `check-prereqs.sh`: cleaner for testing but adds a file; not worth it for this scope
- Sourced helper functions: same benefit without the extra file

---

## Decision 4: README Cleanup Scope

**Decision**: Remove the entire "Running Tests" section from README.md. Add a one-line
cross-reference under "Contributing" pointing to CONTRIBUTING.md. CONTRIBUTING.md requires
no changes — it already documents all test tiers, the pre-commit gate, and TDD guidance.

**Rationale**:
- README "Running Tests" section (lines 151–168) duplicates content already in CONTRIBUTING.md
- End-users have no need for pytest command examples; mixing it in adds noise
- CONTRIBUTING.md already covers: test structure table, per-tier run commands, TDD mandate,
  PR conventions

**Verification**: SC-004 requires zero `pytest` references in README.md after the change.
The existing `./pre-commit.sh` reference in "Running Tests" also moves out; the "Contributing"
section reference to CONTRIBUTING.md is preserved.

**Alternatives considered**:
- Keeping a one-line "run `./pre-commit.sh`" in README: unnecessary; CONTRIBUTING.md covers it
