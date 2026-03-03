"""Tier 1 unit tests for MemoryMetricModel (T019 / T009)."""

import pytest

from pmlogsynth.domains.memory import MemoryMetricModel
from pmlogsynth.pcp_constants import PM_SEM_COUNTER, PM_SEM_DISCRETE, PM_SEM_INSTANT
from pmlogsynth.profile import HardwareProfile, MemoryStressor
from pmlogsynth.sampler import ValueSampler

MEMORY_KB = 8388608  # 8 GiB in KB


def make_hw() -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=MEMORY_KB,
        disks=[],
        interfaces=[],
    )


def make_sampler(noise: float = 0.0) -> ValueSampler:
    return ValueSampler(noise=noise)


def make_model() -> MemoryMetricModel:
    return MemoryMetricModel()


def compute(stressor, hw=None, sampler=None):
    if hw is None:
        hw = make_hw()
    if sampler is None:
        sampler = make_sampler()
    model = make_model()
    return model.compute(stressor, hw, interval=60, sampler=sampler)


# ---------------------------------------------------------------------------
# T019-1: used + free == physmem for multiple used_ratio values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("used_ratio", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_used_plus_free_equals_physmem(used_ratio):
    """FR-008: used + free must equal physmem at every sample."""
    stressor = MemoryStressor(used_ratio=used_ratio, noise=0.0)
    result = compute(stressor)
    used = result["mem.util.used"][None]
    free = result["mem.util.free"][None]
    physmem = result["mem.physmem"][None]
    assert used + free == physmem, (
        f"used ({used}) + free ({free}) != physmem ({physmem}) "
        f"for used_ratio={used_ratio}"
    )


# ---------------------------------------------------------------------------
# T019-2: physmem is always exactly hardware.memory_kb
# ---------------------------------------------------------------------------


def test_physmem_is_constant():
    """mem.physmem must always equal hardware.memory_kb exactly."""
    hw = make_hw()
    stressor = MemoryStressor(used_ratio=0.7, noise=0.0)
    result = compute(stressor, hw=hw)
    assert result["mem.physmem"][None] == hw.memory_kb


def test_physmem_constant_high_noise():
    """mem.physmem must not be affected by noise."""
    hw = make_hw()
    stressor = MemoryStressor(used_ratio=0.5, noise=0.5)
    sampler = make_sampler(noise=0.5)
    model = make_model()
    for _ in range(10):
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result["mem.physmem"][None] == hw.memory_kb


# ---------------------------------------------------------------------------
# T019-3: cached <= used always
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("used_ratio", [0.0, 0.1, 0.5, 1.0])
def test_cached_lte_used(used_ratio):
    """mem.util.cached must never exceed mem.util.used."""
    stressor = MemoryStressor(used_ratio=used_ratio, noise=0.0)
    result = compute(stressor)
    cached = result["mem.util.cached"][None]
    used = result["mem.util.used"][None]
    assert cached <= used, f"cached ({cached}) > used ({used}) for used_ratio={used_ratio}"


# ---------------------------------------------------------------------------
# T019-4: noise=0.0 produces deterministic values
# ---------------------------------------------------------------------------


def test_deterministic_with_zero_noise():
    """With noise=0.0 and no seed, values must be deterministic across calls."""
    stressor = MemoryStressor(used_ratio=0.6, cache_ratio=0.25, noise=0.0)
    results = [compute(stressor) for _ in range(5)]
    first = results[0]
    for r in results[1:]:
        assert r["mem.util.used"][None] == first["mem.util.used"][None]
        assert r["mem.util.free"][None] == first["mem.util.free"][None]
        assert r["mem.util.cached"][None] == first["mem.util.cached"][None]
        assert r["mem.util.bufmem"][None] == first["mem.util.bufmem"][None]
        assert r["mem.physmem"][None] == first["mem.physmem"][None]


# ---------------------------------------------------------------------------
# T019-5: used_ratio=None defaults to 0.50
# ---------------------------------------------------------------------------


def test_used_ratio_none_defaults_to_50_percent():
    """When used_ratio is None, default of 0.50 is applied at compute time."""
    stressor_explicit = MemoryStressor(used_ratio=0.50, cache_ratio=0.30, noise=0.0)
    stressor_default = MemoryStressor(used_ratio=None, cache_ratio=0.30, noise=0.0)
    result_explicit = compute(stressor_explicit)
    result_default = compute(stressor_default)
    assert result_default["mem.util.used"][None] == result_explicit["mem.util.used"][None]
    assert result_default["mem.util.free"][None] == result_explicit["mem.util.free"][None]


# ---------------------------------------------------------------------------
# T019-6: cache_ratio=None defaults to 0.30
# ---------------------------------------------------------------------------


def test_cache_ratio_none_defaults_to_30_percent():
    """When cache_ratio is None, default of 0.30 is applied at compute time."""
    stressor_explicit = MemoryStressor(used_ratio=0.50, cache_ratio=0.30, noise=0.0)
    stressor_default = MemoryStressor(used_ratio=0.50, cache_ratio=None, noise=0.0)
    result_explicit = compute(stressor_explicit)
    result_default = compute(stressor_default)
    assert result_default["mem.util.cached"][None] == result_explicit["mem.util.cached"][None]


# ---------------------------------------------------------------------------
# T019-7: stressor=None uses all defaults
# ---------------------------------------------------------------------------


def test_none_stressor_uses_all_defaults():
    """Passing None as stressor should apply all defaults (used=0.50, cache=0.30)."""
    hw = make_hw()
    sampler = make_sampler()
    model = make_model()
    result = model.compute(None, hw, interval=60, sampler=sampler)

    physmem = result["mem.physmem"][None]
    used = result["mem.util.used"][None]
    free = result["mem.util.free"][None]

    # physmem invariant
    assert used + free == physmem
    # used should be 50% of physmem
    expected_used = int(physmem * 0.50)
    assert used == expected_used
    # cached should be 30% of used
    expected_cached = int(expected_used * 0.30)
    assert result["mem.util.cached"][None] == expected_cached
    # bufmem should be 5% of used
    expected_bufmem = int(expected_used * 0.05)
    assert result["mem.util.bufmem"][None] == expected_bufmem


# ---------------------------------------------------------------------------
# T019-8: metric_descriptors returns 5 descriptors
# ---------------------------------------------------------------------------


def test_metric_descriptors_count():
    """metric_descriptors() must return exactly 13 MetricDescriptor objects."""
    hw = make_hw()
    model = make_model()
    descriptors = model.metric_descriptors(hw)
    assert len(descriptors) == 13


def test_metric_descriptors_names():
    """metric_descriptors() must include all required metric names."""
    hw = make_hw()
    model = make_model()
    descriptors = model.metric_descriptors(hw)
    names = {d.name for d in descriptors}
    expected = {
        "mem.util.used",
        "mem.util.free",
        "mem.util.cached",
        "mem.util.bufmem",
        "mem.physmem",
        "mem.util.active",
        "mem.util.inactive",
        "mem.util.slab",
        "swap.used",
        "swap.pagesin",
        "swap.pagesout",
        "mem.vmstat.pgpgin",
        "mem.vmstat.pgpgout",
    }
    assert names == expected


def test_metric_descriptors_pmids():
    """Verify PMIDs match the research.md specification."""
    hw = make_hw()
    model = make_model()
    descriptors = model.metric_descriptors(hw)
    pmid_map = {d.name: d.pmid for d in descriptors}
    assert pmid_map["mem.util.used"] == (58, 0, 6)
    assert pmid_map["mem.util.free"] == (58, 0, 2)
    assert pmid_map["mem.util.cached"] == (58, 0, 13)
    assert pmid_map["mem.util.bufmem"] == (58, 0, 4)
    assert pmid_map["mem.physmem"] == (58, 0, 0)


def test_metric_descriptors_semantics():
    """mem.physmem must be PM_SEM_DISCRETE; util metrics must be PM_SEM_INSTANT."""
    hw = make_hw()
    model = make_model()
    descriptors = model.metric_descriptors(hw)
    sem_map = {d.name: d.sem for d in descriptors}
    assert sem_map["mem.physmem"] == PM_SEM_DISCRETE
    for name in ("mem.util.used", "mem.util.free", "mem.util.cached", "mem.util.bufmem"):
        assert sem_map[name] == PM_SEM_INSTANT


def test_metric_descriptors_indom_null():
    """All memory metrics must have indom=None (PM_INDOM_NULL)."""
    hw = make_hw()
    model = make_model()
    for d in model.metric_descriptors(hw):
        assert d.indom is None, f"{d.name} has non-null indom: {d.indom}"


# ---------------------------------------------------------------------------
# T009: new memory metrics (written before implementation — must fail initially)
# ---------------------------------------------------------------------------


def test_new_memory_metric_pmids():
    """Verify PMIDs for all 8 new memory metrics match research.md."""
    hw = make_hw()
    model = make_model()
    desc = {d.name: d for d in model.metric_descriptors(hw)}
    assert desc["mem.util.active"].pmid == (58, 0, 15)
    assert desc["mem.util.inactive"].pmid == (58, 0, 16)
    assert desc["mem.util.slab"].pmid == (58, 0, 12)
    assert desc["swap.used"].pmid == (58, 1, 0)
    assert desc["swap.pagesin"].pmid == (58, 1, 1)
    assert desc["swap.pagesout"].pmid == (58, 1, 2)
    assert desc["mem.vmstat.pgpgin"].pmid == (58, 2, 0)
    assert desc["mem.vmstat.pgpgout"].pmid == (58, 2, 1)


def test_instant_new_metrics_semantics():
    """mem.util.active/inactive/slab and swap.used must be PM_SEM_INSTANT."""
    hw = make_hw()
    model = make_model()
    desc = {d.name: d for d in model.metric_descriptors(hw)}
    for name in ("mem.util.active", "mem.util.inactive", "mem.util.slab", "swap.used"):
        assert desc[name].sem == PM_SEM_INSTANT, f"{name}: expected PM_SEM_INSTANT"


def test_counter_new_metrics_semantics():
    """swap.pagesin/out and pgpg* must be PM_SEM_COUNTER."""
    hw = make_hw()
    model = make_model()
    desc = {d.name: d for d in model.metric_descriptors(hw)}
    for name in ("swap.pagesin", "swap.pagesout", "mem.vmstat.pgpgin", "mem.vmstat.pgpgout"):
        assert desc[name].sem == PM_SEM_COUNTER, f"{name}: expected PM_SEM_COUNTER"


@pytest.mark.parametrize("used_ratio", [0.0, 0.40, 0.70])
def test_swap_is_zero_at_or_below_70pct(used_ratio):
    """swap.used, swap.pagesin, swap.pagesout must be 0 when used_ratio <= 0.70."""
    stressor = MemoryStressor(used_ratio=used_ratio, noise=0.0)
    result = compute(stressor)
    assert result["swap.used"][None] == 0, f"swap.used nonzero at used_ratio={used_ratio}"
    assert result["swap.pagesin"][None] == 0
    assert result["swap.pagesout"][None] == 0


@pytest.mark.parametrize("used_ratio", [0.75, 0.85, 1.0])
def test_swap_is_nonzero_above_70pct(used_ratio):
    """swap.used, swap.pagesin, swap.pagesout must be >0 when used_ratio > 0.70."""
    stressor = MemoryStressor(used_ratio=used_ratio, noise=0.0)
    result = compute(stressor)
    assert result["swap.used"][None] > 0, f"swap.used zero at used_ratio={used_ratio}"
    assert result["swap.pagesin"][None] > 0
    assert result["swap.pagesout"][None] > 0


def test_active_is_60pct_of_used():
    """mem.util.active = int(used_kb * 0.60)."""
    stressor = MemoryStressor(used_ratio=0.50, noise=0.0)
    result = compute(stressor)
    used = result["mem.util.used"][None]
    active = result["mem.util.active"][None]
    assert active == int(used * 0.60), f"active={active} expected {int(used * 0.60)}"


def test_inactive_is_25pct_of_used():
    """mem.util.inactive = int(used_kb * 0.25)."""
    stressor = MemoryStressor(used_ratio=0.50, noise=0.0)
    result = compute(stressor)
    used = result["mem.util.used"][None]
    inactive = result["mem.util.inactive"][None]
    assert inactive == int(used * 0.25), f"inactive={inactive} expected {int(used * 0.25)}"


def test_slab_is_4pct_of_physmem():
    """mem.util.slab = int(physmem_kb * 0.04)."""
    hw = make_hw()
    stressor = MemoryStressor(used_ratio=0.50, noise=0.0)
    result = compute(stressor, hw=hw)
    slab = result["mem.util.slab"][None]
    expected = int(hw.memory_kb * 0.04)
    assert slab == expected, f"slab={slab} expected {expected}"


def test_pgpgin_nonzero_with_memory_usage():
    """mem.vmstat.pgpgin must be nonzero when used_ratio > 0."""
    stressor = MemoryStressor(used_ratio=0.50, noise=0.0)
    result = compute(stressor)
    assert result["mem.vmstat.pgpgin"][None] > 0
    assert result["mem.vmstat.pgpgout"][None] > 0


def test_pgpgin_counter_accumulates():
    """mem.vmstat.pgpgin must accumulate monotonically across ticks."""
    hw = make_hw()
    sampler = make_sampler()
    model = make_model()
    stressor = MemoryStressor(used_ratio=0.60, noise=0.0)
    r1 = model.compute(stressor, hw, interval=60, sampler=sampler)
    r2 = model.compute(stressor, hw, interval=60, sampler=sampler)
    assert r2["mem.vmstat.pgpgin"][None] > r1["mem.vmstat.pgpgin"][None]
    assert r2["mem.vmstat.pgpgout"][None] > r1["mem.vmstat.pgpgout"][None]


def test_swap_counter_accumulates_above_threshold():
    """swap.pagesin counter must increase monotonically above the 70% threshold."""
    hw = make_hw()
    sampler = make_sampler()
    model = make_model()
    stressor = MemoryStressor(used_ratio=0.80, noise=0.0)
    r1 = model.compute(stressor, hw, interval=60, sampler=sampler)
    r2 = model.compute(stressor, hw, interval=60, sampler=sampler)
    assert r2["swap.pagesin"][None] > r1["swap.pagesin"][None]
    assert r2["swap.pagesout"][None] > r1["swap.pagesout"][None]


def test_new_metrics_present_in_compute_result():
    """compute() must include all 8 new metric names in result dict."""
    stressor = MemoryStressor(used_ratio=0.50, noise=0.0)
    result = compute(stressor)
    for name in (
        "mem.util.active",
        "mem.util.inactive",
        "mem.util.slab",
        "swap.used",
        "swap.pagesin",
        "swap.pagesout",
        "mem.vmstat.pgpgin",
        "mem.vmstat.pgpgout",
    ):
        assert name in result, f"Missing metric: {name}"
