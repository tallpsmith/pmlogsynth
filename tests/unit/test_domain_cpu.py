"""Tier 1 unit tests for CpuMetricModel (T018 / T007).

No PCP imports — pure Python only.
"""

from pmlogsynth.domains.cpu import CpuMetricModel
from pmlogsynth.pcp_constants import (
    PM_SEM_COUNTER,
    PM_SEM_DISCRETE,
    PM_TYPE_U32,
    PM_TYPE_U64,
    UNITS_MSEC,
    UNITS_NONE,
)
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
    """metric_descriptors() returns exactly 15 descriptors for any hardware."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    descriptors = model.metric_descriptors(hw)
    assert len(descriptors) == 15


def test_metric_descriptors_count_single_cpu() -> None:
    """Count is still 15 even for single-CPU hardware."""
    model = CpuMetricModel()
    hw = make_hw(cpus=1)
    assert len(model.metric_descriptors(hw)) == 15


def test_metric_descriptors_count_many_cpus() -> None:
    """Count is still 15 even for large CPU counts."""
    model = CpuMetricModel()
    hw = make_hw(cpus=128)
    assert len(model.metric_descriptors(hw)) == 15


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
    """Counter metrics are PM_TYPE_U64/PM_SEM_COUNTER; hinv.ncpu is discrete."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    for d in model.metric_descriptors(hw):
        if d.name == "hinv.ncpu":
            assert d.type_code == PM_TYPE_U32, "hinv.ncpu: expected PM_TYPE_U32"
            assert d.sem == PM_SEM_DISCRETE, "hinv.ncpu: expected PM_SEM_DISCRETE"
        else:
            assert d.type_code == PM_TYPE_U64, f"{d.name}: expected PM_TYPE_U64"
            assert d.sem == PM_SEM_COUNTER, f"{d.name}: expected PM_SEM_COUNTER"


def test_descriptor_units_msec() -> None:
    """Counter metrics have UNITS_MSEC; hinv.ncpu has UNITS_NONE."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    for d in model.metric_descriptors(hw):
        if d.name == "hinv.ncpu":
            assert d.units == UNITS_NONE, f"hinv.ncpu: unexpected units {d.units}"
        else:
            assert d.units == UNITS_MSEC, f"{d.name}: unexpected units {d.units}"


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
    """With 0% utilization, all active ticks are 0 and idle owns everything."""
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
    # idle = all ticks (4 cpus * 60s * 1000ms)
    assert result["kernel.all.cpu.idle"][None] == 4 * 60 * 1000


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

    # Default utilization is 0.0 — busy ticks are 0, idle owns everything
    assert isinstance(result, dict)
    assert "kernel.all.cpu.user" in result
    assert "kernel.all.cpu.idle" in result
    assert result["kernel.all.cpu.user"][None] == 0
    assert result["kernel.all.cpu.idle"][None] == 4 * 60 * 1000


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
    """All expected metric names are present in the compute() result dict."""
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
        "kernel.all.cpu.nice",
        "kernel.all.cpu.vuser",
        "kernel.all.cpu.vnice",
        "kernel.all.cpu.intr",
        "kernel.all.cpu.guest",
        "kernel.all.cpu.guest_nice",
        "hinv.ncpu",
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


# ---------------------------------------------------------------------------
# idle correctness — the core invariant that makes pmstat show real utilization
# ---------------------------------------------------------------------------


def test_partial_utilization_idle_is_dominant() -> None:
    """At 15% utilization, idle ticks must exceed user+sys+iowait combined.

    Without this, pmstat shows the same ratio (70/20/10) at every utilization
    level and the spike is invisible.
    """
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(
        utilization=0.15,
        user_ratio=0.70,
        sys_ratio=0.20,
        iowait_ratio=0.10,
        noise=0.0,
    )

    result = model.compute(stressor, hw, interval=60, sampler=sampler)

    idle = result["kernel.all.cpu.idle"][None]
    user = result["kernel.all.cpu.user"][None]
    sys_ = result["kernel.all.cpu.sys"][None]
    iowait = result["kernel.all.cpu.wait.total"][None]

    assert idle > user + sys_ + iowait, (
        "At 15% utilization idle should dominate; "
        "got idle={} user={} sys={} iowait={}".format(idle, user, sys_, iowait)
    )


def test_spike_has_less_idle_than_baseline() -> None:
    """90% utilization produces far fewer idle ticks than 15% utilization."""
    model = CpuMetricModel()
    hw = make_hw(cpus=1)
    interval = 60

    sampler_base = make_sampler(noise=0.0)
    base_result = model.compute(
        CpuStressor(utilization=0.15, noise=0.0), hw, interval=interval, sampler=sampler_base
    )

    sampler_spike = make_sampler(noise=0.0)
    spike_result = model.compute(
        CpuStressor(utilization=0.90, noise=0.0), hw, interval=interval, sampler=sampler_spike
    )

    base_idle = base_result["kernel.all.cpu.idle"][None]
    spike_idle = spike_result["kernel.all.cpu.idle"][None]

    assert base_idle > spike_idle, (
        "Baseline idle ({}) should exceed spike idle ({})".format(base_idle, spike_idle)
    )


def test_idle_plus_busy_equals_all_ticks() -> None:
    """Sum of ALL cpu time buckets (including sub-metrics) must equal total ticks."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.60, noise=0.0)
    interval = 60

    result = model.compute(stressor, hw, interval=interval, sampler=sampler)

    all_ticks_ms = hw.cpus * interval * 1000
    total = (
        result["kernel.all.cpu.user"][None]
        + result["kernel.all.cpu.sys"][None]
        + result["kernel.all.cpu.idle"][None]
        + result["kernel.all.cpu.wait.total"][None]
        + result["kernel.all.cpu.steal"][None]
        + result["kernel.all.cpu.nice"][None]
        + result["kernel.all.cpu.vuser"][None]
        + result["kernel.all.cpu.vnice"][None]
        + result["kernel.all.cpu.intr"][None]
        + result["kernel.all.cpu.guest"][None]
        + result["kernel.all.cpu.guest_nice"][None]
    )
    assert total == all_ticks_ms, "Expected {} ms total, got {}".format(all_ticks_ms, total)


# ---------------------------------------------------------------------------
# T007: new sub-metric descriptors (written before implementation — must fail)
# ---------------------------------------------------------------------------


def test_new_cpu_sub_metric_descriptors_present() -> None:
    """Descriptors for the 6 new CPU sub-metrics must be registered."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    names = {d.name for d in model.metric_descriptors(hw)}
    for expected in (
        "kernel.all.cpu.nice",
        "kernel.all.cpu.vuser",
        "kernel.all.cpu.vnice",
        "kernel.all.cpu.intr",
        "kernel.all.cpu.guest",
        "kernel.all.cpu.guest_nice",
    ):
        assert expected in names, "Missing descriptor: {}".format(expected)


def test_hinv_ncpu_descriptor_present() -> None:
    """hinv.ncpu descriptor must be registered."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    names = {d.name for d in model.metric_descriptors(hw)}
    assert "hinv.ncpu" in names


def test_hinv_ncpu_descriptor_is_discrete() -> None:
    """hinv.ncpu must have is_discrete=True, PM_SEM_DISCRETE, PM_TYPE_U32, UNITS_NONE."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    desc = {d.name: d for d in model.metric_descriptors(hw)}
    d = desc["hinv.ncpu"]
    assert d.is_discrete is True
    assert d.sem == PM_SEM_DISCRETE
    assert d.type_code == PM_TYPE_U32
    assert d.units == UNITS_NONE
    assert d.indom is None
    assert d.pmid == (60, 0, 32)


def test_hinv_ncpu_compute_equals_hardware_cpus() -> None:
    """hinv.ncpu compute value must equal hardware.cpus."""
    model = CpuMetricModel()
    hw = make_hw(cpus=8)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.5)
    result = model.compute(stressor, hw, interval=60, sampler=sampler)
    assert result["hinv.ncpu"][None] == 8


def test_hinv_ncpu_falls_back_to_four_when_none() -> None:
    """hinv.ncpu falls back to hardware.cpus even when stressor is None."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    result = model.compute(None, hw, interval=60, sampler=sampler)
    assert result["hinv.ncpu"][None] == 4


def test_sub_metrics_are_positive_at_nonzero_utilization() -> None:
    """All 6 sub-metrics emit positive values when utilization > 0."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.8, noise=0.0)
    result = model.compute(stressor, hw, interval=60, sampler=sampler)
    for name in (
        "kernel.all.cpu.nice",
        "kernel.all.cpu.vuser",
        "kernel.all.cpu.vnice",
        "kernel.all.cpu.intr",
        "kernel.all.cpu.guest",
        "kernel.all.cpu.guest_nice",
    ):
        assert result[name][None] > 0, "{} should be positive at 80% utilization".format(name)


def test_sub_metrics_are_zero_at_zero_utilization() -> None:
    """All sub-metrics are zero when utilization is 0."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.0, noise=0.0)
    result = model.compute(stressor, hw, interval=60, sampler=sampler)
    for name in (
        "kernel.all.cpu.nice",
        "kernel.all.cpu.vuser",
        "kernel.all.cpu.vnice",
        "kernel.all.cpu.intr",
        "kernel.all.cpu.guest",
        "kernel.all.cpu.guest_nice",
    ):
        assert result[name][None] == 0, "{} should be 0 at 0% utilization".format(name)


def test_new_sub_metric_pmids() -> None:
    """Verify PMIDs for all 6 new CPU sub-metrics match research.md."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    desc = {d.name: d for d in model.metric_descriptors(hw)}
    assert desc["kernel.all.cpu.nice"].pmid == (60, 0, 27)
    assert desc["kernel.all.cpu.vuser"].pmid == (60, 0, 78)
    assert desc["kernel.all.cpu.vnice"].pmid == (60, 0, 82)
    assert desc["kernel.all.cpu.intr"].pmid == (60, 0, 34)
    assert desc["kernel.all.cpu.guest"].pmid == (60, 0, 60)
    assert desc["kernel.all.cpu.guest_nice"].pmid == (60, 0, 81)


def test_sub_metrics_accumulate_as_counters() -> None:
    """CPU sub-metric counters increase monotonically across ticks."""
    model = CpuMetricModel()
    hw = make_hw(cpus=4)
    sampler = make_sampler(noise=0.0)
    stressor = CpuStressor(utilization=0.5, noise=0.0)
    result1 = model.compute(stressor, hw, interval=60, sampler=sampler)
    result2 = model.compute(stressor, hw, interval=60, sampler=sampler)
    for name in ("kernel.all.cpu.nice", "kernel.all.cpu.vuser", "kernel.all.cpu.intr"):
        assert result2[name][None] > result1[name][None], (
            "{} counter did not increase".format(name)
        )
