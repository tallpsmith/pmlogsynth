# Quickstart: AI-Driven Profile Generation

**Feature**: 005-ai-profile-generation | **Date**: 2026-03-03

## Overview

This feature lets you describe a workload in plain English and receive a valid pmlogsynth
profile. No YAML hand-crafting required.

---

## Option A — Claude Code Skill (Recommended)

If you're running Claude Code in this repo, use the `/generate-profile` skill:

```
/generate-profile a 24-hour SaaS workload with diurnal load, 8am-6pm business hours peak at 85% CPU, and a disk I/O spike at 2:30pm lasting 10 minutes
```

The skill will:
1. Load the pmlogsynth schema context automatically
2. Generate a valid YAML profile
3. Validate it with `pmlogsynth --validate`
4. Save it to `generated-archives/` and show you the archive generation command

---

## Option B — Any AI Agent (Schema Context Method)

Works with Claude, ChatGPT, Gemini, or any local model with sufficient context.

### Step 1 — Get the schema context

```bash
pmlogsynth --show-schema > /tmp/pmlogsynth-schema.md
```

### Step 2 — Provide it to your AI agent

Paste the content of `/tmp/pmlogsynth-schema.md` as a system prompt or context block,
then describe your workload:

> "Using the pmlogsynth schema above, generate a profile for: a week-long archive with
> overnight quiet periods (5% CPU), business hours peaks (70% CPU), and a memory pressure
> event on day 3."

### Step 3 — Save and validate the generated profile

```bash
# Save the AI's output
cat > generated-archives/my-workload.yaml << 'EOF'
<paste generated YAML here>
EOF

# Validate it
pmlogsynth --validate generated-archives/my-workload.yaml
```

If validation fails, paste the error message back to the AI agent with: "Please correct
the profile. The validation error was: `<error>`"

### Step 4 — Generate the archive

```bash
pmlogsynth -o ./generated-archives/my-workload generated-archives/my-workload.yaml
```

---

## Option C — Iterative Refinement

To modify an existing profile, reference it in your description:

**With Claude Code skill:**
```
/generate-profile update generated-archives/my-workload.yaml to add a network saturation event at midnight
```

**With any AI agent:**
Include the existing profile YAML in your context along with the schema, and ask for a
specific modification.

---

## Validation Errors — Self-Correction Guide

If a generated profile fails validation, the error message tells you exactly what to fix.
Common errors and their fixes:

| Error | Fix |
|-------|-----|
| `Sum of phase durations (X) does not equal meta.duration (Y)` | Adjust phase durations to sum to `meta.duration` |
| `user_ratio + sys_ratio + iowait_ratio = X > 1.0` | Reduce one or more CPU ratios so their sum ≤ 1.0 |
| `phases[0]: first phase cannot use 'transition: linear'` | Remove `transition: linear` from the first phase |
| `A phase with repeat:daily must be the only phase` | Remove all other phases when using `repeat: daily` |
| `Inline host requires at least 'cpus' and 'memory_kb'` | Add both fields, or use `host.profile: generic-small` instead |
| `Hardware profile 'X' not found` | Use one of the 7 bundled profiles listed in `pmlogsynth --list-profiles` |

Run `pmlogsynth --show-schema` for the full field reference.

---

## Available Hardware Profiles

```bash
pmlogsynth --list-profiles
```

| Profile | Typical Use |
|---------|-------------|
| `generic-small` | Small VM, test environments |
| `generic-medium` | Mid-range server |
| `generic-large` | Production server |
| `generic-xlarge` | High-end server |
| `compute-optimized` | CPU-heavy workloads |
| `memory-optimized` | Memory-heavy workloads |
| `storage-optimized` | Disk I/O-heavy workloads |
