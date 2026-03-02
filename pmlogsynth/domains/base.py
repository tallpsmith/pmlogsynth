"""Abstract base class for domain-specific PCP metric models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pmlogsynth.profile import HardwareProfile
from pmlogsynth.sampler import ValueSampler


@dataclass
class MetricDescriptor:
    """Registration parameters for one PCP metric."""

    name: str
    pmid: Tuple[int, int, int]           # (domain, cluster, item)
    type_code: int                        # PM_TYPE_* constant value
    indom: Optional[Tuple[int, int]]      # (domain, serial) or None for PM_INDOM_NULL
    sem: int                              # PM_SEM_* constant value
    # args to pmiUnits(dimSpace, dimTime, dimCount, scaleSpace, scaleTime, scaleCount)
    units: Tuple[int, int, int, int, int, int]


class MetricModel(ABC):
    """Abstract base class for all domain-specific metric models."""

    @abstractmethod
    def compute(
        self,
        stressor: Any,
        hardware: HardwareProfile,
        interval: int,
        sampler: ValueSampler,
    ) -> Dict[str, Dict[Optional[str], Any]]:
        """Compute metric values for one sample tick.

        Args:
            stressor: Domain-specific stressor (CpuStressor, MemoryStressor, etc.)
                      May be None if no stressor defined for this phase.
            hardware: Resolved hardware profile.
            interval: Sample interval in seconds.
            sampler: ValueSampler for noise + counter accumulation.

        Returns:
            {metric_name: {instance_name_or_None: value}}
            For aggregate (non-instanced) metrics, use None as the key.
        """
        ...

    @abstractmethod
    def metric_descriptors(
        self,
        hardware: HardwareProfile,
    ) -> List[MetricDescriptor]:
        """Return metric definitions for archive header registration.

        Args:
            hardware: Resolved hardware profile (determines indom sizes).

        Returns:
            List of MetricDescriptor objects for this domain's metrics.
        """
        ...
