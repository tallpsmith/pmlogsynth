# Research: AI-Driven Profile Generation

**Branch**: `005-ai-profile-generation` | **Date**: 2026-03-03

## Research Questions

1. What format should the schema context document take for maximum AI agent compatibility?
2. Where does `--show-schema` fit in the CLI argument structure?
3. How should the Claude Code skill be structured?
4. Are the existing validation error messages sufficient for AI self-correction?
5. How is `importlib.resources` used to bundle and load a Markdown file?

---

## Q1: Schema Context Document Format

**Decision**: Plain Markdown file bundled as `pmlogsynth/schema_context.md`, loaded at
runtime via `importlib.resources`.

**Rationale**:
- Markdown is universally readable by all AI agents and humans alike.
- Bundling in the package ensures it ships with `pip install` and stays in sync with code.
- `importlib.resources` is stdlib (Python 3.7+), no new dependency.
- Static file (not generated at runtime) means it can be reviewed, diffed, and versioned in
  git like any other document.
- A version header in the document (matching `pyproject.toml` version) makes drift detectable
  by a Tier 1 test.

**Alternatives considered**:
- *Generated at runtime from dataclasses*: harder to read, fragile if schema changes, and
  the generation code would need its own tests. Rejected — static is simpler and more reliable.
- *JSON Schema*: machine-precise but not human-readable enough for AI agents to understand
  the semantics (e.g., "user_ratio + sys_ratio + iowait_ratio ≤ 1.0"). Rejected.
- *Embedded in cli.py as a string constant*: not diffable, hard to read in code review.
  Rejected.

**Token budget**: Full schema context doc including examples targets ≤6k tokens, well within
the 8k target stated in the spec assumptions. Rough estimate: field table ~1k, examples ~2k,
validation rules ~1k, hardware profiles ~0.5k, preamble/footer ~0.5k = ~5k tokens.

---

## Q2: `--show-schema` CLI Placement

**Decision**: Top-level informational flag, handled before subcommand dispatch — identical
pattern to `--list-metrics` and `--list-profiles`.

**Rationale**:
- Consistency with existing top-level flags — users already know the pattern.
- No subcommand needed; this is a pure query operation with no side effects.
- Composable: `pmlogsynth --show-schema > context.md` or piped directly to an AI agent.
- Handled in `_GLOBAL_FLAGS` so `_preprocess_argv` does not inject `generate`.

**Implementation sketch** (consistent with existing `_cmd_list_metrics` pattern):
```python
# In cli.py _build_parser():
parser.add_argument(
    "--show-schema",
    action="store_true",
    default=False,
    help="Print the pmlogsynth profile schema context document and exit.",
)

# In main():
if getattr(args, "show_schema", False):
    sys.exit(_cmd_show_schema())

# New handler:
def _cmd_show_schema() -> int:
    import importlib.resources as _pkg
    text = _pkg.read_text("pmlogsynth", "schema_context.md", encoding="utf-8")
    print(text, end="")
    return 0
```

**Note**: `importlib.resources.read_text` is available in Python 3.7+; deprecated in 3.11
in favour of `files()` API. For Python 3.8 compatibility, `read_text` is fine — the 3.9+
`files()` path can be added when minimum Python is bumped.

---

## Q3: Claude Code Skill Structure

**Decision**: `.claude/commands/generate-profile.md` — a Claude Code slash command that
orchestrates `pmlogsynth --show-schema` + AI generation + `pmlogsynth --validate`.

**Rationale**:
- Claude Code skills (`.claude/commands/*.md`) are the stated "primary delivery mechanism"
  in the spec assumptions.
- No Python code needed in the skill itself — it composes existing CLI tools.
- The skill can be invoked as `/generate-profile` from any Claude Code session in this repo.
- Keeps AI orchestration code out of the Python package (constitution Principle V).

**Skill flow**:
1. Run `pmlogsynth --show-schema` → capture schema context
2. Prompt user for workload description (or use `$ARGUMENTS`)
3. Call Claude API (via Claude Code's own session) to generate YAML
4. Write YAML to a file in `generated-archives/` with `.yaml` extension
5. Run `pmlogsynth --validate <file>` — if it fails, feed error back and retry once
6. Report success with archive generation command

**Alternatives considered**:
- *Python script using `anthropic` SDK*: would require `[ai]` extra, adds complexity.
  The skill approach is simpler and leverages Claude Code's existing session. Rejected for
  primary path — but valid as a secondary integration for non-Claude-Code users.
- *Interactive CLI subcommand `pmlogsynth generate-ai`*: Would embed AI API calls in the
  CLI, requiring `anthropic` as a dependency (even in optional form) to be explicitly
  invoked. More complex for the primary path. Reserved as a future option.

---

## Q4: Validation Error Message Quality

**Decision**: Existing validation errors are largely sufficient. No structural changes
needed. Minor improvements: ensure all `ValidationError` messages include the failing field
path and the constraint violated (most already do).

**Rationale**:
- Review of `profile.py` shows messages like:
  - `"phases[2] (spike): user_ratio + sys_ratio + iowait_ratio = 1.05 > 1.0 (FR-026)"`
  - `"meta.duration must be a positive integer or duration string"`
  - `"host.profile and inline host fields cannot be mixed without an 'overrides:' key"`
- These are already field-path-specific and constraint-describing.
- The only gap: `pmlogsynth --validate` currently returns exit code 1 with the error on
  stderr. This is adequate for AI self-correction — the AI can read stderr and retry.
- The schema context document should include a section on "Common Validation Errors" to
  give AI agents pre-emptive guidance, avoiding first-attempt failures.

**Alternatives considered**:
- *Structured JSON error output*: useful for machine parsing but not human-readable.
  AI agents can parse plain text just as easily. Rejected as over-engineering for now.

---

## Q5: `importlib.resources` for Bundled Markdown

**Decision**: Use `importlib.resources.read_text("pmlogsynth", "schema_context.md")` for
Python 3.8 compatibility. The file must be listed in `pyproject.toml` package data.

**Required pyproject.toml change**:
```toml
[tool.setuptools.package-data]
pmlogsynth = ["profiles/*.yaml", "schema_context.md"]
```

**Python 3.9+ compatibility note**: `importlib.resources.files("pmlogsynth").joinpath("schema_context.md").read_text()` is the modern API but requires Python 3.9+. Since the project targets Python 3.8+, use `read_text` with a `# type: ignore` or a try/except shim if mypy complains.

---

## Summary of Decisions

| Question | Decision |
|----------|----------|
| Schema doc format | Plain Markdown, bundled in package, version-stamped |
| `--show-schema` placement | Top-level flag, before subcommand dispatch |
| Claude Code skill | `.claude/commands/generate-profile.md` |
| Validation error quality | Sufficient as-is; add "Common Errors" section to schema doc |
| `importlib.resources` API | `read_text` for Python 3.8 compat |
