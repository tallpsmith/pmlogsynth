# Data Model: Developer Experience Improvements

**Branch**: `003-dx-improvements` | **Date**: 2026-03-02

This feature contains no persistent data models or schema changes. The "entities" are
in-script state within `pre-commit.sh` — transient bash data structures used during a
single gate run.

---

## Prerequisite Check State

### MISSING Array

Bash array accumulating human-readable failure strings during the prerequisite check phase.

```
MISSING[]
  type: array of strings
  scope: local to check_prerequisites() function
  lifecycle: populated during check, consumed at report step, script exits if non-empty
  element format: "<short-label>: <explanation>\n  Fix: <exact command>"
```

**Population rules**:
- Each distinct missing prerequisite produces exactly one entry
- `cpmapi` and `pcp.pmi` each produce a separate entry (FR-004)
- "ruff", "mypy", "pytest" each produce a separate entry (FR-002)
- venv absence produces one entry with macOS-aware venv creation guidance

**Exit semantics**:
- `len(MISSING) == 0` → fall through to quality gates
- `len(MISSING) > 0` → print all entries, exit 1; quality gates never run

---

## Man Page Check Inputs

No persistent state. Inputs are:

| Input | Source | Validation |
|-------|--------|------------|
| `man/pmlogsynth.1` | Filesystem path (relative to repo root) | File must exist |
| Formatter tool | PATH lookup: mandoc → groff → none | Tool presence determines validation depth |

**Output semantics**:
- File absent → exit 1, stderr: "ERROR: man/pmlogsynth.1 not found"
- File present, mandoc available → `mandoc -T lint`, exit code propagated
- File present, groff available, no errors in stderr → exit 0
- File present, groff available, "error" in stderr → exit 1, print captured stderr
- File present, no formatter → exit 0 with warning to stderr (FR-009)

---

## No Schema Changes

- `pyproject.toml`: no changes
- Profile YAML schema: no changes
- Python package modules: no changes
- CI workflow (`ci.yml`): add `apt install mandoc` to `quality` job only
