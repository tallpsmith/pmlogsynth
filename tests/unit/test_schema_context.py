"""Tier 1 tests for pmlogsynth/schema_context.md and --show-schema CLI flag."""

import importlib.resources
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_schema_content() -> str:
    return importlib.resources.read_text(  # type: ignore[attr-defined]
        "pmlogsynth", "schema_context.md", encoding="utf-8"
    )


def _get_pyproject_version() -> str:
    """Read the version string from pyproject.toml without installing toml deps."""
    from pathlib import Path

    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version") and "=" in stripped:
            # version = "0.1.0"
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("Could not parse version from pyproject.toml")


# ---------------------------------------------------------------------------
# Schema document tests (T002)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_schema_context_file_exists() -> None:
    """schema_context.md is loadable via importlib.resources."""
    content = _get_schema_content()
    assert content, "schema_context.md must not be empty"


@pytest.mark.unit
def test_schema_context_version_matches() -> None:
    """Schema Version line in the doc matches pyproject.toml version."""
    content = _get_schema_content()
    version = _get_pyproject_version()
    assert f"Schema Version: {version}" in content, (
        f"Expected 'Schema Version: {version}' in schema_context.md"
    )


@pytest.mark.unit
def test_schema_context_has_required_sections() -> None:
    """Schema doc has headings or sections for meta, host, and phases."""
    content = _get_schema_content()
    for section in ("meta", "host", "phases"):
        assert section in content, f"Missing required section '{section}' in schema_context.md"


@pytest.mark.unit
def test_schema_context_lists_hardware_profiles() -> None:
    """Schema doc lists all 7 bundled hardware profile names."""
    content = _get_schema_content()
    profiles = [
        "generic-small",
        "generic-medium",
        "generic-large",
        "generic-xlarge",
        "compute-optimized",
        "memory-optimized",
        "storage-optimized",
    ]
    for profile_name in profiles:
        assert profile_name in content, (
            f"Bundled profile '{profile_name}' not listed in schema_context.md"
        )


@pytest.mark.unit
def test_schema_context_within_token_budget() -> None:
    """Schema doc is within the 8k-token budget (≤ 32 000 characters)."""
    content = _get_schema_content()
    assert len(content) <= 32000, (
        f"schema_context.md is {len(content)} characters — exceeds 32 000 char limit"
    )


# ---------------------------------------------------------------------------
# CLI --show-schema test (T004)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_show_schema_cli_exits_zero() -> None:
    """pmlogsynth --show-schema exits 0 and prints the schema doc to stdout."""
    result = subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "--show-schema"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"--show-schema exited {result.returncode}\nstderr: {result.stderr}"
    )
    assert result.stdout.strip(), "--show-schema produced no output on stdout"
