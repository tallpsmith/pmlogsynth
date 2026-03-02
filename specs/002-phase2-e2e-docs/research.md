# Research: Phase 2 — E2E Tests, Documentation, and Quickstart Validation

**Date**: 2026-03-02
**Method**: Direct codebase inspection — no external sources required

---

## 1. Metric Count: Spec says 24, code has 26 named metrics

**Decision**: Treat the man page's 24 as the canonical documented count; investigate the 2 extras.

**Findings**: The domains register 26 distinct metric name strings:

| Metric | In man page? |
|--------|-------------|
| kernel.all.cpu.{idle,steal,sys,user,wait.total} (×5) | ✅ |
| kernel.percpu.cpu.{idle,sys,user} (×3) | ✅ |
| kernel.all.load (1) | ✅ |
| mem.util.{used,free,cached,bufmem} (×4) + mem.physmem (1) | ✅ |
| disk.all.read, disk.all.write (×2) | ✅ |
| disk.all.read_bytes, disk.all.write_bytes (×2) | ✅ |
| disk.dev.read_bytes, disk.dev.write_bytes (×2) | ✅ |
| **disk.dev.read.**, **disk.dev.write.** (×2, dynamic: += dev.name) | ❌ not documented |
| network.interface.{in,out}.{bytes,packets} (×4) | ✅ |

The two extras are **per-device IOPS** metrics (`disk.dev.read.<devname>`, `disk.dev.write.<devname>`)
registered dynamically in `pmlogsynth/domains/disk.py`. They are in the archive but absent from
the man page's SUPPORTED METRICS section.

**Rationale**: The spec says "24 metrics" and the man page reflects that count. The per-device IOPS
metrics are registered and written to archives — omitting them from the man page is a documentation
gap. The decision for this phase: **do not add them to the man page yet** (they'd change the "24"
claim in spec and tests, requiring spec amendment). Log as a follow-up note. The man page claim of
"24 metrics" matches the 24 explicitly documented; the 2 undocumented extras are an acceptable gap
for Phase 2 scope.

**Impact on E2E tests**: Use `kernel.all.load` for `pmval` assertions (simplest — no per-instance
complexity). Avoid `disk.dev.*` to sidestep the undocumented metric ambiguity.

---

## 2. bad-noise.yaml fixture: spec assumption is incomplete

**Decision**: Include `bad-noise.yaml` in the E2E validation-failure test set.

**Findings**: The spec (Assumptions section) mentions only `bad-ratio.yaml` and `bad-duration.yaml`
as known-bad fixtures, but `tests/fixtures/profiles/bad-noise.yaml` also exists with `noise: 1.5`
(out of range). All three trigger validation errors and should be covered by FR-005.

**Rationale**: Broader coverage costs nothing extra and is strictly better. E2E test
`test_validate_rejects_bad_profiles` should parametrize over all three.

---

## 3. Quickstart: fold into README, drop standalone doc

**Decision**: No standalone `quickstart.md` deliverable. The README Quick Start section IS the
quickstart. The automated test (`test_quickstart_workflow`) validates the workflow the README
promises — it doesn't reference an external document.

**Findings**: `specs/001-pmlogsynth-phase1/quickstart.md` is a planning artifact in `specs/` —
not somewhere users naturally land. The README already has a four-step Quick Start section
covering create → generate → verify → explore. The only gap is that `--validate` doesn't appear
before the generate step. Adding it as a one-liner preamble to step 2 closes the gap in ~3 lines,
keeping the README's Quick Start section intact and the full workflow visible where users look.

**FR-030 reframed**: "The README Quick Start must be accurate and runnable" — same intent as the
original FR-030, simpler delivery. `specs/001-pmlogsynth-phase1/quickstart.md` receives no further
maintenance; it is a historical planning artifact.

**E2E fixture resolution**: Use `good-baseline.yaml` with `-C tests/fixtures/profiles/` for the
quickstart test. The `-C` flag is appropriate here — it's exactly how users with custom hardware
profiles invoke the tool, and the test controls the environment.

---

## 4. Man page gaps (actual vs required)

**Findings** (from direct inspection of `man/pmlogsynth.1`):

| Requirement | Status |
|-------------|--------|
| FR-009: all required sections | ✅ present (YAML PROFILE FORMAT ≈ PROFILES; SUPPORTED METRICS ≈ METRICS) |
| FR-010–FR-015: content completeness | ✅ verified |
| FR-016: SEE ALSO includes pcp(1) | ❌ missing — has pmlogcheck, pmval, pmrep, pmlogdump, pmlogimport but NOT pcp(1) |
| FR-017: repeat:daily cannot-combine warning | ❌ missing explicit warning; repeat:daily is described but the exclusivity constraint lacks a clear "WARNING: cannot be combined" note |
| FR-018: man page installed via pyproject.toml | ❌ pyproject.toml has no `data_files` entry |
| FR-019: CI verifies man ./man/pmlogsynth.1 | ❌ not in ci.yml or pre-commit.sh |

**Patches needed**: 3 small, targeted edits to `man/pmlogsynth.1` + 1 line in pyproject.toml +
1 CI step + 1 local pre-commit.sh step.

---

## 5. README structure: concise front door, not a reference manual

**Decision**: README stays lean (~150 lines max). Reference content lives in dedicated files.
Detailed metrics and profile schema belong in the man page and `docs/` respectively.

**Findings** (from direct inspection of `README.md`, 137 lines):

| Requirement | Revised approach |
|-------------|-----------------|
| Profile Format section | ❌ → new `docs/profile-format.md` with full schema detail; README gets a one-paragraph summary + link |
| Metrics Reference table | ❌ → one-liner in README: *"24 PCP metrics — run `pmlogsynth --list-metrics` or `man pmlogsynth`"*; table belongs in the man page |
| CLI Reference section | ❌ → one-liner: *"See `man pmlogsynth` for the full CLI reference"*; man page already has this at 403 lines |
| Development section | ❌ → new `CONTRIBUTING.md` at repo root; README gets a one-liner link |
| repeat:daily warning | ❌ → detailed warning in `docs/profile-format.md`; one-sentence callout in README Quick Start |
| FR-021: all commands runnable | ✅ current commands look correct |
| FR-023: Hardware Profiles table | ✅ present and accurate — stays in README (7 rows, right size) |
| FR-026: no broken links | ✅ checked; no 404s |
| FR-035: test dir references updated | ❌ Running Tests section still uses tier1/tier2/tier3 — needs rename |
| Quick Start: --validate before generate | ❌ add one-liner preamble to step 2 |

**New files**: `docs/profile-format.md`, `CONTRIBUTING.md`
**README net change**: ~+20 lines (Quick Start tweak + section stubs with links) — stays well under 200 lines.

---

## 6. Test rename: all locations identified

**All files requiring updates** (from exhaustive grep):

| File | Change |
|------|--------|
| `tests/conftest.py` | Marker strings: `tier1` → `unit`, `tier2` → `integration`, `tier3` → `e2e` |
| `pyproject.toml` | `[tool.pytest.ini_options] markers` entries |
| `pre-commit.sh` | `tests/tier1/ tests/tier2/` → `tests/unit/ tests/integration/`; `tests/tier3/` → `tests/e2e/` |
| `.github/workflows/ci.yml` | Same path substitutions |
| `CLAUDE.md` | Project Structure diagram + Commands section |
| `README.md` | Running Tests section |
| `tests/tier1/*.py` | Individual test files with `@pytest.mark.tier1` → `@pytest.mark.unit` |
| `tests/tier2/*.py` | `@pytest.mark.tier2` → `@pytest.mark.integration` |
| `tests/tier3/*.py` | `@pytest.mark.tier3` → `@pytest.mark.e2e` |
| Directory renames | `tests/tier1/` → `tests/unit/`, etc. |

**Grep confirms zero other locations**: SC-009 (zero remaining tier references) is achievable.
