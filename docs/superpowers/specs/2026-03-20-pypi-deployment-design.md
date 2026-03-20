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
- Migrate package-data and man-page data-files to hatchling format

### pmlogsynth/__init__.py

- Replace hardcoded `__version__ = "0.1.0"` with import from `_version.py`
- Include fallback for editable installs before first build

### pmlogsynth/_version.py

- Auto-generated at build time by hatch-vcs
- Added to `.gitignore` — never committed

### cli.py

- Version display (`--version`) reads from `__init__.__version__` — verify chain works

## Section 2: Release Workflow

### .github/workflows/release.yml

**Trigger:** `on: release: types: [published]`

**Job 1 — validate:**
- Checkout with `fetch-depth: 0`, `fetch-tags: true`
- Normalize git tag through `packaging.version.Version`
- Compare against `hatchling version` output
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

### First Release
- Tag `v0.1.0` on the target commit
- Create GitHub Release from the tag
- Workflow fires automatically

## Files Changed

| Change | Files |
|---|---|
| Build backend migration | `pyproject.toml` |
| Dynamic version import | `pmlogsynth/__init__.py` |
| Ignore generated version file | `.gitignore` |
| Release workflow | `.github/workflows/release.yml` |

## Out of Scope

- RPM/Debian packaging (deferred)
- TestPyPI publishing (can add later)
- Changelog generation
- Changes to existing CI, tests, or domain code
