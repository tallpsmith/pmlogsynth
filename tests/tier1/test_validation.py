"""Tier 1 tests for profile validation rules (US2)."""

from pathlib import Path

import pytest

from pmlogsynth.profile import ValidationError, WorkloadProfile

# All fixture profiles that reference test-single-cpu need config_dir
FIXTURES = Path(__file__).parent.parent / "fixtures" / "profiles"


def _load(filename: str) -> WorkloadProfile:
    """Load a fixture profile with config_dir pointing to test fixtures."""
    text = (FIXTURES / filename).read_text(encoding="utf-8")
    return WorkloadProfile.from_string(text, config_dir=FIXTURES)


def _load_str(yaml_text: str, config_dir: Path = FIXTURES) -> WorkloadProfile:
    return WorkloadProfile.from_string(yaml_text, config_dir=config_dir)


@pytest.mark.tier1
def test_good_baseline_passes() -> None:
    """good-baseline.yaml should parse without error."""
    profile = _load("good-baseline.yaml")
    assert profile.meta.duration == 600
    assert len(profile.phases) == 2


@pytest.mark.tier1
def test_bad_ratio_raises_fr026() -> None:
    """CPU ratios summing > 1.0 raise ValidationError (FR-026)."""
    with pytest.raises(ValidationError, match="FR-026"):
        _load("bad-ratio.yaml")


@pytest.mark.tier1
def test_bad_duration_raises_fr027() -> None:
    """Phase duration sum != meta.duration raises ValidationError (FR-027)."""
    with pytest.raises(ValidationError, match="FR-027"):
        _load("bad-duration.yaml")


@pytest.mark.tier1
def test_bad_noise_raises_fr029() -> None:
    """meta.noise out of [0.0, 1.0] raises ValidationError (FR-029)."""
    with pytest.raises(ValidationError, match="FR-029"):
        _load("bad-noise.yaml")


@pytest.mark.tier1
def test_bad_interval_raises_fr030() -> None:
    """meta.interval = 0 raises ValidationError (FR-030)."""
    yaml_text = """
meta:
  duration: 60
  interval: 0
host:
  profile: test-single-cpu
phases:
  - name: p
    duration: 60
"""
    with pytest.raises(ValidationError, match="FR-030"):
        _load_str(yaml_text)


@pytest.mark.tier1
def test_first_phase_linear_raises_fr055() -> None:
    """First phase with transition: linear raises ValidationError (FR-055)."""
    yaml_text = """
meta:
  duration: 300
host:
  profile: test-single-cpu
phases:
  - name: ramp
    duration: 300
    transition: linear
    cpu:
      utilization: 0.80
"""
    with pytest.raises(ValidationError, match="FR-055"):
        _load_str(yaml_text)


@pytest.mark.tier1
def test_unknown_profile_raises_fr028() -> None:
    """Unknown host.profile name raises ValidationError (FR-028)."""
    yaml_text = """
meta:
  duration: 60
host:
  profile: nonexistent-profile
phases:
  - name: p
    duration: 60
"""
    with pytest.raises(ValidationError, match="nonexistent-profile"):
        _load_str(yaml_text)


@pytest.mark.tier1
def test_inline_fields_with_profile_no_overrides_raises_fr015a() -> None:
    """host.profile + inline fields without overrides: raises ValidationError (FR-015a)."""
    yaml_text = """
meta:
  duration: 60
host:
  profile: test-single-cpu
  cpus: 4
phases:
  - name: p
    duration: 60
"""
    with pytest.raises(ValidationError, match="overrides"):
        _load_str(yaml_text)


@pytest.mark.tier1
def test_repeat_daily_overflow_raises_fr031() -> None:
    """repeat:daily phase with duration > meta.duration raises ValidationError (FR-031)."""
    yaml_text = """
meta:
  duration: 3600
host:
  profile: test-single-cpu
phases:
  - name: background
    duration: 3600
  - name: noon-peak
    duration: 7200
    repeat: daily
"""
    with pytest.raises(ValidationError, match="FR-031"):
        _load_str(yaml_text)


@pytest.mark.tier1
def test_inline_host_form_valid() -> None:
    """Fully inline host spec is valid without needing -C."""
    yaml_text = """
meta:
  duration: 60
host:
  name: my-host
  cpus: 2
  memory_kb: 4096000
  disks:
    - name: sda
  interfaces:
    - name: eth0
phases:
  - name: p
    duration: 60
"""
    profile = WorkloadProfile.from_string(yaml_text, config_dir=None)
    assert profile.hardware is not None
    assert profile.hardware.cpus == 2


@pytest.mark.tier1
def test_profile_with_overrides_valid() -> None:
    """host.profile + overrides: is valid (FR-015a form 2)."""
    yaml_text = """
meta:
  duration: 60
host:
  profile: test-single-cpu
  overrides:
    cpus: 4
phases:
  - name: p
    duration: 60
"""
    profile = _load_str(yaml_text)
    assert profile.hardware is not None
    assert profile.hardware.cpus == 4


@pytest.mark.tier1
def test_from_file_delegates_to_from_string(tmp_path: Path) -> None:
    """WorkloadProfile.from_file() correctly loads a bundled-profile spec."""
    # Use a profile that only references bundled 'generic-small'
    yaml_text = """
meta:
  duration: 60
host:
  profile: generic-small
phases:
  - name: p
    duration: 60
"""
    p = tmp_path / "profile.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    profile = WorkloadProfile.from_file(p)
    assert profile.meta.duration == 60
    assert profile.hardware is not None
    assert profile.hardware.name == "generic-small"
