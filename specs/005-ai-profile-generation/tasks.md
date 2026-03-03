# Tasks: AI-Driven Profile Generation

**Input**: Design documents from `/specs/005-ai-profile-generation/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation
and testing of each story. Tests are included per the mandatory TDD workflow in CLAUDE.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Package infrastructure — must be complete before the schema context document
can be bundled and loaded at runtime.

- [ ] T001 Add `schema_context.md` to `[tool.setuptools.package-data]` entry for `pmlogsynth` in `pyproject.toml` (alongside existing `profiles/*.yaml`)

**Checkpoint**: `pip install -e .` picks up `schema_context.md` from the package; `importlib.resources.read_text("pmlogsynth", "schema_context.md")` can be exercised without `FileNotFoundError` once the file exists.

---

## Phase 2: Foundational — Schema Context Document

**Purpose**: The schema context document is the load-bearing artifact for ALL user stories.
US1, US2, and US3 all depend on it existing, being correct, and being within the token budget.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Write five failing Tier 1 unit tests in `tests/unit/test_schema_context.py`: `test_schema_context_file_exists`, `test_schema_context_version_matches`, `test_schema_context_has_required_sections` (checks `meta`, `host`, `phases` headings), `test_schema_context_lists_hardware_profiles` (all 7 bundled profiles), `test_schema_context_within_token_budget` (`len(content) <= 32000`). Confirm all five fail before proceeding.

- [ ] T003 Create `pmlogsynth/schema_context.md` with: (1) `# pmlogsynth Profile Schema` heading, (2) `Schema Version: <version>` line matching `pyproject.toml`, (3) full field-table sections for `meta`, `host`, and `phases` (including all stressor subfields), (4) list of all 7 bundled hardware profile names, (5) one simple and one complex annotated YAML example, (6) "Common Validation Errors" section covering all error messages from `profile.py` and the edge cases in `spec.md`, (7) total character count ≤ 32,000. Run tests from T002 and confirm all pass.

**Checkpoint**: `pytest tests/unit/test_schema_context.py -k "not cli"` passes (5 tests green). Schema doc exists and is complete.

---

## Phase 3: User Story 1 — Natural Language Archive Creation via Claude (Priority: P1) 🎯 MVP

**Goal**: A user running Claude Code in this repo can type `/generate-profile <description>` and receive a validated pmlogsynth YAML profile without editing any YAML manually. `pmlogsynth --show-schema` provides the schema context.

**Independent Test**: Run `pmlogsynth --show-schema | wc -c` (non-zero output, exit 0). Then run `/generate-profile a 10-minute archive with 70% CPU load` — confirm a `.yaml` file appears in `generated-archives/` and `pmlogsynth --validate <file>` exits 0.

### Tests for User Story 1

> **Write these tests FIRST. Confirm they FAIL before implementation.**

- [ ] T004 [US1] Add failing test `test_show_schema_cli_exits_zero` to `tests/unit/test_schema_context.py`: invoke `pmlogsynth --show-schema` via `subprocess.run`, assert exit code 0 and non-empty stdout. Confirm it fails (ImportError or exit ≠ 0) before proceeding.

### Implementation for User Story 1

- [ ] T005 [P] [US1] Add `"--show-schema"` to the `_GLOBAL_FLAGS` set in `_preprocess_argv()` in `pmlogsynth/cli.py` (prevents the flag being consumed by the generate subparser)

- [ ] T006 [P] [US1] Register `--show-schema` argument in `_build_parser()` in `pmlogsynth/cli.py` with `action="store_true"`, alongside `--list-metrics` and `--list-profiles`

- [ ] T007 [US1] Implement `_cmd_show_schema() -> int` in `pmlogsynth/cli.py`: load `pmlogsynth/schema_context.md` via `importlib.resources.read_text("pmlogsynth", "schema_context.md", encoding="utf-8")`, print to stdout with `end=""`, return 0; on `FileNotFoundError` or `ModuleNotFoundError` print to stderr and return 1 (depends on T005, T006)

- [ ] T008 [US1] Add `show_schema` dispatch block in `main()` in `pmlogsynth/cli.py`: `if getattr(args, "show_schema", False): sys.exit(_cmd_show_schema())` — placed after version/help checks and before `--list-metrics`/`--list-profiles` (depends on T007). Run T004 test and confirm it passes.

- [ ] T009 [US1] Create `.claude/commands/generate-profile.md` implementing the 7-step skill flow from `contracts/claude-skill.md`: Step 1 (`pmlogsynth --show-schema` → `$SCHEMA_CONTEXT`), Step 2 (workload description from `$ARGUMENTS` or prompt), Step 4 (AI generation with schema + description, produce YAML only, enforce phase duration sum), Step 5 (write to `generated-archives/<slug>.yaml`, numeric suffix on collision), Step 6 (validate with `pmlogsynth --validate`, retry once on exit 1, stop on exit 2), Step 7 (report success with profile path + archive command + inspect command). Do NOT include Step 3 yet (that is US3).

**Checkpoint**: `pytest tests/unit/test_schema_context.py` passes (all 6 tests green). `pmlogsynth --show-schema` prints the schema doc and exits 0. `/generate-profile` skill exists and is invocable in Claude Code.

---

## Phase 4: User Story 2 — Schema-Aware Context for Any AI Agent (Priority: P2)

**Goal**: Any AI agent (ChatGPT, Gemini, local model via Ollama) that receives the output of `pmlogsynth --show-schema` as context can generate profiles that pass `pmlogsynth --validate` — without Claude specifically.

**Independent Test**: Run `pmlogsynth --show-schema > /tmp/pmlogsynth-schema.md`. Provide the contents to a non-Claude AI agent with a workload description. Save the generated YAML and run `pmlogsynth --validate` — it should exit 0 or produce an error message the AI can self-correct from.

> US2 is architecturally served by Phase 2 (schema doc) and US1 (--show-schema flag). The implementation task here is ensuring the "Common Validation Errors" section in the schema doc is comprehensive enough for AI self-correction — covering all edge cases from the spec and quickstart.

- [ ] T010 [US2] Review `pmlogsynth/schema_context.md` Common Validation Errors section against: (1) all edge cases listed in `spec.md` (unknown metric names, archive size, structurally valid but schema-invalid YAML, contradictory constraints, partial/malformed output), (2) the error table in `quickstart.md`. Add any missing error + fix pairs. Confirm the file still passes all 6 tests from T002 + T004 after edits.

**Checkpoint**: `pmlogsynth --show-schema` output is self-contained with enough error guidance that an AI agent's first-pass failure is self-correctable from the error message alone.

---

## Phase 5: User Story 3 — Iterative Refinement of Generated Profiles (Priority: P3)

**Goal**: A user can hand an existing `.yaml` profile to the `/generate-profile` skill and ask for a specific modification (e.g., "make the CPU spike last 20 minutes instead of 10") and receive an updated, valid profile.

**Independent Test**: Run `/generate-profile update generated-archives/my-workload.yaml to add a network saturation event at midnight`. Confirm the existing profile's unchanged sections are preserved and the requested modification is reflected in the output. `pmlogsynth --validate` exits 0.

- [ ] T011 [US3] Update `.claude/commands/generate-profile.md` to insert Step 3 (Optional: Acquire Existing Profile) between Steps 2 and 4: if the user's description references an existing profile, ask for the file path; read its contents; include the existing YAML in the generation prompt alongside the schema context and the modification request (FR-009). No new CLI or Python changes required.

**Checkpoint**: `/generate-profile` skill handles both generate-from-scratch (US1) and iterative refinement (US3) in a single skill file. All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Man page sync and final quality gate. Mandatory per project CLAUDE.md invariants.

- [ ] T012 Update `man/pmlogsynth.1`: add `--show-schema` to SYNOPSIS and to the Global Options subsection with description matching `_build_parser()` help text; backfill `--list-metrics`, `--list-profiles`, and `-C` which appear in SYNOPSIS but are currently absent from the OPTIONS section. Run `mandoc -T lint man/pmlogsynth.1` and confirm no lint errors.

- [ ] T013 Run `./pre-commit.sh` and confirm it exits 0: mandoc lint ✅, ruff ✅, mypy ✅, Tier 1 tests (includes all 6 schema context tests) ✅, Tier 2 integration tests ✅. Do not push until this is green.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on T001 (pyproject.toml entry must exist before `importlib.resources` can resolve the file)
- **User Stories (Phase 3–5)**: All depend on Phase 2 completion
  - US1 (Phase 3) — no dependency on US2 or US3
  - US2 (Phase 4) — depends on Phase 3 (needs `--show-schema` working to test the doc quality)
  - US3 (Phase 5) — depends on Phase 3 (extends the same skill file)
- **Polish (Phase 6)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2. Independent of US2 and US3.
- **US2 (P2)**: Depends on Phase 3 (T008 — `--show-schema` must work). Independent of US3.
- **US3 (P3)**: Depends on Phase 3 (T009 — skill file must exist). Independent of US2.

### TDD Order Within US1

Per CLAUDE.md mandatory TDD workflow:
1. Write T004 (failing test) → confirm failure → T005–T006 (can run in parallel) → T007 → T008 → confirm T004 now passes → T009

### Parallel Opportunities Within Phase 3 (US1)

```bash
# These two tasks have no interdependency — can run in parallel:
T005: Add --show-schema to _GLOBAL_FLAGS in pmlogsynth/cli.py
T006: Register --show-schema arg in _build_parser() in pmlogsynth/cli.py

# T007 and T008 are sequential (T007 before T008):
T007: Implement _cmd_show_schema() in pmlogsynth/cli.py
T008: Add dispatch in main() in pmlogsynth/cli.py

# T009 is independent of T005–T008 (different file):
T009: Create .claude/commands/generate-profile.md
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001) — pyproject.toml
2. Complete Phase 2 (T002–T003) — schema doc + tests ← **CRITICAL GATE**
3. Complete Phase 3 (T004–T009) — `--show-schema` CLI + Claude Code skill
4. **STOP and VALIDATE**: `pytest tests/unit/test_schema_context.py` (6/6 green) + manual `/generate-profile` invocation
5. Demo: describe workload → get valid archive. MVP achieved.

### Incremental Delivery

1. Phase 1 + Phase 2 → schema doc exists and is tested
2. Phase 3 (US1) → `/generate-profile` skill works from scratch → **Demo-able MVP**
3. Phase 4 (US2) → schema doc verified sufficient for any AI → broader community value
4. Phase 5 (US3) → iterative refinement → power-user workflow
5. Phase 6 → man page + pre-commit green → ready to merge

### Suggested MVP Scope

**Phases 1–3 only**: 9 tasks, delivers the entire Claude Code skill workflow end-to-end. US2 and US3 are enhancements.

---

## Notes

- [P] tasks = different files, no shared state, safe to parallelize
- [Story] label maps every implementation task to a specific user story for traceability
- **TDD is mandatory**: write failing tests, confirm failure, then implement — per CLAUDE.md
- Run `./pre-commit.sh` before every commit (T013 is the final gate, not the only run)
- Schema context doc token budget: target ≤6k tokens (≤24k chars); hard limit 8k tokens (≤32k chars)
- Archive output always goes to `generated-archives/` (gitignored)
- `importlib.resources.read_text` is used for Python 3.8 compat (not the `files()` API)
