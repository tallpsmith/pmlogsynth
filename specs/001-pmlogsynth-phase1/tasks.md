# Tasks: pmlogsynth Phase 1 — Synthetic PCP Archive Generator

**Input**: Design documents from `/specs/001-pmlogsynth-phase1/`
**Branch**: `001-pmlogsynth-phase1`
**Date**: 2026-03-02

---

## Agent Team Execution Strategy

This feature is optimised for **parallel agent execution**. Use **git worktrees** for the
parallel phase: each agent gets an isolated worktree, and a single **Coordinator Agent**
merges completed work, runs pre-commit, and pushes. No agent other than the Coordinator
runs `pre-commit.sh` or pushes to the remote.

### Agent Roster

| Agent | Worktree | Phase | Files Owned |
|-------|----------|-------|-------------|
| Foundation | main worktree | 1–2 | CI, pyproject.toml, profile.py, sampler.py, timeline.py, domains/base.py, tier1 tests for those modules |
| Domain-CPU | `../pmlogsynth-cpu` | 3 | `domains/cpu.py`, `tests/tier1/test_domain_cpu.py` |
| Domain-Memory | `../pmlogsynth-mem` | 3 | `domains/memory.py`, `tests/tier1/test_domain_memory.py` |
| Domain-Disk | `../pmlogsynth-disk` | 3 | `domains/disk.py`, `tests/tier1/test_domain_disk.py` |
| Domain-Network | `../pmlogsynth-net` | 3 | `domains/network.py`, `tests/tier1/test_domain_network.py` |
| Domain-Load | `../pmlogsynth-load` | 3 | `domains/load.py`, `tests/tier1/test_domain_load.py` |
| Writer | `../pmlogsynth-writer` | 3 | `writer.py`, `tests/tier2/test_writer.py`, `pmlogsynth/profiles/*.yaml` |
| CLI | `../pmlogsynth-cli` | 3 | `cli.py`, `tests/tier1/test_cli.py` |
| Coordinator | main worktree | all | `./pre-commit.sh`, `git merge`, `git push` |

### Coordination Protocol

1. Foundation Agent completes Phases 1–2 and signals Coordinator
2. Coordinator runs `./pre-commit.sh`, pushes Phase 2 commit, then creates worktrees:
   ```bash
   BRANCH=001-pmlogsynth-phase1
   for name in cpu mem disk net load writer cli; do
     git worktree add ../pmlogsynth-$name $BRANCH
   done
   ```
3. Each parallel agent works in its worktree; when done, notifies Coordinator
4. Coordinator merges one worktree at a time, runs `./pre-commit.sh`, pushes
5. After all parallel agents complete, integration work (Phase 8) begins

### Coordinator Merge Pattern (per agent)

```bash
# In main worktree, after agent notifies completion:
git fetch ../pmlogsynth-<name> HEAD:refs/heads/worktree-<name>
git merge --no-ff refs/heads/worktree-<name> -m "Merge <name> track"
./pre-commit.sh   # MUST pass — fix issues before next merge
git push
```

---

## Phase 1: Setup (Sequential — Foundation Agent)

**Purpose**: CI pipeline and project skeleton. CI must exist before any code lands so every
push gets automated feedback (constitution principle VI).

- [X] T001 Create `.github/workflows/ci.yml`: quality job (matrix Python 3.8 + latest, runs ruff, mypy, pytest tier1+tier2) and e2e job (ubuntu-latest system Python, apt install pcp python3-pcp, pytest tier3); trigger on push to any branch and PRs to main; e2e job needs quality per research.md Section 2
- [X] T002 Create `pre-commit.sh` at repository root: run `ruff check .`, `mypy pmlogsynth/`, `pytest tests/tier1/ tests/tier2/ -v`; if `python3 -c "import pcp.pmi" 2>/dev/null` succeeds also run `pytest tests/tier3/ -v`, else print `WARNING: PCP library not available — E2E tests skipped`; exit non-zero on any failure (FR-050)
- [X] T003 Create `pyproject.toml`: setuptools backend, `name="pmlogsynth"`, `version="0.1.0"`, `requires-python=">=3.8"`, `dependencies=["PyYAML>=5.1"]`, dev extras (pytest, ruff, mypy), ai extras (anthropic), entry point `pmlogsynth = "pmlogsynth.cli:main"`, `package-data = {pmlogsynth = ["profiles/*.yaml"]}`, ruff config (target-version py38, select E/W/F/I), mypy config (strict, ignore_missing_imports=true), pytest markers (tier1/tier2/tier3) per research.md Section 3
- [X] T004 [P] Create package skeleton: `pmlogsynth/__init__.py` (set `__version__ = "0.1.0"`), `pmlogsynth/__main__.py` (calls `cli.main()`), `pmlogsynth/domains/__init__.py` (empty), stub files `pmlogsynth/cli.py` / `pmlogsynth/profile.py` / `pmlogsynth/sampler.py` / `pmlogsynth/timeline.py` / `pmlogsynth/writer.py` (each containing only a module docstring and `# TODO` so mypy and ruff pass)
- [X] T005 [P] Create `tests/conftest.py`: `pytest_configure` registers tier1/tier2/tier3 markers; session-scoped `pcp_available` fixture that attempts `import pcp.pmi` and calls `pytest.skip("WARNING: PCP library not available — E2E tests skipped")` if it fails per research.md Section 5

**Checkpoint**: `pip install -e ".[dev]"` succeeds; `ruff check .` and `mypy pmlogsynth/` pass on stubs; CI workflow file is present.

---

## Phase 2: Foundation (Sequential — Foundation Agent)

**Purpose**: Shared core modules that ALL user story implementations depend on. No parallel
agent work can begin until this phase is complete and green.

**⚠️ CRITICAL**: Phases 3+ are blocked on T006–T012.

- [X] T006 [P] Implement `pmlogsynth/profile.py`: dataclasses/typed objects for `ProfileMeta`, `DiskDevice`, `NetworkInterface`, `HardwareProfile`, `CpuStressor`, `MemoryStressor`, `DiskStressor`, `NetworkStressor`, `Phase`, `HostConfig` (three mutually exclusive forms per FR-015a — profile-only, profile+overrides, fully-inline; bare inline fields alongside `host.profile` without `overrides:` key is a `ValidationError`), `WorkloadProfile`; `ProfileLoader` with `from_file(path)` delegating to `from_string(yaml_text)` (FR-042); `ValidationError(Exception)` with field-path message; all validation rules: phase duration sum == meta.duration when no repeat (FR-027), noise in [0.0,1.0] (FR-029), interval positive int (FR-030), repeat:daily fits meta.duration (FR-031), first phase with transition:linear rejected (FR-055), cpu ratios ≤ 1.0 (FR-026); `ProfileResolver` accepting optional `config_dir: Optional[Path]`, implementing `resolve(name) -> HardwareProfile` using precedence `-C` > `~/.pcp/pmlogsynth/profiles/` > `pmlogsynth/profiles/` package data, and `list_all() -> list[ProfileEntry]` with source labels `"config-dir"` / `"user"` / `"bundled"` (FR-022–024); all `Optional` stressor fields stay `None` after parse — defaults applied at compute time NOT here (FR-020/D-003); use `pathlib.Path(__file__).parent / "profiles"` for bundled data path (research.md Section 3)
- [X] T007 [P] Implement `pmlogsynth/sampler.py`: `ValueSampler(noise: float = 0.0, seed: Optional[int] = None)` with `_rng = random.Random(seed)`; `apply_noise(value: float, noise_override: Optional[float] = None) -> float` using multiplicative Gaussian `_rng.gauss(1.0, effective_noise)` clamped to `max(0.0, result)` (FR-013, research.md Section 6); `accumulate(key: str, delta: float) -> int` adds delta (already ≥ 0) to `_counters[key]` running total, returns `int(_counters[key])`; `coerce_u64(value: float) -> int` clamps to [0, 2^64-1] and returns int; `seed=None` is non-reproducible, `seed=int` is byte-identical across runs (FR-043)
- [X] T008 Implement `pmlogsynth/timeline.py`: `SamplePoint` dataclass (timestamp_sec, phase_name, cpu, memory, disk, network — all stressor types from profile.py); `ExpandedTimeline` (samples: list[SamplePoint], start_time: datetime); `TimelineSequencer` accepting `WorkloadProfile`; `expand() -> ExpandedTimeline`: (1) expand `repeat: daily` phases by inserting baseline fills, (2) expand `repeat: N` integer phases, (3) validate expanded duration == meta.duration, (4) for each interval tick compute effective stressor values — `transition: instant` uses phase target values, `transition: linear` linearly interpolates from previous phase final values to current phase target over the full phase duration, (5) emit one SamplePoint per interval; `start_time` defaults to `datetime.now(UTC) - timedelta(seconds=meta.duration)` unless caller provides override [depends on T006]
- [X] T009 Implement `pmlogsynth/domains/base.py`: `MetricDescriptor` dataclass with fields `name: str`, `pmid: Tuple[int,int,int]`, `type_code: int`, `indom: Optional[Tuple[int,int]]`, `sem: int`, `units: Tuple[int,...]`; `MetricModel(ABC)` with `@abstractmethod compute(self, stressor: Any, hardware: HardwareProfile, interval: int, sampler: ValueSampler) -> Dict[str, Dict[Optional[str], Any]]` returning `{metric_name: {instance_name_or_None: value}}`, and `@abstractmethod metric_descriptors(self, hardware: HardwareProfile) -> List[MetricDescriptor]` [depends on T006, T007]; Python 3.8 compatible typing (use `Dict`, `List`, `Optional`, `Tuple` from typing)
- [X] T010 Write `tests/tier1/test_profile.py`: unit tests for `ProfileLoader.from_string` (valid profile parses correctly), `from_file` delegates to `from_string`, `ValidationError` raised with correct message for each of: ratio violation (FR-026), duration mismatch (FR-027), unknown profile name (FR-028), noise out of range (FR-029), bad interval (FR-030), repeat:daily overflow (FR-031), first-phase linear (FR-055), bare inline fields alongside `host.profile` without `overrides:` (FR-015a); `ProfileResolver.resolve()` returns `HardwareProfile` for bundled names; `ProfileResolver.list_all()` returns entries with correct source labels [depends on T006]
- [X] T011 [P] Write `tests/tier1/test_sampler.py`: unit tests for `ValueSampler`: `apply_noise` with noise=0.0 returns exact value, with noise>0 returns noisy value, negative result clamped to 0; `accumulate` returns running total, never negative; `coerce_u64` clamps correctly; deterministic output with same seed; different output with different seeds [depends on T007]
- [X] T012 Write `tests/tier1/test_timeline.py`: unit tests for `TimelineSequencer.expand()`: instant transition emits phase target value at all samples, linear transition interpolates from prev-phase end to current target (check first/mid/last sample), repeat:daily inserts baseline fills between repetitions, repeat integer count expands correctly, expanded duration mismatch raises `ValidationError`, first-phase linear raises `ValidationError`, SamplePoint fields populated correctly [depends on T008]

**Checkpoint**: `pytest tests/tier1/ -v` passes all profile/sampler/timeline tests. Coordinator runs `./pre-commit.sh`, pushes, then creates parallel worktrees.

---

## Phase 3: User Story 1 — Generate a Synthetic PCP Archive (Priority: P1) 🎯 MVP

**Goal**: The complete end-to-end pipeline: YAML workload profile → valid PCP v3 archive
that passes `pmlogcheck` and is immediately usable with `pmval`, `pmrep`, `pmlogdump`.

**Independent Test**: Author the spike.yaml profile from quickstart.md (generic-small, 10-min
baseline 15% CPU + 5-min spike 90% CPU), run `pmlogsynth -o ./out spike.yaml`, confirm
`out.0` / `out.index` / `out.meta` exist, `pmlogcheck ./out` exits 0, `pmval -a ./out
kernel.all.cpu.user` values during spike are within ±5% of 90%.

**⚠️ LAUNCH ALL PARALLEL AGENTS SIMULTANEOUSLY after Phase 2 checkpoint.**

### Track A — Domain Models (5 Independent Agents, all parallel)

Each agent works in its own worktree. Zero inter-domain imports. All share only
`MetricModel` and `MetricDescriptor` from `domains/base.py` and entities from `profile.py`.

- [ ] T013 [P] [US1] Implement `pmlogsynth/domains/cpu.py`: `CpuMetricModel(MetricModel)` — `metric_descriptors()` returns descriptors for `kernel.all.cpu.{user,sys,idle,wait.total,steal}` (PM_INDOM_NULL, PM_SEM_COUNTER, PM_TYPE_U64, units msec) and `kernel.percpu.cpu.{user,sys,idle}` (per-CPU indom `pmiInDom(60,0)`, same sem/type/units); `compute()` applies CPU utilization stressor, distributes across `hardware.cpus` CPUs using random split preserving total, applies per-domain noise via `sampler.apply_noise()`, computes tick delta = `utilization * interval_sec * 1000 / cpus` per CPU, returns cumulative counters via `sampler.accumulate()`; user+sys+idle+wait+steal MUST equal total_ticks per CPU per sample (FR-006/007); iowait_ratio portion goes to wait.total; defaults (utilization=0.0, user_ratio=0.70, sys_ratio=0.20, iowait_ratio=0.10) applied here if stressor field is None (FR-020); PMIDs: kernel domain=60, all.cpu cluster=0, percpu cluster=10, item numbers from research.md PMID table
- [ ] T014 [P] [US1] Implement `pmlogsynth/domains/memory.py`: `MemoryMetricModel(MetricModel)` — `metric_descriptors()` returns descriptors for `mem.util.{used,free,cached,bufmem}` (PM_INDOM_NULL, PM_SEM_INSTANT, PM_TYPE_U64, units kbyte) and `mem.physmem` (PM_SEM_DISCRETE, PM_TYPE_U64, kbyte); `compute()` derives `used_kb = hardware.memory_kb * used_ratio`, `free_kb = hardware.memory_kb - used_kb`, `cached_kb = used_kb * cache_ratio`, `bufmem_kb = used_kb * 0.05` (small fixed fraction of used); used+free == physmem at every sample (FR-008); noise applied multiplicatively to used_ratio before compute; defaults: used_ratio=0.50, cache_ratio=0.30; PMIDs: mem domain=58, cluster=0, items from research.md
- [ ] T015 [P] [US1] Implement `pmlogsynth/domains/disk.py`: `DiskMetricModel(MetricModel)` — `metric_descriptors()` returns descriptors for `disk.all.{read,write,read_bytes,write_bytes}` (aggregate, PM_INDOM_NULL, PM_SEM_COUNTER) and `disk.dev.{read_bytes,write_bytes}` (per-device indom `pmiInDom(60,1)`, instances named from `hardware.disks[].name`); `compute()` converts `read_mbps`/`write_mbps` to kbytes/interval delta, splits evenly across disk devices, `iops_read` = `read_mbps * 1024 / 64` if not specified (64KB default block), similarly iops_write; all counters accumulated via `sampler.accumulate()`; defaults: read_mbps=0.0, write_mbps=0.0; PMIDs from research.md (disk domain=60, cluster 4 for all, cluster 5 for dev)
- [ ] T016 [P] [US1] Implement `pmlogsynth/domains/network.py`: `NetworkMetricModel(MetricModel)` — `metric_descriptors()` returns descriptors for `network.interface.{in,out}.{bytes,packets}` (per-NIC indom `pmiInDom(60,2)`, instances from `hardware.interfaces[].name`, PM_SEM_COUNTER, PM_TYPE_U64); `compute()` converts `rx_mbps`/`tx_mbps` to bytes/interval delta per NIC (split evenly across interfaces), `in_packets = in_bytes / meta.mean_packet_bytes` (default 1400), `out_packets = out_bytes / mean_packet_bytes`; defaults: rx_mbps=0.0, tx_mbps=0.0; PMIDs from research.md (network domain=60, cluster=3)
- [ ] T017 [P] [US1] Implement `pmlogsynth/domains/load.py`: `LoadMetricModel(MetricModel)` — `metric_descriptors()` returns descriptor for `kernel.all.load` (PM_INDOM_NULL, PM_SEM_INSTANT, PM_TYPE_FLOAT) with instances `"1 minute"` / `"5 minute"` / `"15 minute"` using load indom `pmiInDom(60,3)` (check research.md — load uses PM_INDOM_NULL not per-instance indom, verify); `compute()` implements UNIX EMA: `load_raw = utilization * hardware.cpus`, decay constants `alpha_1 = exp(-interval/60)`, `alpha_5 = exp(-interval/300)`, `alpha_15 = exp(-interval/900)`, `load_N = alpha_N * prev_load_N + (1-alpha_N) * load_raw`; state maintained across calls in instance attribute; initial loads = 0.0; reads cpu utilization value only, does NOT import cpu.py (FR-011, research.md Section 7)
- [ ] T018 [P] [US1] Write `tests/tier1/test_domain_cpu.py`: unit tests for `CpuMetricModel`: user+sys+idle+wait+steal == total_ticks for all samples, per-CPU indom count equals `hardware.cpus` from test fixture, noise=0 produces exact target values, noise>0 still satisfies tick consistency, defaults applied when stressor is None (utilization defaults to 0.0), negative delta clamped to 0 [depends on T013]
- [ ] T019 [P] [US1] Write `tests/tier1/test_domain_memory.py`: unit tests for `MemoryMetricModel`: `used+free == physmem` invariant at every sample, cache_ratio as fraction of used, physmem constant (discrete sematics), noise affects used_ratio proportionally, defaults applied when stressor is None [depends on T014]
- [ ] T020 [P] [US1] Write `tests/tier1/test_domain_disk.py`: unit tests for `DiskMetricModel`: counter accumulates across samples, per-device instance names match hardware profile disk names, iops estimated correctly from mbps when not specified, noise clamped (no negative deltas), defaults produce zero I/O [depends on T015]
- [ ] T021 [P] [US1] Write `tests/tier1/test_domain_network.py`: unit tests for `NetworkMetricModel`: per-NIC instance names match hardware profile interface names, packet count estimated from bytes/mean_packet_bytes, byte counters accumulate, noise applied, defaults produce zero traffic [depends on T016]
- [ ] T022 [P] [US1] Write `tests/tier1/test_domain_load.py`: unit tests for `LoadMetricModel`: initial load = 0.0, EMA converges toward load_raw over many samples, 1-min load responds faster than 15-min load (higher alpha), different interval values produce different decay rates, zero utilization drives load toward 0.0 [depends on T017]

### Track B1 — Writer Agent

- [ ] T023 [P] [US1] Create `pmlogsynth/profiles/` directory and all 7 bundled hardware profile YAML files using schema from data-model.md HardwareProfile entity: `generic-small.yaml` (name: generic-small, cpus: 2, memory_kb: 8388608, disks: [{name: nvme0n1, type: nvme}], interfaces: [{name: eth0, speed_mbps: 10000}]); `generic-medium.yaml` (4 CPU, 16777216 KB, 1 NVMe, 1×10GbE); `generic-large.yaml` (8 CPU, 33554432 KB, 2×NVMe [nvme0n1, nvme1n1], 1×10GbE); `generic-xlarge.yaml` (16 CPU, 67108864 KB, 2×NVMe, 2×10GbE [eth0, eth1]); `compute-optimized.yaml` (8 CPU, 16777216 KB, 1 NVMe, 1×10GbE); `memory-optimized.yaml` (4 CPU, 67108864 KB, 1 NVMe, 1×10GbE); `storage-optimized.yaml` (4 CPU, 16777216 KB, 4×HDD [sda, sdb, sdc, sdd], 1×10GbE) (FR-021, data-model.md bundled profiles table)
- [ ] T024 [P] [US1] Write `tests/tier2/test_writer.py`: integration tests using `unittest.mock.patch("pcp.pmi.pmiLogImport")` to stub the PCP layer; verify `pmiSetHostname` called with profile hostname, `pmiSetTimezone` called with profile timezone, `pmiAddMetric` called for each expected metric name (check at least one from each domain), `pmiAddInstance` called for each CPU/disk/NIC instance in test hardware profile, `pmiPutValue` called per (metric, instance) per sample, `pmiWrite` called with correct timestamp sequence, `del log` called for finalization; test partial cleanup: if pmiWrite raises, all output files are deleted unless `--leave-partial`; test conflict check: if output file exists and no `--force`, raises I/O error before any write; use `-C ./tests/fixtures/profiles` for all hardware profiles (FR-047)
- [ ] T025 [US1] Implement `pmlogsynth/writer.py`: `ArchiveWriter` class; `__init__(self, output_path: str, profile: WorkloadProfile, hardware: HardwareProfile, config_dir: Optional[Path], force: bool, leave_partial: bool)`; `write(timeline: ExpandedTimeline, sampler: ValueSampler) -> None`: (1) check for pre-existing `.0`/`.index`/`.meta` files, exit with `ArchiveConflictError` identifying all conflicting files unless `force=True` (FR-053); (2) open `pmi.pmiLogImport(output_path)`, call `pmiSetHostname`, `pmiSetTimezone`; (3) instantiate all five `MetricModel` subclasses, collect all `MetricDescriptor`s via `metric_descriptors()`, call `pmiAddMetric` for each; (4) register indom instances via `pmiAddInstance` for per-CPU, per-disk, per-NIC metrics; (5) iterate `timeline.samples`: for each `SamplePoint`, call `.compute()` on all five models, call `pmiPutValue` for each `(metric, instance_or_None, value)`, call `pmiWrite(sample.timestamp_sec, 0)`; (6) `del log` to finalize; on any exception after opening: collect written files, delete them, report removed files to stderr, re-raise as `ArchiveGenerationError` — unless `leave_partial=True`, in which case print warning identifying partial files and re-raise; PCP import ONLY in this file (Tier 1/2 isolation) [depends on T013-T017, T006, T007, T008]

### Track B2 — CLI Agent

- [ ] T026 [P] [US1] Implement `pmlogsynth/cli.py`: `main()` entry point; `argparse` with subparsers; default subcommand is `generate` (invoked when no subcommand given, so `pmlogsynth profile.yaml` works directly); `fleet` subcommand stub that prints `"error: fleet subcommand not yet implemented"` to stderr and exits 2 (FR-041); generate command flags: `-o/--output PATH` (default `./pmlogsynth-out`), `--start TIMESTAMP` (parse ISO 8601 and `YYYY-MM-DD HH:MM:SS TZ` formats), `-v/--verbose` (print per-sample values to stderr), `--validate` (validate only, exit without writing, incompatible with -o/--start/--force/--leave-partial), `--force` (permit overwrite, FR-054), `--leave-partial` (suppress cleanup on failure, FR-052), `-C/--config-dir PATH` (additional hardware profile dir, FR-023, FR-038); `--list-profiles` (print source-labelled table sorted alpha within group: bundled < user < config-dir, respects -C, exit 0, FR-025, cli-schema.md format); `--list-metrics` (print sorted lexicographic list of all 24 metric names from cli-schema.md, one per line, no formatting, exit 0, FR-034, FR-049); `-V/--version` (print version from `__version__`); exit codes 0/1/2/3 per cli-schema.md; all errors to stderr, successful output to stdout; wire `ProfileResolver`, `ProfileLoader`, `TimelineSequencer`, `ValueSampler`, `ArchiveWriter` together in generate command flow
- [ ] T027 [P] [US1] Write `tests/tier1/test_cli.py`: unit tests for CLI using `argparse` parsing only (no subprocess, no file I/O): default subcommand parses profile positional arg, `--validate` conflict rules raise argparse error with -o/--start/--force/--leave-partial, `--list-metrics` output is sorted and contains exactly the 24 metric names from cli-schema.md (no extra text), `--list-profiles` output format matches cli-schema.md SOURCE/NAME columns, fleet subcommand exits 2, `--start` parses ISO 8601 and human-readable forms correctly, `-C` path is passed through to ProfileResolver

**Checkpoint (US1 complete)**: All Phase 3 worktrees merged by Coordinator; `./pre-commit.sh` passes clean; `pmlogsynth -o /tmp/out <quickstart spike profile>` generates archive (on PCP-enabled machine); CI quality matrix green.

---

## Phase 4: User Story 2 — Validate Profile Without Generating Output (Priority: P2)

**Goal**: `pmlogsynth --validate profile.yaml` gives immediate actionable feedback on profile
correctness before any archive is written.

**Independent Test**: `pmlogsynth --validate bad-ratio.yaml` exits 1 with message identifying
the violated ratio constraint; `pmlogsynth --validate good-baseline.yaml` exits 0 with no
output to stdout or stderr.

> **Note**: The `--validate` flag is fully implemented in `cli.py` (T026) and the validation
> logic is in `profile.py` (T006). This phase provides dedicated test fixtures and
> comprehensive validation-specific Tier 1 coverage.

- [ ] T028 [US2] Create `tests/fixtures/profiles/bad-ratio.yaml`: known-bad workload profile with `user_ratio + sys_ratio + iowait_ratio = 1.1` in a CPU phase (violates FR-026); uses `host.profile: test-single-cpu` (from -C fixtures)
- [ ] T029 [US2] Create `tests/fixtures/profiles/bad-duration.yaml`: known-bad workload profile where phase durations sum to 500s but `meta.duration: 600` (violates FR-027)
- [ ] T030 [US2] Create `tests/fixtures/profiles/bad-noise.yaml`: known-bad profile with `meta.noise: 1.5` (violates FR-029)
- [ ] T031 [US2] Create `tests/fixtures/profiles/good-baseline.yaml`: minimal valid 2-phase workload profile (baseline 300s 15% CPU + spike 300s 90% CPU, total 600s) using `host.profile: generic-small`; to be used as canonical known-good fixture across all tiers
- [ ] T032 [P] [US2] Write `tests/tier1/test_validation.py`: parameterized tests for each of the 7 validation rules; each test calls `ProfileLoader.from_string()` with a fixture profile and asserts `ValidationError` is raised with a message containing the relevant field name or constraint description; one test confirms `good-baseline.yaml` raises no error; one test for unknown `host.profile` name raises `ValidationError` (FR-028); one test for first-phase `transition: linear` raises `ValidationError` (FR-055); one test for bare inline fields with `host.profile` without `overrides:` raises `ValidationError` (FR-015a)

**Checkpoint (US2 complete)**: All validation tests pass; Coordinator merges and pushes.

---

## Phase 5: User Story 3 — Use Named Hardware Profiles (Priority: P2)

**Goal**: Named bundled profiles eliminate boilerplate; `-C` makes tests self-contained and
reproducible without touching `~/.pcp/pmlogsynth/profiles/`.

**Independent Test**: `pmlogsynth --list-profiles` lists exactly 7 bundled profiles with
source `bundled`; `pmlogsynth -C ./tests/fixtures/profiles --list-profiles` includes
`test-single-cpu` and `test-multi-disk` labelled `config-dir` without modifying
`~/.pcp/pmlogsynth/profiles/`.

> **Note**: Bundled YAML profiles created in T023; `ProfileResolver` implemented in T006;
> `--list-profiles` and `-C` flags in T026. This phase adds hardware profile resolution unit
> tests and ensures test fixture profiles are complete.

- [ ] T033 [US3] Create `tests/fixtures/profiles/test-single-cpu.yaml`: 1-CPU test hardware profile (name: test-single-cpu, cpus: 1, memory_kb: 4194304, disks: [{name: sda, type: ssd}], interfaces: [{name: eth0, speed_mbps: 1000}])
- [ ] T034 [US3] Create `tests/fixtures/profiles/test-multi-disk.yaml`: 4-disk test hardware profile (name: test-multi-disk, cpus: 2, memory_kb: 8388608, disks: [{name: sda}, {name: sdb}, {name: sdc}, {name: sdd}], interfaces: [{name: eth0, speed_mbps: 10000}])
- [ ] T035 [P] [US3] Write `tests/tier1/test_profile_resolver.py`: unit tests for `ProfileResolver`: `resolve("generic-small")` returns `HardwareProfile` with cpus=2; `resolve("nonexistent")` raises `ValidationError`; `-C` directory entry overrides bundled profile of same name; `list_all()` returns entries with source labels `"bundled"` / `"user"` / `"config-dir"`; `list_all()` with no `-C` contains exactly 7 bundled names; `list_all()` with `-C ./tests/fixtures/profiles` includes test fixture names labelled `"config-dir"`; `resolve()` with `-C` resolves test-only profiles that are not in bundled set

**Checkpoint (US3 complete)**: Profile resolver tests pass; Coordinator merges and pushes.

---

## Phase 6: User Story 4 — Multi-Phase Timelines with Transitions and Repeats (Priority: P2)

**Goal**: Profiles can express gradual ramps (`transition: linear`) and recurring daily
patterns (`repeat: daily`) without copy-pasting phases.

**Independent Test**: Generate archive from profile with a linear-transition recovery phase;
verify that metric values in the archive interpolate smoothly (not step-function) between
spike and recovery target values.

> **Note**: Timeline implementation is complete in T008 and covered in T012. This phase adds
> deeper timeline scenario tests and workload fixture files for integration-level verification.

- [ ] T036 [P] [US4] Write `tests/tier1/test_timeline_scenarios.py`: tests covering — (1) instant transition: sample at phase boundary equals new phase target exactly; (2) linear transition: first sample ≈ previous phase value, middle sample ≈ midpoint, final sample ≈ current target; (3) repeat:daily inserts baseline fills between repetitions at correct timestamps; (4) repeat integer count N produces N copies; (5) expanded duration mismatch raises `ValidationError` with specific message; (6) first-phase `transition: linear` raises `ValidationError`; (7) nested stressor interpolation: both CPU and memory interpolate independently [depends on T008]
- [ ] T037 [P] [US4] Create `tests/fixtures/workload-linear-ramp.yaml`: workload profile with three phases — baseline (300s, 15% CPU), ramp (300s, `transition: linear`, 90% CPU), spike (600s, 90% CPU); total 1200s; uses `host.profile: test-single-cpu` with `-C` fixtures
- [ ] T038 [P] [US4] Create `tests/fixtures/workload-repeat-daily.yaml`: workload profile with `meta.duration: 86400`, two phases — background (82800s baseline) and noon-peak (3600s, `repeat: daily`, 90% CPU utilization); used for repeat expansion verification

**Checkpoint (US4 complete)**: Timeline scenario tests pass; Coordinator merges and pushes.

---

## Phase 7: User Story 5 — Discover What Metrics the Tool Produces (Priority: P3)

**Goal**: `pmlogsynth --list-metrics` gives a sorted, copy-pasteable list of all 24 PCP
metric names the tool can produce — consistent with the man page.

**Independent Test**: `pmlogsynth --list-metrics` output contains at least one name from each
of the five domains (CPU, memory, disk, network, load) and matches the list in cli-schema.md
exactly; names are valid for use in `pmval -a` queries.

> **Note**: `--list-metrics` flag is implemented in `cli.py` (T026). This phase adds explicit
> consistency tests ensuring metric names from domain models match the CLI output and man page.

- [ ] T039 [US5] Write `tests/tier1/test_list_metrics.py`: test that `--list-metrics` output (captured from `cli.main()` with sys.argv stubbed) is sorted lexicographically, contains exactly the 24 metric names listed in `specs/001-pmlogsynth-phase1/contracts/cli-schema.md`, one per line, no trailing whitespace or extra text; test that the set of metric names returned by `metric_descriptors()` across all five domain model classes exactly matches the `--list-metrics` output (FR-049 consistency); test that at least one name from each domain prefix (kernel.all.cpu, mem., disk., network., kernel.all.load) is present

**Checkpoint (US5 complete)**: List-metrics test passes; Coordinator merges and pushes.

---

## Phase 8: Integration & Polish

**Purpose**: End-to-end validation against real PCP, complete documentation, final quality
pass.

- [ ] T040 Write `tests/tier3/test_e2e.py`: mark all tests `@pytest.mark.tier3` and declare `pcp_available` fixture; generate archive from `good-baseline.yaml` using `-C ./tests/fixtures/profiles -o /tmp/pmlogsynth-e2e`; assert all three files exist; run `subprocess.run(["pmlogcheck", "/tmp/pmlogsynth-e2e"])` and assert exit 0 (SC-001); run `pmval -a /tmp/pmlogsynth-e2e kernel.all.cpu.user` via subprocess and assert spike values ≥ 0.80 (SC-002); verify per-CPU instance count in archive matches `test-single-cpu` profile cpus=1 using `pmval -a ./out kernel.percpu.cpu.user` (SC-008); test `--force` allows overwrite of existing archive files; test that generation error causes partial file cleanup (create unwriteable temp dir scenario); test `--leave-partial` leaves files on failure with warning to stderr (FR-044–047)
- [ ] T041 Write `man/pmlogsynth.1`: groff/troff man page in PCP man page conventions; sections: NAME, SYNOPSIS, DESCRIPTION, OPTIONS (all flags from cli-schema.md), YAML PROFILE FORMAT (meta/host/phases with field tables), HARDWARE PROFILES (7 bundled names with specs, precedence chain, -C usage, user dir), SUPPORTED METRICS (all 24 names grouped by domain with PCP semantic/type/units), CONSTRAINTS (all validation rules from FR-026-031/FR-055), EXAMPLES (5 examples from quickstart.md), EXIT STATUS (exit codes 0-3), FILES, SEE ALSO; metric name list MUST match `--list-metrics` output exactly (FR-048/049)
- [ ] T042 [P] Write `README.md`: project tagline, badges (CI status), 3-line description, Installation section (pip + system PCP deps for Linux/macOS per quickstart.md), Quick Start (4-step demo from quickstart.md spike.yaml), Bundled Hardware Profiles table (7 rows: name/CPUs/RAM/disks/NICs), Running Tests section (tier commands from CLAUDE.md), Contributing link
- [ ] T043 [P] Validate all quickstart.md scenarios: execute every bash code block in `specs/001-pmlogsynth-phase1/quickstart.md` in sequence on a PCP-enabled machine; confirm exit codes match expected; confirm `pmlogcheck` passes for each generated archive; report any divergence between quickstart.md and actual behaviour as a bug to fix before this task is marked complete

**Final Checkpoint**: `./pre-commit.sh` passes clean; CI green on all three tiers (quality matrix × 2 Python versions, E2E on system Python); `pmlogcheck` accepts archives from all 7 bundled profiles (SC-001, SC-005); Coordinator pushes final commit.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** (Setup): No dependencies — start immediately
- **Phase 2** (Foundation): Depends on Phase 1 — BLOCKS all user story work
- **Phase 3** (US1): Depends on Phase 2 — all parallel tracks launch simultaneously
- **Phases 4–7** (US2–US5): Depend on Phase 3 complete (cli.py, writer.py, all domains)
- **Phase 8** (Integration): Depends on Phases 1–7 all complete

### Within Phase 3 — Parallel Launch Diagram

```
Phase 2 complete (T006–T012 all pass)
         │
         ▼  Coordinator creates worktrees
         │
         ├── Domain-CPU    (T013, T018)  ─────────────┐
         ├── Domain-Memory (T014, T019)  ─────────────┤
         ├── Domain-Disk   (T015, T020)  ─────────────┤ all simultaneous
         ├── Domain-Network(T016, T021)  ─────────────┤
         ├── Domain-Load   (T017, T022)  ─────────────┤
         ├── Writer        (T023→T024→T025)  ──────────┤
         └── CLI           (T026, T027)  ─────────────┘
                  │
                  ▼  Coordinator merges each worktree, runs pre-commit, pushes
                  │
              Phase 4–7 (small, sequential)
                  │
              Phase 8 (integration)
```

### User Story Dependencies

| Story | Depends On | Independent Of |
|-------|-----------|----------------|
| US1 (P1) | Foundation (Phase 2) | — (is the parallel track itself) |
| US2 (P2) | US1 complete (cli.py + profile.py) | US3, US4, US5 |
| US3 (P2) | US1 complete (cli.py + ProfileResolver) | US2, US4, US5 |
| US4 (P2) | Foundation only (timeline.py done in Phase 2) | US2, US3, US5 |
| US5 (P3) | US1 complete (cli.py + domain metric_descriptors) | US2, US3, US4 |

### Within Phase 3 — Writer Sequential Order

```
T023 (bundled profiles) ─► T024 (tier2 test stubs) ─► T025 (writer.py impl)
```

Writer tests (T024) should be written before writer implementation (T025) to establish
the expected call contract; bundled profiles (T023) must exist first as test fixtures.

---

## Parallel Execution: Agent Worktree Commands

```bash
# Foundation Agent completes and notifies Coordinator
# Coordinator runs:
./pre-commit.sh && git push

BRANCH=001-pmlogsynth-phase1
REPO=$(pwd)

# Create all worktrees at once
for name in cpu mem disk net load writer cli; do
  git worktree add ../pmlogsynth-$name $BRANCH
done

# Each agent independently (example for Domain-CPU agent):
#   cd ../pmlogsynth-cpu
#   [implement T013: domains/cpu.py]
#   [implement T018: tests/tier1/test_domain_cpu.py]
#   pytest tests/tier1/test_domain_cpu.py -v   # must pass before notifying
#   notify Coordinator

# Coordinator merges one at a time (never two simultaneously):
cd $REPO
git merge --no-ff ../pmlogsynth-cpu/HEAD -m "feat: CpuMetricModel and Tier 1 tests (T013, T018)"
./pre-commit.sh   # MUST pass — if it fails, fix before next merge
git push
# repeat for mem, disk, net, load, writer, cli

# Clean up worktrees when done:
for name in cpu mem disk net load writer cli; do
  git worktree remove ../pmlogsynth-$name
done
```

---

## Implementation Strategy

### MVP Scope (US1 Only — 25 tasks)

1. Phase 1 (T001–T005): CI + packaging
2. Phase 2 (T006–T012): profile + sampler + timeline + base + Tier 1 tests
3. Phase 3 (T013–T027): all parallel domain/writer/CLI tracks
4. **STOP AND VALIDATE**: `pmlogsynth -o /tmp/out good-baseline.yaml && pmlogcheck /tmp/out`
5. Ship MVP: archives are generated and pass pmlogcheck

### Incremental Delivery

- Phases 1–2 → Foundation + CI; every push is automatically validated
- Phase 3 → US1 complete; tool generates valid PCP archives (MVP shipped)
- Phase 4 → US2; `--validate` enables fast iteration on profiles
- Phase 5 → US3; hardware profiles + `-C` enable clean test isolation
- Phase 6 → US4; timeline transitions + repeats model realistic workloads
- Phase 7 → US5; `--list-metrics` convenience for tool authors
- Phase 8 → Full E2E, man page, README; production-ready release

### Coordinator Responsibilities

1. Keep `001-pmlogsynth-phase1` branch green at all times
2. Run `./pre-commit.sh` before every push — never push a red state
3. Merge worktrees one at a time; resolve ruff/mypy conflicts before next merge
4. After all Phase 3 merges: verify `pytest tests/tier1/ tests/tier2/ -v` passes end-to-end
5. Push immediately after each successful pre-commit run (small, reviewable commits)

---

## Task Summary

| Phase | US | Task IDs | Count | Parallel Opportunities |
|-------|----|----------|-------|----------------------|
| Phase 1 (Setup) | — | T001–T005 | 5 | T004, T005 parallel |
| Phase 2 (Foundation) | — | T006–T012 | 7 | T006+T007 parallel; T011 parallel with T010/T012 |
| Phase 3 (US1) | US1 | T013–T027 | 15 | All Track A (T013-T022) and B2 (T026-T027) parallel; B1 sequential T023→T024→T025 |
| Phase 4 (US2) | US2 | T028–T032 | 5 | T028-T031 parallel (fixtures); T032 parallel |
| Phase 5 (US3) | US3 | T033–T035 | 3 | T033+T034 parallel |
| Phase 6 (US4) | US4 | T036–T038 | 3 | T036+T037+T038 parallel |
| Phase 7 (US5) | US5 | T039 | 1 | — |
| Phase 8 (Polish) | — | T040–T043 | 4 | T042+T043 parallel |
| **TOTAL** | | **T001–T043** | **43** | |

### Parallel Opportunities in Phase 3 (maximum parallelism point)

```
7 agents working simultaneously:
  Agent A1 (Domain-CPU):    T013 + T018  →  2 tasks
  Agent A2 (Domain-Memory): T014 + T019  →  2 tasks
  Agent A3 (Domain-Disk):   T015 + T020  →  2 tasks
  Agent A4 (Domain-Network):T016 + T021  →  2 tasks
  Agent A5 (Domain-Load):   T017 + T022  →  2 tasks
  Agent B1 (Writer):        T023 → T024 → T025  →  3 tasks (sequential within B1)
  Agent B2 (CLI):           T026 + T027  →  2 tasks
```

---

## Notes

- **[P] tasks** operate on different files — safe for worktree parallel execution
- **PCP library isolation**: `pcp.pmi` imported ONLY in `writer.py` and `tests/tier3/`; all other modules MUST NOT import from `pcp.*` (enables Tier 1/2 to run anywhere)
- **Defaults at compute time**: stressor fields stay `Optional` / `None` after parsing; `MetricModel.compute()` applies defaults — NEVER `ProfileLoader` (FR-020/D-003)
- **Counter safety**: noise application always uses `max(0.0, result)` before accumulation (FR-013)
- **Python 3.8 compatibility**: no walrus operator (`:=`), no `match`, no `X | Y` union types — use `Optional[X]`, `Union[X, Y]`, `Dict`, `List`, `Tuple` from `typing`
- **Test fixtures use `-C`**: all Tier 2 and Tier 3 tests supply hardware profiles via `-C ./tests/fixtures/profiles/` — never depend on `~/.pcp/pmlogsynth/profiles/` (FR-047)
- **Coordinator is the only pusher**: parallel agents MUST NOT push; they work locally in their worktree and notify the Coordinator when done
