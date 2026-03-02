# Contract: CLI Interface

**Tool**: `pmlogsynth`
**Source**: `pmlogsynth/cli.py`
**Date**: 2026-03-01

This document is the authoritative contract for the `pmlogsynth` command-line interface.
The man page (`man/pmlogsynth.1`) MUST stay consistent with this document (FR-049).

---

## Invocation Model

`pmlogsynth` uses argparse subparsers from day one to accommodate the Phase 3 `fleet`
subcommand without refactoring (FR-041, D-002).

```
pmlogsynth [GLOBAL OPTIONS] <subcommand> [SUBCOMMAND OPTIONS] [ARGS]
```

The default subcommand (when none is given) is `generate`. Users do NOT need to type
`pmlogsynth generate` — `pmlogsynth profile.yaml` works directly.

**Reserved subcommand names**: `fleet` (Phase 3), `generate` (default/implicit).

---

## Global Options (available before any subcommand)

| Flag | Description |
|------|-------------|
| `-V`, `--version` | Print version and exit |
| `-h`, `--help` | Print help and exit |

---

## Default Command: generate (implicit)

Generate a PCP archive from a YAML workload profile.

```
pmlogsynth [OPTIONS] PROFILE
```

| Argument/Flag | Type | Default | Description |
|---------------|------|---------|-------------|
| `PROFILE` | positional | required | Path to YAML workload profile file |
| `-o`, `--output PATH` | str | `./pmlogsynth-out` | Output archive base name |
| `--start TIMESTAMP` | str | `now - meta.duration` | Archive start time (ISO 8601 or `YYYY-MM-DD HH:MM:SS TZ`) |
| `-v`, `--verbose` | flag | off | Print per-sample metric values to stderr |
| `--validate` | flag | off | Validate profile only; exit without generating any files |
| `--force` | flag | off | Overwrite existing archive files without error |
| `--leave-partial` | flag | off | On failure, leave partial files; print warning identifying them |
| `-C`, `--config-dir PATH` | str | None | Additional hardware profile directory (highest precedence) |
| `-h`, `--help` | flag | — | Print help and exit |

**Conflict rules**:
- `--validate` is incompatible with `-o`, `--start`, `--force`, `--leave-partial`
  (validate exits before writing; these flags are meaningless)

---

## Informational Commands

These commands print information and exit immediately without reading a profile file.

### `--list-profiles`

```
pmlogsynth [--config-dir DIR] --list-profiles
```

Lists all available hardware profiles with source label.

**Output format** (stdout):
```
SOURCE      NAME
bundled     compute-optimized
bundled     generic-large
bundled     generic-medium
bundled     generic-small
bundled     generic-xlarge
bundled     memory-optimized
bundled     storage-optimized
user        my-server
config-dir  test-profile
```

- Sorted alphabetically within each source group
- Source labels: `bundled`, `user`, `config-dir`
- Respects `-C / --config-dir` for including config-dir entries (FR-025)
- All output goes to stdout; exit 0

### `--list-metrics`

```
pmlogsynth --list-metrics
```

Lists all PCP metric names the tool can produce. One metric name per line, no formatting.

**Output format** (stdout):
```
disk.all.read
disk.all.read_bytes
disk.all.write
disk.all.write_bytes
disk.dev.read_bytes
disk.dev.write_bytes
kernel.all.cpu.idle
kernel.all.cpu.steal
kernel.all.cpu.sys
kernel.all.cpu.user
kernel.all.cpu.wait.total
kernel.all.load
kernel.percpu.cpu.idle
kernel.percpu.cpu.sys
kernel.percpu.cpu.user
mem.physmem
mem.util.bufmem
mem.util.cached
mem.util.free
mem.util.used
network.interface.in.bytes
network.interface.in.packets
network.interface.out.bytes
network.interface.out.packets
```

- Sorted lexicographically
- All output goes to stdout; exit 0
- MUST be consistent with man page metric list (FR-049)

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (archive generated, validation passed, or informational command completed) |
| 1 | Validation error (profile schema, constraint violation, unknown hardware profile) |
| 2 | I/O error (output path not writable, output files already exist, `-C` dir not found) |
| 3 | Generation error (error during archive writing; partial files deleted unless `--leave-partial`) |

**Stderr**: All error messages go to stderr. Successful operation produces no stderr output
unless `-v` / `--verbose` is set. `--leave-partial` warning also goes to stderr (FR-052).

---

## Output Files

On success, the generate command creates exactly three files:

| File | Description |
|------|-------------|
| `<output>.0` | PCP data volume |
| `<output>.index` | Temporal index |
| `<output>.meta` | Metric metadata |

**Pre-existence check** (FR-053): If any of the three files exists at the target path,
the tool exits with code 2 and a message identifying all conflicting files. Nothing is
written. `--force` suppresses this check and overwrites silently.

**Partial cleanup** (FR-051): If an error occurs after writing has started, all partially
written files are deleted and the tool exits with code 3. The error message lists which
files were removed. If deletion itself fails, both the generation error and deletion
failure are reported to stderr.

---

## --validate Mode

```
pmlogsynth --validate profile.yaml
pmlogsynth --validate -C ./test-profiles profile.yaml
```

- Loads and fully validates the profile (schema, constraints, hardware profile resolution)
- Prints nothing to stdout on success
- Prints a specific error message to stderr on failure, identifying the violated constraint
- Exits 0 on valid profile, 1 on invalid
- Does NOT create any files

---

## --start Format

The `--start` argument accepts:
- ISO 8601: `2024-01-15T09:00:00Z`, `2024-01-15T09:00:00+00:00`
- Human-readable: `"2024-01-15 09:00:00 UTC"`, `"2024-01-15 09:00:00"`
- Future timestamps: accepted without warning

Default: `now - meta.duration` (archive ends approximately at the time of generation).

---

## Phase 3 Reserved Interface

The CLI MUST NOT conflict with the following future subcommand:

```
pmlogsynth fleet [OPTIONS] FLEET_PROFILE
```

The `fleet` name is reserved in argparse subparsers from Phase 1. If `fleet` is passed
as the first positional argument, the tool MUST emit a clear "not yet implemented" error
rather than attempting to open it as a profile file.
