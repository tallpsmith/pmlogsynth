"""System domain metric model — load averages and kernel scheduler metrics."""

import math
from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.pcp_constants import (
    PM_SEM_COUNTER,
    PM_SEM_INSTANT,
    PM_TYPE_FLOAT,
    PM_TYPE_U32,
    UNITS_COUNT,
    UNITS_NONE,
)
from pmlogsynth.profile import CpuStressor, HardwareProfile
from pmlogsynth.sampler import ValueSampler

_LOAD_INDOM = (60, 3)

_DEFAULT_UTILIZATION = 0.0

# Interrupt and context-switch base rates per CPU at full utilisation
_INTR_RATE = 1000    # interrupts/second per CPU
_CS_RATE = 5000      # context-switches/second per CPU


class SystemMetricModel(MetricModel):
    """Generates kernel.all.load and kernel scheduler/interrupt metrics."""

    def __init__(self) -> None:
        self._load_1 = 0.0
        self._load_5 = 0.0
        self._load_15 = 0.0

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        return [
            MetricDescriptor(
                name="kernel.all.load",
                pmid=(60, 2, 0),
                type_code=PM_TYPE_FLOAT,
                indom=_LOAD_INDOM,
                sem=PM_SEM_INSTANT,
                units=UNITS_NONE,
            ),
            MetricDescriptor(
                name="kernel.all.intr",
                pmid=(60, 0, 12),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="kernel.all.pswitch",
                pmid=(60, 0, 7),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="kernel.all.running",
                pmid=(60, 0, 15),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_INSTANT,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="kernel.all.blocked",
                pmid=(60, 0, 16),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_INSTANT,
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
        cpu = stressor if isinstance(stressor, CpuStressor) else CpuStressor()

        utilization = cpu.utilization if cpu.utilization is not None else _DEFAULT_UTILIZATION
        load_raw = utilization * hardware.cpus

        alpha_1 = math.exp(-interval / 60.0)
        alpha_5 = math.exp(-interval / 300.0)
        alpha_15 = math.exp(-interval / 900.0)

        self._load_1 = alpha_1 * self._load_1 + (1.0 - alpha_1) * load_raw
        self._load_5 = alpha_5 * self._load_5 + (1.0 - alpha_5) * load_raw
        self._load_15 = alpha_15 * self._load_15 + (1.0 - alpha_15) * load_raw

        num_cpus = hardware.cpus
        intr_delta = utilization * _INTR_RATE * num_cpus * interval
        pswitch_delta = utilization * _CS_RATE * num_cpus * interval
        running = round(utilization * num_cpus)
        blocked = round(running * 0.1)

        return {
            "kernel.all.load": {
                "1 minute": self._load_1,
                "5 minute": self._load_5,
                "15 minute": self._load_15,
            },
            "kernel.all.intr": {None: sampler.accumulate("system.intr", intr_delta)},
            "kernel.all.pswitch": {None: sampler.accumulate("system.pswitch", pswitch_delta)},
            "kernel.all.running": {None: running},
            "kernel.all.blocked": {None: blocked},
        }
