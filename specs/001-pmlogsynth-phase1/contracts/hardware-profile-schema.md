# Contract: YAML Hardware Profile Schema

**Tool**: `pmlogsynth`
**Schema owner**: `pmlogsynth/profile.py` (ProfileResolver + HardwareProfile)
**Date**: 2026-03-01

> **FROZEN after Phase 1**: This schema is a stable contract for Phase 2 and Phase 3.
> Any breaking change requires a schema version bump and a documented migration path (D-005).

---

## Schema

```yaml
# ~/.pcp/pmlogsynth/profiles/prod-web-tier.yaml
# (or pmlogsynth/profiles/generic-large.yaml for bundled profiles)

name: prod-web-tier         # string, REQUIRED: must match filename stem
cpus: 32                    # integer > 0, REQUIRED
memory_kb: 134217728        # integer > 0, REQUIRED (kibibytes; 128 GB = 134217728)
disks:                      # list, REQUIRED, at least 1 entry
  - name: nvme0n1           # string, REQUIRED: appears as PCP instance name
    type: nvme              # string, optional: "nvme", "ssd", "hdd" (informational)
  - name: nvme1n1
    type: nvme
interfaces:                 # list, REQUIRED, at least 1 entry
  - name: bond0             # string, REQUIRED: appears as PCP instance name
    speed_mbps: 25000       # integer > 0, optional (informational)
```

---

## Field Reference

### Top-level fields

| Field | Type | Required | Constraints | Notes |
|-------|------|----------|-------------|-------|
| `name` | string | **yes** | matches filename stem | Used for error messages and `--list-profiles` output |
| `cpus` | integer | **yes** | > 0 | Determines per-CPU indom instance count |
| `memory_kb` | integer | **yes** | > 0 | Total physical RAM in kibibytes |
| `disks` | list | **yes** | ≥ 1 entry | Device names become PCP instance names for `disk.dev.*` |
| `interfaces` | list | **yes** | ≥ 1 entry | Interface names become PCP instance names for `network.interface.*` |

### `disks[]` entry

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | **yes** | e.g., `nvme0n1`, `sda`, `vda`; used as PCP instance name |
| `type` | string | no | `"nvme"`, `"ssd"`, `"hdd"`; informational only |

### `interfaces[]` entry

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | **yes** | e.g., `eth0`, `bond0`, `ens3`; used as PCP instance name |
| `speed_mbps` | integer | no | Link speed; informational only; not used for metric scaling |

---

## Bundled Profile Definitions

### `generic-small`
```yaml
name: generic-small
cpus: 2
memory_kb: 8388608      # 8 GB
disks:
  - name: nvme0n1
    type: nvme
interfaces:
  - name: eth0
    speed_mbps: 10000
```

### `generic-medium`
```yaml
name: generic-medium
cpus: 4
memory_kb: 16777216     # 16 GB
disks:
  - name: nvme0n1
    type: nvme
interfaces:
  - name: eth0
    speed_mbps: 10000
```

### `generic-large`
```yaml
name: generic-large
cpus: 8
memory_kb: 33554432     # 32 GB
disks:
  - name: nvme0n1
    type: nvme
  - name: nvme1n1
    type: nvme
interfaces:
  - name: eth0
    speed_mbps: 10000
```

### `generic-xlarge`
```yaml
name: generic-xlarge
cpus: 16
memory_kb: 67108864     # 64 GB
disks:
  - name: nvme0n1
    type: nvme
  - name: nvme1n1
    type: nvme
interfaces:
  - name: eth0
    speed_mbps: 10000
  - name: eth1
    speed_mbps: 10000
```

### `compute-optimized`
```yaml
name: compute-optimized
cpus: 8
memory_kb: 16777216     # 16 GB
disks:
  - name: nvme0n1
    type: nvme
interfaces:
  - name: eth0
    speed_mbps: 10000
```

### `memory-optimized`
```yaml
name: memory-optimized
cpus: 4
memory_kb: 67108864     # 64 GB
disks:
  - name: nvme0n1
    type: nvme
interfaces:
  - name: eth0
    speed_mbps: 10000
```

### `storage-optimized`
```yaml
name: storage-optimized
cpus: 4
memory_kb: 16777216     # 16 GB
disks:
  - name: sda
    type: hdd
  - name: sdb
    type: hdd
  - name: sdc
    type: hdd
  - name: sdd
    type: hdd
interfaces:
  - name: eth0
    speed_mbps: 10000
```

---

## Profile Resolution Precedence

Hardware profile lookup uses the following order (highest to lowest):

```
1. -C / --config-dir directory (test fixture isolation)
2. ~/.pcp/pmlogsynth/profiles/
3. pmlogsynth/profiles/ (bundled package data)
```

Profile filenames MUST use the pattern `<name>.yaml` where `<name>` is the value of
the `name` field. Filenames with `.yml` extension are not supported.

If the same name appears in multiple sources, the highest-precedence source wins silently.

---

## Validation Rules

| Constraint | Error |
|-----------|-------|
| `name` is required | "hardware profile missing required field: name" |
| `cpus` must be a positive integer | "hardware profile 'X': cpus must be a positive integer" |
| `memory_kb` must be a positive integer | "hardware profile 'X': memory_kb must be a positive integer" |
| `disks` must have at least one entry | "hardware profile 'X': disks list must not be empty" |
| Each disk must have a `name` | "hardware profile 'X': disk entry missing required field: name" |
| `interfaces` must have at least one entry | "hardware profile 'X': interfaces list must not be empty" |
| Each interface must have a `name` | "hardware profile 'X': interface entry missing required field: name" |
| Profile file is malformed YAML (parse error) | "hardware profile 'X': YAML parse error: <message>" |
| Unknown top-level key | warning logged; not a hard error (forward compatibility) |

---

## `host.overrides` Merge Rules

When a workload profile specifies `host.profile` + `host.overrides`, the merge is:

```python
resolved = load_hardware_profile(host.profile)
resolved = dataclasses.replace(resolved, **host.overrides)
```

Only top-level `HardwareProfile` fields can be overridden. Deep merging of `disks[]` or
`interfaces[]` is not supported in Phase 1 — an override of `disks` replaces the entire
list.

Unknown keys in `overrides` are a hard validation error to prevent silent misconfiguration.
