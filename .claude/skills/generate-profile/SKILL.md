---
name: generate-profile
description: >
  Generate a valid pmlogsynth YAML workload profile from a natural language description,
  then validate it with `pmlogsynth --validate`. Use this skill whenever the user wants to
  create a PCP archive workload profile, describes a server workload scenario they want to
  simulate, mentions pmlogsynth profiles, or asks to create/modify synthetic performance
  data for a single host. Also trigger when users say things like "simulate a CPU spike",
  "create a workload that looks like a database server", "generate a profile for testing",
  or "I need a PCP archive that shows memory pressure". If the user wants multiple hosts
  or a fleet, use the generate-fleet-profile skill instead.
---

# Generate pmlogsynth Workload Profile

Generate a valid pmlogsynth YAML workload profile from a natural language description.
The profile describes a single host's workload over time using phases with CPU, memory,
disk, and network stressors.

## Step 1 — Get the Schema and Bootstrap

Read these reference files (relative to this skill's directory):

1. `references/profile-schema.md` — the complete, authoritative schema for workload
   profiles (every field, type, default, constraint, and common validation error)
2. `references/running-pmlogsynth.md` — how to bootstrap and run pmlogsynth

Before any validation or generation, run `uv sync` to ensure the environment is ready.
Do NOT run `pmlogsynth --show-schema` — the bundled reference is identical and faster.

## Step 2 — Understand the Workload

If the user provided a description (via arguments or conversation), use it directly.

Otherwise, ask: **"Describe the workload you want to simulate."**

Good descriptions include:
- What kind of server/service (web, database, batch, etc.)
- How long the simulation should run
- What the interesting patterns are (spikes, ramps, diurnal cycles, steady state)
- Which resources are under pressure (CPU, memory, disk, network, or all)

## Step 3 — (Optional) Refine an Existing Profile

If the user references an existing profile ("update my-workload.yaml to add a network
spike"), read that file and include its content alongside the modification request.

## Step 4 — Generate the Profile

Produce a valid YAML workload profile. Follow these rules strictly:

1. **Output raw YAML only** — no markdown fences, no prose, no explanation mixed in
2. **Phase durations must sum to `meta.duration`** exactly (unless using `repeat`)
3. **First phase cannot use `transition: linear`** — there's no prior phase to interpolate from
4. **CPU ratios must sum to ≤ 1.0**: `user_ratio + sys_ratio + iowait_ratio`
5. **Use duration strings** for readability (`10m`, `1h`, `24h`) rather than raw seconds
6. **Pick a hardware profile** that fits the workload — see the schema reference for the
   7 bundled profiles (`generic-small` through `storage-optimized`)
7. **Add noise** (typically 0.02–0.05) to make the data look realistic, not robotic
8. **Use `transition: linear`** between phases with different load levels for smooth ramps
9. **Include comments** explaining what each phase represents (time of day, event, etc.)

### Realistic Value Ranges

These are typical ranges for production servers — use them as a sanity check:

| Metric | Idle | Moderate | Heavy | Saturated |
|--------|------|----------|-------|-----------|
| CPU utilization | 0.05–0.15 | 0.30–0.60 | 0.70–0.85 | 0.90–0.98 |
| Memory used_ratio | 0.20–0.40 | 0.50–0.70 | 0.75–0.85 | 0.88–0.95 |
| Disk read MB/s | 1–20 | 50–200 | 300–600 | 800+ |
| Disk write MB/s | 1–10 | 20–100 | 150–400 | 500+ |
| Network rx MB/s | 1–20 | 50–200 | 300–600 | 800+ |
| Network tx MB/s | 1–10 | 20–100 | 100–300 | 500+ |

## Step 5 — Save the Profile

1. Ensure the `generated-archives/` directory exists
2. Slugify the workload description into a filename:
   - Lowercase, replace spaces/special chars with hyphens
   - Trim to ≤ 50 characters
   - Append `.yaml`
   - If file exists, append `_1`, `_2`, etc. before `.yaml`

Example: "10-minute CPU spike at 90%" → `generated-archives/10-minute-cpu-spike-at-90.yaml`

## Step 6 — Validate

```bash
uv run pmlogsynth --validate generated-archives/<filename>.yaml
```

If `uv run` fails because dependencies aren't synced, run `uv sync` first.

- **Exit 0**: Profile is valid. Proceed to Step 7.
- **Exit 1** (validation error): Feed the error back into the generation, fix the YAML,
  and retry validation. If it fails a second time, show both the error and the YAML to the
  user and stop.
- **Exit 2** (I/O error): Report the error and stop.

## Step 7 — Generate the Archive

After validation passes, generate the actual PCP archive. Derive the archive name from
the profile filename (strip the `.yaml` extension):

```bash
uv run pmlogsynth -o ./generated-archives/<name> generated-archives/<filename>.yaml
```

If generation fails, report the error to the user.

## Step 8 — Report

Tell the user:
- Where the profile YAML was saved
- Where the archive was generated (the `.0`, `.index`, `.meta` files)
- How to inspect the archive:
  ```bash
  pmstat -a ./generated-archives/<name>
  pmval -a ./generated-archives/<name> kernel.all.cpu.user
  ```
