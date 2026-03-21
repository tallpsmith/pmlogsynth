# Single-File Fleet Profiles

**Date:** 2026-03-21
**Status:** Approved

## Problem

Fleet archive generation currently requires up to 3 separate YAML files: a fleet
profile that references external workload profiles by relative file path. This makes
fleet definitions non-portable (can't share a single file) and harder to grok (must
read multiple files to understand the full intent).

## Decision

Combine everything into a single self-contained YAML file with a `profiles` section
containing named workload definitions. Replace the multi-file format entirely.

## New Schema

```yaml
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

### Key Schema Rules

- `profiles` is a top-level dict of named workload definitions
- Each profile value contains `phases` (same structure as standalone workload profiles)
- No `meta`, `host`, or `hardware` inside profile definitions — those are fleet-level
- `hosts.baseline` and `bad_actors.profiles[*]` are plain string names validated against
  `profiles` keys
- Named profiles enable reuse — the same profile name can appear in both baseline and
  bad-actor references

## Code Changes

### `fleet/models.py`

- `HostsConfig`: drop `baseline_path: Path`, `baseline` becomes a profile name string
- `BadActorsConfig`: drop `profile_paths: List[Path]`, `profiles` becomes list of profile names
- New `InlineProfile` dataclass holding parsed phase definitions
- `FleetProfile` gains `profiles: Dict[str, InlineProfile]`
- `HostAssignment`: drop `workload_path: Path`, keep `workload_rel: str` (profile name)

### `fleet/loader.py`

- New `_parse_profiles()` — validates the `profiles` section, parses each named entry
- `_parse_hosts()` — validates `baseline` is a key in `profiles` dict (no path resolution)
- `_parse_bad_actors()` — validates each profile name exists in `profiles` dict
- `load_fleet_profile()` — drops `fleet_dir` path resolution entirely
- No special old-format detection — missing `profiles` section raises standard
  `ValidationError` which is sufficient

### `fleet/orchestrator.py`

- Instead of reading workload profiles from disk via `assignment.workload_path`, builds
  `WorkloadProfile` in-memory from `FleetProfile.profiles[assignment.workload_rel]`
- Hardware resolution unchanged (still uses `ProfileResolver`)

### `fleet/assignment.py`

- `HostAssignment.workload_path` removed
- `workload_rel` remains as the profile name (used in manifest)

### `fleet/warnings.py`

- Simplifies dramatically or gets removed — inline profiles don't carry their own
  `meta.duration`/`meta.interval`/`host.profile` so there are no override conflicts

### `fleet/manifest.py`

- No structural change. `workload_rel` records the profile name instead of a filename.

### `cli.py`

- `fleet --validate` simplifies: no more checking external file existence

## Skill Changes

### `generate-fleet-profile` skill (significant rewrite)

- `SKILL.md`: Steps 3a (generate workload files) and 3b (generate fleet file) collapse
  into a single "generate the fleet YAML" step
- `references/fleet-schema.md`: Rewrite for `profiles` section and string-reference
  semantics
- `references/workload-profile-schema.md`: Retained as reference for what goes inside
  a named profile definition
- Validation step simplifies to a single `pmlogsynth fleet --validate` call

### `generate-profile` skill — unchanged

## Doc Changes

- `docs/profile-format.md` — Document fleet single-file format
- `README.md` — Update fleet mode section and examples
- `man/pmlogsynth.1` — Update fleet subcommand description and examples

## Test Changes

- `tests/fixtures/fleet/` — Rewrite `test-fleet.yaml` to be self-contained; delete
  separate `baseline.yaml` and `bad-cpu.yaml` fixture files
- All fleet unit/integration tests updated for new schema

## Migration

No backwards compatibility. The loader requires a `profiles` section — old-format files
without it will fail validation naturally with a standard `ValidationError`. No special
detection or migration guidance — the old format has minimal adoption.

## Not Doing

- No `format` version field (YAGNI)
- No YAML anchors/aliases
- No profile inheritance or override mechanism between named profiles
- No backwards compatibility shim
- No changes to standalone workload profile format
