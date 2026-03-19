"""Metadata domain metric model — OS identity and hardware inventory.

All metrics are discrete (is_discrete=True): written once at archive
creation time, never in the per-sample loop. This matches PCP's
'log mandatory on once' pmlogger configuration group (platform/hinv).
"""

from typing import Any, Dict, List, Optional

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.pcp_constants import (
    PM_SEM_DISCRETE,
    PM_TYPE_STRING,
    PM_TYPE_U32,
    PM_TYPE_U64,
    UNITS_BYTES,
    UNITS_NONE,
)
from pmlogsynth.profile import HardwareProfile
from pmlogsynth.sampler import ValueSampler

# Units: megabytes — (dimSpace=1, dimTime=0, dimCount=0, scaleSpace=PM_SPACE_MBYTE, 0, 0)
_UNITS_MBYTE = (1, 0, 0, 2, 0, 0)


class MetadataMetricModel(MetricModel):
    """Generates kernel.uname.* and hinv.* discrete metadata metrics."""

    def metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]:
        return [
            # kernel.uname.* — domain 60, CLUSTER_KERNEL_UNAME=12, items per linux PMDA
            MetricDescriptor(
                name="kernel.uname.sysname",
                pmid=(60, 12, 2),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.nodename",
                pmid=(60, 12, 4),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.release",
                pmid=(60, 12, 0),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.version",
                pmid=(60, 12, 1),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.machine",
                pmid=(60, 12, 3),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="kernel.uname.distro",
                pmid=(60, 12, 7),
                type_code=PM_TYPE_STRING,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            # hinv.* — domain 60; clusters per linux PMDA
            MetricDescriptor(
                name="hinv.ndisk",
                pmid=(60, 0, 33),          # CLUSTER_STAT=0 — already correct
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="hinv.physmem",
                pmid=(60, 1, 9),           # CLUSTER_MEMINFO=1
                type_code=PM_TYPE_U64,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=_UNITS_MBYTE,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="hinv.pagesize",
                pmid=(60, 1, 11),          # CLUSTER_MEMINFO=1
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_BYTES,
                is_discrete=True,
            ),
            MetricDescriptor(
                name="hinv.ninterface",
                pmid=(60, 3, 27),          # CLUSTER_NET_DEV=3
                type_code=PM_TYPE_U32,
                indom=None,
                sem=PM_SEM_DISCRETE,
                units=UNITS_NONE,
                is_discrete=True,
            ),
        ]

    def compute(
        self,
        stressor: Any,
        hardware: HardwareProfile,
        interval: int,
        sampler: ValueSampler,
    ) -> Dict[str, Dict[Optional[str], Any]]:
        os = hardware.os_profile
        nodename = os.nodename if os.nodename is not None else "synthetic-host"
        return {
            "kernel.uname.sysname": {None: os.sysname},
            "kernel.uname.nodename": {None: nodename},
            "kernel.uname.release": {None: os.release},
            "kernel.uname.version": {None: os.version},
            "kernel.uname.machine": {None: os.machine},
            "kernel.uname.distro": {None: os.distro},
            "hinv.ndisk": {None: len(hardware.disks)},
            "hinv.physmem": {None: hardware.memory_kb // 1024},
            "hinv.pagesize": {None: os.pagesize},
            "hinv.ninterface": {None: len(hardware.interfaces)},
        }
