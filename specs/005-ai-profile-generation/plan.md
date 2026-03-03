# Implementation Plan: AI-Driven Profile Generation

**Branch**: `005-ai-profile-generation` | **Date**: 2026-03-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-ai-profile-generation/spec.md`

## Summary

Enable AI-assisted profile generation by: (1) bundling a versioned schema context document
that any AI agent can consume to generate valid profiles, (2) adding a `--show-schema`
top-level CLI flag that prints this document to stdout, and (3) delivering a Claude Code
skill as the primary integration path. The existing `WorkloadProfile.from_string` entry
point already supports programmatic YAML injection — the core archive pipeline requires
zero changes.

## Technical Context

**Language/Version**: Python 3.8+
**Primary Dependencies**: PyYAML (existing core); `anthropic>=0.20.0` (existing `[ai]`
optional extra — stays optional, NOT promoted to core)
**Storage**: Schema context bundled as `pmlogsynth/schema_context.md` (static file, loaded
via `importlib.resources`)
**Testing**: pytest + `unittest.mock`; schema content tests are pure Tier 1 (no PCP)
**Target Platform**: Linux (CI), macOS (developer, Tier 1/2 only)
**Project Type**: CLI tool
**Performance Goals**: Schema context document MUST be ≤8k tokens for broad model compat
**Constraints**: No new core pip dependencies; AI SDK stays in `[ai]` extra only
**Scale/Scope**: Single-user CLI; schema doc is a static artifact, not runtime-generated

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked post-design — all gates hold.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — PCP Archive Fidelity | ✅ PASS | AI generation feeds into existing `from_string` → existing validation → existing archive pipeline. No bypass. |
| II — Layered Testing | ✅ PASS | Schema doc tests are Tier 1 (read file, assert content). `--show-schema` is Tier 1 testable. No new PCP surface. |
| III — Declarative Profile-First | ✅ PASS | AI-generated YAML still goes through `WorkloadProfile.from_string`. No shortcuts. |
| IV — Phase-Aware Extensibility | ✅ PASS | `from_string` already exists per constitution (Phase 2 hook). `--show-schema` follows existing `--list-metrics` pattern. |
| V — Minimal External Dependencies | ✅ PASS | `anthropic` stays in `[ai]` extra. Schema doc is pure Markdown — zero new deps. |
| VI — CI-First Quality Gates | ✅ PASS | Schema doc tests are Tier 1 (always-run). No new conditional gates. |

## Project Structure

### Documentation (this feature)

```text
specs/005-ai-profile-generation/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── cli-show-schema.md
│   └── claude-skill.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
pmlogsynth/
├── cli.py               # MODIFY: add --show-schema top-level informational flag
└── schema_context.md    # NEW: versioned schema context document (bundled)

.claude/commands/
└── generate-profile.md  # NEW: Claude Code skill for AI-driven profile generation

man/
└── pmlogsynth.1         # MODIFY: add --show-schema to SYNOPSIS + Global Options;
                         #         also backfill --list-metrics, --list-profiles, -C
                         #         which appear in SYNOPSIS but are missing from OPTIONS

tests/unit/
└── test_schema_context.py  # NEW: Tier 1 tests — schema doc exists, version matches,
                            #      --show-schema exits 0 and produces content
```

**Structure Decision**: Single-project (Option 1). All changes are additive to existing
`pmlogsynth/` package. No new subpackages or top-level directories required beyond
`.claude/commands/` (already conventional for Claude Code skills).

## Complexity Tracking

> No constitution violations requiring justification.
