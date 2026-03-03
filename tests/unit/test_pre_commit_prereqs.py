"""
Tier 1 tests for pre-commit.sh prerequisite detection.

Strategy: invoke pre-commit.sh via subprocess with a fully restricted environment.
- PATH is stripped to {tmp bin dir}:/bin:/usr/bin — no venv, no Homebrew.
- A stub python3 in tmp bin dir controls import-check outcomes.
- Stub executables for dev tools (ruff, mypy, pytest, pmpython) are added only
  when a test scenario wants them to be "present".

This ensures the script exits at the prereq check step; quality gates never run.
"""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "pre-commit.sh"


def make_stub(directory: Path, name: str, exit_code: int = 0) -> None:
    """Create a minimal stub executable that exits with exit_code."""
    stub = directory / name
    stub.write_text(f"#!/bin/bash\nexit {exit_code}\n")
    stub.chmod(0o755)


def make_python3_stub(directory: Path, cpmapi_ok: bool, pcp_pmi_ok: bool) -> None:
    """Create a stub python3 that controls import check outcomes."""
    cpmapi_exit = 0 if cpmapi_ok else 1
    pcp_pmi_exit = 0 if pcp_pmi_ok else 1
    stub = directory / "python3"
    stub.write_text(
        "#!/bin/bash\n"
        f'if [[ "$*" == *"cpmapi"* ]]; then exit {cpmapi_exit}; fi\n'
        f'if [[ "$*" == *"pcp.pmi"* ]]; then exit {pcp_pmi_exit}; fi\n'
        "exit 0\n"
    )
    stub.chmod(0o755)


def make_uname_stub(directory: Path) -> None:
    """Create a uname stub reporting Linux — avoids picking up real system uname."""
    stub = directory / "uname"
    stub.write_text("#!/bin/bash\necho Linux\n")
    stub.chmod(0o755)


def run_script(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


def base_env(tmp_path: Path) -> tuple:
    """
    Fully isolated env: PATH contains only bin_dir so no system binaries
    (including pmpython) can leak in.  Provides python3 and uname stubs.
    python3 stub defaults to both imports failing (all-missing scenario).
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_python3_stub(bin_dir, cpmapi_ok=False, pcp_pmi_ok=False)
    make_uname_stub(bin_dir)
    env = {
        "PATH": str(bin_dir),
        "HOME": str(tmp_path),
    }
    return env, bin_dir


class TestAllPrerequisitesMissing:
    """No venv, no tools, no PCP — expect exit 1 with all 7 labels."""

    def test_exits_nonzero(self, tmp_path):
        env, _ = base_env(tmp_path)
        result = run_script(env)
        assert result.returncode == 1

    def test_prerequisite_check_failed_header(self, tmp_path):
        env, _ = base_env(tmp_path)
        result = run_script(env)
        assert "prerequisite check failed" in result.stdout

    def test_no_virtualenv_label(self, tmp_path):
        env, _ = base_env(tmp_path)
        result = run_script(env)
        assert "no virtualenv active" in result.stdout

    def test_ruff_label(self, tmp_path):
        env, _ = base_env(tmp_path)
        result = run_script(env)
        assert "ruff not found" in result.stdout

    def test_mypy_label(self, tmp_path):
        env, _ = base_env(tmp_path)
        result = run_script(env)
        assert "mypy not found" in result.stdout

    def test_pytest_label(self, tmp_path):
        env, _ = base_env(tmp_path)
        result = run_script(env)
        assert "pytest not found" in result.stdout

    def test_pmpython_label(self, tmp_path):
        env, _ = base_env(tmp_path)
        result = run_script(env)
        assert "pmpython not on PATH" in result.stdout

    def test_quality_gates_do_not_run(self, tmp_path):
        env, _ = base_env(tmp_path)
        result = run_script(env)
        assert "ruff check" not in result.stdout
        assert "=== mypy ===" not in result.stdout
        assert "Unit + Integration" not in result.stdout


class TestPCPOnlyMissing:
    """venv active, dev tools present, pmpython absent — pmpython + import labels."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path)
        env["VIRTUAL_ENV"] = str(tmp_path / ".venv")
        for tool in ("ruff", "mypy", "pytest"):
            make_stub(bin_dir, tool)
        # No pmpython stub — not on PATH
        # python3 stub: both imports fail (PCP not installed)
        return env

    def test_exits_nonzero(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert result.returncode == 1

    def test_pmpython_label_present(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "pmpython not on PATH" in result.stdout

    def test_dev_tool_labels_absent(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "ruff not found" not in result.stdout
        assert "mypy not found" not in result.stdout
        assert "pytest not found" not in result.stdout

    def test_venv_label_absent(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "no virtualenv active" not in result.stdout


class TestCpmapiImportableButPcpPmiNot:
    """cpmapi importable, pcp.pmi not — only pcp.pmi label."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path)
        env["VIRTUAL_ENV"] = str(tmp_path / ".venv")
        for tool in ("ruff", "mypy", "pytest", "pmpython"):
            make_stub(bin_dir, tool)
        # Override python3 stub: cpmapi ok, pcp.pmi not
        make_python3_stub(bin_dir, cpmapi_ok=True, pcp_pmi_ok=False)
        return env

    def test_cpmapi_not_in_output(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "cpmapi not importable" not in result.stdout

    def test_pcp_pmi_label_present(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "pcp.pmi not importable" in result.stdout

    def test_exits_nonzero(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert result.returncode == 1


class TestVenvAbsent:
    """All tools present but no VIRTUAL_ENV — only venv label."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path)
        for tool in ("ruff", "mypy", "pytest", "pmpython"):
            make_stub(bin_dir, tool)
        # python3 stub: both imports pass
        make_python3_stub(bin_dir, cpmapi_ok=True, pcp_pmi_ok=True)
        # No VIRTUAL_ENV
        return env

    def test_exits_nonzero(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert result.returncode == 1

    def test_no_virtualenv_label(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "no virtualenv active" in result.stdout

    def test_tool_labels_absent(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "ruff not found" not in result.stdout
        assert "pmpython not on PATH" not in result.stdout
        assert "cpmapi not importable" not in result.stdout
        assert "pcp.pmi not importable" not in result.stdout


class TestAllPrerequisitesSatisfied:
    """All prerequisites met — prereq check passes, quality gates are attempted."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path)
        env["VIRTUAL_ENV"] = str(tmp_path / ".venv")
        for tool in ("ruff", "mypy", "pytest", "pmpython"):
            make_stub(bin_dir, tool)
        make_python3_stub(bin_dir, cpmapi_ok=True, pcp_pmi_ok=True)
        return env

    def test_no_prerequisite_check_failed_header(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "prerequisite check failed" not in result.stdout

    def test_no_missing_labels(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "MISSING:" not in result.stdout

    def test_man_page_check_gate_is_attempted(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "man page check" in result.stdout
