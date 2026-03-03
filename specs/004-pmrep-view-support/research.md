# Research: pmrep View Support

**Feature**: 004-pmrep-view-support
**Phase**: 0 — all NEEDS CLARIFICATION items resolved

---

## Decision 1: PMID values for new metrics

**Decision**: Use Linux PMDA (domain 60) and memory PMDA (domain 58) PMIDs consistent with the existing codebase. PMID item numbers below are verified from the PCP linux PMDA source (`src/pmdas/linux/pmda.c` on GitHub) and cross-checked where possible.

**Key constraint**: For pmlogsynth-generated archives, PMIDs only need to be *unique within the archive* — pmrep reads archives by metric name and uses the archive's own PMNS. The PMID does not need to match the live PMDA. The existing code already uses domain 58 for `mem.util.*` (real PMDA uses domain 60) and cluster 5 for `disk.dev.*` (real PMDA uses cluster 0 = CLUSTER_STAT), and these work fine. New metrics follow the same internal conventions to avoid conflicts.

**Rationale for hardcoding**: `pmLookupName()` at runtime requires a running `pmcd` — rejected (Constitution V).

### cpu.py new metrics (domain 60, cluster 0)

All in CLUSTER_STAT (0), same as existing kernel.all.cpu.user/sys/idle. Item numbers verified from PCP source.

| Metric | PMID | Type | Sem | Units | Notes |
|--------|------|------|-----|-------|-------|
| `kernel.all.cpu.nice` | (60, 0, 27) | U64 | counter | UNITS_MSEC | Item 27 confirmed consistent with existing (idle=21, user=20, sys=22) |
| `kernel.all.cpu.vuser` | (60, 0, 78) | U64 | counter | UNITS_MSEC | Verified from PCP source (was 56 — wrong) |
| `kernel.all.cpu.vnice` | (60, 0, 82) | U64 | counter | UNITS_MSEC | Verified from PCP source (was 57 — wrong) |
| `kernel.all.cpu.intr` | (60, 0, 34) | U64 | counter | UNITS_MSEC | Verified from PCP source (was 55 — wrong) |
| `kernel.all.cpu.guest` | (60, 0, 60) | U64 | counter | UNITS_MSEC | Verified from PCP source (was 59 — wrong) |
| `kernel.all.cpu.guest_nice` | (60, 0, 81) | U64 | counter | UNITS_MSEC | Verified from PCP source (was 60 — conflicted with guest) |
| `hinv.ncpu` | (60, 0, 32) | U32 | discrete | UNITS_NONE | Verified from PCP source (was 1 — wrong); is_discrete=True |

> Linux verification: `pminfo -d kernel.all.cpu.vuser kernel.all.cpu.vnice kernel.all.cpu.intr kernel.all.cpu.guest kernel.all.cpu.guest_nice hinv.ncpu kernel.all.cpu.nice`

### system.py new metrics (domain 60, cluster 0)

All in CLUSTER_STAT (0). Item numbers verified from PCP source.

| Metric | PMID | Type | Sem | Units | Notes |
|--------|------|------|-----|-------|-------|
| `kernel.all.intr` | (60, 0, 12) | U32 | counter | UNITS_COUNT | Verified from PCP source (was 3 — wrong) |
| `kernel.all.pswitch` | (60, 0, 7) | U32 | counter | UNITS_COUNT | `[VERIFY on Linux]` — sources conflict (7 vs 13) |
| `kernel.all.running` | (60, 0, 15) | U32 | instant | UNITS_COUNT | Verified from PCP source (was 32 — conflicted with hinv.ncpu) |
| `kernel.all.blocked` | (60, 0, 16) | U32 | instant | UNITS_COUNT | Verified from PCP source (was 33 — wrong) |

> Linux verification: `pminfo -md kernel.all.intr kernel.all.pswitch kernel.all.running kernel.all.blocked`

### memory.py new metrics (domain 58, cluster 0 — consistent with existing memory.py)

Existing memory.py uses domain 58 cluster 0 for mem.util.*. New metrics follow the same convention. Items chosen to avoid conflicts with existing: {0, 2, 4, 6, 13} are taken.

| Metric | PMID | Type | Sem | Units | Notes |
|--------|------|------|-----|-------|-------|
| `mem.util.active` | (58, 0, 15) | U64 | instant | UNITS_KBYTE | No conflict with existing items |
| `mem.util.inactive` | (58, 0, 16) | U64 | instant | UNITS_KBYTE | No conflict |
| `mem.util.slab` | (58, 0, 12) | U64 | instant | UNITS_KBYTE | No conflict |
| `swap.used` | (58, 1, 0) | U64 | instant | UNITS_KBYTE | Cluster 1 = new swap cluster; type confirmed via `pminfo` |
| `swap.pagesin` | (58, 1, 1) | PM_TYPE_32 | counter | UNITS_COUNT | Type confirmed: "32-bit int" via `pminfo` |
| `swap.pagesout` | (58, 1, 2) | PM_TYPE_32 | counter | UNITS_COUNT | Type confirmed: "32-bit int" via `pminfo` |
| `mem.vmstat.pgpgin` | (58, 2, 0) | U32 | counter | UNITS_COUNT | Cluster 2 = new vmstat cluster; `[VERIFY type on Linux]` |
| `mem.vmstat.pgpgout` | (58, 2, 1) | U32 | counter | UNITS_COUNT | `[VERIFY type on Linux]` |

> Linux verification: `pminfo -md mem.util.slab swap.used swap.pagesin swap.pagesout mem.vmstat.pgpgin mem.vmstat.pgpgout`

### disk.py new metrics (domain 60, cluster 5; indom (60, 1) — consistent with existing disk.py)

Existing disk.py uses cluster 5 for `disk.dev.*`. New metrics extend this cluster. Items chosen to avoid conflicts with existing disk.dev.read_bytes (item 5) and disk.dev.write_bytes (item 6).

`disk.dev.secactive` is a **derived** metric computed by pmrep via `instant(disk.dev.avactive)` — we do NOT need to emit it directly. Only `disk.dev.avactive` is required.

| Metric | PMID | Type | Sem | Units | Notes |
|--------|------|------|-----|-------|-------|
| `disk.dev.read` | (60, 5, 0) | U64 | counter | UNITS_COUNT | Item 0 — no conflict |
| `disk.dev.write` | (60, 5, 1) | U64 | counter | UNITS_COUNT | Item 1 — no conflict |
| `disk.dev.read_merge` | (60, 5, 2) | U64 | counter | UNITS_COUNT | Item 2 — no conflict |
| `disk.dev.write_merge` | (60, 5, 3) | U64 | counter | UNITS_COUNT | Item 3 — no conflict |
| `disk.dev.blkread` | (60, 5, 7) | U64 | counter | UNITS_COUNT | Item 7 — avoids existing items 5, 6 |
| `disk.dev.blkwrite` | (60, 5, 8) | U64 | counter | UNITS_COUNT | Item 8 |
| `disk.dev.read_rawactive` | (60, 5, 9) | U64 | counter | UNITS_MSEC | Item 9 — `[VERIFY type on Linux]` |
| `disk.dev.write_rawactive` | (60, 5, 10) | U64 | counter | UNITS_MSEC | Item 10 — `[VERIFY type on Linux]` |
| `disk.dev.avg_qlen` | (60, 5, 11) | DOUBLE | instant | UNITS_NONE | Item 11 — type confirmed via `pminfo` |
| `disk.dev.avactive` | (60, 5, 12) | U64 | counter | UNITS_MSEC | Item 12 — `[VERIFY type on Linux]` |

> Linux verification: `pminfo -md disk.dev.read disk.dev.write disk.dev.read_merge disk.dev.write_merge disk.dev.blkread disk.dev.blkwrite disk.dev.read_rawactive disk.dev.write_rawactive disk.dev.avg_qlen disk.dev.avactive`

---

## Decision 2: `MetricDescriptor.is_discrete` flag

**Decision**: Add `is_discrete: bool = False` to the `MetricDescriptor` dataclass. The writer performs a dedicated one-shot pass immediately after archive open: collect all descriptors where `is_discrete=True`, call `pmiPutValue` for each, then `pmiWrite(0, 0)` to commit them as the first record at t=0. Discrete metrics are then excluded from the per-sample loop.

**Rationale**: `hinv.ncpu` has `PM_SEM_DISCRETE` semantics — it represents a hardware property that doesn't change. PCP archives should include it once, not once per sample. pmrep's CPU percentage formulae (`100 * ... / hinv.ncpu`) require it to be present in the archive to compute column values.

**Alternatives considered**: Emitting `hinv.ncpu` every sample like an instant metric. Rejected: semantically wrong (SEM_DISCRETE means "value doesn't change across samples"); pmlogcheck may warn on it; and it wastes archive space.

---

## Decision 3: CPU sub-metric carving (FR-008)

**Decision**: Carve sub-metrics from their parent bucket so the CPU time budget remains constant. Hardcoded default slice fractions (no new `CpuStressor` fields needed):

| Sub-metric | Carved from | Default fraction |
|------------|-------------|-----------------|
| `cpu.nice` | `user` | 2% |
| `cpu.vuser` | `user` | 1.5% |
| `cpu.vnice` | `user` | 0.5% |
| `cpu.guest` | `user` | 1% |
| `cpu.guest_nice` | `user` | 0.5% |
| `cpu.intr` | `sys` | 3% |

The emitted `kernel.all.cpu.user` value is reduced by the sum of all user-carve sub-metrics. The emitted `kernel.all.cpu.sys` value is reduced by the `intr` carve. This preserves `user + sys + idle + wait + steal = total_ticks`.

**Rationale**: FR-008 requires total CPU time budget to be constant. These are ambient noise-level metrics (≤3% of parent), not dominant workload signals. Adding `CpuStressor` fields to make them configurable would be premature — the spec says "Stressor config MAY override" but provides no field names, and no user story requires tuning them.

**Alternatives considered**: Adding `nice_fraction`, `vuser_fraction`, etc. to `CpuStressor`. Deferred per over-engineering policy — can be added in a future feature if needed.

---

## Decision 4: Swap pool derivation (FR-007)

**Decision**: `swap_total_kb = hardware.memory_kb` (swap equals RAM). No new profile field.

- `swap.used`: scales with memory pressure only above 70% used_ratio.
  `pressure = max(0.0, (used_ratio - 0.7) / 0.3)` → `swap_used_kb = int(swap_total_kb * pressure * 0.5)`
- `swap.pagesin`, `swap.pagesout`: zero when `used_ratio ≤ 0.7`; small counts when under pressure.
- Counter deltas through `sampler.accumulate()`.

**Rationale**: Matches common Linux convention. Avoids a new profile field (Constitution III — schema frozen post-Phase 1). The 70% threshold and 0.5 max-fraction are tuning choices that keep swap.used at believable levels without consuming all swap.

---

## Decision 5: `system.py` replaces `load.py`

**Decision**: Rename `pmlogsynth/domains/load.py` → `pmlogsynth/domains/system.py`. Rename `LoadMetricModel` → `SystemMetricModel`. Add four scheduler/interrupt metrics to the same class. Update all imports in `writer.py`, `cli.py`, and tests.

**Rationale**: Load averages and kernel scheduler metrics are logically cohesive — both derived from CPU utilization, both need to move together for consistent phase behavior. One model = one file = one import chain.

**Alternatives considered**: A separate `scheduler.py` domain. Rejected: adds a new domain model for just four metrics that are directly derived from the same `CpuStressor` input as load averages.

---

## Decision 6: New PCP type constants needed

**Decision**: Add to `pcp_constants.py`:
- `PM_TYPE_U32 = _c.PM_TYPE_U32` — for `hinv.ncpu`
- `PM_TYPE_32 = _c.PM_TYPE_32` — for `swap.pagesin`, `swap.pagesout` (32-bit signed int per pminfo)
- `PM_TYPE_DOUBLE = _c.PM_TYPE_DOUBLE` — for `disk.dev.avg_qlen`

**Rationale**: The existing constants only cover U64 and FLOAT. Three new metrics require types not yet in the constants file. Centralising them maintains the single-source-of-truth pattern (Constitution I).

---

## Decision 7: `complete-example.yml` updates (FR-003)

**Decision**: Update `complete-example.yml` to drive non-zero values across all new metric columns:
- Add `memory.used_ratio` progression: baseline 0.40 → ramp 0.65 → peak 0.80 (crosses 0.70 threshold at peak, triggering swap pressure).
- Add `memory.cache_ratio` to baseline phase for stable cached/slab values.
- Ensure disk stressor exists in all three phases (currently only peak has it).
- Add `memory` stressor to ramp and peak phases to drive `mem.vmstat.pg*` paging activity.

**Rationale**: SC-003 requires peak-phase values ≥ 50% higher than baseline for CPU columns. The spec calls out explicit phase-visibility for all pmrep columns. The existing `complete-example.yml` has no memory stressor in ramp/peak and no disk stressor in baseline/ramp — columns would be zeros or dashes.
