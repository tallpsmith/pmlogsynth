# Implementation Plan: Developer Experience Improvements

**Branch**: `003-dx-improvements` | **Date**: 2026-03-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-dx-improvements/spec.md`

## Summary

Add collect-all-failures prerequisite detection to `pre-commit.sh` (venv, dev tools, PCP
bindings), replace the interactive `man` pager call with a non-interactive `mandoc`/`groff`
syntax check, and trim README.md to user-facing content by removing the "Running Tests"
section. CONTRIBUTING.md already contains complete contributor documentation; no changes
needed there.

## Technical Context

**Language/Version**: Bash (pre-commit.sh); Markdown (README.md); Python 3.8+ (new unit tests)
**Primary Dependencies**: mandoc (system package; apt/brew) for man page validation; groff as
fallback (pre-installed on ubuntu-latest)
**Storage**: N/A
**Testing**: pytest + subprocess (no new test frameworks); Tier 1 tests for prereq detection
**Target Platform**: macOS (Homebrew PCP) + Linux (Debian/Ubuntu, RHEL/Fedora)
**Project Type**: CLI script (bash) + documentation edits
**Performance Goals**: N/A — gate wall-clock time unchanged
**Constraints**: pre-commit.sh remains pure bash; detect-and-advise only (no auto-install);
path resolution must work when invoked from any directory
**Scale/Scope**: Three files modified: `pre-commit.sh`, `README.md`, `.github/workflows/ci.yml`

## Constitution Check

*Gate evaluated before Phase 0 research; re-evaluated post-design below.*

### Pre-design evaluation

| Principle | Status | Notes |
|-----------|--------|-------|
| I. PCP Archive Fidelity | ✅ PASS | No changes to archive generation |
| II. Layered Testing | ✅ PASS | New bash tests added as Tier 1 (no PCP needed); TDD applies |
| III. Declarative Profile-First | ✅ PASS | No profile schema changes |
| IV. Phase-Aware Extensibility | ✅ PASS | No CLI/API surface changes |
| V. Minimal External Dependencies | ✅ PASS | mandoc is a system package, not a pip dep |
| VI. CI-First Quality Gates | ✅ PASS | mandoc added to CI `quality` job; gate parity maintained |

**Gate decision**: PASS — no violations. Research confirmed tool choices and testing strategy.

### Post-design re-evaluation

All six principles remain unaffected. The only CI change is `apt install mandoc` in the
`quality` job, which adds a system tool used only for man page validation — not a Python
dependency. Tier 1/2/3 parity is preserved.

## Project Structure

### Documentation (this feature)

```text
specs/003-dx-improvements/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── pre-commit-contract.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
pre-commit.sh                        # prereq check function + non-interactive man check
README.md                            # remove "Running Tests" section (lines 151–168)
.github/workflows/ci.yml             # add mandoc to quality job
tests/unit/test_pre_commit_prereqs.py  # NEW: Tier 1 subprocess tests for prereq detection
tests/unit/test_man_page_check.py      # NEW: Tier 1 tests for man page check logic
man/pmlogsynth.1                     # no changes (input to validation)
CONTRIBUTING.md                      # no changes needed
```

**Structure decision**: No new directories or Python modules. All changes are to the bash
script, CI config, documentation, and a new test file in the existing Tier 1 directory.

## Design Decisions

### pre-commit.sh restructuring

1. **Remove `set -e`** from the top level — replace with explicit `|| exit 1` on each quality
   gate invocation. `set -e` prevents accumulating multiple failures.

2. **`check_prerequisites()` function**: runs first, before the man page check and all quality
   gates. Collects all failures into a `MISSING` array; exits 1 if non-empty.

3. **`check_man_page()` function**: replaces `man ./man/pmlogsynth.1 || exit 1`. Resolves the
   file path relative to the script directory (robust to invocation from any working directory).
   Validator chain: `mandoc -T lint` → `groff` + stderr grep → existence-only + warning.

4. **Path robustness**: `SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)` at script top.

### Prerequisite check logic

```
check_prerequisites():
  MISSING = []
  if $VIRTUAL_ENV is empty:
    MISSING += venv-absent message (macOS/Linux guidance)
  for tool in ruff mypy pytest:
    if not command -v $tool:
      MISSING += tool-absent message
  if not command -v pmpython:
    MISSING += pmpython-absent message
  if not python3 -c "import cpmapi" 2>/dev/null:
    MISSING += cpmapi-absent message
  if not python3 -c "import pcp.pmi" 2>/dev/null:
    MISSING += pcp.pmi-absent message
  if MISSING non-empty:
    print header
    for each item: print formatted message
    exit 1
```

### Testing approach (TDD — tests written before implementation)

Tests in `tests/unit/test_pre_commit_prereqs.py` and `tests/unit/test_man_page_check.py`
use `subprocess.run` with a manipulated `env` dict and stub executables in `tmp_path/bin/`
that mimic absent or failing tools. Key scenarios:

- All tools missing (minimal PATH) → exit 1, all tools named in output
- Only PCP missing (full PATH, no pmpython) → exit 1, PCP message in output
- cpmapi importable but pcp.pmi not → exit 1, distinct messages for each
- All prerequisites satisfied → function returns without error

Man page tests:
- Valid roff file → exit 0
- Malformed roff file → exit 1 with error output
- Absent file → exit 1 with "not found" message
- No formatter available → exit 0 with warning (existence-only pass)

### README change

Remove lines 151–168 (the "Running Tests" section including the `---` separator before it).
The existing "Contributing" section already references CONTRIBUTING.md — no text changes
needed there.

## Complexity Tracking

No constitution violations — no entries required.

## Assumptions

- `VIRTUAL_ENV` environment variable is the canonical way to detect an active venv in bash
  (set by `venv/bin/activate`; not set for system Python or conda envs not using this mechanism)
- Platform detection for venv guidance uses `uname -s` (Darwin = macOS, else Linux)
- mandoc installation in CI adds negligible time to the `quality` job
- CONTRIBUTING.md test documentation is already complete (verified: it covers all three tiers,
  the pre-commit gate, and TDD guidance)
