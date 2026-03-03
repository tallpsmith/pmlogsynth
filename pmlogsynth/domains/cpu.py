"""CPU domain metric model."""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
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

# CPU indom serial
_CPU_INDOM_SERIAL = 0

# Stressor defaults (applied at compute time, NOT at parse time — FR-020)
_DEFAULT_UTILIZATION = 0.0
_DEFAULT_USER_RATIO = 0.70
_DEFAULT_SYS_RATIO = 0.20
_DEFAULT_IOWAIT_RATIO = 0.10
_DEFAULT_STEAL_RATIO = 0.0

# Sub-metric carve fractions (proportion of parent bucket — Decision 3)
_NICE_FRAC = 0.02
_VUSER_FRAC = 0.015
_VNICE_FRAC = 0.005
_GUEST_FRAC = 0.01
_GUEST_NICE_FRAC = 0.005
_INTR_FRAC = 0.03  # carved from sys


class CpuMetricModel(MetricModel):
    """Generates kernel.all.cpu.*, kernel.percpu.cpu.*, and hinv.ncpu metrics."""

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        cpu_indom = (60, _CPU_INDOM_SERIAL)
        descriptors = [
            # Aggregate metrics
            MetricDescriptor(
                name="kernel.all.cpu.user",
                pmid=(60, 0, 20),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.all.cpu.sys",
                pmid=(60, 0, 22),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.all.cpu.idle",
                pmid=(60, 0, 21),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.all.cpu.wait.total",
                pmid=(60, 0, 35),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.all.cpu.steal",
                pmid=(60, 0, 58),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            # Sub-metric carves from user bucket
            MetricDescriptor(
                name="kernel.all.cpu.nice",
                pmid=(60, 0, 27),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.all.cpu.vuser",
                pmid=(60, 0, 78),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.all.cpu.vnice",
                pmid=(60, 0, 82),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.all.cpu.guest",
                pmid=(60, 0, 60),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.all.cpu.guest_nice",
                pmid=(60, 0, 81),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            # Sub-metric carved from sys bucket
            MetricDescriptor(
                name="kernel.all.cpu.intr",
                pmid=(60, 0, 34),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            # Discrete hardware invariant — emitted once at archive open
            MetricDescriptor(
                name="hinv.ncpu",
                pmid=(60, 0, 32),
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            # Per-CPU metrics
            MetricDescriptor(
                name="kernel.percpu.cpu.user",
                pmid=(60, 10, 20),
                type_code=PM_TYPE_U64,
                indom=cpu_indom,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.percpu.cpu.sys",
                pmid=(60, 10, 22),
                type_code=PM_TYPE_U64,
                indom=cpu_indom,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="kernel.percpu.cpu.idle",
                pmid=(60, 10, 21),
                type_code=PM_TYPE_U64,
                indom=cpu_indom,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
        ]
        return descriptors

    def compute(
        self,
        stressor: Any,
        hardware: HardwareProfile,
        interval: int,
        sampler: ValueSampler,
    ) -> Dict[str, Dict[Optional[str], Any]]:
        cpu = stressor if isinstance(stressor, CpuStressor) else CpuStressor()

        # Apply defaults at compute time (FR-020)
        utilization = cpu.utilization if cpu.utilization is not None else _DEFAULT_UTILIZATION
        user_ratio = cpu.user_ratio if cpu.user_ratio is not None else _DEFAULT_USER_RATIO
        sys_ratio = cpu.sys_ratio if cpu.sys_ratio is not None else _DEFAULT_SYS_RATIO
        iowait_ratio = cpu.iowait_ratio if cpu.iowait_ratio is not None else _DEFAULT_IOWAIT_RATIO
        noise = cpu.noise  # None means use sampler.noise

        # Apply noise to utilization
        noisy_util = sampler.apply_noise(utilization, noise)
        noisy_util = max(0.0, min(1.0, noisy_util))

        num_cpus = hardware.cpus
        # All CPU ticks across all CPUs in this interval (in milliseconds)
        all_ticks_ms = num_cpus * interval * 1000
        # Busy ticks scaled by utilization
        busy_ticks_ms = noisy_util * all_ticks_ms

        # Compute parent buckets before carving
        user_ms = busy_ticks_ms * user_ratio
        sys_ms = busy_ticks_ms * sys_ratio
        iowait_ms = busy_ticks_ms * iowait_ratio
        steal_ms = 0.0

        # Carve sub-metrics from user bucket (Decision 3)
        nice_ms = user_ms * _NICE_FRAC
        vuser_ms = user_ms * _VUSER_FRAC
        vnice_ms = user_ms * _VNICE_FRAC
        guest_ms = user_ms * _GUEST_FRAC
        guest_nice_ms = user_ms * _GUEST_NICE_FRAC
        user_carved = nice_ms + vuser_ms + vnice_ms + guest_ms + guest_nice_ms

        # Carve intr from sys bucket
        intr_ms = sys_ms * _INTR_FRAC

        # Reduce parent buckets by carved amounts — preserves total budget
        user_emitted_ms = user_ms - user_carved
        sys_emitted_ms = sys_ms - intr_ms

        # Idle is the remaining time from ALL ticks, not just busy ticks.
        idle_ms = max(
            0.0,
            all_ticks_ms - user_emitted_ms - sys_emitted_ms - iowait_ms - steal_ms
            - nice_ms - vuser_ms - vnice_ms - guest_ms - guest_nice_ms - intr_ms,
        )

        # Accumulate aggregate counters
        result: Dict[str, Dict[Optional[str], Any]] = {
            "kernel.all.cpu.user": {None: sampler.accumulate("all.cpu.user", user_emitted_ms)},
            "kernel.all.cpu.sys": {None: sampler.accumulate("all.cpu.sys", sys_emitted_ms)},
            "kernel.all.cpu.idle": {None: sampler.accumulate("all.cpu.idle", idle_ms)},
            "kernel.all.cpu.wait.total": {None: sampler.accumulate("all.cpu.wait", iowait_ms)},
            "kernel.all.cpu.steal": {None: sampler.accumulate("all.cpu.steal", steal_ms)},
            "kernel.all.cpu.nice": {None: sampler.accumulate("all.cpu.nice", nice_ms)},
            "kernel.all.cpu.vuser": {None: sampler.accumulate("all.cpu.vuser", vuser_ms)},
            "kernel.all.cpu.vnice": {None: sampler.accumulate("all.cpu.vnice", vnice_ms)},
            "kernel.all.cpu.intr": {None: sampler.accumulate("all.cpu.intr", intr_ms)},
            "kernel.all.cpu.guest": {None: sampler.accumulate("all.cpu.guest", guest_ms)},
            "kernel.all.cpu.guest_nice": {
                None: sampler.accumulate("all.cpu.guest_nice", guest_nice_ms)
            },
            "hinv.ncpu": {None: hardware.cpus},
        }

        # Per-CPU: distribute total ticks randomly across CPUs
        per_cpu_user: Dict[Optional[str], Any] = {}
        per_cpu_sys: Dict[Optional[str], Any] = {}
        per_cpu_idle: Dict[Optional[str], Any] = {}

        if num_cpus == 1:
            splits = [1.0]
        else:
            # Random split that sums to 1.0
            raw = [sampler._rng.random() for _ in range(num_cpus)]
            total = sum(raw)
            splits = [r / total for r in raw]

        for i, split in enumerate(splits):
            cpu_key = "cpu{}".format(i)
            cpu_user = user_emitted_ms * split
            cpu_sys = sys_emitted_ms * split
            cpu_iowait = iowait_ms * split
            cpu_steal = steal_ms * split
            cpu_idle = max(
                0.0,
                (all_ticks_ms * split) - cpu_user - cpu_sys - cpu_iowait - cpu_steal,
            )

            per_cpu_user[cpu_key] = sampler.accumulate("percpu.user.{}".format(i), cpu_user)
            per_cpu_sys[cpu_key] = sampler.accumulate("percpu.sys.{}".format(i), cpu_sys)
            per_cpu_idle[cpu_key] = sampler.accumulate("percpu.idle.{}".format(i), cpu_idle)

        result["kernel.percpu.cpu.user"] = per_cpu_user
        result["kernel.percpu.cpu.sys"] = per_cpu_sys
        result["kernel.percpu.cpu.idle"] = per_cpu_idle

        return result
