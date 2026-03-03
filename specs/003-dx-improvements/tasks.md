# Tasks: Developer Experience Improvements

**Input**: Design documents from `/specs/003-dx-improvements/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/pre-commit-contract.md ✓, quickstart.md ✓

**Organization**: Tasks grouped by user story. US1 and US2 both write to `pre-commit.sh` so they are kept sequential. US3 (README.md) and US2's CI change are independently parallelisable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no upstream dependencies)
- **[Story]**: User story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bash restructuring that unlocks both US1 and US2 — establish `SCRIPT_DIR` and remove top-level `set -e`.

- [x] T001 Add `SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)` variable and replace top-level `set -e` with explicit `|| exit 1` guards on each quality gate invocation in `pre-commit.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: T001 is the sole foundational task. Once it is complete, US1 and US2 proceed sequentially (both write `pre-commit.sh`); US3 can run in parallel at any point.

**⚠️ CRITICAL**: T001 must be complete before any user story work begins.

**Checkpoint**: Foundation ready — proceed to Phase 3 (US1), then Phase 4 (US2); Phase 5 (US3) may start in parallel.

---

## Phase 3: User Story 1 — New Contributor Runs pre-commit.sh Cold (Priority: P1) 🎯 MVP

**Goal**: `pre-commit.sh` collects ALL missing prerequisites (venv, ruff/mypy/pytest, pmpython, cpmapi, pcp.pmi), reports each with a precise fix command, then exits non-zero without running any quality gate.

**Independent Test**: Run `./pre-commit.sh` with a stripped PATH and `$VIRTUAL_ENV` unset → exit 1, all seven prerequisite labels present in stdout, zero quality gate output.

### Tests for User Story 1 (TDD — write and confirm FAILING before implementation)

- [x] T002 [US1] Write failing pytest tests covering all 5 prerequisite check scenarios (all-missing, PCP-only-missing, cpmapi-importable-but-pcp.pmi-not, venv-absent, all-satisfied) using stub executables in `tmp_path/bin/` in `tests/unit/test_pre_commit_prereqs.py`

### Implementation for User Story 1

- [x] T003 [US1] Implement `check_prerequisites()` bash function in `pre-commit.sh` — `MISSING` array accumulator, all 7 checks (venv, ruff, mypy, pytest, pmpython, cpmapi, pcp.pmi), platform-aware remediation messages, exit 1 if non-empty (per plan.md design and `pre-commit-contract.md` label table)
- [x] T004 [US1] Call `check_prerequisites` as the first action in `pre-commit.sh` main execution path (before man page check and all quality gate steps)

**Checkpoint**: T002 tests pass. Running `./pre-commit.sh` in a missing-env produces the full prerequisite failure report with exact fix commands. All existing tests still pass.

---

## Phase 4: User Story 2 — Non-Interactive Man Page Check (Priority: P2)

**Goal**: `pre-commit.sh` validates `man/pmlogsynth.1` roff syntax non-interactively using a mandoc → groff-stderr-grep → existence-only fallback chain; a pager is never opened.

**Independent Test**: Run check against a valid `.1` file → exit 0, silent. Run against a malformed `.1` file → exit 1 with error output. Run with absent file → exit 1 "not found". Run in a no-TTY environment → no blocking.

### Tests for User Story 2 (TDD — write and confirm FAILING before implementation)

- [x] T005 [US2] Write failing pytest tests for man page check scenarios (valid roff, invalid roff, absent file, no-formatter fallback) in `tests/unit/test_man_page_check.py`

### Implementation for User Story 2

- [x] T006 [US2] Implement `check_man_page()` bash function in `pre-commit.sh` — path resolved via `$SCRIPT_DIR`, mandoc → groff stderr-grep → existence-only fallback chain, output semantics per `data-model.md` and `pre-commit-contract.md` Man Page Check Contract
- [x] T007 [US2] Replace `man ./man/pmlogsynth.1 || exit 1` invocation with `check_man_page || exit 1` in `pre-commit.sh`
- [x] T008 [P] [US2] Add `sudo apt-get install -y mandoc` step to the `quality` job in `.github/workflows/ci.yml` (before the pre-commit.sh invocation)

**Checkpoint**: T005 tests pass. Man page check runs non-interactively in all three tool-availability scenarios. Gate ordering matches `pre-commit-contract.md` Quality Gate Ordering Contract.

---

## Phase 5: User Story 3 — README Focused on Using pmlogsynth (Priority: P3)

**Goal**: Remove the "Running Tests" section (including its preceding `---` separator) from `README.md`; confirm the Contributing section cross-references `CONTRIBUTING.md`.

**Independent Test**: `grep -c "pytest" README.md` returns 0. The Contributing section in `README.md` contains a link to `CONTRIBUTING.md`.

### Implementation for User Story 3

- [x] T009 [P] [US3] Remove the "Running Tests" section and its preceding `---` separator from `README.md` (lines 151–168 per plan.md Design Decisions → README Change)
- [x] T010 [P] [US3] Verify the "Contributing" section in `README.md` references `CONTRIBUTING.md` for development workflows; add one-line cross-reference if absent

**Checkpoint**: `README.md` contains zero `pytest` references (SC-004). `CONTRIBUTING.md` link is present and correct. No regressions in any automated cross-reference checks.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the fully integrated gate and confirm all success criteria are met.

- [x] T011 Run `./pre-commit.sh` in a fully configured environment and confirm: no prerequisite warnings, no pager prompt, all quality gates pass, exit 0 — validating SC-001 through SC-005
- [x] T012 [P] Manually validate quickstart.md scenarios: macOS and Linux fresh-clone paths produce expected prerequisite output matching the contract labels

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1, T001)**: No dependencies — start immediately
- **US1 (Phase 3)**: Requires T001 complete
- **US2 (Phase 4)**: Requires T001 AND US1 complete (T002–T004) — sequential `pre-commit.sh` edits
- **US3 (Phase 5)**: Requires T001 only — can run concurrently with US1 and US2 (`README.md` is independent)
- **Polish (Phase 6)**: Requires all user stories complete

### User Story Dependencies

- **US1 (P1)**: Requires T001. No dependency on US2 or US3.
- **US2 (P2)**: Requires T001 AND US1 complete. T008 (ci.yml) is independent of T006/T007 within the story.
- **US3 (P3)**: Requires T001 only. Fully independent of US1 and US2.

### Within Each User Story

- Tests (T002, T005) MUST be written and confirmed RED before implementation begins
- Implementation tasks within each story run sequentially: T003 → T004, T006 → T007
- T008 (ci.yml) can run in parallel with T006/T007 — different file, no conflict

### Parallel Opportunities

- T009/T010 (US3 README) can start immediately after T001 — independent of US1 and US2 work
- T005 (US2 tests) can be written while T003/T004 (US1 impl) is in progress — different files
- T008 (ci.yml) can run in parallel with T006/T007 (both US2; different files)
- T012 (quickstart validation) can run in parallel with T011

---

## Parallel Example: User Story 2

```bash
# These run simultaneously (different files, no conflict):
Task T005: Write man page check tests in tests/unit/test_man_page_check.py
Task T008: Add mandoc apt-get step to .github/workflows/ci.yml

# Then sequentially:
Task T006: Implement check_man_page() in pre-commit.sh
Task T007: Replace man invocation in pre-commit.sh
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T001: bash restructuring
2. Complete T002: write failing prereq tests — confirm RED
3. Complete T003–T004: implement `check_prerequisites()`
4. **STOP and VALIDATE**: `pytest tests/unit/test_pre_commit_prereqs.py` passes; smoke test with stripped env produces actionable output
5. Ship US1 if ready — new contributors unblocked immediately

### Incremental Delivery

1. T001 → Foundation ready
2. T002 → T003 → T004: US1 done → test independently → demo (MVP)
3. T005 → T006 → T007 → T008: US2 done → test independently → demo
4. T009 → T010: US3 done → verify SC-004 → done
5. T011 → T012: full gate validation

### Parallel Team Strategy

With two developers after T001:

- Developer A: T002 → T003 → T004 (US1, prereq detection)
- Developer B: T009 → T010 (US3, README cleanup) — then T005 → T006 → T007 → T008 (US2)

---

## Notes

- [P] tasks = different files, no upstream dependencies — safe to run concurrently
- [Story] label maps each task to its user story for traceability
- TDD is mandatory: confirm T002 and T005 are RED before implementing T003 and T006 respectively
- US1 and US2 both write `pre-commit.sh` — keep them sequential to avoid conflicts
- US3 (README.md) is fully independent; tackle it whenever convenient after T001
- `pre-commit.sh` must remain pure bash — no language rewrite per Stability Contract
- Commit after each checkpoint to preserve working increments
