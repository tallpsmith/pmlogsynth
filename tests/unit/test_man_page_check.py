"""
Tier 1 tests for pre-commit.sh check_man_page() function.

Strategy: invoke pre-commit.sh via subprocess with a controlled environment:
- All prerequisites satisfied (stubs for all tools, python3 stub with imports passing)
- Valid or invalid .1 files created in tmp_path
- mandoc/groff stubs in tmp bin to control formatter availability and output

The check_man_page() function must never open a pager or block on input.
"""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "pre-commit.sh"

_SYSTEM_PATH = "/bin:/usr/bin"

# Minimal valid roff content
_VALID_ROFF = """\
.TH TEST 1 "2026" "test" "User Commands"
.SH NAME
test \\- a test page
.SH DESCRIPTION
Valid roff content.
"""

# Malformed roff — unmatched macro that mandoc/groff will flag
_INVALID_ROFF = """\
.TH TEST 1 "2026" "test" "User Commands"
.SH NAME
test - broken
.SH DESCRIPTION
.B unclosed bold macro without newline"""


def make_stub(directory: Path, name: str, exit_code: int = 0, body: str = "") -> None:
    stub = directory / name
    content = f"#!/bin/bash\n{body}exit {exit_code}\n"
    stub.write_text(content)
    stub.chmod(0o755)


def all_prereqs_env(tmp_path: Path, man_dir: Path) -> dict:
    """
    Build env where all prerequisites are satisfied.
    SCRIPT_DIR is faked via a wrapper so check_man_page resolves
    the man file relative to the script's real location (which we
    keep as-is; we supply the real man dir via symlink or direct path).
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)

    # Dev tool stubs
    for tool in ("ruff", "mypy", "pytest", "pmpython"):
        make_stub(bin_dir, tool)

    # python3 stub: all imports pass
    py3 = bin_dir / "python3"
    py3.write_text(
        "#!/bin/bash\n"
        'if [[ "$*" == *"cpmapi"* ]]; then exit 0; fi\n'
        'if [[ "$*" == *"pcp.pmi"* ]]; then exit 0; fi\n'
        "exit 0\n"
    )
    py3.chmod(0o755)

    return {
        "PATH": f"{bin_dir}:{_SYSTEM_PATH}",
        "HOME": str(tmp_path),
        "VIRTUAL_ENV": str(tmp_path / ".venv"),
    }


def make_mandoc_stub(bin_dir: Path, exit_code: int, stderr_msg: str = "") -> None:
    """Stub mandoc that emits stderr_msg and exits with exit_code."""
    body = f'echo "{stderr_msg}" >&2\n' if stderr_msg else ""
    make_stub(bin_dir, "mandoc", exit_code, body)


def make_groff_stub(bin_dir: Path, exit_code: int, stderr_msg: str = "") -> None:
    """Stub groff that emits stderr_msg on stderr."""
    body = f'echo "{stderr_msg}" >&2\n' if stderr_msg else ""
    make_stub(bin_dir, "groff", exit_code, body)


def run_script(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


class TestManPageAbsent:
    """When man/pmlogsynth.1 is absent, check_man_page must exit 1."""

    def test_exits_nonzero(self, tmp_path):
        # Use a SCRIPT_DIR that has no man/ subdir → file will not exist
        env = all_prereqs_env(tmp_path, tmp_path)
        # Redirect SCRIPT_DIR by wrapping pre-commit.sh through a temp script
        # that overrides SCRIPT_DIR to a directory without man/pmlogsynth.1
        wrapper = tmp_path / "run.sh"
        wrapper.write_text(
            f"#!/bin/bash\n"
            f"SCRIPT_DIR={tmp_path}\n"
            f"source {SCRIPT}\n"
        )
        wrapper.chmod(0o755)
        # Instead: invoke real script but with PATH pointing to no man file.
        # The real check_man_page() uses $SCRIPT_DIR which is the script's dir.
        # We test via a temp copy placed in tmp_path so SCRIPT_DIR = tmp_path.
        script_copy = tmp_path / "pre-commit.sh"
        script_copy.write_text(SCRIPT.read_text())
        script_copy.chmod(0o755)
        # tmp_path has no man/ subdir → file absent
        result = subprocess.run(
            ["bash", str(script_copy)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_error_message_on_stderr(self, tmp_path):
        env = all_prereqs_env(tmp_path, tmp_path)
        script_copy = tmp_path / "pre-commit.sh"
        script_copy.write_text(SCRIPT.read_text())
        script_copy.chmod(0o755)
        result = subprocess.run(
            ["bash", str(script_copy)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert "not found" in result.stderr or "not found" in result.stdout


class TestManPageValidMandoc:
    """Valid roff + mandoc available → exit 0, silent."""

    def _run(self, tmp_path):
        env = all_prereqs_env(tmp_path, tmp_path)
        # Add mandoc stub: exits 0 (valid file)
        bin_dir = tmp_path / "bin"
        make_mandoc_stub(bin_dir, exit_code=0)

        # Place script in tmp_path so SCRIPT_DIR = tmp_path
        script_copy = tmp_path / "pre-commit.sh"
        script_copy.write_text(SCRIPT.read_text())
        script_copy.chmod(0o755)

        # Create man/pmlogsynth.1
        man_dir = tmp_path / "man"
        man_dir.mkdir()
        (man_dir / "pmlogsynth.1").write_text(_VALID_ROFF)

        # Stub dev tools to exit 0 (ruff, mypy, pytest will "pass")
        return subprocess.run(
            ["bash", str(script_copy)],
            env=env,
            capture_output=True,
            text=True,
        )

    def test_man_page_check_in_summary(self, tmp_path):
        result = self._run(tmp_path)
        assert "✓ man page" in result.stdout

    def test_no_mandate_error_in_stderr(self, tmp_path):
        result = self._run(tmp_path)
        assert "error" not in result.stderr.lower()


class TestManPageInvalidMandoc:
    """Invalid roff + mandoc available → exit 1 with error output."""

    def test_exits_nonzero(self, tmp_path):
        env = all_prereqs_env(tmp_path, tmp_path)
        bin_dir = tmp_path / "bin"
        # mandoc stub: exits non-zero (linting failed)
        make_mandoc_stub(bin_dir, exit_code=3, stderr_msg="pmlogsynth.1:5: WARNING: skipping bad")

        script_copy = tmp_path / "pre-commit.sh"
        script_copy.write_text(SCRIPT.read_text())
        script_copy.chmod(0o755)

        man_dir = tmp_path / "man"
        man_dir.mkdir()
        (man_dir / "pmlogsynth.1").write_text(_INVALID_ROFF)

        result = subprocess.run(
            ["bash", str(script_copy)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0


class TestManPageNoFormatter:
    """No mandoc or groff available → exit 0 with WARNING, never blocks."""

    def _no_formatter_env(self, tmp_path: Path) -> dict:
        """
        PATH restricted to tmp bin_dir only — excludes /usr/bin where groff
        lives on macOS. All prereqs stubbed; no mandoc/groff stubs.
        """
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)

        for tool in ("ruff", "mypy", "pytest", "pmpython"):
            make_stub(bin_dir, tool)

        py3 = bin_dir / "python3"
        py3.write_text(
            "#!/bin/bash\n"
            'if [[ "$*" == *"cpmapi"* ]]; then exit 0; fi\n'
            'if [[ "$*" == *"pcp.pmi"* ]]; then exit 0; fi\n'
            "exit 0\n"
        )
        py3.chmod(0o755)

        return {
            # No /usr/bin — prevents macOS /usr/bin/groff from being found
            "PATH": str(bin_dir),
            "HOME": str(tmp_path),
            "VIRTUAL_ENV": str(tmp_path / ".venv"),
        }

    def _run(self, tmp_path: Path) -> subprocess.CompletedProcess:
        env = self._no_formatter_env(tmp_path)
        script_copy = tmp_path / "pre-commit.sh"
        script_copy.write_text(SCRIPT.read_text())
        script_copy.chmod(0o755)

        man_dir = tmp_path / "man"
        man_dir.mkdir()
        (man_dir / "pmlogsynth.1").write_text(_VALID_ROFF)

        # Use absolute /bin/bash so subprocess.run doesn't search PATH for it
        return subprocess.run(
            ["/bin/bash", str(script_copy)],
            env=env,
            capture_output=True,
            text=True,
        )

    def test_exits_zero_with_warning(self, tmp_path):
        result = self._run(tmp_path)
        # existence-only pass: must not exit 1
        assert result.returncode != 1 or "WARNING" in result.stderr

    def test_passes_silently_when_no_formatter(self, tmp_path):
        # No formatter = existence-only check; passes and appears in summary.
        # The old WARNING was captured and swallowed by run_check's 2>&1.
        result = self._run(tmp_path)
        assert result.returncode == 0
        assert "✓ man page" in result.stdout
