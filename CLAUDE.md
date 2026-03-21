# pmlogsynth Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-01

## Active Technologies
- Bash (pre-commit.sh); Markdown (README.md); Python 3.8+ (new unit tests) + mandoc (system package; apt/brew) for man page validation; groff as (003-dx-improvements)
- Python 3.8+ + `pcp.pmi` (system package `python3-pcp`), PyYAML (004-pmrep-view-support)
- PCP v3 binary archive files (004-pmrep-view-support)
- Python 3.8+ + PyYAML, `pcp.pmapi` (system `python3-pcp`) — existing hard dependency (006-relative-starttime)
- N/A — tool generates PCP binary archive files (006-relative-starttime)

- **Language**: Python 3.8+ (minimum); system Python tested in CI with PCP installed
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
├── fleet.py                # fleet profile loader, host assignment, orchestrator, manifest
├── jitter.py               # per-host stressor jitter (pure functions, no mutation)
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

.github/workflows/ci.yml    # quality (system Python + PCP) + E2E job
pre-commit.sh               # local quality gate (lint + types + Tier 1 + Tier 2)
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

# Fleet mode
pmlogsynth fleet fleet-profile.yml --dry-run
pmlogsynth fleet fleet-profile.yml -o ./generated-archives/my-fleet
```

## Key Invariants

- **PCP is a hard dependency**: `python3-pcp` must be installed.
  `pcp_constants.py` imports type/sem/unit constants directly from `cpmapi`.
  Domain modules and tests import from `pcp_constants`, never from `cpmapi` directly.
- **PCP archive writing isolated in `writer.py`**: only `writer.py` imports `pcp.pmi`
- **Stressor defaults applied at compute time**: `MetricModel.compute()` applies defaults,
  NOT `ProfileLoader`. Parsed stressor fields are `Optional` — `None` ≠ default value.
- **Counter increments clamped ≥ 0**: noise must never produce negative counter deltas
- **`ProfileLoader.from_file` delegates to `from_string`**: always
- **CLI uses argparse subparsers**: `fleet` and `generate` are implemented subcommands

## Code Style

- Python 3.8 compatible syntax throughout (no walrus operator, no `match`, no `|` unions)
- ruff handles formatting/import sorting — run before committing
- mypy strict — all `Optional` types must be handled explicitly
- No NumPy — use `random.gauss` from stdlib

## Recent Changes
- 006-relative-starttime: Added Python 3.8+ + PyYAML, `pcp.pmapi` (system `python3-pcp`) — existing hard dependency
- 004-pmrep-view-support: Added Python 3.8+ + `pcp.pmi` (system package `python3-pcp`), PyYAML
- 003-dx-improvements: Added Bash (pre-commit.sh); Markdown (README.md); Python 3.8+ (new unit tests) + mandoc (system package; apt/brew) for man page validation; groff as

  PyYAML + pcp.pmi, three-tier test strategy, CI-first delivery

<!-- MANUAL ADDITIONS START -->
## PCP Metric PMIDs — Aligned With Linux PMDA

**All pmlogsynth PMIDs now match the real Linux PMDA assignments.** Domain 60 is used
throughout (the invented domain 58 has been eliminated). Metric names also match
(e.g. `disk.dev.aveq`, not `disk.dev.avg_qlen`).

**macOS `pminfo` is useless for verifying Linux PMIDs.** macOS PCP uses domain 78 for
nearly everything. Always verify against the Linux PMDA source.

**Authoritative source for Linux PMIDs:**
`https://github.com/performancecopilot/pcp` → `src/pmdas/linux/pmda.c`

Key cluster definitions (from `src/pmdas/linux/linux.h`):
- `CLUSTER_STAT = 0` — `/proc/stat` (cpu, disk, scheduler, swap page counters)
- `CLUSTER_MEMINFO = 1` — `/proc/meminfo` (mem.util.*, swap.used, mem.physmem, hinv.physmem)
- `CLUSTER_LOADAVG = 2` — `/proc/loadavg`
- `CLUSTER_NET_DEV = 3` — `/proc/net/dev` (network.interface.*, hinv.ninterface)
- `CLUSTER_KERNEL_UNAME = 12` — `uname()` (kernel.uname.*)
- `CLUSTER_VMSTAT = 28` — `/proc/vmstat` (mem.vmstat.pgpgin etc.)
- `CLUSTER_NET_ALL = 90` — network.all.* aggregates

**Convention for new metrics:** look up the real Linux PMDA assignment in `pmda.c`
and use the exact (domain, cluster, item) tuple. All pmlogsynth metrics should match
real Linux hosts. If the item number cannot be determined from source (e.g. vmstat
fields with dynamic ordering), use a reasonable convention and document it.

**Linux verification command** (run on CI or a Linux box with PCP installed):
```bash
pminfo -md kernel.all.cpu.vuser kernel.all.intr hinv.ncpu swap.used disk.dev.read
```


## Workflow — MANDATORY

**Run `./pre-commit.sh` before every commit and push.** It is the single gate
that mirrors CI exactly: mandoc lint, ruff, mypy, unit + integration tests,
and E2E tests when PCP is available.

**MANDATORY for Claude:** When asked to "commit and push" (or any variant), ALWAYS
run `./pre-commit.sh` first and confirm it is green before pushing. No pre-commit, no push.

First-time setup (macOS):
```bash
./setup-venv.sh        # creates .venv with the correct PCP-linked Python
./pre-commit.sh        # auto-activates the venv; run quality gate
```

Never commit without a green `./pre-commit.sh`.

## Archive Output Convention

All locally generated PCP archives go in `generated-archives/` (gitignored).
Never generate archives to the project root or ad-hoc paths.

```bash
pmlogsynth -o ./generated-archives/spike docs/spike.yml
pmstat -a ./generated-archives/spike
```

See `docs/pcp-tools.md` for the full PCP toolkit reference and validation workflow.

## Example Profile Files

`docs/spike.yml` and `docs/complete-example.yml` are the canonical example profiles.

**Invariant**: the inline YAML block in `README.md` Quick Start (step 1) must always
match `docs/spike.yml` exactly. If one changes, update the other.

## Developer Experience Docs — MANDATORY

**`man/pmlogsynth.1`, `README.md`, `CONTRIBUTING.md`, and `docs/profile-format.md`
form the developer experience quad.** Before completing any feature or bug fix, ask:
"Does this touch the CLI surface, YAML schema, user workflow, or contributor setup?"
If yes, update all relevant docs:

- **`man/pmlogsynth.1`** — CLI flags, subcommands, YAML schema, exit codes, file paths.
  Authoritative CLI reference.
- **`docs/profile-format.md`** — Full YAML schema: every field, type, default, constraint,
  and accepted format. **Must be updated whenever the profile schema changes** — new fields,
  changed types, new accepted formats (e.g. duration strings, relative timestamps). Also
  fed to AI agents via `--show-schema`, so accuracy is critical.
- **`README.md`** — Quick Start steps, bundled hardware profiles table, metrics count
  (keep in sync with `len(_ALL_METRIC_NAMES)`), any new user-facing capabilities.
- **`CONTRIBUTING.md`** — dev setup steps, test tier table, PR conventions.

**Specific invariants to check on every schema-touching PR:**
- `docs/profile-format.md` field table types match what `parse_duration` / `_parse_meta` actually accept
- `meta.start` section covers both absolute and relative forms
- Metric count in `README.md` matches `len(_ALL_METRIC_NAMES)` in `cli.py`
- Man page duration descriptions match accepted string forms
- Man page EXAMPLES section includes an example for any newly supported input form

New user-facing tools (e.g. Claude skills, new informational flags) must appear in
`README.md`. New dev workflow requirements (e.g. new quality gate steps) must appear in
`CONTRIBUTING.md`.
<!-- MANUAL ADDITIONS END -->
