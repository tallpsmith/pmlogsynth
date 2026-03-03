# Data Model: AI-Driven Profile Generation

**Branch**: `005-ai-profile-generation` | **Date**: 2026-03-03

## Overview

This feature introduces one new entity (`SchemaContextDocument`) and enhances one
conceptual entity (`ValidationReport`). The core data model — `WorkloadProfile`,
`HardwareProfile`, `Phase`, and all stressor types — is unchanged.

---

## New Entity: SchemaContextDocument

A versioned, self-contained Markdown document that describes the pmlogsynth profile YAML
schema in enough detail for any capable AI agent to generate valid profiles without
additional reference material.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | `str` | Schema doc version, must match `pyproject.toml` project version |
| `content` | `str` | Full Markdown text of the schema context document |
| `token_estimate` | `int` | Approximate token count (informational; target ≤ 8000) |

### Storage

- **At rest**: `pmlogsynth/schema_context.md` — a static Markdown file checked into source
  control, bundled with the Python package via `pyproject.toml` package-data.
- **At runtime**: loaded via `importlib.resources.read_text("pmlogsynth", "schema_context.md")`.
- **Versioning**: the document contains a `Schema Version:` header that must match the
  `version` field in `pyproject.toml`. A Tier 1 test enforces this invariant.

### Validation Rules

- Document MUST be non-empty.
- Document MUST contain a `Schema Version:` line matching `pyproject.toml` version.
- Document MUST contain a section for each top-level profile key: `meta`, `host`, `phases`.
- Document MUST list all 7 bundled hardware profile names.
- Document MUST include at least one complete annotated YAML example.
- Document MUST be ≤ 8000 tokens (enforced by Tier 1 test using a character-count proxy:
  ≤ 32000 characters, since average token ≈ 4 chars).

### State Transitions

Static artifact — no state transitions. Updated only when the profile schema changes (with
a version bump).

---

## Enhanced Concept: ValidationReport

`ValidationError` already exists in `profile.py`. This feature makes no structural changes
to it, but the schema context document adds a "Common Validation Errors" section that
allows AI agents to avoid first-attempt failures. The conceptual model:

| Field | Type | Description |
|-------|------|-------------|
| `message` | `str` | Human/AI-readable description of what failed |
| `field_path` | `str` | Dotted path to the failing field (e.g., `phases[2].cpu.user_ratio`) |
| `constraint` | `str` | The rule violated (e.g., `user_ratio + sys_ratio + iowait_ratio ≤ 1.0`) |
| `exit_code` | `int` | `1` for validation errors, `2` for I/O errors, `3` for PCP errors |

**Current state**: `ValidationError` is a simple exception with a string message. The
message already includes field path and constraint for most cases (see research.md Q4).
No code changes required.

---

## Conceptual Entity: ProfileGenerationRequest

Not a Python type — describes the logical inputs to a profile generation session. Used by
the Claude Code skill (`.claude/commands/generate-profile.md`).

| Field | Type | Description |
|-------|------|-------------|
| `description` | `str` | Natural language workload description from the user |
| `schema_context` | `str` | Output of `pmlogsynth --show-schema` |
| `existing_profile` | `Optional[str]` | Existing YAML profile for iterative refinement (FR-009) |
| `output_path` | `str` | Where the generated `.yaml` file should be written |

### Flow

```
user description
       │
       ▼
[Claude Code skill]
       │
       ├─► pmlogsynth --show-schema ──► schema_context
       │
       ├─► (optional) read existing_profile ──► existing YAML
       │
       ▼
[AI generation: description + schema_context + existing_profile → YAML]
       │
       ▼
write YAML to output_path
       │
       ▼
pmlogsynth --validate output_path
       │
  ┌────┴────┐
  │         │
 PASS      FAIL
  │         │
  ▼         ▼
report    feed ValidationReport back to AI → retry once
success
```

---

## Unchanged Entities

The following core entities from `pmlogsynth/profile.py` are **not modified**:

- `WorkloadProfile` — still the authoritative parsed representation
- `HardwareProfile` — no changes
- `Phase`, `CpuStressor`, `MemoryStressor`, `DiskStressor`, `NetworkStressor` — no changes
- `ProfileMeta`, `HostConfig` — no changes
- `ProfileResolver` — no changes
- `ValidationError` — no structural changes (see above)
