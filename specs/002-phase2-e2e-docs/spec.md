# Feature Specification: Phase 2 — E2E Tests, Documentation, and Quickstart Validation

**Feature Branch**: `002-phase2-e2e-docs`
**Created**: 2026-03-02
**Status**: Draft
**Input**: User description: "Phase 2 deferred scope from specs/phase2-deferred-scope.md — E2E test suite, man page, README, quickstart script validation, and repeat:daily constraint documentation"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated E2E Archive Verification (Priority: P1)

A CI system automatically generates a real PCP archive from a known test profile and verifies that all PCP tools (`pmlogcheck`, `pmval`, `pmrep`) can read it without errors. When the E2E test suite runs, any regression that produces an unreadable or malformed archive is caught automatically.

**Why this priority**: This is the most critical gap in the test suite. Without real E2E assertions, the tool could produce broken archives and no automated check would catch it. Fixing this closes the largest quality risk.

**Independent Test**: Can be fully tested by running `pytest tests/e2e/ -v` on a system with PCP installed, and verifying all tests pass with real assertions (no stubs or skips).

**Acceptance Scenarios**:

1. **Given** a system with PCP installed and a known fixture profile, **When** the E2E test suite runs, **Then** a real archive is generated, `pmlogcheck` exits 0, `pmval` reads a metric without error, and `pmrep` reads the archive without error.
2. **Given** a known-bad profile (e.g., invalid ratio, invalid duration), **When** the E2E test suite runs, **Then** `pmlogsynth --validate` exits with a non-zero code and no archive is produced.
3. **Given** PCP is not installed, **When** the E2E tests run, **Then** all e2e tests are automatically skipped without error.
4. **Given** a valid fixture profile, **When** `pmlogsynth --validate` is run, **Then** it exits 0 for all valid fixture profiles and exits 1 for all known-bad fixture profiles.

---

### User Story 2 - Discoverable Man Page (Priority: P2)

A system administrator or operator installs pmlogsynth and types `man pmlogsynth` to learn how to use the tool. They find a complete, accurate man page covering all command-line options, profile format, available metrics, and example usage patterns.

**Why this priority**: The tool is designed for system-wide installation. Without a man page it is not discoverable by the standard Unix mechanism, reducing adoption and usability.

**Independent Test**: Can be fully tested by running `man ./man/pmlogsynth.1` and verifying it renders without errors, then reviewing that all documented options match actual CLI output.

**Acceptance Scenarios**:

1. **Given** the man page is installed, **When** a user runs `man pmlogsynth`, **Then** the man page displays without errors and covers NAME, SYNOPSIS, DESCRIPTION, OPTIONS, PROFILES, METRICS, EXAMPLES, FILES, and SEE ALSO sections.
2. **Given** the man page documents all CLI flags, **When** compared to `pmlogsynth --help` output, **Then** every flag in `--help` appears in the man page OPTIONS section and no undocumented flags exist in the man page.
3. **Given** the man page documents all 24 metrics, **When** compared to `pmlogsynth --list-metrics` output, **Then** every metric listed by the tool appears in the man page METRICS section.
4. **Given** the man page documents all 7 bundled profiles, **When** compared to `pmlogsynth --list-profiles` output, **Then** every profile appears in the man page PROFILES section with hardware specs.
5. **Given** the `repeat:daily` constraint, **When** a user reads the PROFILES section, **Then** a warning note explains that `repeat: daily` cannot be combined with other phases.

---

### User Story 3 - Self-Describing README (Priority: P3)

A new contributor or user discovers pmlogsynth on GitHub and reads the README to understand what the tool does, how to install it, how to use it, and how to contribute. All commands shown in the README actually work.

**Why this priority**: The project is not self-describing without a README. New contributors and users need orientation before they can evaluate or adopt the tool.

**Independent Test**: Can be fully tested by following the README's Quick Start instructions on a clean system with PCP installed and verifying each command exits 0 and produces expected output.

**Acceptance Scenarios**:

1. **Given** a new user reads the README, **When** they follow the Prerequisites and Installation steps, **Then** they can install pmlogsynth without additional guidance.
2. **Given** a new user reads the Quick Start section, **When** they copy and run the example commands, **Then** the commands exit 0 and produce a readable archive.
3. **Given** the README documents all 24 metrics and 7 hardware profiles, **When** compared to actual tool output, **Then** all entries are accurate and complete.
4. **Given** the README documents the `repeat:daily` constraint, **When** a user reads the Profile Format section, **Then** they see a clear note with an invalid example showing what NOT to do and why.
5. **Given** the README documents CLI flags, **When** compared to `pmlogsynth --help`, **Then** all flags are present and descriptions match actual behaviour.

---

### User Story 4 - Quickstart Script Validation (Priority: P4)

An automated test runs the quickstart scenario end-to-end as a subprocess, verifying that the documented quick-start workflow produces a valid archive that PCP tools can read. If the quickstart script in the documentation goes out of sync with the actual CLI, the test fails.

**Why this priority**: The quickstart is the most visible user-facing workflow. Automated verification ensures documentation stays accurate as the CLI evolves.

**Independent Test**: Can be fully tested by running the quickstart test in isolation, verifying it exercises validate → generate → check → read in sequence with a bundled fixture profile.

**Acceptance Scenarios**:

1. **Given** a system with PCP installed, **When** the quickstart test runs, **Then** `pmlogsynth --validate` exits 0 for the chosen fixture profile, followed by `pmlogsynth -o <tmpdir>` exits 0, `pmlogcheck` exits 0, and `pmval` reads a metric with exit 0.
2. **Given** PCP is not installed, **When** the quickstart test runs, **Then** it is automatically skipped without error.
3. **Given** the `quickstart.md` documents specific command flags, **When** compared against the implementation, **Then** the commands in the document are accurate and runnable.

---

### User Story 5 - Human-Readable Test Directory Names (Priority: P2)

A developer navigating the test suite sees directory names that immediately communicate intent — `tests/unit/`, `tests/integration/`, `tests/e2e/` — rather than opaque tier numbers. New contributors understand the test structure without needing to read documentation first.

**Why this priority**: The tier numbering is an internal implementation convention, not a meaningful description. Renaming improves discoverability and onboarding. It is a prerequisite to making the E2E test story self-evident to anyone reading the repository.

**Independent Test**: Can be fully tested by verifying the old `tests/tier{1,2,3}/` directories no longer exist, the new `tests/unit/`, `tests/integration/`, `tests/e2e/` directories contain the same tests, and all CI jobs and pre-commit gates pass without modification to their pytest invocations.

**Acceptance Scenarios**:

1. **Given** the renamed test directories, **When** a developer runs `pytest tests/unit/ -v`, **Then** all former tier1 tests pass.
2. **Given** the renamed test directories, **When** a developer runs `pytest tests/integration/ -v`, **Then** all former tier2 tests pass (with PCP mocked).
3. **Given** the renamed test directories, **When** a developer runs `pytest tests/e2e/ -v` on a system without PCP, **Then** all e2e tests are automatically skipped.
4. **Given** the renamed test directories, **When** CI runs all jobs, **Then** all quality and E2E jobs pass without changes to job definitions beyond directory names.
5. **Given** documentation (README, CLAUDE.md, CI config) references test directories, **When** the rename is complete, **Then** all references use the new names and none reference `tier1`, `tier2`, or `tier3`.

---

### Edge Cases

- What happens if a pytest marker or conftest references `tier3` by string after the rename? All marker names and skip logic must be updated to reference the new names.
- What happens when the E2E tests run on a system where `pcp.pmi` is importable but PCP tools (`pmlogcheck`, `pmval`, `pmrep`) are not in `PATH`? Each tool invocation must fail clearly with a descriptive error rather than silently succeeding.
- What happens if archive generation produces a file but `pmlogcheck` reports errors? The test must fail explicitly, not skip.
- What happens if a man page section references a metric or flag that no longer exists in the codebase? The discrepancy must be caught before merge.
- What happens if the `quickstart.md` uses a `-C` flag or custom profile path that requires non-bundled hardware profiles? The quickstart test must use only bundled profiles so it works without any extra setup.
- What happens if `repeat:daily` documentation is added to the man page or README but contradicts the actual validation error message? Documentation must match the exact constraint as implemented.

## Requirements *(mandatory)*

### Functional Requirements

**E2E Test Suite**

- **FR-001**: The E2E test suite MUST generate a real PCP archive from a known fixture profile and verify archive integrity using `pmlogcheck` (exit 0, no errors).
- **FR-002**: The E2E test suite MUST verify that at least one metric (e.g., `kernel.all.load`) is readable via `pmval` from the generated archive.
- **FR-003**: The E2E test suite MUST verify that `pmrep` can read the generated archive without error.
- **FR-004**: The E2E test suite MUST verify that `pmlogsynth --validate` exits 0 for all fixture profiles under `tests/fixtures/`.
- **FR-005**: The E2E test suite MUST verify that `pmlogsynth --validate` exits 1 for all known-bad profiles (e.g., bad-ratio.yaml, bad-duration.yaml).
- **FR-006**: All E2E tests MUST be marked so they are automatically skipped when the PCP library is unavailable, with no manual configuration required.
- **FR-007**: Generated archive files produced during E2E tests MUST be written to an isolated temporary directory and automatically cleaned up after the test run.
- **FR-008**: The CI E2E job MUST run the full E2E test suite (no stubs, no `pytest.skip("not yet implemented")`) and go green.

**Man Page**

- **FR-009**: A man page MUST exist covering NAME, SYNOPSIS, DESCRIPTION, OPTIONS, PROFILES, METRICS, EXAMPLES, FILES, and SEE ALSO sections.
- **FR-010**: The SYNOPSIS MUST document all CLI forms: default invocation, `generate` subcommand, `--validate`, `--list-profiles`, and `--list-metrics`.
- **FR-011**: The OPTIONS section MUST document every flag: `-o`, `--start`, `-v`, `-C`, `--validate`, `--list-profiles`, `--list-metrics`, `--force`, `--leave-partial`.
- **FR-012**: The PROFILES section MUST explain the three-tier resolution precedence (`-C dir` > user dir > bundled) and list all 7 bundled profiles with their hardware specifications.
- **FR-013**: The METRICS section MUST list all 24 metric names with units and semantics.
- **FR-014**: The EXAMPLES section MUST include: generating a 7-day archive from a named profile, using `--validate` before generating, overriding hardware with `-C` and `--overrides`, and reading the archive with `pmval` and `pmrep`.
- **FR-015**: The FILES section MUST document `~/.pcp/pmlogsynth/profiles/` as the user profile directory.
- **FR-016**: The SEE ALSO section MUST reference `pmval(1)`, `pmrep(1)`, `pmlogcheck(1)`, and `pcp(1)`.
- **FR-017**: The man page MUST include a warning in the PROFILES section stating that `repeat: daily` cannot be combined with other phases.
- **FR-018**: The man page MUST be installed via the project packaging configuration so that package installation makes it available via the `man` command.
- **FR-019**: CI MUST verify that `man ./man/pmlogsynth.1` exits 0 without errors.

**README**

- **FR-020**: A top-level README MUST exist with sections covering: Overview, Prerequisites, Installation, Quick Start, Profile Format, Hardware Profiles, Metrics Reference, CLI Reference, Development, and Contributing.
- **FR-021**: All example commands in the README MUST be runnable and exit 0 on a system with PCP installed.
- **FR-022**: The Metrics Reference table MUST list all 24 metrics with domain, name, units, and semantics, matching `pmlogsynth --list-metrics` output.
- **FR-023**: The Hardware Profiles table MUST list all 7 bundled profiles with CPU, RAM, disk, and NIC specifications, matching `pmlogsynth --list-profiles` output.
- **FR-024**: The CLI Reference section MUST summarise all flags matching the man page OPTIONS section.
- **FR-025**: The Profile Format section MUST document the `repeat:daily` constraint with an example of what NOT to do and an explanation of why.
- **FR-026**: The README MUST contain no broken links.

**Quickstart Validation**

- **FR-027**: An automated quickstart test MUST execute the full quickstart workflow: validate → generate → check → read, as a subprocess sequence.
- **FR-028**: The quickstart test MUST use a fixture profile that works with bundled hardware profiles, requiring no `-C` flag or custom profile directory.
- **FR-029**: The quickstart test MUST be automatically skipped when PCP is unavailable.
- **FR-030**: The `quickstart.md` document MUST be updated to match the actual CLI if any commands or flags have diverged from the implementation.

**Test Directory Rename**

- **FR-032**: The test directories MUST be renamed: `tests/tier1/` → `tests/unit/`, `tests/tier2/` → `tests/integration/`, `tests/tier3/` → `tests/e2e/`.
- **FR-033**: All pytest marker names, conftest skip logic, and `pytest.ini` / `pyproject.toml` marker registrations MUST be updated from `tier1`/`tier2`/`tier3` to `unit`/`integration`/`e2e`.
- **FR-034**: All CI job definitions, `pre-commit.sh`, and `CLAUDE.md` MUST be updated to reference the new directory names; no reference to `tier1`, `tier2`, or `tier3` MUST remain in any tracked file. `CLAUDE.md` is maintained directly (not auto-generated); its "Commands" section describing how to run tests by tier MUST accurately reflect the new `tests/unit/`, `tests/integration/`, `tests/e2e/` paths after the rename.
- **FR-035**: The README and any other documentation referencing the test structure MUST use the new directory names.
- **FR-036**: After the rename, running `pytest` without arguments MUST collect and execute exactly the same tests as before, with all e2e tests auto-skipping on systems without PCP.

**Cross-Cutting Documentation**

- **FR-031**: The `repeat:daily` exclusivity constraint MUST be documented consistently across the man page, README, and quickstart.md, with wording that matches the validation error produced by the tool.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The CI E2E job passes with zero test stubs or skips marked "not yet implemented" — all e2e tests execute real assertions against a generated archive.
- **SC-002**: Running the test suite against a known-bad profile set results in 100% detection: every bad profile triggers a validation failure exit code.
- **SC-003**: A user following the README Quick Start on a clean system with PCP installed completes the generate-and-verify workflow in under 5 minutes with no errors.
- **SC-004**: The man page covers 100% of CLI flags listed by `--help` and 100% of metrics listed by `--list-metrics`, with zero undocumented or missing entries.
- **SC-005**: All 7 bundled hardware profiles are documented in both the man page and README with accurate hardware specifications.
- **SC-006**: The quickstart test runs end-to-end without failures on a system with PCP installed, and is automatically skipped (not failed) on a system without PCP.
- **SC-007**: The `repeat:daily` constraint warning appears in the man page, README profile format section, and quickstart.md, with no example in any of those documents violating the constraint.
- **SC-008**: `man ./man/pmlogsynth.1` exits 0 in CI with no rendering errors.
- **SC-009**: Zero references to `tier1`, `tier2`, or `tier3` remain in any tracked file after the rename; a grep of the repository returns no matches.

## Clarifications

### Session 2026-03-02

- Q: Is CLAUDE.md auto-generated by a script, or maintained manually? → A: Maintained directly — edit it like any other file. Its "Commands" section describing how to run tests MUST be updated to accurately reflect the renamed test directories.
- Q: Should the man page be hand-written roff or generated from Markdown? → A: Hand-written roff, consistent with PCP project conventions and likely future upstreaming into PCP.

## Assumptions

- The 24 metrics and 7 bundled profiles are fully implemented and stable in Phase 1; this phase documents them as-is without modification.
- The fixture profiles in `tests/fixtures/` are sufficient to drive E2E tests without adding new fixtures.
- The known-bad profiles (`bad-ratio.yaml`, `bad-duration.yaml`) already exist in `tests/fixtures/profiles/` and will trigger the expected validation errors.
- The man page will be hand-written directly in roff format (not generated from Markdown), consistent with PCP project conventions and the likely long-term goal of upstreaming into PCP itself.
- CI E2E job runs on `ubuntu-latest` with PCP installed via `apt-get install pcp python3-pcp`, unchanged from the existing CI configuration.
- The quickstart.md already exists at `specs/001-pmlogsynth-phase1/quickstart.md`; it will be updated in-place if commands have diverged.
- Auto-skip behaviour for E2E tests is already implemented in `tests/conftest.py` via the `pcp.pmi` import check; only the marker name needs updating from `tier3` to `e2e`.

## Dependencies

- Phase 1 must be fully merged and stable (it is — all 212 tests passing on main).
- PCP system packages (`pcp`, `python3-pcp`) must be available in the CI E2E job (already configured).
- The `--list-metrics` and `--list-profiles` commands must produce stable, complete output to serve as the ground truth for documentation.
