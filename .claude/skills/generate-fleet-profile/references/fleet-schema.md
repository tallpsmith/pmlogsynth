# pmlogsynth Fleet Profile Schema

A fleet profile generates multiple PCP archives — one per simulated host — from a single
YAML file. It is a different document type from a workload profile.

---

## Top-Level Structure

A fleet profile has three top-level sections:

```yaml
meta:        # Fleet-wide settings (required)
hosts:       # Baseline host pool (required)
bad_actors:  # Anomalous host pool (optional)
```

---

## meta

Fleet-wide metadata. All fields are required.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Fleet identifier. Used in output directory naming and the manifest. |
| `duration` | int or string | Archive duration for ALL hosts. Overrides workload profile durations. Integer = seconds, or strings: `'10m'`, `'1h'`, `'24h'`, `'7d'`. |
| `interval` | int or string | Sampling interval for ALL hosts. Overrides workload profile intervals. |
| `hostname_prefix` | string | Prefix for generated hostnames. Hosts are named `<prefix>-01`, `<prefix>-02`, etc. |
| `hardware` | string | Hardware profile name (e.g. `generic-large`). Applied to ALL hosts, overriding workload profile hardware. |

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

## hosts

Baseline host pool configuration. Required.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | — | **Required.** Total number of hosts in the fleet (includes bad actors). Must be ≥ 1. |
| `baseline` | string | — | **Required.** Path to the baseline workload profile YAML file. Resolved relative to the fleet profile file's directory. |
| `jitter` | float | `0.0` | Standard deviation for per-host Gaussian jitter. Applied multiplicatively to all stressor values. Typical range: 0.02–0.10. |

### Example

```yaml
hosts:
  count: 20
  baseline: fleet-baseline.yaml
  jitter: 0.05
```

---

## bad_actors

Optional section defining hosts that deviate from the baseline.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | `0` | Number of bad-actor hosts. Must not exceed `hosts.count`. |
| `jitter` | float | inherits `hosts.jitter` | Jitter for bad-actor hosts. |
| `profiles` | list of strings | `[]` | Paths to workload profile YAML files for bad actors. Resolved relative to the fleet profile file. Bad actors are randomly assigned a profile from this list. |

### Example

```yaml
bad_actors:
  count: 2
  jitter: 0.03
  profiles:
    - fleet-bad-cpu.yaml
    - fleet-bad-memory.yaml
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

hosts:
  count: 20
  baseline: fleet-baseline.yaml
  jitter: 0.05

bad_actors:
  count: 2
  jitter: 0.03
  profiles:
    - fleet-bad-cpu.yaml
    - fleet-bad-memory.yaml
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

## How Fleet Overrides Work

The fleet profile overrides several settings from individual workload profiles:

| Fleet setting | Overrides workload field | Notes |
|---------------|--------------------------|-------|
| `meta.duration` | `meta.duration` in workload | All hosts get the same duration |
| `meta.interval` | `meta.interval` in workload | All hosts get the same interval |
| `meta.hardware` | `host.profile` in workload | All hosts get the same hardware |
| `meta.hostname_prefix` + index | `meta.hostname` in workload | Each host gets a unique name |

Warnings are emitted when the fleet overrides differ from the workload profile values.

---

## Validation Rules

- `meta` must include all five fields: `name`, `duration`, `interval`, `hostname_prefix`, `hardware`
- `hosts.count` must be a positive integer
- `hosts.baseline` must be a valid path to a workload profile
- `bad_actors.count` must not exceed `hosts.count`
- `bad_actors.profiles` must be a non-empty list when `bad_actors.count > 0`
- All referenced workload profiles must be valid pmlogsynth workload profiles
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
# Validate the fleet profile (and referenced workload profiles)
pmlogsynth fleet --validate fleet-profile.yaml

# Preview host assignments without generating archives
pmlogsynth fleet --dry-run fleet-profile.yaml

# Generate all archives
pmlogsynth fleet -o ./generated-archives/my-fleet fleet-profile.yaml

# Reproducible generation (same seed = same host assignment + jitter)
pmlogsynth fleet --seed 42 -o ./generated-archives/my-fleet fleet-profile.yaml

# Parallel generation (use multiple workers)
pmlogsynth fleet --jobs 4 -o ./generated-archives/my-fleet fleet-profile.yaml
```
