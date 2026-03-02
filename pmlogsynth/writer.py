"""PCP archive writer — wraps pcp.pmi.pmiLogImport.

NOTE: This is the ONLY module in the pmlogsynth package that imports pcp.*
Tier 1 and Tier 2 tests must never import from this module without mocking pcp.
"""

import sys
from pathlib import Path
from typing import Any, List

from pmlogsynth.domains.base import MetricDescriptor, MetricModel
from pmlogsynth.domains.cpu import CpuMetricModel
from pmlogsynth.domains.disk import DiskMetricModel
from pmlogsynth.domains.load import LoadMetricModel
from pmlogsynth.domains.memory import MemoryMetricModel
from pmlogsynth.domains.network import NetworkMetricModel
from pmlogsynth.profile import HardwareProfile, WorkloadProfile
from pmlogsynth.sampler import ValueSampler
from pmlogsynth.timeline import ExpandedTimeline

try:
    from cpmapi import PM_INDOM_NULL
    from pcp import pmi  # noqa: F401
except ImportError:
    pmi = None
    PM_INDOM_NULL = 0xFFFFFFFF


class ArchiveConflictError(Exception):
    """Raised when output archive files already exist and --force not set."""


class ArchiveGenerationError(Exception):
    """Raised when archive generation fails mid-write."""


class ArchiveWriter:
    """Writes a PCP v3 archive from an ExpandedTimeline."""

    _SUFFIXES = (".0", ".index", ".meta")

    def __init__(
        self,
        output_path: str,
        profile: WorkloadProfile,
        hardware: HardwareProfile,
        force: bool = False,
        leave_partial: bool = False,
    ) -> None:
        self._output_path = output_path
        self._profile = profile
        self._hardware = hardware
        self._force = force
        self._leave_partial = leave_partial

        # Instantiate all five domain models
        mean_pkt = profile.meta.mean_packet_bytes
        self._models: List[MetricModel] = [
            CpuMetricModel(),
            MemoryMetricModel(),
            DiskMetricModel(),
            NetworkMetricModel(mean_packet_bytes=mean_pkt),
            LoadMetricModel(),
        ]

    def write(self, timeline: ExpandedTimeline, sampler: ValueSampler) -> None:
        """Write the archive. Raises ArchiveConflictError or ArchiveGenerationError."""
        if pmi is None:
            raise RuntimeError(
                "pcp.pmi is not available. Install python3-pcp to generate archives."
            )

        output = Path(self._output_path)

        # FR-053: pre-existence check
        if not self._force:
            conflicts = [
                str(output.parent / (output.name + suf))
                for suf in self._SUFFIXES
                if (output.parent / (output.name + suf)).exists()
            ]
            if conflicts:
                raise ArchiveConflictError(
                    f"Output archive files already exist: {conflicts}. "
                    f"Use --force to overwrite."
                )

        log: Any = pmi.pmiLogImport(self._output_path)

        try:
            log.pmiSetHostname(self._profile.meta.hostname)
            log.pmiSetTimezone(self._profile.meta.timezone)

            # Collect all metric descriptors and register
            all_descriptors: List[MetricDescriptor] = []
            for model in self._models:
                all_descriptors.extend(model.metric_descriptors(self._hardware))

            registered_indoms = set()
            for desc in all_descriptors:
                pmid = log.pmiID(*desc.pmid)
                if desc.indom is not None:
                    indom_key = desc.indom
                    if indom_key not in registered_indoms:
                        registered_indoms.add(indom_key)
                    indom_obj = log.pmiInDom(*desc.indom)
                else:
                    indom_obj = PM_INDOM_NULL
                units_obj = log.pmiUnits(*desc.units)
                log.pmiAddMetric(desc.name, pmid, desc.type_code, indom_obj, desc.sem, units_obj)

            # Register instances for instanced metrics
            self._register_instances(log)

            # Write samples
            interval = self._profile.meta.interval
            for sample in timeline.samples:
                for model in self._models:
                    if isinstance(model, (CpuMetricModel, LoadMetricModel)):
                        stressor: Any = sample.cpu
                    elif isinstance(model, MemoryMetricModel):
                        stressor = sample.memory
                    elif isinstance(model, DiskMetricModel):
                        stressor = sample.disk
                    else:
                        stressor = sample.network
                    values = model.compute(stressor, self._hardware, interval, sampler)
                    for metric_name, instances in values.items():
                        for instance, value in instances.items():
                            inst = instance if instance is not None else ""
                            log.pmiPutValue(metric_name, inst, str(value))
                log.pmiWrite(sample.timestamp_sec, 0)

        except Exception as exc:
            # FR-051: clean up partial files
            if not self._leave_partial:
                deleted = []
                for suf in self._SUFFIXES:
                    p = output.parent / (output.name + suf)
                    if p.exists():
                        try:
                            p.unlink()
                            deleted.append(str(p))
                        except OSError as del_err:
                            print(
                                f"ERROR: Failed to delete partial file {p}: {del_err}",
                                file=sys.stderr,
                            )
                if deleted:
                    print(
                        f"ERROR: Archive generation failed; deleted partial files: {deleted}",
                        file=sys.stderr,
                    )
            else:
                partial = [
                    str(output.parent / (output.name + suf))
                    for suf in self._SUFFIXES
                    if (output.parent / (output.name + suf)).exists()
                ]
                if partial:
                    print(
                        f"WARNING: --leave-partial set; partial files left: {partial}",
                        file=sys.stderr,
                    )
            raise ArchiveGenerationError(str(exc)) from exc
        finally:
            del log  # pmiEnd() + finalises .0/.index/.meta

    def _register_instances(self, log: Any) -> None:
        """Register per-CPU, per-disk, per-NIC instances."""
        hw = self._hardware

        # Per-CPU
        cpu_indom = log.pmiInDom(60, 0)
        for i in range(hw.cpus):
            log.pmiAddInstance(cpu_indom, "cpu{}".format(i), i)

        # Per-disk
        disk_indom = log.pmiInDom(60, 1)
        for idx, disk in enumerate(hw.disks):
            log.pmiAddInstance(disk_indom, disk.name, idx)

        # Per-NIC
        net_indom = log.pmiInDom(60, 2)
        for idx, iface in enumerate(hw.interfaces):
            log.pmiAddInstance(net_indom, iface.name, idx)

        # Load average instances
        load_indom = log.pmiInDom(60, 3)
        for idx, label in enumerate(["1 minute", "5 minute", "15 minute"]):
            log.pmiAddInstance(load_indom, label, idx)
