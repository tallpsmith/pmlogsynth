"""Disk domain metric model."""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.profile import DiskStressor, HardwareProfile
from pmlogsynth.sampler import ValueSampler

_PM_TYPE_U64 = 3
_PM_SEM_COUNTER = 1
_UNITS_KBYTE = (1, 0, 0, 1, 0, 0)
_UNITS_COUNT = (0, 0, 1, 0, 0, 0)
_DISK_INDOM = (60, 1)

_DEFAULT_READ_MBPS = 0.0
_DEFAULT_WRITE_MBPS = 0.0
_DEFAULT_BLOCK_KB = 64


class DiskMetricModel(MetricModel):
    """Metric model for disk I/O metrics."""

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        """Return metric definitions for disk metrics."""
        descriptors = [
            MetricDescriptor(
                name="disk.all.read",
                pmid=(60, 4, 0),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_COUNT,
            ),
            MetricDescriptor(
                name="disk.all.write",
                pmid=(60, 4, 1),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_COUNT,
            ),
            MetricDescriptor(
                name="disk.all.read_bytes",
                pmid=(60, 4, 5),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="disk.all.write_bytes",
                pmid=(60, 4, 6),
                type_code=_PM_TYPE_U64,
                indom=None,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="disk.dev.read_bytes",
                pmid=(60, 5, 5),
                type_code=_PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="disk.dev.write_bytes",
                pmid=(60, 5, 6),
                type_code=_PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=_PM_SEM_COUNTER,
                units=_UNITS_KBYTE,
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
        """Compute disk metric values for one sample tick."""
        disk = stressor if isinstance(stressor, DiskStressor) else DiskStressor()

        read_mbps = disk.read_mbps if disk.read_mbps is not None else _DEFAULT_READ_MBPS
        write_mbps = disk.write_mbps if disk.write_mbps is not None else _DEFAULT_WRITE_MBPS
        noise = disk.noise

        noisy_read = sampler.apply_noise(read_mbps, noise)
        noisy_write = sampler.apply_noise(write_mbps, noise)

        # Convert MB/s to bytes per interval
        read_bytes = noisy_read * 1024 * 1024 * interval
        write_bytes = noisy_write * 1024 * 1024 * interval

        # IOPS estimation
        block_bytes = _DEFAULT_BLOCK_KB * 1024
        if disk.iops_read is not None:
            iops_read = float(disk.iops_read) * interval
        else:
            iops_read = read_bytes / block_bytes if block_bytes > 0 else 0.0
        if disk.iops_write is not None:
            iops_write = float(disk.iops_write) * interval
        else:
            iops_write = write_bytes / block_bytes if block_bytes > 0 else 0.0

        # kbytes for PCP units (PCP convention)
        read_kb = read_bytes / 1024
        write_kb = write_bytes / 1024

        result: Dict[str, Dict[Optional[str], Any]] = {
            "disk.all.read": {None: sampler.accumulate("disk.all.read", iops_read)},
            "disk.all.write": {None: sampler.accumulate("disk.all.write", iops_write)},
            "disk.all.read_bytes": {None: sampler.accumulate("disk.all.read_bytes", read_kb)},
            "disk.all.write_bytes": {None: sampler.accumulate("disk.all.write_bytes", write_kb)},
        }

        # Per-device split evenly across disk devices
        num_disks = len(hardware.disks)
        dev_read: Dict[Optional[str], Any] = {}
        dev_write: Dict[Optional[str], Any] = {}
        if num_disks > 0:
            per_dev_read_kb = read_kb / num_disks
            per_dev_write_kb = write_kb / num_disks
            for dev in hardware.disks:
                dev_read[dev.name] = sampler.accumulate(
                    "disk.dev.read." + dev.name, per_dev_read_kb
                )
                dev_write[dev.name] = sampler.accumulate(
                    "disk.dev.write." + dev.name, per_dev_write_kb
                )
        result["disk.dev.read_bytes"] = dev_read
        result["disk.dev.write_bytes"] = dev_write

        return result
