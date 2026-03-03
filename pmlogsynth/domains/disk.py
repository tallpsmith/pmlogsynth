"""Disk domain metric model."""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.pcp_constants import (
    PM_SEM_COUNTER,
    PM_SEM_INSTANT,
    PM_TYPE_DOUBLE,
    PM_TYPE_U64,
    UNITS_COUNT,
    UNITS_KBYTE,
    UNITS_MSEC,
    UNITS_NONE,
)
from pmlogsynth.profile import DiskStressor, HardwareProfile
from pmlogsynth.sampler import ValueSampler

_DISK_INDOM = (60, 1)

_DEFAULT_READ_MBPS = 0.0
_DEFAULT_WRITE_MBPS = 0.0
_DEFAULT_BLOCK_KB = 64

# Merge ratios (fraction of IOPS that are merged I/Os)
_READ_MERGE_RATIO = 0.15
_WRITE_MERGE_RATIO = 0.20


class DiskMetricModel(MetricModel):
    """Metric model for disk I/O metrics."""

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        """Return metric definitions for disk metrics."""
        descriptors = [
            # Aggregate metrics (disk.all.*)
            MetricDescriptor(
                name="disk.all.read",
                pmid=(60, 4, 0),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="disk.all.write",
                pmid=(60, 4, 1),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="disk.all.read_bytes",
                pmid=(60, 4, 5),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="disk.all.write_bytes",
                pmid=(60, 4, 6),
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_COUNTER,
                units=UNITS_KBYTE,
            ),
            # Existing per-device metrics
            MetricDescriptor(
                name="disk.dev.read_bytes",
                pmid=(60, 5, 5),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_KBYTE,
            ),
            MetricDescriptor(
                name="disk.dev.write_bytes",
                pmid=(60, 5, 6),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_KBYTE,
            ),
            # New per-device IOPS counters
            MetricDescriptor(
                name="disk.dev.read",
                pmid=(60, 5, 0),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="disk.dev.write",
                pmid=(60, 5, 1),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="disk.dev.read_merge",
                pmid=(60, 5, 2),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="disk.dev.write_merge",
                pmid=(60, 5, 3),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            # New sector counters
            MetricDescriptor(
                name="disk.dev.blkread",
                pmid=(60, 5, 7),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            MetricDescriptor(
                name="disk.dev.blkwrite",
                pmid=(60, 5, 8),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_COUNT,
            ),
            # I/O time counters (milliseconds)
            MetricDescriptor(
                name="disk.dev.read_rawactive",
                pmid=(60, 5, 9),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            MetricDescriptor(
                name="disk.dev.write_rawactive",
                pmid=(60, 5, 10),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
                sem=PM_SEM_COUNTER,
                units=UNITS_MSEC,
            ),
            # Queue length instant (double)
            MetricDescriptor(
                name="disk.dev.avg_qlen",
                pmid=(60, 5, 11),
                type_code=PM_TYPE_DOUBLE,
                indom=_DISK_INDOM,
                sem=PM_SEM_INSTANT,
                units=UNITS_NONE,
            ),
            # Active time counter
            MetricDescriptor(
                name="disk.dev.avactive",
                pmid=(60, 5, 12),
                type_code=PM_TYPE_U64,
                indom=_DISK_INDOM,
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
        dev_read_bytes: Dict[Optional[str], Any] = {}
        dev_write_bytes: Dict[Optional[str], Any] = {}
        dev_read: Dict[Optional[str], Any] = {}
        dev_write: Dict[Optional[str], Any] = {}
        dev_read_merge: Dict[Optional[str], Any] = {}
        dev_write_merge: Dict[Optional[str], Any] = {}
        dev_blkread: Dict[Optional[str], Any] = {}
        dev_blkwrite: Dict[Optional[str], Any] = {}
        dev_read_rawactive: Dict[Optional[str], Any] = {}
        dev_write_rawactive: Dict[Optional[str], Any] = {}
        dev_avg_qlen: Dict[Optional[str], Any] = {}
        dev_avactive: Dict[Optional[str], Any] = {}

        if num_disks > 0:
            per_dev_read_kb = read_kb / num_disks
            per_dev_write_kb = write_kb / num_disks
            per_dev_iops_read = iops_read / num_disks
            per_dev_iops_write = iops_write / num_disks
            per_dev_read_bytes = read_bytes / num_disks
            per_dev_write_bytes = write_bytes / num_disks

            # Sector counts: bytes / 512
            per_dev_blkread = per_dev_read_bytes / 512
            per_dev_blkwrite = per_dev_write_bytes / 512

            # I/O time in ms: approximate as bytes_transferred * 0.8 / (1MB) * 1000
            per_dev_read_raw_ms = (per_dev_read_bytes * 0.8 / (1024 * 1024)) * 1000
            per_dev_write_raw_ms = (per_dev_write_bytes * 0.8 / (1024 * 1024)) * 1000

            # Queue length: proportional to combined throughput
            avg_qlen_val = (read_mbps + write_mbps) / 100.0 / num_disks

            for dev in hardware.disks:
                n = dev.name
                dev_read_bytes[n] = sampler.accumulate(
                    "disk.dev.read_bytes." + n, per_dev_read_kb
                )
                dev_write_bytes[n] = sampler.accumulate(
                    "disk.dev.write_bytes." + n, per_dev_write_kb
                )
                dev_read[n] = sampler.accumulate(
                    "disk.dev.read." + n, per_dev_iops_read
                )
                dev_write[n] = sampler.accumulate(
                    "disk.dev.write." + n, per_dev_iops_write
                )
                dev_read_merge[n] = sampler.accumulate(
                    "disk.dev.read_merge." + n, per_dev_iops_read * _READ_MERGE_RATIO
                )
                dev_write_merge[n] = sampler.accumulate(
                    "disk.dev.write_merge." + n, per_dev_iops_write * _WRITE_MERGE_RATIO
                )
                dev_blkread[n] = sampler.accumulate(
                    "disk.dev.blkread." + n, per_dev_blkread
                )
                dev_blkwrite[n] = sampler.accumulate(
                    "disk.dev.blkwrite." + n, per_dev_blkwrite
                )
                dev_read_rawactive[n] = sampler.accumulate(
                    "disk.dev.read_rawactive." + n, per_dev_read_raw_ms
                )
                dev_write_rawactive[n] = sampler.accumulate(
                    "disk.dev.write_rawactive." + n, per_dev_write_raw_ms
                )
                dev_avg_qlen[n] = avg_qlen_val
                raw_active_ms = per_dev_read_raw_ms + per_dev_write_raw_ms
                dev_avactive[n] = sampler.accumulate(
                    "disk.dev.avactive." + n, raw_active_ms
                )

        result["disk.dev.read_bytes"] = dev_read_bytes
        result["disk.dev.write_bytes"] = dev_write_bytes
        result["disk.dev.read"] = dev_read
        result["disk.dev.write"] = dev_write
        result["disk.dev.read_merge"] = dev_read_merge
        result["disk.dev.write_merge"] = dev_write_merge
        result["disk.dev.blkread"] = dev_blkread
        result["disk.dev.blkwrite"] = dev_blkwrite
        result["disk.dev.read_rawactive"] = dev_read_rawactive
        result["disk.dev.write_rawactive"] = dev_write_rawactive
        result["disk.dev.avg_qlen"] = dev_avg_qlen
        result["disk.dev.avactive"] = dev_avactive

        return result
