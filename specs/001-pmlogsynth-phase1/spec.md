# Feature Specification: pmlogsynth Phase 1 — Synthetic PCP Archive Generator

**Feature Branch**: `001-pmlogsynth-phase1`
**Created**: 2026-02-28
**Status**: Draft
**Input**: Implement Phase 1 of pmlogsynth — the core synthetic PCP archive generation tool, with awareness of Phase 2 (natural language profile generation) and Phase 3 (fleet archive generation) to follow.

---

## Clarifications

### Session 2026-03-01

- Q: What should `pre-commit.sh` run? → A: Tier 1 + Tier 2 always; Tier 3 if PCP library is detected. Single exit code covering all runnable tiers.
- Q: What happens to partial archive files when generation fails mid-way? → A: Delete all partial output files by default; add `--leave-partial` flag to preserve them for post-failure inspection.
- Q: What should happen if output archive files already exist at the specified path? → A: Fail with a clear error identifying the conflicting files. Provide `--force` to explicitly permit overwrite.
- Q: What happens if the first phase in a profile specifies `transition: linear`? → A: Validation error — no prior phase exists to interpolate from; reject with a clear message.
- Q: What happens if a workload profile specifies both `host.profile` and inline host fields? → A: An explicit `overrides:` sub-key is required to override named profile fields. Bare inline fields alongside `host.profile` (without `overrides:`) are a validation error. Consistent with Phase 3 overlay semantics.
- Q: Does CI run E2E tests, and if so, how is PCP made available in CI? → A: Install PCP via `apt` on a GitHub Actions `ubuntu-latest` runner; run all three tiers. The Linux runner also provides cross-platform validation coverage for macOS-primary developers.
- Q: What events trigger the GitHub CI workflow? → A: Push to any branch and pull requests targeting `main`.
- Q: Should CI validate Python version compatibility across the stated 3.8+ range? → A: Yes, using a matrix for Tier 1 and Tier 2 (Python 3.8 + latest stable). Tier 3 E2E runs on the system Python that the `apt` PCP package was built against — the version must match PCP's own bindings, not be freely chosen.
- Q: Does CI add quality gates beyond the three test tiers (e.g. linting, type checking)? → A: Yes — static analysis and type checking MUST run in both `pre-commit.sh` and the GitHub CI workflow. The same quality gates apply locally and in CI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a Synthetic PCP Archive from a YAML Profile (Priority: P1)

A PCP tool developer or QA engineer has a PCP analysis tool, alerting rule, or dashboard that they need to test. They author a YAML workload profile describing the host hardware and a timeline of performance phases, then run `pmlogsynth` to produce a valid PCP archive. They immediately replay the archive with standard PCP tools (`pmval`, `pmrep`, `pmlogcheck`) to verify their tooling behaves correctly.

**Why this priority**: This is the entire raison d'être of the tool. Without this working, nothing else matters. Everything downstream (Phase 2, Phase 3, CI pipelines) depends on correct archive generation.

**Independent Test**: Author a minimal YAML profile specifying a 2-phase workload (baseline + CPU spike) on a `generic-small` host, run `pmlogsynth`, and confirm the output passes `pmlogcheck` and `pmval` returns values within the expected range for `kernel.all.cpu.user`.

**Acceptance Scenarios**:

1. **Given** a valid YAML profile with a `host.profile: generic-small`, a 10-minute baseline (15% CPU) and a 5-minute spike (90% CPU), **When** `pmlogsynth -o ./out profile.yaml` is run, **Then** three archive files (`out.0`, `out.index`, `out.meta`) are created and `pmlogcheck ./out` exits zero.
2. **Given** the generated archive, **When** `pmval -a ./out kernel.all.cpu.user` is replayed, **Then** values during the spike phase are within ±5% of 90%.
3. **Given** a profile with `--start "2024-01-15 09:00:00 UTC"`, **When** the archive is generated, **Then** the archive's start timestamp matches the specified time.
4. **Given** a profile where `user_ratio + sys_ratio + iowait_ratio > 1.0`, **When** `pmlogsynth` attempts to process it, **Then** it exits non-zero with a clear validation error message identifying the constraint violation.

---

### User Story 2 - Validate a Profile Without Generating Output (Priority: P2)

A developer writing or editing a YAML workload profile wants to check it for correctness before committing to the time cost of generating a full archive. They run `pmlogsynth --validate profile.yaml` to get immediate feedback on any schema violations or constraint failures.

**Why this priority**: Profile validation is critical for fast iteration and CI pipeline usage. A profile library without validation is an unmaintained profile library.

**Independent Test**: Run `pmlogsynth --validate` against a known-bad profile (ratio constraint violated) and a known-good profile; confirm correct exit codes and appropriate error messages in each case.

**Acceptance Scenarios**:

1. **Given** a profile with valid structure and all constraints satisfied, **When** `pmlogsynth --validate profile.yaml` is run, **Then** it exits zero with no error output.
2. **Given** a profile where `meta.duration` does not equal the sum of phase durations (and no `repeat` key is used), **When** validated, **Then** it exits non-zero with a message identifying which constraint failed.
3. **Given** a profile referencing `host.profile: nonexistent-profile`, **When** validated, **Then** it exits non-zero with a message identifying the unknown profile name.
4. **Given** a profile with a `noise` value outside [0.0, 1.0], **When** validated, **Then** it exits non-zero with a specific error on the offending field.

---

### User Story 3 - Use Named Hardware Profiles (Priority: P2)

A user wants to simulate a specific tier of host without manually specifying CPU count, RAM, disk devices, and network interfaces. They reference a named bundled hardware profile (`generic-large`, `compute-optimized`, etc.) in their workload profile. Advanced users place custom hardware profiles in `~/.pcp/pmlogsynth/profiles/` to model their specific infrastructure. Test authors and CI pipelines supply an additional profile directory via `-C <dir>` to inject test-specific hardware profiles without polluting the user's home directory or the bundled profile set.

**Why this priority**: Hardware profiles are what make workload profiles reusable and composable. Without them, every profile would embed hardware specs inline, making the profile library unmaintainable. The `-C` override is what makes integration tests self-contained and reproducible.

**Independent Test**: Run `pmlogsynth --list-profiles` and confirm all 7 bundled profiles appear. Run `pmlogsynth -C ./tests/fixtures/profiles --list-profiles` and confirm test-only profiles appear without modifying `~/.pcp/pmlogsynth/profiles/`. Author a profile using `host.profile: generic-large` and confirm the archive contains 8 per-CPU metric instances.

**Acceptance Scenarios**:

1. **Given** the tool is installed, **When** `pmlogsynth --list-profiles` is run, **Then** all 7 bundled profiles are listed with their source (bundled vs. user-defined) and key specs.
2. **Given** a user places a file `~/.pcp/pmlogsynth/profiles/my-server.yaml`, **When** `--list-profiles` is run, **Then** `my-server` appears and is marked as user-defined.
3. **Given** both a bundled profile and a user profile share the same name, **When** the shared name is referenced in a workload profile, **Then** the user's profile takes precedence.
4. **Given** a workload profile uses `host.profile: generic-large` (8 CPUs), **When** the archive is generated and `pmval -a ./out kernel.percpu.cpu.user` is queried, **Then** 8 CPU instances are present.
5. **Given** a directory of test-specific hardware profiles supplied via `-C ./tests/fixtures/profiles`, **When** a workload profile references a profile name defined only in that directory, **Then** the profile is resolved correctly and the archive is generated without requiring that profile to exist in `~/.pcp/pmlogsynth/profiles/` or in the bundled set.
6. **Given** a profile name exists in both the `-C` directory and a lower-precedence source, **When** that name is resolved, **Then** the `-C` directory takes precedence over both the user home directory and bundled profiles.

---

### User Story 4 - Use Multi-Phase Timelines with Transitions and Repeating Phases (Priority: P2)

A developer wants to model complex workload patterns: a gradual ramp into a peak load (linear transition), or a recurring daily pattern (repeat: daily) without copy-pasting phases. They use the `transition` and `repeat` keys in their profile to express these patterns declaratively.

**Why this priority**: Without transitions and repeats, users can only model step-function workloads, which do not represent real workload patterns. This is required to make the tool useful for realistic archive generation.

**Independent Test**: Author a profile with a `recovery` phase using `transition: linear` and verify that metric values in the generated archive interpolate smoothly between the spike and recovery target values, rather than stepping immediately.

**Acceptance Scenarios**:

1. **Given** a phase with `transition: linear`, **When** the archive is generated, **Then** metric values during that phase interpolate linearly from the previous phase's final values to the current phase's target values.
2. **Given** a phase with `repeat: daily`, **When** the timeline is expanded, **Then** the phase repeats with baseline fill between repetitions to satisfy `meta.duration`.
3. **Given** a profile where `repeat: daily` is used and `meta.duration` cannot accommodate the full expanded timeline, **When** validated, **Then** it exits non-zero with a clear error.
4. **Given** a phase with no `transition` key, **When** the archive is generated, **Then** values jump immediately (instant transition) at the phase boundary.

---

### User Story 5 - Discover What Metrics the Tool Produces (Priority: P3)

A developer working with `pmlogsynth` wants a quick reminder of which PCP metric names the tool can generate — for example, to write correct assertions in a test, or to check whether a metric they need is supported — without having to open the man page. They run `pmlogsynth --list-metrics` and get an immediate, unambiguous list they can copy directly into a profile or assertion.

**Why this priority**: The metric set is fixed and bounded; it's implied by the five supported domains. The man page is the authoritative reference. `--list-metrics` is a convenience shortcut for users already familiar with the tool. It delivers no new capability, just faster access to existing information.

**Independent Test**: Run `pmlogsynth --list-metrics` and confirm the output lists at least one metric name from each of the five domains (CPU, memory, disk, network, load average), with no extraneous text.

**Acceptance Scenarios**:

1. **Given** the tool is installed, **When** `pmlogsynth --list-metrics` is run, **Then** all PCP metric names the tool can produce are printed to stdout, one per line, with no additional formatting.
2. **Given** the output of `--list-metrics`, **When** a metric name from that list is used in a `pmval -a` command against a generated archive, **Then** `pmval` returns data without an "unknown metric" error.
3. **Given** archive generation fails for any reason, **When** `pmlogsynth` exits, **Then** the exit code is non-zero and a human-readable error is printed to stderr.

---

### Edge Cases

- What happens when `meta.duration` is zero or negative?
- What if a phase duration is zero?
- What if the output directory does not exist or is not writable?
- What if a user's hardware profile is malformed YAML (a parse error, not a schema violation)?
- What happens when `repeat: daily` is applied to a phase longer than 24 hours?
- How are counter values handled when Gaussian noise could push a rate increment negative?
- What if per-CPU utilisation values, after per-CPU variance is applied, do not sum to total ticks?
- What if `--start` specifies a future timestamp?
- What if `-C` is specified but the directory does not exist or is not readable?
- What if partial file deletion itself fails during cleanup (e.g. permission error)? Tool should report the deletion failure alongside the original generation error.
- What if only some of the three archive files exist (e.g. `.0` present but `.index` and `.meta` absent)? The existence check must cover all three files individually — any pre-existing file is a conflict.
- What if the same profile name appears in both the `-C` directory and `~/.pcp/pmlogsynth/profiles/`? (Answer: `-C` wins — this is the defined precedence and enables clean test overrides.)

---

## Requirements *(mandatory)*

### Functional Requirements

**Archive Generation**

- **FR-001**: The tool MUST produce valid PCP v3 archive files (`.0`, `.index`, `.meta`) that pass `pmlogcheck` without error.
- **FR-002**: Generated archives MUST be usable with standard PCP tooling (`pmval`, `pmrep`, `pmlogdump`, `pmlogsummary`) without modification.
- **FR-003**: The tool MUST NOT require a running `pmcd`, real hardware, or root access to generate archives.
- **FR-004**: Archives MUST use real PCP metric identifiers, units, and semantics as defined in the installed PCP PMDA.
- **FR-005**: Archive start time MUST default to `now - meta.duration` unless `--start` is provided.

**Metric Domains**

- **FR-006**: The tool MUST generate consistent CPU metrics (`kernel.all.cpu.*`, `kernel.percpu.cpu.*`) such that `user + sys + idle + wait + steal == total_ticks` per CPU per sample interval.
- **FR-007**: CPU metrics MUST be cumulative counters (milliseconds) so rate-based PCP tools produce correct rates on replay.
- **FR-008**: The tool MUST generate consistent memory metrics (`mem.util.*`) such that `used + free == physmem` at every sample.
- **FR-009**: Disk metrics (`disk.all.*`, `disk.dev.*`) MUST be cumulative byte and operation counters, split across named device instances from the hardware profile.
- **FR-010**: Network metrics (`network.interface.*`) MUST be cumulative byte and packet counters, split across named interface instances from the hardware profile.
- **FR-011**: Load average metrics (`kernel.all.load`) MUST be derived from CPU utilisation using UNIX exponential smoothing constants for 1-, 5-, and 15-minute averages.
- **FR-012**: Gaussian noise MUST be applied to metric values; the noise factor MUST be configurable globally (`meta.noise`) and overridable per domain within a phase.
- **FR-013**: Gaussian noise MUST NOT produce negative counter increments; noise application MUST clamp values to valid ranges before accumulation.

**Profile Format**

- **FR-014**: The tool MUST accept a YAML workload profile as its primary input.
- **FR-015**: The profile MUST support `meta` (hostname, timezone, duration, interval, noise), `host` (hardware profile reference or inline spec), and `phases` (workload timeline).
- **FR-015a**: The `host` block MUST support three mutually exclusive forms: (1) `host.profile` alone — use a named profile as-is; (2) `host.profile` + `host.overrides` — use a named profile as base and apply per-field overrides from the `overrides` sub-block; (3) inline fields without `host.profile` — fully inline host specification. Specifying `host.profile` alongside bare inline fields without an `overrides:` key MUST be a validation error with a message directing the author to use `overrides:`.
- **FR-016**: Each phase MUST support stressor fields for CPU (`utilization`, `user_ratio`, `sys_ratio`, `iowait_ratio`), memory (`used_ratio`, `cache_ratio`), disk (`read_mbps`, `write_mbps`, `iops_read`, `iops_write`), and network (`rx_mbps`, `tx_mbps`).
- **FR-017**: Phase transitions MUST support `instant` (default) and `linear` (interpolates over the full phase duration from prior phase end values).
- **FR-018**: Phases MUST support a `repeat` key with values `daily` or an integer count; the timeline sequencer MUST expand repeats before writing begins.
- **FR-019**: Per-domain noise override (`noise:` key within a domain block in a phase) MUST override `meta.noise` for that domain in that phase only.
- **FR-020**: Stressor fields MUST be individually optional; defaults MUST be applied at value-computation time, not at parse time, so that absent fields are distinguishable from explicitly set fields (required for Phase 3 overlay merging).

**Hardware Profiles**

- **FR-021**: The tool MUST ship with 7 bundled hardware profiles: `generic-small`, `generic-medium`, `generic-large`, `generic-xlarge`, `compute-optimized`, `memory-optimized`, `storage-optimized`.
- **FR-022**: Users MUST be able to define custom hardware profiles in `~/.pcp/pmlogsynth/profiles/`; user-defined profiles MUST take precedence over bundled profiles of the same name.
- **FR-023**: The tool MUST accept a `-C / --config-dir` option specifying an additional hardware profile directory; profiles in this directory MUST take precedence over both the user home directory and bundled profiles.
- **FR-024**: Hardware profile lookup MUST follow this precedence order (highest to lowest): `-C` directory → `~/.pcp/pmlogsynth/profiles/` → bundled package data.
- **FR-025**: `--list-profiles` MUST display the source directory for each profile (including `-C` directory entries), labelled distinctly from user-defined and bundled profiles.

**Validation**

- **FR-026**: The tool MUST validate that `user_ratio + sys_ratio + iowait_ratio ≤ 1.0` in every CPU phase block.
- **FR-027**: The tool MUST validate that the sum of phase durations equals `meta.duration` when no `repeat` key is present.
- **FR-028**: The tool MUST validate that `host.profile` resolves to a known hardware profile name (using the full precedence chain, including any `-C` directory).
- **FR-029**: The tool MUST validate that all `noise` values are in [0.0, 1.0].
- **FR-030**: The tool MUST validate that `interval` is a positive integer in seconds.
- **FR-031**: The tool MUST validate that `repeat: daily` phases fit within `meta.duration` when expanded.
- **FR-055**: The tool MUST reject a profile where the first phase specifies `transition: linear`, with a validation error explaining that no prior phase exists to interpolate from.

**CLI**

- **FR-032**: The tool MUST provide a `--validate` flag that validates the profile and exits without generating any archive files.
- **FR-033**: The tool MUST provide a `--list-profiles` flag that lists all available hardware profiles (bundled, user-defined, and `-C` directory) with source indicated.
- **FR-034**: The tool MUST provide a `--list-metrics` flag that prints all PCP metric names the tool can produce.
- **FR-035**: The tool MUST provide `-o / --output` to specify the archive base name (default: `./pmlogsynth-out`).
- **FR-036**: The tool MUST provide `--start` to specify archive start time.
- **FR-037**: The tool MUST provide `-v / --verbose` to print per-sample values to stderr.
- **FR-038**: The tool MUST provide `-C / --config-dir` to specify an additional hardware profile directory that takes highest precedence in profile lookup.
- **FR-039**: All errors MUST be written to stderr; successful output MUST NOT be mixed with error output.
- **FR-051**: If archive generation fails after any output files have been written, the tool MUST delete all partially-written output files and exit non-zero, reporting which files were removed.
- **FR-053**: If any of the three output archive files already exist at the specified output path, the tool MUST exit non-zero with a clear error identifying the conflicting files before writing anything.
- **FR-054**: The tool MUST provide a `--force` flag that permits overwriting existing archive files. When `--force` is used and files are overwritten, no warning is required.
- **FR-052**: The tool MUST provide a `--leave-partial` flag that suppresses cleanup on failure, leaving partial output files in place for post-failure inspection. When `--leave-partial` is active and cleanup is skipped, the tool MUST print a warning identifying the partial files.
- **FR-040**: The tool MUST exit non-zero on any validation or generation failure, and zero on success.
- **FR-041**: The CLI MUST be structured to accommodate a `fleet` subcommand without refactoring in Phase 3 (argparse subparsers from the start).

**Documentation**

- **FR-048**: The tool MUST ship a `pmlogsynth(1)` man page following PCP man page conventions, documenting all CLI flags, the YAML profile format, the full set of supported PCP metrics per domain, hardware profile schema, constraint rules, and usage examples.
- **FR-049**: `--list-metrics` output MUST be consistent with the metric names documented in the man page; the two MUST never diverge.

**Internal Architecture (Phase-aware)**

- **FR-042**: `ProfileLoader` MUST expose both `from_file(path)` and `from_string(yaml_text)` class methods; `from_file` MUST delegate to `from_string` internally.
- **FR-043**: `ValueSampler` MUST accept an optional PRNG seed parameter to support deterministic archive generation (required by Phase 3 `--seed`). No user-facing `--seed` flag is required in Phase 1.

**Testing**

The test suite MUST be structured in three tiers to maximise fast-feedback iteration:

- **FR-044**: **Tier 1 — Unit tests** MUST run on any Python 3.8+ system with no PCP packages installed. They cover profile loading, validation, timeline sequencing, phase transitions, repeat expansion, noise application, counter accumulation, and all domain consistency constraints — verified at value-computation level, with no archive write required.
- **FR-045**: **Tier 2 — Integration tests** MUST stub or mock the `libpcp_import` / `pcp.pmi` layer so that the full archive-generation pipeline (from parsed profile through to the writer) can be tested without PCP being installed. These tests verify that the writer is called with correct metric names, correct values, and correct timestamps — without requiring a real PCP library on the test runner.
- **FR-046**: **Tier 3 — E2E tests** MUST be automatically detected and conditionally run based on whether the underlying PCP library (`pcp.pmi` / `libpcp_import`) can be successfully imported at test-suite startup — not merely whether `pmlogcheck` is on `PATH`. If the library is not importable, all Tier 3 tests MUST be skipped with a clearly visible warning (e.g., `WARNING: PCP library not available — E2E tests skipped`). When PCP is present, they generate a real archive from a known profile, run `pmlogcheck`, and assert metric values via `pmval`. These are the only tests that depend on a real PCP installation.
- **FR-047**: Tier 2 and Tier 3 tests MUST use `-C` to supply test-specific hardware profiles from a fixtures directory, so no test depends on or modifies `~/.pcp/pmlogsynth/profiles/`.
- **FR-050**: The repository MUST ship a `pre-commit.sh` script at the repository root that serves as a single local quality gate. It MUST run static analysis (linting) and static type checking unconditionally, followed by Tier 1 and Tier 2 tests unconditionally, and Tier 3 automatically if the PCP library is detected. It MUST exit non-zero if any runnable check or tier fails, and print a visible warning (not an error) when Tier 3 is skipped due to PCP being absent. Specific tool choices (linter, type checker) are an implementation detail deferred to planning.
- **FR-056**: The repository MUST ship a GitHub Actions workflow (`.github/workflows/ci.yml`) that triggers on push to any branch and on pull requests targeting `main`. The workflow MUST run static analysis, type checking, Tier 1 tests, and Tier 2 tests in a matrix across Python 3.8 and the latest stable Python release to validate the stated minimum version support. Tier 3 E2E tests MUST run separately on the system Python provided by the `ubuntu-latest` runner (i.e., the Python version the `apt` PCP package was built against), since the `python3-pcp` bindings are linked against that specific interpreter. The Linux runner provides cross-platform validation coverage alongside local macOS development.

### Key Entities

- **WorkloadProfile**: A YAML document describing `meta`, `host`, and `phases`. The authoritative input to the tool. Must support construction from both file and string (for Phase 2 `--run` integration).
- **HardwareProfile**: Named YAML document specifying CPU count, memory, disk devices, and network interfaces. Bundled in package data; user-extensible. Schema is frozen after Phase 1 and treated as a stable contract for Phase 2 and Phase 3.
- **Phase**: A named time segment within the workload timeline, with stressor values, optional transition type, and optional repeat count. Expanded into a flat sample sequence by the timeline sequencer.
- **MetricModel**: A domain-specific class (CPU, memory, disk, network, load) that translates high-level stressor values into consistent, correctly-typed PCP metric values at each sample tick. Defaults are applied here, not at parse time.
- **ValueSampler**: Applies Gaussian noise, accumulates counter state across samples, coerces values to PCP-appropriate types, and accepts an optional PRNG seed for reproducibility.
- **Archive**: The three output files (`.0`, `.index`, `.meta`) constituting a valid PCP v3 archive, produced via `libpcp_import` through the `pcp.pmi.pmiLogImport` Python bindings.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every archive generated by `pmlogsynth` passes `pmlogcheck` without errors or warnings, for all 7 bundled hardware profiles across all stressor combinations within valid ranges.
- **SC-002**: Metric values during a constant-value phase are within ±(noise_factor + 1%) of the specified stressor target value, as verified by `pmval` replay.
- **SC-003**: The Tier 1 test suite passes completely on a stock Python 3.8+ environment with no PCP packages installed.
- **SC-004**: The Tier 2 integration test suite passes on any system (with or without PCP) by mocking the PCP library layer. The Tier 3 E2E suite additionally passes on any system where `pcp.pmi` is importable, validating real archives from at least one profile per metric domain.
- **SC-005**: All 7 bundled hardware profiles pass schema validation in GitHub Actions CI (ubuntu-latest runner with PCP installed via apt).
- **SC-006**: A 7-day archive at 60-second intervals (≈10,080 samples) generates without memory exhaustion on a standard developer workstation.
- **SC-007**: `--validate` correctly accepts all known-good profiles and rejects all known-bad profiles with a specific, actionable error message identifying the violated constraint.
- **SC-008**: Per-CPU metric instances in a generated archive exactly match the CPU count defined in the hardware profile used.

---

## Constraints & Out of Scope

The following are explicitly out of scope for Phase 1 and MUST NOT be implemented:

- Multi-host archives
- Event records
- Derived metrics
- Per-process metrics (`proc.*`)
- Hotplug instance domain changes (instance domains are fixed for the archive lifetime)
- GPU / PMDA-specific namespaces beyond the five supported domains
- Archive v2 format (v3 only)
- Natural language profile generation (Phase 2)
- Fleet archive generation (Phase 3)
- User-facing `--seed` flag (internal seed support in `ValueSampler` is required; CLI flag is Phase 3)

---

## Assumptions

- PCP is installed on the host machine and `libpcp_import.so` and the `pcp` Python bindings (`python3-pcp`) are available.
- Python 3.8+ is the minimum supported version.
- PyYAML is the only third-party Python dependency required for core generation.
- Gaussian noise uses `random.gauss` from the Python standard library (no NumPy).
- The default sample interval is 60 seconds.
- Counter metrics accumulate from zero at archive start; there is no concept of pre-existing counter state.
- Per-CPU utilisation distribution across CPUs uses a simple random split, not a scheduling simulation.
- Mean packet size for network packet count estimation defaults to 1,400 bytes; overridable via `meta.mean_packet_bytes`.
- Mean block size for disk IOPS estimation defaults to 64 KB when `iops_read`/`iops_write` are not specified.
- The hardware profile YAML schema is considered frozen after Phase 1 ships; changes require a versioned migration path due to downstream dependency in Phase 2 and Phase 3.

---

## Cross-Phase Design Decisions

The following decisions have direct implications for Phase 2 and Phase 3 and are captured here to prevent costly retrofits later. These decisions affect Phase 1 implementation choices.

### D-001: ProfileLoader exposes `from_string()` from Day One (Phase 2 dependency)

Phase 2 generates YAML profile text via Claude and immediately passes it to the tool with `--run`. If `ProfileLoader` is file-only, Phase 2 requires a retrofit. **Resolution**: `ProfileLoader` exposes both `from_file(path)` and `from_string(yaml_text)` from Phase 1; `from_file` delegates to `from_string` internally.

### D-002: CLI uses argparse subparsers from the start (Phase 3 dependency)

Phase 3 adds `pmlogsynth fleet [OPTIONS] FLEET_PROFILE`. A flat argument parser requires a full CLI refactor in Phase 3. **Resolution**: Phase 1 CLI uses argparse subparsers; the existing generation behaviour is the default command. `fleet` is a reserved subcommand name.

### D-007: `host.overrides:` pattern is consistent with Phase 3 anomaly overlay semantics

Phase 3 anomaly overlays apply partial workload specs on top of a base profile. The `host.overrides:` pattern in Phase 1 establishes the same "named base + explicit partial override" idiom at the hardware profile level, giving users a consistent mental model across both phases. **Resolution**: Phase 1 introduces `host.overrides:` as the canonical override mechanism; Phase 3's overlay design should reference this pattern.

### D-003: Stressor field defaults applied at value-computation time, not parse time (Phase 3 dependency)

Phase 3 anomaly overlays are partial profiles that override only specified fields. If defaults are baked in at parse time, absent fields are indistinguishable from "set to default", breaking overlay merge logic. **Resolution**: Parsed profile objects use `Optional` types; `MetricModel` applies defaults at value-computation time.

### D-004: ValueSampler accepts an optional PRNG seed (Phase 3 dependency)

Phase 3 requires `--seed` for byte-identical reproducible fleet archives. If the sampler uses unseeded global state, reproducibility cannot be added without a refactor. **Resolution**: `ValueSampler.__init__` accepts an optional `seed` parameter (default: `None` for non-reproducible). No user-facing CLI flag in Phase 1.

### D-006: `-C / --config-dir` must be propagated through to fleet generation (Phase 3 dependency)

Phase 3's `pmlogsynth fleet` needs the same `-C` capability for integration test isolation of fleet profile test fixtures. Since the hardware profile lookup chain is implemented as a standalone resolver, Phase 3 should pass `-C` through to the same resolver without reimplementing it. **Resolution**: Hardware profile lookup is encapsulated in a `ProfileResolver` (or equivalent) that accepts the `-C` path at construction time; both the top-level command and the future `fleet` subcommand construct it from the same CLI argument.

### D-005: Hardware profile schema is frozen after Phase 1 CI (Phase 2 and Phase 3 dependency)

Phase 2 embeds hardware profile summaries in the Claude system prompt. Phase 3 fleet profiles reference hardware profiles by name. Schema changes after Phase 1 ships require coordinated updates across all three phases. **Resolution**: The hardware profile schema is treated as a stable contract from Phase 1 onward. Any breaking change requires a schema version bump and migration path.

---

## Dependencies

**Runtime (required)**:
- Python 3.8+
- PCP installed (provides `libpcp_import.so`)
- `python3-pcp` (provides `pcp.pmi`, `pcp.pmapi`)
- PyYAML

**Optional (Phase 2 only, not Phase 1)**:
- `anthropic>=0.20.0` (installed via `pip install "pmlogsynth[ai]"`)

**Not required**:
- C compiler
- NumPy or any scientific Python stack
- Running `pmcd`
- Root access

**Test dependencies**:
- `pytest`
- `unittest.mock` (stdlib)
