# Tasks: Phase 2 — E2E Tests, Documentation, and Quickstart Validation

**Input**: Design documents from `/specs/002-phase2-e2e-docs/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths included in every description

---

## Phase 1: Setup

**Purpose**: Confirm the existing baseline before any changes are made

- [X] T001 Run `pytest tests/tier1/ tests/tier2/ -v` and confirm all existing tests pass — this is the green baseline to preserve throughout the rename

---

## Phase 2: Foundational — Test Directory Rename (US5 prerequisite for US1)

**Purpose**: Rename tier-numbered directories to semantically named ones. All US1 work writes to `tests/e2e/` — this rename must complete before Phase 3 can begin.

**⚠️ CRITICAL**: US1 (Phase 3) cannot begin until this phase is complete — `tests/e2e/` does not exist until T002 runs.

- [X] T002 [US5] Rename all three test directories: `git mv tests/tier1 tests/unit`, `git mv tests/tier2 tests/integration`, `git mv tests/tier3 tests/e2e` — three sequential git-mv commands in `tests/`
- [X] T003 [P] [US5] Update `@pytest.mark.tier1` → `@pytest.mark.unit` in all test files under `tests/unit/` (batch sed/replace across all `*.py` files in that directory)
- [X] T004 [P] [US5] Update `@pytest.mark.tier2` → `@pytest.mark.integration` in all test files under `tests/integration/` (batch replace across all `*.py` files in that directory)
- [X] T005 [P] [US5] Update `@pytest.mark.tier3` → `@pytest.mark.e2e` in `tests/e2e/test_e2e.py`
- [X] T006 [P] [US5] Update `tests/conftest.py` — rename marker registration strings (`tier1`/`tier2`/`tier3` → `unit`/`integration`/`e2e`) and update the PCP-skip guard from `tier3` to `e2e`
- [X] T007 [P] [US5] Update `pyproject.toml` `[tool.pytest.ini_options]` markers list — replace `tier1`, `tier2`, `tier3` entries with `unit`, `integration`, `e2e`
- [X] T008 [P] [US5] Update `pre-commit.sh` — replace all `tests/tier1/` and `tests/tier2/` paths with `tests/unit/` and `tests/integration/`; replace `tests/tier3/` with `tests/e2e/`
- [X] T009 [P] [US5] Update `.github/workflows/ci.yml` — replace all `tests/tier1/`, `tests/tier2/`, `tests/tier3/` directory references with `tests/unit/`, `tests/integration/`, `tests/e2e/`
- [X] T010 [P] [US5] Update `CLAUDE.md` — project structure diagram (tier1/2/3 → unit/integration/e2e) and Commands section test-running examples

**Checkpoint**: Run `pytest tests/unit/ tests/integration/ -v` — all tests must pass. Run `pytest tests/e2e/ -v` — tests must auto-skip on macOS (no PCP). Zero `tier1`/`tier2`/`tier3` references in any file.

---

## Phase 3: User Story 1 — Automated E2E Archive Verification (Priority: P1) 🎯 MVP

**Goal**: Replace the stub E2E test with real archive-generation and PCP-tool-verification assertions that catch broken archive output automatically.

**Independent Test**: `pytest tests/e2e/ -v` on a Linux system with PCP installed — all tests pass with real assertions. No `pytest.skip("not yet implemented")` stubs remain.

- [X] T011 [US1] Replace stub content in `tests/e2e/test_e2e.py` with three real test functions: `test_archive_roundtrip` (generates archive from `good-baseline.yaml` with `-C tests/fixtures/profiles/`, asserts `pmlogcheck` rc==0, `pmval -a <archive> kernel.all.load` rc==0, `pmrep -a <archive> kernel.all.load` rc==0); `test_validate_accepts_good_profiles` (parametrized over `good-baseline.yaml` and `workload-linear-ramp.yaml`, asserts rc==0); `test_validate_rejects_bad_profiles` (parametrized over `bad-ratio.yaml`, `bad-duration.yaml`, `bad-noise.yaml`, asserts rc==1 and stderr non-empty). All tests use `@pytest.mark.e2e`, accept `pcp_available` fixture for auto-skip, and invoke CLI via `sys.executable + ["-m", "pmlogsynth", ...]`. Archive isolation via `tmp_path` fixture per `contracts/e2e-test-contract.md`.
- [X] T012 [US1] Verify `.github/workflows/ci.yml` E2E job runs `tests/e2e/` with no stub-skip guards or `xfail` marks remaining — remove any `# not yet implemented` comments or `pytest.mark.xfail` decorators from the E2E job definition; confirm job is not gated on a skip flag

**Checkpoint**: CI E2E job goes green with zero stubs or skips marked "not yet implemented" (SC-001).

---

## Phase 4: User Story 2 — Discoverable Man Page (Priority: P2)

**Goal**: Patch the existing man page with the two missing items (repeat:daily warning, `pcp(1)` in SEE ALSO), wire it into package installation, and add a CI check to catch rendering regressions.

**Independent Test**: `man ./man/pmlogsynth.1` exits 0 with no rendering errors. `grep -i "pcp(1)" man/pmlogsynth.1` returns a match. `grep -i "repeat.*daily" man/pmlogsynth.1` shows a "cannot be combined" warning.

- [X] T013 [US2] Patch `man/pmlogsynth.1` — two targeted edits: (1) add `pcp(1)` to the SEE ALSO section alongside the existing `pmlogcheck(1)`, `pmval(1)`, `pmrep(1)`, `pmlogdump(1)`, `pmlogimport(1)` entries; (2) add an explicit "WARNING: `repeat: daily` cannot be combined with other phases" note in the YAML PROFILE FORMAT section's `repeat` field description (FR-016, FR-017)
- [X] T014 [P] [US2] Add `data_files` entry to `pyproject.toml` for man page installation so that `pip install .` makes `man pmlogsynth` available: `data_files = [("share/man/man1", ["man/pmlogsynth.1"])]` (FR-018)
- [X] T015 [P] [US2] Add man page verification step to `.github/workflows/ci.yml` quality job: `man ./man/pmlogsynth.1` must exit 0 — add as a step in the existing lint/type-check job or a new dedicated man-check step (FR-019)
- [X] T016 [P] [US2] Add man page check to `pre-commit.sh` local quality gate: `man ./man/pmlogsynth.1 || exit 1` so the local gate mirrors CI (FR-019)

**Checkpoint**: `man ./man/pmlogsynth.1` exits 0 locally and in CI (SC-008). SEE ALSO contains `pcp(1)`. repeat:daily warning is visible in the PROFILES section.

---

## Phase 5: User Story 3 — Self-Describing README (Priority: P3)

**Goal**: Patch README to be accurate and self-contained for new users, while keeping it under ~150 lines by linking out to dedicated docs files for detailed content.

**Independent Test**: Follow the README Quick Start on a system with PCP installed — all commands exit 0 and produce a readable archive (SC-003). Running Tests section references `tests/unit/`, `tests/integration/`, `tests/e2e/` only.

- [X] T017 [US3] Patch `README.md` with all required changes: (1) add `pmlogsynth --validate` one-liner before the generate step in Quick Start; (2) add one-sentence repeat:daily callout in Quick Start; (3) update Running Tests section directory names from `tier1/tier2/tier3` to `unit/integration/e2e`; (4) add Profile Format paragraph with link to `docs/profile-format.md`; (5) add Metrics one-liner: *"24 PCP metrics — `pmlogsynth --list-metrics` or `man pmlogsynth`"*; (6) add CLI Reference one-liner: *"Full CLI reference — `man pmlogsynth`"*; (7) add Contributing one-liner linking `CONTRIBUTING.md` (FR-020 through FR-026, FR-035)
- [X] T018 [P] [US3] Create `docs/profile-format.md` — full YAML schema documentation covering all workload and hardware profile fields, types, defaults, valid ranges, constraints, and an explicit `repeat:daily` exclusivity warning with a "don't do this" invalid example and explanation of the error it produces (FR-025, FR-031)
- [X] T019 [P] [US3] Create `CONTRIBUTING.md` at repo root — dev setup (`pip install -e ".[dev]"`), pre-commit gate usage (`./pre-commit.sh`), test structure explanation (unit/integration/e2e tiers and what each covers), and PR conventions

**Checkpoint**: README Quick Start is accurate and runnable. No broken links (FR-026). `docs/profile-format.md` and `CONTRIBUTING.md` exist and contain the content listed above.

---

## Phase 6: User Story 4 — Quickstart Script Validation (Priority: P4)

**Goal**: Add an automated test that validates the README Quick Start workflow end-to-end, catching any drift between documentation and CLI behaviour.

**Independent Test**: `pytest tests/e2e/test_e2e.py::test_quickstart_workflow -v` on a system with PCP installed — passes end-to-end. Auto-skips on macOS without PCP.

- [X] T020 [US4] Add `test_quickstart_workflow` function to `tests/e2e/test_e2e.py` — 4-step subprocess sequence using `sys.executable + ["-m", "pmlogsynth", ...]`: step 1 `--validate -C tests/fixtures/profiles/ good-baseline.yaml` asserts rc==0; step 2 `-C tests/fixtures/profiles/ -o <tmp_path>/archive good-baseline.yaml` asserts rc==0; step 3 `pmlogcheck <tmp_path>/archive` asserts rc==0; step 4 `pmval -a <tmp_path>/archive kernel.all.load` asserts rc==0. Uses `@pytest.mark.e2e` and `pcp_available` fixture. Archive written to `tmp_path` fixture for automatic isolation and cleanup (FR-027, FR-028, FR-029, per `contracts/e2e-test-contract.md`).

**Checkpoint**: `pytest tests/e2e/ -v` on a PCP-enabled system passes all four test functions with real assertions.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify consistency across the whole change set

- [X] T021 [P] Verify FR-031 consistency — compare repeat:daily constraint wording across `man/pmlogsynth.1`, `README.md`, and `docs/profile-format.md`; confirm phrasing matches the exact validation error message produced by `pmlogsynth --validate` on a profile with repeat:daily coexisting with other phases (SC-007)
- [X] T022 [P] Verify SC-009 — run `git grep -i "tier[123]"` across all tracked files and confirm zero matches; fix any stragglers found
- [X] T023 Run full test suite `pytest -v` to confirm all unit and integration tests pass and all e2e tests auto-skip correctly on macOS; no regressions from the rename or file edits

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run immediately
- **Foundational (Phase 2)**: Depends on Phase 1 baseline ✅ — **BLOCKS Phase 3 (US1)**
- **US1 (Phase 3)**: Depends on Phase 2 completion — `tests/e2e/` must exist
- **US2 (Phase 4)**: Depends on Phase 2 only — can start as soon as Phase 2 completes, independently of US1
- **US3 (Phase 5)**: Depends on Phase 2 only — can start as soon as Phase 2 completes, independently of US1/US2
- **US4 (Phase 6)**: Depends on Phase 3 (US1) — `test_quickstart_workflow` is added to the same file as the Phase 3 tests; complete US1 first
- **Polish (Phase 7)**: Depends on all user story phases complete

### User Story Dependencies

- **US5 (Foundational)**: No dependencies — blocks US1
- **US1 (P1)**: Depends on US5 (directory must exist) — no dependency on US2, US3, US4
- **US2 (P2)**: Depends on US5 only — no dependency on US1, US3, US4
- **US3 (P3)**: Depends on US5 only — no dependency on US1, US2, US4
- **US4 (P4)**: Depends on US1 (same test file) — no dependency on US2, US3

### Within Each Phase

- T002 (directory renames) must complete before T003–T005 (marker updates in renamed files)
- T003, T004, T005 can run in parallel after T002 (different directories)
- T006–T010 can run in parallel with T002–T005 (different files: conftest.py, pyproject.toml, pre-commit.sh, ci.yml, CLAUDE.md)
- T013 (man page patches) must complete before verifying T015 (CI step) works locally
- T018 and T019 can run in parallel with T017 (different new files vs. patch to existing README)

### Parallel Opportunities

```bash
# Phase 2 — after T002 completes:
T003  # tests/unit/ marker updates
T004  # tests/integration/ marker updates
T005  # tests/e2e/ marker update
T006  # tests/conftest.py
T007  # pyproject.toml
T008  # pre-commit.sh
T009  # .github/workflows/ci.yml
T010  # CLAUDE.md

# Phase 4 — after T013 completes:
T014  # pyproject.toml data_files
T015  # ci.yml man check step
T016  # pre-commit.sh man check

# Phase 5 — all parallel:
T017  # README.md patch
T018  # docs/profile-format.md (new file)
T019  # CONTRIBUTING.md (new file)

# Phase 7 — parallel:
T021  # repeat:daily consistency check
T022  # tier1/2/3 grep verification
```

---

## Implementation Strategy

### MVP First (US5 + US1 Only)

1. Complete Phase 1: baseline confirmation
2. Complete Phase 2: US5 rename — establishes `tests/e2e/` and clean marker names
3. Complete Phase 3: US1 — real E2E assertions replace stubs
4. **STOP and VALIDATE**: `pytest tests/e2e/ -v` on CI passes green (SC-001)
5. Ship: the largest quality gap is closed

### Incremental Delivery

1. Phase 1 + Phase 2 (US5) → Rename complete, baseline still green
2. Phase 3 (US1) → E2E suite live → CI green with real assertions (MVP)
3. Phase 4 (US2) → Man page complete and installable
4. Phase 5 (US3) → README accurate and self-describing
5. Phase 6 (US4) → Quickstart workflow validated automatically
6. Phase 7 → Final consistency sweep, no tier references remain

---

## Summary

| Phase | User Story | Tasks | Priority |
|-------|-----------|-------|----------|
| Phase 2 | US5 — Test Directory Rename | T002–T010 (9 tasks) | P2 (foundational) |
| Phase 3 | US1 — E2E Archive Verification | T011–T012 (2 tasks) | P1 |
| Phase 4 | US2 — Discoverable Man Page | T013–T016 (4 tasks) | P2 |
| Phase 5 | US3 — Self-Describing README | T017–T019 (3 tasks) | P3 |
| Phase 6 | US4 — Quickstart Validation | T020 (1 task) | P4 |
| Phase 7 | Polish | T021–T023 (3 tasks) | — |

**Total tasks**: 23 (T001–T023, including 1 setup task)
**Parallel opportunities**: 13 tasks marked [P]
**MVP scope**: Phases 1–3 (US5 + US1) — closes the largest quality gap with 12 tasks
