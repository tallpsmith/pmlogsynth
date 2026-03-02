"""Tier 1 unit tests for LoadMetricModel (T022)."""

import math

import pytest

from pmlogsynth.domains.load import LoadMetricModel
from pmlogsynth.profile import CpuStressor, HardwareProfile
from pmlogsynth.sampler import ValueSampler  # noqa: F401 (used in fixtures)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def hw4() -> HardwareProfile:
    return HardwareProfile(name="test", cpus=4, memory_kb=8388608, disks=[], interfaces=[])


@pytest.fixture()
def hw1() -> HardwareProfile:
    return HardwareProfile(name="test-1cpu", cpus=1, memory_kb=1048576, disks=[], interfaces=[])


@pytest.fixture()
def sampler() -> ValueSampler:
    return ValueSampler(noise=0.0)


# ---------------------------------------------------------------------------
# T022-1: metric_descriptors returns 1 descriptor named "kernel.all.load"
# ---------------------------------------------------------------------------

def test_metric_descriptors_count(hw4: HardwareProfile) -> None:
    model = LoadMetricModel()
    descriptors = model.metric_descriptors(hw4)
    assert len(descriptors) == 1


def test_metric_descriptors_name(hw4: HardwareProfile) -> None:
    model = LoadMetricModel()
    descriptors = model.metric_descriptors(hw4)
    assert descriptors[0].name == "kernel.all.load"


def test_metric_descriptors_pmid(hw4: HardwareProfile) -> None:
    model = LoadMetricModel()
    descriptor = model.metric_descriptors(hw4)[0]
    assert descriptor.pmid == (60, 2, 0)


def test_metric_descriptors_type_and_sem(hw4: HardwareProfile) -> None:
    model = LoadMetricModel()
    descriptor = model.metric_descriptors(hw4)[0]
    assert descriptor.type_code == 5   # PM_TYPE_FLOAT
    assert descriptor.sem == 3         # PM_SEM_INSTANT


def test_metric_descriptors_indom(hw4: HardwareProfile) -> None:
    model = LoadMetricModel()
    descriptor = model.metric_descriptors(hw4)[0]
    assert descriptor.indom == (60, 3)


# ---------------------------------------------------------------------------
# T022-2: Initial load = 0.0 when utilization=0
# ---------------------------------------------------------------------------

def test_initial_load_zero_utilization(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    model = LoadMetricModel()
    stressor = CpuStressor(utilization=0.0)
    result = model.compute(stressor, hw4, 60, sampler)
    loads = result["kernel.all.load"]
    assert loads["1 minute"] == 0.0
    assert loads["5 minute"] == 0.0
    assert loads["15 minute"] == 0.0


def test_initial_load_none_stressor(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    model = LoadMetricModel()
    result = model.compute(None, hw4, 60, sampler)
    loads = result["kernel.all.load"]
    assert loads["1 minute"] == 0.0
    assert loads["5 minute"] == 0.0
    assert loads["15 minute"] == 0.0


# ---------------------------------------------------------------------------
# T022-3: load_raw=4.0 with util=1.0 and 4 CPUs; after many calls load_1 converges to 4.0
# ---------------------------------------------------------------------------

def test_load_convergence_toward_load_raw(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    model = LoadMetricModel()
    stressor = CpuStressor(utilization=1.0)  # load_raw = 1.0 * 4 = 4.0
    # After many intervals the EMA converges to load_raw=4.0
    for _ in range(200):
        result = model.compute(stressor, hw4, 60, sampler)
    load_1 = result["kernel.all.load"]["1 minute"]
    assert abs(load_1 - 4.0) < 0.01, f"Expected load_1 near 4.0, got {load_1}"


# ---------------------------------------------------------------------------
# T022-4: Faster convergence for 1-minute vs 15-minute EMA
# ---------------------------------------------------------------------------

def test_load_1min_responds_faster_than_15min(
    hw1: HardwareProfile, sampler: ValueSampler
) -> None:
    """After 10 calls at 100% util on 1 CPU, load_1 should be closer to 1.0 than load_15."""
    model = LoadMetricModel()
    stressor = CpuStressor(utilization=1.0)  # load_raw = 1.0
    for _ in range(10):
        result = model.compute(stressor, hw1, 60, sampler)
    loads = result["kernel.all.load"]
    load_1 = loads["1 minute"]
    load_15 = loads["15 minute"]
    # 1-minute EMA has larger alpha decay per interval → converges faster
    assert abs(load_1 - 1.0) < abs(load_15 - 1.0), (
        f"load_1={load_1} should be closer to 1.0 than load_15={load_15}"
    )


# ---------------------------------------------------------------------------
# T022-5: All three instance values are positive after non-zero utilization
# ---------------------------------------------------------------------------

def test_all_instances_positive_after_nonzero_util(
    hw1: HardwareProfile, sampler: ValueSampler
) -> None:
    model = LoadMetricModel()
    stressor = CpuStressor(utilization=1.0)
    result = model.compute(stressor, hw1, 60, sampler)
    loads = result["kernel.all.load"]
    assert loads["1 minute"] > 0
    assert loads["5 minute"] > 0
    assert loads["15 minute"] > 0


# ---------------------------------------------------------------------------
# T022-6: Zero utilization after spike drives load back toward 0.0
# ---------------------------------------------------------------------------

def test_zero_utilization_drives_load_toward_zero(
    hw4: HardwareProfile, sampler: ValueSampler
) -> None:
    model = LoadMetricModel()
    high_stressor = CpuStressor(utilization=1.0)
    zero_stressor = CpuStressor(utilization=0.0)

    # Spike load up
    for _ in range(20):
        model.compute(high_stressor, hw4, 60, sampler)

    # Record peak load_1
    peak_result = model.compute(high_stressor, hw4, 60, sampler)
    peak_load_1 = peak_result["kernel.all.load"]["1 minute"]
    assert peak_load_1 > 1.0, f"Expected a spike, got {peak_load_1}"

    # Now drive load down with zero utilization
    for _ in range(20):
        result = model.compute(zero_stressor, hw4, 60, sampler)

    load_after_decay = result["kernel.all.load"]["1 minute"]
    assert load_after_decay < peak_load_1, (
        f"Expected load to decrease from {peak_load_1}, got {load_after_decay}"
    )
    assert load_after_decay < 0.5, f"Expected load near 0, got {load_after_decay}"


# ---------------------------------------------------------------------------
# T022-7: Different intervals produce different decay rates
# ---------------------------------------------------------------------------

def test_different_intervals_different_decay(
    hw1: HardwareProfile, sampler: ValueSampler
) -> None:
    """A shorter interval means a smaller alpha, so more decay per step when util goes to 0."""
    stressor_high = CpuStressor(utilization=1.0)
    stressor_zero = CpuStressor(utilization=0.0)

    model_60 = LoadMetricModel()
    model_300 = LoadMetricModel()

    # Spike both models up identically using interval=60
    for _ in range(20):
        model_60.compute(stressor_high, hw1, 60, sampler)
        model_300.compute(stressor_high, hw1, 60, sampler)

    # Now decay: model_60 uses interval=60, model_300 uses interval=300
    # With interval=60: alpha_1 = exp(-60/60) = exp(-1) ≈ 0.368 → more decay per step
    # With interval=300: alpha_1 = exp(-300/60) = exp(-5) ≈ 0.007 → even more decay
    for _ in range(3):
        result_60 = model_60.compute(stressor_zero, hw1, 60, sampler)
        result_300 = model_300.compute(stressor_zero, hw1, 300, sampler)

    # After same number of ticks, the larger-interval model decays more per tick
    load_60 = result_60["kernel.all.load"]["1 minute"]
    load_300 = result_300["kernel.all.load"]["1 minute"]
    assert load_60 != load_300, (
        f"Expected different decay for interval=60 ({load_60}) vs interval=300 ({load_300})"
    )


# ---------------------------------------------------------------------------
# T022-8: Result dict has exactly the three expected instance keys
# ---------------------------------------------------------------------------

def test_result_has_exactly_three_instance_keys(
    hw4: HardwareProfile, sampler: ValueSampler
) -> None:
    model = LoadMetricModel()
    stressor = CpuStressor(utilization=0.5)
    result = model.compute(stressor, hw4, 60, sampler)
    assert "kernel.all.load" in result
    instances = result["kernel.all.load"]
    assert set(instances.keys()) == {"1 minute", "5 minute", "15 minute"}


# ---------------------------------------------------------------------------
# T022-9: load.py does NOT import from cpu.py
# ---------------------------------------------------------------------------

def test_load_module_does_not_import_cpu_module() -> None:

    import pmlogsynth.domains.load as load_module

    # Verify cpu module is not a dependency of load module
    source_file = load_module.__file__
    assert source_file is not None

    with open(source_file, encoding="utf-8") as fh:
        source = fh.read()

    assert "from pmlogsynth.domains.cpu" not in source
    assert "import pmlogsynth.domains.cpu" not in source
    assert "domains.cpu" not in source


# ---------------------------------------------------------------------------
# T022-10: EMA formula correctness — single step manual verification
# ---------------------------------------------------------------------------

def test_ema_single_step_correctness(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    """Verify EMA values match manual calculation for one step from 0."""
    model = LoadMetricModel()
    stressor = CpuStressor(utilization=1.0)  # load_raw = 4.0
    interval = 60

    result = model.compute(stressor, hw4, interval, sampler)

    alpha_1 = math.exp(-interval / 60.0)
    alpha_5 = math.exp(-interval / 300.0)
    alpha_15 = math.exp(-interval / 900.0)

    expected_1 = (1.0 - alpha_1) * 4.0   # prev=0
    expected_5 = (1.0 - alpha_5) * 4.0
    expected_15 = (1.0 - alpha_15) * 4.0

    loads = result["kernel.all.load"]
    assert abs(loads["1 minute"] - expected_1) < 1e-9
    assert abs(loads["5 minute"] - expected_5) < 1e-9
    assert abs(loads["15 minute"] - expected_15) < 1e-9
