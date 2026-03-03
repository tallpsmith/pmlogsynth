# Feature Specification: Developer Experience Improvements

**Feature Branch**: `003-dx-improvements`
**Created**: 2026-03-02
**Status**: Draft
**Input**: User description: "Improve developer experience: automated man page validation, venv setup detection, PCP prerequisite checks, and README focused on usage"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New Contributor Runs pre-commit.sh Cold (Priority: P1)

A developer has just cloned the repository and runs `./pre-commit.sh` for the first time with no virtualenv, no dev dependencies installed, and possibly no PCP on their system. Instead of failing cryptically with `ruff: command not found`, the script detects what is missing and tells them exactly what to do to fix it before running any quality checks.

**Why this priority**: This is the first thing every new contributor hits. A confusing failure here kills onboarding momentum before they've even read a line of source code. Fixing this delivers the most value to the most people, immediately.

**Independent Test**: Can be tested by running `./pre-commit.sh` from a clean environment (no venv, no ruff) and observing that the output names each missing prerequisite with a clear remediation instruction, then exits non-zero without attempting any quality checks.

**Acceptance Scenarios**:

1. **Given** no Python virtualenv exists, **When** `./pre-commit.sh` is run, **Then** the script prints a clear message explaining how to create and activate a venv using the correct Python (including the macOS Homebrew `pmpython` guidance), then exits non-zero.
2. **Given** a venv is active but dev dependencies are not installed, **When** `./pre-commit.sh` is run, **Then** the script detects that `ruff`, `mypy`, or `pytest` are missing and prints the `pip install -e ".[dev]"` command to run, then exits non-zero.
3. **Given** all Python deps are present but `pmpython` is not on PATH, **When** `./pre-commit.sh` is run, **Then** the script warns that PCP is not installed, explains it is a hard dependency, and provides the platform-appropriate install command (apt/dnf/Homebrew), then exits non-zero.
4. **Given** `pmpython` is on PATH but `cpmapi` bindings are absent from the active Python's site-packages, **When** `./pre-commit.sh` is run, **Then** the script warns that the active Python cannot see the PCP bindings and explains how to create a venv from `pmpython` instead.
5. **Given** all prerequisites are satisfied, **When** `./pre-commit.sh` is run, **Then** no prerequisite warnings appear and the quality checks proceed as today.

---

### User Story 2 - pre-commit.sh Validates Man Page Without Opening a Pager (Priority: P2)

The quality gate checks that the man page source file (`man/pmlogsynth.1`) exists and is syntactically valid roff, without invoking an interactive pager that blocks on user input.

**Why this priority**: The current `man ./man/pmlogsynth.1` call halts the script until the developer hits `q`. In a CI context or during rapid iteration this is unacceptable. The value of the check — confirming the file is present and renders correctly — can be preserved without the interaction.

**Independent Test**: Can be tested by running the man page check step in isolation against a valid `.1` file (passes silently), a malformed `.1` file (fails with an error message), and an absent file (fails stating the file is missing).

**Acceptance Scenarios**:

1. **Given** `man/pmlogsynth.1` exists and contains valid roff, **When** the man page check runs, **Then** it exits 0 silently (or with a one-line "OK" confirmation).
2. **Given** `man/pmlogsynth.1` exists but contains a roff syntax error, **When** the man page check runs, **Then** it exits non-zero and prints the offending error.
3. **Given** `man/pmlogsynth.1` does not exist, **When** the man page check runs, **Then** it exits non-zero with a clear "file not found" message.
4. **Given** the man page check runs in a non-interactive environment (e.g., CI), **Then** it never opens a pager or waits for user input.

---

### User Story 3 - README Focused on Using pmlogsynth (Priority: P3)

A user who wants to use `pmlogsynth` reads the README and finds only content relevant to running the tool — installation, quick start, profiles, metrics, and CLI reference. Test-running instructions are not in README; they live exclusively in CONTRIBUTING.md for contributors.

**Why this priority**: README is the project's front door. Mixing contributor workflows into it adds noise for end-users. The content already exists in CONTRIBUTING.md; this is about removing duplication and tightening focus.

**Independent Test**: Can be tested by reading README.md and confirming the "Running Tests" section (or equivalent pytest commands) no longer appears, while CONTRIBUTING.md still contains complete test-running documentation.

**Acceptance Scenarios**:

1. **Given** a user reads README.md, **When** they scan for information about running `pmlogsynth`, **Then** they find installation, quick start examples, bundled profiles, metrics overview, and CLI reference — with no pytest or test-tier instructions.
2. **Given** a contributor reads CONTRIBUTING.md, **When** they look for how to run tests, **Then** they find complete documentation covering all test tiers, the pre-commit gate, and TDD guidance.
3. **Given** README.md references CONTRIBUTING.md for contributor workflows, **When** a contributor clicks that link, **Then** it correctly navigates to CONTRIBUTING.md.

---

### Edge Cases

- What happens when `groff` / `nroff` is not installed on the developer's machine? The man page check should detect this and warn, rather than fail with an obscure error.
- What if the developer is on macOS and the system Python is the active Python when running `pre-commit.sh`? The prerequisite check should detect this and give macOS-specific guidance about using `pmpython` to create the venv.
- What if the developer runs `pre-commit.sh` from a directory other than the repo root? Path resolution must be robust.
- What if `cpmapi` is importable but `pcp.pmi` is not (partial PCP install)? The prerequisite check reports each as a distinct failure; a partial install is NOT treated the same as a full PCP absence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `pre-commit.sh` MUST perform a prerequisite check before any quality gate step executes.
- **FR-002**: The prerequisite check MUST verify that the active Python environment has `ruff`, `mypy`, and `pytest` available on PATH or within the venv.
- **FR-003**: The prerequisite check MUST verify that `pmpython` is accessible on PATH as evidence PCP is installed system-wide.
- **FR-004**: The prerequisite check MUST verify that both `cpmapi` and `pcp.pmi` are importable from the active Python (i.e., the venv was created from the correct Python with PCP bindings). Each missing module MUST be reported as a distinct failure with its own remediation message.
- **FR-005**: When one or more prerequisites are missing, `pre-commit.sh` MUST check ALL prerequisites before exiting — collecting every failure — then print a human-readable explanation of each missing item with the exact command to resolve it, and exit non-zero without running quality checks.
- **FR-006**: The man page check MUST verify file existence and roff syntax validity non-interactively using a formatting tool rather than opening a pager.
- **FR-007**: The man page check MUST exit 0 on a valid file and non-zero on a missing or malformed file.
- **FR-008**: The man page check MUST never open an interactive pager or require user input.
- **FR-009**: If the roff formatting tool is not available, the man page check MUST fall back to a file-existence-only check and warn that full syntax validation was skipped.
- **FR-010**: README.md MUST NOT contain instructions for running tests or pytest command examples.
- **FR-011**: CONTRIBUTING.md MUST contain complete test-running documentation covering all tiers (unit, integration, E2E) and the pre-commit gate.
- **FR-012**: README.md MUST include a reference directing contributors to CONTRIBUTING.md for development workflows.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with a fresh clone can run `./pre-commit.sh` and receive actionable, specific remediation instructions for every missing prerequisite — zero ambiguous error messages.
- **SC-002**: Running `./pre-commit.sh` in a fully configured environment completes without any interactive pause or pager prompt.
- **SC-003**: The man page check catches a deliberately introduced roff syntax error and exits non-zero with a descriptive message.
- **SC-004**: README.md contains zero references to `pytest` commands or test-tier instructions after this change.
- **SC-005**: All existing passing tests continue to pass after the README and CONTRIBUTING.md edits (no regressions in documentation cross-references tested by any automated checks).

## Clarifications

### Session 2026-03-02

- Q: When multiple prerequisites are missing, should the script report all failures before exiting or stop on the first? → A: Collect all missing prerequisites, report all of them, then exit non-zero.
- Q: Should pre-commit.sh automatically create the venv and install dependencies, or detect-and-advise only? → A: Detect-and-advise only — print instructions, exit non-zero, never auto-create or auto-install anything.
- Q: Should the prerequisite check verify both `cpmapi` and `pcp.pmi`, or cpmapi only? → A: Check both — report each as a distinct failure with a specific message if missing.

## Assumptions

- The primary development platform is macOS with Homebrew PCP, but the pre-commit improvements must also work on Linux (Debian/Ubuntu, RHEL/Fedora).
- `groff` is the preferred roff formatting tool for syntax checking; `nroff` or `mandoc` may serve as fallbacks if `groff` is absent.
- CONTRIBUTING.md already contains the full test-running documentation; the README change is purely a removal and a cross-reference addition.
- The venv creation approach documented in README (using `pmpython -m venv .venv`) is the canonical macOS setup; the prerequisite check should reinforce this.
- `pre-commit.sh` remains a bash script; no rewrite to another language is in scope.
- `pre-commit.sh` is strictly detect-and-advise — it MUST NOT auto-create virtualenvs, auto-install packages, or modify the developer's environment in any way.
