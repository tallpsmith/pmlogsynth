# Implementation Plan: pmlogsynth Phase 1 — Synthetic PCP Archive Generator

**Branch**: `001-pmlogsynth-phase1` | **Date**: 2026-03-01 | **Spec**: `specs/001-pmlogsynth-phase1/spec.md`
**Input**: Feature specification from `/specs/001-pmlogsynth-phase1/spec.md`

> **Delivery strategy**: CI workflow is created first so every subsequent push gets
> automated feedback. Implementation phases are sequenced for parallel agent execution
> once the shared foundation is in place.

## Summary

`pmlogsynth` is a Python CLI tool that generates valid PCP v3 archives from a declarative
YAML workload profile. It requires no running `pmcd`, no real hardware, and no root access.
Archives pass `pmlogcheck` and are immediately usable with all standard PCP tooling.

Technical approach: a pure-Python pipeline — `ProfileLoader → MetricModel → ValueSampler
→ pcp.pmi.pmiLogImport` — where each layer is independently testable. The PCP library
dependency is isolated in `writer.py` so Tier 1 and Tier 2 tests can run anywhere.

## Technical Context

**Language/Version**: Python 3.8+ (minimum); 3.8 and latest stable tested in CI matrix
**Primary Dependencies**: PyYAML (profile parsing); `pcp.pmi.pmiLogImport` via `python3-pcp`
  system package (archive writing)
**Storage**: Output files only — three PCP archive files (`.0`, `.index`, `.meta`)
**Testing**: pytest; `unittest.mock` (stdlib) for Tier 2 PCP stubs; three-tier structure
**Target Platform**: Linux primary (CI on ubuntu-latest); macOS (developer, Tier 1/2 only)
**Project Type**: CLI tool + installable Python package (PyPI)
**Performance Goals**: 7-day archive at 60-second intervals (~10,080 samples) without
  memory exhaustion on a standard developer workstation (SC-006)
**Constraints**: No NumPy, no pmcd, no root access, no C compiler; Python 3.8 minimum
**Scale/Scope**: Single-host archives; fixed instance domains for archive lifetime

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | PCP Archive Fidelity | PASS | FR-001/002 require pmlogcheck + all PCP tools; FR-006/007 counter semantics; FR-013 noise clamping |
| II | Layered Testing | PASS | FR-044/045/046 define Tier 1/2/3 exactly; FR-047 -C fixtures; FR-046 import detection not PATH |
| III | Declarative Profile-First | PASS | FR-020 defaults at compute time; D-005 schema frozen; FR-015a overrides: sub-key |
| IV | Phase-Aware Extensibility | PASS | FR-042 from_string(); FR-041 argparse subparsers; FR-043 ValueSampler seed; D-006 ProfileResolver |
| V | Minimal Dependencies | PASS | PyYAML only; NumPy prohibited; no pmcd; no root; stdlib random.gauss |
| VI | CI-First Quality Gates | PASS | FR-056 CI workflow; FR-050 pre-commit.sh; same gates in both |

**Result: ALL GATES PASS. Proceed to Phase 0.**

*Post-design re-check*: All six gates confirmed by design artifacts (research.md,
data-model.md, contracts/). No violations introduced. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-pmlogsynth-phase1/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output
    ├── cli-schema.md              # CLI flags, arguments, exit codes
    ├── profile-schema.md          # YAML workload profile schema
    └── hardware-profile-schema.md # YAML hardware profile schema
```

### Source Code (repository root)

```text
pmlogsynth/                     # repository root
├── pyproject.toml              # package metadata, entry point, ruff/mypy/pytest config
├── README.md
├── pre-commit.sh               # local quality gate (linting + types + Tier 1 + Tier 2)
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions: matrix + E2E jobs
├── man/
│   └── pmlogsynth.1            # man page (groff/troff format)
├── pmlogsynth/                 # installable Python package
│   ├── __init__.py
│   ├── __main__.py             # enables: python -m pmlogsynth
│   ├── cli.py                  # argparse subparsers, entry point
│   ├── profile.py              # ProfileLoader (from_file + from_string) + ProfileResolver
│   ├── timeline.py             # phase sequencer, linear interpolation, repeat expansion
│   ├── sampler.py              # ValueSampler: noise, counter accumulation, type coercion
│   ├── writer.py               # PCP layer: pcp.pmi.pmiLogImport wrapper
│   ├── profiles/               # bundled hardware profiles (package data)
│   │   ├── generic-small.yaml
│   │   ├── generic-medium.yaml
│   │   ├── generic-large.yaml
│   │   ├── generic-xlarge.yaml
│   │   ├── compute-optimized.yaml
│   │   ├── memory-optimized.yaml
│   │   └── storage-optimized.yaml
│   └── domains/
│       ├── __init__.py
│       ├── base.py             # MetricModel abstract base class
│       ├── cpu.py
│       ├── memory.py
│       ├── disk.py
│       ├── network.py
│       └── load.py
└── tests/
    ├── conftest.py             # pytest config: tier markers, PCP detection fixture
    ├── fixtures/
    │   └── profiles/           # test-specific hardware profiles (used with -C)
    │       ├── test-single-cpu.yaml
    │       └── test-multi-disk.yaml
    ├── tier1/                  # Unit tests — no PCP required
    │   ├── test_profile.py
    │   ├── test_timeline.py
    │   ├── test_sampler.py
    │   └── test_domains.py
    ├── tier2/                  # Integration tests — PCP layer mocked
    │   └── test_writer.py
    └── tier3/                  # E2E tests — real PCP required (conditionally skipped)
        └── test_e2e.py
```

**Structure Decision**: Single-project layout. The `domains/` sub-package groups the five
`MetricModel` subclasses. Tests are organized by tier so CI can run each tier as a
separate job. `.github/workflows/ci.yml` is the first deliverable per constitution
principle VI and the project's incremental delivery requirement.

## Parallel Execution Map

Once the shared foundation (CI + project skeleton + ProfileLoader + ValueSampler) is
complete, the following tracks can be run by independent agents simultaneously:

```
FOUNDATION (sequential — blocks all parallel work)
  F1: .github/workflows/ci.yml + pre-commit.sh  [deliver immediately; CI gates all future pushes]
  F2: pyproject.toml + package skeleton + conftest.py + test fixtures
  F3: profile.py  — ProfileLoader (from_file/from_string) + ProfileResolver + HardwareProfile loading
  F4: sampler.py + timeline.py  — ValueSampler + phase sequencer

PARALLEL TRACKS (launch simultaneously once foundation is complete)
  Track A — Domain Models (five fully independent agents):
    A1: domains/cpu.py    (no imports of other domains)
    A2: domains/memory.py (no imports of other domains)
    A3: domains/disk.py   (no imports of other domains)
    A4: domains/network.py(no imports of other domains)
    A5: domains/load.py   (reads CPU utilization value only, not cpu.py module)

  Track B — Writer + CLI (can run in parallel with Track A):
    B1: writer.py  — pcp.pmi wrapper + Tier 2 mock test
    B2: cli.py     — argparse subparsers + all flag handling

INTEGRATION (after foundation + all parallel tracks complete)
  I1: Tier 3 E2E tests (test_e2e.py)
  I2: man page (man/pmlogsynth.1)
  I3: README.md + bundled hardware profile YAML content
```

Domain models A1–A5 share only `MetricModel` from `domains/base.py` and have zero
inter-domain imports. Each can be developed, tested (Tier 1), and merged independently.
`writer.py` and `cli.py` can use stubs for domain calls while domains are in flight.

## Complexity Tracking

> No constitution violations detected. This section is intentionally empty.
