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


def run_script(env: dict, args: list = None, script: Path = None) -> subprocess.CompletedProcess:
    cmd = ["/bin/bash", str(script or SCRIPT)] + (args or [])
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def make_script_copy(tmp_path: Path) -> Path:
    """
    Copy pre-commit.sh into tmp_path so SCRIPT_DIR resolves to tmp_path.
    tmp_path has no .venv, which prevents auto-activation — needed for tests
    that want to exercise the 'no virtualenv active' error path.
    """
    copy = tmp_path / "pre-commit.sh"
    copy.write_text(SCRIPT.read_text())
    copy.chmod(0o755)
    return copy


def make_dirname_stub(directory: Path) -> None:
    """Stub dirname using its absolute path so SCRIPT_DIR is always computed
    correctly regardless of the restricted PATH used in tests."""
    stub = directory / "dirname"
    stub.write_text("#!/bin/bash\n/usr/bin/dirname \"$@\"\n")
    stub.chmod(0o755)


def base_env(tmp_path: Path) -> tuple:
    """
    Fully isolated env: PATH contains only bin_dir so no system binaries
    (including pmpython) can leak in.  Provides python3, uname, and dirname
    stubs.  dirname is stubbed so SCRIPT_DIR resolves to the script's actual
    directory rather than accidentally falling back to HOME.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_dirname_stub(bin_dir)
    make_python3_stub(bin_dir, cpmapi_ok=False, pcp_pmi_ok=False)
    make_uname_stub(bin_dir)
    env = {
        "PATH": str(bin_dir),
        "HOME": str(tmp_path),
    }
    return env, bin_dir


class TestAllPrerequisitesMissing:
    """No venv, no tools, no PCP — expect exit 1 with all 7 labels.

    Uses a script copy in tmp_path so SCRIPT_DIR has no .venv, which prevents
    auto-activation and keeps the 'no virtualenv active' error path reachable.
    """

    def _run(self, tmp_path):
        env, _ = base_env(tmp_path)
        return run_script(env, script=make_script_copy(tmp_path))

    def test_exits_nonzero(self, tmp_path):
        assert self._run(tmp_path).returncode == 1

    def test_prerequisite_check_failed_header(self, tmp_path):
        assert "prerequisite check failed" in self._run(tmp_path).stdout

    def test_no_virtualenv_label(self, tmp_path):
        assert "no virtualenv active" in self._run(tmp_path).stdout

    def test_ruff_label(self, tmp_path):
        assert "ruff not found" in self._run(tmp_path).stdout

    def test_mypy_label(self, tmp_path):
        assert "mypy not found" in self._run(tmp_path).stdout

    def test_pytest_label(self, tmp_path):
        assert "pytest not found" in self._run(tmp_path).stdout

    def test_pmpython_label(self, tmp_path):
        assert "pmpython not on PATH" in self._run(tmp_path).stdout

    def test_quality_gates_do_not_run(self, tmp_path):
        result = self._run(tmp_path)
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
    """All tools present, no VIRTUAL_ENV, and no .venv dir — only venv label.

    Uses a script copy in tmp_path (no .venv present) so auto-activation is
    bypassed and the 'no virtualenv active' error path remains reachable.
    """

    def _run(self, tmp_path):
        env, bin_dir = base_env(tmp_path)
        for tool in ("ruff", "mypy", "pytest", "pmpython"):
            make_stub(bin_dir, tool)
        make_python3_stub(bin_dir, cpmapi_ok=True, pcp_pmi_ok=True)
        # No VIRTUAL_ENV, no .venv dir in tmp_path
        return run_script(env, script=make_script_copy(tmp_path))

    def test_exits_nonzero(self, tmp_path):
        assert self._run(tmp_path).returncode == 1

    def test_no_virtualenv_label(self, tmp_path):
        assert "no virtualenv active" in self._run(tmp_path).stdout

    def test_tool_labels_absent(self, tmp_path):
        result = self._run(tmp_path)
        assert "ruff not found" not in result.stdout
        assert "pmpython not on PATH" not in result.stdout
        assert "cpmapi not importable" not in result.stdout
        assert "pcp.pmi not importable" not in result.stdout


class TestAutoActivation:
    """When .venv/bin/activate exists and no VIRTUAL_ENV is set, pre-commit
    should auto-source the venv — no manual activation step required."""

    def _run(self, tmp_path):
        env, bin_dir = base_env(tmp_path)
        for tool in ("ruff", "mypy", "pytest", "pmpython"):
            make_stub(bin_dir, tool)
        make_python3_stub(bin_dir, cpmapi_ok=True, pcp_pmi_ok=True)
        # Script copy lives in tmp_path so SCRIPT_DIR = tmp_path.
        # check_man_page looks for $SCRIPT_DIR/man/pmlogsynth.1 — provide a stub.
        man_dir = tmp_path / "man"
        man_dir.mkdir()
        (man_dir / "pmlogsynth.1").write_text(".TH STUB 1\n.SH NAME\nstub\n")

        # No VIRTUAL_ENV — but a .venv with a working activate script IS present
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        activate = venv_bin / "activate"
        activate.write_text(
            f'export VIRTUAL_ENV="{tmp_path / ".venv"}"\n'
            f'export PATH="{venv_bin}:$PATH"\n'
        )
        return run_script(env, script=make_script_copy(tmp_path))

    def test_no_venv_error_when_venv_dir_present(self, tmp_path):
        assert "no virtualenv active" not in self._run(tmp_path).stdout

    def test_summary_shown_after_auto_activation(self, tmp_path):
        assert "pre-commit passed" in self._run(tmp_path).stdout


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

    def test_summary_shown_on_success(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "pre-commit passed" in result.stdout


class TestSummaryOutput:
    """Default mode: clean summary with ✓ lines, no tool banner noise."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path)
        env["VIRTUAL_ENV"] = str(tmp_path / ".venv")
        for tool in ("ruff", "mypy", "pytest", "pmpython"):
            make_stub(bin_dir, tool)
        make_python3_stub(bin_dir, cpmapi_ok=True, pcp_pmi_ok=True)
        return env

    def test_summary_header_present(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "pre-commit passed" in result.stdout

    def test_summary_includes_man_page(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "✓ man page" in result.stdout

    def test_summary_includes_ruff(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "✓ ruff" in result.stdout

    def test_summary_includes_mypy(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "✓ mypy" in result.stdout

    def test_summary_includes_tests(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "✓ unit + integration tests" in result.stdout

    def test_progress_indicator_shown(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "→ ruff" in result.stdout
        assert "→ mypy" in result.stdout

    def test_no_tool_banner_noise(self, tmp_path):
        result = run_script(self._build_env(tmp_path))
        assert "=== ruff check ===" not in result.stdout
        assert "=== mypy ===" not in result.stdout


class TestQuietMode:
    """-q flag: no stdout on success, just exit code."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path)
        env["VIRTUAL_ENV"] = str(tmp_path / ".venv")
        for tool in ("ruff", "mypy", "pytest", "pmpython"):
            make_stub(bin_dir, tool)
        make_python3_stub(bin_dir, cpmapi_ok=True, pcp_pmi_ok=True)
        return env

    def test_exits_zero_on_success(self, tmp_path):
        result = run_script(self._build_env(tmp_path), args=["-q"])
        assert result.returncode == 0

    def test_no_stdout_on_success(self, tmp_path):
        result = run_script(self._build_env(tmp_path), args=["-q"])
        assert result.stdout == ""
