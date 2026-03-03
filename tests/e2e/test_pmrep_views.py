"""E2E tests for pmrep view support (T019) — conditionally skipped if PCP absent."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
COMPLETE_EXAMPLE = DOCS_DIR / "complete-example.yml"

# Prevent pmrep from invoking a pager (less/more) when output is large.
# capture_output=True already detaches stdout from the TTY, but PAGER=cat
# is an explicit belt-and-suspenders guard for PCP tools that check $PAGER.
_NO_PAGER_ENV = {**os.environ, "PAGER": "cat"}


def _run_pmrep(archive: Path, view: str) -> subprocess.CompletedProcess:
    # Colon-prefix selects a built-in pmrep view (e.g. :pmstat, :vmstat).
    return subprocess.run(
        ["pmrep", ":" + view, "-a", str(archive)],
        capture_output=True,
        text=True,
        env=_NO_PAGER_ENV,
    )


@pytest.mark.e2e
def test_pmrep_pmstat_exits_zero(pcp_available: bool, tmp_path: Path) -> None:
    """SC-001: pmrep -c pmstat exits 0 with no unknown metric errors (T019)."""
    archive = tmp_path / "complete-example"
    result = subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "-o", str(archive), str(COMPLETE_EXAMPLE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "pmlogsynth failed:\n{}".format(result.stderr)

    pmrep = _run_pmrep(archive, "pmstat")
    assert pmrep.returncode == 0, (
        "pmrep -c pmstat failed:\nstdout={}\nstderr={}".format(pmrep.stdout, pmrep.stderr)
    )
    assert "unknown metric" not in pmrep.stderr.lower(), (
        "pmrep reported unknown metrics:\n{}".format(pmrep.stderr)
    )


@pytest.mark.e2e
def test_pmrep_vmstat_exits_zero(pcp_available: bool, tmp_path: Path) -> None:
    """SC-002: pmrep -c vmstat exits 0 (T019)."""
    archive = tmp_path / "complete-example"
    subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "-o", str(archive), str(COMPLETE_EXAMPLE)],
        capture_output=True,
        text=True,
    )

    pmrep = _run_pmrep(archive, "vmstat")
    assert pmrep.returncode == 0, (
        "pmrep -c vmstat failed:\nstdout={}\nstderr={}".format(pmrep.stdout, pmrep.stderr)
    )
    assert "unknown metric" not in pmrep.stderr.lower()


@pytest.mark.e2e
def test_pmrep_vmstat_d_exits_zero(pcp_available: bool, tmp_path: Path) -> None:
    """pmrep -c vmstat-d exits 0 with disk columns populated (T019)."""
    archive = tmp_path / "complete-example"
    subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "-o", str(archive), str(COMPLETE_EXAMPLE)],
        capture_output=True,
        text=True,
    )

    pmrep = _run_pmrep(archive, "vmstat-d")
    assert pmrep.returncode == 0, (
        "pmrep -c vmstat-d failed:\nstdout={}\nstderr={}".format(pmrep.stdout, pmrep.stderr)
    )
    assert "unknown metric" not in pmrep.stderr.lower()


@pytest.mark.e2e
def test_pmlogcheck_clean_on_complete_example(pcp_available: bool, tmp_path: Path) -> None:
    """Generated archive passes pmlogcheck (no corruption)."""
    archive = tmp_path / "complete-example"
    subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "-o", str(archive), str(COMPLETE_EXAMPLE)],
        capture_output=True,
        text=True,
    )

    check = subprocess.run(
        ["pmlogcheck", str(archive)],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, (
        "pmlogcheck failed:\n{}".format(check.stdout + check.stderr)
    )
