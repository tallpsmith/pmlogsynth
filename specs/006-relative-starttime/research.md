# Research: Relative Start Time in Profiles

**Branch**: `006-relative-starttime` | **Date**: 2026-03-04

## Decision 1: PCP interval parsing API

**Decision**: Use `pcp.pmapi.timespec.fromInterval(s)` as the authoritative interval parser.

**Rationale**: Already a hard dependency. Handles all of PCP's unit vocabulary — short forms (`s`, `m`, `h`, `d`), long forms (`seconds`, `minutes`, etc.), and compound forms (`1h30m`, `4d6h`). Returns a `timespec` with `.tv_sec` as an integer.

**Critical caveat**: `fromInterval` does NOT accept a leading `-`. Strip the sign before calling; subtract the resulting seconds from now.

**Alternatives considered**:
- Hand-rolled regex parser: rejected — duplicates PCP's own parser, diverges over time
- `pmParseTimeWindow`: rejected — no Python binding; C-only

---

## Decision 2: Isolation pattern for `pcp.pmapi` import

**Decision**: Create `pmlogsynth/time_parsing.py` with a `pcp_parse_interval()` helper that lazy-imports `pcp.pmapi` inside the function body.

**Rationale**: `profile.py` is imported in Tier 1 tests (no PCP). A top-level `import pcp.pmapi` in `profile.py` would break Tier 1 on PCP-less systems. The lazy-import pattern (already used for `writer.py` in `cli.py`) keeps Tier 1 clean — tests mock `pmlogsynth.time_parsing.pcp_parse_interval` via `unittest.mock.patch`.

**Alternatives considered**:
- Top-level import in `profile.py`: rejected — breaks Tier 1 constitution requirement
- Top-level import in a new `pcp_time.py` constant module: rejected — still requires PCP at import time, preventing Tier 1 use

---

## Decision 3: Consolidation target for absolute timestamp parsing

**Decision**: `parse_absolute_timestamp()` lives in `time_parsing.py`, raises `ValidationError`, is imported by both `profile.py` and `cli.py`.

**Rationale**: `_parse_start_for_meta` (profile.py) and `_parse_start_time` (cli.py) are byte-for-byte identical. One shared function eliminates the duplication. `cli.py`'s catch clause at line 306 must be updated from `ValueError` to `ValidationError` to match.

**Note on PCP**: `pmParseTime` and `pmParseTimeWindow` exist in C but have no Python bindings. Absolute timestamp parsing stays stdlib (`datetime.strptime`).

---

## Decision 4: `parse_duration` migration strategy

**Decision**: Keep `parse_duration` in `profile.py` but delegate to `pcp_parse_interval` from `time_parsing.py` for the string-parsing path. Retain the positive-only, non-zero constraint. The plain-integer path (accepts `int` directly) remains as pure Python.

**Rationale**: `parse_duration` is imported by Tier 1 tests from `profile.py`. Moving it to `time_parsing.py` would require updating the public import path. Keeping it in `profile.py` minimises churn while still gaining `d` and compound-form support.

**Behaviour changes after migration**:
- `"10d"` (previously rejected) → now accepted → 864000 seconds
- `"1h30m"` (previously rejected) → now accepted → 5400 seconds
- `"1.5h"` behaviour: `pmParseInterval` may accept floats — must explicitly clamp to reject non-integer results if needed (verify in tests)
- Zero result from a valid PCP interval string (e.g., `"0m"`) must still be rejected (existing positive constraint)

---

## Decision 5: YAML field name

**Decision**: The profile field is `meta.start` (not top-level `starttime`). Relative time extends the existing `meta.start` field — no new field name needed.

**Rationale**: Confirmed from `profile.py` line 231: `if "start" in raw: start = _parse_start_for_meta(str(raw["start"]))`. The spec used "starttime" loosely; the actual schema key is `meta.start`.

---

## Decision 6: `--start` CLI flag scope

**Decision**: The `--start` CLI flag continues to accept absolute timestamps only (no relative time). Relative time is profile-only (`meta.start: -90m`).

**Rationale**: The feature spec targets profile-level relative time. Extending `--start` to accept relative intervals is a separate future concern. The CLI flag already overrides `meta.start` — this interaction is unchanged.
