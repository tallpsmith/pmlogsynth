"""Tier 1 unit tests for MetadataMetricModel — no PCP imports."""

from pmlogsynth.domains.metadata import MetadataMetricModel
from pmlogsynth.pcp_constants import (
    PM_SEM_DISCRETE,
    PM_TYPE_STRING,
    PM_TYPE_U32,
    PM_TYPE_U64,
    UNITS_NONE,
)
from pmlogsynth.profile import (
    DiskDevice,
    HardwareProfile,
    NetworkInterface,
    OsProfile,
)
from pmlogsynth.sampler import ValueSampler


def _make_hw() -> HardwareProfile:
    return HardwareProfile(
        name="test",
        cpus=4,
        memory_kb=16777216,
        disks=[DiskDevice(name="sda"), DiskDevice(name="sdb")],
        interfaces=[NetworkInterface(name="eth0"), NetworkInterface(name="eth1")],
        os_profile=OsProfile(
            sysname="Linux",
            nodename="test-server",
            release="6.1.0-generic",
            version="#2 SMP",
            machine="aarch64",
            distro="Debian 12",
            pagesize=65536,
        ),
    )


def _make_sampler() -> ValueSampler:
    return ValueSampler(noise=0.0, seed=42)


def test_descriptor_count() -> None:
    model = MetadataMetricModel()
    assert len(model.metric_descriptors(_make_hw())) == 10


def test_all_descriptors_are_discrete() -> None:
    model = MetadataMetricModel()
    for desc in model.metric_descriptors(_make_hw()):
        assert desc.is_discrete, f"{desc.name} must be is_discrete=True"


def test_all_descriptors_sem_discrete() -> None:
    model = MetadataMetricModel()
    for desc in model.metric_descriptors(_make_hw()):
        assert desc.sem == PM_SEM_DISCRETE, f"{desc.name} must be PM_SEM_DISCRETE"


def test_string_metrics_type_code() -> None:
    model = MetadataMetricModel()
    string_names = {
        "kernel.uname.sysname", "kernel.uname.nodename", "kernel.uname.release",
        "kernel.uname.version", "kernel.uname.machine", "kernel.uname.distro",
    }
    descs = {d.name: d for d in model.metric_descriptors(_make_hw())}
    for name in string_names:
        assert name in descs, f"Missing descriptor for {name}"
        assert descs[name].type_code == PM_TYPE_STRING, f"{name} must be PM_TYPE_STRING"


def test_integer_metrics_type_codes() -> None:
    model = MetadataMetricModel()
    descs = {d.name: d for d in model.metric_descriptors(_make_hw())}
    assert descs["hinv.ndisk"].type_code == PM_TYPE_U32
    assert descs["hinv.physmem"].type_code == PM_TYPE_U64
    assert descs["hinv.pagesize"].type_code == PM_TYPE_U32
    assert descs["hinv.ninterface"].type_code == PM_TYPE_U32


def test_all_descriptors_no_indom() -> None:
    model = MetadataMetricModel()
    for desc in model.metric_descriptors(_make_hw()):
        assert desc.indom is None, f"{desc.name} must have indom=None"


def test_no_duplicate_pmids() -> None:
    model = MetadataMetricModel()
    pmids = [d.pmid for d in model.metric_descriptors(_make_hw())]
    assert len(pmids) == len(set(pmids)), "Duplicate PMIDs found"


def test_metric_names() -> None:
    model = MetadataMetricModel()
    names = {d.name for d in model.metric_descriptors(_make_hw())}
    expected = {
        "kernel.uname.sysname", "kernel.uname.nodename", "kernel.uname.release",
        "kernel.uname.version", "kernel.uname.machine", "kernel.uname.distro",
        "hinv.ndisk", "hinv.physmem", "hinv.pagesize", "hinv.ninterface",
    }
    assert names == expected


def test_compute_string_values() -> None:
    model = MetadataMetricModel()
    values = model.compute(None, _make_hw(), 60, _make_sampler())
    assert values["kernel.uname.sysname"][None] == "Linux"
    assert values["kernel.uname.nodename"][None] == "test-server"
    assert values["kernel.uname.release"][None] == "6.1.0-generic"
    assert values["kernel.uname.version"][None] == "#2 SMP"
    assert values["kernel.uname.machine"][None] == "aarch64"
    assert values["kernel.uname.distro"][None] == "Debian 12"


def test_compute_integer_values() -> None:
    model = MetadataMetricModel()
    values = model.compute(None, _make_hw(), 60, _make_sampler())
    assert values["hinv.ndisk"][None] == 2
    assert values["hinv.physmem"][None] == 16777216 // 1024
    assert values["hinv.pagesize"][None] == 65536
    assert values["hinv.ninterface"][None] == 2


def test_compute_nodename_fallback() -> None:
    model = MetadataMetricModel()
    hw = HardwareProfile(name="test", cpus=2, memory_kb=8388608, os_profile=OsProfile())
    values = model.compute(None, hw, 60, _make_sampler())
    assert values["kernel.uname.nodename"][None] == "synthetic-host"


def test_compute_no_disks_no_interfaces() -> None:
    model = MetadataMetricModel()
    hw = HardwareProfile(name="bare", cpus=1, memory_kb=4194304, disks=[], interfaces=[])
    values = model.compute(None, hw, 60, _make_sampler())
    assert values["hinv.ndisk"][None] == 0
    assert values["hinv.ninterface"][None] == 0


def test_compute_returns_all_10_metrics() -> None:
    model = MetadataMetricModel()
    values = model.compute(None, _make_hw(), 60, _make_sampler())
    assert len(values) == 10
