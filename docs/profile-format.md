# Profile Format Reference

A pmlogsynth workload profile is a YAML document with three top-level sections:
`meta`, `host`, and `phases`.

---

## `meta`

Global archive metadata.

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `hostname` | string | `synthetic-host` | — |
| `timezone` | string | `UTC` | Any valid timezone string |
| `duration` | integer | required | Positive; must equal sum of phase durations unless `repeat` is used |
| `interval` | integer | `60` | Positive integer (seconds) |
| `noise` | float | `0.0` | Range [0.0, 1.0] |
| `mean_packet_bytes` | integer | `1400` | Positive |

---

## `host`

Specifies the hardware profile used to generate per-instance metrics (per-CPU,
per-disk, per-NIC). Three mutually exclusive forms:

### Form 1 — Named profile only

```yaml
host:
  profile: generic-large
```

### Form 2 — Named profile with overrides

```yaml
host:
  profile: generic-large
  overrides:
    cpus: 16
```

### Form 3 — Fully inline

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

**Validation error**: mixing `profile:` with inline fields (`cpus`, `memory_kb`, etc.)
without an `overrides:` key is rejected.

---

## `phases`

An ordered list of named time segments. When no phase uses `repeat`, the sum of
all phase durations must equal `meta.duration`.

### Phase fields

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `name` | string | required | Unique identifier |
| `duration` | integer | required | Positive seconds |
| `transition` | string | `instant` | `instant` or `linear`; first phase cannot use `linear` |
| `repeat` | string or integer | — | `daily` or positive integer count |
| `cpu` | object | — | See CPU stressor below |
| `memory` | object | — | See Memory stressor below |
| `disk` | object | — | See Disk stressor below |
| `network` | object | — | See Network stressor below |

### `repeat: daily` — exclusivity constraint

> **WARNING**: `repeat: daily` cannot be combined with other phases.

A profile that contains a `repeat: daily` phase alongside any other phase is a
validation error. The validator will reject it with a clear error message.

**Invalid — do not do this:**

```yaml
phases:
  - name: daily-window
    duration: 3600
    repeat: daily
    cpu:
      utilization: 0.80

  - name: baseline          # ERROR: cannot coexist with repeat: daily
    duration: 86400
    cpu:
      utilization: 0.10
```

This produces: `Validation error: A phase with repeat:daily must be the only phase in the profile`

**Valid — use repeat: daily alone:**

```yaml
meta:
  duration: 604800   # 7 days
  interval: 60

host:
  profile: generic-small

phases:
  - name: daily-peak
    duration: 3600
    repeat: daily
    cpu:
      utilization: 0.85
```

---

## CPU stressor

```yaml
cpu:
  utilization: 0.70     # overall fraction [0.0, 1.0], default 0.0
  user_ratio: 0.70      # fraction of utilization in user space, default 0.70
  sys_ratio: 0.20       # fraction in kernel space, default 0.20
  iowait_ratio: 0.10    # fraction in iowait, default 0.10
  noise: 0.05           # per-domain noise override (inherits meta.noise)
```

`user_ratio + sys_ratio + iowait_ratio` must not exceed 1.0.

---

## Memory stressor

```yaml
memory:
  used_ratio: 0.60      # fraction of total RAM in use [0.0, 1.0], default 0.50
  cache_ratio: 0.30     # fraction of used RAM that is page cache, default 0.30
  noise: 0.02           # per-domain noise override
```

---

## Disk stressor

```yaml
disk:
  read_mbps: 200.0      # read throughput MB/s, default 0.0
  write_mbps: 50.0      # write throughput MB/s, default 0.0
  iops_read: 3200       # IOPS (estimated from MB/s ÷ 64KB if absent)
  iops_write: 800
  noise: 0.05           # per-domain noise override
```

---

## Network stressor

```yaml
network:
  rx_mbps: 500.0        # receive throughput MB/s, default 0.0
  tx_mbps: 100.0        # transmit throughput MB/s, default 0.0
  noise: 0.03           # per-domain noise override
```

---

## Complete example

See [`docs/complete-example.yml`](complete-example.yml) — a ready-to-run profile
covering all four stressor domains across three phases (baseline → ramp → peak).

```bash
pmlogsynth -o ./generated-archives/complete-example docs/complete-example.yml
```
