# Contract: E2E Test Suite

**Feature**: 002-phase2-e2e-docs
**Date**: 2026-03-02

This document specifies the observable contract of the E2E test suite — what it
asserts, what it skips, and what it must never do. It is the ground truth for
test implementation review.

---

## Skip Contract

All E2E tests MUST use the `pcp_available` session fixture from `tests/conftest.py`.

```python
@pytest.mark.e2e
def test_something(pcp_available: bool) -> None:
    ...  # only reached when pcp.pmi is importable
```

When `pcp.pmi` is not importable, `pytest.skip("WARNING: PCP library not available")` is
raised by the fixture before the test body runs. This produces a visible `s` in the output
(never a silent pass). Matches constitution Principle II.

---

## Archive Integrity Contract

`test_archive_roundtrip` must assert all three:

| Tool | Command form | Assertion |
|------|-------------|-----------|
| `pmlogcheck` | `pmlogcheck <archive_base>` | return code == 0 |
| `pmval` | `pmval -a <archive_base> kernel.all.load` | return code == 0 |
| `pmrep` | `pmrep -a <archive_base> kernel.all.load` | return code == 0 |

If any tool is not in PATH, the subprocess call raises `FileNotFoundError` — the test
fails (not skips) with a descriptive message.

---

## Validation Contract

`test_validate_accepts_good_profiles` — parametrized over:
- `tests/fixtures/profiles/good-baseline.yaml` (with `-C tests/fixtures/profiles/`)
- `tests/fixtures/workload-linear-ramp.yaml` (with `-C tests/fixtures/profiles/`)

Each invokes:
```
pmlogsynth --validate -C <hw_dir> <profile>
```
Asserts: return code == 0.

`test_validate_rejects_bad_profiles` — parametrized over:
- `tests/fixtures/profiles/bad-ratio.yaml`
- `tests/fixtures/profiles/bad-duration.yaml`
- `tests/fixtures/profiles/bad-noise.yaml`

Each invokes:
```
pmlogsynth --validate -C <hw_dir> <profile>
```
Asserts: return code == 1 AND stderr is non-empty.

---

## Quickstart Workflow Contract

`test_quickstart_workflow` must run these steps **in order** as subprocesses:

```
1. pmlogsynth --validate -C <hw_dir> <good_profile>  → rc == 0
2. pmlogsynth -C <hw_dir> -o <tmpdir>/archive <good_profile>  → rc == 0
3. pmlogcheck <tmpdir>/archive  → rc == 0
4. pmval -a <tmpdir>/archive kernel.all.load  → rc == 0
```

The temporary output directory is created via `tempfile.mkdtemp()` and cleaned up in a
`finally` block (or via `pytest` `tmp_path` fixture). FR-007 compliance.

---

## Archive Isolation Contract

Each test that writes an archive MUST write to an isolated directory. Tests MUST NOT
share archive paths. Archive files MUST be deleted on test completion (pass or fail).

Recommended implementation: `tmp_path` pytest fixture (stdlib, no dependencies).

---

## CLI Invocation Contract

All subprocesses invoke the CLI via `sys.executable + ["-m", "pmlogsynth", ...]` to
guarantee the same Python interpreter as the test process. Never invoke a bare `pmlogsynth`
binary — it may resolve to a different installation.

```python
import subprocess, sys

result = subprocess.run(
    [sys.executable, "-m", "pmlogsynth", "--validate", profile],
    capture_output=True,
    text=True,
)
```
