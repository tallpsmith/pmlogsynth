# PyPI Deployment for pmlogsynth

**Date:** 2026-03-20
**Status:** Approved

## Summary

Add PyPI publishing to pmlogsynth, mirroring the proven pattern from tallpsmith/pmunfi.
Migrate the build backend from setuptools to hatchling + hatch-vcs for git-tag-derived
versioning, and add a GitHub Actions release workflow using OIDC Trusted Publishers.

Package will be published as `pcp-pmlogsynth` on PyPI.

## Decision: Approach A — Full hatchling migration

Chosen over keeping setuptools (Approach B) or hatchling without VCS versioning
(Approach C) for consistency with pmunfi and to eliminate manual version bumping.

RPM/Debian packaging explicitly deferred — PyPI only for now.

## Section 1: Build System Migration

### pyproject.toml

- Replace build-system from `setuptools` to `hatchling` + `hatch-vcs`
- Change `name` from `pmlogsynth` to `pcp-pmlogsynth`
- Replace `version = "0.1.0"` with `dynamic = ["version"]`
- Add `[tool.hatch.version]` with `source = "vcs"`
- Add `[tool.hatch.build.hooks.vcs]` to auto-generate `pmlogsynth/_version.py`
- Use `local_scheme = "no-local-version"` (PyPI rejects local version segments)
- Tag pattern: default `v*` prefix — hatch-vcs strips the `v` automatically
- Man page installation: migrate from setuptools `data-files` to hatchling's
  `[tool.hatch.build.targets.wheel.shared-data]` which maps files into the
  wheel's data directory. pip installs them to the correct location:
  ```toml
  [tool.hatch.build.targets.wheel.shared-data]
  "man/pmlogsynth.1" = "share/man/man1/pmlogsynth.1"
  ```
- Package data (`profiles/*.yaml`, `schema_context.md`): hatchling includes all
  tracked files by default, so these are automatically included. Verify during
  implementation that the built wheel contains them.

### pmlogsynth/__init__.py

- Replace hardcoded `__version__ = "0.1.0"` with import from `_version.py`
- Fallback pattern for editable installs / pre-build state:
  ```python
  try:
      from pmlogsynth._version import __version__
  except ImportError:
      __version__ = "0.0.0+unknown"
  ```

### pmlogsynth/_version.py

- Auto-generated at build time by hatch-vcs
- Added to `.gitignore` — never committed

### cli.py

- **Required change:** `cli.py` currently has a hardcoded `version="%(prog)s 0.1.0"`.
  This must be updated to import and use `__version__` from `pmlogsynth.__init__`.

### PCP system dependency notice

`python3-pcp` is not pip-installable. Users who `pip install pcp-pmlogsynth` need
PCP installed separately. Address this via:
- Prominent note in the PyPI long-description (README.md) stating the system dependency
- A runtime check in `cli.py` (or `writer.py`) that produces a helpful error message
  if `pcp` is not importable, rather than a raw ImportError traceback

### Build environment vs runtime target

`requires-python = ">=3.8"` is the runtime target. The build environment (GitHub Actions)
uses a newer Python. Pin `hatch-vcs` to a version compatible with Python 3.8 runtime
if any build-time generated code must run on 3.8. In practice, `_version.py` is pure
string assignment and has no compatibility concerns.

## Section 2: Release Workflow

### .github/workflows/release.yml

**Trigger:** `on: release: types: [published]`

**Job 1 — validate:**
- Checkout with `fetch-depth: 0`, `fetch-tags: true`
- Install `hatch` CLI (not just `hatchling` library) — needed for `hatch version`
- Normalize git tag through `packaging.version.Version` (strip `v` prefix first)
- Compare against `hatch version` output
- Fail on mismatch

**Job 2 — pypi:**
- Depends on validate passing
- Checkout, `python -m build` (sdist + wheel)
- Publish via `pypa/gh-action-pypi-publish@release/v1`

**Auth:** OIDC Trusted Publisher
- Workflow declares `id-token: write` permission
- Uses `environment: pypi` on the publish job
- No API tokens or secrets required

## Section 3: Repository & PyPI Setup (Manual, One-Time)

### GitHub
- Create `pypi` environment in repo Settings > Environments

### PyPI
- Register pending publisher for `pcp-pmlogsynth`:
  - Owner: `tallpsmith`
  - Repository: `pmlogsynth`
  - Workflow: `release.yml`
  - Environment: `pypi`

### First Release — TestPyPI dry-run recommended
- First publish should target TestPyPI to verify OIDC plumbing works before
  burning the `pcp-pmlogsynth` 0.1.0 version number on real PyPI (version
  numbers are permanent and cannot be re-uploaded if something goes wrong)
- After TestPyPI success: tag `v0.1.0`, create GitHub Release, workflow fires

## Files Changed

| Change | Files |
|---|---|
| Build backend migration | `pyproject.toml` |
| Dynamic version import | `pmlogsynth/__init__.py` |
| Fix hardcoded version | `pmlogsynth/cli.py` |
| Ignore generated version file | `.gitignore` |
| Release workflow | `.github/workflows/release.yml` |

## Out of Scope

- RPM/Debian packaging (deferred)
- Ongoing TestPyPI publishing (one-time dry-run recommended above)
- Changelog generation
- Changes to existing tests or domain code
