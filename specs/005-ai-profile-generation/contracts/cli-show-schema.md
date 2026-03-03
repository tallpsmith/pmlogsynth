# Contract: `--show-schema` CLI Flag

**Feature**: 005-ai-profile-generation | **Date**: 2026-03-03

## Purpose

The `--show-schema` flag prints the pmlogsynth profile schema context document to stdout
and exits. Its output is the primary mechanism for providing AI agents with the context
needed to generate valid profiles (FR-004).

---

## Invocation

```
pmlogsynth --show-schema
```

### Behaviour

- Prints the full content of `pmlogsynth/schema_context.md` to stdout.
- Exits with code `0` on success.
- Exits with code `1` if the bundled file cannot be read (should never happen in a correctly
  installed package; indicates broken installation).
- Produces no output to stderr on success.
- Compatible with shell redirection and piping:
  ```bash
  pmlogsynth --show-schema > context.md          # save to file
  pmlogsynth --show-schema | pbcopy               # macOS clipboard
  pmlogsynth --show-schema | wc -w                # token budget check
  ```

### Argument Conflicts

- `--show-schema` is a top-level informational flag. It is incompatible with all
  generate-subcommand flags (`--output`, `--validate`, `--force`, etc.).
- If `--show-schema` is present, the `generate` subcommand is NOT injected by
  `_preprocess_argv`. Handled before subcommand dispatch in `main()`, same as
  `--list-metrics` and `--list-profiles`.

---

## Implementation Contract

### Parser Registration

```python
# In _build_parser(), alongside --list-metrics and --list-profiles:
parser.add_argument(
    "--show-schema",
    action="store_true",
    default=False,
    help="Print the profile schema context document (for AI agents) and exit.",
)
```

`--show-schema` must also be added to `_GLOBAL_FLAGS` in `_preprocess_argv` so it is not
consumed by the generate subparser.

### Handler

```python
def _cmd_show_schema() -> int:
    import importlib.resources as _pkg
    try:
        text = _pkg.read_text("pmlogsynth", "schema_context.md", encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        print(f"error: schema context not found: {exc}", file=sys.stderr)
        return 1
    print(text, end="")
    return 0
```

### Dispatch in `main()`

```python
if getattr(args, "show_schema", False):
    sys.exit(_cmd_show_schema())
```

Placed after version/help checks, before `--list-metrics`, `--list-profiles`, and
`_cmd_generate`.

---

## Schema Context Document Contract

The file printed by `--show-schema` (`pmlogsynth/schema_context.md`) MUST:

1. Begin with a `# pmlogsynth Profile Schema` heading.
2. Include a `Schema Version: <version>` line matching `pyproject.toml` project version.
3. Cover all top-level profile keys: `meta`, `host`, `phases` (with all subfields).
4. List all 7 bundled hardware profile names.
5. Include at least one complete, annotated YAML example (simple) and one complex example.
6. Include a "Common Validation Errors" section listing error messages AI agents may
   encounter and how to fix them.
7. Be self-contained — no external links, no references to other documents.
8. Not exceed 32,000 characters (proxy for ≤ 8,000 tokens).

---

## Test Contract

Tier 1 tests in `tests/unit/test_schema_context.py` MUST assert:

| Test | Assertion |
|------|-----------|
| `test_schema_context_file_exists` | `importlib.resources.read_text("pmlogsynth", "schema_context.md")` succeeds |
| `test_schema_context_version_matches` | Version line in doc matches `pyproject.toml` version |
| `test_schema_context_has_required_sections` | Headings for `meta`, `host`, `phases` present |
| `test_schema_context_lists_hardware_profiles` | All 7 bundled profile names present |
| `test_schema_context_within_token_budget` | `len(content) <= 32000` |
| `test_show_schema_cli_exits_zero` | `pmlogsynth --show-schema` exits 0 with non-empty stdout |
