"""Tier 1 unit tests for SystemMetricModel (T006/T008)."""

import math

import pytest

from pmlogsynth.domains.system import SystemMetricModel
from pmlogsynth.pcp_constants import PM_SEM_COUNTER, PM_SEM_INSTANT, PM_TYPE_FLOAT, PM_TYPE_U32
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
# metric_descriptors — load average
# ---------------------------------------------------------------------------

def test_metric_descriptors_count(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    descriptors = model.metric_descriptors(hw4)
    assert len(descriptors) == 5


def test_metric_descriptors_has_load(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    names = {d.name for d in model.metric_descriptors(hw4)}
    assert "kernel.all.load" in names


def test_metric_descriptors_load_pmid(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    desc = {d.name: d for d in model.metric_descriptors(hw4)}
    assert desc["kernel.all.load"].pmid == (60, 2, 0)


def test_metric_descriptors_load_type_and_sem(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    desc = {d.name: d for d in model.metric_descriptors(hw4)}
    assert desc["kernel.all.load"].type_code == PM_TYPE_FLOAT
    assert desc["kernel.all.load"].sem == PM_SEM_INSTANT


def test_metric_descriptors_load_indom(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    desc = {d.name: d for d in model.metric_descriptors(hw4)}
    assert desc["kernel.all.load"].indom == (60, 3)


# ---------------------------------------------------------------------------
# metric_descriptors — new scheduler/interrupt metrics (T008)
# ---------------------------------------------------------------------------

def test_descriptors_include_intr(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    desc = {d.name: d for d in model.metric_descriptors(hw4)}
    assert "kernel.all.intr" in desc
    assert desc["kernel.all.intr"].pmid == (60, 0, 12)
    assert desc["kernel.all.intr"].type_code == PM_TYPE_U32
    assert desc["kernel.all.intr"].sem == PM_SEM_COUNTER
    assert desc["kernel.all.intr"].indom is None


def test_descriptors_include_pswitch(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    desc = {d.name: d for d in model.metric_descriptors(hw4)}
    assert "kernel.all.pswitch" in desc
    assert desc["kernel.all.pswitch"].pmid == (60, 0, 7)
    assert desc["kernel.all.pswitch"].type_code == PM_TYPE_U32
    assert desc["kernel.all.pswitch"].sem == PM_SEM_COUNTER


def test_descriptors_include_running(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    desc = {d.name: d for d in model.metric_descriptors(hw4)}
    assert "kernel.all.running" in desc
    assert desc["kernel.all.running"].pmid == (60, 0, 15)
    assert desc["kernel.all.running"].type_code == PM_TYPE_U32
    assert desc["kernel.all.running"].sem == PM_SEM_INSTANT


def test_descriptors_include_blocked(hw4: HardwareProfile) -> None:
    model = SystemMetricModel()
    desc = {d.name: d for d in model.metric_descriptors(hw4)}
    assert "kernel.all.blocked" in desc
    assert desc["kernel.all.blocked"].pmid == (60, 0, 16)
    assert desc["kernel.all.blocked"].type_code == PM_TYPE_U32
    assert desc["kernel.all.blocked"].sem == PM_SEM_INSTANT


# ---------------------------------------------------------------------------
# compute() — load average (existing behaviour preserved)
# ---------------------------------------------------------------------------

def test_initial_load_zero_utilization(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=0.0)
    result = model.compute(stressor, hw4, 60, sampler)
    loads = result["kernel.all.load"]
    assert loads["1 minute"] == 0.0
    assert loads["5 minute"] == 0.0
    assert loads["15 minute"] == 0.0


def test_initial_load_none_stressor(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    model = SystemMetricModel()
    result = model.compute(None, hw4, 60, sampler)
    loads = result["kernel.all.load"]
    assert loads["1 minute"] == 0.0
    assert loads["5 minute"] == 0.0
    assert loads["15 minute"] == 0.0


def test_load_convergence_toward_load_raw(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=1.0)
    for _ in range(200):
        result = model.compute(stressor, hw4, 60, sampler)
    load_1 = result["kernel.all.load"]["1 minute"]
    assert abs(load_1 - 4.0) < 0.01, f"Expected load_1 near 4.0, got {load_1}"


def test_load_1min_responds_faster_than_15min(
    hw1: HardwareProfile, sampler: ValueSampler
) -> None:
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=1.0)
    for _ in range(10):
        result = model.compute(stressor, hw1, 60, sampler)
    loads = result["kernel.all.load"]
    load_1 = loads["1 minute"]
    load_15 = loads["15 minute"]
    assert abs(load_1 - 1.0) < abs(load_15 - 1.0), (
        f"load_1={load_1} should be closer to 1.0 than load_15={load_15}"
    )


def test_all_load_instances_positive_after_nonzero_util(
    hw1: HardwareProfile, sampler: ValueSampler
) -> None:
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=1.0)
    result = model.compute(stressor, hw1, 60, sampler)
    loads = result["kernel.all.load"]
    assert loads["1 minute"] > 0
    assert loads["5 minute"] > 0
    assert loads["15 minute"] > 0


def test_load_result_has_three_instance_keys(
    hw4: HardwareProfile, sampler: ValueSampler
) -> None:
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=0.5)
    result = model.compute(stressor, hw4, 60, sampler)
    assert "kernel.all.load" in result
    assert set(result["kernel.all.load"].keys()) == {"1 minute", "5 minute", "15 minute"}


def test_ema_single_step_correctness(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=1.0)
    interval = 60

    result = model.compute(stressor, hw4, interval, sampler)

    alpha_1 = math.exp(-interval / 60.0)
    alpha_5 = math.exp(-interval / 300.0)
    alpha_15 = math.exp(-interval / 900.0)

    expected_1 = (1.0 - alpha_1) * 4.0
    expected_5 = (1.0 - alpha_5) * 4.0
    expected_15 = (1.0 - alpha_15) * 4.0

    loads = result["kernel.all.load"]
    assert abs(loads["1 minute"] - expected_1) < 1e-9
    assert abs(loads["5 minute"] - expected_5) < 1e-9
    assert abs(loads["15 minute"] - expected_15) < 1e-9


# ---------------------------------------------------------------------------
# compute() — scheduler/interrupt metrics (T008 — written before implementation)
# ---------------------------------------------------------------------------

def test_zero_utilization_intr_and_pswitch_zero(
    hw4: HardwareProfile, sampler: ValueSampler
) -> None:
    """With 0% utilization, intr and pswitch counters stay at 0."""
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=0.0)
    result = model.compute(stressor, hw4, 60, sampler)
    assert result["kernel.all.intr"][None] == 0
    assert result["kernel.all.pswitch"][None] == 0
    assert result["kernel.all.running"][None] == 0
    assert result["kernel.all.blocked"][None] == 0


def test_full_utilization_intr_positive(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    """At 100% utilization intr and pswitch counters are positive after first tick."""
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=1.0)
    result = model.compute(stressor, hw4, 60, sampler)
    assert result["kernel.all.intr"][None] > 0
    assert result["kernel.all.pswitch"][None] > 0


def test_running_scales_with_utilization(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    """kernel.all.running should equal round(utilization * num_cpus)."""
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=0.75)
    result = model.compute(stressor, hw4, 60, sampler)
    # 4 cpus * 0.75 = 3.0 → round → 3
    assert result["kernel.all.running"][None] == 3


def test_blocked_is_10pct_of_running(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    """kernel.all.blocked = round(running * 0.1)."""
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=1.0)
    result = model.compute(stressor, hw4, 60, sampler)
    running = result["kernel.all.running"][None]
    blocked = result["kernel.all.blocked"][None]
    assert blocked == round(running * 0.1)


def test_intr_counter_accumulates_across_ticks(
    hw4: HardwareProfile, sampler: ValueSampler
) -> None:
    """kernel.all.intr counter is monotonically increasing across ticks."""
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=0.5)
    result1 = model.compute(stressor, hw4, 60, sampler)
    result2 = model.compute(stressor, hw4, 60, sampler)
    assert result2["kernel.all.intr"][None] > result1["kernel.all.intr"][None]
    assert result2["kernel.all.pswitch"][None] > result1["kernel.all.pswitch"][None]


def test_pswitch_rate_higher_than_intr_rate(hw4: HardwareProfile, sampler: ValueSampler) -> None:
    """pswitch (cs_rate=5000) should exceed intr (intr_rate=1000) at same utilization."""
    model = SystemMetricModel()
    stressor = CpuStressor(utilization=1.0)
    result = model.compute(stressor, hw4, 60, sampler)
    assert result["kernel.all.pswitch"][None] > result["kernel.all.intr"][None]


def test_system_module_does_not_import_cpu_module() -> None:
    """system.py must not import from cpu.py (no cross-domain coupling)."""
    import pmlogsynth.domains.system as system_module

    source_file = system_module.__file__
    assert source_file is not None

    with open(source_file, encoding="utf-8") as fh:
        source = fh.read()

    assert "from pmlogsynth.domains.cpu" not in source
    assert "import pmlogsynth.domains.cpu" not in source
    assert "domains.cpu" not in source
