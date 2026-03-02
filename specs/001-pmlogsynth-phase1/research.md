# Research: pmlogsynth Phase 1

**Branch**: `001-pmlogsynth-phase1` | **Date**: 2026-03-01
**Status**: All NEEDS CLARIFICATION items resolved.

---

## 1. PCP Python Archive Writing API

### Decision
Use `pcp.pmi.pmiLogImport` (the `pmiLogImport` class from the `python3-pcp` system package)
to write PCP v3 archives. Do not use the C `libpcp_import` API directly.

### Rationale
The Python bindings are the established high-level interface for programmatic archive
creation. They handle the binary format details, endianness, and v3 record structure
internally. Using the Python layer keeps the codebase pure Python and avoids ctypes
complexity.

### Alternatives considered
- Direct ctypes calls to `libpcp_import.so`: too low-level, fragile across PCP versions
- Subprocess calls to `pmlc`/`pmlogger`: requires a running pmcd, violates FR-003

### API Summary

```python
from pcp import pmi

# Create and open an archive
log = pmi.pmiLogImport(archive_path)          # opens .0/.index/.meta files
log.pmiSetHostname("synthetic-host")
log.pmiSetTimezone("UTC")

# Register metrics (must be done before first pmiWrite)
# pmiID(domain, cluster, item) — domain 60 is kernel PMDA
pmid = pmi.pmiID(60, 0, 0)  # kernel.all.cpu.user
indom = pmi.pmiInDom(60, 0)  # per-CPU indom
log.pmiAddMetric("kernel.all.cpu.user", pmid,
                 pmi.PM_TYPE_U64,   # cumulative counter
                 pmi.PM_INDOM_NULL, # aggregate (not per-instance)
                 pmi.PM_SEM_COUNTER,
                 pmi.pmiUnits(0, 1, 0, 0, pmi.PM_TIME_MSEC, 0))  # milliseconds

# Register instances (for per-CPU, per-disk, per-NIC metrics)
log.pmiAddInstance(indom, "cpu0", 0)
log.pmiAddInstance(indom, "cpu1", 1)

# Set values for the next sample
log.pmiPutValue("kernel.all.cpu.user", None, str(value_ms))
log.pmiPutValue("kernel.percpu.cpu.user", "cpu0", str(cpu0_ms))

# Write one sample at a given timestamp
log.pmiWrite(int(timestamp_sec), 0)  # second arg is microseconds

# Finalize
del log  # destructor calls pmiEnd() and closes files
```

### PCP Archive v3 vs v2
- v3 uses nanosecond timestamps (v2 uses microseconds)
- v3 supports larger archives (>2GB data volumes)
- `pmiLogImport` creates v3 by default when available; no explicit version flag needed in
  the Python API — the version is determined by the PCP library's compile-time default
- `pmlogcheck` validates both formats; v3 is the current standard

### Key PMIDs for supported metric domains

| Metric | Domain | Cluster | Item | Type | Sem | Units |
|--------|--------|---------|------|------|-----|-------|
| `kernel.all.cpu.user` | 60 | 0 | 20 | U64 | counter | msec |
| `kernel.all.cpu.sys` | 60 | 0 | 22 | U64 | counter | msec |
| `kernel.all.cpu.idle` | 60 | 0 | 21 | U64 | counter | msec |
| `kernel.all.cpu.wait.total` | 60 | 0 | 35 | U64 | counter | msec |
| `kernel.all.cpu.steal` | 60 | 0 | 58 | U64 | counter | msec |
| `kernel.percpu.cpu.user` | 60 | 10 | 20 | U64 | counter | msec |
| `kernel.percpu.cpu.sys` | 60 | 10 | 22 | U64 | counter | msec |
| `kernel.percpu.cpu.idle` | 60 | 10 | 21 | U64 | counter | msec |
| `kernel.all.load` | 60 | 2 | 0 | FLOAT | instant | none |
| `mem.util.used` | 58 | 0 | 6 | U64 | instant | kbyte |
| `mem.util.free` | 58 | 0 | 2 | U64 | instant | kbyte |
| `mem.util.cached` | 58 | 0 | 13 | U64 | instant | kbyte |
| `mem.util.bufmem` | 58 | 0 | 4 | U64 | instant | kbyte |
| `mem.physmem` | 58 | 0 | 0 | U64 | discrete | kbyte |
| `disk.all.read_bytes` | 60 | 4 | 5 | U64 | counter | kbyte |
| `disk.all.write_bytes` | 60 | 4 | 6 | U64 | counter | kbyte |
| `disk.all.read` | 60 | 4 | 0 | U64 | counter | count |
| `disk.all.write` | 60 | 4 | 1 | U64 | counter | count |
| `disk.dev.read_bytes` | 60 | 5 | 5 | U64 | counter | kbyte |
| `disk.dev.write_bytes` | 60 | 5 | 6 | U64 | counter | kbyte |
| `network.interface.in.bytes` | 60 | 3 | 3 | U64 | counter | byte |
| `network.interface.out.bytes` | 60 | 3 | 11 | U64 | counter | byte |
| `network.interface.in.packets` | 60 | 3 | 0 | U64 | counter | count |
| `network.interface.out.packets` | 60 | 3 | 8 | U64 | counter | count |

> **Implementation note**: PMIDs must be verified against the PCP installation using
> `pminfo -d <metric>` before writing tests. The cluster/item values above are reference
> values from the Linux kernel PMDA; the writer.py module MUST use symbolic names
> (`pmiID`) rather than hardcoded integers where the Python API permits. Where PMIDs must
> be hardcoded, they MUST be documented with a comment citing the source PMDA.

### Instance Domains

| InDom | Serial | Instances |
|-------|--------|-----------|
| Per-CPU | `pmiInDom(60, 0)` | `"cpu0"`, `"cpu1"`, ... (from hardware profile) |
| Per-disk | `pmiInDom(60, 1)` | `"sda"`, `"nvme0n1"`, ... (from hardware profile) |
| Per-NIC | `pmiInDom(60, 2)` | `"eth0"`, `"bond0"`, ... (from hardware profile) |
| Load avg | `PM_INDOM_NULL` | `"1 minute"`, `"5 minute"`, `"15 minute"` |

### Counter Accumulation Strategy
Counter metrics (CPU ticks, disk bytes, network bytes) MUST accumulate from zero at
archive start. `ValueSampler` maintains running totals across samples. At each tick:

```
counter_total += interval_delta
pmiPutValue(metric, instance, str(counter_total))
```

Interval delta = (target_rate × interval_seconds), after Gaussian noise, clamped to ≥ 0.

---

## 2. GitHub Actions CI Setup

### Decision
Two jobs in a single workflow:
1. **`quality`**: matrix Python 3.8 + latest on ubuntu-latest; linting, type checking,
   Tier 1, Tier 2
2. **`e2e`**: single job on ubuntu-latest with apt PCP + system Python; Tier 3

### Rationale
The `python3-pcp` apt package links against the system Python (Python 3.12 on ubuntu-24.04
as of 2026). Tier 3 must run with exactly that interpreter. Using `actions/setup-python`
for Tier 3 would cause a Python version mismatch with the PCP C extensions.

### Alternatives considered
- Single job with both matrix and E2E: impossible — E2E cannot use setup-python
- Docker container with custom PCP build: overkill; apt packages are sufficient

### Workflow Structure

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: ['**']
  pull_request:
    branches: [main]

jobs:
  quality:
    name: "Quality (${{ matrix.python-version }})"
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.x']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy pmlogsynth/
      - run: pytest tests/tier1/ tests/tier2/ -v

  e2e:
    name: "E2E (system Python + PCP)"
    runs-on: ubuntu-latest
    needs: quality
    steps:
      - uses: actions/checkout@v4
      - name: Install PCP
        run: |
          sudo apt-get update
          sudo apt-get install -y pcp python3-pcp
      - name: Install pmlogsynth (system Python)
        run: python3 -m pip install -e .
      - name: Run E2E tests
        run: python3 -m pytest tests/tier3/ -v
```

### PCP apt packages (ubuntu-24.04 / ubuntu-latest 2026)
- `pcp` — installs `pmlogger`, `pmval`, `pmlogcheck`, `pmlc`, and `libpcp_import.so`
- `python3-pcp` — provides `pcp.pmi`, `pcp.pmapi`, `pcp.pmcc` Python modules
- Both are required; `python3-pcp` has a hard dependency on `pcp`

---

## 3. Python Packaging

### Decision
Use `pyproject.toml` with `setuptools` as the build backend. Use
`pathlib.Path(__file__).parent / "profiles"` for locating bundled hardware profile YAML
files (avoids `importlib.resources` Python 3.8 API incompatibilities).

### Rationale
`pyproject.toml` (PEP 517/518) is the modern standard. setuptools is the most compatible
backend for `pip install -e .` workflows. The `pathlib`-relative approach for package data
works reliably in both installed and editable modes on Python 3.8+.

### Alternatives considered
- `hatchling`: cleaner but less universal `pip install -e .` support in some edge cases
- `importlib.resources.files()`: only available in Python 3.9+; backport adds a dependency
- `pkg_resources`: deprecated in setuptools 67+

### pyproject.toml skeleton

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "pmlogsynth"
version = "0.1.0"
requires-python = ">=3.8"
dependencies = ["PyYAML>=5.1"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff>=0.3", "mypy>=1.0"]
ai  = ["anthropic>=0.20.0"]

[project.scripts]
pmlogsynth = "pmlogsynth.cli:main"

[tool.setuptools.package-data]
pmlogsynth = ["profiles/*.yaml"]

[tool.ruff]
target-version = "py38"
select = ["E", "W", "F", "I"]

[tool.mypy]
python_version = "3.8"
strict = true
ignore_missing_imports = true   # pcp.pmi has no type stubs

[tool.pytest.ini_options]
markers = [
  "tier1: unit tests, no PCP required",
  "tier2: integration tests, PCP mocked",
  "tier3: E2E tests, real PCP required",
]
```

---

## 4. Static Analysis Tool Choices

### Linting: ruff
**Decision**: ruff with rules E, W, F, I (pycodestyle + pyflakes + isort).
**Rationale**: Covers all flake8 rules plus import sorting in a single fast tool.
  Python 3.8 compatible output. Config in `pyproject.toml`.
**Alternative**: flake8 + isort — two tools, slower, separate config.

### Type Checking: mypy (strict mode)
**Decision**: mypy with `--strict` and `ignore_missing_imports = true`.
**Rationale**: Best Python 3.8 compatibility track record. Strict mode catches Optional
  handling errors that matter for the Phase 3 overlay merge logic (FR-020 / D-003).
  `ignore_missing_imports` needed because `pcp.pmi` has no published type stubs.
**Alternative**: pyright — faster but less established for CI in Python 3.8 projects.

---

## 5. Test Tier Detection

### Decision
Use a pytest `conftest.py` session-scoped fixture that attempts `import pcp.pmi` and
stores the result. All Tier 3 tests use a `pcp_available` fixture that calls
`pytest.skip()` if the import failed. A session-level warning is printed when Tier 3 is
skipped.

### Implementation

```python
# tests/conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "tier3: requires pcp.pmi")

@pytest.fixture(scope="session")
def pcp_available():
    try:
        import pcp.pmi  # noqa: F401
        return True
    except ImportError:
        pytest.skip(
            "WARNING: PCP library not available — E2E tests skipped",
            allow_module_level=False,
        )
        return False  # unreachable, but satisfies type checker
```

Tier 3 tests use `@pytest.mark.tier3` and declare `pcp_available` as a fixture parameter.

---

## 6. Gaussian Noise and Counter Safety

### Decision
Apply noise as a multiplicative factor using `random.gauss(mean=1.0, sigma=noise_factor)`,
then clamp the result so counter increments are never negative.

```python
def apply_noise(base_value: float, noise: float, rng: random.Random) -> float:
    if noise == 0.0:
        return base_value
    noisy = base_value * rng.gauss(1.0, noise)
    return max(0.0, noisy)
```

Counter deltas are computed from the noisy rate and clamped to ≥ 0 before accumulation.
This satisfies FR-013 and avoids pmlogcheck failing on negative counter increments.

### Rationale
Multiplicative noise keeps values proportional to the stressor target. Additive noise
would cause problems at low values (e.g., 0% CPU idle + noise → negative).

---

## 7. Load Average Computation

### Decision
Simulate UNIX exponential moving average using the standard decay constants:
- 1-min: `exp(-interval/60)`
- 5-min: `exp(-interval/300)`
- 15-min: `exp(-interval/900)`

```python
load_raw = utilization * num_cpus
alpha_1  = math.exp(-interval / 60)
alpha_5  = math.exp(-interval / 300)
alpha_15 = math.exp(-interval / 900)
load_1  = alpha_1  * prev_load_1  + (1 - alpha_1)  * load_raw
load_5  = alpha_5  * prev_load_5  + (1 - alpha_5)  * load_raw
load_15 = alpha_15 * prev_load_15 + (1 - alpha_15) * load_raw
```

Initial load values are 0.0. This satisfies FR-011.

---

## 8. Summary: All Decisions Made

| Area | Decision | Status |
|------|----------|--------|
| Archive writing | `pcp.pmi.pmiLogImport` Python class | Resolved |
| Archive version | v3 (library default) | Resolved |
| PCP metric IDs | Reference table above; verify with `pminfo -d` | Resolved |
| Counter accumulation | Running total + noise clamped ≥ 0 | Resolved |
| GitHub Actions CI | Two jobs: quality matrix + E2E system Python | Resolved |
| PCP apt packages | `pcp` + `python3-pcp` | Resolved |
| Packaging | pyproject.toml + setuptools + pathlib profiles | Resolved |
| Linting | ruff (E, W, F, I rules) | Resolved |
| Type checking | mypy strict | Resolved |
| Tier 3 detection | `import pcp.pmi` in conftest.py | Resolved |
| Noise application | Multiplicative Gaussian, clamped ≥ 0 | Resolved |
| Load average | UNIX EMA with standard decay constants | Resolved |
