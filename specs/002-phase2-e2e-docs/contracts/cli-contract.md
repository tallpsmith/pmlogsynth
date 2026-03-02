# Contract: CLI Interface

**Feature**: 002-phase2-e2e-docs
**Date**: 2026-03-02

This is the stable CLI surface documented in the man page and README.
No CLI changes in Phase 2 — this contract is the ground truth for documentation
accuracy review (FR-011, FR-024, SC-004).

---

## Commands

```
pmlogsynth [GLOBAL] PROFILE [OPTIONS]        # generate archive (default subcommand)
pmlogsynth generate PROFILE [OPTIONS]        # explicit generate subcommand
pmlogsynth --validate [-C DIR] PROFILE       # validate only, no archive written
pmlogsynth [--config-dir DIR] --list-profiles
pmlogsynth --list-metrics
pmlogsynth --version
```

## Flags

| Flag | Short | Type | Description |
|------|-------|------|-------------|
| `--output` | `-o` | path | Output archive base path (default: `<hostname>`) |
| `--start` | | ISO8601 or "now" | Start time for archive (default: now) |
| `--verbose` | `-v` | flag | Verbose output |
| `--config-dir` | `-C` | dir | Additional hardware profile search directory |
| `--validate` | | flag | Validate profile, exit 0/1, write no archive |
| `--list-profiles` | | flag | List all discoverable hardware profiles, exit 0 |
| `--list-metrics` | | flag | List all 24 supported PCP metric names, exit 0 |
| `--force` | | flag | Overwrite existing archive files |
| `--leave-partial` | | flag | Do not delete partial files on error |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation error (profile invalid) |
| 2 | Usage error (bad arguments) |
| 3 | Generation error (archive write failed) |

## Hardware Profile Resolution Order

1. `-C / --config-dir` directory (highest priority)
2. `~/.pcp/pmlogsynth/profiles/`
3. Bundled package data (lowest priority)
