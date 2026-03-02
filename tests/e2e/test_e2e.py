"""E2E tests — require real pcp.pmi (conditionally skipped if absent)."""

import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
HW_PROFILES_DIR = FIXTURES_DIR / "profiles"


@pytest.mark.e2e
def test_archive_roundtrip(pcp_available: bool, tmp_path: Path) -> None:
    """Generate an archive from good-baseline and verify all three PCP tools accept it."""
    archive_path = tmp_path / "archive"
    profile = HW_PROFILES_DIR / "good-baseline.yaml"

    result = subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "-C", str(HW_PROFILES_DIR),
         "-o", str(archive_path), str(profile)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"pmlogsynth failed:\n{result.stderr}"

    check = subprocess.run(
        ["pmlogcheck", str(archive_path)],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, f"pmlogcheck failed:\n{check.stderr}"

    pmval = subprocess.run(
        ["pmval", "-a", str(archive_path), "kernel.all.load"],
        capture_output=True,
        text=True,
    )
    assert pmval.returncode == 0, f"pmval failed:\n{pmval.stderr}"

    pmrep = subprocess.run(
        ["pmrep", "-a", str(archive_path), "kernel.all.load"],
        capture_output=True,
        text=True,
    )
    assert pmrep.returncode == 0, f"pmrep failed:\n{pmrep.stderr}"


@pytest.mark.e2e
@pytest.mark.parametrize("profile", [
    HW_PROFILES_DIR / "good-baseline.yaml",
    FIXTURES_DIR / "workload-linear-ramp.yaml",
])
def test_validate_accepts_good_profiles(pcp_available: bool, profile: Path) -> None:
    """--validate exits 0 for well-formed profiles."""
    result = subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "--validate",
         "-C", str(HW_PROFILES_DIR), str(profile)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected valid but rc={result.returncode} for {profile.name}:\n{result.stderr}"
    )


@pytest.mark.e2e
@pytest.mark.parametrize("profile", [
    HW_PROFILES_DIR / "bad-ratio.yaml",
    HW_PROFILES_DIR / "bad-duration.yaml",
    HW_PROFILES_DIR / "bad-noise.yaml",
])
def test_validate_rejects_bad_profiles(pcp_available: bool, profile: Path) -> None:
    """--validate exits 1 with non-empty stderr for invalid profiles."""
    result = subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "--validate",
         "-C", str(HW_PROFILES_DIR), str(profile)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"Expected rc=1 but got {result.returncode} for {profile.name}"
    )
    assert result.stderr.strip(), f"Expected non-empty stderr for invalid profile {profile.name}"


@pytest.mark.e2e
def test_quickstart_workflow(pcp_available: bool, tmp_path: Path) -> None:
    """Validate the README Quick Start workflow end-to-end."""
    profile = HW_PROFILES_DIR / "good-baseline.yaml"
    archive_path = tmp_path / "archive"

    # Step 1: validate
    result = subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "--validate",
         "-C", str(HW_PROFILES_DIR), str(profile)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Step 1 validate failed:\n{result.stderr}"

    # Step 2: generate archive
    result = subprocess.run(
        [sys.executable, "-m", "pmlogsynth",
         "-C", str(HW_PROFILES_DIR), "-o", str(archive_path), str(profile)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Step 2 generate failed:\n{result.stderr}"

    # Step 3: pmlogcheck
    result = subprocess.run(
        ["pmlogcheck", str(archive_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Step 3 pmlogcheck failed:\n{result.stderr}"

    # Step 4: pmval
    result = subprocess.run(
        ["pmval", "-a", str(archive_path), "kernel.all.load"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Step 4 pmval failed:\n{result.stderr}"
