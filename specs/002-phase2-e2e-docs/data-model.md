# Data Model: Phase 2 — E2E Tests, Documentation, and Quickstart Validation

**Date**: 2026-03-02

This is primarily a testing and documentation phase — no new domain entities. The relevant
"data model" is the structure of E2E test scenarios, the test fixture registry, and the
test directory layout before and after the rename.

---

## Test Directory Rename

### Before (current state)

```
tests/
├── conftest.py         markers: tier1, tier2, tier3
├── tier1/              unit tests, @pytest.mark.tier1
├── tier2/              integration tests, @pytest.mark.tier2
└── tier3/              E2E tests, @pytest.mark.tier3
```

### After (target state)

```
tests/
├── conftest.py         markers: unit, integration, e2e
├── unit/               unit tests, @pytest.mark.unit
├── integration/        integration tests, @pytest.mark.integration
└── e2e/                E2E tests, @pytest.mark.e2e
```

**Invariant**: No test content changes — only directory and marker names change.

---

## E2E Test Scenarios

### ArchiveRoundTrip (FR-001, FR-002, FR-003)

Generates a real PCP archive from a known fixture and verifies it with three PCP tools.

```
fixture_profile:  tests/fixtures/profiles/good-baseline.yaml
fixture_hw_dir:   tests/fixtures/profiles/    (passed as -C flag)
output_dir:       tempfile.mkdtemp()           (cleaned in teardown)

Assertions:
  pmlogcheck <archive>       → exit code 0, stdout contains no "Error"
  pmval -a <archive> kernel.all.load → exit code 0
  pmrep -a <archive> kernel.all.load → exit code 0
```

### ValidateGoodProfiles (FR-004)

Runs `pmlogsynth --validate` on all fixture profiles that should pass.

```
good_fixtures:
  - tests/fixtures/profiles/good-baseline.yaml
  - tests/fixtures/workload-linear-ramp.yaml

Assertion per fixture: exit code 0
```

### ValidateBadProfiles (FR-005)

Runs `pmlogsynth --validate` on all known-bad fixture profiles.

```
bad_fixtures:
  - tests/fixtures/profiles/bad-ratio.yaml
  - tests/fixtures/profiles/bad-duration.yaml
  - tests/fixtures/profiles/bad-noise.yaml

Assertion per fixture: exit code 1, stderr non-empty
```

### QuickstartWorkflow (FR-027, FR-028)

Runs the full quickstart sequence as a subprocess chain.

```
Steps:
  1. pmlogsynth --validate -C <fixture_hw_dir> <good_profile> → exit 0
  2. pmlogsynth -C <fixture_hw_dir> -o <tmpdir/archive> <good_profile> → exit 0
  3. pmlogcheck <tmpdir/archive> → exit 0
  4. pmval -a <tmpdir/archive> kernel.all.load → exit 0
```

### PcpNotAvailableSkip (FR-006, FR-029)

Auto-skip guard — implemented via the `pcp_available` session-scoped fixture in `conftest.py`.
No new fixture needed; the existing `_pcp_importable()` detection covers all four scenarios above.

---

## Fixture Registry

| Fixture file | Type | Role |
|---|---|---|
| `good-baseline.yaml` | workload profile | primary E2E happy-path + quickstart |
| `workload-linear-ramp.yaml` | workload profile | validate-good secondary |
| `bad-ratio.yaml` | bad workload profile | validate-fail: cpu ratio sum > 1.0 |
| `bad-duration.yaml` | bad workload profile | validate-fail: phase durations != meta.duration |
| `bad-noise.yaml` | bad workload profile | validate-fail: noise out of [0,1] range |
| `test-single-cpu.yaml` | hardware profile | referenced by workload fixtures (via -C flag) |

---

## Documentation Entities

### ManPageSection

The man page at `man/pmlogsynth.1` has these top-level sections:

| Section | Status |
|---------|--------|
| NAME | ✅ complete |
| SYNOPSIS | ✅ complete |
| DESCRIPTION | ✅ complete |
| OPTIONS | ✅ complete |
| YAML PROFILE FORMAT | ✅ complete; needs repeat:daily exclusivity warning |
| HARDWARE PROFILES | ✅ complete |
| SUPPORTED METRICS | ✅ complete (24 documented metrics) |
| EXAMPLES | ✅ complete |
| EXIT STATUS | ✅ complete |
| FILES | ✅ complete |
| SEE ALSO | ⚠️ needs `pcp(1)` added |

### ReadmeSection

README is the front door, not the manual. Target: stays under ~200 lines.

| Section | Status | Approach |
|---------|--------|----------|
| Overview/badges | ✅ present | keep |
| Installation | ✅ complete | keep |
| Quick Start | ⚠️ nearly complete | add `--validate` one-liner before generate step; add one-sentence repeat:daily callout |
| Bundled Hardware Profiles | ✅ complete | keep (7-row table is the right size for README) |
| Profile Format | ❌ absent | one-paragraph summary + link to `docs/profile-format.md` |
| Metrics | ❌ absent | one-liner: *"24 PCP metrics — `pmlogsynth --list-metrics` or `man pmlogsynth`"* |
| CLI Reference | ❌ absent | one-liner: *"Full CLI reference — `man pmlogsynth`"* |
| Running Tests | ⚠️ present, stale | update dir names unit/integration/e2e |
| Development / Contributing | ⚠️ one-liner | link to new `CONTRIBUTING.md` |

### New Documentation Files

| File | Content |
|------|---------|
| `docs/profile-format.md` | Full YAML schema: all fields, types, defaults, constraints, `repeat:daily` exclusivity warning with "don't do this" example |
| `CONTRIBUTING.md` | Dev setup, pre-commit gate, test structure explanation, PR conventions |
