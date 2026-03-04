"""Integration tests for relative meta.start support."""

import textwrap
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from pmlogsynth.profile import ValidationError, WorkloadProfile

_INLINE_HOST = textwrap.dedent("""\
    host:
      cpus: 2
      memory_kb: 8388608
    phases:
      - name: baseline
        duration: 5400
        cpu:
          utilization: 0.5
""")


def _profile_with_start(start_value: str) -> str:
    return textwrap.dedent(f"""\
        meta:
          duration: 5400
          interval: 60
          start: {start_value}
    """) + _INLINE_HOST


# ---------------------------------------------------------------------------
# T008: relative meta.start round-trip
# ---------------------------------------------------------------------------


class TestRelativeMetaStart:
    """Integration: profile with meta.start: -90m loads and resolves correctly."""

    def test_relative_minus_90m_resolves_within_2s_of_expected(self):
        fixed_now = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        expected = fixed_now - timedelta(seconds=5400)  # 90m = 5400s

        yaml_text = _profile_with_start("-90m")

        with patch(
            "pmlogsynth.time_parsing.pcp_parse_interval", return_value=5400
        ):
            with patch("pmlogsynth.time_parsing.datetime") as mock_dt:
                mock_dt.now.return_value = fixed_now
                mock_dt.strptime = datetime.strptime
                profile = WorkloadProfile.from_string(yaml_text)

        assert profile.meta.start is not None
        diff = abs((profile.meta.start - expected).total_seconds())
        assert diff < 2, f"Expected ~{expected}, got {profile.meta.start}"

    def test_relative_meta_start_is_utc_aware(self):
        yaml_text = _profile_with_start("-90m")
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=5400):
            profile = WorkloadProfile.from_string(yaml_text)
        assert profile.meta.start is not None
        assert profile.meta.start.tzinfo is not None

    def test_absolute_meta_start_unchanged(self):
        """Absolute timestamps must still work after the refactor."""
        yaml_text = _profile_with_start('"2026-03-04T12:00:00Z"')
        profile = WorkloadProfile.from_string(yaml_text)
        assert profile.meta.start == datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# T016: --validate flag with invalid relative meta.start
# ---------------------------------------------------------------------------


class TestValidateFlagInvalidRelativeStart:
    """Integration: --validate produces ValidationError for bad relative forms."""

    def _load(self, start_value: str) -> None:
        yaml_text = _profile_with_start(start_value)
        WorkloadProfile.from_string(yaml_text)

    def test_unknown_unit_raises_validation_error(self):
        with patch(
            "pmlogsynth.time_parsing.pcp_parse_interval",
            side_effect=ValidationError("unknown unit"),
        ):
            with pytest.raises(ValidationError):
                self._load("-90x")

    def test_bare_dash_raises_validation_error(self):
        with pytest.raises(ValidationError):
            self._load("-")

    def test_positive_offset_raises_validation_error(self):
        with pytest.raises(ValidationError, match="past-anchored"):
            self._load("+30m")
