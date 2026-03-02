"""Unit tests for timeline.py — TimelineSequencer."""

import time
from datetime import datetime, timezone

import pytest

from pmlogsynth.profile import (
    CpuStressor,
    DiskStressor,
    HardwareProfile,
    HostConfig,
    MemoryStressor,
    NetworkStressor,
    Phase,
    ProfileMeta,
    ValidationError,
    WorkloadProfile,
)
from pmlogsynth.timeline import (
    SamplePoint,
    TimelineSequencer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_START = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def make_hw() -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=8388608,
    )


def make_meta(duration: int, interval: int = 60) -> ProfileMeta:
    return ProfileMeta(duration=duration, interval=interval)


def make_profile_obj(
    phases: "list[Phase]",
    duration: int,
    interval: int = 60,
) -> WorkloadProfile:
    meta = make_meta(duration=duration, interval=interval)
    hw = make_hw()
    host = HostConfig(cpus=2, memory_kb=8388608)
    return WorkloadProfile(meta=meta, host=host, phases=phases, hardware=hw)


# ---------------------------------------------------------------------------
# Instant transition tests
# ---------------------------------------------------------------------------


class TestInstantTransition:
    def test_single_phase_instant_uses_target_values(self) -> None:
        phases = [Phase(name="baseline", duration=120, cpu=CpuStressor(utilization=0.3))]
        profile = make_profile_obj(phases, duration=120)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        assert len(tl.samples) == 2  # 120s / 60s = 2 ticks
        for sample in tl.samples:
            assert sample.cpu.utilization == pytest.approx(0.3)
            assert sample.phase_name == "baseline"

    def test_two_phase_instant_second_phase_uses_own_target(self) -> None:
        phases = [
            Phase(name="baseline", duration=120, cpu=CpuStressor(utilization=0.1)),
            Phase(name="spike", duration=120, cpu=CpuStressor(utilization=0.9)),
        ]
        profile = make_profile_obj(phases, duration=240)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        assert len(tl.samples) == 4
        for s in tl.samples[:2]:
            assert s.cpu.utilization == pytest.approx(0.1)
        for s in tl.samples[2:]:
            assert s.cpu.utilization == pytest.approx(0.9)

    def test_none_transition_treated_as_instant(self) -> None:
        phases = [Phase(name="p1", duration=60, cpu=CpuStressor(utilization=0.5))]
        profile = make_profile_obj(phases, duration=60)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        assert len(tl.samples) == 1
        assert tl.samples[0].cpu.utilization == pytest.approx(0.5)

    def test_instant_transition_explicit(self) -> None:
        phases = [
            Phase(name="p1", duration=60, cpu=CpuStressor(utilization=0.2)),
            Phase(name="p2", duration=60, transition="instant", cpu=CpuStressor(utilization=0.8)),
        ]
        profile = make_profile_obj(phases, duration=120)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        assert tl.samples[0].cpu.utilization == pytest.approx(0.2)
        assert tl.samples[1].cpu.utilization == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Linear transition tests
# ---------------------------------------------------------------------------


class TestLinearTransition:
    def test_linear_transition_interpolates(self) -> None:
        phases = [
            Phase(name="low", duration=120, cpu=CpuStressor(utilization=0.0)),
            Phase(name="ramp", duration=120, transition="linear", cpu=CpuStressor(utilization=1.0)),
        ]
        profile = make_profile_obj(phases, duration=240)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        # Samples 0-1: "low" phase (instant, util=0.0)
        # Samples 2-3: "ramp" phase (linear from 0.0 to 1.0), 2 ticks
        # frac = (t+1)/ticks: tick0 → 0.5, tick1 → 1.0
        ramp_samples = tl.samples[2:]
        assert len(ramp_samples) == 2
        assert ramp_samples[0].cpu.utilization == pytest.approx(0.5)
        assert ramp_samples[1].cpu.utilization == pytest.approx(1.0)

    def test_linear_first_sample_near_prev_values(self) -> None:
        # prev=0.0, target=0.6, 3 ticks: fracs = 1/3, 2/3, 3/3
        phases = [
            Phase(name="p1", duration=180, cpu=CpuStressor(utilization=0.0)),
            Phase(name="p2", duration=180, transition="linear", cpu=CpuStressor(utilization=0.6)),
        ]
        profile = make_profile_obj(phases, duration=360)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        ramp = tl.samples[3:]
        assert ramp[0].cpu.utilization == pytest.approx(0.2)  # 0 + 0.6*(1/3)
        assert ramp[1].cpu.utilization == pytest.approx(0.4)  # 0 + 0.6*(2/3)
        assert ramp[2].cpu.utilization == pytest.approx(0.6)  # 0 + 0.6*(3/3)

    def test_first_phase_linear_raises_validation_error(self) -> None:
        meta = ProfileMeta(duration=60)
        hw = make_hw()
        host = HostConfig(cpus=2, memory_kb=8388608)
        phase = Phase(name="p1", duration=60, transition="linear", cpu=CpuStressor(utilization=0.5))
        profile = WorkloadProfile(meta=meta, host=host, phases=[phase], hardware=hw)

        seq = TimelineSequencer(profile)
        with pytest.raises(ValidationError, match="linear"):
            seq._generate_samples([phase], meta, FIXED_START)


# ---------------------------------------------------------------------------
# Repeat tests
# ---------------------------------------------------------------------------


class TestRepeatExpansion:
    def test_repeat_integer_expands_correctly(self) -> None:
        # repeat=3 for a 60s phase, meta.duration=180
        phases = [Phase(name="work", duration=60, repeat=3, cpu=CpuStressor(utilization=0.7))]
        profile = make_profile_obj(phases, duration=180)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        assert len(tl.samples) == 3
        for s in tl.samples:
            assert s.cpu.utilization == pytest.approx(0.7)
        assert tl.samples[0].phase_name == "work-rep1"
        assert tl.samples[1].phase_name == "work-rep2"
        assert tl.samples[2].phase_name == "work-rep3"

    def test_repeat_daily_two_days(self) -> None:
        # 2 days = 172800s; peak 3600s daily; fill 82800s per day
        phases = [
            Phase(name="peak", duration=3600, repeat="daily", cpu=CpuStressor(utilization=0.9))
        ]
        profile = make_profile_obj(phases, duration=172800, interval=3600)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        # 172800 / 3600 = 48 ticks total
        assert len(tl.samples) == 48

    def test_expanded_duration_mismatch_raises(self) -> None:
        """Manually build a profile with phases summing to wrong total."""
        meta = ProfileMeta(duration=180, interval=60)
        hw = make_hw()
        host = HostConfig(cpus=2, memory_kb=8388608)
        # Phases sum to 120, but meta says 180
        phase1 = Phase(name="p1", duration=60, cpu=CpuStressor(utilization=0.1))
        phase2 = Phase(name="p2", duration=60, cpu=CpuStressor(utilization=0.5))
        profile = WorkloadProfile(meta=meta, host=host, phases=[phase1, phase2], hardware=hw)

        seq = TimelineSequencer(profile)
        with pytest.raises(ValidationError, match="duration"):
            seq.expand(start_time=FIXED_START)


# ---------------------------------------------------------------------------
# SamplePoint timestamp tests
# ---------------------------------------------------------------------------


class TestSamplePointTimestamps:
    def test_timestamps_increment_by_interval(self) -> None:
        phases = [Phase(name="baseline", duration=300)]
        profile = make_profile_obj(phases, duration=300, interval=60)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        ts_list = [s.timestamp_sec for s in tl.samples]
        for i in range(1, len(ts_list)):
            assert ts_list[i] - ts_list[i - 1] == 60

    def test_custom_start_time_used(self) -> None:
        phases = [Phase(name="baseline", duration=60)]
        profile = make_profile_obj(phases, duration=60)
        custom_start = datetime(2020, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=custom_start)
        assert tl.start_time == custom_start
        assert tl.samples[0].timestamp_sec == int(custom_start.timestamp())

    def test_default_start_time_is_now_minus_duration(self) -> None:
        phases = [Phase(name="baseline", duration=60)]
        profile = make_profile_obj(phases, duration=60)
        before = int(time.time())
        seq = TimelineSequencer(profile)
        tl = seq.expand()
        after = int(time.time())
        start_ts = int(tl.start_time.timestamp())
        assert before - 60 <= start_ts <= after


# ---------------------------------------------------------------------------
# SamplePoint field population
# ---------------------------------------------------------------------------


class TestSamplePointFields:
    def test_sample_point_has_all_stressor_fields(self) -> None:
        phases = [Phase(
            name="p1",
            duration=60,
            cpu=CpuStressor(utilization=0.5),
            memory=MemoryStressor(used_ratio=0.6),
            disk=DiskStressor(read_mbps=100.0),
            network=NetworkStressor(rx_mbps=50.0),
        )]
        profile = make_profile_obj(phases, duration=60)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        s = tl.samples[0]
        assert isinstance(s, SamplePoint)
        assert s.cpu.utilization == pytest.approx(0.5)
        assert s.memory.used_ratio == pytest.approx(0.6)
        assert s.disk.read_mbps == pytest.approx(100.0)
        assert s.network.rx_mbps == pytest.approx(50.0)

    def test_phase_without_stressors_uses_empty_defaults(self) -> None:
        phases = [Phase(name="idle", duration=60)]
        profile = make_profile_obj(phases, duration=60)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        s = tl.samples[0]
        # Empty stressors — all None (defaults at compute time, not here)
        assert s.cpu.utilization is None
        assert s.memory.used_ratio is None
        assert s.disk.read_mbps is None
        assert s.network.rx_mbps is None

    def test_start_time_stored_in_timeline(self) -> None:
        phases = [Phase(name="baseline", duration=60)]
        profile = make_profile_obj(phases, duration=60)
        seq = TimelineSequencer(profile)
        tl = seq.expand(start_time=FIXED_START)
        assert tl.start_time == FIXED_START
