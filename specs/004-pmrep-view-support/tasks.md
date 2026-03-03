# Tasks: pmrep View Support

**Feature**: 004-pmrep-view-support
**Input**: Design documents from `/specs/004-pmrep-view-support/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/metric-inventory.md ✓, quickstart.md ✓

**Tests**: TDD — mandatory per project CLAUDE.md and plan.md constitution (each phase explicitly calls "Tests first")

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- **TDD**: write tests first, confirm they FAIL, then implement

---

## Phase 1: Setup

**Purpose**: PMID verification — confirm all `[VERIFY]`-tagged metric item numbers before any implementation touches domain files

- [X] T001 Verify all [VERIFY]-tagged PMIDs in research.md via `pminfo -d <metrics>` on Linux CI and update research.md with confirmed values — corrected from PCP source (github.com/performancecopilot/pcp src/pmdas/linux/pmda.c); 3 items still flagged `[VERIFY on Linux]` (pswitch item, rawactive types, vmstat types) but none block Phase 2

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story work begins

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Add PM_TYPE_U32, PM_TYPE_32, PM_TYPE_DOUBLE constants sourced from `cpmapi` to pmlogsynth/pcp_constants.py
- [X] T003 [P] Add `is_discrete: bool = False` field to MetricDescriptor dataclass in pmlogsynth/domains/base.py
- [X] T004 Rename pmlogsynth/domains/load.py to pmlogsynth/domains/system.py and rename class LoadMetricModel to SystemMetricModel
- [X] T005 Update pmlogsynth/writer.py and pmlogsynth/cli.py to import SystemMetricModel from domains/system instead of LoadMetricModel from domains/load
- [X] T006 Rename tests/unit/test_domain_load.py to tests/unit/test_domain_system.py and update all LoadMetricModel class references to SystemMetricModel

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 — pmstat View Works End-to-End (Priority: P1) 🎯 MVP

**Goal**: Generate a complete-example archive where `pmrep -c pmstat` exits 0 with all columns populated — no `unknown metric` errors, no dashes where numbers should appear

**Independent Test**: `pmlogsynth -o ./generated-archives/complete-example docs/complete-example.yml && pmrep -c pmstat -a ./generated-archives/complete-example` — exits 0, all columns numeric

### Tests for User Story 1 (write and confirm FAIL before implementing)

- [X] T007 [US1] Write failing unit tests for 6 CPU sub-metrics (carving invariant: user+nice+vuser+vnice+guest+guest_nice+sys+intr+idle+wait+steal == ncpu×interval×1000ms; individual slice values) and hinv.ncpu (discrete value equals hardware.cpus; falls back to 4 when hardware.cpus absent) in tests/unit/test_domain_cpu.py
- [X] T008 [P] [US1] Write failing unit tests for kernel.all.intr and kernel.all.pswitch derivations from utilization×rate×num_cpus×interval in tests/unit/test_domain_system.py
- [X] T009 [P] [US1] Write failing unit tests for 8 new memory metrics: active=used_kb×0.60, inactive=used_kb×0.25, slab=physmem_kb×0.04; swap.used/pagesin/pagesout are zero when used_ratio≤0.70 and non-zero above; pgpgin/pgpgout counter derivations in tests/unit/test_domain_memory.py
- [X] T010 [P] [US1] Write failing integration test asserting writer._write_discrete_sample() emits hinv.ncpu (is_discrete=True) exactly once before the per-sample loop in tests/integration/test_writer.py

### Implementation for User Story 1

- [X] T011 [US1] Add descriptors for kernel.all.cpu.nice, vuser, vnice, intr, guest, guest_nice (all PM_SEM_COUNTER, PM_TYPE_U64, UNITS_MSEC) and hinv.ncpu (PM_SEM_DISCRETE, PM_TYPE_U32, is_discrete=True) to pmlogsynth/domains/cpu.py; update compute() to carve sub-metrics from user/sys budgets using fractions from data-model.md (nice 2%, vuser 1.5%, vnice 0.5%, guest 1%, guest_nice 0.5% of user; intr 3% of sys)
- [X] T012 [P] [US1] Implement _write_discrete_sample() in pmlogsynth/writer.py — collect all is_discrete=True descriptors across all models, pmiPutValue each, call pmiWrite(0, 0) once; exclude discrete metrics from the per-sample loop
- [X] T013 [P] [US1] Add kernel.all.intr (U32, counter), kernel.all.pswitch (U32, counter), kernel.all.running (U32, instant), kernel.all.blocked (U32, instant) descriptors and derivations to pmlogsynth/domains/system.py using PM_TYPE_U32 from pcp_constants
- [X] T014 [P] [US1] Add 8 new memory metric descriptors (mem.util.active, mem.util.inactive, mem.util.slab, swap.used, swap.pagesin, swap.pagesout, mem.vmstat.pgpgin, mem.vmstat.pgpgout) and compute logic to pmlogsynth/domains/memory.py per derivation formulas in data-model.md; swap pressure threshold at used_ratio=0.70

**Checkpoint**: User Story 1 fully functional — `pmrep -c pmstat` exits 0 with all columns populated

---

## Phase 4: User Story 2 — vmstat View Works End-to-End (Priority: P2)

**Goal**: `pmrep -c vmstat`, `pmrep -c vmstat-a`, and `pmrep -c vmstat-d` all exit 0 with all columns populated against the same generated archive

**Independent Test**: `pmrep -c vmstat -a ./generated-archives/complete-example && pmrep -c vmstat-d -a ./generated-archives/complete-example` — both exit 0; per-device disk columns show non-zero values

### Tests for User Story 2 (write and confirm FAIL before implementing)

- [X] T015 [US2] Write failing unit tests for 10 new disk.dev.* metrics: read/write counter accumulation via sampler.accumulate; blkread/blkwrite sector derivation (bytes÷512); avg_qlen instant formula ((read_mbps+write_mbps)÷100); avactive counter; all values split by num_disks in tests/unit/test_domain_disk.py

### Implementation for User Story 2

- [X] T016 [US2] Add disk.dev.read, write, read_merge, write_merge, blkread, blkwrite, read_rawactive, write_rawactive, avactive (all U64 counters) and disk.dev.avg_qlen (PM_TYPE_DOUBLE, instant) descriptors and compute logic to pmlogsynth/domains/disk.py; all share existing _DISK_INDOM=(60,1) instance domain per contract clarification
- [X] T017 [P] [US2] Update tests/unit/test_list_metrics.py to assert all 29 new metric names appear in `--list-metrics` output (FR-005)

**Checkpoint**: User Stories 1 and 2 both independently functional

---

## Phase 5: User Story 3 — Spike Phases Produce Visible Fluctuations (Priority: P3)

**Goal**: The three phases in complete-example.yml (baseline→ramp→peak) produce visually distinct values across all pmrep columns — CPU columns ≥ 50% higher at peak than baseline (SC-003)

**Independent Test**: Replay archive with `pmrep -c pmstat` and confirm peak-phase rows have markedly higher usr/sys/intr/run values than baseline; `pmval -a ./generated-archives/complete-example swap.used` shows non-zero values in peak phase only

### Implementation for User Story 3

- [X] T018 [US3] Update docs/complete-example.yml: add memory stressor to all three phases (used_ratio 0.40 baseline, 0.65 ramp, 0.80 peak to trigger swap pressure at peak); add disk stressor to baseline and ramp phases (currently disk only in peak); add cache_ratio to baseline phase per Decision 7 in research.md
- [X] T019 [P] [US3] Write E2E tests for pmrep -c pmstat, pmrep -c vmstat, pmrep -c vmstat-a, pmrep -c vmstat-d against generated complete-example archive (exit 0, no `unknown metric` warnings, all view columns populated) in tests/e2e/test_pmrep_views.py behind existing PCP availability guard

**Checkpoint**: All three user stories functional — archive generates phase-visible, demo-ready data

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gate and final validation

- [ ] T020 Run ./pre-commit.sh and confirm all tiers green (ruff, mypy, unit tests, integration tests, E2E when PCP available) with zero regressions on any existing tests
- [ ] T021 [P] Validate generated archive against quickstart.md checklist: pmlogcheck exits 0; all four pmrep view commands exit 0; phase fluctuations visible via pmval for kernel.all.cpu.user, kernel.all.running, swap.used

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (PMIDs confirmed) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on Phase 2 and Phase 3 (disk additions independent; vmstat reuses CPU/memory metrics from US1)
- **US3 (Phase 5)**: Depends on Phase 3 (complete-example.yml fluctuations require all pmstat metrics present)
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no US2/US3 dependency
- **US2 (P2)**: Depends on US1 (vmstat CPU/memory columns require US1 metrics; disk columns are independent but tested together)
- **US3 (P3)**: Depends on US1 (profile fluctuations only meaningful once pmstat metrics emit correctly)

### Within User Story 1 (Phase 3)

```
T007 (cpu tests) ──────────────────► T011 (cpu impl)
T008 (system tests) ──────────────► T013 (system impl)   all T011-T014
T009 (memory tests) ──────────────► T014 (memory impl)   can run in
T010 (writer test)  ──────────────► T012 (writer impl)   parallel
```

### Parallel Opportunities

- T007, T008, T009, T010: all different files — run in parallel (test writing)
- T011, T012, T013, T014: all different files — run in parallel (implementation, after tests fail)
- T002 and T003: different files — run in parallel within Phase 2
- T005 and T006: different files — run in parallel within Phase 2

---

## Parallel Example: Phase 3 (User Story 1)

```bash
# Step 1: Write all tests in parallel (confirm each FAILS before moving on)
Task T007: CPU sub-metrics + hinv.ncpu tests → tests/unit/test_domain_cpu.py
Task T008: system scheduler tests           → tests/unit/test_domain_system.py
Task T009: memory new metrics tests         → tests/unit/test_domain_memory.py
Task T010: writer discrete pass test        → tests/integration/test_writer.py

# Step 2: Implement in parallel (tests now define the contract — make them pass)
Task T011: cpu.py sub-metrics + hinv.ncpu carving compute
Task T012: writer.py _write_discrete_sample()
Task T013: system.py intr/pswitch/running/blocked
Task T014: memory.py active/inactive/slab/swap.*/pgpg*
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Verify PMIDs on Linux CI
2. Phase 2: Foundation (CRITICAL — pcp_constants, base.py, rename load→system)
3. Phase 3: User Story 1 — pmstat works end-to-end
4. **STOP and VALIDATE**: `pmrep -c pmstat` exits 0, all columns populated
5. Ship the pmstat MVP

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → `pmrep -c pmstat` works → Demo/validate (MVP)
3. Phase 4 → `pmrep -c vmstat/vmstat-d` works → Demo/validate
4. Phase 5 → Spike phases visible → Archive ready for training/demo use
5. Phase 6 → Full quality gate passes → Feature complete

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same phase
- TDD is non-negotiable: write tests, run `pytest` to confirm FAIL, then implement
- `[VERIFY]` PMIDs in research.md must be confirmed on Linux before implementing each domain — a wrong PMID silently produces an unreadable archive (no Python error)
- `disk.dev.secactive` is NOT emitted by pmlogsynth — pmrep derives it as `instant(disk.dev.avactive)` automatically; do not add it
- Counter monotonicity is enforced by existing `sampler.accumulate()` (clamps ≥ 0) — no changes to ValueSampler needed
- Never delete existing tests; if a test breaks, diagnose and fix together
