"""Tier 1 unit tests for OsProfile dataclass, YAML parsing, and override wiring."""

import textwrap
from pathlib import Path

import pytest

from pmlogsynth.profile import (
    DiskDevice,
    HardwareProfile,
    NetworkInterface,
    OsProfile,
    ValidationError,
    _apply_overrides,
    _load_hardware_profile,
)


# ---------------------------------------------------------------------------
# Task 2: OsProfile dataclass defaults and construction
# ---------------------------------------------------------------------------


def test_os_profile_all_defaults() -> None:
    os = OsProfile()
    assert os.sysname == "Linux"
    assert os.release == "5.15.0-91-generic"
    assert os.version == "#1 SMP PREEMPT_DYNAMIC"
    assert os.machine == "x86_64"
    assert os.distro == "Ubuntu 22.04.3 LTS"
    assert os.pagesize == 4096
    assert os.nodename is None


def test_os_profile_custom_fields() -> None:
    os = OsProfile(
        sysname="Linux",
        nodename="prod-web-03",
        release="6.1.0-generic",
        version="#2 SMP",
        machine="aarch64",
        distro="Red Hat Enterprise Linux 9.2",
        pagesize=65536,
    )
    assert os.nodename == "prod-web-03"
    assert os.machine == "aarch64"
    assert os.pagesize == 65536


def test_os_profile_partial_override() -> None:
    os = OsProfile(nodename="myhost", distro="Debian 12")
    assert os.sysname == "Linux"
    assert os.nodename == "myhost"
    assert os.distro == "Debian 12"
    assert os.pagesize == 4096


def test_hardware_profile_has_os_profile_field() -> None:
    hw = HardwareProfile(name="test", cpus=4, memory_kb=16777216)
    assert hasattr(hw, "os_profile")
    assert isinstance(hw.os_profile, OsProfile)


def test_hardware_profile_os_profile_defaults() -> None:
    hw = HardwareProfile(name="test", cpus=4, memory_kb=16777216)
    assert hw.os_profile.sysname == "Linux"
    assert hw.os_profile.nodename is None


def test_hardware_profile_custom_os_profile() -> None:
    os = OsProfile(nodename="custom-host", machine="aarch64")
    hw = HardwareProfile(name="test", cpus=4, memory_kb=16777216, os_profile=os)
    assert hw.os_profile.nodename == "custom-host"
    assert hw.os_profile.machine == "aarch64"


# ---------------------------------------------------------------------------
# Task 3: Parse os: section from hardware profile YAML
# ---------------------------------------------------------------------------


def test_load_hardware_profile_with_os_section(tmp_path: Path) -> None:
    hw_yaml = tmp_path / "test.yaml"
    hw_yaml.write_text(textwrap.dedent("""\
        name: test-os
        cpus: 4
        memory_kb: 16777216
        os:
          sysname: Linux
          nodename: test-server
          release: "6.1.0-generic"
          machine: aarch64
          distro: "Debian 12"
          pagesize: 65536
        disks:
          - name: sda
        interfaces:
          - name: eth0
    """))
    hw = _load_hardware_profile(hw_yaml)
    assert hw.os_profile.sysname == "Linux"
    assert hw.os_profile.nodename == "test-server"
    assert hw.os_profile.release == "6.1.0-generic"
    assert hw.os_profile.machine == "aarch64"
    assert hw.os_profile.distro == "Debian 12"
    assert hw.os_profile.pagesize == 65536


def test_load_hardware_profile_without_os_section(tmp_path: Path) -> None:
    hw_yaml = tmp_path / "test.yaml"
    hw_yaml.write_text(textwrap.dedent("""\
        name: test-no-os
        cpus: 2
        memory_kb: 8388608
        disks:
          - name: nvme0n1
    """))
    hw = _load_hardware_profile(hw_yaml)
    assert hw.os_profile.sysname == "Linux"
    assert hw.os_profile.nodename is None
    assert hw.os_profile.pagesize == 4096


def test_load_hardware_profile_partial_os(tmp_path: Path) -> None:
    hw_yaml = tmp_path / "test.yaml"
    hw_yaml.write_text(textwrap.dedent("""\
        name: test-partial
        cpus: 2
        memory_kb: 8388608
        os:
          nodename: custom-host
        disks:
          - name: sda
    """))
    hw = _load_hardware_profile(hw_yaml)
    assert hw.os_profile.nodename == "custom-host"
    assert hw.os_profile.sysname == "Linux"
    assert hw.os_profile.pagesize == 4096


def test_load_hardware_profile_os_not_a_mapping(tmp_path: Path) -> None:
    hw_yaml = tmp_path / "bad.yaml"
    hw_yaml.write_text(textwrap.dedent("""\
        name: bad-os
        cpus: 2
        memory_kb: 8388608
        os: "not-a-dict"
    """))
    with pytest.raises(ValidationError, match="'os' must be a mapping"):
        _load_hardware_profile(hw_yaml)


# ---------------------------------------------------------------------------
# Task 4: Wire os: overrides into _apply_overrides
# ---------------------------------------------------------------------------


def test_apply_overrides_os_partial() -> None:
    base = HardwareProfile(
        name="base", cpus=4, memory_kb=16777216,
        os_profile=OsProfile(nodename="base-host", distro="Ubuntu 22.04.3 LTS"),
    )
    overrides = {"os": {"nodename": "override-host", "distro": "Red Hat Enterprise Linux 9.2"}}
    result = _apply_overrides(base, overrides)
    assert result.os_profile.nodename == "override-host"
    assert result.os_profile.distro == "Red Hat Enterprise Linux 9.2"
    assert result.os_profile.sysname == "Linux"
    assert result.os_profile.pagesize == 4096


def test_apply_overrides_no_os_keeps_base() -> None:
    base = HardwareProfile(
        name="base", cpus=4, memory_kb=16777216,
        os_profile=OsProfile(nodename="base-host"),
    )
    overrides = {"cpus": 8}
    result = _apply_overrides(base, overrides)
    assert result.os_profile.nodename == "base-host"
    assert result.cpus == 8


def test_apply_overrides_os_full_replacement() -> None:
    base = HardwareProfile(
        name="base", cpus=4, memory_kb=16777216,
        os_profile=OsProfile(nodename="base-host", machine="x86_64"),
    )
    overrides = {
        "os": {
            "nodename": "new-host",
            "machine": "aarch64",
            "distro": "Fedora 39",
            "pagesize": 65536,
        }
    }
    result = _apply_overrides(base, overrides)
    assert result.os_profile.nodename == "new-host"
    assert result.os_profile.machine == "aarch64"
    assert result.os_profile.distro == "Fedora 39"
    assert result.os_profile.pagesize == 65536
    # Fields not in override keep base values
    assert result.os_profile.sysname == "Linux"
