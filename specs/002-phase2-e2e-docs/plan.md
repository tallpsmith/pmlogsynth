# Implementation Plan: Phase 2 — E2E Tests, Documentation, and Quickstart Validation

**Branch**: `002-phase2-e2e-docs` | **Date**: 2026-03-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-phase2-e2e-docs/spec.md`

## Summary

Phase 1 left three quality gaps: stub-only E2E tests (no real archive assertions), tier-numbered
test directories (opaque naming), and documentation that's incomplete or diverged from the
implementation. Phase 2 closes all three by (1) renaming `tests/tier{1,2,3}/` to
`tests/{unit,integration,e2e}/`, (2) replacing the E2E stub with a full archive-generation
and verification suite, (3) patching the man page and README with the few remaining gaps,
and (4) adding a CI-validated automated quickstart test.

## Technical Context

**Language/Version**: Python 3.8+ (minimum); latest stable tested in CI matrix
**Primary Dependencies**: pytest, pcp.pmi (system package), PyYAML
**Storage**: Temporary directories (via `tempfile.mkdtemp`) for E2E-generated archives; cleaned after each test
**Testing**: pytest with `unit`/`integration`/`e2e` markers (renamed from `tier1`/`tier2`/`tier3`)
**Target Platform**: Linux (CI, E2E); macOS (developer, unit+integration only)
**Project Type**: CLI tool
**Performance Goals**: N/A — test correctness only
**Constraints**: Python 3.8 syntax throughout; no walrus operator, no match, no `|` unions; no NumPy
**Scale/Scope**: ~5 new E2E test functions; ~15 file updates for rename; 2 documentation patches

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. PCP Archive Fidelity | ✅ PASS | E2E tests assert `pmlogcheck` exits 0 — directly validates Principle I |
| II. Layered Testing | ✅ PASS | Rename preserves tier structure; marker rename is surface-only, contracts unchanged |
| III. Declarative Profile-First | ✅ PASS | No profile schema changes |
| IV. Phase-Aware Extensibility | ✅ PASS | No architectural changes to CLI or domain models |
| V. Minimal External Dependencies | ✅ PASS | No new pip dependencies; `subprocess` is stdlib |
| VI. CI-First Quality Gates | ✅ PASS | FR-019 (CI man check) adds a gate that runs both locally and in CI |

**Gate result: GREEN — proceed to Phase 0.**

*Post-design re-check*: All gates remain GREEN. The E2E test design uses only stdlib (`subprocess`,
`tempfile`) and existing fixtures. Man page and README patches add no new dependencies.

## Project Structure

### Documentation (this feature)

```text
specs/002-phase2-e2e-docs/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output (points to existing, captures what we'll update)
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (end-state after this feature)

```text
tests/
├── conftest.py          # UPDATED: markers renamed tier1/2/3 → unit/integration/e2e
├── fixtures/
│   ├── profiles/
│   │   ├── good-baseline.yaml      (existing — primary E2E fixture)
│   │   ├── bad-ratio.yaml          (existing — validation failure fixture)
│   │   ├── bad-duration.yaml       (existing — validation failure fixture)
│   │   ├── bad-noise.yaml          (existing — validation failure fixture)
│   │   └── test-single-cpu.yaml    (existing — hardware profile fixture)
│   └── workload-linear-ramp.yaml   (existing)
├── unit/                # RENAMED from tests/tier1/
│   └── [all existing tier1 test files, unchanged]
├── integration/         # RENAMED from tests/tier2/
│   └── [all existing tier2 test files, unchanged]
└── e2e/                 # RENAMED from tests/tier3/
    └── test_e2e.py      # REPLACED: full archive assertions (no stubs)

docs/
└── profile-format.md    # NEW: full YAML schema, repeat:daily warning, examples

man/
└── pmlogsynth.1         # PATCHED: repeat:daily exclusivity warning + pcp(1) in SEE ALSO

CONTRIBUTING.md          # NEW: dev setup, pre-commit gate, test structure, PR conventions
README.md                # PATCHED: Quick Start (--validate step), section stubs linking out,
                         #          Running Tests (renamed dirs); stays under ~200 lines

pyproject.toml           # UPDATED: pytest markers renamed; data_files for man page install
pre-commit.sh            # UPDATED: directory paths unit/integration/e2e
.github/workflows/ci.yml # UPDATED: directory paths + man page CI check
CLAUDE.md                # UPDATED: Commands section, project structure diagram
```

**Structure Decision**: Single project (existing layout). Only renames and patches — no new
modules, no new packages, no new domain models. E2E tests live in `tests/e2e/test_e2e.py`.

## Complexity Tracking

> No Constitution violations to justify.
