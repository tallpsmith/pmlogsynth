# Data Model: pmlogsynth Phase 1

**Branch**: `001-pmlogsynth-phase1` | **Date**: 2026-03-01

---

## Entities

### 1. WorkloadProfile

**File**: `pmlogsynth/profile.py`
**Description**: The authoritative input document. A parsed, validated YAML workload
profile describing a simulation scenario.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `meta` | `ProfileMeta` | yes | Archive-level settings |
| `host` | `HostConfig` | yes | Hardware specification (named or inline) |
| `phases` | `list[Phase]` | yes | Ordered list of workload phases |

**Construction**:
- `WorkloadProfile.from_file(path: Path) -> WorkloadProfile`
- `WorkloadProfile.from_string(yaml_text: str) -> WorkloadProfile`
- `from_file` delegates to `from_string` internally (FR-042)

**Validation rules** (raise `ValidationError` with specific message):
- Phase duration sum must equal `meta.duration` when no `repeat` key is present (FR-027)
- `host.profile` must resolve to a known hardware profile via `ProfileResolver` (FR-028)
- `host.profile` + bare inline fields (without `overrides:`) is a validation error (FR-015a)
- At least one phase must be present

---

### 2. ProfileMeta

**Embedded in**: `WorkloadProfile`

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `hostname` | `str` | no | `"synthetic-host"` | — |
| `timezone` | `str` | no | `"UTC"` | — |
| `duration` | `int` | yes | — | > 0 (FR-030 analog) |
| `interval` | `int` | no | `60` | positive integer, seconds (FR-030) |
| `noise` | `float` | no | `0.0` | [0.0, 1.0] (FR-029) |
| `mean_packet_bytes` | `int` | no | `1400` | > 0 |

---

### 3. HostConfig

**Embedded in**: `WorkloadProfile`

Three mutually exclusive forms (FR-015a):

**Form 1** — Named profile only:
```yaml
host:
  profile: generic-large
```

**Form 2** — Named profile + overrides:
```yaml
host:
  profile: generic-large
  overrides:
    cpus: 16
```

**Form 3** — Fully inline:
```yaml
host:
  name: my-host
  cpus: 4
  memory_kb: 16384000
  disks:
    - name: sda
      type: ssd
  interfaces:
    - name: eth0
      speed_mbps: 10000
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `profile` | `Optional[str]` | no | Named hardware profile reference |
| `overrides` | `Optional[dict]` | no | Partial overrides applied to named profile |
| `name` | `Optional[str]` | no | For inline form |
| `cpus` | `Optional[int]` | no | For inline form or overrides |
| `memory_kb` | `Optional[int]` | no | For inline form or overrides |
| `disks` | `Optional[list[DiskDevice]]` | no | For inline form or overrides |
| `interfaces` | `Optional[list[NetworkInterface]]` | no | For inline form or overrides |

**State transition**: `HostConfig` is resolved to a `HardwareProfile` by `ProfileResolver`
during validation. The resolved profile is stored for use by `MetricModel` instances.

---

### 4. HardwareProfile

**File**: `pmlogsynth/profile.py`
**Description**: Named YAML document specifying the physical/virtual host being simulated.
Schema is frozen after Phase 1 ships (D-005).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Profile identifier (matches filename stem) |
| `cpus` | `int` | yes | CPU count (determines per-CPU indom size) |
| `memory_kb` | `int` | yes | Total physical RAM in kibibytes |
| `disks` | `list[DiskDevice]` | yes | One or more disk devices |
| `interfaces` | `list[NetworkInterface]` | yes | One or more network interfaces |

**Sources (precedence order, highest to lowest)**:
1. `-C / --config-dir` directory
2. `~/.pcp/pmlogsynth/profiles/`
3. Bundled package data (`pmlogsynth/profiles/`)

**Bundled profiles** (FR-021):

| Name | CPUs | RAM | Disks | NICs |
|------|------|-----|-------|------|
| `generic-small` | 2 | 8 GB | 1× NVMe | 1× 10GbE |
| `generic-medium` | 4 | 16 GB | 1× NVMe | 1× 10GbE |
| `generic-large` | 8 | 32 GB | 2× NVMe | 1× 10GbE |
| `generic-xlarge` | 16 | 64 GB | 2× NVMe | 2× 10GbE |
| `compute-optimized` | 8 | 16 GB | 1× NVMe | 1× 10GbE |
| `memory-optimized` | 4 | 64 GB | 1× NVMe | 1× 10GbE |
| `storage-optimized` | 4 | 16 GB | 4× HDD | 1× 10GbE |

---

### 5. DiskDevice

**Embedded in**: `HardwareProfile`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Device name (e.g., `nvme0n1`, `sda`) |
| `type` | `str` | no | `"nvme"`, `"ssd"`, `"hdd"` (informational) |

---

### 6. NetworkInterface

**Embedded in**: `HardwareProfile`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Interface name (e.g., `eth0`, `bond0`) |
| `speed_mbps` | `int` | no | Link speed in Mbps (informational) |

---

### 7. Phase

**File**: `pmlogsynth/profile.py`
**Description**: A named time segment in the workload timeline.

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | `str` | yes | — | Identifier |
| `duration` | `int` | yes | — | Seconds; > 0 |
| `transition` | `Optional[str]` | no | `"instant"` | `"instant"` or `"linear"` |
| `repeat` | `Optional[str\|int]` | no | — | `"daily"` or integer count |
| `cpu` | `Optional[CpuStressor]` | no | — | All fields default at compute time (FR-020) |
| `memory` | `Optional[MemoryStressor]` | no | — | All fields default at compute time |
| `disk` | `Optional[DiskStressor]` | no | — | All fields default at compute time |
| `network` | `Optional[NetworkStressor]` | no | — | All fields default at compute time |

**Validation rules**:
- First phase with `transition: linear` is a validation error — no prior phase (FR-055)
- `repeat: daily` must fit within `meta.duration` when expanded (FR-031)

---

### 8. CpuStressor

**Embedded in**: `Phase`

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `utilization` | `Optional[float]` | 0.0 at compute time | [0.0, 1.0] |
| `user_ratio` | `Optional[float]` | 0.70 at compute time | — |
| `sys_ratio` | `Optional[float]` | 0.20 at compute time | — |
| `iowait_ratio` | `Optional[float]` | 0.10 at compute time | — |
| `noise` | `Optional[float]` | inherits `meta.noise` | [0.0, 1.0] |

**Constraint**: `user_ratio + sys_ratio + iowait_ratio ≤ 1.0` (FR-026)

---

### 9. MemoryStressor

**Embedded in**: `Phase`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `used_ratio` | `Optional[float]` | 0.50 at compute time | [0.0, 1.0] |
| `cache_ratio` | `Optional[float]` | 0.30 at compute time | fraction of used |
| `noise` | `Optional[float]` | inherits `meta.noise` | [0.0, 1.0] |

---

### 10. DiskStressor

**Embedded in**: `Phase`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `read_mbps` | `Optional[float]` | 0.0 at compute time | MB/s |
| `write_mbps` | `Optional[float]` | 0.0 at compute time | MB/s |
| `iops_read` | `Optional[int]` | None (estimated from read_mbps) | — |
| `iops_write` | `Optional[int]` | None (estimated from write_mbps) | — |
| `noise` | `Optional[float]` | inherits `meta.noise` | [0.0, 1.0] |

---

### 11. NetworkStressor

**Embedded in**: `Phase`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `rx_mbps` | `Optional[float]` | 0.0 at compute time | MB/s |
| `tx_mbps` | `Optional[float]` | 0.0 at compute time | MB/s |
| `noise` | `Optional[float]` | inherits `meta.noise` | [0.0, 1.0] |

---

### 12. ExpandedTimeline

**File**: `pmlogsynth/timeline.py`
**Description**: A flat, ordered list of `SamplePoint` objects produced by the timeline
sequencer after expanding `repeat` keys and computing linear interpolations.

| Field | Type | Description |
|-------|------|-------------|
| `samples` | `list[SamplePoint]` | All sample points in chronological order |
| `start_time` | `datetime` | Absolute start timestamp |

---

### 13. SamplePoint

**Embedded in**: `ExpandedTimeline`
**Description**: One sample — the effective stressor values at a single timestamp.

| Field | Type | Description |
|-------|------|-------------|
| `timestamp_sec` | `int` | Unix epoch second |
| `phase_name` | `str` | Source phase name (for debugging) |
| `cpu` | `CpuStressor` | Effective CPU stressors (interpolated if linear) |
| `memory` | `MemoryStressor` | Effective memory stressors |
| `disk` | `DiskStressor` | Effective disk stressors |
| `network` | `NetworkStressor` | Effective network stressors |

---

### 14. MetricModel (abstract base)

**File**: `pmlogsynth/domains/base.py`
**Description**: Abstract base class for all domain-specific metric models.

```python
class MetricModel(ABC):
    @abstractmethod
    def compute(
        self,
        stressor: Any,
        hardware: HardwareProfile,
        interval: int,
        sampler: "ValueSampler",
    ) -> dict[str, dict[str, float]]:
        """Return {metric_name: {instance_or_None: value}} for one sample."""
        ...

    @abstractmethod
    def metric_descriptors(
        self, hardware: HardwareProfile
    ) -> list[MetricDescriptor]:
        """Return metric definitions for archive header registration."""
        ...
```

**Concrete subclasses** (one per domain, each in its own file):
- `CpuMetricModel` — `domains/cpu.py`
- `MemoryMetricModel` — `domains/memory.py`
- `DiskMetricModel` — `domains/disk.py`
- `NetworkMetricModel` — `domains/network.py`
- `LoadMetricModel` — `domains/load.py`

---

### 15. MetricDescriptor

**Embedded in**: `MetricModel.metric_descriptors()` return type
**Description**: Carries the registration parameters for one PCP metric.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | PCP metric name (e.g., `kernel.all.cpu.user`) |
| `pmid` | `tuple[int,int,int]` | (domain, cluster, item) |
| `type_code` | `int` | `PM_TYPE_*` constant |
| `indom` | `Optional[tuple[int,int]]` | `(domain, serial)` or `None` for `PM_INDOM_NULL` |
| `sem` | `int` | `PM_SEM_COUNTER` or `PM_SEM_INSTANT` or `PM_SEM_DISCRETE` |
| `units` | `tuple[int,...]` | args to `pmiUnits(...)` |

---

### 16. ValueSampler

**File**: `pmlogsynth/sampler.py`
**Description**: Stateful class that applies Gaussian noise, accumulates counter state
across samples, and coerces values to PCP-appropriate types.

| Attribute | Type | Description |
|-----------|------|-------------|
| `noise` | `float` | Global noise factor (overridden per domain in compute()) |
| `_rng` | `random.Random` | Private PRNG; seeded by `seed` parameter (FR-043) |
| `_counters` | `dict[str, float]` | Running totals per `(metric, instance)` key |

**Constructor**: `ValueSampler(noise: float = 0.0, seed: Optional[int] = None)`
- `seed=None` → non-reproducible (default)
- `seed=<int>` → byte-identical reproducible output (Phase 3 requirement)

**Key methods**:
- `apply_noise(value, noise_override) -> float` — multiplicative Gaussian, clamped ≥ 0
- `accumulate(key, delta) -> int` — adds delta to running counter, returns new total
- `coerce_u64(value) -> int` — clamps and converts to unsigned 64-bit integer

---

### 17. ProfileResolver

**File**: `pmlogsynth/profile.py`
**Description**: Resolves hardware profile names to `HardwareProfile` objects using the
three-level precedence chain. Constructed once with the optional `-C` path (D-006).

| Attribute | Type | Description |
|-----------|------|-------------|
| `config_dir` | `Optional[Path]` | `-C` directory (highest precedence) |
| `user_dir` | `Path` | `~/.pcp/pmlogsynth/profiles/` |
| `bundled_dir` | `Path` | `pmlogsynth/profiles/` (package data) |

**Key methods**:
- `resolve(name: str) -> HardwareProfile` — raises `ValidationError` if not found
- `list_all() -> list[ProfileEntry]` — returns all profiles with source label

---

## Entity Relationships

```
WorkloadProfile
    ├── ProfileMeta
    ├── HostConfig ──resolves via──► HardwareProfile
    │                                   ├── DiskDevice[]
    │                                   └── NetworkInterface[]
    └── Phase[]
            ├── CpuStressor (Optional)
            ├── MemoryStressor (Optional)
            ├── DiskStressor (Optional)
            └── NetworkStressor (Optional)

ProfileResolver  ──resolves──► HardwareProfile

ExpandedTimeline
    └── SamplePoint[]
            ├── CpuStressor (effective, interpolated)
            ├── MemoryStressor
            ├── DiskStressor
            └── NetworkStressor

MetricModel (abstract)
    ├── CpuMetricModel
    ├── MemoryMetricModel
    ├── DiskMetricModel
    ├── NetworkMetricModel
    └── LoadMetricModel
    Each uses: ValueSampler + HardwareProfile → dict[metric, dict[instance, value]]

writer.py (ArchiveWriter)
    ├── Registers MetricDescriptors via pmiAddMetric / pmiAddInstance
    └── Iterates SamplePoints → calls MetricModel.compute() → pmiPutValue → pmiWrite
```

---

## State Transitions

### Profile Loading

```
raw YAML string
    → parse (PyYAML)
    → validate schema (raise ValidationError with field path on failure)
    → resolve host (ProfileResolver)
    → WorkloadProfile (valid, ready for timeline expansion)
```

### Timeline Expansion

```
WorkloadProfile.phases[]
    → expand repeat: daily (insert baseline fills between repetitions)
    → validate expanded duration == meta.duration
    → for each sample tick:
        → compute effective stressor values (linear interpolation if transition: linear)
        → emit SamplePoint
    → ExpandedTimeline (flat, all samples)
```

### Archive Writing

```
ExpandedTimeline
    → open pmiLogImport (archive path, hostname, timezone)
    → register all MetricDescriptors (metrics + indom instances)
    → for each SamplePoint:
        → for each domain: MetricModel.compute(stressor, hardware, interval, sampler)
        → pmiPutValue for each (metric, instance, value) pair
        → pmiWrite(timestamp_sec, 0)
    → close/del pmiLogImport → finalizes .0/.index/.meta
    → on error: delete partial files (FR-051) unless --leave-partial
```
