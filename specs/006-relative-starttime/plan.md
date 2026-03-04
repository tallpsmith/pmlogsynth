# Implementation Plan: Relative Start Time in Profiles

**Branch**: `006-relative-starttime` | **Date**: 2026-03-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-relative-starttime/spec.md`

## Summary

Extend `meta.start` in the workload profile YAML to accept PCP-style relative time expressions (e.g., `meta.start: -90m`, `meta.start: -1h30m`). The interval portion is parsed via PCP's own `pmParseInterval` — a hard dependency — giving compound expressions and the full PCP unit vocabulary for free. The feature bundles two DRY consolidations: migrating `parse_duration` to use `pmParseInterval` (adding `d` and compound form support), and merging the two duplicate absolute timestamp parsers into one shared function.

## Technical Context

**Language/Version**: Python 3.8+
**Primary Dependencies**: PyYAML, `pcp.pmapi` (system `python3-pcp`) — existing hard dependency
**Storage**: N/A — tool generates PCP binary archive files
**Testing**: pytest; `unittest.mock` for Tier 1/2 PCP stubs
**Target Platform**: Linux (CI); macOS (Tier 1/2 dev)
**Project Type**: CLI tool / library
**Performance Goals**: N/A — parsing is not on a hot path
**Constraints**: Python 3.8 compatible; no new pip dependencies; Tier 1 must run with zero PCP packages
**Scale/Scope**: Small targeted change — 2 existing files modified, 1 new module, new test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. PCP Archive Fidelity | ✅ Pass | `meta.start` feeds `timeline.py` start time. Resolved timestamp is a UTC `datetime` — identical contract to existing absolute path. No archive format changes. |
| II. Layered Testing | ✅ Pass | Tier 1: `parse_duration`, `parse_absolute_timestamp`, `parse_relative_starttime` all testable by mocking `pcp_parse_interval`. Tier 2: integration pipeline with mocked writer unchanged. Tier 3: E2E with real PCP validates resolved timestamps. |
| III. Declarative Profile-First | ✅ Pass | Relative time is accepted in `meta.start` — parsed in `profile.py` as part of `_parse_meta`. No CLI-only parsing path for relative times. |
| IV. Phase-Aware Extensibility | ✅ Pass | No changes to `ProfileLoader.from_file/from_string` contract, no new subcommands, `ValueSampler.seed` untouched. |
| V. Minimal External Dependencies | ✅ Pass | `pcp.pmapi` is already a hard dependency. No new pip packages. |
| VI. CI-First Quality Gates | ✅ Pass | New tests are Tier 1 (no PCP) and Tier 2. All gates preserved. |

## Project Structure

### Documentation (this feature)

```text
specs/006-relative-starttime/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── time-parsing.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
pmlogsynth/
├── time_parsing.py      # NEW — pcp_parse_interval, parse_absolute_timestamp,
│                        #        parse_relative_starttime
├── profile.py           # MODIFIED — parse_duration delegates to pcp_parse_interval;
│                        #             _parse_start_for_meta replaced by time_parsing fns;
│                        #             _parse_meta handles relative vs absolute meta.start
└── cli.py               # MODIFIED — _parse_start_time replaced by time_parsing fn;
                         #             ValueError → ValidationError at --start catch site

tests/
├── unit/
│   ├── test_time_parsing.py   # NEW — all Tier 1 tests for the new module
│   └── test_profile.py        # MODIFIED — parse_duration tests gain d/compound cases
└── integration/
    └── test_profile_integration.py  # MODIFIED (or new) — relative starttime round-trip

man/
└── pmlogsynth.1         # MODIFIED — document meta.start relative syntax

docs/
└── spike.yml            # UNCHANGED — no starttime in spike.yml (uses default)
```

**Structure Decision**: Single-project layout, no new top-level directories. New module `time_parsing.py` sits alongside existing package modules.

## Complexity Tracking

No constitution violations. No complexity justification required.

---

## Phase 0: Research

Complete. See [research.md](research.md). All unknowns resolved:

- ✅ PCP parsing API identified: `pcp.pmapi.timespec.fromInterval(s)` → `timespec.tv_sec`
- ✅ Isolation pattern: lazy import in `pcp_parse_interval()` in `time_parsing.py`
- ✅ YAML field confirmed: `meta.start` (not top-level `starttime`)
- ✅ Duplicate timestamp parsers: consolidated into `parse_absolute_timestamp()` in `time_parsing.py`
- ✅ `parse_duration` migration: stays in `profile.py`, delegates string path to `pcp_parse_interval`
- ✅ `--start` CLI flag: absolute only, no change in scope

---

## Phase 1: Design & Contracts

### New module: `pmlogsynth/time_parsing.py`

Three public functions. Zero module-level PCP imports.

```python
def pcp_parse_interval(interval_str: str) -> int:
    """Parse a PCP interval string to whole seconds. Lazy-imports pcp.pmapi."""
    # Raises ValidationError on parse failure.

def parse_absolute_timestamp(raw: str, field: str = "meta.start") -> datetime:
    """Parse ISO 8601 / 'YYYY-MM-DD HH:MM:SS UTC' to UTC-aware datetime."""
    # Raises ValidationError. Consolidates _parse_start_for_meta + _parse_start_time.

def parse_relative_starttime(raw: str, now: Optional[datetime] = None) -> datetime:
    """Parse '-90m' / '-1h30m' / '-2d' to UTC-aware datetime anchored to now."""
    # Strips leading '-', delegates magnitude to pcp_parse_interval.
    # Raises ValidationError for: positive offsets (+), bare '-', unrecognised interval.
```

### Changes to `pmlogsynth/profile.py`

- `parse_duration`: replace string-parsing branch (`_DURATION_SUFFIXES` dict) with a call to `time_parsing.pcp_parse_interval`. Retain int-literal path and the `> 0` constraint. Keep function in `profile.py` — Tier 1 tests import it from here.
- `_parse_start_for_meta`: deleted. Replaced inline by logic in `_parse_meta` that detects relative vs absolute:

  ```python
  if "start" in raw:
      raw_start = str(raw["start"])
      if raw_start.startswith("-"):
          start = parse_relative_starttime(raw_start)
      else:
          start = parse_absolute_timestamp(raw_start, field="meta.start")
  ```

### Changes to `pmlogsynth/cli.py`

- `_parse_start_time`: deleted.
- Import `parse_absolute_timestamp` from `pmlogsynth.time_parsing`.
- Update `--start` handler catch clause from `except ValueError` → `except ValidationError` to match the shared function's exception type.

### Tier 1 test mocking pattern

```python
from unittest.mock import patch

def test_parse_duration_days(self) -> None:
    with patch("pmlogsynth.profile.pcp_parse_interval", return_value=86400):
        assert parse_duration("1d") == 86400

def test_relative_starttime(self) -> None:
    with patch("pmlogsynth.time_parsing.pcp_parse_interval", return_value=5400):
        result = parse_relative_starttime("-90m", now=fixed_now)
    assert result == fixed_now - timedelta(seconds=5400)
```
