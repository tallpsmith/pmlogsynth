"""Tier 1 tests for --list-metrics consistency (US5)."""

import io
import sys
from typing import Set

import pytest

# Expected 53 metric names (24 original + 29 new from 004-pmrep-view-support)
EXPECTED_METRICS: Set[str] = {
    # Existing metrics
    "disk.all.read",
    "disk.all.read_bytes",
    "disk.all.write",
    "disk.all.write_bytes",
    "disk.dev.read_bytes",
    "disk.dev.write_bytes",
    "kernel.all.cpu.idle",
    "kernel.all.cpu.steal",
    "kernel.all.cpu.sys",
    "kernel.all.cpu.user",
    "kernel.all.cpu.wait.total",
    "kernel.all.load",
    "kernel.percpu.cpu.idle",
    "kernel.percpu.cpu.sys",
    "kernel.percpu.cpu.user",
    "mem.physmem",
    "mem.util.bufmem",
    "mem.util.cached",
    "mem.util.free",
    "mem.util.used",
    "network.interface.in.bytes",
    "network.interface.in.packets",
    "network.interface.out.bytes",
    "network.interface.out.packets",
    # New CPU sub-metrics
    "kernel.all.cpu.nice",
    "kernel.all.cpu.vuser",
    "kernel.all.cpu.vnice",
    "kernel.all.cpu.intr",
    "kernel.all.cpu.guest",
    "kernel.all.cpu.guest_nice",
    "hinv.ncpu",
    # New system metrics
    "kernel.all.intr",
    "kernel.all.pswitch",
    "kernel.all.running",
    "kernel.all.blocked",
    # New memory metrics
    "mem.util.active",
    "mem.util.inactive",
    "mem.util.slab",
    "swap.used",
    "swap.pagesin",
    "swap.pagesout",
    "mem.vmstat.pgpgin",
    "mem.vmstat.pgpgout",
    # New disk metrics
    "disk.dev.read",
    "disk.dev.write",
    "disk.dev.read_merge",
    "disk.dev.write_merge",
    "disk.dev.blkread",
    "disk.dev.blkwrite",
    "disk.dev.read_rawactive",
    "disk.dev.write_rawactive",
    "disk.dev.avg_qlen",
    "disk.dev.avactive",
}


def _capture_list_metrics() -> list:
    """Run _cmd_list_metrics() and capture stdout lines."""
    from pmlogsynth.cli import _cmd_list_metrics  # type: ignore[attr-defined]

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        _cmd_list_metrics()
    finally:
        sys.stdout = old_stdout
    return [line for line in buf.getvalue().splitlines() if line.strip()]


@pytest.mark.unit
def test_list_metrics_contains_53_names() -> None:
    """--list-metrics output contains exactly 53 metric names."""
    lines = _capture_list_metrics()
    assert len(lines) == 53, f"Expected 53 metrics, got {len(lines)}: {lines}"


@pytest.mark.unit
def test_list_metrics_matches_schema() -> None:
    """--list-metrics output matches expected metric list exactly."""
    lines = _capture_list_metrics()
    actual = set(lines)
    assert actual == EXPECTED_METRICS, (
        "Metric mismatch.\n"
        f"Extra: {actual - EXPECTED_METRICS}\n"
        f"Missing: {EXPECTED_METRICS - actual}"
    )


@pytest.mark.unit
def test_list_metrics_is_sorted() -> None:
    """--list-metrics output is sorted lexicographically."""
    lines = _capture_list_metrics()
    assert lines == sorted(lines), f"Metrics not sorted: {lines}"


@pytest.mark.unit
def test_list_metrics_no_trailing_whitespace() -> None:
    """Each line in --list-metrics output has no trailing whitespace."""
    lines = _capture_list_metrics()
    for line in lines:
        assert line == line.rstrip(), f"Trailing whitespace in: {line!r}"


@pytest.mark.unit
def test_list_metrics_covers_all_domains() -> None:
    """At least one metric from each of the 5 domains is present."""
    lines = _capture_list_metrics()
    metric_set = set(lines)

    assert any(m.startswith("kernel.all.cpu.") for m in metric_set), "No CPU metrics"
    assert any(m.startswith("mem.") for m in metric_set), "No memory metrics"
    assert any(m.startswith("disk.") for m in metric_set), "No disk metrics"
    assert any(m.startswith("network.") for m in metric_set), "No network metrics"
    assert "kernel.all.load" in metric_set, "No load metric"


@pytest.mark.unit
def test_domain_descriptors_match_cli_metric_names() -> None:
    """Metric names from all domain MetricModel.metric_descriptors() match _ALL_METRIC_NAMES."""
    from pmlogsynth.cli import _ALL_METRIC_NAMES  # type: ignore[attr-defined]
    from pmlogsynth.domains.cpu import CpuMetricModel
    from pmlogsynth.domains.disk import DiskMetricModel
    from pmlogsynth.domains.memory import MemoryMetricModel
    from pmlogsynth.domains.network import NetworkMetricModel
    from pmlogsynth.domains.system import SystemMetricModel
    from pmlogsynth.profile import (
        DiskDevice,
        HardwareProfile,
        NetworkInterface,
    )

    hw = HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=8_388_608,
        disks=[DiskDevice(name="nvme0n1")],
        interfaces=[NetworkInterface(name="eth0")],
    )

    domain_names = set()
    for model in [
        CpuMetricModel(),
        MemoryMetricModel(),
        DiskMetricModel(),
        NetworkMetricModel(),
        SystemMetricModel(),
    ]:
        for desc in model.metric_descriptors(hw):
            domain_names.add(desc.name)

    cli_names = set(_ALL_METRIC_NAMES)
    assert domain_names == cli_names, (
        "Domain descriptors don't match CLI metric list.\n"
        f"In domains only: {domain_names - cli_names}\n"
        f"In CLI only: {cli_names - domain_names}"
    )
