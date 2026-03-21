# pmlogsynth Fleet Profile Schema

A fleet profile generates multiple PCP archives — one per simulated host — from a single
self-contained YAML file. All workload profiles are defined inline using named definitions
in the `profiles` section.

---

## Top-Level Structure

A fleet profile has four top-level sections:

```yaml
meta:        # Fleet-wide settings (required)
profiles:    # Named workload profile definitions (required)
hosts:       # Baseline host pool (required)
bad_actors:  # Anomalous host pool (optional)
```

---

## meta

Fleet-wide metadata. All fields are required.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Fleet identifier. Used in output directory naming and the manifest. |
| `duration` | int or string | Archive duration for ALL hosts. Integer = seconds, or strings: `'10m'`, `'1h'`, `'24h'`, `'7d'`. |
| `interval` | int or string | Sampling interval for ALL hosts. |
| `hostname_prefix` | string | Prefix for generated hostnames. Hosts are named `<prefix>-01`, `<prefix>-02`, etc. |
| `hardware` | string | Hardware profile name (e.g. `generic-large`). Applied to ALL hosts. |

### Example

```yaml
meta:
  name: prod-web-cluster
  duration: 24h
  interval: 60
  hostname_prefix: web
  hardware: generic-large
```

This produces hostnames `web-01`, `web-02`, ..., `web-NN`.

---

## profiles

Named workload profile definitions. Required. Each entry defines a workload that can be
referenced by name from `hosts.baseline` or `bad_actors.profiles`.

Each profile contains a `phases` list — the same structure as the `phases` section of a
standalone workload profile. Profiles do **not** contain `meta`, `host`, or `hardware`
sections — those are all controlled at the fleet level.

### Example

```yaml
profiles:
  steady-baseline:
    phases:
      - name: normal-operations
        duration: 24h
        cpu:
          utilization: 0.35
          user_ratio: 0.65
          sys_ratio: 0.20
          iowait_ratio: 0.05
        memory:
          used_ratio: 0.55
          cache_ratio: 0.25
        disk:
          read_mbps: 20.0
          write_mbps: 10.0
        network:
          rx_mbps: 200.0
          tx_mbps: 100.0

  cpu-saturated:
    phases:
      - name: overloaded
        duration: 24h
        cpu:
          utilization: 0.96
          user_ratio: 0.85
          sys_ratio: 0.10
          iowait_ratio: 0.05
        memory:
          used_ratio: 0.70
          cache_ratio: 0.10
```

---

## hosts

Baseline host pool configuration. Required.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | — | **Required.** Total number of hosts in the fleet (includes bad actors). Must be ≥ 1. |
| `baseline` | string | — | **Required.** Name of a profile defined in the `profiles` section. |
| `jitter` | float | `0.0` | Standard deviation for per-host Gaussian jitter. Applied multiplicatively to all stressor values. Typical range: 0.02–0.10. |

### Example

```yaml
hosts:
  count: 20
  baseline: steady-baseline
  jitter: 0.05
```

---

## bad_actors

Optional section defining hosts that deviate from the baseline.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | `0` | Number of bad-actor hosts. Must not exceed `hosts.count`. |
| `jitter` | float | inherits `hosts.jitter` | Jitter for bad-actor hosts. |
| `profiles` | list of strings | `[]` | Names of profiles defined in the `profiles` section. Bad actors are randomly assigned a profile from this list. |

### Example

```yaml
bad_actors:
  count: 2
  jitter: 0.03
  profiles:
    - cpu-saturated
    - memory-exhausted
```

---

## Complete Example

```yaml
# Fleet: 20-host web cluster with 2 bad actors
meta:
  name: web-cluster
  duration: 24h
  interval: 60
  hostname_prefix: web
  hardware: generic-large

profiles:
  steady-baseline:
    phases:
      - name: normal-operations
        duration: 24h
        cpu:
          utilization: 0.35
          user_ratio: 0.65
          sys_ratio: 0.20
          iowait_ratio: 0.05
        memory:
          used_ratio: 0.55
          cache_ratio: 0.25
        disk:
          read_mbps: 20.0
          write_mbps: 10.0
        network:
          rx_mbps: 200.0
          tx_mbps: 100.0

  cpu-saturated:
    phases:
      - name: overloaded
        duration: 24h
        cpu:
          utilization: 0.96
          user_ratio: 0.85
          sys_ratio: 0.10
          iowait_ratio: 0.05
        memory:
          used_ratio: 0.70
          cache_ratio: 0.10

hosts:
  count: 20
  baseline: steady-baseline
  jitter: 0.05

bad_actors:
  count: 2
  jitter: 0.03
  profiles:
    - cpu-saturated
```

This generates 20 archives:
- 18 baseline hosts (`web-01` through `web-20`, minus 2 randomly selected bad actors)
- 2 bad-actor hosts (randomly selected from the pool, each assigned a profile from the
  `profiles` list)

All hosts share the `generic-large` hardware profile, a 24h duration, and 60s interval.

---

## How Host Assignment Works

1. All hosts are numbered `<hostname_prefix>-01` through `<hostname_prefix>-NN`
2. `bad_actors.count` hosts are randomly selected from the pool
3. Each bad actor is randomly assigned a profile from the `profiles` list
4. Remaining hosts use the `baseline` workload profile
5. Per-host jitter is applied multiplicatively to all stressor values:
   `effective_value = base_value × Normal(mean=1.0, stddev=jitter)`
6. Use `--seed` for deterministic, reproducible assignment

---

## Validation Rules

- `meta` must include all five fields: `name`, `duration`, `interval`, `hostname_prefix`, `hardware`
- `profiles` must be a non-empty mapping of named profile definitions
- Each profile must contain a non-empty `phases` list
- `hosts.count` must be a positive integer
- `hosts.baseline` must be a name defined in the `profiles` section
- `bad_actors.count` must not exceed `hosts.count`
- `bad_actors.profiles` entries must be names defined in the `profiles` section
- `hardware` must be a valid hardware profile name

---

## Available Hardware Profiles

| Name | Description |
|------|-------------|
| `generic-small` | Small VM (2 CPUs, ~4 GB RAM) |
| `generic-medium` | Mid-range server (8 CPUs, ~32 GB RAM) |
| `generic-large` | Production server (16 CPUs, ~64 GB RAM) |
| `generic-xlarge` | High-end server (32 CPUs, ~128 GB RAM) |
| `compute-optimized` | CPU-heavy workloads (64 CPUs, ~32 GB RAM) |
| `memory-optimized` | Memory-heavy workloads (16 CPUs, ~512 GB RAM) |
| `storage-optimized` | Disk I/O-heavy (8 CPUs, ~64 GB RAM, multiple NVMe) |

---

## CLI Commands

```bash
# Validate the fleet profile
pmlogsynth fleet --validate fleet-profile.yaml

# Preview host assignments without generating archives
pmlogsynth fleet --dry-run fleet-profile.yaml

# Generate all archives
pmlogsynth fleet -o ./generated-archives/my-fleet fleet-profile.yaml

# Reproducible generation (same seed = same host assignment + jitter)
pmlogsynth fleet --seed 42 -o ./generated-archives/my-fleet fleet-profile.yaml
```
