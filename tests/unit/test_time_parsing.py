"""Unit tests for time_parsing.py — TDD: write failing tests first."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from pmlogsynth.profile import ValidationError

# ---------------------------------------------------------------------------
# T002: pcp_parse_interval
# ---------------------------------------------------------------------------

class TestPcpParseInterval:
    """Tests for pcp_parse_interval — wraps PCP's pmParseInterval."""

    def test_valid_interval_returns_seconds(self):
        from pmlogsynth.time_parsing import pcp_parse_interval
        with patch("pmlogsynth.time_parsing._pmapi_parse_interval", return_value=90.0):
            result = pcp_parse_interval("90s")
        assert result == 90

    def test_result_is_int(self):
        from pmlogsynth.time_parsing import pcp_parse_interval
        with patch("pmlogsynth.time_parsing._pmapi_parse_interval", return_value=3600.0):
            result = pcp_parse_interval("1h")
        assert isinstance(result, int)

    def test_zero_seconds_allowed(self):
        from pmlogsynth.time_parsing import pcp_parse_interval
        with patch("pmlogsynth.time_parsing._pmapi_parse_interval", return_value=0.0):
            result = pcp_parse_interval("0s")
        assert result == 0

    def test_compound_interval(self):
        from pmlogsynth.time_parsing import pcp_parse_interval
        with patch("pmlogsynth.time_parsing._pmapi_parse_interval", return_value=5400.0):
            result = pcp_parse_interval("1h30m")
        assert result == 5400

    def test_days_interval(self):
        from pmlogsynth.time_parsing import pcp_parse_interval
        with patch("pmlogsynth.time_parsing._pmapi_parse_interval", return_value=172800.0):
            result = pcp_parse_interval("2days")
        assert result == 172800

    def test_parse_failure_raises_validation_error(self):
        from pmlogsynth.time_parsing import pcp_parse_interval
        with patch(
            "pmlogsynth.time_parsing._pmapi_parse_interval",
            side_effect=Exception("bad interval"),
        ):
            with pytest.raises(ValidationError):
                pcp_parse_interval("90x")

    def test_pcp_unavailable_raises_validation_error_not_import_error(self):
        from pmlogsynth.time_parsing import pcp_parse_interval
        with patch(
            "pmlogsynth.time_parsing._pmapi_parse_interval",
            side_effect=ImportError("no pcp"),
        ):
            with pytest.raises(ValidationError, match="PCP"):
                pcp_parse_interval("90m")


# ---------------------------------------------------------------------------
# T003: parse_absolute_timestamp
# ---------------------------------------------------------------------------

_FIXED_DT = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)

class TestParseAbsoluteTimestamp:
    """Tests for parse_absolute_timestamp — all six accepted formats."""

    def _parse(self, raw, field="meta.start"):
        from pmlogsynth.time_parsing import parse_absolute_timestamp
        return parse_absolute_timestamp(raw, field=field)

    def test_iso8601_Z(self):
        result = self._parse("2025-01-15T09:00:00Z")
        assert result == _FIXED_DT

    def test_iso8601_plus_offset(self):
        result = self._parse("2025-01-15T09:00:00+00:00")
        assert result == _FIXED_DT

    def test_iso8601_bare_T(self):
        result = self._parse("2025-01-15T09:00:00")
        assert result == _FIXED_DT

    def test_space_utc(self):
        result = self._parse("2025-01-15 09:00:00 UTC")
        assert result == _FIXED_DT

    def test_space_bare(self):
        result = self._parse("2025-01-15 09:00:00")
        assert result == _FIXED_DT

    def test_iso8601_percent_z(self):
        result = self._parse("2025-01-15T09:00:00+0000")
        assert result == _FIXED_DT

    def test_all_results_are_utc_aware(self):
        for raw in [
            "2025-01-15T09:00:00Z",
            "2025-01-15T09:00:00+00:00",
            "2025-01-15T09:00:00",
            "2025-01-15 09:00:00 UTC",
            "2025-01-15 09:00:00",
        ]:
            result = self._parse(raw)
            assert result.tzinfo is not None, f"tzinfo is None for {raw!r}"

    def test_unrecognised_format_raises_validation_error(self):
        with pytest.raises(ValidationError):
            self._parse("not-a-date")

    def test_error_includes_field_name(self):
        from pmlogsynth.time_parsing import parse_absolute_timestamp
        with pytest.raises(ValidationError, match="meta.start"):
            parse_absolute_timestamp("garbage", field="meta.start")

    def test_custom_field_name_in_error(self):
        from pmlogsynth.time_parsing import parse_absolute_timestamp
        with pytest.raises(ValidationError, match="--start"):
            parse_absolute_timestamp("garbage", field="--start")


# ---------------------------------------------------------------------------
# T006: parse_relative_starttime
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)


class TestParseRelativeStarttime:
    """Tests for parse_relative_starttime — mocks pcp_parse_interval."""

    def _parse(self, raw, now=_FIXED_NOW):
        from pmlogsynth.time_parsing import parse_relative_starttime
        return parse_relative_starttime(raw, now=now)

    def test_minus_90m(self):
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=5400):
            result = self._parse("-90m")
        assert result == _FIXED_NOW - timedelta(seconds=5400)

    def test_minus_1h30m(self):
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=5400):
            result = self._parse("-1h30m")
        assert result == _FIXED_NOW - timedelta(seconds=5400)

    def test_minus_2d(self):
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=172800):
            result = self._parse("-2d")
        assert result == _FIXED_NOW - timedelta(seconds=172800)

    def test_minus_0s(self):
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=0):
            result = self._parse("-0s")
        assert result == _FIXED_NOW

    def test_minus_2days(self):
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=172800):
            result = self._parse("-2days")
        assert result == _FIXED_NOW - timedelta(seconds=172800)

    def test_result_is_utc_aware(self):
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=3600):
            result = self._parse("-1h")
        assert result.tzinfo is not None

    def test_calls_pcp_parse_interval_with_interval_portion(self):
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=90) as mock_pcp:
            self._parse("-90s")
        mock_pcp.assert_called_once_with("90s")

    def test_positive_offset_raises_validation_error(self):
        with pytest.raises(ValidationError, match="past-anchored"):
            self._parse("+30m")

    def test_bare_dash_raises_validation_error(self):
        with pytest.raises(ValidationError):
            self._parse("-")

    def test_no_leading_dash_raises_validation_error(self):
        with pytest.raises(ValidationError):
            self._parse("90m")

    def test_default_now_is_used_when_none(self):
        from pmlogsynth.time_parsing import parse_relative_starttime
        with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=3600):
            before = datetime.now(tz=timezone.utc)
            result = parse_relative_starttime("-1h")
            after = datetime.now(tz=timezone.utc)
        # result should be approximately (now - 1h)
        assert before - timedelta(seconds=3601) < result < after - timedelta(seconds=3599)
