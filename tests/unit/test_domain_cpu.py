"""Tier 1 unit tests for CpuMetricModel (T018).

No PCP imports — pure Python only.
"""

from pmlogsynth.domains.cpu import CpuMetricModel
from pmlogsynth.profile import CpuStressor, HardwareProfile
from pmlogsynth.sampler import ValueSampler


def make_hw(cpus: int = 4) -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=cpus,
        memory_kb=8388608,
        disks=[],
        interfaces=[],
    )


def make_sampler(noise: float = 0.0, seed: int = 42) -> ValueSampler:
    return ValueSampler(noise=noise, seed=seed)


# ---------------------------------------------------------------------------
# metric_descriptors tests
# ---------------------------------------------------------------------------


def test_metric_descriptors_count() -> None:
    """metric_descriptors() returns exactly 8 descriptors for any hardware."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    descriptors = model.metric_descriptors(hw)
    assert len(descriptors) == 8


def test_metric_descriptors_count_single_cpu() -> None:
    """Count is still 8 even for single-CPU hardware."""
    model = CpuMetricModel()
    hw = make_hw(cpus=1)
    assert len(model.metric_descriptors(hw)) == 8


def test_metric_descriptors_count_many_cpus() -> None:
    """Count is still 8 even for large CPU counts."""
    model = CpuMetricModel()
    hw = make_hw(cpus=128)
    assert len(model.metric_descriptors(hw)) == 8


def test_per_cpu_indom_is_set() -> None:
    """Per-CPU metrics have a non-None indom."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    descriptors = model.metric_descriptors(hw)
    per_cpu_names = {
        "kernel.percpu.cpu.user",
        "kernel.percpu.cpu.sys",
        "kernel.percpu.cpu.idle",
    }
    for d in descriptors:
        if d.name in per_cpu_names:
            assert d.indom is not None, "Per-CPU metric should have indom set"
            assert d.indom == (60, 0)


def test_aggregate_indom_is_none() -> None:
    """Aggregate metrics have indom=None (PM_INDOM_NULL)."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    descriptors = model.metric_descriptors(hw)
    aggregate_names = {
        "kernel.all.cpu.user",
        "kernel.all.cpu.sys",
        "kernel.all.cpu.idle",
        "kernel.all.cpu.wait.total",
        "kernel.all.cpu.steal",
    }
    for d in descriptors:
        if d.name in aggregate_names:
            assert d.indom is None, "Aggregate metric should have indom=None"


def test_descriptor_pmids() -> None:
    """Verify PMID tuples for all metrics match the PMID table."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    descriptors = {d.name: d for d in model.metric_descriptors(hw)}

    assert descriptors["kernel.all.cpu.user"].pmid == (60, 0, 20)
    assert descriptors["kernel.all.cpu.sys"].pmid == (60, 0, 22)
    assert descriptors["kernel.all.cpu.idle"].pmid == (60, 0, 21)
    assert descriptors["kernel.all.cpu.wait.total"].pmid == (60, 0, 35)
    assert descriptors["kernel.all.cpu.steal"].pmid == (60, 0, 58)
    assert descriptors["kernel.percpu.cpu.user"].pmid == (60, 10, 20)
    assert descriptors["kernel.percpu.cpu.sys"].pmid == (60, 10, 22)
    assert descriptors["kernel.percpu.cpu.idle"].pmid == (60, 10, 21)


def test_descriptor_type_and_sem() -> None:
    """All metrics must be PM_TYPE_U64 (3) and PM_SEM_COUNTER (1)."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    for d in model.metric_descriptors(hw):
        assert d.type_code == 3, "Expected PM_TYPE_U64=3"
        assert d.sem == 1, "Expected PM_SEM_COUNTER=1"


def test_descriptor_units_msec() -> None:
    """All metrics must have millisecond time units tuple."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    expected_units = (0, 1, 0, 0, 2, 0)
    for d in model.metric_descriptors(hw):
        assert d.units == expected_units, f"{d.name}: unexpected units {d.units}"


# ---------------------------------------------------------------------------
# compute() instance count tests
# ---------------------------------------------------------------------------


def test_per_cpu_instance_count_4cpus() -> None:
    """4-CPU hardware produces cpu0..cpu3 instance keys in per-CPU metrics."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler()
    stressor = CpuStressor(utilization=0.5)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    for metric in ("kernel.percpu.cpu.user", "kernel.percpu.cpu.sys", "kernel.percpu.cpu.idle"):
        instances = result[metric]
        assert len(instances) == 4
        for i in range(4):
            assert "cpu{}".format(i) in instances


def test_per_cpu_instance_count_1cpu() -> None:
    """1-CPU hardware produces only cpu0."""
    model = CpuMetricModel()
    hw = make_hw(cpus=1)
    sampler = make_sampler()
    stressor = CpuStressor(utilization=0.5)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    for metric in ("kernel.percpu.cpu.user", "kernel.percpu.cpu.sys", "kernel.percpu.cpu.idle"):
        instances = result[metric]
        assert len(instances) == 1
        assert "cpu0" in instances


# ---------------------------------------------------------------------------
# compute() correctness tests
# ---------------------------------------------------------------------------


def test_zero_utilization_all_idle() -> None:
    """With 0% utilization, all active ticks are 0 and idle dominates."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.0, noise=0.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    # With 0% utilization, user/sys/wait/steal all should be 0
    assert result["kernel.all.cpu.user"][None] == 0
    assert result["kernel.all.cpu.sys"][None] == 0
    assert result["kernel.all.cpu.wait.total"][None] == 0
    assert result["kernel.all.cpu.steal"][None] == 0
    # idle should be 0 too since total_ticks=0
    assert result["kernel.all.cpu.idle"][None] == 0


def test_full_utilization_idle_near_zero() -> None:
    """With 100% utilization and no noise, idle ticks should be 0."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    # user+sys+iowait = 0.7+0.2+0.1 = 1.0 → idle = 0
    stressor = CpuStressor(
        utilization=1.0,
        user_ratio=0.70,
        sys_ratio=0.20,
        iowait_ratio=0.10,
        noise=0.0,
    )

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    assert result["kernel.all.cpu.idle"][None] == 0


def test_no_stressor_uses_defaults() -> None:
    """Passing None stressor uses all defaults and returns valid dict."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)

    result = model.compute(None, hw, interval=60, sampler=sampler)

    # Default utilization is 0.0 — all values should be 0
    assert isinstance(result, dict)
    assert "kernel.all.cpu.user" in result
    assert "kernel.all.cpu.idle" in result
    assert result["kernel.all.cpu.user"][None] == 0


def test_noise_zero_deterministic() -> None:
    """With noise=0, two identical calls with fresh samplers produce identical results."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    stressor = CpuStressor(utilization=0.6, noise=0.0)

    sampler1 = make_sampler(noise=0.0, seed=42)
    result1 = model.compute(stressor, hw, interval=60, sampler=sampler1)

    sampler2 = make_sampler(noise=0.0, seed=42)
    result2 = model.compute(stressor, hw, interval=60, sampler=sampler2)

    assert result1["kernel.all.cpu.user"] == result2["kernel.all.cpu.user"]
    assert result1["kernel.all.cpu.sys"] == result2["kernel.all.cpu.sys"]
    assert result1["kernel.all.cpu.idle"] == result2["kernel.all.cpu.idle"]


def test_counter_accumulation_increases() -> None:
    """Second compute() call returns higher counter values than the first."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.5, noise=0.0)

    result1 = model.compute(stressor, hw, interval=60, sampler=sampler)
    result2 = model.compute(stressor, hw, interval=60, sampler=sampler)

    # Counters should be monotonically increasing
    assert result2["kernel.all.cpu.user"][None] > result1["kernel.all.cpu.user"][None]
    assert result2["kernel.all.cpu.sys"][None] > result1["kernel.all.cpu.sys"][None]


def test_all_metric_names_present() -> None:
    """All 8 metric names are present in the result dict."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler()
    stressor = CpuStressor(utilization=0.5)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    expected_names = {
        "kernel.all.cpu.user",
        "kernel.all.cpu.sys",
        "kernel.all.cpu.idle",
        "kernel.all.cpu.wait.total",
        "kernel.all.cpu.steal",
        "kernel.percpu.cpu.user",
        "kernel.percpu.cpu.sys",
        "kernel.percpu.cpu.idle",
    }
    assert set(result.keys()) == expected_names


def test_aggregate_values_are_integers() -> None:
    """Aggregate counter values returned by compute() are Python ints."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.5, noise=0.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    for name in ("kernel.all.cpu.user", "kernel.all.cpu.sys", "kernel.all.cpu.idle",
                 "kernel.all.cpu.wait.total", "kernel.all.cpu.steal"):
        val = result[name][None]
        assert isinstance(val, int), "{}: expected int, got {}".format(name, type(val))


def test_per_cpu_values_are_integers() -> None:
    """Per-CPU counter values are Python ints."""
    model = CpuMetricModel()
    hw = make_hw(cpus=2)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.5, noise=0.0)

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    for name in ("kernel.percpu.cpu.user", "kernel.percpu.cpu.sys", "kernel.percpu.cpu.idle"):
        for inst_key, val in result[name].items():
            assert isinstance(val, int), "{}/{}: expected int, got {}".format(
                name, inst_key, type(val)
            )


def test_steal_always_zero() -> None:
    """kernel.all.cpu.steal should always be 0 (steal not modelled)."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.8, noise=0.0)

    # Call twice to confirm it stays at 0
    model.compute(stressor, hw, interval=60, sampler=sampler)
    result2 = model.compute(stressor, hw, interval=60, sampler=sampler)

    assert result2["kernel.all.cpu.steal"][None] == 0
