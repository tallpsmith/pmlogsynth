# Feature Specification: Relative Start Time in Profiles

**Feature Branch**: `006-relative-starttime`
**Created**: 2026-03-04
**Status**: Draft
**Input**: User description: "Allow the profile `starttime` variable to include relative time, on top of the existing explicit timestamp. e.g. `starttime: -90minutes` to define a start time of 90 minutes earlier than whatever `now` is."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Archive Anchored to Recent Past (Priority: P1)

A user wants to generate a synthetic PCP archive that represents a workload that "happened" 90 minutes ago, without needing to calculate or hardcode an exact timestamp. They set `starttime: -90m` in their profile and run the tool — the resulting archive begins at a timestamp 90 minutes before the moment the tool is invoked.

**Why this priority**: This is the core value of the feature. Relative times eliminate the mental overhead of computing absolute timestamps and make profiles reusable across different invocations. Using PCP's own interval format means users familiar with other PCP tools (`pmrep`, `pmstat`, `pmlogger`) already know the syntax.

**Independent Test**: Can be fully tested by running the tool with a profile containing `starttime: -90m` and verifying the archive's first sample timestamp is within a few seconds of `(now - 90 minutes)`.

**Acceptance Scenarios**:

1. **Given** a profile with `starttime: -90m`, **When** the tool is invoked, **Then** the archive begins at a timestamp approximately 90 minutes before the current wall-clock time.
2. **Given** a profile with `starttime: -30minutes`, **When** the tool is invoked at different times on different days, **Then** the archive always starts 30 minutes before *that* invocation's time, making the profile fully reusable.
3. **Given** a profile with `starttime: -1h30m`, **When** the tool is invoked, **Then** the archive starts 90 minutes before the current time (compound interval).
4. **Given** a profile with `starttime: -0s`, **When** the tool is invoked, **Then** the archive starts at approximately the current time.

---

### User Story 2 - Mix Relative and Absolute Start Times Across Profiles (Priority: P2)

A user maintains a library of profiles: some use absolute timestamps (e.g., for reproducible test fixtures) and some use relative times (e.g., for ad-hoc monitoring simulations). Both formats must coexist and the tool must handle each correctly without requiring any flag or mode switch.

**Why this priority**: Backwards compatibility is essential. Existing profiles with absolute timestamps must continue to work exactly as before.

**Independent Test**: Can be fully tested by running the tool once with an existing absolute-timestamp profile and once with a new relative-timestamp profile, verifying both produce correctly-timestamped archives.

**Acceptance Scenarios**:

1. **Given** an existing profile with `starttime: "2025-01-15 09:00:00"`, **When** the tool is invoked, **Then** the archive starts at exactly that absolute time (existing behaviour preserved).
2. **Given** a profile with `starttime: -2h`, **When** the tool is invoked, **Then** the archive starts 2 hours before the current time.
3. **Given** a profile with `starttime: -2hours`, **When** the tool is invoked, **Then** the archive starts 2 hours before the current time (full-word form accepted, same result).

---

### User Story 3 - Receive Clear Errors for Malformed Relative Times (Priority: P3)

A user accidentally types a malformed relative time (e.g., `starttime: -90x` or `starttime: ago1hour`). The tool must reject the profile with a descriptive validation error rather than silently producing a wrong archive.

**Why this priority**: Good error messages prevent silent data corruption and reduce debugging time.

**Independent Test**: Can be fully tested by running `--validate` against a profile with a malformed relative starttime and verifying the tool exits non-zero with a clear message identifying the field and the problem.

**Acceptance Scenarios**:

1. **Given** a profile with `starttime: -90x` (unrecognised unit), **When** the tool validates the profile, **Then** a validation error is raised naming the field and describing what a valid interval looks like (e.g., `-90m`, `-2h`, `-1d`).
2. **Given** a profile with `starttime: ago1hour` (wrong syntax — missing leading `-`), **When** the tool validates the profile, **Then** a validation error is raised with a human-readable explanation.
3. **Given** a profile with `starttime: -` (leading dash but no interval), **When** the tool validates the profile, **Then** a validation error is raised.

---

### Edge Cases

- What happens with compound intervals (e.g., `-1h30m`, `-4d6h`)? These must be supported — they follow PCP interval syntax and `pmParseInterval` handles them natively.
- What happens when the relative offset is larger than a day (e.g., `-3d`)? Multi-day offsets must be supported using the same syntax.
- What happens when the relative offset is zero (e.g., `-0s`)? The archive starts at the current time, equivalent to omitting `starttime`.
- What happens when `starttime` is absent from the profile? Existing default behaviour is preserved with no change.
- What happens with positive relative values (e.g., `+30m`)? Out of scope — only negative (past-anchored) offsets are supported. Positive values produce a validation error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The profile `starttime` field MUST accept relative time expressions of the form `-<interval>`, where `<interval>` is any interval string valid in PCP's native interval format (e.g., `-90m`, `-2h`, `-1d`, `-1h30m`, `-2days`). Both short (`s`, `m`, `h`, `d`) and long (`seconds`, `minutes`, `hours`, `days`, and their singular forms) unit tokens are accepted. Compound intervals (e.g., `-1h30m`) are also accepted.
- **FR-002**: When a relative `starttime` is used, the tool MUST resolve it to an absolute timestamp by subtracting the offset from the wall-clock time at the moment of invocation.
- **FR-003**: The tool MUST continue to accept absolute timestamp strings in `starttime` with no change to existing behaviour.
- **FR-004**: The tool MUST reject relative time expressions that fail PCP interval parsing or use malformed syntax (e.g., unrecognised unit tokens, bare `-`, missing magnitude), reporting a validation error that identifies the field and shows a valid example.
- **FR-005**: Positive relative values (e.g., `+30m`) MUST be rejected with a validation error stating that only past-anchored (negative) offsets are supported.
- **FR-006**: The `--validate` flag MUST detect and report invalid relative time expressions without generating any archive output.
- **FR-007**: The resolved absolute start time MUST be used consistently throughout archive generation — all sample timestamps are derived from this resolved value.
- **FR-008**: The existing `parse_duration` function (used for phase and meta `duration` fields) MUST be migrated to use PCP's interval parser, gaining `d` (days) and compound form support (e.g., `1h30m`) while retaining the existing positive-only, non-zero constraint.
- **FR-009**: The two duplicate absolute timestamp parsing functions (`_parse_start_for_meta` in profile.py and `_parse_start_time` in cli.py) MUST be consolidated into a single shared function. The consolidated function uses stdlib date/time parsing (PCP's Python API does not expose absolute timestamp parsing).

### Key Entities

- **Profile**: A YAML document describing a synthetic workload. The `starttime` field controls when the archive's timeline begins.
- **Relative Time Expression**: A string value for `starttime` consisting of a leading `-` followed by a PCP interval string (e.g., `-90m`, `-2h`, `-1h30m`, `-2days`). The interval portion conforms to PCP's standard interval format as used by tools like `pmrep` and `pmlogger`.
- **PCP Interval String**: An interval magnitude expressed in PCP's native format, supporting unit tokens `s`/`sec`/`secs`/`second`/`seconds`, `m`/`min`/`mins`/`minute`/`minutes`, `h`/`hour`/`hours`, `d`/`day`/`days`, optionally compounded (e.g., `1h30m`).
- **Resolved Start Time**: The absolute timestamp produced by subtracting a relative offset from the invocation wall-clock time. Used as the effective origin for archive generation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing profiles using absolute `starttime` values produce identical archive output after this change (zero regression).
- **SC-002**: A profile using any PCP interval expression — including short forms (`-90m`, `-2h`, `-1d`), long forms (`-90minutes`, `-2hours`), and compound forms (`-1h30m`) — produces an archive whose first sample timestamp matches `(invocation time − offset)` within a 2-second tolerance.
- **SC-003**: Invalid relative time expressions are caught and reported during `--validate` in 100% of cases, with no archive written to disk.
- **SC-004**: The existing unit, integration, and end-to-end test suite passes with zero new failures.

## Clarifications

### Session 2026-03-04

- Q: Should `parse_duration` (used for phase/meta duration fields) also be migrated to use `pmParseInterval` as part of this feature? → A: Yes — migrate `parse_duration` to `pmParseInterval`, giving `d` support and compound forms (`1h30m`) via a single parsing path.
- Q: Should the duplicate absolute timestamp parsing (`_parse_start_for_meta` in profile.py vs `_parse_start_time` in cli.py) be consolidated as part of this work? Does PCP offer a utility for this? → A: Yes — consolidate into one shared function. PCP Python API does not expose absolute timestamp parsing (`pmParseTime`/`pmParseTimeWindow` are C-only with no Python bindings), so the consolidated function uses stdlib `datetime`, which is correct.

## Assumptions

- Only negative (past-anchored) relative offsets are in scope. Future-anchored (positive) offsets are explicitly excluded from this feature.
- The interval portion of a relative time expression is parsed using PCP's native interval format (`pmParseInterval`), which is already available as a hard dependency. This gives compound expressions (e.g., `-1h30m`) and all of PCP's unit vocabulary for free, without implementing a custom parser.
- Validation of the interval string delegates to the same PCP interval parser — if PCP rejects it, the tool rejects it with an informative error.
- The reference point for "now" is the wall-clock time at the start of tool invocation.
- No sub-second precision is required for relative time resolution.
- The `--show-schema` output and man page must be updated to document the new relative time syntax alongside the existing absolute timestamp syntax.
