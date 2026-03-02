# Contributing

## Dev setup

```bash
git clone https://github.com/tallpsmith/pmlogsynth
cd pmlogsynth
pip install -e ".[dev]"
```

This installs pytest, ruff, mypy, and type stubs. The `pcp.pmi` C extension
must come from your system's PCP package (`python3-pcp` on Debian/Ubuntu,
`python3-pcp` on RHEL/Fedora) — it cannot be installed via pip.

## Local quality gate

Before pushing, run the pre-commit gate — it mirrors CI exactly:

```bash
./pre-commit.sh
```

This runs: man page check, ruff lint, mypy type check, unit tests, integration
tests, and E2E tests (skipped automatically if PCP is not available).

## Test structure

Tests are organised in three tiers, each with a distinct dependency profile:

| Directory | Marker | PCP needed | Purpose |
|-----------|--------|------------|---------|
| `tests/unit/` | `@pytest.mark.unit` | No | Pure logic, no I/O |
| `tests/integration/` | `@pytest.mark.integration` | Mocked | PCP layer stubbed with `unittest.mock` |
| `tests/e2e/` | `@pytest.mark.e2e` | Yes (real) | Full archive generation + PCP tool verification |

Run individual tiers:

```bash
pytest tests/unit/ -v
pytest tests/unit/ tests/integration/ -v
pytest tests/e2e/ -v      # auto-skipped if pcp.pmi unavailable
```

**TDD is mandatory**: write failing tests before implementation. Never delete
existing tests — discuss failures before removing any.

## PR conventions

- One logical change per PR
- Include test coverage for new behaviour
- Run `./pre-commit.sh` and confirm it exits 0 before opening a PR
- Commit messages: concise, focus on *why* not *what*
