# Contract: Claude Code Skill — `generate-profile`

**Feature**: 005-ai-profile-generation | **Date**: 2026-03-03

## Purpose

The `/generate-profile` Claude Code skill is the primary AI-driven profile generation
integration (FR-003). It orchestrates `pmlogsynth --show-schema`, AI generation, and
`pmlogsynth --validate` in a single conversational workflow.

---

## Invocation

```
/generate-profile [<workload description>]
```

### Examples

```
/generate-profile a week-long SaaS archive with diurnal load and a CPU spike at 2:30pm

/generate-profile high-memory database workload with 80% RAM utilisation and low CPU

/generate-profile                        # prompts user for description interactively
```

---

## Skill Flow Contract

The skill MUST execute the following steps in order:

### Step 1 — Acquire Schema Context

```bash
pmlogsynth --show-schema
```

Capture stdout as `$SCHEMA_CONTEXT`. If this command fails (exit code ≠ 0), report the
error and stop.

### Step 2 — Acquire Workload Description

- If `$ARGUMENTS` is non-empty, use it as the workload description.
- Otherwise, ask the user: "Describe the workload you want to simulate."

### Step 3 — (Optional) Acquire Existing Profile for Iterative Refinement

If the user's description references an existing profile (e.g., "update the spike profile
to use disk I/O"), ask: "Provide the path to the existing profile, or press Enter to
generate from scratch."

If provided, read the existing profile content and include it in the generation prompt.

### Step 4 — Generate Profile

Using the current Claude session, generate a valid pmlogsynth YAML profile from:
- The schema context (`$SCHEMA_CONTEXT`)
- The workload description
- The existing profile content (if provided)

The generation prompt MUST include:
1. The full schema context as reference
2. The workload description
3. Instruction to produce ONLY the YAML profile, no explanation
4. Instruction that the total phase durations MUST equal `meta.duration` (unless `repeat` is used)

### Step 5 — Save Profile

Write the generated YAML to `generated-archives/<slugified-description>.yaml`.

If the target file already exists, append a numeric suffix (`_1`, `_2`, etc.).

### Step 6 — Validate Profile

```bash
pmlogsynth --validate generated-archives/<filename>.yaml
```

- **If exit code 0**: proceed to Step 7.
- **If exit code 1** (validation error): capture stderr, feed the error back to the AI
  with: "The profile failed validation with this error: `<error>`. Please correct the
  profile." Retry generation once (Step 4 → Step 5 → Step 6). If it fails again, report
  both the error and the generated profile to the user and stop.
- **If exit code 2** (I/O error): report and stop.

### Step 7 — Report Success

Report to the user:
- Profile saved to: `<path>`
- Generate archive: `pmlogsynth -o ./generated-archives/<name> <path>`
- Inspect archive: `pmstat -a ./generated-archives/<name>`

---

## Input Contract

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| Workload description | string | Yes (prompted if absent) | Natural language description |
| Existing profile path | file path | No | For iterative refinement (FR-009) |

## Output Contract

| Output | Description |
|--------|-------------|
| YAML file | Written to `generated-archives/<name>.yaml` |
| Validation status | Reported inline; retried once on failure |
| Archive command | Shown to user on success |

---

## Skill File Location

```text
.claude/commands/generate-profile.md
```

This file is the skill definition consumed by Claude Code. It contains the full workflow
description in natural language, with shell commands embedded as bash blocks.

---

## Non-Goals

- The skill does NOT invoke `pmlogsynth` to generate the archive itself (that is left to
  the user to run with the provided command).
- The skill does NOT call the Anthropic API directly — it uses the current Claude Code
  session.
- The skill does NOT support non-Claude AI agents. For other agents, use
  `pmlogsynth --show-schema` to obtain the schema context and provide it manually.
