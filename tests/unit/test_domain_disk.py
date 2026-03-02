"""Tier 1 unit tests for DiskMetricModel (T020)."""

from unittest.mock import patch

from pmlogsynth.domains.disk import DiskMetricModel
from pmlogsynth.profile import DiskDevice, DiskStressor, HardwareProfile
from pmlogsynth.sampler import ValueSampler


def _make_hw(disks=None):
    """Build a test HardwareProfile with optional disk list."""
    if disks is None:
        disks = [DiskDevice(name="sda"), DiskDevice(name="sdb")]
    return HardwareProfile(
        name="test",
        cpus=2,
        memory_kb=8388608,
        disks=disks,
        interfaces=[],
    )


def _make_sampler(seed=0):
    return ValueSampler(noise=0.0, seed=seed)


class TestMetricDescriptors:
    def test_returns_six_descriptors(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        descriptors = model.metric_descriptors(hw)
        assert len(descriptors) == 6

    def test_descriptor_names(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        names = [d.name for d in model.metric_descriptors(hw)]
        assert "disk.all.read" in names
        assert "disk.all.write" in names
        assert "disk.all.read_bytes" in names
        assert "disk.all.write_bytes" in names
        assert "disk.dev.read_bytes" in names
        assert "disk.dev.write_bytes" in names

    def test_aggregate_metrics_have_no_indom(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        for d in model.metric_descriptors(hw):
            if d.name.startswith("disk.all."):
                assert d.indom is None

    def test_per_device_metrics_have_indom(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        for d in model.metric_descriptors(hw):
            if d.name.startswith("disk.dev."):
                assert d.indom == (60, 1)

    def test_pmids_are_correct(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        by_name = {d.name: d for d in model.metric_descriptors(hw)}
        assert by_name["disk.all.read"].pmid == (60, 4, 0)
        assert by_name["disk.all.write"].pmid == (60, 4, 1)
        assert by_name["disk.all.read_bytes"].pmid == (60, 4, 5)
        assert by_name["disk.all.write_bytes"].pmid == (60, 4, 6)
        assert by_name["disk.dev.read_bytes"].pmid == (60, 5, 5)
        assert by_name["disk.dev.write_bytes"].pmid == (60, 5, 6)


class TestPerDeviceInstances:
    def test_instance_names_match_disk_device_names(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw(disks=[DiskDevice(name="sda"), DiskDevice(name="sdb")])
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=100.0, write_mbps=50.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert set(result["disk.dev.read_bytes"].keys()) == {"sda", "sdb"}
        assert set(result["disk.dev.write_bytes"].keys()) == {"sda", "sdb"}

    def test_per_device_keys_match_hardware_profile(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw(disks=[DiskDevice(name="nvme0n1"), DiskDevice(name="nvme1n1")])
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=200.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert "nvme0n1" in result["disk.dev.read_bytes"]
        assert "nvme1n1" in result["disk.dev.read_bytes"]

    def test_three_disks_all_represented(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw(
            disks=[DiskDevice(name="sda"), DiskDevice(name="sdb"), DiskDevice(name="sdc")]
        )
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=300.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert set(result["disk.dev.read_bytes"].keys()) == {"sda", "sdb", "sdc"}


class TestCounterAccumulation:
    def test_counter_increases_on_second_call(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=100.0, write_mbps=50.0)
        result1 = model.compute(stressor, hw, interval=60, sampler=sampler)
        result2 = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result2["disk.all.read_bytes"][None] > result1["disk.all.read_bytes"][None]
        assert result2["disk.all.write_bytes"][None] > result1["disk.all.write_bytes"][None]

    def test_read_counter_accumulates(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=10.0)
        first = model.compute(stressor, hw, interval=60, sampler=sampler)
        second = model.compute(stressor, hw, interval=60, sampler=sampler)
        third = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert third["disk.all.read_bytes"][None] > second["disk.all.read_bytes"][None]
        assert second["disk.all.read_bytes"][None] > first["disk.all.read_bytes"][None]

    def test_iops_counter_accumulates(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=100.0, write_mbps=100.0)
        result1 = model.compute(stressor, hw, interval=60, sampler=sampler)
        result2 = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result2["disk.all.read"][None] > result1["disk.all.read"][None]
        assert result2["disk.all.write"][None] > result1["disk.all.write"][None]


class TestZeroIO:
    def test_zero_read_write_produces_zero_deltas(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=0.0, write_mbps=0.0)
        result1 = model.compute(stressor, hw, interval=60, sampler=sampler)
        result2 = model.compute(stressor, hw, interval=60, sampler=sampler)
        # Counter should not increase when there is zero I/O
        assert result1["disk.all.read_bytes"][None] == 0
        assert result2["disk.all.read_bytes"][None] == 0
        assert result1["disk.all.write_bytes"][None] == 0
        assert result2["disk.all.write_bytes"][None] == 0

    def test_zero_io_iops_also_zero(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=0.0, write_mbps=0.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result["disk.all.read"][None] == 0
        assert result["disk.all.write"][None] == 0


class TestNoStressor:
    def test_none_stressor_defaults_to_zero_io(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        result = model.compute(None, hw, interval=60, sampler=sampler)
        assert result["disk.all.read_bytes"][None] == 0
        assert result["disk.all.write_bytes"][None] == 0
        assert result["disk.all.read"][None] == 0
        assert result["disk.all.write"][None] == 0

    def test_none_stressor_per_device_also_zero(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        result = model.compute(None, hw, interval=60, sampler=sampler)
        for val in result["disk.dev.read_bytes"].values():
            assert val == 0
        for val in result["disk.dev.write_bytes"].values():
            assert val == 0

    def test_default_stressor_same_as_none(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler1 = _make_sampler(seed=1)
        sampler2 = _make_sampler(seed=1)
        result_none = model.compute(None, hw, interval=60, sampler=sampler1)
        result_default = model.compute(DiskStressor(), hw, interval=60, sampler=sampler2)
        assert (
            result_none["disk.all.read_bytes"][None]
            == result_default["disk.all.read_bytes"][None]
        )
        assert (
            result_none["disk.all.write_bytes"][None]
            == result_default["disk.all.write_bytes"][None]
        )


class TestDevReadBytesKeys:
    def test_dev_read_bytes_keys_match_disk_names(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw(disks=[DiskDevice(name="sda"), DiskDevice(name="sdb")])
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=50.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        expected_keys = {"sda", "sdb"}
        assert set(result["disk.dev.read_bytes"].keys()) == expected_keys

    def test_dev_write_bytes_keys_match_disk_names(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw(disks=[DiskDevice(name="sda"), DiskDevice(name="sdb")])
        sampler = _make_sampler()
        stressor = DiskStressor(write_mbps=50.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        expected_keys = {"sda", "sdb"}
        assert set(result["disk.dev.write_bytes"].keys()) == expected_keys

    def test_no_disks_produces_empty_per_device_dicts(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw(disks=[])
        sampler = _make_sampler()
        stressor = DiskStressor(read_mbps=100.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result["disk.dev.read_bytes"] == {}
        assert result["disk.dev.write_bytes"] == {}


class TestIopsEstimation:
    def test_iops_derived_from_read_mbps_when_not_specified(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        # 64 MB/s read, 60s interval, 64KB block size
        # read_bytes = 64 * 1024 * 1024 * 60 = 4_026_531_840
        # iops_read = 4_026_531_840 / (64 * 1024) = 61_440
        stressor = DiskStressor(read_mbps=64.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result["disk.all.read"][None] == 61440

    def test_explicit_iops_overrides_estimation(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        # iops_read=500 * 60s = 30000
        stressor = DiskStressor(read_mbps=100.0, iops_read=500)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result["disk.all.read"][None] == 30000

    def test_explicit_iops_write_overrides_estimation(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        # iops_write=200 * 60s = 12000
        stressor = DiskStressor(write_mbps=50.0, iops_write=200)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result["disk.all.write"][None] == 12000

    def test_iops_write_derived_from_write_mbps(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = _make_sampler()
        # 64 MB/s write, 60s interval, 64KB block size
        # write_bytes = 64 * 1024 * 1024 * 60 = 4_026_531_840
        # iops_write = 4_026_531_840 / (64 * 1024) = 61_440
        stressor = DiskStressor(write_mbps=64.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        assert result["disk.all.write"][None] == 61440


class TestNoiseClamping:
    def test_noise_applied_but_negative_deltas_never_accumulate(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = ValueSampler(noise=0.5, seed=42)
        stressor = DiskStressor(read_mbps=100.0, noise=0.5)
        # Run many ticks — counters should never decrease
        prev_read = 0
        for _ in range(20):
            result = model.compute(stressor, hw, interval=60, sampler=sampler)
            current = result["disk.all.read_bytes"][None]
            assert current >= prev_read, (
                "Counter decreased from {} to {}".format(prev_read, current)
            )
            prev_read = current

    def test_zero_value_with_noise_stays_zero_or_positive(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        # Force gauss to return a very negative value — clamping must protect us
        sampler = ValueSampler(noise=10.0, seed=1)
        stressor = DiskStressor(read_mbps=0.0, noise=10.0)
        result = model.compute(stressor, hw, interval=60, sampler=sampler)
        # Zero * anything = zero, so still zero
        assert result["disk.all.read_bytes"][None] == 0

    def test_large_noise_never_produces_negative_counter_increment(self) -> None:
        model = DiskMetricModel()
        hw = _make_hw()
        sampler = ValueSampler(noise=0.0, seed=0)
        stressor = DiskStressor(read_mbps=10.0, noise=0.5)
        # Patch gauss to return a value that would make the noisy result negative
        with patch.object(sampler._rng, "gauss", return_value=-5.0):
            result = model.compute(stressor, hw, interval=60, sampler=sampler)
        # With gauss returning -5.0, read_mbps * -5.0 = negative → clamped to 0
        assert result["disk.all.read_bytes"][None] == 0
