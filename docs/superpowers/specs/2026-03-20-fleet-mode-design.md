# Fleet Mode — Design Specification

**Date:** 2026-03-20
**Status:** Superseded by `2026-03-21-single-file-fleet-profiles-design.md`

> **Note:** The multi-file fleet format described here has been replaced by a
> single self-contained YAML format with inline named workload profiles.
> See `2026-03-21-single-file-fleet-profiles-design.md` for the current design.

---

## Motivation

Generate a coherent set of PCP archives representing a multi-host fleet for:

1. **pmview-nextgen**: 3D visualization of fleet-scale performance data via pmproxy
2. **PCP training**: help people practice finding "bad actor" hosts using PCP tooling
3. **Visualization tool testing**: stress-test tools that consume multiple host archives

Primary driver: feeding fleet data into [pmview-nextgen](https://github.com/tallpsmith/pmview-nextgen) via a single pmproxy instance serving the archive directory.

## Approach

**Thin Orchestrator** — the `fleet` subcommand parses a fleet profile YAML, assigns
hosts to workload profiles (with random bad-actor selection), then calls the existing
`ArchiveWriter` once per host. No overlay engine, no merge logic — bad actors use
complete standalone workload profiles.

### Relationship to Phase 3 Spec

This design **supersedes** `pmlogsynth-phase3-spec.md` for the initial fleet
implementation. The Phase 3 spec describes a more complex architecture with anomaly
overlays, time-windowed fault injection, and multi-group host definitions. This design
intentionally simplifies to the minimum viable fleet: one host group, complete
standalone profiles for bad actors, no overlay merging. The fleet YAML schema is
different from the Phase 3 spec (`hosts:` + `bad_actors:` vs `groups:` with
`anomalies:`). Future enhancements may reintroduce Phase 3 concepts incrementally.

---

## 1. Fleet Profile Format

A fleet profile is a standalone YAML file, distinct from a workload profile. It
references workload profiles by path.

```yaml
# fleet: web-cluster.yaml
meta:
  name: web-cluster
  duration: 24h
  interval: 15s
  hostname_prefix: web        # hosts named web-01, web-02, ... web-NN
  hardware: generic-large     # hardware profile for all hosts

hosts:
  count: 20                   # total host count
  baseline: profiles/normal-web.yaml
  jitter: 0.05                # +/-5% per-host variation on stressor values

bad_actors:
  count: 2                    # how many hosts get a bad profile instead
  jitter: 0.15                # +/-15% — optional, defaults to hosts.jitter
  profiles:
    - profiles/cpu-saturated.yaml
    - profiles/memory-starved.yaml
```

### Fleet-Level Overrides

Fleet `meta` settings override the corresponding values in individual workload
profiles. The overridden fields are:

- `duration`
- `interval`
- `hardware`
- `timezone` (defaults to UTC)
- `hostname` (generated from `hostname_prefix` + zero-padded index)

The workload profile's stressor sections (cpu, memory, disk, network phases) are
used as-is — the fleet only overrides operational parameters.

**Override warnings:** When a referenced workload profile defines a value that
conflicts with the fleet setting, a warning is emitted (once per unique profile):

```
WARNING: workload profile 'profiles/normal-web.yaml' defines duration=3600 — overridden by fleet setting duration=86400
```

### Path Resolution

Workload profile paths are resolved relative to the fleet profile file's directory.

---

## 2. CLI Interface

```
pmlogsynth fleet [OPTIONS] FLEET_PROFILE

Arguments:
  FLEET_PROFILE              Path to fleet YAML profile

Options:
  -o, --output-dir PATH      Output directory [default: ./generated-archives/fleet-<name>]
  --seed INT                 PRNG seed for reproducible jitter and bad-actor assignment
  --jobs INT                 Parallel generation workers [default: CPU count]
  --dry-run                  Print host->profile assignments without generating
  --force                    Overwrite existing archive files
  --validate                 Validate fleet + referenced profiles, then exit
                             (incompatible with --force and --dry-run)
  --start TIMESTAMP          Archive start time (same formats as generate)
  -v, --verbose              Per-host progress output
  -C, --config-dir PATH      Additional hardware profile directory
```

### Dry-Run Output

```
Fleet: web-cluster (20 hosts, seed=42)

  web-01  baseline  profiles/normal-web.yaml      (jitter: x1.03)
  web-02  baseline  profiles/normal-web.yaml      (jitter: x0.97)
  ...
  web-13  BAD       profiles/cpu-saturated.yaml   (jitter: x1.01)
  ...
  web-18  BAD       profiles/memory-starved.yaml  (jitter: x0.98)
  ...
```

---

## 3. Output Layout & Fleet Manifest

Flat directory structure — no subdirectories:

```
generated-archives/fleet-web-cluster/
├── web-01.0
├── web-01.index
├── web-01.meta
│   ...
├── web-20.0
├── web-20.index
├── web-20.meta
└── fleet.manifest
```

### fleet.manifest

Machine-readable YAML listing every archive, its role, and metadata:

```yaml
meta:
  name: web-cluster
  generated: "2026-03-20T09:00:00Z"
  pmlogsynth_version: "1.0"
  seed: 42
  duration: 86400
  interval: 15
  hardware: generic-large
  host_count: 20

archives:
  - hostname: web-01
    profile: profiles/normal-web.yaml
    role: baseline
    jitter_factor: 1.03

  - hostname: web-13
    profile: profiles/cpu-saturated.yaml
    role: bad_actor
    jitter_factor: 1.01

  - hostname: web-18
    profile: profiles/memory-starved.yaml
    role: bad_actor
    jitter_factor: 0.98
```

---

## 4. Internal Architecture

### New modules

**`pmlogsynth/fleet.py`** — Profile loader and orchestrator:

- `FleetProfile` dataclass: meta, hosts config, bad actor config
- `load_fleet_profile(path)`: parse YAML, validate, resolve paths, emit override warnings
- `assign_hosts(fleet, seed)`: create `HostAssignment` list with random bad-actor selection
- `generate_fleet(fleet, assignments, output_dir, args)`: loop/parallelize over assignments,
  call existing `ArchiveWriter` per host, write `fleet.manifest`

**`pmlogsynth/jitter.py`** — Per-host stressor variation:

- `apply_jitter(profile, factor)`: multiply all numeric stressor values by factor,
  clamp ratios to [0.0, 1.0] and counters to >= 0. Returns new `WorkloadProfile`.
  Pure function, no mutation.

### Per-host WorkloadProfile construction

`generate_fleet` produces a per-host `WorkloadProfile` by:

1. Loading the workload profile via existing `ProfileLoader.from_file()`
2. Using `dataclasses.replace()` to override `meta.hostname`, `meta.duration`,
   `meta.interval`, `meta.timezone` with fleet-level values
3. Passing through `apply_jitter()` to apply the host's jitter factor
4. Handing the resulting `WorkloadProfile` to `ArchiveWriter` as normal

Hardware profile resolution uses `ProfileResolver` with the fleet-level hardware name.
No changes to `ProfileLoader` or `ArchiveWriter` — all construction happens in `fleet.py`.

### Changes to existing modules

- **`cli.py`**: Replace the `fleet` stub parser (line 134) with a fully-wired subparser
  via a new `_add_fleet_args()` function (mirroring `_add_generate_args()`). Replace
  the stub handler with a call to `generate_fleet()`.
- **`profile.py`**: No changes — `WorkloadProfile` is a dataclass, `dataclasses.replace()`
  handles per-host construction without modifying the loader.
- **`writer.py`**: No changes

### What we're NOT building

- No `overlay.py` — no anomaly overlay merge logic
- No new domain models
- No changes to `timeline.py` or `sampler.py`

---

## 5. Jitter Design

1. Fleet profile specifies `jitter: 0.05` (baseline) and optionally `bad_actors.jitter: 0.15`
2. Per-host PRNG seeded deterministically: `hashlib.sha256(f'{seed}:{hostname}'.encode())`
   truncated to an integer. **Do NOT use Python's built-in `hash()`** — it is randomized
   across processes (PYTHONHASHSEED) and would break reproducibility.
3. Single jitter factor drawn per host: `Normal(mean=1.0, stddev=jitter)`
4. Every numeric stressor value in every phase multiplied by that factor
5. Post-jitter clamping: ratios to [0.0, 1.0], counters >= 0
6. Bad actors get their own (potentially higher) jitter applied to their different profile

Single factor per host (not per field) gives coherent variation — a "slightly busier
box" is busier across the board, not randomly hot on CPU but cold on memory.

### Ratio vs Unrestricted Fields

Jitter clamping requires knowing which stressor fields are ratios (clamped `[0, 1]`)
vs throughput/count fields (clamped `>= 0` only):

**Ratio fields** (clamp `[0.0, 1.0]`): `utilization`, `user_ratio`, `sys_ratio`,
`iowait_ratio`, `steal_ratio`, `used_ratio`, `cache_ratio`, `noise`, `error_rate`

**Throughput/count fields** (clamp `>= 0`): `read_mbps`, `write_mbps`, `iops_read`,
`iops_write`, `rx_mbps`, `tx_mbps`, `pps_rx`, `pps_tx`, `avg_request_size_kb`,
`load_1min`, `load_5min`, `load_15min`

---

## 6. Testing Strategy

### Tier 1 — Unit tests (`tests/unit/test_fleet.py`)

- Fleet profile parsing: valid loads, missing fields raise `ValidationError`
- Override warnings: conflicting workload profile values emit warnings
- Host assignment: correct count, correct hostnames, deterministic with seed
- Reproducibility: same seed = same assignments and jitter factors
- Bad actor pool selection: random from pool, respects count
- Jitter application: `apply_jitter(profile, 1.05)` multiplies stressor values
- Jitter clamping: ratios [0.0, 1.0], counters >= 0
- Independent jitter: bad actor stddev differs from baseline stddev
- Profile path resolution: relative to fleet file directory
- Dry-run output: correct mapping, no archives written
- Validate mode: catches broken paths, invalid hardware names

### Tier 2 — Integration tests (`tests/integration/test_fleet_integration.py`)

- Full generation with mocked PCP: 3-host fleet, `ArchiveWriter.write()` called 3x
- Fleet manifest written and well-formed
- Override application: fleet-level values used, not workload profile values
- Parallel generation: `--jobs=2` dispatches correctly

### Tier 3 — E2E tests (`tests/e2e/test_fleet_e2e.py`)

- Generate 3-host fleet, all archive triplets exist
- `pmlogcheck` passes on every archive
- Seed reproducibility: two `--seed 42` runs produce identical archives
- Manifest roles match actual profile assignments

Tier 3 auto-skipped if PCP not installed.

---

## Future Enhancements

- Multiple host groups with different hardware profiles
- Anomaly overlays with time-windowed fault injection
- Per-field jitter (independent variation per stressor dimension)
- Rolling/cascading faults across hosts
- Fleet profile generation via natural language (`--prompt`)
