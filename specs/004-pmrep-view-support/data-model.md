# Data Model: pmrep View Support

**Feature**: 004-pmrep-view-support

---

## Modified Entities

### `MetricDescriptor` (`domains/base.py`)

Adds one boolean field to support discrete one-shot emission (FR-006).

```python
@dataclass
class MetricDescriptor:
    name: str
    pmid: Tuple[int, int, int]
    type_code: int
    indom: Optional[Tuple[int, int]]
    sem: int
    units: Tuple[int, int, int, int, int, int]
    is_discrete: bool = False          # NEW — emit once at archive open, skip per-sample
```

**Invariant**: A metric descriptor with `is_discrete=True` MUST have `sem == PM_SEM_DISCRETE`. The writer enforces this by construction (only the writer decides when to emit discrete metrics).

---

### `CpuMetricModel` (`domains/cpu.py`)

Six new `kernel.all.cpu.*` sub-metrics added. `hinv.ncpu` added as the first discrete metric.

**Sub-metric carving invariant**: The total CPU time budget is preserved at every sample:
```
user_emitted + nice + vuser + vnice + guest + guest_nice
    + sys_emitted + intr
    + idle + wait + steal
    == num_cpus × interval × 1000  (milliseconds)
```

New compute logic:
1. Compute `user_ms` and `sys_ms` as before (from `utilization × ratios`).
2. Compute sub-metric slices from parent budgets using hardcoded fractions.
3. Reduce `user_ms` and `sys_ms` by their respective carved amounts.
4. Emit all metrics including the carved-down parent values.

New descriptors (all `PM_SEM_COUNTER`, `UNITS_MSEC`, `PM_TYPE_U64`, no indom):
- `kernel.all.cpu.nice` — carved from user (2%)
- `kernel.all.cpu.vuser` — carved from user (1.5%)
- `kernel.all.cpu.vnice` — carved from user (0.5%)
- `kernel.all.cpu.intr` — carved from sys (3%)
- `kernel.all.cpu.guest` — carved from user (1%)
- `kernel.all.cpu.guest_nice` — carved from user (0.5%)

New discrete descriptor:
- `hinv.ncpu` — `PM_TYPE_U32`, `PM_SEM_DISCRETE`, `UNITS_NONE`, `is_discrete=True`
  - Value = `hardware.cpus` (constant per archive)

---

### `SystemMetricModel` (`domains/system.py`, renamed from `load.py`)

`LoadMetricModel` is renamed `SystemMetricModel`. The EMA load-average logic is unchanged.

Four new scheduler/interrupt counters and instants derived from `CpuStressor.utilization`:

| Metric | Sem | Type | Derivation |
|--------|-----|------|------------|
| `kernel.all.intr` | counter | U32 | `utilization × base_rate × num_cpus × interval` |
| `kernel.all.pswitch` | counter | U32 | `utilization × cs_rate × num_cpus × interval` |
| `kernel.all.running` | instant | U32 | `round(utilization × num_cpus)` |
| `kernel.all.blocked` | instant | U32 | `round(running × 0.1)` |

Where:
- `base_rate = 1000` interrupts/second per CPU at full utilization
- `cs_rate = 5000` context-switches/second per CPU at full utilization

These values produce plausible numbers (e.g., 4 CPUs at 90% utilization → ~3600 interrupts/s, ~18000 context-switches/s) without being precise simulation.

---

### `MemoryMetricModel` (`domains/memory.py`)

Eight new metrics added. All existing metrics and invariants (`used + free == physmem`) unchanged.

**New instant metrics** (no state, computed from `used_ratio` each tick):

| Metric | PMID | Type | Sem | Units | Derivation |
|--------|------|------|-----|-------|------------|
| `mem.util.active` | (58, 0, 15) | U64 | instant | UNITS_KBYTE | `used_kb × 0.60` |
| `mem.util.inactive` | (58, 0, 16) | U64 | instant | UNITS_KBYTE | `used_kb × 0.25` |
| `mem.util.slab` | (58, 0, 12) | U64 | instant | UNITS_KBYTE | `physmem_kb × 0.04` |

**New swap metrics** (counter-based, zero below 70% used_ratio):

| Metric | Type | Sem | Units | Derivation |
|--------|------|-----|-------|------------|
| `swap.used` | U64 | instant | UNITS_KBYTE | `swap_total × pressure × 0.5` |
| `swap.pagesin` | PM_TYPE_32 | counter | UNITS_COUNT | `pressure × 100 × interval` |
| `swap.pagesout` | PM_TYPE_32 | counter | UNITS_COUNT | `pressure × 80 × interval` |

Where `pressure = max(0.0, (used_ratio - 0.7) / 0.3)` and `swap_total = hardware.memory_kb`.

**New paging metrics** (counter-based, always non-zero when any disk I/O occurs):

| Metric | Type | Sem | Units | Derivation |
|--------|------|-----|-------|------------|
| `mem.vmstat.pgpgin` | U32 | counter | UNITS_COUNT | `used_kb / physmem_kb × 200 × interval` |
| `mem.vmstat.pgpgout` | U32 | counter | UNITS_COUNT | `used_kb / physmem_kb × 150 × interval` |

These metrics are driven by `MemoryStressor` (no new stressor fields needed).

---

### `DiskMetricModel` (`domains/disk.py`)

Ten new per-device metrics added. All share the existing `_DISK_INDOM = (60, 1)` instance domain — no new registration required (spec clarification confirmed).

**New counter metrics** (per-device, accumulated via `sampler.accumulate`):

| Metric | PMID | Derivation |
|--------|------|------------|
| `disk.dev.read` | (60, 5, 0) | `iops_read / num_disks` |
| `disk.dev.write` | (60, 5, 1) | `iops_write / num_disks` |
| `disk.dev.read_merge` | (60, 5, 2) | `iops_read × 0.15 / num_disks` |
| `disk.dev.write_merge` | (60, 5, 3) | `iops_write × 0.20 / num_disks` |
| `disk.dev.blkread` | (60, 5, 7) | `read_bytes / 512 / num_disks` (sectors) |
| `disk.dev.blkwrite` | (60, 5, 8) | `write_bytes / 512 / num_disks` (sectors) |
| `disk.dev.read_rawactive` | (60, 5, 9) | `read_bytes × 0.8 / (1024²) × interval × 1000 / num_disks` ms |
| `disk.dev.write_rawactive` | (60, 5, 10) | `write_bytes × 0.8 / (1024²) × interval × 1000 / num_disks` ms |
| `disk.dev.avactive` | (60, 5, 12) | `(read_rawactive + write_rawactive)` ms |

**New instant metrics** (per-device, not accumulated):

| Metric | PMID | Type | Derivation |
|--------|------|------|------------|
| `disk.dev.avg_qlen` | (60, 5, 11) | PM_TYPE_DOUBLE | `(read_mbps + write_mbps) / 100.0` |

Note: `disk.dev.secactive` is a **derived** metric in `vmstat-d.conf` — computed by pmrep as `instant(disk.dev.avactive)`. We do NOT emit it; pmrep computes it automatically.

---

## Unchanged Entities

- `HardwareProfile` — no new fields; `memory_kb` used for swap_total derivation
- `CpuStressor` — no new fields; sub-metric fractions are hardcoded constants
- `MemoryStressor` — no new fields
- `DiskStressor` — no new fields
- `NetworkStressor` — unchanged
- `ValueSampler` — no changes; existing `accumulate()` handles all new counters
- `ProfileLoader` — no changes

---

## Writer Changes (`writer.py`)

1. Import `SystemMetricModel` instead of `LoadMetricModel`.
2. After registering all descriptors, perform the **discrete pass**:
   - Collect all descriptors where `is_discrete=True` across all models.
   - For each, call the model's `compute()` to get the value (or compute inline for `hinv.ncpu`).
   - Call `pmiPutValue` for each discrete metric, then `pmiWrite(0, 0)` once.
3. Main sample loop excludes discrete metrics (they are already written).

The discrete pass implementation is cleanest as a method on `ArchiveWriter`:
```python
def _write_discrete_sample(self, log, sampler) -> None:
    """Emit all is_discrete metrics once at archive open (t=0)."""
    ...
    log.pmiWrite(0, 0)
```

---

## `pcp_constants.py` Changes

Three new type constants:
```python
PM_TYPE_U32: int = _c.PM_TYPE_U32
PM_TYPE_32: int = _c.PM_TYPE_32
PM_TYPE_DOUBLE: int = _c.PM_TYPE_DOUBLE
```
