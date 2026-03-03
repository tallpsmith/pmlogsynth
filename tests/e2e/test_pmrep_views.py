"""E2E tests for pmrep view support (T019) — conditionally skipped if PCP absent."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
COMPLETE_EXAMPLE = DOCS_DIR / "complete-example.yml"

# Prevent pmrep/pmlogcheck from invoking a pager when output is large.
# capture_output=True detaches stdout from the TTY, but PCP tools also check
# $PAGER, $LESS, and $MORE directly, so we stomp all three.
_NO_PAGER_ENV = {**os.environ, "PAGER": "cat", "LESS": "", "MORE": ""}

# Generous upper bound — archive generation is the slow path (~30s on CI).
_SUBPROCESS_TIMEOUT = 120


def _run_pmrep(archive: Path, view: str) -> subprocess.CompletedProcess:
    # Colon-prefix selects a built-in pmrep view (e.g. :pmstat, :vmstat).
    return subprocess.run(
        ["pmrep", ":" + view, "-a", str(archive)],
        capture_output=True,
        text=True,
        env=_NO_PAGER_ENV,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _run_pmlogsynth(archive: Path, profile: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pmlogsynth", "-o", str(archive), str(profile)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )


@pytest.fixture(scope="session")
def complete_example_archive(pcp_available: bool, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate the complete-example archive once for the entire test session."""
    archive = tmp_path_factory.mktemp("pmrep_views") / "complete-example"
    result = _run_pmlogsynth(archive, COMPLETE_EXAMPLE)
    assert result.returncode == 0, "pmlogsynth failed:\n{}".format(result.stderr)
    return archive


@pytest.mark.e2e
def test_pmrep_pmstat_exits_zero(complete_example_archive: Path) -> None:
    """SC-001: pmrep -c pmstat exits 0 with no unknown metric errors (T019)."""
    pmrep = _run_pmrep(complete_example_archive, "pmstat")
    assert pmrep.returncode == 0, (
        "pmrep -c pmstat failed:\nstdout={}\nstderr={}".format(pmrep.stdout, pmrep.stderr)
    )
    assert "unknown metric" not in pmrep.stderr.lower(), (
        "pmrep reported unknown metrics:\n{}".format(pmrep.stderr)
    )


@pytest.mark.e2e
def test_pmrep_vmstat_exits_zero(complete_example_archive: Path) -> None:
    """SC-002: pmrep -c vmstat exits 0 (T019)."""
    pmrep = _run_pmrep(complete_example_archive, "vmstat")
    assert pmrep.returncode == 0, (
        "pmrep -c vmstat failed:\nstdout={}\nstderr={}".format(pmrep.stdout, pmrep.stderr)
    )
    assert "unknown metric" not in pmrep.stderr.lower()


@pytest.mark.e2e
def test_pmrep_vmstat_d_exits_zero(complete_example_archive: Path) -> None:
    """pmrep -c vmstat-d exits 0 with disk columns populated (T019)."""
    pmrep = _run_pmrep(complete_example_archive, "vmstat-d")
    assert pmrep.returncode == 0, (
        "pmrep -c vmstat-d failed:\nstdout={}\nstderr={}".format(pmrep.stdout, pmrep.stderr)
    )
    assert "unknown metric" not in pmrep.stderr.lower()


@pytest.mark.e2e
def test_pmlogcheck_clean_on_complete_example(complete_example_archive: Path) -> None:
    """Generated archive passes pmlogcheck (no corruption)."""
    check = subprocess.run(
        ["pmlogcheck", str(complete_example_archive)],
        capture_output=True,
        text=True,
        env=_NO_PAGER_ENV,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    assert check.returncode == 0, (
        "pmlogcheck failed:\n{}".format(check.stdout + check.stderr)
    )
