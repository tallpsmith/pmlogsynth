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
        from pmlogsynth.jitter import apply_jitter

        result = apply_jitter(baseline_profile, 2.5)
        phase = result.phases[0]
        assert phase.cpu is not None
        assert phase.cpu.utilization == 1.0
        assert phase.cpu.user_ratio == 1.0
        assert phase.memory is not None
        assert phase.memory.used_ratio == 1.0
        assert phase.network is not None
        assert phase.network.error_rate == pytest.approx(0.0025)

    def test_throughput_fields_clamped_non_negative(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        from pmlogsynth.jitter import apply_jitter

        result = apply_jitter(baseline_profile, 0.0)
        phase = result.phases[0]
        assert phase.disk is not None
        assert phase.disk.read_mbps == 0.0
        assert phase.disk.write_mbps == 0.0

    def test_does_not_mutate_original(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        from pmlogsynth.jitter import apply_jitter

        original_util = baseline_profile.phases[0].cpu.utilization
        apply_jitter(baseline_profile, 1.5)
        assert baseline_profile.phases[0].cpu.utilization == original_util

    def test_none_stressor_fields_unchanged(
        self, baseline_profile: WorkloadProfile
    ) -> None:
        from pmlogsynth.jitter import apply_jitter

        result = apply_jitter(baseline_profile, 1.1)
        phase = result.phases[0]
        assert phase.cpu is not None
        assert phase.cpu.noise is None

    def test_none_stressor_block_unchanged(self) -> None:
        from pmlogsynth.jitter import apply_jitter
        from pmlogsynth.profile import CpuStressor, HostConfig, Phase, ProfileMeta, WorkloadProfile

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
        from pmlogsynth.jitter import apply_jitter

        result = apply_jitter(baseline_profile, 1.5)
        assert result.meta.hostname == baseline_profile.meta.hostname
        assert result.meta.duration == baseline_profile.meta.duration
        assert result.meta.interval == baseline_profile.meta.interval

    def test_multiple_phases_all_jittered(self) -> None:
        from pmlogsynth.jitter import apply_jitter
        from pmlogsynth.profile import CpuStressor, HostConfig, Phase, ProfileMeta, WorkloadProfile

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
