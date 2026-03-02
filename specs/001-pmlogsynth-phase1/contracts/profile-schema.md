# Contract: YAML Workload Profile Schema

**Tool**: `pmlogsynth`
**Schema owner**: `pmlogsynth/profile.py` (ProfileLoader)
**Date**: 2026-03-01

This document is the authoritative schema for workload profile YAML files consumed by
`pmlogsynth`. Any change to this schema MUST be reflected in the man page and in
`ProfileLoader` simultaneously.

---

## Annotated Full Example

```yaml
# ── Archive metadata ──────────────────────────────────────────────────────────
meta:
  hostname: synthetic-host      # string, optional, default: "synthetic-host"
  timezone: UTC                 # string, optional, default: "UTC"
  duration: 1800                # integer, REQUIRED: total archive length in seconds
  interval: 60                  # integer, optional, default: 60, must be > 0
  noise: 0.03                   # float [0.0, 1.0], optional, default: 0.0
  mean_packet_bytes: 1400       # integer > 0, optional, default: 1400

# ── Host hardware ─────────────────────────────────────────────────────────────
# Three mutually exclusive forms (pick exactly one):

# Form 1: named profile only
host:
  profile: generic-large

# Form 2: named profile + explicit overrides
# host:
#   profile: generic-large
#   overrides:
#     cpus: 16

# Form 3: fully inline
# host:
#   name: my-host
#   cpus: 8
#   memory_kb: 32768000
#   disks:
#     - name: nvme0n1
#       type: nvme
#   interfaces:
#     - name: eth0
#       speed_mbps: 10000

# ── Workload phases ───────────────────────────────────────────────────────────
phases:
  - name: baseline                # string, REQUIRED
    duration: 300                 # integer seconds, REQUIRED, must be > 0
    # transition: instant         # "instant" (default) or "linear"
    # repeat: daily               # "daily" or integer count; optional

    cpu:                          # optional block
      utilization: 0.15           # float [0.0, 1.0]
      user_ratio: 0.70            # float; sum of user+sys+iowait must be <= 1.0
      sys_ratio: 0.20
      iowait_ratio: 0.10
      # noise: 0.05               # per-domain noise override

    memory:                       # optional block
      used_ratio: 0.40            # float [0.0, 1.0]
      cache_ratio: 0.30           # fraction of used memory that is page cache

    disk:                         # optional block
      read_mbps: 2.0
      write_mbps: 0.5
      # iops_read: 500            # optional; estimated from read_mbps if absent
      # iops_write: 200

    network:                      # optional block
      rx_mbps: 10.0
      tx_mbps: 2.0

  - name: cpu-spike
    duration: 300
    cpu:
      utilization: 0.92
      user_ratio: 0.85
      sys_ratio: 0.10
      iowait_ratio: 0.05
    memory:
      used_ratio: 0.55
    disk:
      read_mbps: 8.0
      write_mbps: 3.0
    network:
      rx_mbps: 10.0
      tx_mbps: 2.0

  - name: recovery
    duration: 1200
    transition: linear            # interpolates from cpu-spike end values over 1200s
    cpu:
      utilization: 0.20
    memory:
      used_ratio: 0.42
    disk:
      read_mbps: 2.5
      write_mbps: 0.8
    network:
      rx_mbps: 10.0
      tx_mbps: 2.0
```

---

## Schema Reference

### `meta` block (required)

| Key | Type | Required | Default | Constraints |
|-----|------|----------|---------|-------------|
| `hostname` | string | no | `"synthetic-host"` | — |
| `timezone` | string | no | `"UTC"` | — |
| `duration` | integer | **yes** | — | > 0 |
| `interval` | integer | no | `60` | > 0, seconds |
| `noise` | float | no | `0.0` | [0.0, 1.0] |
| `mean_packet_bytes` | integer | no | `1400` | > 0 |

### `host` block (required)

Exactly one of the three forms must be used:

| Form | Keys present | Valid? |
|------|-------------|--------|
| Named only | `profile` | Yes |
| Named + overrides | `profile` + `overrides` | Yes |
| Inline | no `profile` key; `name`, `cpus`, `memory_kb`, `disks`, `interfaces` | Yes |
| Mixed (illegal) | `profile` + bare inline fields (no `overrides` key) | **Validation error** |

`overrides` sub-block may contain any subset of inline host fields. Unknown keys are a
validation error.

### `phases` list (required)

At least one phase is required.

**Per-phase keys**:

| Key | Type | Required | Default | Notes |
|-----|------|----------|---------|-------|
| `name` | string | **yes** | — | — |
| `duration` | integer | **yes** | — | > 0, seconds |
| `transition` | string | no | `"instant"` | `"instant"` or `"linear"` |
| `repeat` | string or integer | no | — | `"daily"` or count > 0 |
| `cpu` | object | no | — | see below |
| `memory` | object | no | — | see below |
| `disk` | object | no | — | see below |
| `network` | object | no | — | see below |

**`cpu` stressor keys**:

| Key | Type | Notes |
|-----|------|-------|
| `utilization` | float [0.0, 1.0] | Overall CPU utilization |
| `user_ratio` | float | Fraction of busy time in user space |
| `sys_ratio` | float | Fraction of busy time in kernel space |
| `iowait_ratio` | float | Fraction of busy time in I/O wait |
| `noise` | float [0.0, 1.0] | Per-domain override of `meta.noise` |

Constraint: `user_ratio + sys_ratio + iowait_ratio ≤ 1.0`

**`memory` stressor keys**:

| Key | Type | Notes |
|-----|------|-------|
| `used_ratio` | float [0.0, 1.0] | Fraction of `memory_kb` in use |
| `cache_ratio` | float [0.0, 1.0] | Fraction of used memory that is page cache |
| `noise` | float [0.0, 1.0] | Per-domain override |

**`disk` stressor keys**:

| Key | Type | Notes |
|-----|------|-------|
| `read_mbps` | float ≥ 0 | Aggregate read throughput MB/s |
| `write_mbps` | float ≥ 0 | Aggregate write throughput MB/s |
| `iops_read` | integer ≥ 0 | Read ops/s; estimated if absent |
| `iops_write` | integer ≥ 0 | Write ops/s; estimated if absent |
| `noise` | float [0.0, 1.0] | Per-domain override |

**`network` stressor keys**:

| Key | Type | Notes |
|-----|------|-------|
| `rx_mbps` | float ≥ 0 | Aggregate receive throughput MB/s |
| `tx_mbps` | float ≥ 0 | Aggregate transmit throughput MB/s |
| `noise` | float [0.0, 1.0] | Per-domain override |

---

## Validation Constraints Summary

| Constraint | Error |
|-----------|-------|
| `meta.duration` must be a positive integer | "meta.duration must be a positive integer" |
| `meta.interval` must be a positive integer | "meta.interval must be a positive integer" |
| All `noise` values must be in [0.0, 1.0] | "noise value N is out of range [0.0, 1.0]" |
| Sum of phase durations == `meta.duration` (no `repeat`) | "phase durations sum to N but meta.duration is M" |
| `user_ratio + sys_ratio + iowait_ratio ≤ 1.0` | "cpu ratios sum to N > 1.0 in phase 'P'" |
| First phase must not have `transition: linear` | "first phase cannot use linear transition: no prior phase" |
| `host.profile` must resolve to a known name | "hardware profile 'X' not found in any profile directory" |
| `host.profile` + bare inline fields (no `overrides:`) | "use overrides: sub-key to override named profile fields" |
| `repeat: daily` expanded timeline exceeds `meta.duration` | "repeat: daily in phase 'P' expands to N seconds but meta.duration is M" |
| `meta.duration` is zero or negative | "meta.duration must be > 0" |
| Phase duration is zero | "phase 'P' duration must be > 0" |
| `-C` directory does not exist | "config-dir 'X' does not exist or is not a directory" |
| `host.profile` references unknown profile (with -C active) | "hardware profile 'X' not found (searched: config-dir, ~/.pcp/pmlogsynth/profiles/, bundled)" |

---

## `repeat` Expansion Rules

### `repeat: daily`

The phase repeats every 24 hours. The sequencer:
1. Inserts the first phase (treated as the "baseline fill" phase) between each repetition
2. Validates that the expanded sequence fits within `meta.duration`
3. Truncates or pads to exactly `meta.duration` with baseline fill

### `repeat: N` (integer)

The phase appears exactly N times in sequence, with no fill between repetitions.
Phase duration × N must be ≤ total remaining timeline after preceding phases.

---

## Defaults Applied at Compute Time

All stressor fields are `Optional` in the parsed object. Defaults are applied by
`MetricModel.compute()`, not by `ProfileLoader`. This allows Phase 3 overlay logic to
distinguish "not set" from "set to 0.0":

| Domain | Field | Compute-time default |
|--------|-------|---------------------|
| CPU | `utilization` | 0.0 |
| CPU | `user_ratio` | 0.70 |
| CPU | `sys_ratio` | 0.20 |
| CPU | `iowait_ratio` | 0.10 |
| Memory | `used_ratio` | 0.50 |
| Memory | `cache_ratio` | 0.30 |
| Disk | `read_mbps` | 0.0 |
| Disk | `write_mbps` | 0.0 |
| Network | `rx_mbps` | 0.0 |
| Network | `tx_mbps` | 0.0 |
