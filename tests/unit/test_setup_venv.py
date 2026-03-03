"""
Unit tests for setup-venv.sh.

Strategy: invoke setup-venv.sh via subprocess with a restricted environment.
- PATH contains only a tmp bin dir so no real system tools leak in.
- uname stub controls platform detection.
- pmpython stub echoes the path to our python3 stub (macOS path).
- python3 stub creates a minimal .venv/bin/pip when called with -m venv.
"""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "setup-venv.sh"


def make_uname_stub(directory: Path, platform: str) -> None:
    stub = directory / "uname"
    stub.write_text(f"#!/bin/bash\necho {platform}\n")
    stub.chmod(0o755)


def make_python3_stub(directory: Path, exit_code: int = 0) -> Path:
    """
    Handles -m venv by creating <venv>/bin/pip; all other invocations exit cleanly.
    Returns the stub path so pmpython stubs can point at it.
    """
    stub = directory / "python3"
    stub.write_text(
        "#!/bin/bash\n"
        "if [[ \"$*\" == *\"-m venv\"* ]]; then\n"
        f"  if [ {exit_code} -ne 0 ]; then exit {exit_code}; fi\n"
        "  VENV=\"${!#}\"\n"
        "  mkdir -p \"$VENV/bin\"\n"
        "  printf '#!/bin/bash\\nexit 0\\n' > \"$VENV/bin/pip\"\n"
        "  chmod +x \"$VENV/bin/pip\"\n"
        "fi\n"
        f"exit {exit_code}\n"
    )
    stub.chmod(0o755)
    return stub


def make_pmpython_stub(directory: Path, python_path: Path) -> None:
    """Prints python_path for any invocation — simulates pmpython's sys.executable output."""
    stub = directory / "pmpython"
    stub.write_text(f"#!/bin/bash\necho '{python_path}'\n")
    stub.chmod(0o755)


def run_script(env: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def base_env(tmp_path: Path, platform: str) -> tuple:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_uname_stub(bin_dir, platform)
    env = {"PATH": f"{bin_dir}:/bin:/usr/bin", "HOME": str(tmp_path)}
    return env, bin_dir


class TestMacOSPmpythonMissing:
    """macOS + no pmpython on PATH → exit 1 with actionable error."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path, "Darwin")
        make_python3_stub(bin_dir)
        # no pmpython stub
        return env

    def test_exits_nonzero(self, tmp_path):
        assert run_script(self._build_env(tmp_path), tmp_path).returncode == 1

    def test_error_mentions_pmpython(self, tmp_path):
        result = run_script(self._build_env(tmp_path), tmp_path)
        assert "pmpython" in result.stderr

    def test_error_mentions_brew_install_pcp(self, tmp_path):
        result = run_script(self._build_env(tmp_path), tmp_path)
        assert "brew install pcp" in result.stderr


class TestMacOSSuccess:
    """macOS + pmpython present → venv created, activation hint printed."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path, "Darwin")
        python3_stub = make_python3_stub(bin_dir)
        make_pmpython_stub(bin_dir, python3_stub)
        return env

    def test_exits_zero(self, tmp_path):
        assert run_script(self._build_env(tmp_path), tmp_path).returncode == 0

    def test_activation_hint_shown(self, tmp_path):
        result = run_script(self._build_env(tmp_path), tmp_path)
        assert "source" in result.stdout
        assert ".venv/bin/activate" in result.stdout

    def test_venv_bin_pip_created(self, tmp_path):
        run_script(self._build_env(tmp_path), tmp_path)
        assert (tmp_path / ".venv" / "bin" / "pip").exists()


class TestLinuxSuccess:
    """Linux → venv created via system python3, pmpython not required."""

    def _build_env(self, tmp_path):
        env, bin_dir = base_env(tmp_path, "Linux")
        make_python3_stub(bin_dir)
        # no pmpython stub — should not be needed
        return env

    def test_exits_zero(self, tmp_path):
        assert run_script(self._build_env(tmp_path), tmp_path).returncode == 0

    def test_activation_hint_shown(self, tmp_path):
        result = run_script(self._build_env(tmp_path), tmp_path)
        assert "source" in result.stdout
        assert ".venv/bin/activate" in result.stdout

    def test_venv_bin_pip_created(self, tmp_path):
        run_script(self._build_env(tmp_path), tmp_path)
        assert (tmp_path / ".venv" / "bin" / "pip").exists()


class TestLinuxPython3Fails:
    """Linux + python3 exits nonzero → setup-venv.sh exits nonzero."""

    def test_exits_nonzero(self, tmp_path):
        env, bin_dir = base_env(tmp_path, "Linux")
        make_python3_stub(bin_dir, exit_code=1)
        assert run_script(env, tmp_path).returncode != 0
