"""Tier 1 unit tests for MemoryMetricModel (T019)."""

import pytest

from pmlogsynth.domains.memory import MemoryMetricModel
from pmlogsynth.pcp_constants import PM_SEM_DISCRETE, PM_SEM_INSTANT
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
    """metric_descriptors() must return exactly 5 MetricDescriptor objects."""
    hw = make_hw()
    model = make_model()
    descriptors = model.metric_descriptors(hw)
    assert len(descriptors) == 5


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
