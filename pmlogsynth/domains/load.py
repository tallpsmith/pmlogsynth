"""Load average domain metric model."""

import math
from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.profile import CpuStressor, HardwareProfile
from pmlogsynth.sampler import ValueSampler

_PM_TYPE_FLOAT = 5
_PM_SEM_INSTANT = 3
_LOAD_INDOM = (60, 3)
_UNITS_NONE = (0, 0, 0, 0, 0, 0)

_DEFAULT_UTILIZATION = 0.0


class LoadMetricModel(MetricModel):
    """Generates kernel.all.load with 1/5/15-minute UNIX EMA averages."""

    def __init__(self) -> None:
        self._load_1 = 0.0
        self._load_5 = 0.0
        self._load_15 = 0.0

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        return [
            MetricDescriptor(
                name="kernel.all.load",
                pmid=(60, 2, 0),
                type_code=_PM_TYPE_FLOAT,
                indom=_LOAD_INDOM,
                sem=_PM_SEM_INSTANT,
                units=_UNITS_NONE,
            ),
        ]

    def compute(
        self,
        stressor: Any,
        hardware: HardwareProfile,
        interval: int,
        sampler: ValueSampler,
    ) -> Dict[str, Dict[Optional[str], Any]]:
        cpu = stressor if isinstance(stressor, CpuStressor) else CpuStressor()

        utilization = cpu.utilization if cpu.utilization is not None else _DEFAULT_UTILIZATION
        load_raw = utilization * hardware.cpus

        alpha_1 = math.exp(-interval / 60.0)
        alpha_5 = math.exp(-interval / 300.0)
        alpha_15 = math.exp(-interval / 900.0)

        self._load_1 = alpha_1 * self._load_1 + (1.0 - alpha_1) * load_raw
        self._load_5 = alpha_5 * self._load_5 + (1.0 - alpha_5) * load_raw
        self._load_15 = alpha_15 * self._load_15 + (1.0 - alpha_15) * load_raw

        return {
            "kernel.all.load": {
                "1 minute": self._load_1,
                "5 minute": self._load_5,
                "15 minute": self._load_15,
            },
        }
