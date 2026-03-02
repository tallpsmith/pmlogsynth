"""Tier 1 tests for ProfileResolver (US3)."""

from pathlib import Path

import pytest

from pmlogsynth.profile import ProfileResolver, ValidationError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "profiles"
BUNDLED_NAMES = {
    "compute-optimized",
    "generic-large",
    "generic-medium",
    "generic-small",
    "generic-xlarge",
    "memory-optimized",
    "storage-optimized",
}


@pytest.mark.unit
def test_resolve_bundled_generic_small() -> None:
    """Resolve generic-small without -C returns a 2-CPU profile."""
    resolver = ProfileResolver()
    hw = resolver.resolve("generic-small")
    assert hw.cpus == 2
    assert hw.name == "generic-small"


@pytest.mark.unit
def test_resolve_all_bundled_profiles() -> None:
    """All 7 bundled profiles resolve without error."""
    resolver = ProfileResolver()
    for name in BUNDLED_NAMES:
        hw = resolver.resolve(name)
        assert hw.name == name
        assert hw.cpus > 0


@pytest.mark.unit
def test_resolve_nonexistent_raises_validation_error() -> None:
    """Resolving an unknown profile name raises ValidationError."""
    resolver = ProfileResolver()
    with pytest.raises(ValidationError, match="nonexistent"):
        resolver.resolve("nonexistent")


@pytest.mark.unit
def test_list_all_no_config_dir_has_seven_bundled() -> None:
    """list_all() without -C contains exactly 7 bundled profiles."""
    resolver = ProfileResolver()
    entries = resolver.list_all()
    bundled = [e for e in entries if e.source == "bundled"]
    bundled_names = {e.name for e in bundled}
    assert bundled_names == BUNDLED_NAMES


@pytest.mark.unit
def test_list_all_with_config_dir_includes_test_profiles() -> None:
    """list_all() with -C includes test fixture profiles labelled 'config-dir'."""
    resolver = ProfileResolver(config_dir=FIXTURES)
    entries = resolver.list_all()
    config_dir_names = {e.name for e in entries if e.source == "config-dir"}
    assert "test-single-cpu" in config_dir_names
    assert "test-multi-disk" in config_dir_names


@pytest.mark.unit
def test_config_dir_overrides_bundled() -> None:
    """A config-dir profile with the same name as a bundled one takes precedence."""
    import tempfile

    # Create a temp directory with a generic-small.yaml that has cpus: 99
    with tempfile.TemporaryDirectory() as tmpdir:
        override_yaml = (
            "name: generic-small\ncpus: 99\nmemory_kb: 1024\n"
            "disks: []\ninterfaces: []\n"
        )
        (Path(tmpdir) / "generic-small.yaml").write_text(override_yaml)
        resolver = ProfileResolver(config_dir=Path(tmpdir))
        hw = resolver.resolve("generic-small")
        assert hw.cpus == 99  # config-dir takes precedence


@pytest.mark.unit
def test_list_all_source_labels() -> None:
    """All entries from list_all() have valid source labels."""
    resolver = ProfileResolver(config_dir=FIXTURES)
    entries = resolver.list_all()
    valid_sources = {"bundled", "user", "config-dir"}
    for entry in entries:
        assert entry.source in valid_sources


@pytest.mark.unit
def test_resolve_test_only_profile_from_config_dir() -> None:
    """Profiles only in -C (not bundled) can be resolved."""
    resolver = ProfileResolver(config_dir=FIXTURES)
    hw = resolver.resolve("test-single-cpu")
    assert hw.cpus == 1
    assert len(hw.disks) == 1
    assert hw.disks[0].name == "sda"


@pytest.mark.unit
def test_resolve_test_multi_disk_profile() -> None:
    """test-multi-disk profile has 4 disk devices."""
    resolver = ProfileResolver(config_dir=FIXTURES)
    hw = resolver.resolve("test-multi-disk")
    assert hw.cpus == 2
    assert len(hw.disks) == 4
    disk_names = [d.name for d in hw.disks]
    assert "sda" in disk_names
    assert "sdd" in disk_names
