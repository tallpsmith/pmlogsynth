# Requirements Checklist — 004-pmrep-view-support

## Spec Quality

- [x] Feature branch matches spec directory name (`004-pmrep-view-support`)
- [x] All user stories have acceptance scenarios in Given/When/Then form
- [x] Each user story is independently testable
- [x] Priorities assigned (P1 → P3)
- [x] Edge cases documented
- [x] Every functional requirement is unambiguous and verifiable
- [x] `NEEDS CLARIFICATION` tags — none outstanding
- [x] Success criteria are measurable (exit codes, column population, %)

## Metric Coverage

- [ ] `kernel.all.cpu.nice` descriptor added to `cpu.py`
- [ ] `kernel.all.cpu.vuser` descriptor added to `cpu.py`
- [ ] `kernel.all.cpu.vnice` descriptor added to `cpu.py`
- [ ] `kernel.all.cpu.intr` descriptor added to `cpu.py`
- [ ] `kernel.all.cpu.guest` descriptor added to `cpu.py`
- [ ] `kernel.all.cpu.guest_nice` descriptor added to `cpu.py`
- [ ] `hinv.ncpu` descriptor added with `PM_SEM_DISCRETE` semantics
- [ ] `kernel.all.intr` counter implemented
- [ ] `kernel.all.pswitch` counter implemented
- [ ] `kernel.all.running` instant implemented
- [ ] `kernel.all.blocked` instant implemented
- [ ] `mem.util.active` instant implemented
- [ ] `mem.util.inactive` instant implemented
- [ ] `mem.util.slab` instant implemented
- [ ] `swap.used` instant implemented
- [ ] `swap.pagesin` counter implemented (zero when used_ratio ≤ 0.7)
- [ ] `swap.pagesout` counter implemented (zero when used_ratio ≤ 0.7)
- [ ] `mem.vmstat.pgpgin` counter implemented
- [ ] `mem.vmstat.pgpgout` counter implemented
- [ ] `disk.dev.read` IOPS counter implemented
- [ ] `disk.dev.write` IOPS counter implemented
- [ ] `disk.dev.read_merge` counter implemented
- [ ] `disk.dev.write_merge` counter implemented
- [ ] `disk.dev.blkread` counter implemented
- [ ] `disk.dev.blkwrite` counter implemented
- [ ] `disk.dev.read_rawactive` counter implemented
- [ ] `disk.dev.write_rawactive` counter implemented
- [ ] `disk.dev.avg_qlen` instant implemented
- [ ] `disk.dev.avactive` instant implemented
- [ ] `disk.dev.secactive` counter implemented

## Semantics & Invariants

- [ ] Counter deltas clamped ≥ 0 for all new counters
- [ ] `hinv.ncpu` written once (discrete), not every sample
- [ ] `swap.pagesin/out` emit 0 (not absent) when no memory pressure
- [ ] `--list-metrics` output includes all new metrics
- [ ] All new metrics use `pcp_constants` (not `cpmapi` directly)

## Profile (`docs/complete-example.yml`)

- [ ] Baseline phase produces low but non-zero values for all new metrics
- [ ] Ramp and peak phases produce visibly higher values for CPU/disk columns
- [ ] Swap stressor configured to trigger `swap.pagesin/out` in peak phase
- [ ] Profile validates cleanly with `pmlogsynth --validate`

## Tests (TDD — must precede implementation)

- [ ] Failing unit test written for each new cpu.py metric before code
- [ ] Failing unit test written for kernel system metrics before code
- [ ] Failing unit test written for each new memory metric before code
- [ ] Failing unit test written for each new disk metric before code
- [ ] All new unit tests live in `tests/unit/`
- [ ] No existing tests deleted or weakened

## Integration & CI

- [ ] `./pre-commit.sh` passes green (lint + types + unit + integration)
- [ ] `ruff check .` — no new warnings
- [ ] `mypy pmlogsynth/` — no new type errors
- [ ] SC-001 verified manually: `pmrep -c pmstat` exits 0, no unknown metrics
- [ ] SC-002 verified manually: `pmrep -c vmstat` exits 0, all columns populated
- [ ] SC-003 verified manually: peak values ≥ 50% higher than baseline for CPU cols
