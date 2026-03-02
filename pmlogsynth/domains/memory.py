"""Memory domain metric model."""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.profile import HardwareProfile, MemoryStressor
from pmlogsynth.sampler import ValueSampler

_PM_TYPE_U64 = 3
_PM_SEM_INSTANT = 3
_PM_SEM_DISCRETE = 4
_PM_SPACE_KBYTE = 1
_UNITS_KBYTE = (1, 0, 0, _PM_SPACE_KBYTE, 0, 0)

_DEFAULT_USED_RATIO = 0.50
_DEFAULT_CACHE_RATIO = 0.30
_BUFMEM_FRACTION = 0.05


class MemoryMetricModel(MetricModel):
    """Generates mem.util.* and mem.physmem metrics."""

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        return [
            MetricDescriptor(
                name="mem.util.used",
                pmid=(58, 0, 6),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_INSTANT,
                units=_UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.util.free",
                pmid=(58, 0, 2),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_INSTANT,
                units=_UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.util.cached",
                pmid=(58, 0, 13),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_INSTANT,
                units=_UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.util.bufmem",
                pmid=(58, 0, 4),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_INSTANT,
                units=_UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="mem.physmem",
                pmid=(58, 0, 0),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_DISCRETE,
                units=_UNITS_KBYTE,
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

        return {
            "mem.util.used": {None: used_kb},
            "mem.util.free": {None: free_kb},
            "mem.util.cached": {None: cached_kb},
            "mem.util.bufmem": {None: bufmem_kb},
            "mem.physmem": {None: physmem_kb},
        }
