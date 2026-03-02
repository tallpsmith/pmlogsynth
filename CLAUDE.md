# pmlogsynth Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-01

## Active Technologies
- Python 3.8+ (minimum); latest stable tested in CI matrix + pytest, pcp.pmi (system package), PyYAML (002-phase2-e2e-docs)
- Temporary directories (via `tempfile.mkdtemp`) for E2E-generated archives; cleaned after each tes (002-phase2-e2e-docs)

- **Language**: Python 3.8+ (minimum); Python 3.8 and latest stable both tested in CI
- **Archive writing**: `pcp.pmi.pmiLogImport` via `python3-pcp` system package
- **Profile parsing**: PyYAML
- **Testing**: pytest; `unittest.mock` (stdlib) for integration PCP stubs
- **Linting**: ruff (rules: E, W, F, I) — `ruff check .`
- **Type checking**: mypy (strict) — `mypy pmlogsynth/`
- **Packaging**: pyproject.toml + setuptools

## Project Structure

```text
pmlogsynth/                 # installable Python package
├── cli.py                  # argparse subparsers, main entry point
├── profile.py              # ProfileLoader (from_file + from_string) + ProfileResolver
├── timeline.py             # phase sequencer, linear interpolation, repeat expansion
├── sampler.py              # ValueSampler: noise, counter accumulation
├── writer.py               # pcp.pmi.pmiLogImport wrapper (isolated PCP dependency)
├── profiles/               # bundled hardware profile YAML files (7 profiles)
└── domains/
    ├── base.py             # MetricModel abstract base
    ├── cpu.py, memory.py, disk.py, network.py, load.py

tests/
├── conftest.py             # test markers, PCP import detection
├── fixtures/profiles/      # test hardware profiles (use with -C flag)
├── unit/                   # unit tests — no PCP needed
├── integration/            # integration tests — PCP mocked
└── e2e/                    # E2E tests — real PCP, conditionally skipped

.github/workflows/ci.yml    # quality matrix (3.8 + latest) + E2E system Python job
pre-commit.sh               # local quality gate (lint + types + unit + integration)
```

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run quality gate locally (same as CI)
./pre-commit.sh

# Run tests by tier
pytest tests/unit/ -v                      # unit tests, no PCP needed
pytest tests/unit/ tests/integration/ -v   # all non-E2E tests
pytest -v                                   # all tiers (E2E auto-skipped if no PCP)

# Individual quality checks
ruff check .
mypy pmlogsynth/

# Use the tool
pmlogsynth --validate profile.yaml
pmlogsynth -o ./out profile.yaml
pmlogsynth --list-profiles
pmlogsynth --list-metrics
```

## Key Invariants

- **PCP library isolated in `writer.py`**: unit and integration tests MUST NOT import from `pcp.*`
- **Stressor defaults applied at compute time**: `MetricModel.compute()` applies defaults,
  NOT `ProfileLoader`. Parsed stressor fields are `Optional` — `None` ≠ default value.
- **Counter increments clamped ≥ 0**: noise must never produce negative counter deltas
- **`ProfileLoader.from_file` delegates to `from_string`**: always
- **CLI uses argparse subparsers**: `fleet` is reserved; do not use as positional arg handling

## Code Style

- Python 3.8 compatible syntax throughout (no walrus operator, no `match`, no `|` unions)
- ruff handles formatting/import sorting — run before committing
- mypy strict — all `Optional` types must be handled explicitly
- No NumPy — use `random.gauss` from stdlib

## Recent Changes
- 002-phase2-e2e-docs: Added Python 3.8+ (minimum); latest stable tested in CI matrix + pytest, pcp.pmi (system package), PyYAML

- 001-pmlogsynth-phase1: Initial project setup — Python 3.8+ CLI tool with
  PyYAML + pcp.pmi, three-tier test strategy, CI-first delivery

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
