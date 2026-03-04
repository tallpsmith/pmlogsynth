"""Tier 1 unit tests for CLI argument parsing and informational commands."""

from pathlib import Path
from unittest.mock import patch

import pytest

from pmlogsynth.cli import (
    _ALL_METRIC_NAMES,
    _cmd_list_metrics,
    main,
)
from pmlogsynth.profile import ValidationError
from pmlogsynth.time_parsing import parse_absolute_timestamp


def test_list_metrics_output_is_sorted() -> None:
    """--list-metrics output is sorted lexicographically."""
    assert _ALL_METRIC_NAMES == sorted(_ALL_METRIC_NAMES)


def test_list_metrics_count() -> None:
    """--list-metrics has exactly 53 metric names (24 original + 29 new from 004)."""
    assert len(_ALL_METRIC_NAMES) == 53


def test_list_metrics_contains_all_domains() -> None:
    """At least one metric from each of the 5 domains."""
    prefixes = ["kernel.all.cpu", "mem.", "disk.", "network.", "kernel.all.load"]
    for prefix in prefixes:
        assert any(m.startswith(prefix) for m in _ALL_METRIC_NAMES), f"No metric for {prefix}"


def test_list_metrics_cmd_exits_zero(capsys: pytest.CaptureFixture) -> None:
    """_cmd_list_metrics returns 0 and prints all names."""
    rc = _cmd_list_metrics()
    assert rc == 0
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 53
    assert lines == sorted(lines)


def test_parse_start_iso8601_z() -> None:
    dt = parse_absolute_timestamp("2024-01-15T09:00:00Z", field="--start")
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15
    assert dt.hour == 9
    assert dt.tzinfo is not None


def test_parse_start_human_readable_utc() -> None:
    dt = parse_absolute_timestamp("2024-01-15 09:00:00 UTC", field="--start")
    assert dt.year == 2024 and dt.hour == 9


def test_parse_start_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        parse_absolute_timestamp("not-a-date", field="--start")


def test_fleet_subcommand_exits_2(capsys: pytest.CaptureFixture) -> None:
    """fleet subcommand prints 'not yet implemented' and exits 2."""
    with patch("sys.argv", ["pmlogsynth", "fleet"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "fleet" in captured.err.lower() or "not yet implemented" in captured.err.lower()


def test_list_metrics_flag_exits_zero() -> None:
    """--list-metrics flag exits 0."""
    with patch("sys.argv", ["pmlogsynth", "--list-metrics"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0


def test_list_profiles_flag_exits_zero() -> None:
    """--list-profiles flag exits 0."""
    with patch("sys.argv", ["pmlogsynth", "--list-profiles"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0


def test_list_profiles_output_format(capsys: pytest.CaptureFixture) -> None:
    """--list-profiles shows SOURCE NAME columns."""
    with patch("sys.argv", ["pmlogsynth", "--list-profiles"]):
        with pytest.raises(SystemExit):
            main()
    captured = capsys.readouterr()
    assert "SOURCE" in captured.out or "bundled" in captured.out


def test_validate_flag_with_force_exits_nonzero(
    capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """--validate is incompatible with --force."""
    profile = tmp_path / "p.yaml"
    profile.write_text(
        "meta:\n  duration: 60\n  interval: 60\n"
        "host:\n  cpus: 2\n  memory_kb: 8388608\n"
        "  disks:\n    - name: sda\n  interfaces:\n    - name: eth0\n"
        "phases:\n  - name: b\n    duration: 60\n"
    )
    with patch("sys.argv", ["pmlogsynth", "--validate", "--force", str(profile)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code != 0


def test_validate_good_profile_exits_zero(tmp_path: Path) -> None:
    """--validate with a valid profile exits 0."""
    profile = tmp_path / "p.yaml"
    profile.write_text(
        "meta:\n  duration: 60\n  interval: 60\n"
        "host:\n  cpus: 2\n  memory_kb: 8388608\n"
        "  disks:\n    - name: sda\n  interfaces:\n    - name: eth0\n"
        "phases:\n  - name: baseline\n    duration: 60\n"
    )
    with patch("sys.argv", ["pmlogsynth", "--validate", str(profile)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0


def test_validate_bad_profile_exits_nonzero(tmp_path: Path) -> None:
    """--validate with invalid profile (bad ratios) exits 1."""
    profile = tmp_path / "bad.yaml"
    profile.write_text(
        "meta:\n  duration: 60\n  interval: 60\n"
        "host:\n  cpus: 2\n  memory_kb: 8388608\n"
        "  disks:\n    - name: sda\n  interfaces:\n    - name: eth0\n"
        "phases:\n  - name: b\n    duration: 60\n"
        "    cpu:\n      user_ratio: 0.8\n      sys_ratio: 0.8\n"
    )
    with patch("sys.argv", ["pmlogsynth", "--validate", str(profile)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_no_profile_arg_exits_nonzero(capsys: pytest.CaptureFixture) -> None:
    """Running without PROFILE argument exits non-zero."""
    with patch("sys.argv", ["pmlogsynth"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code != 0
