# Single-File Fleet Profiles Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace multi-file fleet profiles with a single self-contained YAML file containing named inline workload profiles.

**Architecture:** Add a `profiles` top-level section to fleet YAML containing named workload definitions. `hosts.baseline` and `bad_actors.profiles` become string references into that dict. The loader resolves profiles in-memory instead of reading external files. The orchestrator builds `WorkloadProfile` objects from inline data rather than from disk.

**Tech Stack:** Python 3.8+, PyYAML, pytest, dataclasses

**Spec:** `docs/superpowers/specs/2026-03-21-single-file-fleet-profiles-design.md`

---

## Chunk 1: Models and Loader

### Task 1: Update Fleet Data Models

**Files:**
- Modify: `pmlogsynth/fleet/models.py`
- Test: `tests/unit/test_fleet.py`

- [ ] **Step 1: Write failing tests for new model structure**

Add to `tests/unit/test_fleet.py`:

```python
class TestInlineProfile:
    """Tests for the InlineProfile dataclass."""

    def test_inline_profile_holds_phases_raw(self) -> None:
        from pmlogsynth.fleet.models import InlineProfile

        phases = [{"name": "steady", "duration": 600, "cpu": {"utilization": 0.5}}]
        profile = InlineProfile(phases=phases)
        assert profile.phases == phases

    def test_inline_profile_default_empty_phases(self) -> None:
        from pmlogsynth.fleet.models import InlineProfile

        profile = InlineProfile(phases=[])
        assert profile.phases == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestInlineProfile -v`
Expected: FAIL — `InlineProfile` does not exist

- [ ] **Step 3: Add InlineProfile dataclass and update models**

In `pmlogsynth/fleet/models.py`:

1. Add `InlineProfile` dataclass:
```python
@dataclass
class InlineProfile:
    """A named workload profile defined inline in a fleet file."""
    phases: List[Dict[str, Any]]
```

2. Update imports: add `Dict` and `Any` to `typing`, remove `Path` from `pathlib`

3. Update `HostsConfig` — remove `baseline_path: Path` field:
```python
@dataclass
class HostsConfig:
    """Baseline host configuration."""
    count: int
    baseline: str
    jitter: float = 0.0
```

4. Update `BadActorsConfig` — remove `profile_paths: List[Path]` field:
```python
@dataclass
class BadActorsConfig:
    """Bad-actor host configuration."""
    count: int = 0
    jitter: float = 0.0
    profiles: List[str] = field(default_factory=list)
```

5. Update `FleetProfile` — add `profiles` dict:
```python
@dataclass
class FleetProfile:
    """Parsed fleet profile — the full fleet specification."""
    meta: FleetMeta
    hosts: HostsConfig
    bad_actors: BadActorsConfig
    profiles: Dict[str, InlineProfile] = field(default_factory=dict)
```

6. Update `HostAssignment` — remove `workload_path: Path`:
```python
@dataclass
class HostAssignment:
    """One host's role, jitter factor, and workload profile name."""
    hostname: str
    role: str  # "baseline" or "bad_actor"
    jitter_factor: float
    workload_rel: str
```

- [ ] **Step 4: Run tests to verify InlineProfile tests pass**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestInlineProfile -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/fleet/models.py tests/unit/test_fleet.py
git commit -m "Add InlineProfile, remove file-path fields from fleet models

Prepare models for single-file fleet profiles: add InlineProfile dataclass,
remove baseline_path/profile_paths/workload_path fields that referenced
external files."
```

---

### Task 2: Rewrite Test Fixture and Fleet Loader (Atomic)

**Important:** The fixture and loader must change together. Changing the fixture without
the loader (or vice versa) would break all tests. This task is atomic.

**Files:**
- Modify: `tests/fixtures/fleet/test-fleet.yaml`
- Delete: `tests/fixtures/fleet/baseline.yaml`
- Delete: `tests/fixtures/fleet/bad-cpu.yaml`
- Modify: `pmlogsynth/fleet/loader.py`
- Modify: `tests/unit/test_fleet.py`

- [ ] **Step 1: Rewrite test fixture as self-contained single file**

Replace `tests/fixtures/fleet/test-fleet.yaml` with:

```yaml
meta:
  name: test-fleet
  duration: 600
  interval: 60
  hostname_prefix: host
  hardware: generic-small

profiles:
  baseline:
    phases:
      - name: steady
        duration: 600
        cpu:
          utilization: 0.50
          user_ratio: 0.70
          sys_ratio: 0.20
          iowait_ratio: 0.10
        memory:
          used_ratio: 0.40
          cache_ratio: 0.20
        disk:
          read_mbps: 10.0
          write_mbps: 5.0
        network:
          rx_mbps: 100.0
          tx_mbps: 50.0
          error_rate: 0.001

  bad-cpu:
    phases:
      - name: saturated
        duration: 600
        cpu:
          utilization: 0.96
          user_ratio: 0.85
          sys_ratio: 0.10
          iowait_ratio: 0.05
        memory:
          used_ratio: 0.70
          cache_ratio: 0.10

hosts:
  count: 5
  baseline: baseline
  jitter: 0.05

bad_actors:
  count: 1
  jitter: 0.15
  profiles:
    - bad-cpu
```

Delete the old separate workload profile fixtures:
```bash
rm tests/fixtures/fleet/baseline.yaml tests/fixtures/fleet/bad-cpu.yaml
```

- [ ] **Step 2: Write failing tests for new loader behaviour**

Rewrite the `TestLoadFleetProfile` class in `tests/unit/test_fleet.py`. The key changes:
- `test_loads_valid_fleet_profile`: verify `fleet.profiles` dict has expected keys, remove `baseline_path` assertions
- `test_baseline_references_missing_profile_raises`: new test — `hosts.baseline` points to a name not in `profiles`
- `test_bad_actor_references_missing_profile_raises`: new test
- `test_workload_paths_resolved_relative_to_fleet_file`: DELETE this test (no more file paths)
- Keep existing meta/hosts validation tests but update inline YAML strings to include a minimal `profiles` section

Updated/new tests:

```python
class TestLoadFleetProfile:
    """Tests for load_fleet_profile YAML parsing."""

    def test_loads_valid_fleet_profile(self) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assert fleet.meta.name == "test-fleet"
        assert fleet.meta.duration == 600
        assert fleet.meta.interval == 60
        assert fleet.meta.hostname_prefix == "host"
        assert fleet.meta.hardware == "generic-small"
        assert fleet.hosts.count == 5
        assert fleet.hosts.baseline == "baseline"
        assert fleet.hosts.jitter == 0.05
        assert fleet.bad_actors.count == 1
        assert fleet.bad_actors.jitter == 0.15
        assert len(fleet.bad_actors.profiles) == 1
        assert "baseline" in fleet.profiles
        assert "bad-cpu" in fleet.profiles

    def test_profiles_contain_phases(self) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assert len(fleet.profiles["baseline"].phases) == 1
        assert fleet.profiles["baseline"].phases[0]["name"] == "steady"
        assert len(fleet.profiles["bad-cpu"].phases) == 1
        assert fleet.profiles["bad-cpu"].phases[0]["name"] == "saturated"

    def test_missing_profiles_section_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 1\n  baseline: foo\n"
        )
        with pytest.raises(ValidationError, match="profiles"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_baseline_references_missing_profile_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 1\n  baseline: bar\n"
        )
        with pytest.raises(ValidationError, match="bar.*not found in profiles"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actor_references_missing_profile_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 2\n  baseline: foo\n"
            "bad_actors:\n  count: 1\n  profiles:\n    - missing\n"
        )
        with pytest.raises(ValidationError, match="missing.*not found in profiles"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_missing_meta_name_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 1\n  baseline: foo\n"
        )
        with pytest.raises(ValidationError, match="meta.name"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_missing_hosts_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
        )
        with pytest.raises(ValidationError, match="hosts"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actors_count_exceeds_host_count_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 2\n  baseline: foo\n"
            "bad_actors:\n  count: 3\n  profiles:\n    - foo\n"
        )
        with pytest.raises(ValidationError, match="bad_actors.count"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actors_defaults_jitter_to_hosts_jitter(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 3\n  baseline: foo\n  jitter: 0.08\n"
            "bad_actors:\n  count: 1\n  profiles:\n    - foo\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.bad_actors.jitter == 0.08

    def test_no_bad_actors_section_is_valid(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 3\n  baseline: foo\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.bad_actors.count == 0
        assert fleet.bad_actors.profiles == []

    def test_duration_accepts_duration_strings(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 24h\n  interval: 15s\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 1\n  baseline: foo\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.meta.duration == 86400
        assert fleet.meta.interval == 15

    def test_profile_with_empty_phases_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "profiles:\n  foo:\n    phases: []\n"
            "hosts:\n  count: 1\n  baseline: foo\n"
        )
        with pytest.raises(ValidationError, match="phases.*non-empty"):
            load_fleet_profile(tmp_path / "bad.yaml")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestLoadFleetProfile -v`
Expected: FAIL — loader still expects old format

- [ ] **Step 4: Rewrite the loader**

Replace `pmlogsynth/fleet/loader.py` with:

```python
"""Fleet profile YAML parsing and validation."""

from pathlib import Path
from typing import Any, Dict

import yaml

from pmlogsynth.fleet.models import (
    BadActorsConfig,
    FleetMeta,
    FleetProfile,
    HostsConfig,
    InlineProfile,
)
from pmlogsynth.profile import ValidationError, parse_duration


def _parse_fleet_meta(raw: Dict[str, Any]) -> FleetMeta:
    """Parse and validate the meta section of a fleet profile."""
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        raise ValidationError("fleet profile missing 'meta' section")

    name = meta.get("name")
    if not name:
        raise ValidationError("fleet profile missing 'meta.name'")

    duration_raw = meta.get("duration")
    if duration_raw is None:
        raise ValidationError("fleet profile missing 'meta.duration'")
    duration = parse_duration(duration_raw)

    interval_raw = meta.get("interval")
    if interval_raw is None:
        raise ValidationError("fleet profile missing 'meta.interval'")
    interval = parse_duration(interval_raw)

    hostname_prefix = meta.get("hostname_prefix")
    if not hostname_prefix:
        raise ValidationError("fleet profile missing 'meta.hostname_prefix'")

    hardware = meta.get("hardware")
    if not hardware:
        raise ValidationError("fleet profile missing 'meta.hardware'")

    return FleetMeta(
        name=str(name),
        duration=duration,
        interval=interval,
        hostname_prefix=str(hostname_prefix),
        hardware=str(hardware),
    )


def _parse_profiles(raw: Dict[str, Any]) -> Dict[str, InlineProfile]:
    """Parse and validate the profiles section of a fleet profile."""
    section = raw.get("profiles")
    if not isinstance(section, dict):
        raise ValidationError("fleet profile missing 'profiles' section")

    profiles = {}  # type: Dict[str, InlineProfile]
    for name, body in section.items():
        if not isinstance(body, dict):
            raise ValidationError(
                "profile '{}' must be a mapping".format(name)
            )
        phases = body.get("phases")
        if not isinstance(phases, list) or len(phases) == 0:
            raise ValidationError(
                "profile '{}' phases must be a non-empty list".format(name)
            )
        profiles[str(name)] = InlineProfile(phases=phases)

    return profiles


def _parse_hosts(
    raw: Dict[str, Any],
    profiles: Dict[str, InlineProfile],
) -> HostsConfig:
    """Parse and validate the hosts section of a fleet profile."""
    hosts = raw.get("hosts")
    if not isinstance(hosts, dict):
        raise ValidationError("fleet profile missing 'hosts' section")

    count = hosts.get("count")
    if not isinstance(count, int) or count < 1:
        raise ValidationError("hosts.count must be a positive integer")

    baseline = hosts.get("baseline")
    if not baseline:
        raise ValidationError("hosts.baseline is required")
    baseline = str(baseline)

    if baseline not in profiles:
        raise ValidationError(
            "hosts.baseline '{}' not found in profiles".format(baseline)
        )

    jitter = float(hosts.get("jitter", 0.0))

    return HostsConfig(
        count=count,
        baseline=baseline,
        jitter=jitter,
    )


def _parse_bad_actors(
    raw: Dict[str, Any],
    hosts_config: HostsConfig,
    profiles: Dict[str, InlineProfile],
) -> BadActorsConfig:
    """Parse and validate the bad_actors section of a fleet profile."""
    section = raw.get("bad_actors")
    if section is None:
        return BadActorsConfig()

    if not isinstance(section, dict):
        raise ValidationError("bad_actors must be a mapping")

    count = int(section.get("count", 0))
    if count > hosts_config.count:
        raise ValidationError(
            "bad_actors.count ({}) exceeds hosts.count ({})".format(
                count, hosts_config.count
            )
        )

    # Default bad_actors jitter to hosts jitter if not specified
    jitter_raw = section.get("jitter")
    if jitter_raw is not None:
        jitter = float(jitter_raw)
    else:
        jitter = hosts_config.jitter

    profiles_raw = section.get("profiles", [])
    profile_names = [str(p) for p in profiles_raw]

    for name in profile_names:
        if name not in profiles:
            raise ValidationError(
                "bad_actors profile '{}' not found in profiles".format(name)
            )

    return BadActorsConfig(
        count=count,
        jitter=jitter,
        profiles=profile_names,
    )


def load_fleet_profile(path: Path) -> FleetProfile:
    """Load and validate a fleet profile YAML file.

    All workload profiles are defined inline in the 'profiles' section.
    References in hosts.baseline and bad_actors.profiles are validated
    against profile names.
    """
    text = path.read_text()
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValidationError("fleet profile must be a YAML mapping")

    meta = _parse_fleet_meta(raw)
    profiles = _parse_profiles(raw)
    hosts = _parse_hosts(raw, profiles)
    bad_actors = _parse_bad_actors(raw, hosts, profiles)

    return FleetProfile(
        meta=meta, hosts=hosts, bad_actors=bad_actors, profiles=profiles,
    )
```

- [ ] **Step 5: Run loader tests to verify they pass**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestLoadFleetProfile -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/fleet/loader.py tests/unit/test_fleet.py tests/fixtures/fleet/
git commit -m "Rewrite fleet loader and fixtures for single-file profiles

Convert fleet profile format from multi-file (external workload YAML
references) to single-file (inline named profiles). Fixture, loader,
and tests updated atomically."
```

---

### Task 3: Update Host Assignment

**Files:**
- Modify: `pmlogsynth/fleet/assignment.py`
- Modify: `tests/unit/test_fleet.py`

- [ ] **Step 1: Update TestAssignHosts tests**

The tests that load from fixture need updating because:
- `HostAssignment` no longer has `workload_path` — use `workload_rel` (profile name)
- Remove `test_bad_actor_profiles_selected_from_pool` assertion on `workload_path.name`
- Replace with assertion on `workload_rel`
- Tests using `tmp_path` inline YAML need `profiles` section added

Update `test_bad_actor_profiles_selected_from_pool`:
```python
    def test_bad_actor_profiles_selected_from_pool(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        bad = [a for a in assignments if a.role == "bad_actor"]
        for b in bad:
            assert b.workload_rel in ("bad-cpu",)
```

Update `test_no_bad_actors_all_baseline`:
```python
    def test_no_bad_actors_all_baseline(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: srv\n  hardware: generic-small\n"
            "profiles:\n  base:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 3\n  baseline: base\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assignments = assign_hosts(fleet, seed=1)
        assert all(a.role == "baseline" for a in assignments)
```

Update `test_zero_pad_width_scales_with_count`:
```python
    def test_zero_pad_width_scales_with_count(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: srv\n  hardware: generic-small\n"
            "profiles:\n  base:\n    phases:\n      - name: a\n        duration: 60\n"
            "hosts:\n  count: 100\n  baseline: base\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assignments = assign_hosts(fleet, seed=1)
        assert assignments[0].hostname == "srv-001"
        assert assignments[99].hostname == "srv-100"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestAssignHosts -v`
Expected: FAIL — `HostAssignment` constructor changed

- [ ] **Step 3: Update assignment.py**

In `pmlogsynth/fleet/assignment.py`, remove references to `workload_path` and `profile_paths`:

```python
"""Host assignment — role selection, jitter factors, and stable seeding."""

import hashlib
import random
from typing import List, Optional

from pmlogsynth.fleet.models import FleetProfile, HostAssignment


def _stable_host_seed(fleet_name: str, hostname: str, seed: int) -> int:
    """Derive a deterministic per-host seed using SHA-256."""
    digest = hashlib.sha256(
        "{}:{}:{}".format(fleet_name, hostname, seed).encode()
    ).hexdigest()
    return int(digest[:16], 16)


def assign_hosts(
    fleet: FleetProfile,
    seed: Optional[int] = None,
) -> List[HostAssignment]:
    """Assign hostnames, roles, and jitter factors to each host."""
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    rng = random.Random(seed)
    count = fleet.hosts.count
    pad_width = max(2, len(str(count)))

    bad_actor_indices = set(rng.sample(range(count), fleet.bad_actors.count))

    assignments = []  # type: List[HostAssignment]
    for i in range(count):
        hostname = "{}-{}".format(
            fleet.meta.hostname_prefix,
            str(i + 1).zfill(pad_width),
        )
        is_bad = i in bad_actor_indices

        if is_bad:
            role = "bad_actor"
            jitter_stddev = fleet.bad_actors.jitter
            profile_idx = rng.randrange(len(fleet.bad_actors.profiles))
            workload_rel = fleet.bad_actors.profiles[profile_idx]
        else:
            role = "baseline"
            jitter_stddev = fleet.hosts.jitter
            workload_rel = fleet.hosts.baseline

        host_seed = _stable_host_seed(fleet.meta.name, hostname, seed)
        host_rng = random.Random(host_seed)
        jitter_factor = host_rng.gauss(1.0, jitter_stddev)

        assignments.append(
            HostAssignment(
                hostname=hostname,
                role=role,
                jitter_factor=jitter_factor,
                workload_rel=workload_rel,
            )
        )

    return assignments
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestAssignHosts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/fleet/assignment.py tests/unit/test_fleet.py
git commit -m "Update host assignment to use profile names instead of paths

HostAssignment no longer carries a workload_path — workload_rel is the
profile name referencing the fleet's inline profiles dict."
```

---

## Chunk 2: Orchestrator, Warnings, Display, and __init__

### Task 4: Update Orchestrator to Build WorkloadProfile from Inline Data

**Files:**
- Modify: `pmlogsynth/fleet/orchestrator.py`
- Modify: `tests/integration/test_fleet_integration.py`

- [ ] **Step 1: Update integration tests**

All integration tests use `load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")` which now returns the new format. The key change is in the orchestrator: it must build `WorkloadProfile` from inline phase data instead of reading files from disk.

The existing tests should work with minimal changes since they mock the `ArchiveWriter`. The main thing: `test_fleet_overrides_applied_to_profiles` verifies that `profile.meta.hostname`, `profile.meta.duration`, and `profile.meta.interval` are overridden — this should still work.

The existing integration tests _should_ pass without changes since `_build_workload_yaml`
bakes hostname/duration/interval directly into the YAML that `WorkloadProfile.from_string()`
parses. The mock `ArchiveWriter` captures the resulting profile object. Verify by running:

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/integration/test_fleet_integration.py -v`
Expected: FAIL — orchestrator still tries to use `assignment.workload_path` which no longer exists

If any test fails for reasons beyond `workload_path` removal (e.g. missing fields in
the constructed YAML), diagnose and fix the `_build_workload_yaml` dict before proceeding.

- [ ] **Step 2: Rewrite the orchestrator**

The key change: instead of `assignment.workload_path.read_text()` → `WorkloadProfile.from_string()`, we build a `WorkloadProfile` directly from the inline profile data and fleet meta.

```python
"""Fleet archive generation orchestrator."""

import importlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from pmlogsynth.fleet.manifest import write_manifest
from pmlogsynth.fleet.models import FleetProfile, HostAssignment


def _build_workload_yaml(
    fleet: FleetProfile,
    assignment: HostAssignment,
) -> str:
    """Build a standalone workload profile YAML string from inline data.

    Constructs a complete workload profile dict with fleet-level meta
    overrides, then serialises to YAML for WorkloadProfile.from_string().
    """
    inline = fleet.profiles[assignment.workload_rel]

    workload = {
        "meta": {
            "hostname": assignment.hostname,
            "duration": fleet.meta.duration,
            "interval": fleet.meta.interval,
        },
        "host": {
            "profile": fleet.meta.hardware,
        },
        "phases": inline.phases,
    }  # type: Dict[str, Any]

    return yaml.dump(workload, default_flow_style=False, sort_keys=False)


def generate_fleet(
    fleet: FleetProfile,
    assignments: List[HostAssignment],
    output_dir: Path,
    seed: Optional[int],
    jobs: int = 1,
    force: bool = False,
    start: Optional[datetime] = None,
    verbose: bool = False,
    config_dir: Optional[Path] = None,
) -> None:
    """Generate one PCP archive per host, then write fleet.manifest."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Lazy import writer module (avoid PCP dependency at parse time)
    _writer_mod = importlib.import_module("pmlogsynth.writer")
    ArchiveWriter = _writer_mod.ArchiveWriter

    from dataclasses import replace

    from pmlogsynth.jitter import apply_jitter
    from pmlogsynth.profile import ProfileResolver, WorkloadProfile
    from pmlogsynth.sampler import ValueSampler
    from pmlogsynth.timeline import TimelineSequencer

    # Resolve hardware profile once (shared across all hosts)
    resolver = ProfileResolver(config_dir=config_dir)
    hardware = resolver.resolve(fleet.meta.hardware)

    def _generate_one(assignment: HostAssignment) -> None:
        """Generate a single host archive."""
        workload_yaml = _build_workload_yaml(fleet, assignment)
        profile = WorkloadProfile.from_string(
            workload_yaml, config_dir=config_dir,
        )

        profile = apply_jitter(profile, assignment.jitter_factor)

        timeline = TimelineSequencer(profile).expand(start_time=start)
        sampler = ValueSampler(noise=profile.meta.noise)

        output_path = str(output_dir / assignment.hostname)
        writer = ArchiveWriter(
            output_path=output_path,
            profile=profile,
            hardware=hardware,
            force=force,
        )
        writer.write(timeline=timeline, sampler=sampler)

        if verbose:
            print(
                "  generated: {} ({})".format(
                    assignment.hostname, assignment.role,
                ),
                file=sys.stderr,
            )

    # Generate archives — sequential by default.
    # NOTE: PCP's pmiLogImport C library is not thread-safe.
    # See https://github.com/tallpsmith/pmlogsynth/issues/16
    if jobs <= 1:
        for assignment in assignments:
            _generate_one(assignment)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(_generate_one, a): a for a in assignments
            }
            for future in as_completed(futures):
                future.result()

    # Write manifest
    write_manifest(
        output_dir / "fleet.manifest", fleet, assignments, seed=seed,
    )
```

Note: The `_build_workload_yaml` approach re-serialises inline data to YAML and feeds it through `WorkloadProfile.from_string()`. This reuses all existing validation and parsing rather than duplicating it. The fleet meta (hostname, duration, interval, hardware) is baked in directly — no more post-hoc `replace()` overrides.

- [ ] **Step 3: Run integration tests**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/integration/test_fleet_integration.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pmlogsynth/fleet/orchestrator.py
git commit -m "Build WorkloadProfile from inline data instead of external files

Orchestrator constructs workload YAML from fleet.profiles entries and
fleet-level meta, then feeds it through WorkloadProfile.from_string().
No more reading workload profiles from disk."
```

---

### Task 5: Simplify Warnings Module

**Files:**
- Modify: `pmlogsynth/fleet/warnings.py`
- Modify: `tests/unit/test_fleet.py`

- [ ] **Step 1: Update warning tests**

With inline profiles, there are no external files carrying conflicting durations/intervals/hardware. The `check_override_warnings` function becomes a no-op. Replace the test class:

```python
class TestOverrideWarnings:
    """Override warnings are no longer applicable with inline profiles."""

    def test_check_override_warnings_is_noop(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        from pmlogsynth.fleet import check_override_warnings, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        with caplog.at_level(logging.WARNING):
            check_override_warnings(fleet)
        assert len(caplog.records) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestOverrideWarnings -v`
Expected: FAIL — old implementation tries to read external files

- [ ] **Step 3: Replace warnings.py with a no-op**

```python
"""Override warning checks — retained as no-op for API compatibility.

With inline profiles, fleet-level meta is the only source of truth for
duration/interval/hardware. There are no external files to conflict with.
"""

from pmlogsynth.fleet.models import FleetProfile


def check_override_warnings(fleet: FleetProfile) -> None:
    """No-op — inline profiles cannot conflict with fleet meta."""
    pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestOverrideWarnings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/fleet/warnings.py tests/unit/test_fleet.py
git commit -m "Simplify override warnings to no-op

Inline profiles don't carry their own meta, so there's nothing to
conflict with fleet-level settings."
```

---

### Task 6: Update Display and __init__

**Files:**
- Modify: `pmlogsynth/fleet/display.py` (no changes needed — uses `workload_rel` which still exists)
- Modify: `pmlogsynth/fleet/__init__.py` — add `InlineProfile` to exports

- [ ] **Step 1: Run dry-run test to verify it passes**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestDryRun -v`
Expected: PASS (display.py only uses `workload_rel` and `hostname` which are unchanged)

- [ ] **Step 2: Run manifest tests**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py::TestWriteManifest -v`
Expected: PASS (manifest uses `workload_rel` which is still a string)

- [ ] **Step 3: Update __init__.py exports**

Add `InlineProfile` to `pmlogsynth/fleet/__init__.py`:

```python
from pmlogsynth.fleet.models import (
    BadActorsConfig,
    FleetMeta,
    FleetProfile,
    HostAssignment,
    HostsConfig,
    InlineProfile,
)

__all__ = [
    "assign_hosts",
    "BadActorsConfig",
    "check_override_warnings",
    "FleetMeta",
    "FleetProfile",
    "generate_fleet",
    "HostAssignment",
    "HostsConfig",
    "InlineProfile",
    "load_fleet_profile",
    "print_dry_run",
    "write_manifest",
]
```

- [ ] **Step 4: Run full unit test suite**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/unit/test_fleet.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full integration test suite**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run pytest tests/integration/test_fleet_integration.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/fleet/__init__.py
git commit -m "Export InlineProfile from fleet package"
```

---

## Chunk 3: Quality Gate, Skills, and Docs

### Task 7: Run Full Quality Gate

**Files:** None (verification only)

- [ ] **Step 1: Run mypy**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run mypy pmlogsynth/`
Expected: PASS — no type errors

If there are type errors from removed fields (e.g. code elsewhere referencing `baseline_path`), fix them.

- [ ] **Step 2: Run ruff**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && uv run ruff check .`
Expected: PASS

- [ ] **Step 3: Run pre-commit.sh**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && ./pre-commit.sh`
Expected: ALL GREEN

- [ ] **Step 4: Fix any issues and commit**

If anything fails, fix and commit with an appropriate message.

---

### Task 8: Update generate-fleet-profile Skill

**Files:**
- Modify: `.claude/skills/generate-fleet-profile/SKILL.md`
- Modify: `.claude/skills/generate-fleet-profile/references/fleet-schema.md`

- [ ] **Step 1: Rewrite fleet-schema.md**

Update `.claude/skills/generate-fleet-profile/references/fleet-schema.md` to document the new single-file format with `profiles` section. Replace all references to external file paths with profile name references. Remove all mentions of "resolved relative to the fleet profile file's directory".

Key sections to update:
- Top-level structure: add `profiles` section
- `hosts.baseline`: "string — name of a profile defined in the `profiles` section"
- `bad_actors.profiles`: "list of strings — names of profiles in the `profiles` section"
- Complete example: self-contained single file
- Validation rules: profile name reference validation instead of file existence checks

- [ ] **Step 2: Rewrite SKILL.md**

Update `.claude/skills/generate-fleet-profile/SKILL.md`:
- Step 3: Collapse 3a (generate workload files) and 3b (generate fleet file) into a single step — "Generate the fleet YAML with inline profiles"
- Step 4: Save a single file instead of multiple files
- Step 5: Validate with a single `pmlogsynth fleet --validate` call (no separate workload validation)
- Remove all references to generating separate workload profile files
- Update the example output to show single-file format

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/generate-fleet-profile/
git commit -m "Update fleet skill for single-file profile format

Skill now generates one self-contained YAML file with inline workload
profiles instead of coordinating multiple files."
```

---

### Task 9: Update Documentation

**Files:**
- Modify: `README.md` — fleet mode section
- Modify: `man/pmlogsynth.1` — fleet subcommand description and examples
- Modify: `docs/profile-format.md` — if fleet format is documented here

- [ ] **Step 1: Update README fleet section**

Find the fleet mode section in `README.md` and update examples to show single-file format. Replace any multi-file examples with the new self-contained format.

- [ ] **Step 2: Update man page**

Update `man/pmlogsynth.1` fleet section to describe the new format.

- [ ] **Step 3: Update profile-format.md if applicable**

If `docs/profile-format.md` documents the fleet format, update it.

- [ ] **Step 4: Commit**

```bash
git add README.md man/pmlogsynth.1 docs/profile-format.md
git commit -m "Update docs for single-file fleet profiles

README, man page, and profile format docs now show the self-contained
fleet YAML format with inline workload definitions."
```

---

### Task 10: Update Design Spec for Fleet Mode

**Files:**
- Modify: `docs/superpowers/specs/2026-03-20-fleet-mode-design.md` — add note about superseded format

- [ ] **Step 1: Add superseded note**

Add a note at the top of the original fleet mode design spec indicating the multi-file format has been replaced by single-file format, referencing `2026-03-21-single-file-fleet-profiles-design.md`.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-03-20-fleet-mode-design.md
git commit -m "Mark fleet mode spec as superseded by single-file design"
```

---

### Task 11: Final Quality Gate

- [ ] **Step 1: Final pre-commit run**

Run: `cd /Volumes/My\ Shared\ Files/pmlogsynth && ./pre-commit.sh`
Expected: ALL GREEN

- [ ] **Step 2: Clean up generated-archives (local only)**

`generated-archives/` is gitignored — no commit needed. Manually delete any old
multi-file fleet YAML files from `generated-archives/` if present.

**Note on `cli.py`:** No changes are needed. The `_cmd_fleet` function calls
`check_override_warnings(fleet)` which is now a no-op, and `load_fleet_profile()`
handles all validation. The import chain is intentionally preserved.
