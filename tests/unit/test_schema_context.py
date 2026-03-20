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


def _get_schema_version_line(content: str) -> str:
    """Extract the 'Schema Version: X.Y.Z' value from schema_context.md."""
    for line in content.splitlines():
        if line.startswith("Schema Version:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("Could not find 'Schema Version:' in schema_context.md")


# ---------------------------------------------------------------------------
# Schema document tests (T002)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_schema_context_file_exists() -> None:
    """schema_context.md is loadable via importlib.resources."""
    content = _get_schema_content()
    assert content, "schema_context.md must not be empty"


@pytest.mark.unit
def test_schema_context_has_valid_version() -> None:
    """Schema Version line in the doc is a valid version string."""
    import re

    content = _get_schema_content()
    version = _get_schema_version_line(content)
    assert re.match(r"^\d+\.\d+\.\d+", version), (
        f"Schema Version '{version}' does not look like a valid version"
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
