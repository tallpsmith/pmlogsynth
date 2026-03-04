"""Unit tests for profile.py — ProfileLoader and ProfileResolver."""

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from pmlogsynth.profile import (
    HardwareProfile,
    ProfileResolver,
    ValidationError,
    WorkloadProfile,
    parse_duration,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_INLINE_HOST = textwrap.dedent("""\
    meta:
      duration: 120
      interval: 60
    host:
      cpus: 2
      memory_kb: 8388608
      disks:
        - name: nvme0n1
      interfaces:
        - name: eth0
    phases:
      - name: baseline
        duration: 120
        cpu:
          utilization: 0.1
""")


def make_profile_yaml(
    duration: int = 120,
    interval: int = 60,
    noise: float = 0.0,
    phases_yaml: str = "",
    host_yaml: str = "",
) -> str:
    if not host_yaml:
        host_yaml = textwrap.dedent("""\
            host:
              cpus: 2
              memory_kb: 8388608
              disks:
                - name: sda
              interfaces:
                - name: eth0
        """)
    if not phases_yaml:
        phases_yaml = textwrap.dedent(f"""\
            phases:
              - name: baseline
                duration: {duration}
                cpu:
                  utilization: 0.1
        """)
    return textwrap.dedent(f"""\
        meta:
          duration: {duration}
          interval: {interval}
          noise: {noise}
        {host_yaml}
        {phases_yaml}
    """)


# ---------------------------------------------------------------------------
# T009: parse_duration helper
# ---------------------------------------------------------------------------


class TestParseDuration:
    def test_plain_integer_seconds(self) -> None:
        assert parse_duration(3600) == 3600

    def test_seconds_suffix(self) -> None:
        assert parse_duration("90s") == 90

    def test_minutes_suffix(self) -> None:
        assert parse_duration("30m") == 1800

    def test_hours_suffix(self) -> None:
        assert parse_duration("24h") == 86400

    def test_fractional_hours_rejected(self) -> None:
        # "1.5h" has known suffix 'h' but non-int body — falls through to PCP,
        # which also rejects it (mocked here for Tier 1)
        from unittest.mock import patch
        with patch(
            "pmlogsynth.time_parsing.pcp_parse_interval",
            side_effect=ValidationError("invalid interval"),
        ):
            with pytest.raises(ValidationError, match="duration"):
                parse_duration("1.5h")

    def test_unknown_suffix_rejected(self) -> None:
        # After T010, unknown suffixes delegate to PCP; mock PCP rejecting it
        from unittest.mock import patch
        with patch(
            "pmlogsynth.time_parsing.pcp_parse_interval",
            side_effect=ValidationError("invalid interval"),
        ):
            with pytest.raises(ValidationError, match="duration"):
                parse_duration("10x")

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duration"):
            parse_duration(0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duration"):
            parse_duration(-60)

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duration"):
            parse_duration("")

    def test_non_numeric_body_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duration"):
            parse_duration("xh")


# ---------------------------------------------------------------------------
# T007: parse_duration — d suffix and compound forms (via pcp_parse_interval)
# ---------------------------------------------------------------------------


class TestParseDurationDSuffix:
    """Tests for 'd' suffix and compound forms delegated to pcp_parse_interval."""

    def test_days_suffix_no_longer_delegates_to_pcp(self) -> None:
        """'d' is now a native suffix — PCP is not required."""
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval") as mock_pcp:
            result = parse_duration("1d")
        assert result == 86400
        mock_pcp.assert_not_called()

    def test_two_days_via_pcp(self) -> None:
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=172800):
            result = parse_duration("2d")
        assert result == 172800

    def test_compound_1h30m_via_pcp(self) -> None:
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=5400):
            result = parse_duration("1h30m")
        assert result == 5400

    def test_zero_via_pcp_still_rejected(self) -> None:
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=0):
            with pytest.raises(ValidationError, match="positive"):
                parse_duration("0d")

    def test_existing_h_suffix_still_works_without_pcp(self) -> None:
        """Existing single-unit suffixes (s/m/h) with integer body skip PCP."""
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval") as mock_pcp:
            result = parse_duration("24h")
        assert result == 86400
        mock_pcp.assert_not_called()

    def test_existing_m_suffix_still_works_without_pcp(self) -> None:
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval") as mock_pcp:
            result = parse_duration("30m")
        assert result == 1800
        mock_pcp.assert_not_called()


# ---------------------------------------------------------------------------
# T007b: parse_duration — d suffix native (no PCP required)
# ---------------------------------------------------------------------------


class TestParseDurationNativeDSuffix:
    """'d' suffix must resolve natively without delegating to pcp_parse_interval."""

    def test_1d_resolves_natively_without_pcp(self) -> None:
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval") as mock_pcp:
            result = parse_duration("1d")
        assert result == 86400
        mock_pcp.assert_not_called()

    def test_2d_resolves_natively_without_pcp(self) -> None:
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval") as mock_pcp:
            result = parse_duration("2d")
        assert result == 172800
        mock_pcp.assert_not_called()

    def test_7d_resolves_natively_without_pcp(self) -> None:
        from unittest.mock import patch
        with patch("pmlogsynth.time_parsing.pcp_parse_interval") as mock_pcp:
            result = parse_duration("7d")
        assert result == 604800
        mock_pcp.assert_not_called()

    def test_0d_still_rejected(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            parse_duration("0d")


# ---------------------------------------------------------------------------
# T010: from_string — valid profile
# ---------------------------------------------------------------------------


class TestFromString:
    def test_meta_duration_defaults_to_one_full_day(self) -> None:
        """Omitting meta.duration should default to 86400s (one day)."""
        yaml = textwrap.dedent("""\
            meta:
              interval: 60
            host:
              cpus: 2
              memory_kb: 8388608
              disks:
                - name: sda
              interfaces:
                - name: eth0
            phases:
              - name: baseline
                duration: 86400
        """)
        profile = WorkloadProfile.from_string(yaml)
        assert profile.meta.duration == 86400

    def test_meta_duration_accepts_hours_string(self) -> None:
        yaml = textwrap.dedent("""\
            meta:
              duration: 24h
              interval: 60
            host:
              cpus: 2
              memory_kb: 8388608
              disks:
                - name: sda
              interfaces:
                - name: eth0
            phases:
              - name: baseline
                duration: 86400
        """)
        profile = WorkloadProfile.from_string(yaml)
        assert profile.meta.duration == 86400

    def test_phase_duration_accepts_hours_string(self) -> None:
        yaml = textwrap.dedent("""\
            meta:
              duration: 24h
              interval: 60
            host:
              cpus: 2
              memory_kb: 8388608
              disks:
                - name: sda
              interfaces:
                - name: eth0
            phases:
              - name: baseline
                duration: 12h
              - name: peak
                duration: 12h
        """)
        profile = WorkloadProfile.from_string(yaml)
        assert profile.phases[0].duration == 43200
        assert profile.phases[1].duration == 43200

    def test_minimal_valid_profile_parses(self) -> None:
        profile = WorkloadProfile.from_string(MINIMAL_INLINE_HOST)
        assert profile.meta.duration == 120
        assert profile.meta.interval == 60
        assert profile.hardware is not None
        assert profile.hardware.cpus == 2
        assert len(profile.phases) == 1
        assert profile.phases[0].name == "baseline"

    def test_stressor_fields_remain_none_after_parse(self) -> None:
        """Stressor defaults must NOT be set by parser — applied at compute time."""
        profile = WorkloadProfile.from_string(MINIMAL_INLINE_HOST)
        phase = profile.phases[0]
        # utilization was set, but user_ratio etc. stay None
        assert phase.cpu is not None
        assert phase.cpu.utilization == pytest.approx(0.1)
        assert phase.cpu.user_ratio is None
        assert phase.cpu.sys_ratio is None
        assert phase.cpu.iowait_ratio is None
        assert phase.cpu.noise is None

    def test_meta_defaults_applied(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
            host:
              cpus: 1
              memory_kb: 1048576
            phases:
              - name: p1
                duration: 60
        """)
        profile = WorkloadProfile.from_string(yaml_text)
        assert profile.meta.hostname == "synthetic-host"
        assert profile.meta.timezone == "UTC"
        assert profile.meta.interval == 60
        assert profile.meta.noise == pytest.approx(0.0)
        assert profile.meta.mean_packet_bytes == 1400

    def test_host_inline_form_no_profile(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
            host:
              cpus: 4
              memory_kb: 16777216
              disks:
                - name: sda
                  type: ssd
              interfaces:
                - name: eth0
                  speed_mbps: 1000
            phases:
              - name: p1
                duration: 60
        """)
        profile = WorkloadProfile.from_string(yaml_text)
        assert profile.hardware is not None
        assert profile.hardware.cpus == 4
        assert profile.hardware.memory_kb == 16777216
        assert len(profile.hardware.disks) == 1
        assert profile.hardware.disks[0].name == "sda"
        assert len(profile.hardware.interfaces) == 1
        assert profile.hardware.interfaces[0].name == "eth0"

    def test_host_profile_plus_overrides(self, tmp_path: Path) -> None:
        hw_yaml = tmp_path / "base-hw.yaml"
        hw_yaml.write_text(
            "name: base-hw\ncpus: 4\nmemory_kb: 16777216\n"
            "disks:\n  - name: nvme0n1\ninterfaces:\n  - name: eth0\n"
        )
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
            host:
              profile: base-hw
              overrides:
                cpus: 8
            phases:
              - name: p1
                duration: 60
        """)
        profile = WorkloadProfile.from_string(yaml_text, config_dir=tmp_path)
        assert profile.hardware is not None
        assert profile.hardware.cpus == 8
        assert profile.hardware.memory_kb == 16777216  # inherited from base


# ---------------------------------------------------------------------------
# T010: from_file delegates to from_string
# ---------------------------------------------------------------------------


class TestFromFile:
    def test_from_file_delegates_to_from_string(self, tmp_path: Path) -> None:
        """from_file MUST call from_string (not duplicate logic)."""
        profile_file = tmp_path / "test.yaml"
        profile_file.write_text(MINIMAL_INLINE_HOST)

        with patch.object(
            WorkloadProfile, "from_string", wraps=WorkloadProfile.from_string
        ) as mock_from_string:
            WorkloadProfile.from_file(profile_file)
            mock_from_string.assert_called_once()

    def test_from_file_reads_file_and_parses(self, tmp_path: Path) -> None:
        profile_file = tmp_path / "test.yaml"
        profile_file.write_text(MINIMAL_INLINE_HOST)
        profile = WorkloadProfile.from_file(profile_file)
        assert profile.meta.duration == 120
        assert profile.hardware is not None
        assert profile.hardware.cpus == 2


# ---------------------------------------------------------------------------
# T010: ValidationError cases
# ---------------------------------------------------------------------------


class TestValidationErrors:
    def test_ratio_violation_fr026(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: p1
                duration: 60
                cpu:
                  utilization: 0.9
                  user_ratio: 0.7
                  sys_ratio: 0.3
                  iowait_ratio: 0.1
        """)
        with pytest.raises(ValidationError, match="FR-026"):
            WorkloadProfile.from_string(yaml_text)

    def test_duration_mismatch_fr027(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 120
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: p1
                duration: 60
        """)
        with pytest.raises(ValidationError, match="FR-027"):
            WorkloadProfile.from_string(yaml_text)

    def test_unknown_profile_fr028(self, tmp_path: Path) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
            host:
              profile: nonexistent-profile
            phases:
              - name: p1
                duration: 60
        """)
        with pytest.raises(ValidationError, match="nonexistent-profile"):
            WorkloadProfile.from_string(yaml_text, config_dir=tmp_path)

    def test_noise_out_of_range_fr029(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
              noise: 1.5
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: p1
                duration: 60
        """)
        with pytest.raises(ValidationError, match="FR-029"):
            WorkloadProfile.from_string(yaml_text)

    def test_bad_interval_fr030(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
              interval: 0
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: p1
                duration: 60
        """)
        with pytest.raises(ValidationError, match="FR-030"):
            WorkloadProfile.from_string(yaml_text)

    def test_first_phase_linear_fr055(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: p1
                duration: 60
                transition: linear
        """)
        with pytest.raises(ValidationError, match="FR-055"):
            WorkloadProfile.from_string(yaml_text)

    def test_bare_inline_fields_with_profile_fr015a(self, tmp_path: Path) -> None:
        hw_yaml = tmp_path / "hw.yaml"
        hw_yaml.write_text(
            "name: hw\ncpus: 2\nmemory_kb: 8388608\n"
            "disks:\n  - name: sda\ninterfaces:\n  - name: eth0\n"
        )
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 60
            host:
              profile: hw
              cpus: 4
            phases:
              - name: p1
                duration: 60
        """)
        with pytest.raises(ValidationError, match="overrides"):
            WorkloadProfile.from_string(yaml_text, config_dir=tmp_path)

    def test_repeat_daily_overflow_fr031(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 3600
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: daily-peak
                duration: 7200
                repeat: daily
        """)
        with pytest.raises(ValidationError, match="FR-031"):
            WorkloadProfile.from_string(yaml_text)


# ---------------------------------------------------------------------------
# T010: ProfileResolver tests
# ---------------------------------------------------------------------------


class TestProfileResolver:
    def test_list_all_returns_bundled_entries(self) -> None:
        resolver = ProfileResolver()
        entries = resolver.list_all()
        names = [e.name for e in entries]
        # At least generic-small is bundled
        assert "generic-small" in names

    def test_list_all_bundled_source_label(self) -> None:
        resolver = ProfileResolver()
        entries = resolver.list_all()
        for e in entries:
            if e.source == "bundled":
                assert isinstance(e.name, str)
                assert e.path.exists()

    def test_resolve_bundled_profile(self) -> None:
        resolver = ProfileResolver()
        hw = resolver.resolve("generic-small")
        assert isinstance(hw, HardwareProfile)
        assert hw.cpus == 2
        assert hw.memory_kb == 8388608

    def test_resolve_unknown_raises_validation_error(self) -> None:
        resolver = ProfileResolver()
        with pytest.raises(ValidationError, match="not found"):
            resolver.resolve("does-not-exist-xyz")

    def test_config_dir_overrides_bundled(self, tmp_path: Path) -> None:
        # Create a config-dir version of generic-small with different cpus
        override_yaml = tmp_path / "generic-small.yaml"
        override_yaml.write_text(
            "name: generic-small\ncpus: 99\nmemory_kb: 8388608\n"
            "disks:\n  - name: sda\ninterfaces:\n  - name: eth0\n"
        )
        resolver = ProfileResolver(config_dir=tmp_path)
        hw = resolver.resolve("generic-small")
        assert hw.cpus == 99  # config-dir version wins

    def test_config_dir_entries_labelled_config_dir(self, tmp_path: Path) -> None:
        hw_yaml = tmp_path / "my-custom.yaml"
        hw_yaml.write_text(
            "name: my-custom\ncpus: 4\nmemory_kb: 8388608\n"
            "disks:\n  - name: sda\ninterfaces:\n  - name: eth0\n"
        )
        resolver = ProfileResolver(config_dir=tmp_path)
        entries = resolver.list_all()
        custom = next((e for e in entries if e.name == "my-custom"), None)
        assert custom is not None
        assert custom.source == "config-dir"

    def test_resolve_config_dir_only_profile(self, tmp_path: Path) -> None:
        hw_yaml = tmp_path / "test-only.yaml"
        hw_yaml.write_text(
            "name: test-only\ncpus: 1\nmemory_kb: 4194304\n"
            "disks:\n  - name: sda\ninterfaces:\n  - name: eth0\n"
        )
        resolver = ProfileResolver(config_dir=tmp_path)
        hw = resolver.resolve("test-only")
        assert hw.cpus == 1

    def test_inline_host_no_profile_field(self) -> None:
        from pmlogsynth.profile import HostConfig

        host = HostConfig(cpus=2, memory_kb=8388608)
        resolver = ProfileResolver()
        hw = resolver.resolve_host(host)
        assert hw.cpus == 2

    def test_inline_host_missing_cpus_raises(self) -> None:
        from pmlogsynth.profile import HostConfig

        host = HostConfig(memory_kb=8388608)
        resolver = ProfileResolver()
        with pytest.raises(ValidationError, match="cpus"):
            resolver.resolve_host(host)


# ---------------------------------------------------------------------------
# meta.start parsing tests
# ---------------------------------------------------------------------------


class TestMetaStart:
    def test_meta_start_omitted_is_none(self) -> None:
        profile = WorkloadProfile.from_string(MINIMAL_INLINE_HOST)
        assert profile.meta.start is None

    def test_meta_start_parses_iso8601_utc_z(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 120
              interval: 60
              start: "2026-03-02T00:00:00Z"
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: baseline
                duration: 120
        """)
        from datetime import datetime, timezone
        profile = WorkloadProfile.from_string(yaml_text)
        assert profile.meta.start == datetime(2026, 3, 2, 0, 0, 0, tzinfo=timezone.utc)

    def test_meta_start_parses_iso8601_space_utc(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 120
              interval: 60
              start: "2026-03-02 00:00:00 UTC"
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: baseline
                duration: 120
        """)
        from datetime import datetime, timezone
        profile = WorkloadProfile.from_string(yaml_text)
        assert profile.meta.start == datetime(2026, 3, 2, 0, 0, 0, tzinfo=timezone.utc)

    def test_meta_start_invalid_raises_validation_error(self) -> None:
        yaml_text = textwrap.dedent("""\
            meta:
              duration: 120
              interval: 60
              start: "not-a-date"
            host:
              cpus: 2
              memory_kb: 8388608
            phases:
              - name: baseline
                duration: 120
        """)
        with pytest.raises(ValidationError, match="meta.start"):
            WorkloadProfile.from_string(yaml_text)
