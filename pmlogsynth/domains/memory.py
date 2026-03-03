"""Memory domain metric model."""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.pcp_constants import (
    PM_SEM_COUNTER,
    PM_SEM_DISCRETE,
    PM_SEM_INSTANT,
    PM_TYPE_32,
    PM_TYPE_U32,
    PM_TYPE_U64,
    UNITS_COUNT,
    UNITS_KBYTE,
)
from pmlogsynth.profile import HardwareProfile, MemoryStressor
from pmlogsynth.sampler import ValueSampler

_DEFAULT_USED_RATIO = 0.50
_DEFAULT_CACHE_RATIO = 0.30
_BUFMEM_FRACTION = 0.05

# Swap pressure threshold: pagesin/out and swap.used are zero below this
_SWAP_THRESHOLD = 0.70


class MemoryMetricModel(MetricModel):
    """Generates mem.util.*, mem.physmem, swap.*, and mem.vmstat.* metrics."""

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        return [
            # Existing metrics
            MetricDescriptor(
                name="mem.util.used",
                pmid=(58, 0, 6),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.util.free",
                pmid=(58, 0, 2),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.util.cached",
                pmid=(58, 0, 13),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.util.bufmem",
                pmid=(58, 0, 4),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.physmem",
                pmid=(58, 0, 0),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_KBYTE,
            ),
            # New instant metrics
            MetricDescriptor(
                name="mem.util.active",
                pmid=(58, 0, 15),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.util.inactive",
                pmid=(58, 0, 16),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.util.slab",
                pmid=(58, 0, 12),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_KBYTE,
            ),
            # Swap metrics (cluster 1)
            MetricDescriptor(
                name="swap.used",
                pmid=(58, 1, 0),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="swap.pagesin",
                pmid=(58, 1, 1),
                type_code=PM_TYPE_32,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="swap.pagesout",
                pmid=(58, 1, 2),
                type_code=PM_TYPE_32,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            # Paging metrics (cluster 2)
            MetricDescriptor(
                name="mem.vmstat.pgpgin",
                pmid=(58, 2, 0),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="mem.vmstat.pgpgout",
                pmid=(58, 2, 1),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
        ]

    def compute(
        self,
        stressor: Any,
        hardware: HardwareProfile,
        interval: int,
        sampler: ValueSampler,
    ) -> Dict[str, Dict[Optional[str], Any]]:
        mem = stressor if isinstance(stressor, MemoryStressor) else MemoryStressor()

        used_ratio = mem.used_ratio if mem.used_ratio is not None else _DEFAULT_USED_RATIO
        cache_ratio = mem.cache_ratio if mem.cache_ratio is not None else _DEFAULT_CACHE_RATIO
        noise = mem.noise

        noisy_used_ratio = sampler.apply_noise(used_ratio, noise)
        noisy_used_ratio = max(0.0, min(1.0, noisy_used_ratio))

        physmem_kb = hardware.memory_kb
        used_kb = int(physmem_kb * noisy_used_ratio)
        free_kb = physmem_kb - used_kb  # guarantees used + free == physmem
        cached_kb = int(used_kb * cache_ratio)
        bufmem_kb = int(used_kb * _BUFMEM_FRACTION)

        # New instant metrics derived from used_kb
        active_kb = int(used_kb * 0.60)
        inactive_kb = int(used_kb * 0.25)
        slab_kb = int(physmem_kb * 0.04)

        # Swap pressure — only above 70% used_ratio
        pressure = max(0.0, (noisy_used_ratio - _SWAP_THRESHOLD) / (1.0 - _SWAP_THRESHOLD))
        swap_total_kb = physmem_kb
        swap_used_kb = int(swap_total_kb * pressure * 0.5)
        swap_pagesin_delta = pressure * 100 * interval
        swap_pagesout_delta = pressure * 80 * interval

        # Paging counters — proportional to memory usage, always non-zero when memory in use
        pgpgin_delta = (used_kb / physmem_kb) * 200 * interval if physmem_kb > 0 else 0.0
        pgpgout_delta = (used_kb / physmem_kb) * 150 * interval if physmem_kb > 0 else 0.0

        return {
            "mem.util.used": {None: used_kb},
            "mem.util.free": {None: free_kb},
            "mem.util.cached": {None: cached_kb},
            "mem.util.bufmem": {None: bufmem_kb},
            "mem.physmem": {None: physmem_kb},
            "mem.util.active": {None: active_kb},
            "mem.util.inactive": {None: inactive_kb},
            "mem.util.slab": {None: slab_kb},
            "swap.used": {None: swap_used_kb},
            "swap.pagesin": {None: sampler.accumulate("swap.pagesin", swap_pagesin_delta)},
            "swap.pagesout": {None: sampler.accumulate("swap.pagesout", swap_pagesout_delta)},
            "mem.vmstat.pgpgin": {None: sampler.accumulate("mem.pgpgin", pgpgin_delta)},
            "mem.vmstat.pgpgout": {None: sampler.accumulate("mem.pgpgout", pgpgout_delta)},
        }
