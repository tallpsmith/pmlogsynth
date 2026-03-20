# Fleet Mode Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate coherent multi-host PCP archive sets from a single fleet profile YAML, with random bad-actor assignment and per-host jitter.

**Architecture:** Thin orchestrator pattern — new `fleet.py` parses fleet YAML, `jitter.py` applies per-host stressor variation, then the existing `ArchiveWriter` is called once per host. No changes to profile.py, writer.py, timeline.py, or sampler.py.

**Tech Stack:** Python 3.8+, PyYAML, hashlib (stdlib), concurrent.futures (stdlib), dataclasses (stdlib)

**Design Spec:** `docs/superpowers/specs/2026-03-20-fleet-mode-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pmlogsynth/jitter.py` | Create | Pure function: apply multiplicative jitter to WorkloadProfile stressor fields |
| `pmlogsynth/fleet.py` | Create | Fleet profile dataclasses, YAML loader, host assignment, orchestrator, manifest writer |
| `pmlogsynth/cli.py` | Modify (lines 131-134, 395-407) | Wire fleet subparser args, replace stub handler |
| `tests/unit/test_jitter.py` | Create | Unit tests for jitter application and clamping |
| `tests/unit/test_fleet.py` | Create | Unit tests for fleet profile parsing, host assignment, manifest |
| `tests/integration/test_fleet_integration.py` | Create | Integration tests with mocked ArchiveWriter |
| `tests/fixtures/fleet/baseline.yaml` | Create | Minimal workload profile for fleet test baseline |
| `tests/fixtures/fleet/bad-cpu.yaml` | Create | Bad actor workload profile (CPU saturated) |
| `tests/fixtures/fleet/test-fleet.yaml` | Create | Fleet profile referencing above workloads |

---

## Chunk 1: Jitter Module

### Task 1: Jitter — apply_jitter pure function

**Files:**
- Create: `tests/unit/test_jitter.py`
- Create: `pmlogsynth/jitter.py`

- [ ] **Step 1: Create test fixtures for jitter**

Create minimal workload profile fixtures for fleet tests. These are standalone workload profiles (not fleet profiles) that the fleet will reference.

`tests/fixtures/fleet/baseline.yaml`:
```yaml
meta:
  hostname: baseline-host
  duration: 600
  interval: 60

host:
  profile: generic-small

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
```

`tests/fixtures/fleet/bad-cpu.yaml`:
```yaml
meta:
  hostname: bad-host
  duration: 600
  interval: 60

host:
  profile: generic-small

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
```

- [ ] **Step 2: Write failing tests for apply_jitter**

`tests/unit/test_jitter.py`:
```python
"""Unit tests for jitter application."""

import pytest

from pmlogsynth.profile import WorkloadProfile


@pytest.fixture()
def baseline_profile() -> WorkloadProfile:
    """Load the fleet baseline workload profile."""
    from pathlib import Path

    fixture = Path(__file__).parent.parent / "fixtures" / "fleet" / "baseline.yaml"
    return WorkloadProfile.from_file(fixture)


class TestApplyJitter:
    """Tests for the apply_jitter pure function."""

    def test_factor_one_returns_identical_values(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        """Jitter factor of 1.0 should not change any values."""
        from pmlogsynth.jitter import apply_jitter

        result = apply_jitter(baseline_profile, 1.0)
        phase = result.phases[0]
        assert phase.cpu is not None
        assert phase.cpu.utilization == 0.50
        assert phase.cpu.user_ratio == 0.70
        assert phase.disk is not None
        assert phase.disk.read_mbps == 10.0

    def test_factor_multiplies_stressor_values(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        """Jitter factor > 1 should scale all numeric stressor fields."""
        from pmlogsynth.jitter import apply_jitter

        result = apply_jitter(baseline_profile, 1.10)
        phase = result.phases[0]
        assert phase.disk is not None
        assert phase.disk.read_mbps == pytest.approx(11.0)
        assert phase.disk.write_mbps == pytest.approx(5.5)
        assert phase.network is not None
        assert phase.network.rx_mbps == pytest.approx(110.0)
        assert phase.network.tx_mbps == pytest.approx(55.0)

    def test_ratio_fields_clamped_to_unit_interval(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        """Ratio fields must stay in [0.0, 1.0] after jitter."""
        from pmlogsynth.jitter import apply_jitter

        # Factor of 2.5 would push utilization=0.50 to 1.25 — must clamp to 1.0
        result = apply_jitter(baseline_profile, 2.5)
        phase = result.phases[0]
        assert phase.cpu is not None
        assert phase.cpu.utilization == 1.0
        assert phase.cpu.user_ratio == 1.0
        assert phase.memory is not None
        assert phase.memory.used_ratio == 1.0
        assert phase.network is not None
        assert phase.network.error_rate == pytest.approx(0.0025)  # 0.001 * 2.5

    def test_throughput_fields_clamped_non_negative(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        """Throughput/count fields must stay >= 0 after jitter."""
        from pmlogsynth.jitter import apply_jitter

        # Factor of 0.0 should clamp everything to 0, not go negative
        result = apply_jitter(baseline_profile, 0.0)
        phase = result.phases[0]
        assert phase.disk is not None
        assert phase.disk.read_mbps == 0.0
        assert phase.disk.write_mbps == 0.0

    def test_does_not_mutate_original(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        """apply_jitter must return a new profile, not mutate the input."""
        from pmlogsynth.jitter import apply_jitter

        original_util = baseline_profile.phases[0].cpu.utilization
        apply_jitter(baseline_profile, 1.5)
        assert baseline_profile.phases[0].cpu.utilization == original_util

    def test_none_stressor_fields_unchanged(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        """None fields in stressors should remain None after jitter."""
        from pmlogsynth.jitter import apply_jitter

        result = apply_jitter(baseline_profile, 1.1)
        phase = result.phases[0]
        # baseline.yaml doesn't set noise on cpu stressor
        assert phase.cpu is not None
        assert phase.cpu.noise is None

    def test_none_stressor_block_unchanged(self) -> None:
        """A phase with no disk/network stressor should remain None."""
        from pmlogsynth.jitter import apply_jitter
        from pmlogsynth.profile import CpuStressor, Phase, ProfileMeta, WorkloadProfile, HostConfig

        profile = WorkloadProfile(
            meta=ProfileMeta(duration=60),
            host=HostConfig(),
            phases=[Phase(name="minimal", duration=60, cpu=CpuStressor(utilization=0.5))],
        )
        result = apply_jitter(profile, 1.2)
        assert result.phases[0].disk is None
        assert result.phases[0].network is None
        assert result.phases[0].cpu is not None
        assert result.phases[0].cpu.utilization == pytest.approx(0.6)

    def test_meta_unchanged_by_jitter(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        """Jitter should not touch meta fields (hostname, duration, etc)."""
        from pmlogsynth.jitter import apply_jitter

        result = apply_jitter(baseline_profile, 1.5)
        assert result.meta.hostname == baseline_profile.meta.hostname
        assert result.meta.duration == baseline_profile.meta.duration
        assert result.meta.interval == baseline_profile.meta.interval

    def test_multiple_phases_all_jittered(self) -> None:
        """All phases in the profile get jitter applied."""
        from pmlogsynth.jitter import apply_jitter
        from pmlogsynth.profile import CpuStressor, Phase, ProfileMeta, WorkloadProfile, HostConfig

        profile = WorkloadProfile(
            meta=ProfileMeta(duration=120),
            host=HostConfig(),
            phases=[
                Phase(name="a", duration=60, cpu=CpuStressor(utilization=0.5)),
                Phase(name="b", duration=60, cpu=CpuStressor(utilization=0.3)),
            ],
        )
        result = apply_jitter(profile, 1.2)
        assert result.phases[0].cpu.utilization == pytest.approx(0.6)
        assert result.phases[1].cpu.utilization == pytest.approx(0.36)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_jitter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pmlogsynth.jitter'`

- [ ] **Step 4: Implement jitter module**

`pmlogsynth/jitter.py`:
```python
"""Per-host stressor jitter — pure function, no mutation."""

from dataclasses import replace
from typing import List, Optional, Union

from pmlogsynth.profile import (
    CpuStressor,
    DiskStressor,
    MemoryStressor,
    NetworkStressor,
    Phase,
    WorkloadProfile,
)

# Fields that represent ratios — clamped to [0.0, 1.0]
# Only fields that actually exist in stressor dataclasses belong here.
_RATIO_FIELDS = frozenset({
    "utilization", "user_ratio", "sys_ratio", "iowait_ratio",
    "used_ratio", "cache_ratio", "noise", "error_rate",
})


def _clamp(value: float, field_name: str) -> float:
    """Clamp a jittered value to its valid range."""
    if field_name in _RATIO_FIELDS:
        return max(0.0, min(1.0, value))
    return max(0.0, value)


_Stressor = Union[CpuStressor, DiskStressor, MemoryStressor, NetworkStressor]


def _jitter_stressor(stressor: Optional[_Stressor], factor: float) -> Optional[_Stressor]:
    """Apply jitter factor to all numeric Optional fields on a stressor dataclass."""
    if stressor is None:
        return None
    updates = {}
    for field_name in stressor.__dataclass_fields__:
        val = getattr(stressor, field_name)
        if val is not None and isinstance(val, (int, float)):
            jittered = val * factor
            clamped = _clamp(jittered, field_name)
            # Preserve int type for int fields
            updates[field_name] = type(val)(clamped) if isinstance(val, int) else clamped
    return replace(stressor, **updates)


def _jitter_phase(phase: Phase, factor: float) -> Phase:
    """Apply jitter to all stressors in a phase."""
    return replace(
        phase,
        cpu=_jitter_stressor(phase.cpu, factor),
        memory=_jitter_stressor(phase.memory, factor),
        disk=_jitter_stressor(phase.disk, factor),
        network=_jitter_stressor(phase.network, factor),
    )


def apply_jitter(profile: WorkloadProfile, factor: float) -> WorkloadProfile:
    """Apply a multiplicative jitter factor to all stressor values in a profile.

    Returns a new WorkloadProfile — the original is not mutated.
    Ratio fields are clamped to [0.0, 1.0]; throughput fields to >= 0.
    """
    jittered_phases: List[Phase] = [_jitter_phase(p, factor) for p in profile.phases]
    return replace(profile, phases=jittered_phases)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_jitter.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/jitter.py tests/unit/test_jitter.py tests/fixtures/fleet/
git commit -m "Add jitter module for per-host stressor variation

Pure function multiplies all stressor values by a factor, clamps
ratios to [0,1] and throughput fields to >=0. No mutation."
```

---

## Chunk 2: Fleet Profile Parsing & Host Assignment

### Task 2: Fleet profile dataclasses and YAML parser

**Files:**
- Create: `tests/unit/test_fleet.py` (first batch of tests)
- Create: `pmlogsynth/fleet.py`
- Create: `tests/fixtures/fleet/test-fleet.yaml`

- [ ] **Step 1: Create fleet test fixture**

`tests/fixtures/fleet/test-fleet.yaml`:
```yaml
meta:
  name: test-fleet
  duration: 600
  interval: 60
  hostname_prefix: host
  hardware: generic-small

hosts:
  count: 5
  baseline: baseline.yaml
  jitter: 0.05

bad_actors:
  count: 1
  jitter: 0.15
  profiles:
    - bad-cpu.yaml
```

Note: `baseline.yaml` and `bad-cpu.yaml` are resolved relative to this file's directory — they live alongside it in `tests/fixtures/fleet/`.

- [ ] **Step 2: Write failing tests for fleet profile parsing**

`tests/unit/test_fleet.py`:
```python
"""Unit tests for fleet profile loading and host assignment."""

from pathlib import Path

import pytest


FLEET_FIXTURES = Path(__file__).parent.parent / "fixtures" / "fleet"


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
        assert fleet.hosts.jitter == 0.05
        assert fleet.bad_actors.count == 1
        assert fleet.bad_actors.jitter == 0.15
        assert len(fleet.bad_actors.profiles) == 1

    def test_missing_meta_name_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 1\n  baseline: x.yaml\n"
        )
        with pytest.raises(ValidationError, match="meta.name"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_missing_hosts_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
        )
        with pytest.raises(ValidationError, match="hosts"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actors_count_exceeds_host_count_raises(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile
        from pmlogsynth.profile import ValidationError

        (tmp_path / "bad.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 2\n  baseline: x.yaml\n"
            "bad_actors:\n  count: 3\n  profiles:\n    - y.yaml\n"
        )
        with pytest.raises(ValidationError, match="bad_actors.count"):
            load_fleet_profile(tmp_path / "bad.yaml")

    def test_bad_actors_defaults_jitter_to_hosts_jitter(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 3\n  baseline: x.yaml\n  jitter: 0.08\n"
            "bad_actors:\n  count: 1\n  profiles:\n    - y.yaml\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.bad_actors.jitter == 0.08

    def test_no_bad_actors_section_is_valid(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 3\n  baseline: x.yaml\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.bad_actors.count == 0
        assert fleet.bad_actors.profiles == []

    def test_duration_accepts_duration_strings(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 24h\n  interval: 15s\n"
            "  hostname_prefix: x\n  hardware: generic-small\n"
            "hosts:\n  count: 1\n  baseline: x.yaml\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assert fleet.meta.duration == 86400
        assert fleet.meta.interval == 15

    def test_workload_paths_resolved_relative_to_fleet_file(self) -> None:
        from pmlogsynth.fleet import load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        # baseline.yaml is relative to fleet file dir
        assert fleet.hosts.baseline_path.exists()
        assert fleet.hosts.baseline_path.name == "baseline.yaml"


class TestAssignHosts:
    """Tests for host assignment with random bad-actor selection."""

    def test_correct_total_count(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        assert len(assignments) == 5

    def test_correct_bad_actor_count(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        bad = [a for a in assignments if a.role == "bad_actor"]
        assert len(bad) == 1

    def test_hostnames_zero_padded(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        hostnames = [a.hostname for a in assignments]
        assert hostnames == ["host-01", "host-02", "host-03", "host-04", "host-05"]

    def test_seed_produces_deterministic_assignments(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        a1 = assign_hosts(fleet, seed=42)
        a2 = assign_hosts(fleet, seed=42)
        assert [a.hostname for a in a1 if a.role == "bad_actor"] == \
               [a.hostname for a in a2 if a.role == "bad_actor"]
        assert [a.jitter_factor for a in a1] == [a.jitter_factor for a in a2]

    def test_different_seeds_produce_different_assignments(self) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        a1 = assign_hosts(fleet, seed=42)
        a2 = assign_hosts(fleet, seed=99)
        # With 5 hosts and 1 bad actor, different seeds should (usually) pick
        # a different bad host. We check jitter factors differ at minimum.
        factors1 = [a.jitter_factor for a in a1]
        factors2 = [a.jitter_factor for a in a2]
        assert factors1 != factors2

    def test_bad_actor_gets_bad_actor_jitter_stddev(self) -> None:
        """Bad actor jitter factors should use bad_actors.jitter, not hosts.jitter."""
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        # Run many seeds and check bad actor jitter variance is larger
        import statistics

        bad_factors = []
        baseline_factors = []
        for seed in range(100):
            assignments = assign_hosts(fleet, seed=seed)
            for a in assignments:
                if a.role == "bad_actor":
                    bad_factors.append(a.jitter_factor)
                else:
                    baseline_factors.append(a.jitter_factor)

        # bad_actors.jitter=0.15 vs hosts.jitter=0.05
        # stddev of bad actor factors should be ~3x larger
        bad_std = statistics.stdev(bad_factors)
        baseline_std = statistics.stdev(baseline_factors)
        assert bad_std > baseline_std * 1.5  # conservative check

    def test_no_bad_actors_all_baseline(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: srv\n  hardware: generic-small\n"
            "hosts:\n  count: 3\n  baseline: x.yaml\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assignments = assign_hosts(fleet, seed=1)
        assert all(a.role == "baseline" for a in assignments)

    def test_none_seed_produces_assignments(self) -> None:
        """seed=None should still work (non-reproducible mode)."""
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=None)
        assert len(assignments) == 5

    def test_zero_pad_width_scales_with_count(self, tmp_path: Path) -> None:
        """100+ hosts should get 3-digit zero padding."""
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        (tmp_path / "f.yaml").write_text(
            "meta:\n  name: x\n  duration: 600\n  interval: 60\n"
            "  hostname_prefix: srv\n  hardware: generic-small\n"
            "hosts:\n  count: 100\n  baseline: x.yaml\n"
        )
        fleet = load_fleet_profile(tmp_path / "f.yaml")
        assignments = assign_hosts(fleet, seed=1)
        assert assignments[0].hostname == "srv-001"
        assert assignments[99].hostname == "srv-100"

    def test_bad_actor_profiles_selected_from_pool(self) -> None:
        """Each bad actor gets a profile randomly selected from the pool."""
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        bad = [a for a in assignments if a.role == "bad_actor"]
        for b in bad:
            assert b.workload_path.name in ("bad-cpu.yaml",)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_fleet.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pmlogsynth.fleet'`

- [ ] **Step 4: Implement fleet profile dataclasses and parsing**

`pmlogsynth/fleet.py`:
```python
"""Fleet profile loading, host assignment, and archive orchestration."""

import hashlib
import math
import random
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from pmlogsynth.profile import ValidationError, parse_duration


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FleetMeta:
    name: str
    duration: int          # seconds
    interval: int          # seconds
    hostname_prefix: str
    hardware: str          # hardware profile name
    timezone: str = "UTC"


@dataclass
class HostsConfig:
    count: int
    baseline_path: Path    # resolved absolute path to workload YAML
    jitter: float = 0.05
    # Store the original relative path string for manifest/warnings
    baseline_rel: str = ""


@dataclass
class BadActorsConfig:
    count: int = 0
    jitter: Optional[float] = None  # defaults to hosts.jitter at load time
    profiles: List[Path] = field(default_factory=list)
    # Original relative path strings
    profiles_rel: List[str] = field(default_factory=list)


@dataclass
class FleetProfile:
    meta: FleetMeta
    hosts: HostsConfig
    bad_actors: BadActorsConfig
    source_path: Path = field(default_factory=lambda: Path("."))


@dataclass
class HostAssignment:
    hostname: str
    workload_path: Path
    workload_rel: str      # original relative path for manifest
    role: str              # "baseline" | "bad_actor"
    jitter_factor: float


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def load_fleet_profile(path: Path) -> FleetProfile:
    """Parse and validate a fleet profile YAML file."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Fleet YAML parse error: {exc}") from exc
    except OSError as exc:
        raise ValidationError(f"Cannot read fleet profile: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValidationError("Fleet profile must be a YAML mapping")

    fleet_dir = path.parent

    meta = _parse_fleet_meta(raw.get("meta"))
    hosts = _parse_hosts(raw.get("hosts"), fleet_dir)
    bad_actors = _parse_bad_actors(raw.get("bad_actors"), fleet_dir, hosts)

    # Validate bad_actors.count <= hosts.count
    if bad_actors.count > hosts.count:
        raise ValidationError(
            f"bad_actors.count ({bad_actors.count}) exceeds hosts.count ({hosts.count})"
        )

    return FleetProfile(meta=meta, hosts=hosts, bad_actors=bad_actors, source_path=path)


def _parse_fleet_meta(raw: Any) -> FleetMeta:
    if not isinstance(raw, dict):
        raise ValidationError("Fleet profile requires a 'meta' section")

    for required in ("name", "duration", "interval", "hostname_prefix", "hardware"):
        if required not in raw:
            raise ValidationError(f"meta.{required} is required")

    return FleetMeta(
        name=str(raw["name"]),
        duration=parse_duration(raw["duration"]),
        interval=parse_duration(raw["interval"]),
        hostname_prefix=str(raw["hostname_prefix"]),
        hardware=str(raw["hardware"]),
        timezone=str(raw.get("timezone", "UTC")),
    )


def _parse_hosts(raw: Any, fleet_dir: Path) -> HostsConfig:
    if not isinstance(raw, dict):
        raise ValidationError("Fleet profile requires a 'hosts' section")

    if "count" not in raw:
        raise ValidationError("hosts.count is required")
    if "baseline" not in raw:
        raise ValidationError("hosts.baseline is required")

    count = int(raw["count"])
    if count < 1:
        raise ValidationError("hosts.count must be >= 1")

    baseline_rel = str(raw["baseline"])
    baseline_path = (fleet_dir / baseline_rel).resolve()

    jitter = float(raw.get("jitter", 0.05))
    if jitter < 0:
        raise ValidationError("hosts.jitter must be >= 0")

    return HostsConfig(
        count=count,
        baseline_path=baseline_path,
        jitter=jitter,
        baseline_rel=baseline_rel,
    )


def _parse_bad_actors(
    raw: Any, fleet_dir: Path, hosts: HostsConfig
) -> BadActorsConfig:
    if raw is None:
        return BadActorsConfig(count=0, jitter=hosts.jitter)

    if not isinstance(raw, dict):
        raise ValidationError("bad_actors must be a mapping")

    count = int(raw.get("count", 0))
    jitter = float(raw["jitter"]) if "jitter" in raw else hosts.jitter

    profiles_rel = raw.get("profiles", [])
    if not isinstance(profiles_rel, list):
        raise ValidationError("bad_actors.profiles must be a list")

    if count > 0 and len(profiles_rel) == 0:
        raise ValidationError("bad_actors.profiles required when bad_actors.count > 0")

    profiles = [(fleet_dir / str(p)).resolve() for p in profiles_rel]

    return BadActorsConfig(
        count=count,
        jitter=jitter,
        profiles=profiles,
        profiles_rel=[str(p) for p in profiles_rel],
    )


# ---------------------------------------------------------------------------
# Host assignment
# ---------------------------------------------------------------------------

def _stable_host_seed(global_seed: Optional[int], hostname: str) -> int:
    """Deterministic per-host seed using SHA-256 (PYTHONHASHSEED-safe)."""
    seed_str = "{}:{}".format(global_seed if global_seed is not None else "", hostname)
    digest = hashlib.sha256(seed_str.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def assign_hosts(fleet: FleetProfile, seed: Optional[int] = None) -> List[HostAssignment]:
    """Assign hostnames, workload profiles, and jitter factors to each host."""
    count = fleet.hosts.count
    pad_width = max(2, len(str(count)))

    # Determine which host indices are bad actors
    rng = random.Random(seed)
    bad_indices = set(rng.sample(range(count), fleet.bad_actors.count))

    assignments: List[HostAssignment] = []
    for i in range(count):
        hostname = "{}-{}".format(
            fleet.meta.hostname_prefix,
            str(i + 1).zfill(pad_width),
        )

        if i in bad_indices:
            role = "bad_actor"
            # Random selection from pool
            profile_idx = rng.randrange(len(fleet.bad_actors.profiles))
            workload_path = fleet.bad_actors.profiles[profile_idx]
            workload_rel = fleet.bad_actors.profiles_rel[profile_idx]
            jitter_stddev = fleet.bad_actors.jitter if fleet.bad_actors.jitter is not None else fleet.hosts.jitter
        else:
            role = "baseline"
            workload_path = fleet.hosts.baseline_path
            workload_rel = fleet.hosts.baseline_rel
            jitter_stddev = fleet.hosts.jitter

        # Per-host jitter factor
        host_rng = random.Random(_stable_host_seed(seed, hostname))
        jitter_factor = host_rng.gauss(1.0, jitter_stddev) if jitter_stddev > 0 else 1.0

        assignments.append(HostAssignment(
            hostname=hostname,
            workload_path=workload_path,
            workload_rel=workload_rel,
            role=role,
            jitter_factor=jitter_factor,
        ))

    return assignments
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_fleet.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/fleet.py tests/unit/test_fleet.py tests/fixtures/fleet/test-fleet.yaml
git commit -m "Add fleet profile parsing and host assignment

Fleet YAML loader with dataclasses, path resolution relative to
fleet file, deterministic host assignment via SHA-256 seeding."
```

---

## Chunk 3: Fleet Manifest, Override Warnings & Generation Orchestrator

### Task 3: Fleet manifest writer and override warnings

**Files:**
- Modify: `tests/unit/test_fleet.py` (add manifest and warning tests)
- Modify: `pmlogsynth/fleet.py` (add manifest writer and override check)

- [ ] **Step 1: Write failing tests for manifest and warnings**

Append to `tests/unit/test_fleet.py`:
```python
class TestWriteManifest:
    """Tests for fleet.manifest YAML output."""

    def test_manifest_contains_all_hosts(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import (
            assign_hosts, load_fleet_profile, write_manifest,
        )

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        manifest_path = tmp_path / "fleet.manifest"
        write_manifest(manifest_path, fleet, assignments, seed=42)

        import yaml as _yaml

        manifest = _yaml.safe_load(manifest_path.read_text())
        assert manifest["meta"]["name"] == "test-fleet"
        assert manifest["meta"]["host_count"] == 5
        assert manifest["meta"]["seed"] == 42
        assert len(manifest["archives"]) == 5

    def test_manifest_roles_match_assignments(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import (
            assign_hosts, load_fleet_profile, write_manifest,
        )

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        write_manifest(tmp_path / "fleet.manifest", fleet, assignments, seed=42)

        import yaml as _yaml

        manifest = _yaml.safe_load((tmp_path / "fleet.manifest").read_text())
        for entry, assignment in zip(manifest["archives"], assignments):
            assert entry["hostname"] == assignment.hostname
            assert entry["role"] == assignment.role
            assert entry["jitter_factor"] == pytest.approx(assignment.jitter_factor)

    def test_manifest_records_none_seed(self, tmp_path: Path) -> None:
        from pmlogsynth.fleet import (
            assign_hosts, load_fleet_profile, write_manifest,
        )

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=None)
        write_manifest(tmp_path / "fleet.manifest", fleet, assignments, seed=None)

        import yaml as _yaml

        manifest = _yaml.safe_load((tmp_path / "fleet.manifest").read_text())
        assert manifest["meta"]["seed"] is None


class TestOverrideWarnings:
    """Tests for warnings when fleet settings override workload profile values."""

    def test_warns_on_duration_conflict(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging
        from pmlogsynth.fleet import check_override_warnings, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        # baseline.yaml has duration=600, fleet has duration=600 — no conflict
        # So let's modify fleet to have a different duration
        from dataclasses import replace

        fleet_different = replace(fleet, meta=replace(fleet.meta, duration=3600))
        with caplog.at_level(logging.WARNING):
            check_override_warnings(fleet_different)
        assert any("duration" in r.message for r in caplog.records)

    def test_no_warning_when_values_match(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging
        from pmlogsynth.fleet import check_override_warnings, load_fleet_profile

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        # baseline.yaml has duration=600, fleet also 600 — no conflict
        with caplog.at_level(logging.WARNING):
            check_override_warnings(fleet)
        assert not any("duration" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_fleet.py::TestWriteManifest -v`
Expected: FAIL — `ImportError: cannot import name 'write_manifest'`

- [ ] **Step 3: Implement manifest writer and override warnings**

Add to `pmlogsynth/fleet.py`:
```python
import logging

logger = logging.getLogger(__name__)


def write_manifest(
    path: Path,
    fleet: FleetProfile,
    assignments: List[HostAssignment],
    seed: Optional[int],
) -> None:
    """Write fleet.manifest YAML file."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest = {
        "meta": {
            "name": fleet.meta.name,
            "generated": now,
            "pmlogsynth_version": "1.0",
            "seed": seed,
            "duration": fleet.meta.duration,
            "interval": fleet.meta.interval,
            "hardware": fleet.meta.hardware,
            "host_count": len(assignments),
        },
        "archives": [
            {
                "hostname": a.hostname,
                "profile": a.workload_rel,
                "role": a.role,
                "jitter_factor": round(a.jitter_factor, 6),
            }
            for a in assignments
        ],
    }

    path.write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def check_override_warnings(fleet: FleetProfile) -> None:
    """Emit warnings for workload profile values that fleet settings override.

    Checks each unique workload profile once.
    """
    seen: Dict[Path, bool] = {}

    all_paths = [fleet.hosts.baseline_path]
    all_rels = [fleet.hosts.baseline_rel]
    for p, r in zip(fleet.bad_actors.profiles, fleet.bad_actors.profiles_rel):
        all_paths.append(p)
        all_rels.append(r)

    for wpath, wrel in zip(all_paths, all_rels):
        if wpath in seen:
            continue
        seen[wpath] = True

        try:
            raw = yaml.safe_load(wpath.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue  # validation catches this elsewhere

        if not isinstance(raw, dict):
            continue

        meta = raw.get("meta", {})
        if not isinstance(meta, dict):
            continue

        if "duration" in meta:
            profile_duration = parse_duration(meta["duration"])
            if profile_duration != fleet.meta.duration:
                logger.warning(
                    "workload profile '%s' defines duration=%s "
                    "— overridden by fleet setting duration=%s",
                    wrel, profile_duration, fleet.meta.duration,
                )

        if "interval" in meta:
            profile_interval = parse_duration(meta["interval"])
            if profile_interval != fleet.meta.interval:
                logger.warning(
                    "workload profile '%s' defines interval=%s "
                    "— overridden by fleet setting interval=%s",
                    wrel, profile_interval, fleet.meta.interval,
                )

        host = raw.get("host", {})
        if isinstance(host, dict) and "profile" in host:
            profile_hw = str(host["profile"])
            if profile_hw != fleet.meta.hardware:
                logger.warning(
                    "workload profile '%s' defines hardware=%s "
                    "— overridden by fleet setting hardware=%s",
                    wrel, profile_hw, fleet.meta.hardware,
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_fleet.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pmlogsynth/fleet.py tests/unit/test_fleet.py
git commit -m "Add fleet manifest writer and override warnings

YAML manifest records all host assignments with roles and jitter
factors. Override warnings emitted once per unique workload profile."
```

### Task 4: Fleet generation orchestrator

**Files:**
- Modify: `tests/unit/test_fleet.py` (add dry-run test)
- Create: `tests/integration/test_fleet_integration.py`
- Modify: `pmlogsynth/fleet.py` (add generate_fleet)

- [ ] **Step 1: Write failing test for dry-run**

Append to `tests/unit/test_fleet.py`:
```python
class TestDryRun:
    """Tests for --dry-run output formatting."""

    def test_dry_run_prints_all_hosts(self, capsys: pytest.CaptureFixture) -> None:
        from pmlogsynth.fleet import assign_hosts, load_fleet_profile, print_dry_run

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        print_dry_run(fleet, assignments, seed=42)

        captured = capsys.readouterr()
        assert "test-fleet" in captured.out
        assert "5 hosts" in captured.out
        for a in assignments:
            assert a.hostname in captured.out
        # Bad actors should be marked
        bad = [a for a in assignments if a.role == "bad_actor"]
        for b in bad:
            assert "BAD" in captured.out
```

- [ ] **Step 2: Write failing integration test for generate_fleet**

`tests/integration/test_fleet_integration.py`:
```python
"""Integration tests for fleet generation with mocked PCP."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


FLEET_FIXTURES = Path(__file__).parent.parent / "fixtures" / "fleet"


class TestGenerateFleet:
    """Tests for the fleet generation orchestrator."""

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_generates_correct_number_of_archives(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import generate_fleet, assign_hosts, load_fleet_profile

        # Mock the writer module
        mock_writer_mod = MagicMock()
        mock_writer_cls = MagicMock()
        mock_writer_mod.ArchiveWriter = mock_writer_cls
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=tmp_path,
            seed=42,
            jobs=1,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        # ArchiveWriter should be instantiated once per host
        assert mock_writer_cls.call_count == 5

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_manifest_written_after_generation(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import generate_fleet, assign_hosts, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_mod.ArchiveWriter = MagicMock()
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=tmp_path,
            seed=42,
            jobs=1,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        manifest_path = tmp_path / "fleet.manifest"
        assert manifest_path.exists()

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_fleet_overrides_applied_to_profiles(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import generate_fleet, assign_hosts, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_cls = MagicMock()
        mock_writer_mod.ArchiveWriter = mock_writer_cls
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=tmp_path,
            seed=42,
            jobs=1,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        # Check each ArchiveWriter call got the right hostname
        for call_args, assignment in zip(mock_writer_cls.call_args_list, assignments):
            profile = call_args[1]["profile"] if "profile" in call_args[1] else call_args[0][1]
            assert profile.meta.hostname == assignment.hostname
            assert profile.meta.duration == fleet.meta.duration
            assert profile.meta.interval == fleet.meta.interval

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_output_directory_created(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import generate_fleet, assign_hosts, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_mod.ArchiveWriter = MagicMock()
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)
        out = tmp_path / "nested" / "output"

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=out,
            seed=42,
            jobs=1,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        assert out.exists()

    @patch("pmlogsynth.fleet.importlib.import_module")
    def test_parallel_jobs_generates_all_archives(
        self, mock_import: MagicMock, tmp_path: Path
    ) -> None:
        from pmlogsynth.fleet import generate_fleet, assign_hosts, load_fleet_profile

        mock_writer_mod = MagicMock()
        mock_writer_cls = MagicMock()
        mock_writer_mod.ArchiveWriter = mock_writer_cls
        mock_writer_mod.ArchiveConflictError = Exception
        mock_writer_mod.ArchiveGenerationError = Exception
        mock_import.return_value = mock_writer_mod

        fleet = load_fleet_profile(FLEET_FIXTURES / "test-fleet.yaml")
        assignments = assign_hosts(fleet, seed=42)

        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=tmp_path,
            seed=42,
            jobs=2,
            force=False,
            start=None,
            verbose=False,
            config_dir=None,
        )

        # All 5 archives generated even with --jobs=2
        assert mock_writer_cls.call_count == 5
        # Manifest still written
        assert (tmp_path / "fleet.manifest").exists()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_fleet.py::TestDryRun tests/integration/test_fleet_integration.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 4: Implement generate_fleet and print_dry_run**

Add to `pmlogsynth/fleet.py`:
```python
import importlib
import sys


def print_dry_run(
    fleet: FleetProfile,
    assignments: List[HostAssignment],
    seed: Optional[int],
) -> None:
    """Print host assignment table without generating archives."""
    seed_str = str(seed) if seed is not None else "none"
    print("Fleet: {} ({} hosts, seed={})".format(fleet.meta.name, len(assignments), seed_str))
    print()
    for a in assignments:
        role_label = "BAD      " if a.role == "bad_actor" else "baseline "
        print("  {}  {}  {}  (jitter: x{:.2f})".format(
            a.hostname, role_label, a.workload_rel, a.jitter_factor,
        ))


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
    ArchiveConflictError = _writer_mod.ArchiveConflictError
    ArchiveGenerationError = _writer_mod.ArchiveGenerationError

    from pmlogsynth.jitter import apply_jitter
    from pmlogsynth.profile import ProfileResolver, WorkloadProfile
    from pmlogsynth.sampler import ValueSampler
    from pmlogsynth.timeline import TimelineSequencer

    # Resolve hardware profile once (shared across all hosts)
    resolver = ProfileResolver(config_dir=config_dir)
    hardware = resolver.resolve(fleet.meta.hardware)

    # Check for override warnings (once, before generation loop)
    check_override_warnings(fleet)

    def _generate_one(assignment: HostAssignment) -> None:
        """Generate a single host archive."""
        # Load workload profile
        profile_text = assignment.workload_path.read_text(encoding="utf-8")
        profile = WorkloadProfile.from_string(profile_text, config_dir=config_dir)

        # Apply fleet-level overrides via dataclasses.replace
        overridden_meta = replace(
            profile.meta,
            hostname=assignment.hostname,
            duration=fleet.meta.duration,
            interval=fleet.meta.interval,
            timezone=fleet.meta.timezone,
        )
        profile = replace(profile, meta=overridden_meta, hardware=hardware)

        # Apply jitter
        profile = apply_jitter(profile, assignment.jitter_factor)

        # Expand timeline
        timeline = TimelineSequencer(profile).expand(start_time=start)

        # Create sampler
        sampler = ValueSampler(noise=profile.meta.noise)

        # Write archive
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
                "  generated: {} ({})".format(assignment.hostname, assignment.role),
                file=sys.stderr,
            )

    # Generate archives — ThreadPoolExecutor for --jobs>1.
    # Threads (not processes) because _generate_one is a closure and PCP
    # archive writing is I/O-bound (disk writes), so GIL isn't a bottleneck.
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
                future.result()  # raises if _generate_one failed

    # Write manifest
    write_manifest(output_dir / "fleet.manifest", fleet, assignments, seed=seed)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_fleet.py tests/integration/test_fleet_integration.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add pmlogsynth/fleet.py tests/unit/test_fleet.py tests/integration/test_fleet_integration.py
git commit -m "Add fleet generation orchestrator, dry-run, and manifest output

Loops over host assignments, loads workload profiles with fleet-level
overrides, applies jitter, and calls existing ArchiveWriter per host."
```

---

## Chunk 4: CLI Wiring & Update Existing Fleet Stub Test

### Task 5: Wire fleet subcommand into CLI

**Files:**
- Modify: `pmlogsynth/cli.py` (lines 131-134, 395-407)
- Modify: `tests/unit/test_cli.py` (update fleet stub test)

- [ ] **Step 1: Write failing test for fleet CLI**

Update existing test in `tests/unit/test_cli.py`. The existing `test_fleet_subcommand_exits_2` should be replaced with a test that verifies the fleet subcommand now accepts arguments and calls into fleet logic.

Add to `tests/unit/test_cli.py`:
```python
def test_fleet_validate_exits_0_on_valid_profile(tmp_path: pytest.TempPathFactory) -> None:
    """fleet --validate should exit 0 for a valid fleet profile."""
    from pathlib import Path

    fleet_fixtures = Path(__file__).parent.parent / "fixtures" / "fleet"
    with patch("sys.argv", [
        "pmlogsynth", "fleet", "--validate",
        str(fleet_fixtures / "test-fleet.yaml"),
    ]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_fleet_dry_run_exits_0(capsys: pytest.CaptureFixture) -> None:
    """fleet --dry-run should print assignments and exit 0."""
    from pathlib import Path

    fleet_fixtures = Path(__file__).parent.parent / "fixtures" / "fleet"
    with patch("sys.argv", [
        "pmlogsynth", "fleet", "--dry-run", "--seed", "42",
        str(fleet_fixtures / "test-fleet.yaml"),
    ]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "test-fleet" in captured.out
    assert "host-01" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_cli.py::test_fleet_validate_exits_0_on_valid_profile tests/unit/test_cli.py::test_fleet_dry_run_exits_0 -v`
Expected: FAIL — fleet subcommand still exits 2

- [ ] **Step 3: Wire fleet subparser and handler in cli.py**

Replace the fleet stub parser at line 134 with a fully-wired subparser. Replace the fleet stub handler at lines 404-407.

In `_build_parser()`, replace:
```python
    # Reserve 'fleet' for Phase 3
    subparsers.add_parser("fleet", help=argparse.SUPPRESS)
```

With:
```python
    # --- fleet subcommand ---
    fleet_parser = subparsers.add_parser(
        "fleet",
        help="Generate a fleet of PCP archives from a fleet profile.",
        add_help=True,
    )
    _add_fleet_args(fleet_parser)
```

Add new function `_add_fleet_args`:
```python
def _add_fleet_args(p: argparse.ArgumentParser) -> None:
    """Add fleet-command arguments to a parser."""
    p.add_argument(
        "fleet_profile",
        metavar="FLEET_PROFILE",
        help="Path to fleet YAML profile.",
    )
    p.add_argument(
        "-o", "--output-dir",
        metavar="PATH",
        default=None,
        help="Output directory for archives (default: ./generated-archives/fleet-<name>).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="INT",
        help="PRNG seed for reproducible jitter and bad-actor assignment.",
    )
    import os

    p.add_argument(
        "--jobs",
        type=int,
        default=os.cpu_count() or 1,
        metavar="INT",
        help="Parallel archive generation workers (default: CPU count).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print host/profile assignments without generating archives.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing archive files.",
    )
    p.add_argument(
        "--validate",
        action="store_true",
        default=False,
        help="Validate fleet profile and exit.",
    )
    p.add_argument(
        "--start",
        metavar="TIMESTAMP",
        help=(
            "Archive start time (ISO 8601 or 'YYYY-MM-DD HH:MM:SS TZ'). "
            "Overrides meta.start. Default: today at 00:00:00 UTC."
        ),
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Show per-host progress.",
    )
```

Add new function `_cmd_fleet`:
```python
def _cmd_fleet(args: argparse.Namespace) -> int:
    """Handle the fleet subcommand."""
    from pmlogsynth.fleet import (
        assign_hosts,
        check_override_warnings,
        generate_fleet,
        load_fleet_profile,
        print_dry_run,
    )

    config_dir = Path(args.config_dir) if args.config_dir else None

    # Validate incompatibilities
    if args.validate:
        for flag in ("force", "dry_run"):
            if getattr(args, flag, False):
                print(
                    "error: --validate is incompatible with "
                    "--{}".format(flag.replace("_", "-")),
                    file=sys.stderr,
                )
                return 1

    # Load fleet profile
    try:
        fleet = load_fleet_profile(Path(args.fleet_profile))
    except ValidationError as exc:
        print("Validation error: {}".format(exc), file=sys.stderr)
        return 1

    # Validate-only mode
    if args.validate:
        check_override_warnings(fleet)
        print("Fleet profile is valid: {} ({} hosts)".format(
            fleet.meta.name, fleet.hosts.count,
        ))
        return 0

    # Assign hosts
    assignments = assign_hosts(fleet, seed=args.seed)

    # Dry-run mode
    if args.dry_run:
        print_dry_run(fleet, assignments, seed=args.seed)
        return 0

    # Parse start time
    start_time = None
    if args.start:
        from pmlogsynth.time_parsing import parse_absolute_timestamp
        try:
            start_time = parse_absolute_timestamp(args.start, field="--start")
        except ValidationError as exc:
            print("error: {}".format(exc), file=sys.stderr)
            return 1

    # Determine output directory
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = "./generated-archives/fleet-{}".format(fleet.meta.name)

    # Generate
    try:
        generate_fleet(
            fleet=fleet,
            assignments=assignments,
            output_dir=Path(output_dir),
            seed=args.seed,
            jobs=args.jobs,
            force=args.force,
            start=start_time,
            verbose=args.verbose,
            config_dir=config_dir,
        )
    except Exception as exc:
        print("error: Fleet generation failed: {}".format(exc), file=sys.stderr)
        return 3

    print("Fleet '{}' generated: {} archives in {}".format(
        fleet.meta.name, len(assignments), output_dir,
    ))
    return 0
```

In `main()`, replace the fleet stub:
```python
    # Fleet stub
    if args.subcommand == "fleet":
        print("error: fleet subcommand not yet implemented", file=sys.stderr)
        sys.exit(2)
```

With:
```python
    # Fleet subcommand
    if args.subcommand == "fleet":
        sys.exit(_cmd_fleet(args))
```

- [ ] **Step 4: Update existing fleet stub test in-place**

In `tests/unit/test_cli.py`, modify `test_fleet_subcommand_exits_2` in-place. The
function body changes but the test is updated, not deleted (per CLAUDE.md rules).
Change the docstring and assertion to reflect that fleet now uses argparse which
exits 2 on missing positional args (same exit code, different reason):
```python
def test_fleet_subcommand_exits_2(capsys: pytest.CaptureFixture) -> None:
    """fleet subcommand without FLEET_PROFILE arg exits non-zero."""
    with patch("sys.argv", ["pmlogsynth", "fleet"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_cli.py -v`
Expected: All PASS (including old tests that didn't change)

- [ ] **Step 6: Run full quality gate**

Run: `./pre-commit.sh`
Expected: All green — ruff, mypy, unit + integration tests

- [ ] **Step 7: Commit**

```bash
git add pmlogsynth/cli.py tests/unit/test_cli.py
git commit -m "Wire fleet subcommand into CLI with validate and dry-run

Replaces the Phase 3 stub with a fully functional fleet subparser.
Supports --validate, --dry-run, --seed, --jobs, --force, --start."
```

---

## Chunk 5: Final Validation & Docs

### Task 6: Quality gate and documentation updates

**Files:**
- Modify: `CLAUDE.md` (update project structure, remove fleet reservation note)
- Modify: `man/pmlogsynth.1` (add fleet subcommand)
- Modify: `README.md` (mention fleet mode)
- Modify: `docs/profile-format.md` (add fleet profile schema section)

- [ ] **Step 1: Run full pre-commit quality gate**

Run: `./pre-commit.sh`
Expected: All green

- [ ] **Step 2: Update CLAUDE.md project structure**

Add `fleet.py` and `jitter.py` to the project structure listing. Update the CLI note about `fleet` being reserved — it's now implemented.

- [ ] **Step 3: Update man page**

Add fleet subcommand documentation to `man/pmlogsynth.1` — synopsis, description of options, example usage.

- [ ] **Step 4: Update docs/profile-format.md**

Add a "Fleet Profile Format" section covering: `meta` fields (name, duration, interval,
hostname_prefix, hardware, timezone), `hosts` fields (count, baseline, jitter), and
`bad_actors` fields (count, jitter, profiles). Document path resolution rules and
fleet-level override behaviour.

- [ ] **Step 5: Update README.md**

Add a brief "Fleet Mode" section showing:
```bash
# Generate a 20-host fleet with 2 bad actors
pmlogsynth fleet -o ./generated-archives/cluster --seed 42 fleet-profile.yaml

# Preview assignments without generating
pmlogsynth fleet --dry-run --seed 42 fleet-profile.yaml
```

- [ ] **Step 6: Run quality gate again after doc changes**

Run: `./pre-commit.sh`
Expected: All green (mandoc lint, ruff, mypy, all tests)

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md man/pmlogsynth.1 README.md docs/profile-format.md
git commit -m "Document fleet mode in man page, README, and CLAUDE.md

Fleet subcommand is now implemented — update project docs to reflect
the new capability and remove Phase 3 reservation notes."
```

- [ ] **Step 8: Final verification**

Run: `pytest -v` (all tiers)
Run: `./pre-commit.sh`

Confirm everything is green before pushing.
