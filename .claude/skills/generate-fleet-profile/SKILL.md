---
name: generate-fleet-profile
description: >
  Generate a valid pmlogsynth fleet profile YAML from a natural language description of a
  multi-host environment, then validate it with `pmlogsynth fleet --validate`. Use this
  skill whenever the user wants to simulate multiple hosts, a server fleet, a cluster, a
  farm, or any multi-machine scenario. Trigger when users mention things like "fleet of
  web servers", "cluster with some bad hosts", "20 hosts with a few showing CPU problems",
  "generate archives for a server farm", "simulate a production fleet", or "I need
  multiple PCP archives with some anomalies". A fleet profile is different from a regular
  workload profile — it orchestrates multiple hosts sharing a common hardware profile,
  with baseline hosts and optional bad-actor hosts running different workload profiles.
  If the user only wants a single host, use the generate-profile skill instead.
---

# Generate pmlogsynth Fleet Profile

Generate a single self-contained fleet profile YAML that produces multiple PCP archives —
one per simulated host. Fleet profiles describe a pool of hosts sharing common hardware,
with a majority running a baseline workload and an optional minority running as "bad
actors" with different workload profiles. All workload definitions are inline — no
external files needed.

## Key Concepts

A fleet profile is **not** a workload profile. It's a higher-level orchestrator:

- **All hosts share one hardware profile** (from `meta.hardware`)
- **Workload profiles are defined inline** in a `profiles` section, referenced by name
- **Baseline hosts** all run the same named profile, with per-host jitter for variation
- **Bad-actor hosts** are randomly selected from the pool and assigned profiles
  from a separate list (e.g. CPU-saturated, memory-exhausted scenarios)
- **Jitter** adds Gaussian noise (±N%) to all stressor values per host, so no two hosts
  are identical even if they share the same workload
- **Fleet-level `duration`, `interval`, and `hardware`** apply to all hosts

## Step 1 — Read the Schema References and Bootstrap

Read these reference files (relative to this skill's directory):

1. `references/fleet-schema.md` — the fleet profile format, fields, and validation rules
2. `references/workload-profile-schema.md` — the workload profile stressor format (for
   generating the phase definitions inside named profiles)
3. `references/running-pmlogsynth.md` — how to bootstrap and run pmlogsynth

Before any validation or generation, run `uv sync` to ensure the environment is ready.

## Step 2 — Understand the Fleet Scenario

If the user provided a description, use it. Otherwise ask:

**"Describe the fleet you want to simulate. For example: how many hosts, what kind of
workload (web, database, batch), and what problems should some hosts exhibit?"**

Key details to extract:
- **Total host count** — how many servers in the fleet
- **Workload character** — what the baseline hosts are doing (web serving, DB queries, etc.)
- **Bad actors** — how many, and what's wrong with them (CPU saturation, memory pressure,
  disk thrashing, network degradation)
- **Duration** — how long the simulation runs
- **Hardware class** — what size machines (`generic-small` through `storage-optimized`)

## Step 3 — Generate the Fleet Profile YAML

Produce a single self-contained fleet profile YAML with all workload definitions inline.
Follow the format in `references/fleet-schema.md` exactly.

Rules:
1. **Output raw YAML only** — no markdown fences, no prose
2. **`meta` is required** — must include `name`, `duration`, `interval`,
   `hostname_prefix`, and `hardware`
3. **`profiles` is required** — define named workload profiles with `phases` lists
4. **`hosts` is required** — must include `count` and `baseline` (name from `profiles`)
5. **`bad_actors` is optional** — include `count`, `profiles` list (names from `profiles`),
   and optionally `jitter`
6. **`bad_actors.count` must not exceed `hosts.count`**
7. **Use readable duration strings** (`10m`, `1h`, `24h`) for `duration` and `interval`
8. **Add jitter** (typically 0.03–0.10) for realistic per-host variation
9. **Include comments** explaining the fleet scenario

### Realistic Fleet Patterns

| Scenario | Hosts | Bad Actors | Typical Jitter |
|----------|-------|------------|----------------|
| Small dev cluster | 3–5 | 0–1 | 0.02–0.05 |
| Web tier | 10–50 | 1–3 | 0.03–0.08 |
| Database cluster | 3–10 | 1–2 | 0.02–0.05 |
| Large production fleet | 50–200 | 2–10 | 0.05–0.10 |

### Named Fault Patterns for Bad Actors

When the user describes problems, translate them into named profile definitions:

| Fault | Key Characteristics |
|-------|---------------------|
| CPU saturation | `utilization: 0.94–0.98`, high `user_ratio`, elevated `iowait_ratio` |
| Memory pressure | `used_ratio: 0.88–0.95`, very low `cache_ratio: 0.02–0.05` |
| Disk thrashing | High `read_mbps`/`write_mbps`, high `iops_*`, elevated `iowait_ratio` |
| Network degradation | Low `rx_mbps`/`tx_mbps` relative to interface capacity |
| Noisy neighbour | High CPU with elevated `sys_ratio` (virtualisation overhead) |
| Slow drain | Gradual increase across all metrics over multiple phases |

## Step 4 — Save the Fleet Profile

1. Ensure `generated-archives/` exists
2. Save the fleet profile with a descriptive slugified name:
   - Example: "20-host web cluster with CPU problems" →
     `generated-archives/20-host-web-cluster-fleet.yaml`

## Step 5 — Validate

Validate the fleet profile. If `uv run` fails because dependencies aren't synced,
run `uv sync` first.

```bash
uv run pmlogsynth fleet --validate generated-archives/<fleet-file>.yaml
```

- **Exit 0**: Valid. Proceed.
- **Exit 1**: Fix the error and retry once.
- **Exit 2**: I/O error — report and stop.

## Step 6 — Generate the Archives

After validation passes, generate the actual PCP archives. Derive the output directory
name from the fleet name in the profile:

```bash
uv run pmlogsynth fleet --seed 42 -o ./generated-archives/<fleet-name> generated-archives/<fleet-file>.yaml
```

Use `--seed 42` by default for reproducible host assignment. If generation fails, report
the error to the user.

## Step 7 — Report

Tell the user:
- Fleet profile YAML saved and its path
- Where the archives were generated
- How to preview the host assignment:
  ```bash
  uv run pmlogsynth fleet --dry-run generated-archives/<fleet-file>.yaml
  ```
- How to inspect individual archives:
  ```bash
  pmstat -a ./generated-archives/<fleet-name>/<hostname>
  ```
