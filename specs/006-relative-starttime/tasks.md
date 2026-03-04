# Tasks: Relative Start Time in Profiles

**Feature**: `006-relative-starttime`
**Branch**: `006-relative-starttime`
**Input**: Design documents from `/specs/006-relative-starttime/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/time-parsing.md

**Tests**: Included — mandatory TDD workflow per project guidelines.

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in all descriptions

---

## Phase 1: Setup

**Purpose**: Verify the baseline is green before any code changes.

- [X] T001 Verify existing test suite passes with `pytest tests/unit/ tests/integration/ -v` — confirm zero failures before touching code

---

## Phase 2: Foundational — Create `time_parsing.py` Module

**Purpose**: New module is a hard prerequisite for ALL user stories. `pcp_parse_interval` and `parse_absolute_timestamp` must exist before US1, US2, or US3 can proceed.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests (write first — must FAIL before implementation)

- [X] T002 Write failing Tier 1 tests for `pcp_parse_interval`: valid interval strings return whole seconds, PCP unavailability raises `ValidationError` — in `tests/unit/test_time_parsing.py`
- [X] T003 Write failing Tier 1 tests for `parse_absolute_timestamp`: all six accepted formats parse to UTC-aware datetime, unrecognised format raises `ValidationError` with field name — in `tests/unit/test_time_parsing.py`

### Implementation

- [X] T004 Create `pmlogsynth/time_parsing.py` with `pcp_parse_interval(interval_str: str) -> int` — lazy-imports `pcp.pmapi` inside function body; raises `ValidationError` on parse failure or PCP unavailable (not `ImportError`)
- [X] T005 Add `parse_absolute_timestamp(raw: str, field: str = "meta.start") -> datetime` to `pmlogsynth/time_parsing.py` — stdlib parsing of all six formats from `contracts/time-parsing.md`; all paths return UTC-aware datetime; raises `ValidationError` with field name on no match

**Checkpoint**: T002 and T003 tests pass. Module exists with two working functions.

---

## Phase 3: User Story 1 — Generate Archive Anchored to Recent Past (Priority: P1) 🎯 MVP

**Goal**: A profile with `meta.start: -90m` produces an archive starting 90 minutes before invocation time.

**Independent Test**: Run `pmlogsynth -o ./generated-archives/test-relative <profile>` with `meta.start: -90m` and verify archive first-sample timestamp is within 2 seconds of `(now - 90m)`.

### Tests (write first — must FAIL before implementation)

- [X] T006 Write failing Tier 1 tests for `parse_relative_starttime` with valid inputs (`-90m`, `-1h30m`, `-2d`, `-0s`, `-2days`) — mock `pmlogsynth.time_parsing.pcp_parse_interval`; verify `now - timedelta(seconds=offset)` result — in `tests/unit/test_time_parsing.py`
- [X] T007 [P] Write failing Tier 1 tests for `parse_duration` with new `d` and compound forms (`1d` → 86400, `1h30m` → 5400) — mock `pmlogsynth.profile.pcp_parse_interval`; verify existing positive/nonzero constraints still hold — in `tests/unit/test_profile.py`
- [X] T008 [P] Write failing integration test for relative `meta.start` round-trip: profile with `meta.start: -90m` loads successfully and `ProfileMeta.start` is within 2 seconds of `(now - 90m)` — in `tests/integration/test_profile_integration.py`

### Implementation

- [X] T009 Add `parse_relative_starttime(raw: str, now: Optional[datetime] = None) -> datetime` to `pmlogsynth/time_parsing.py` — strips leading `-`, calls `pcp_parse_interval`, subtracts seconds from `now`; returns UTC-aware datetime; per full contract in `contracts/time-parsing.md`
- [X] T010 Migrate `parse_duration` string-parsing branch in `pmlogsynth/profile.py` to import and delegate to `pcp_parse_interval` from `pmlogsynth.time_parsing`; remove the `_DURATION_SUFFIXES` dict; retain int-literal path and positive-nonzero constraint unchanged
- [X] T011 Update `_parse_meta` in `pmlogsynth/profile.py`: detect `raw_start.startswith("-")` → call `parse_relative_starttime`; else → call `parse_absolute_timestamp`; delete `_parse_start_for_meta` function

**Checkpoint**: Profile with `meta.start: -90m` resolves to correct timestamp. T006, T007, T008 all pass.

---

## Phase 4: User Story 2 — Mix Relative and Absolute Start Times (Priority: P2)

**Goal**: Profiles with absolute timestamps produce identical output to pre-feature; cli.py duplicate parser removed; `parse_duration` gains `d`/compound support.

**Independent Test**: Run tool with an existing absolute-timestamp profile (e.g., `meta.start: "2025-01-15 09:00:00 UTC"`) and verify archive start timestamp is unchanged from pre-feature behaviour.

### Tests (write first — must FAIL before implementation)

- [X] T012 Write Tier 1 regression tests for all six absolute timestamp formats accepted by `parse_absolute_timestamp`: ISO 8601 with Z, +00:00, bare T, space-separated UTC, space-separated, and `%z` — in `tests/unit/test_time_parsing.py`
- [X] T013 [P] Write Tier 1 regression tests confirming existing `parse_duration` behaviours are preserved: existing unit strings accepted, zero rejected, negative rejected — in `tests/unit/test_profile.py`

### Implementation

- [X] T014 Update `pmlogsynth/cli.py`: delete `_parse_start_time`, import `parse_absolute_timestamp` from `pmlogsynth.time_parsing`, call `parse_absolute_timestamp(args.start, field="--start")` in the `--start` handler, update catch clause from `except ValueError` to `except ValidationError`

**Checkpoint**: `pytest tests/unit/ tests/integration/` fully green. Absolute timestamps produce identical archive output. T012 and T013 pass.

---

## Phase 5: User Story 3 — Clear Errors for Malformed Relative Times (Priority: P3)

**Goal**: Invalid `meta.start` values produce a descriptive `ValidationError`; `--validate` exits non-zero with no archive written.

**Independent Test**: Run `pmlogsynth --validate <profile>` for profiles with `meta.start: -90x`, `meta.start: ago1hour`, and `meta.start: -` — verify non-zero exit and a clear error message naming the field for each.

### Tests (write first — must FAIL before implementation)

- [X] T015 Write failing Tier 1 tests for all `ValidationError` paths in `parse_relative_starttime`: positive offset (`+30m`) rejected, bare dash (`-`) rejected, unknown unit (`-90x`) rejected via `pcp_parse_interval` mock raising — in `tests/unit/test_time_parsing.py`
- [X] T016 [P] Write failing integration tests for `--validate` flag: profiles with `meta.start: -90x`, `meta.start: -`, and `meta.start: +30m` all exit non-zero and emit no archive — in `tests/integration/test_profile_integration.py`

### Implementation

- [X] T017 Audit `parse_relative_starttime` in `pmlogsynth/time_parsing.py` against all US3 acceptance scenarios: ensure `+`-prefixed input raises `ValidationError` naming the field with "only past-anchored offsets supported", bare `-` raises `ValidationError`, PCP-rejected interval surfaces a `ValidationError` with a valid example — patch any gaps
- [X] T018 Audit `_parse_meta` in `pmlogsynth/profile.py`: ensure `+`-prefixed `meta.start` values are routed through `parse_relative_starttime` (not silently passed to `parse_absolute_timestamp`) so the "only past-anchored offsets" message is emitted — patch if needed

**Checkpoint**: All three US3 acceptance scenarios pass. `--validate` exits non-zero for every invalid form. T015 and T016 pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final quality gate.

- [X] T019 Update `man/pmlogsynth.1` to document `meta.start` relative syntax: accepted forms (`-90m`, `-2h`, `-1h30m`, `-3d`, `-2days`), resolution semantics, and error cases
- [X] T020 [P] Update `README.md` to mention relative `meta.start` support in the profile YAML documentation section (Quick Start inline block stays as `docs/spike.yml` — spike.yml has no `meta.start`, no change needed there)
- [X] T021 Run `./pre-commit.sh` quality gate — fix any ruff/mypy failures; confirms CI-equivalent gate is green before push

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — `parse_relative_starttime` needs `pcp_parse_interval`
- **US2 (Phase 4)**: Depends on Phase 2 — can run in parallel with US1 (different primary files: cli.py vs profile.py)
- **US3 (Phase 5)**: Depends on US1 (Phase 3) — tests ValidationError paths in `parse_relative_starttime`
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Unblocked after Phase 2. No dependency on US2 or US3.
- **US2 (P2)**: Unblocked after Phase 2. Can run in parallel with US1 — primary change is `cli.py` (different file from US1's `profile.py`).
- **US3 (P3)**: Depends on US1 complete — tests error paths in the `parse_relative_starttime` implementation built in Phase 3.

### Within Each Phase

- Write tests → confirm they FAIL → write implementation → confirm tests PASS
- Commit only when tests are green

### Parallel Opportunities

- T002/T003: Same file, write sequentially to avoid conflicts
- T006, T007, T008: Different files — safe to launch in parallel
- T012 and T013: Different files — safe to launch in parallel
- T015 and T016: Different test files — safe to launch in parallel
- US1 (Phase 3) and US2 (Phase 4): Different source files — safe to work in parallel once Phase 2 is done

---

## Parallel Example: US1 Tests

```bash
# All US1 tests touch different files — launch together:
Task T006: parse_relative_starttime tests → tests/unit/test_time_parsing.py
Task T007: parse_duration d/compound tests → tests/unit/test_profile.py
Task T008: relative meta.start integration test → tests/integration/test_profile_integration.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Verify baseline
2. Complete Phase 2: Create `time_parsing.py` (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 — relative `meta.start` works end-to-end
4. **STOP and VALIDATE**: `pmlogsynth -o ./generated-archives/test-relative <profile-with-minus-90m>`
5. Ship: existing users unaffected; relative time delivers immediate value

### Incremental Delivery

1. Setup + Foundational → module skeleton exists, two functions tested
2. US1 → relative `meta.start` works → demo with `-90m` profile (MVP!)
3. US2 → consolidation complete; cli.py cleaned up; `parse_duration` gains `d`
4. US3 → validation errors polished; `--validate` rejects all bad forms
5. Polish → docs updated; `./pre-commit.sh` green

### Parallel Team Strategy

With two developers after Phase 2:

- **Developer A**: US1 (Phase 3) — `parse_relative_starttime` + `profile.py` `_parse_meta`
- **Developer B**: US2 (Phase 4) — `cli.py` consolidation (different file, fully independent)

---

## Notes

- `[P]` = different files, no incomplete dependencies — safe to execute concurrently
- `[Story]` maps each task to its user story for traceability
- **TDD**: every test task MUST be confirmed FAILING before paired implementation tasks begin
- Tier 1 mock target for `parse_relative_starttime`: `pmlogsynth.time_parsing.pcp_parse_interval`
- Tier 1 mock target for `parse_duration`: `pmlogsynth.profile.pcp_parse_interval`
- Run `./pre-commit.sh` before every commit (mandoc + ruff + mypy + Tier 1 + Tier 2)
- All generated archives → `./generated-archives/` (gitignored)
- `docs/spike.yml` is unchanged (no `meta.start` field in spike.yml)
