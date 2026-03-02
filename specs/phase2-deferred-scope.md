# pmlogsynth Phase 2 — Deferred Scope

These items were scoped in Phase 1 but deferred. This document captures requirements
in sufficient detail to feed into the next speckit round.

---

## 1. Full E2E Test Suite (was T040)

**Problem**: `tests/tier3/test_e2e.py` currently contains only stubs. There is no
automated verification that a generated archive is actually usable by PCP tools.

**Requirements**:
- Generate a real PCP archive from a known fixture profile (e.g. `tests/fixtures/workload-linear-ramp.yaml`)
- Verify archive integrity with `pmlogcheck` — must exit 0 with no errors
- Verify at least one metric is readable with `pmval` (e.g. `pmval -a <archive> kernel.all.load`)
- Verify `pmrep` can read the archive without error
- Verify that `pmlogsynth --validate <profile>` exits 0 for all fixture profiles in `tests/fixtures/`
- Verify exit code 1 for known-bad profiles (e.g. `bad-ratio.yaml`, `bad-duration.yaml`)
- Tests must be marked `@pytest.mark.tier3` and auto-skip when `pcp.pmi` is unavailable
- The E2E job in CI must continue to run on `ubuntu-latest` with `apt-get install pcp python3-pcp`
- Generated archive files should be written to `tmp_path` (pytest fixture) to avoid cleanup issues

**Acceptance criteria**:
- `pytest tests/tier3/ -v` passes on a system with PCP installed (CI E2E job goes green with real assertions)
- No stubs or `pytest.skip("not yet implemented")` in tier3

---

## 2. Man Page (was T041)

**Problem**: There is no `pmlogsynth(1)` man page. The tool is intended to be
installed system-wide and discoverable via `man pmlogsynth`.

**Requirements**:
- Write `man/pmlogsynth.1` in roff format (standard Unix man page)
- Sections: NAME, SYNOPSIS, DESCRIPTION, OPTIONS, PROFILES, METRICS, EXAMPLES, FILES, SEE ALSO
- SYNOPSIS must cover all CLI forms:
  - `pmlogsynth [options] profile.yaml`
  - `pmlogsynth generate [options] profile.yaml`
  - `pmlogsynth --validate profile.yaml`
  - `pmlogsynth --list-profiles [-C dir]`
  - `pmlogsynth --list-metrics`
- OPTIONS must document every flag: `-o`, `--start`, `-v`, `-C`, `--validate`,
  `--list-profiles`, `--list-metrics`, `--force`, `--leave-partial`
- PROFILES section must explain the 3-tier resolution precedence (`-C dir` > user dir > bundled)
  and list all 7 bundled profile names with their hardware specs
- METRICS section must list all 24 metric names with units and semantics
- EXAMPLES must include at minimum:
  - Generating a 7-day archive from a named profile
  - Using `--validate` before generating
  - Overriding host hardware with `-C` and `--overrides`
  - Reading the archive with `pmval` and `pmrep`
- FILES: document `~/.pcp/pmlogsynth/profiles/` as the user profile directory
- SEE ALSO: `pmval(1)`, `pmrep(1)`, `pmlogcheck(1)`, `pcp(1)`
- The man page must be installed via `pyproject.toml` data files or a `setup.cfg` entry
- CI should verify `man ./man/pmlogsynth.1` does not error

---

## 3. README (was T042)

**Problem**: There is no top-level `README.md`. The project is not self-describing
for new contributors or users discovering it on GitHub.

**Requirements**:
- Write `README.md` at the repo root
- Sections:
  - **Overview**: one-paragraph description of what pmlogsynth does and why
  - **Prerequisites**: `pcp`, `python3-pcp`, Python ≥ 3.8
  - **Installation**: `pip install -e ".[dev]"` and system package steps for Ubuntu/RHEL
  - **Quick Start**: a minimal working example (generate + inspect with pmval)
  - **Profile Format**: brief YAML reference with annotated example covering meta, host (all 3 forms), and phases with repeat and transition
  - **Hardware Profiles**: table of 7 bundled profiles with CPU/RAM/disk/NIC specs; how to add custom profiles
  - **Metrics Reference**: table of all 24 metrics with domain, name, units, semantics
  - **CLI Reference**: all flags summarised (should mirror man page OPTIONS)
  - **Development**: how to run the test tiers, pre-commit.sh, and CI structure
  - **Contributing**: PR process, coding standards (ruff, mypy strict, Python 3.8+)
- Must be accurate against the actual CLI output of `--help`, `--list-profiles`, `--list-metrics`
- No broken links; any example commands must be runnable

---

## 4. Quickstart Script Validation (was T043)

**Problem**: `specs/001-pmlogsynth-phase1/quickstart.md` contains a quickstart script
that has never been mechanically verified to run correctly end-to-end.

**Requirements**:
- Create `tests/tier3/test_quickstart.py` (or similar) that executes the quickstart
  scenario as a subprocess, verifying:
  1. `pmlogsynth --validate <profile>` exits 0
  2. `pmlogsynth -o /tmp/test-out <profile>` exits 0 and creates `.0`, `.index`, `.meta` files
  3. `pmlogcheck /tmp/test-out` exits 0
  4. `pmval -a /tmp/test-out kernel.all.load` produces readable output (exit 0)
- The test must use a fixture profile that works with bundled hardware profiles (no `-C` needed)
- Must be marked `@pytest.mark.tier3` and auto-skip without PCP
- The quickstart.md itself should be updated if any commands or flags differ from the
  actual implementation (ground-truth is the code, not the doc)

---

## 5. Cross-Cutting: repeat:daily Exclusivity Rule (Documentation)

**Problem**: The constraint that `repeat:daily` must be the sole phase in a profile
is now enforced as a `ValidationError` (added in Phase 1 cleanup), but it is not yet
documented in the man page, README, or quickstart examples.

**Requirements**:
- The man page must include a warning/note under the `repeat` field description
  explaining that `repeat: daily` cannot be combined with other phases
- The profile format section of the README must note the same constraint with an example
  of what NOT to do and why
- `quickstart.md` example profiles must not violate this constraint

---

## Notes for speckit

- All 4 deferred items can be a single Phase 2 spec or split into separate specs
  (suggest: E2E tests + quickstart as one, docs as a second)
- E2E and quickstart validation depend on a system with PCP — document clearly in spec
  which CI job executes them
- Man page and README have no code dependencies and can be authored independently
