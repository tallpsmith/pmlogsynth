"""Tier 1 unit tests for pcp_constants — verify PM_TYPE_STRING is exported."""

from pmlogsynth.pcp_constants import PM_TYPE_STRING


def test_pm_type_string_is_integer() -> None:
    assert isinstance(PM_TYPE_STRING, int)


def test_pm_type_string_value() -> None:
    assert PM_TYPE_STRING == 6
