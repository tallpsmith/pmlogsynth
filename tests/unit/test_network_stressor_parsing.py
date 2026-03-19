"""Tier 1 tests for NetworkStressor error_rate parsing."""

import pytest

from pmlogsynth.profile import NetworkStressor, ValidationError


def _parse(raw: dict) -> NetworkStressor:
    from pmlogsynth.profile import _parse_network_stressor
    return _parse_network_stressor(raw)


def test_error_rate_parsed_from_yaml() -> None:
    result = _parse({"rx_mbps": 10.0, "error_rate": 0.001})
    assert result.error_rate == 0.001


def test_error_rate_missing_defaults_to_none() -> None:
    result = _parse({"rx_mbps": 10.0})
    assert result.error_rate is None


def test_error_rate_zero_is_valid() -> None:
    result = _parse({"error_rate": 0.0})
    assert result.error_rate == 0.0


def test_error_rate_one_is_valid() -> None:
    result = _parse({"error_rate": 1.0})
    assert result.error_rate == 1.0


def test_error_rate_negative_raises() -> None:
    with pytest.raises(ValidationError, match="error_rate"):
        _parse({"error_rate": -0.1})


def test_error_rate_above_one_raises() -> None:
    with pytest.raises(ValidationError, match="error_rate"):
        _parse({"error_rate": 1.5})
