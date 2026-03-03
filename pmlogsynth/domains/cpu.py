"""CPU domain metric model."""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.pcp_constants import PM_SEM_COUNTER, PM_TYPE_U64, UNITS_MSEC
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


class CpuMetricModel(MetricModel):
    """Generates kernel.all.cpu.* and kernel.percpu.cpu.* metrics."""

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

        # Compute aggregate breakdown
        user_ms = busy_ticks_ms * user_ratio
        sys_ms = busy_ticks_ms * sys_ratio
        iowait_ms = busy_ticks_ms * iowait_ratio
        steal_ms = 0.0
        # Idle is the remaining time from ALL ticks, not just busy ticks.
        # Without this, ratios are identical at every utilization level.
        idle_ms = max(0.0, all_ticks_ms - user_ms - sys_ms - iowait_ms - steal_ms)

        # Accumulate aggregate counters
        result: Dict[str, Dict[Optional[str], Any]] = {
            "kernel.all.cpu.user": {None: sampler.accumulate("all.cpu.user", user_ms)},
            "kernel.all.cpu.sys": {None: sampler.accumulate("all.cpu.sys", sys_ms)},
            "kernel.all.cpu.idle": {None: sampler.accumulate("all.cpu.idle", idle_ms)},
            "kernel.all.cpu.wait.total": {None: sampler.accumulate("all.cpu.wait", iowait_ms)},
            "kernel.all.cpu.steal": {None: sampler.accumulate("all.cpu.steal", steal_ms)},
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
            cpu_user = user_ms * split
            cpu_sys = sys_ms * split
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
