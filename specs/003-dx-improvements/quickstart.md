# Quickstart: What Changes for Contributors

**Branch**: `003-dx-improvements` | **Date**: 2026-03-02

This document describes the experience changes for contributors after this feature ships.

---

## New Contributor Experience (P1 — was broken, now fixed)

**Before**: Fresh clone → `./pre-commit.sh` → `ruff: command not found` (cryptic, no guidance)

**After**: Fresh clone → `./pre-commit.sh` → clear list of what is missing and exactly how to fix it:

```
=== prerequisite check failed ===

MISSING: no virtualenv active
  pre-commit.sh requires a Python virtualenv created from pmpython.
  Fix (macOS):  $(readlink -f $(which pmpython)) -m venv .venv && source .venv/bin/activate
  Fix (Linux):  python3 -m venv .venv && source .venv/bin/activate

MISSING: pmpython not on PATH
  PCP is a hard dependency. Install it first.
  Fix (Debian/Ubuntu):  sudo apt-get install pcp python3-pcp
  Fix (RHEL/Fedora):    sudo dnf install pcp python3-pcp
  Fix (macOS):          brew install pcp
```

The script exits non-zero. No quality checks run until all prerequisites are satisfied.

---

## CI Experience (P2 — was broken, now fixed)

**Before**: `./pre-commit.sh` in CI or during rapid iteration → man page check opens `less` pager,
blocks indefinitely waiting for `q` key.

**After**: Man page check runs non-interactively:

```
=== man page check ===
# valid file: silent exit 0
# invalid file: mandoc lint output to stderr, exit 1
# missing file: "ERROR: man/pmlogsynth.1 not found", exit 1
```

---

## README Change (P3 — documentation cleanup)

**Before**: README.md contained a "Running Tests" section with pytest commands — noise for
end-users who just want to run the tool.

**After**: README.md covers only what a user needs: installation, quick start, profiles,
metrics, CLI reference. pytest instructions live exclusively in CONTRIBUTING.md.

```
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, test structure, and PR conventions.
```

---

## Setup Checklist (post-feature)

For a new macOS contributor:

```bash
# 1. Install PCP via Homebrew
brew install pcp

# 2. Create venv from Homebrew's Python (the one PCP compiled against)
$(readlink -f $(which pmpython)) -m venv .venv
source .venv/bin/activate

# 3. Install dev dependencies
pip install -e ".[dev]"

# 4. Run the gate
./pre-commit.sh
# Expected: all checks pass, exit 0
```

For a new Linux (Ubuntu) contributor:

```bash
# 1. Install PCP
sudo apt-get install pcp python3-pcp

# 2. Create venv
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dev dependencies
pip install -e ".[dev]"

# 4. Run the gate
./pre-commit.sh
# Expected: all checks pass, exit 0
```
