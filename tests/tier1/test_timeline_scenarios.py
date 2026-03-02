"""Tier 1 tests for complex timeline scenarios (US4)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pmlogsynth.profile import (
    CpuStressor,
    DiskDevice,
    HardwareProfile,
    MemoryStressor,
    NetworkInterface,
    Phase,
    ProfileMeta,
    WorkloadProfile,
)
from pmlogsynth.timeline import TimelineSequencer

FIXTURES = Path(__file__).parent.parent / "fixtures" / "profiles"

# Minimal hardware profile for testing
_SIMPLE_HW = HardwareProfile(
    name="test",
    cpus=1,
    memory_kb=4_194_304,
    disks=[DiskDevice(name="sda")],
    interfaces=[NetworkInterface(name="eth0")],
)

_START = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _make_profile(
    phases: list,
    duration: int,
    interval: int = 60,
) -> WorkloadProfile:
    return WorkloadProfile(
        meta=ProfileMeta(duration=duration, interval=interval),
        host=None,  # type: ignore[arg-type]
        phases=phases,
        hardware=_SIMPLE_HW,
    )


@pytest.mark.tier1
def test_instant_transition_holds_phase_value() -> None:
    """Instant transition: all samples in a phase use the phase's target values."""
    phases = [
        Phase(name="low", duration=300, cpu=CpuStressor(utilization=0.10)),
        Phase(name="high", duration=300, cpu=CpuStressor(utilization=0.80)),
    ]
    profile = _make_profile(phases, duration=600, interval=60)
    timeline = TimelineSequencer(profile).expand(start_time=_START)

    # First 5 samples → low phase (utilization=0.10)
    for sp in timeline.samples[:5]:
        assert sp.phase_name == "low"
        assert sp.cpu.utilization == 0.10

    # Next 5 samples → high phase (utilization=0.80)
    for sp in timeline.samples[5:]:
        assert sp.phase_name == "high"
        assert sp.cpu.utilization == 0.80


@pytest.mark.tier1
def test_linear_transition_interpolates_cpu() -> None:
    """Linear transition: first sample ≈ start value, last sample ≈ target."""
    phases = [
        Phase(name="baseline", duration=300, cpu=CpuStressor(utilization=0.10)),
        Phase(
            name="ramp",
            duration=300,
            transition="linear",
            cpu=CpuStressor(utilization=0.90),
        ),
    ]
    profile = _make_profile(phases, duration=600, interval=60)
    timeline = TimelineSequencer(profile).expand(start_time=_START)

    ramp_samples = [sp for sp in timeline.samples if sp.phase_name == "ramp"]
    assert len(ramp_samples) == 5  # 300s / 60s interval

    # First ramp sample should be closer to 0.10 than 0.90
    first_util = ramp_samples[0].cpu.utilization
    assert first_util is not None
    assert first_util < 0.50, f"First ramp sample too high: {first_util}"

    # Last ramp sample should be close to 0.90
    last_util = ramp_samples[-1].cpu.utilization
    assert last_util is not None
    assert last_util > 0.70, f"Last ramp sample too low: {last_util}"

    # Values are monotonically increasing
    utils = [sp.cpu.utilization for sp in ramp_samples]
    for a, b in zip(utils, utils[1:]):
        assert a is not None and b is not None
        assert b >= a, f"Not monotonically increasing: {a} -> {b}"


@pytest.mark.tier1
def test_linear_transition_midpoint() -> None:
    """Linear transition: midpoint sample is approximately halfway between endpoints."""
    phases = [
        Phase(name="start", duration=120, cpu=CpuStressor(utilization=0.0)),
        Phase(
            name="ramp",
            duration=120,
            transition="linear",
            cpu=CpuStressor(utilization=1.0),
        ),
    ]
    profile = _make_profile(phases, duration=240, interval=60)
    timeline = TimelineSequencer(profile).expand(start_time=_START)

    ramp_samples = [sp for sp in timeline.samples if sp.phase_name == "ramp"]
    assert len(ramp_samples) == 2

    # frac = (t+1)/ticks: t=0 → frac=0.5, t=1 → frac=1.0
    mid_util = ramp_samples[0].cpu.utilization
    assert mid_util is not None
    assert abs(mid_util - 0.5) < 0.01, f"Midpoint util expected 0.5, got {mid_util}"


@pytest.mark.tier1
def test_repeat_integer_produces_n_copies() -> None:
    """repeat: N produces N copies of the phase."""
    phases = [
        Phase(
            name="burst",
            duration=300,
            repeat=2,
            cpu=CpuStressor(utilization=0.90),
        ),
    ]
    profile = _make_profile(phases, duration=600, interval=60)
    timeline = TimelineSequencer(profile).expand(start_time=_START)
    assert len(timeline.samples) == 10  # 600s / 60s


@pytest.mark.tier1
def test_repeat_daily_expands_correctly() -> None:
    """repeat: daily produces one peak + one fill per day for the total duration.

    When only a single repeat:daily phase is present (no explicit background),
    the sequencer auto-generates fill phases for the remaining portion of each day.
    A 1-hour peak in a 24-hour window yields: 1h peak + 23h fill = 24h.
    """
    phases = [
        Phase(name="peak", duration=3600, repeat="daily"),
    ]
    profile = _make_profile(phases, duration=86400, interval=3600)
    timeline = TimelineSequencer(profile).expand(start_time=_START)
    assert len(timeline.samples) == 24  # 86400s / 3600s interval


@pytest.mark.tier1
def test_sample_timestamps_are_sequential() -> None:
    """Sample timestamps increase by exactly meta.interval each step."""
    phases = [Phase(name="p", duration=300, cpu=CpuStressor(utilization=0.5))]
    profile = _make_profile(phases, duration=300, interval=60)
    timeline = TimelineSequencer(profile).expand(start_time=_START)

    ts_list = [sp.timestamp_sec for sp in timeline.samples]
    for i in range(1, len(ts_list)):
        assert ts_list[i] - ts_list[i - 1] == 60


@pytest.mark.tier1
def test_sample_count_matches_duration_over_interval() -> None:
    """Number of samples == meta.duration // meta.interval."""
    phases = [Phase(name="p", duration=600)]
    profile = _make_profile(phases, duration=600, interval=30)
    timeline = TimelineSequencer(profile).expand(start_time=_START)
    assert len(timeline.samples) == 20  # 600 / 30


@pytest.mark.tier1
def test_sample_point_fields_populated() -> None:
    """Every SamplePoint has all four stressor objects set."""
    phases = [Phase(name="p", duration=60)]
    profile = _make_profile(phases, duration=60, interval=60)
    timeline = TimelineSequencer(profile).expand(start_time=_START)
    sp = timeline.samples[0]
    assert sp.cpu is not None
    assert sp.memory is not None
    assert sp.disk is not None
    assert sp.network is not None
    assert sp.phase_name == "p"


@pytest.mark.tier1
def test_stressor_defaults_are_none_in_sample_points() -> None:
    """Stressor fields with no value remain None in SamplePoints (defaults at compute time)."""
    phases = [Phase(name="p", duration=60)]
    profile = _make_profile(phases, duration=60, interval=60)
    timeline = TimelineSequencer(profile).expand(start_time=_START)
    sp = timeline.samples[0]
    # CpuStressor with no explicit utilization → utilization is None
    assert sp.cpu.utilization is None


@pytest.mark.tier1
def test_both_cpu_and_memory_interpolate_independently() -> None:
    """Linear transition interpolates CPU and memory stressors independently."""
    phases = [
        Phase(
            name="low",
            duration=60,
            cpu=CpuStressor(utilization=0.0),
            memory=MemoryStressor(used_ratio=0.2),
        ),
        Phase(
            name="high",
            duration=60,
            transition="linear",
            cpu=CpuStressor(utilization=1.0),
            memory=MemoryStressor(used_ratio=0.8),
        ),
    ]
    profile = _make_profile(phases, duration=120, interval=60)
    timeline = TimelineSequencer(profile).expand(start_time=_START)

    high_sp = timeline.samples[-1]
    assert high_sp.cpu.utilization is not None
    assert high_sp.cpu.utilization > 0.8
    assert high_sp.memory.used_ratio is not None
    assert high_sp.memory.used_ratio > 0.6


@pytest.mark.tier1
def test_fixture_linear_ramp_profile() -> None:
    """workload-linear-ramp.yaml loads and expands to correct sample count."""
    fixtures_root = Path(__file__).parent.parent / "fixtures"
    text = (fixtures_root / "workload-linear-ramp.yaml").read_text(encoding="utf-8")
    profile = WorkloadProfile.from_string(text, config_dir=FIXTURES)
    timeline = TimelineSequencer(profile).expand(start_time=_START)
    # 1200s / 60s = 20 samples
    assert len(timeline.samples) == 20
