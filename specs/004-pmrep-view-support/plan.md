# Implementation Plan: pmrep View Support

**Branch**: `004-pmrep-view-support` | **Date**: 2026-03-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-pmrep-view-support/spec.md`

---

## Summary

Add the 29 metrics required by `pmrep -c pmstat`, `pmrep -c vmstat`, `pmrep -c vmstat-a`, and `pmrep -c vmstat-d` so that a generated `complete-example` archive produces fully-populated tables with no `unknown metric` errors. Metrics are added to existing domain models (`cpu.py`, `memory.py`, `disk.py`) and to `system.py` (renamed from `load.py`). A new `is_discrete` flag on `MetricDescriptor` drives a one-shot writer pass for `hinv.ncpu`.

---

## Technical Context

**Language/Version**: Python 3.8+
**Primary Dependencies**: `pcp.pmi` (system package `python3-pcp`), PyYAML
**Storage**: PCP v3 binary archive files
**Testing**: pytest; `unittest.mock` for Tier 2 PCP stubs
**Target Platform**: Linux (Tier 3 E2E); macOS (Tier 1/2 only)
**Project Type**: CLI tool / archive generator
**Performance Goals**: N/A — offline archive generation, not real-time
**Constraints**: No NumPy; Python 3.8 syntax; no running pmcd
**Scale/Scope**: 29 new metrics across 4 domain files + writer change

---

## Constitution Check

*Gate: must pass before implementation. All six principles evaluated.*

### I. PCP Archive Fidelity — ✅ PASS

All new metrics use real PCP metric names and PMIDs verified against the installed PMDA. PMID item numbers marked `[VERIFY]` in `research.md` must be confirmed via `pminfo -d` on Linux CI before coding each metric. The writer's discrete pass emits `hinv.ncpu` exactly once, matching `PM_SEM_DISCRETE` semantics. Counter invariants are preserved (sampler.accumulate clamps ≥ 0). CPU time-budget invariant is explicitly maintained via sub-metric carving (FR-008).

### II. Layered Testing — ✅ PASS (with commitment)

Every new metric's `compute()` logic gets a Tier 1 unit test. Integration (Tier 2) writer tests verify discrete-pass invocation. E2E tests (Tier 3) verify `pmrep -c pmstat` and `pmrep -c vmstat` exit 0. No existing tests are deleted.

### III. Declarative Profile-First — ✅ PASS

No new profile schema fields. Stressor defaults applied at compute time. Swap pool (`swap_total = hardware.memory_kb`) derived without a new profile field (FR-007). CPU sub-metric slice fractions are hardcoded constants — not configurable in this feature.

### IV. Phase-Aware Extensibility — ✅ PASS

No changes to `ProfileLoader`, `ValueSampler` API, CLI subparser structure, or the `fleet`-reserved command path. The `MetricDescriptor.is_discrete` field defaults to `False` — backward compatible. Renaming `load.py` → `system.py` is internal; the writer import is the only external reference.

### V. Minimal External Dependencies — ✅ PASS

No new pip dependencies. New PCP type constants (`PM_TYPE_U32`, `PM_TYPE_32`, `PM_TYPE_DOUBLE`) are sourced from `cpmapi` — already a hard dependency.

### VI. CI-First Quality Gates — ✅ PASS

All new tests go in `tests/unit/` and `tests/integration/`. Pre-commit.sh and CI workflow are unchanged in structure; they automatically pick up new test files. E2E test for pmrep validation goes in `tests/e2e/` behind the existing PCP availability guard.

---

## Project Structure

### Documentation (this feature)

```text
specs/004-pmrep-view-support/
├── plan.md              # This file
├── research.md          # PMID values, design decisions
├── data-model.md        # Entity changes and metric derivations
├── quickstart.md        # How to generate and validate the archive
├── contracts/
│   └── metric-inventory.md   # pmrep view → required metric mapping
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code Changes

```text
pmlogsynth/
├── pcp_constants.py        # ADD: PM_TYPE_U32, PM_TYPE_32, PM_TYPE_DOUBLE
├── domains/
│   ├── base.py             # ADD: is_discrete field to MetricDescriptor
│   ├── cpu.py              # ADD: 6 sub-metrics + hinv.ncpu (discrete)
│   ├── system.py           # RENAME from load.py; ADD: intr, pswitch, running, blocked
│   ├── memory.py           # ADD: active, inactive, slab, swap.*, mem.vmstat.pg*
│   └── disk.py             # ADD: 10 per-device metrics
├── writer.py               # ADD: discrete pass; IMPORT SystemMetricModel
└── cli.py                  # UPDATE: import SystemMetricModel

docs/
└── complete-example.yml    # UPDATE: memory stressors + disk stressors across phases

tests/
├── unit/
│   ├── test_domain_cpu.py      # ADD: tests for 6 sub-metrics, hinv.ncpu, carving invariant
│   ├── test_domain_system.py   # RENAME from test_domain_load.py; ADD: 4 new metrics
│   ├── test_domain_memory.py   # ADD: tests for 8 new metrics, swap formula, slab
│   ├── test_domain_disk.py     # ADD: tests for 10 new per-device metrics
│   └── test_list_metrics.py    # UPDATE: assert new metrics present in --list-metrics
├── integration/
│   └── test_writer.py          # ADD: test discrete pass writes hinv.ncpu before sample loop
└── e2e/
    └── test_pmrep_views.py     # NEW: pmrep -c pmstat/vmstat/vmstat-d exit 0, no unknowns
```

**Structure Decision**: Single project layout, unchanged from existing structure. `system.py` is a rename of `load.py` with in-place extension.

---

## Complexity Tracking

No constitution violations in this plan.

---

## Implementation Phases

### Phase A: Foundation changes (unblock everything else)

1. **`pcp_constants.py`**: add `PM_TYPE_U32`, `PM_TYPE_32`, `PM_TYPE_DOUBLE`.
2. **`domains/base.py`**: add `is_discrete: bool = False` to `MetricDescriptor`.
3. **`domains/load.py` → `domains/system.py`**: rename file, rename class to `SystemMetricModel`, update all imports (`writer.py`, `cli.py`).
4. **Tests first**: update `tests/unit/test_domain_load.py` → `test_domain_system.py`; confirm all existing load tests still pass under new name.

### Phase B: CPU sub-metrics + hinv.ncpu

5. **`domains/cpu.py`**: add 6 sub-metric descriptors + `hinv.ncpu` descriptor. Update `compute()` to carve sub-metrics from parent buckets.
6. **`writer.py`**: implement `_write_discrete_sample()` — collect `is_discrete=True` descriptors, emit via `pmiPutValue`, call `pmiWrite(0, 0)`.
7. **Tests first**: unit tests for CPU carving invariant, sub-metric values, hinv.ncpu value = hardware.cpus. Integration test for discrete pass.

### Phase C: System metrics

8. **`domains/system.py`**: add `kernel.all.intr`, `kernel.all.pswitch`, `kernel.all.running`, `kernel.all.blocked` to `SystemMetricModel`.
9. **Tests first**: unit tests for scheduler metric derivations from utilization.

### Phase D: Memory metrics

10. **`domains/memory.py`**: add 8 new metrics (active, inactive, slab, swap.*, pgpgin, pgpgout).
11. **Tests first**: unit tests for swap formula (zero below 0.7, non-zero above), slab fraction, active/inactive fractions, pgpg* derivation.

### Phase E: Disk per-device metrics

12. **`domains/disk.py`**: add 10 per-device metrics to `metric_descriptors()` and `compute()`.
13. **Tests first**: unit tests for new per-device metrics — counter accumulation, sector derivation, avg_qlen instant, avactive counter.

### Phase F: Profile + E2E validation

14. **`docs/complete-example.yml`**: add `memory` stressor to all phases with `used_ratio` progression (0.40 → 0.65 → 0.80). Add `disk` stressor to baseline and ramp phases (currently only in peak). Update `README.md` inline YAML if it matches spike.yml (it does — no change needed there).
15. **`tests/e2e/test_pmrep_views.py`**: new E2E tests for `pmrep -c pmstat/vmstat/vmstat-a/vmstat-d`.
16. **`tests/unit/test_list_metrics.py`**: verify all 29 new metric names appear in `--list-metrics` output.

### Phase G: Gate

17. **`./pre-commit.sh`**: full green run. All tiers pass.

---

## Key Invariants to Enforce in Tests

1. **CPU time budget**: `user_emitted + nice + vuser + vnice + guest + guest_nice + sys_emitted + intr + idle + wait + steal == num_cpus × interval × 1000 ms`
2. **Memory constraint**: `used + free == physmem` (unchanged from existing)
3. **Swap zero below threshold**: `swap.used == 0` when `used_ratio ≤ 0.70`
4. **Counter monotonicity**: all counter metrics increase or stay flat across ticks (never decrease)
5. **hinv.ncpu == hardware.cpus**: discrete value matches hardware profile
6. **Per-device totals**: `sum(disk.dev.read_bytes across devices) == disk.all.read_bytes` (approx, given noise)

---

## PMID Verification Step

Before implementing each domain's new metrics on Linux CI, run:
```bash
pminfo -d <metric names from research.md [VERIFY] list>
```
If any PMID differs from the plan, update `research.md` and the corresponding domain file before committing. A PMID mismatch won't cause a Python error but will produce an invalid archive that pmrep can't read.
