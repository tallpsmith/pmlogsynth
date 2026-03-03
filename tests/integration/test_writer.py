"""Tier 2 integration tests for writer.py — PCP layer mocked."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pmlogsynth.profile import (
    DiskDevice,
    HardwareProfile,
    NetworkInterface,
    WorkloadProfile,
)
from pmlogsynth.sampler import ValueSampler
from pmlogsynth.timeline import TimelineSequencer


def _make_hardware() -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=4096000,
        disks=[DiskDevice(name="sda")],
        interfaces=[NetworkInterface(name="eth0")],
    )


def _make_profile(hardware: HardwareProfile, tmp_path: Path) -> WorkloadProfile:
    """Create a minimal WorkloadProfile without filesystem hardware lookup."""
    # Write a test hardware profile to tmp_path so ProfileResolver can find it
    hw_yaml = tmp_path / "test.yaml"
    hw_yaml.write_text(
        "name: test\ncpus: 2\nmemory_kb: 4096000\n"
        "disks:\n  - name: sda\ninterfaces:\n  - name: eth0\n"
    )
    yaml_text = """
meta:
  hostname: test-host
  timezone: UTC
  duration: 120
  interval: 60
  noise: 0.0
host:
  profile: test
phases:
  - name: baseline
    duration: 120
    cpu:
      utilization: 0.20
"""
    profile = WorkloadProfile.from_string(yaml_text, config_dir=tmp_path)
    return profile


@pytest.mark.integration
def test_writer_registers_metrics(tmp_path: Path) -> None:
    """ArchiveWriter calls pmiAddMetric for at least one metric from each domain."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    output = str(tmp_path / "out")

    mock_log = MagicMock()
    with patch("pmlogsynth.writer.pmi") as mock_pmi, \
         patch("pmlogsynth.writer.PM_INDOM_NULL", 0xFFFFFFFF):
        mock_pmi.pmiLogImport.return_value = mock_log
        mock_log.pmiID.side_effect = lambda d, c, i: (d, c, i)
        mock_log.pmiInDom.side_effect = lambda d, s: (d, s)
        mock_log.pmiUnits.side_effect = lambda *a: a

        from pmlogsynth.writer import ArchiveWriter

        writer = ArchiveWriter(output_path=output, profile=profile, hardware=hardware)
        writer.write(timeline=timeline, sampler=sampler)

    # Should have registered at least these metric names
    add_metric_calls = [str(c.args[0]) for c in mock_log.pmiAddMetric.call_args_list]
    assert any("kernel.all.cpu" in m for m in add_metric_calls), (
        f"No CPU metric registered. Got: {add_metric_calls}"
    )
    assert any("mem." in m for m in add_metric_calls)
    assert any("disk." in m for m in add_metric_calls)
    assert any("network." in m for m in add_metric_calls)
    assert any("kernel.all.load" in m for m in add_metric_calls)


@pytest.mark.integration
def test_writer_registers_instances(tmp_path: Path) -> None:
    """ArchiveWriter calls pmiAddInstance for CPU, disk, and NIC instances."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    output = str(tmp_path / "out")

    mock_log = MagicMock()
    with patch("pmlogsynth.writer.pmi") as mock_pmi, \
         patch("pmlogsynth.writer.PM_INDOM_NULL", 0xFFFFFFFF):
        mock_pmi.pmiLogImport.return_value = mock_log
        mock_log.pmiID.side_effect = lambda d, c, i: (d, c, i)
        mock_log.pmiInDom.side_effect = lambda d, s: (d, s)
        mock_log.pmiUnits.side_effect = lambda *a: a

        from pmlogsynth.writer import ArchiveWriter

        writer = ArchiveWriter(output_path=output, profile=profile, hardware=hardware)
        writer.write(timeline=timeline, sampler=sampler)

    instance_names = [c.args[1] for c in mock_log.pmiAddInstance.call_args_list]
    assert "cpu0" in instance_names
    assert "cpu1" in instance_names
    assert "sda" in instance_names
    assert "eth0" in instance_names


@pytest.mark.integration
def test_writer_calls_pmiwrite_per_sample(tmp_path: Path) -> None:
    """pmiWrite is called once per sample in the timeline."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    expected_samples = len(timeline.samples)
    output = str(tmp_path / "out")

    mock_log = MagicMock()
    with patch("pmlogsynth.writer.pmi") as mock_pmi, \
         patch("pmlogsynth.writer.PM_INDOM_NULL", 0xFFFFFFFF):
        mock_pmi.pmiLogImport.return_value = mock_log
        mock_log.pmiID.side_effect = lambda d, c, i: (d, c, i)
        mock_log.pmiInDom.side_effect = lambda d, s: (d, s)
        mock_log.pmiUnits.side_effect = lambda *a: a

        from pmlogsynth.writer import ArchiveWriter

        writer = ArchiveWriter(output_path=output, profile=profile, hardware=hardware)
        writer.write(timeline=timeline, sampler=sampler)

    # +1 for the discrete pass (hinv.ncpu) written before the per-sample loop
    assert mock_log.pmiWrite.call_count == expected_samples + 1


@pytest.mark.integration
def test_writer_sets_hostname_and_timezone(tmp_path: Path) -> None:
    """pmiSetHostname and pmiSetTimezone are called with profile values."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    output = str(tmp_path / "out")

    mock_log = MagicMock()
    with patch("pmlogsynth.writer.pmi") as mock_pmi, \
         patch("pmlogsynth.writer.PM_INDOM_NULL", 0xFFFFFFFF):
        mock_pmi.pmiLogImport.return_value = mock_log
        mock_log.pmiID.side_effect = lambda d, c, i: (d, c, i)
        mock_log.pmiInDom.side_effect = lambda d, s: (d, s)
        mock_log.pmiUnits.side_effect = lambda *a: a

        from pmlogsynth.writer import ArchiveWriter

        writer = ArchiveWriter(output_path=output, profile=profile, hardware=hardware)
        writer.write(timeline=timeline, sampler=sampler)

    mock_log.pmiSetHostname.assert_called_once_with("test-host")
    mock_log.pmiSetTimezone.assert_called_once_with("UTC")


@pytest.mark.integration
def test_writer_conflict_detection(tmp_path: Path) -> None:
    """Writer raises error if output files already exist (FR-053)."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    output = str(tmp_path / "out")

    # Pre-create a conflicting file
    (tmp_path / "out.0").write_text("existing")

    with patch("pmlogsynth.writer.pmi"):
        from pmlogsynth.writer import ArchiveConflictError, ArchiveWriter

        writer = ArchiveWriter(output_path=output, profile=profile, hardware=hardware)
        with pytest.raises(ArchiveConflictError):
            writer.write(timeline=timeline, sampler=sampler)


@pytest.mark.integration
def test_writer_discrete_sample_written_once(tmp_path: Path) -> None:
    """hinv.ncpu (is_discrete=True) is written exactly once before the per-sample loop (T010)."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    expected_samples = len(timeline.samples)
    output = str(tmp_path / "out")

    mock_log = MagicMock()
    with patch("pmlogsynth.writer.pmi") as mock_pmi, \
         patch("pmlogsynth.writer.PM_INDOM_NULL", 0xFFFFFFFF):
        mock_pmi.pmiLogImport.return_value = mock_log
        mock_log.pmiID.side_effect = lambda d, c, i: (d, c, i)
        mock_log.pmiInDom.side_effect = lambda d, s: (d, s)
        mock_log.pmiUnits.side_effect = lambda *a: a

        from pmlogsynth.writer import ArchiveWriter

        writer = ArchiveWriter(output_path=output, profile=profile, hardware=hardware)
        writer.write(timeline=timeline, sampler=sampler)

    # pmiWrite: 1 discrete call (one interval before first sample) + expected_samples regular calls
    assert mock_log.pmiWrite.call_count == expected_samples + 1

    # hinv.ncpu must appear in pmiPutValue exactly once (discrete = one shot)
    put_value_calls = [c.args[0] for c in mock_log.pmiPutValue.call_args_list]
    assert "hinv.ncpu" in put_value_calls, "hinv.ncpu was never emitted via pmiPutValue"
    hinv_calls = [c for c in mock_log.pmiPutValue.call_args_list if c.args[0] == "hinv.ncpu"]
    assert len(hinv_calls) == 1, "hinv.ncpu emitted {} times; expected 1".format(len(hinv_calls))

    # The discrete pmiWrite must use a timestamp BEFORE the first real sample's timestamp
    first_real_ts = timeline.samples[0].timestamp_sec
    discrete_write_ts = mock_log.pmiWrite.call_args_list[0].args[0]
    assert discrete_write_ts < first_real_ts, (
        "Discrete record ts={} is not before first real sample ts={}".format(
            discrete_write_ts, first_real_ts
        )
    )
    assert discrete_write_ts > 0, "Discrete record must not be at epoch 0 (1970)"


@pytest.mark.integration
def test_writer_force_overwrites(tmp_path: Path) -> None:
    """--force flag allows overwriting existing archive files (FR-054)."""
    hardware = _make_hardware()
    profile = _make_profile(hardware, tmp_path)
    sampler = ValueSampler(noise=0.0, seed=42)
    timeline = TimelineSequencer(profile).expand()
    output = str(tmp_path / "out")

    (tmp_path / "out.0").write_text("existing")

    mock_log = MagicMock()
    with patch("pmlogsynth.writer.pmi") as mock_pmi, \
         patch("pmlogsynth.writer.PM_INDOM_NULL", 0xFFFFFFFF):
        mock_pmi.pmiLogImport.return_value = mock_log
        mock_log.pmiID.side_effect = lambda d, c, i: (d, c, i)
        mock_log.pmiInDom.side_effect = lambda d, s: (d, s)
        mock_log.pmiUnits.side_effect = lambda *a: a

        from pmlogsynth.writer import ArchiveWriter

        writer = ArchiveWriter(
            output_path=output, profile=profile, hardware=hardware, force=True
        )
        writer.write(timeline=timeline, sampler=sampler)  # should not raise
