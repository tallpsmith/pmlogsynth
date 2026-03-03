# Feature Specification: pmrep View Support

**Feature Branch**: `004-pmrep-view-support`
**Created**: 2026-03-03
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — pmstat View Works End-to-End (Priority: P1)

A developer generates a `complete-example` archive and immediately runs
`pmrep -c pmstat` against it. Every column in the pmstat table is populated
with believable values — no `unknown metric` errors, no dashes where numbers
should be.

**Why this priority**: This is the primary failure mode that motivated the
feature. A pmstat table with holes or error noise is useless for demo,
troubleshooting, or training scenarios.

**Independent Test**: Generate archive with `pmlogsynth -o ./generated-archives/complete-example docs/complete-example.yml`,
then run `pmrep -c pmstat -a ./generated-archives/complete-example`. All
columns must show numeric values.

**Acceptance Scenarios**:

1. **Given** a freshly generated `complete-example` archive, **When** the
   developer runs `pmrep -c pmstat -a generated-archives/complete-example`,
   **Then** the command exits 0 and every column (usr, sys, wait, idle, run,
   intr, swap, etc.) shows numeric values with no `unknown metric` warnings.

2. **Given** the same archive, **When** the developer scrolls through output
   across the baseline → ramp → peak phases, **Then** CPU-related columns
   visibly increase through the ramp and peak phases and recover afterward.

---

### User Story 2 — vmstat View Works End-to-End (Priority: P2)

A developer runs `pmrep -c vmstat` (and `pmrep -c vmstat-d`) against the
same generated archive and sees meaningful memory, swap, disk, and CPU data.

**Why this priority**: vmstat columns exercise memory and disk metrics that
pmstat doesn't touch. Getting them populated validates that the new metric
domains are consistent and complete.

**Independent Test**: Run `pmrep -c vmstat -a ./generated-archives/complete-example`
and `pmrep -c vmstat-d -a ...`. Both must exit 0 with all columns populated.

**Acceptance Scenarios**:

1. **Given** a generated archive, **When** `pmrep -c vmstat` is run,
   **Then** all vmstat columns (memory, swap, I/O, CPU blocks) are populated.

2. **Given** a generated archive, **When** `pmrep -c vmstat-d` is run,
   **Then** per-device disk columns (reads, writes, merged, active time) show
   non-zero values.

---

### User Story 3 — Spike Phases Produce Visible Fluctuations (Priority: P3)

The three phases defined in `complete-example.yml` (baseline → ramp → peak)
produce visually distinct values across all pmrep columns, making the CPU
spike and recovery immediately obvious to anyone reviewing a pmrep replay.

**Why this priority**: Zero-filled columns or flat lines make the archive
useless for demo and training. The fluctuation is the whole point of
"complete-example".

**Independent Test**: Replay archive with `pmrep -c pmstat` and visually
inspect that peak-phase rows have markedly higher usr/sys/intr/run values
than baseline rows.

**Acceptance Scenarios**:

1. **Given** a generated archive, **When** peak-phase samples are compared to
   baseline, **Then** `kernel.all.cpu.user` + `kernel.all.cpu.sys` ≥ 2× their
   baseline values.

2. **Given** a generated archive, **When** peak-phase samples are compared to
   baseline, **Then** `kernel.all.intr`, `kernel.all.pswitch`, and
   `kernel.all.running` are visibly higher than baseline.

---

### Edge Cases

- What happens when `hardware.cpus` is not set in the profile? `hinv.ncpu`
  must fall back to a sensible default (e.g., 4) rather than crashing.
- How does the system handle swap metrics when no swap stressor is configured?
  `swap.pagesin/out` must emit zero (not absent) so pmrep doesn't report
  `unknown metric`.
- What happens with disk metrics when only one device is configured in the
  profile? Per-device counters must still emit cleanly for a single device.

---

## Clarifications

### Session 2026-03-03

- Q: How should `hinv.ncpu` (PM_SEM_DISCRETE) be emitted without being written every sample interval? → A: Add `is_discrete: bool` flag to `MetricDescriptor`. Writer emits all discrete metrics once at archive open via a one-shot pass, then excludes them from the per-sample loop entirely.

- Q: How should `swap.used` / `swap.pagesin` / `swap.pagesout` determine the total swap pool size when no swap stressor exists in the profile? → A: Derive `swap_total = hardware.memory × 1.0` (swap equals RAM, matching common Linux convention). No new profile field required. `swap.used` scales with memory `used_ratio`, non-zero only when `used_ratio > 0.7`.

- Q: Should kernel scheduler metrics (`kernel.all.intr`, `pswitch`, `running`, `blocked`) live in `load.py` or a new `system.py`? → A: Rename `load.py` to `system.py` and extend it in-place. All load-average and kernel scheduler metrics are logically cohesive and must behave together.

- Q: Do new `disk.dev.*` metrics share the existing per-device instance domain already established by `disk.dev.read_bytes`/`write_bytes`? → A: Yes — all disk.dev.* metrics share a single instance domain registered at domain level; new metrics inherit it automatically with no duplicate registration needed.

- Q: How should new `kernel.all.cpu.*` sub-metrics (nice, vuser, vnice, intr, guest, guest_nice) be populated without breaking the 100% time-budget invariant? → A: Carve from parent buckets (nice/vuser/vnice/guest/guest_nice from `user`; intr from `sys`), keeping total CPU time constant. Default slicer allocations must be small (natural system noise level) so these esoteric sub-metrics don't dominate the parent bucket.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: pmlogsynth MUST emit all metrics consumed by the `[pmstat]`
  section of `/etc/pcp/pmrep/pmstat.conf` (see metric list below).

- **FR-002**: pmlogsynth MUST emit all metrics consumed by the `[vmstat]`
  and `[vmstat-d]` sections of `/etc/pcp/pmrep/vmstat.conf`.

- **FR-003**: `docs/complete-example.yml` MUST be updated so stressor values
  across its three phases drive visible, non-zero fluctuations in every pmrep
  column.

- **FR-004**: All new metrics MUST follow existing counter/instant semantics
  and noise model (counters clamped ≥ 0 per-delta, instants may float).

- **FR-008**: The six CPU sub-metrics (`kernel.all.cpu.nice`, `vuser`, `vnice`,
  `intr`, `guest`, `guest_nice`) MUST be carved from their parent bucket so
  the total CPU time budget remains constant (sums to 100% × ncpu × interval).
  `nice`, `vuser`, `vnice`, `guest`, `guest_nice` are sliced from `user`;
  `intr` is sliced from `sys`. Default slice fractions MUST be small (≤ 3% of
  parent each) to represent ambient system noise, not dominant workload.
  Stressor config MAY override these fractions.

- **FR-005**: `--list-metrics` MUST reflect all newly added metrics.

- **FR-006**: `MetricDescriptor` MUST support an `is_discrete` boolean flag.
  The writer MUST emit all discrete metrics once at archive open via a dedicated
  one-shot pass, then exclude them from the per-sample loop. `hinv.ncpu` is the
  first consumer of this flag; the mechanism generalises to any future `hinv.*`
  metric automatically.

- **FR-007**: Swap pool size MUST be derived as `swap_total = hardware.memory × 1.0`
  (swap equals RAM, matching common Linux convention). No new profile field is
  required. `swap.used` scales with memory `used_ratio`; `swap.pagesin` and
  `swap.pagesout` MUST be zero when `used_ratio` ≤ 0.7 and non-zero only under
  memory pressure.

### Metrics to Implement

**cpu.py additions:**
- `kernel.all.cpu.nice` — time in nice-priority userspace
- `kernel.all.cpu.vuser` — time in virtual-machine user mode
- `kernel.all.cpu.vnice` — time in virtual-machine nice mode
- `kernel.all.cpu.intr` — time servicing interrupts
- `kernel.all.cpu.guest` — time in guest virtual machine
- `kernel.all.cpu.guest_nice` — time in guest-nice virtual machine
- `hinv.ncpu` — hardware CPU count (discrete)

**`system.py` (rename from `load.py`, extended in-place):**

`load.py` is renamed to `system.py`. Existing load-average metrics remain unchanged.
The following scheduler/interrupt metrics are added to the same domain — they are
logically cohesive with load and must behave consistently together (e.g., high
`kernel.all.running` correlates with high load averages).

- `kernel.all.intr` — interrupt rate counter
- `kernel.all.pswitch` — context-switch counter
- `kernel.all.running` — runqueue depth (instant)
- `kernel.all.blocked` — blocked processes (instant)

**memory.py additions:**
- `mem.util.active` — active memory pages
- `mem.util.inactive` — inactive memory pages
- `mem.util.slab` — kernel slab cache
- `swap.used` — bytes of swap in use
- `swap.pagesin` — pages swapped in (counter)
- `swap.pagesout` — pages swapped out (counter)
- `mem.vmstat.pgpgin` — pages paged in (counter)
- `mem.vmstat.pgpgout` — pages paged out (counter)

**disk.py additions (per-device, shared instance domain):**

All new `disk.dev.*` metrics share the single per-device instance domain already
established by `disk.dev.read_bytes` / `disk.dev.write_bytes`. Device instances
are drawn from the profile's `hardware.devices` list. No additional instance
domain registration is required for new metrics.

- `disk.dev.read` — read operations count (IOPS counter)
- `disk.dev.write` — write operations count (IOPS counter)
- `disk.dev.read_merge` — merged read requests (counter)
- `disk.dev.write_merge` — merged write requests (counter)
- `disk.dev.blkread` — 512-byte sectors read (counter)
- `disk.dev.blkwrite` — 512-byte sectors written (counter)
- `disk.dev.read_rawactive` — milliseconds spent reading (counter)
- `disk.dev.write_rawactive` — milliseconds spent writing (counter)
- `disk.dev.avg_qlen` — average queue length (instant)
- `disk.dev.avactive` — average active time (instant)
- `disk.dev.secactive` — seconds device was active (counter)

### Key Entities

- **MetricDescriptor**: existing abstraction in `domains/base.py` — each new
  metric needs a descriptor registered in the domain's `metrics()` list.
- **ValueSampler**: existing counter-accumulation logic in `sampler.py` — new
  counter metrics plug into the same accumulator map.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pmrep -c pmstat -a generated-archives/complete-example` exits 0
  with no `unknown metric` errors and all columns showing numeric values.

- **SC-002**: `pmrep -c vmstat -a generated-archives/complete-example` exits 0,
  all columns populated including disk columns from `vmstat-d` section.

- **SC-003**: Peak-phase values for CPU-related pmstat columns are visibly
  (≥ 50%) higher than baseline-phase values in the same archive.

- **SC-004**: All existing tests remain green (`./pre-commit.sh` passes with no
  regressions); new unit tests cover every new metric's `compute()` logic.
