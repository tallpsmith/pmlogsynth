# pmlogsynth Profile Schema

Schema Version: 0.1.0

pmlogsynth generates synthetic PCP (Performance Co-Pilot) archives from declarative YAML
workload profiles. This document is the complete reference for generating valid profiles.

---

## Overview

A profile has three top-level keys: `meta`, `host`, and `phases`. All three are required.

```yaml
meta:
  duration: 1h          # total archive length
  hostname: my-host
host:
  profile: generic-small
phases:
  - name: baseline
    duration: 1h
    cpu:
      utilization: 0.30
```

---

## meta

Global archive settings. All fields except `duration` are optional.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `duration` | int or string | — | **Required.** Total archive length. Integer = seconds. Strings: `'30s'`, `'10m'`, `'24h'`. Must be positive. |
| `hostname` | string | `synthetic-host` | Hostname written into the archive. |
| `timezone` | string | `UTC` | Timezone label (informational only). |
| `interval` | int | `60` | Seconds between samples. Must be a positive integer. |
| `noise` | float | `0.0` | Global noise amplitude [0.0–1.0] applied to all metrics. |
| `mean_packet_bytes` | int | `1400` | Mean packet size for network byte calculations. |
| `start` | string | today 00:00:00 UTC | Archive start time. ISO 8601: `2026-03-01T08:00:00Z` or `2026-03-01 08:00:00 UTC`. |

### meta validation rules

- `duration` must be a positive integer (seconds) or a duration string (`'30s'`, `'10m'`, `'24h'`).
- `interval` must be a positive integer.
- `noise` must be in the range [0.0, 1.0].
- `start` must be parseable as ISO 8601.

---

## host

Specifies the hardware the workload runs on. Three forms are supported.

### Form 1 — Named profile (recommended)

```yaml
host:
  profile: generic-small
```

### Form 2 — Named profile with overrides

```yaml
host:
  profile: generic-medium
  overrides:
    cpus: 32
    memory_kb: 65536000
```

### Form 3 — Fully inline

```yaml
host:
  name: custom-server
  cpus: 8
  memory_kb: 16777216
  disks:
    - name: nvme0n1
      type: nvme
  interfaces:
    - name: eth0
      speed_mbps: 10000
```

### host field reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile` | string | No | Name of a bundled or user hardware profile. |
| `overrides` | mapping | No | Override specific fields from the named profile. |
| `name` | string | No | Custom name for inline hardware. |
| `cpus` | int | Inline only | Number of CPUs. Required for inline form. |
| `memory_kb` | int | Inline only | Total RAM in kilobytes. Required for inline form. |
| `disks` | list | No | List of `{name: str, type: str}`. `type` is one of `nvme`, `ssd`, `hdd`. |
| `interfaces` | list | No | List of `{name: str, speed_mbps: int}`. |

### host validation rules

- **Cannot mix** `profile` with inline fields (`cpus`, `memory_kb`, etc.) without an `overrides:` key.
- Inline form requires **both** `cpus` and `memory_kb`.
- Each disk must have a `name` field.
- Each interface must have a `name` field.

---

## Available Hardware Profiles

Use one of these names for `host.profile`:

| Name | Description |
|------|-------------|
| `generic-small` | Small VM / test environment (2 CPUs, ~4 GB RAM) |
| `generic-medium` | Mid-range server (8 CPUs, ~32 GB RAM) |
| `generic-large` | Production server (16 CPUs, ~64 GB RAM) |
| `generic-xlarge` | High-end server (32 CPUs, ~128 GB RAM) |
| `compute-optimized` | CPU-heavy workloads (64 CPUs, ~32 GB RAM) |
| `memory-optimized` | Memory-heavy workloads (16 CPUs, ~512 GB RAM) |
| `storage-optimized` | Disk I/O-heavy workloads (8 CPUs, ~64 GB RAM, multiple NVMe disks) |

---

## phases

An ordered list of workload phases. Each phase describes a period of the archive with
specific resource utilisation patterns. At least one phase is required.

**Critical constraint**: The sum of all phase `duration` values **must equal** `meta.duration`,
unless a phase uses `repeat` (see below).

### Phase fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Phase identifier. Used in validation error messages. |
| `duration` | int or string | Yes | Length of this phase. Same format as `meta.duration`. |
| `transition` | string | No | `instant` (default) or `linear`. `linear` interpolates from the previous phase's values. **Cannot be set on the first phase.** |
| `repeat` | string or int | No | `daily` repeats this phase every day for `meta.duration`. Only one phase allowed when `repeat: daily`. Integer repeat count is also supported. |
| `cpu` | mapping | No | CPU stressor (see below). |
| `memory` | mapping | No | Memory stressor (see below). |
| `disk` | mapping | No | Disk stressor (see below). |
| `network` | mapping | No | Network stressor (see below). |

### cpu stressor

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `utilization` | float [0.0–1.0] | 0.05 | Overall CPU utilisation fraction. |
| `user_ratio` | float | 0.70 | Fraction of CPU time in user space. |
| `sys_ratio` | float | 0.20 | Fraction of CPU time in kernel space. |
| `iowait_ratio` | float | 0.10 | Fraction of CPU time in I/O wait. |
| `noise` | float [0.0–1.0] | 0.0 | Per-sample noise for CPU metrics. |

**Constraint**: `user_ratio + sys_ratio + iowait_ratio` must be ≤ 1.0.

### memory stressor

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `used_ratio` | float [0.0–1.0] | 0.50 | Fraction of total RAM used. |
| `cache_ratio` | float [0.0–1.0] | 0.20 | Fraction of RAM used as page cache. |
| `noise` | float [0.0–1.0] | 0.0 | Per-sample noise for memory metrics. |

### disk stressor

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `read_mbps` | float | 0.0 | Disk read throughput in MB/s. |
| `write_mbps` | float | 0.0 | Disk write throughput in MB/s. |
| `iops_read` | int | 0 | Read I/O operations per second. |
| `iops_write` | int | 0 | Write I/O operations per second. |
| `noise` | float [0.0–1.0] | 0.0 | Per-sample noise for disk metrics. |

### network stressor

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rx_mbps` | float | 0.0 | Inbound throughput in MB/s. |
| `tx_mbps` | float | 0.0 | Outbound throughput in MB/s. |
| `noise` | float [0.0–1.0] | 0.0 | Per-sample noise for network metrics. |

---

## Examples

### Simple — 10-minute CPU spike

```yaml
meta:
  hostname: demo-host
  timezone: UTC
  duration: 10m
  interval: 60

host:
  profile: generic-small

phases:
  - name: baseline
    duration: 5m
    cpu:
      utilization: 0.15

  - name: spike
    duration: 5m
    cpu:
      utilization: 0.90
```

### Complex — 24-hour SaaS workload with diurnal pattern

```yaml
meta:
  hostname: saas-prod-01
  timezone: UTC
  duration: 24h
  interval: 60
  noise: 0.05
  start: "2026-03-01T00:00:00Z"

host:
  profile: generic-large
  overrides:
    cpus: 24

phases:
  - name: overnight-quiet
    duration: 8h
    cpu:
      utilization: 0.08
      user_ratio: 0.60
      sys_ratio: 0.20
      iowait_ratio: 0.10
    memory:
      used_ratio: 0.40
    network:
      rx_mbps: 5.0
      tx_mbps: 2.0

  - name: business-hours-ramp
    duration: 2h
    transition: linear
    cpu:
      utilization: 0.55
      user_ratio: 0.65
      sys_ratio: 0.20
      iowait_ratio: 0.10
    memory:
      used_ratio: 0.65

  - name: business-hours-peak
    duration: 8h
    cpu:
      utilization: 0.75
      user_ratio: 0.65
      sys_ratio: 0.20
      iowait_ratio: 0.10
    memory:
      used_ratio: 0.72
      cache_ratio: 0.15
    disk:
      read_mbps: 120.0
      write_mbps: 60.0
      iops_read: 4000
      iops_write: 2000
    network:
      rx_mbps: 450.0
      tx_mbps: 380.0

  - name: evening-wind-down
    duration: 4h
    transition: linear
    cpu:
      utilization: 0.25
    memory:
      used_ratio: 0.50
    network:
      rx_mbps: 80.0
      tx_mbps: 60.0

  - name: late-night-batch
    duration: 2h
    cpu:
      utilization: 0.40
      user_ratio: 0.30
      sys_ratio: 0.20
      iowait_ratio: 0.45
    disk:
      read_mbps: 800.0
      write_mbps: 400.0
      iops_read: 20000
      iops_write: 10000
    memory:
      used_ratio: 0.60
```

Note: 8h + 2h + 8h + 4h + 2h = 24h = meta.duration ✓

---

## Common Validation Errors

### Duration errors

| Error message | Fix |
|---------------|-----|
| `Sum of phase durations (Xs) does not equal meta.duration (Ys) (FR-027)` | Adjust phase durations to sum to exactly `meta.duration`. |
| `invalid duration '...': use a positive integer or a string like '30s', '10m', '24h'` | Use seconds as an integer, or a string like `'1h'`, `'30m'`, `'600s'`. |
| `meta.duration must be a positive integer or duration string` | Set `meta.duration` to a positive int or a string like `'24h'`. |
| `phases[N].duration must be a positive integer or duration string` | Fix the duration in the Nth phase. |

### CPU errors

| Error message | Fix |
|---------------|-----|
| `phases[N] (name): user_ratio + sys_ratio + iowait_ratio = X > 1.0 (FR-026)` | Reduce `user_ratio`, `sys_ratio`, or `iowait_ratio` so their sum is ≤ 1.0. |
| `cpu.noise must be in [0.0, 1.0]` | Set `cpu.noise` to a value between 0.0 and 1.0. |

### Phase structure errors

| Error message | Fix |
|---------------|-----|
| `phases[0]: first phase cannot use 'transition: linear' (FR-055)` | Remove `transition: linear` from the first phase (no prior phase to interpolate from). |
| `A phase with repeat:daily must be the only phase` | Remove all other phases when using `repeat: daily`. |
| `phases[N].transition must be 'instant' or 'linear'` | Use `instant` or `linear`, or omit the field entirely. |
| `phases must be a non-empty list` | Add at least one phase to the `phases` list. |
| `phases[N].name is required` | Add a `name` field to the Nth phase. |

### Host errors

| Error message | Fix |
|---------------|-----|
| `Hardware profile 'X' not found` | Use one of the 7 bundled profiles listed in the Available Hardware Profiles table above. |
| `Inline host specification requires at least 'cpus' and 'memory_kb'` | Add both `cpus` and `memory_kb` to the inline `host` block. |
| `host.profile and inline host fields cannot be mixed without an 'overrides:' key` | Either use `host.profile` alone, or add an `overrides:` key alongside `profile`. |

### meta field errors

| Error message | Fix |
|---------------|-----|
| `meta.interval must be a positive integer (FR-030)` | Set `meta.interval` to a positive integer (seconds). |
| `meta.noise must be in [0.0, 1.0]` | Set `meta.noise` to a float between 0.0 and 1.0. |
| `meta.start: cannot parse '...'` | Use ISO 8601 format: `2026-03-01T08:00:00Z` or `2026-03-01 08:00:00 UTC`. |

### YAML format errors

| Error message | Fix |
|---------------|-----|
| `YAML parse error: ...` | The profile YAML is malformed or incomplete. Ensure the output is valid YAML with no truncation, no markdown code fences, and no prose mixed in. |
| `Profile must be a YAML mapping` | The profile must be a YAML mapping (key: value pairs at the top level), not a list or scalar. |

### Semantic pitfalls (no error raised, but incorrect output)

| Situation | Fix |
|-----------|-----|
| `meta.interval` (e.g. `3600`) is larger than `meta.duration` (e.g. `300`) | The archive will have zero or one sample. Set `interval` to a value smaller than `duration`. For a 5-minute archive use `interval: 60` (5 samples). |
| Phase durations don't sum to `meta.duration` by a few seconds | Adjust one phase duration. Common mistake: using `'1h'` phases in a `'24h'` archive where 24 × 1h = 24h but rounding errors creep in. Use exact integers: `3600` × 24 = `86400`. |

---

## Duration arithmetic tips

When writing multi-phase profiles, ensure your phase durations sum to `meta.duration`:

```
meta.duration: 24h = 86400s
phases:
  - duration: 8h   → 28800s
  - duration: 10h  → 36000s
  - duration: 6h   → 21600s
  Total:             86400s ✓
```

If using `repeat: daily`, omit all other phases and set `duration` to the length of the
repeating daily pattern (e.g., `86400` for a full 24h daily pattern, or less for a pattern
that repeats within each day).

---

## Generating archives

After generating a valid profile file:

```bash
# Validate the profile
pmlogsynth --validate generated-archives/my-workload.yaml

# Generate the PCP archive
pmlogsynth -o ./generated-archives/my-workload generated-archives/my-workload.yaml

# Inspect the archive
pmstat -a ./generated-archives/my-workload
```
