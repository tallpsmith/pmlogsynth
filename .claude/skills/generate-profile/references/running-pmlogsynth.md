# Running pmlogsynth

pmlogsynth requires PCP Python bindings (`python3-pcp`) which are system packages, not
pip-installable. The project uses `uv` for dependency management.

## Bootstrap

Before running any `pmlogsynth` commands, ensure the environment is ready:

```bash
uv sync
```

This is idempotent — safe to run every time. It installs/updates dependencies and makes
`uv run pmlogsynth` available.

## Running commands

Always use `uv run` to invoke pmlogsynth — this ensures the correct virtualenv is used:

```bash
# Validate a workload profile
uv run pmlogsynth --validate <profile.yaml>

# Generate an archive from a workload profile
uv run pmlogsynth -o ./generated-archives/<name> <profile.yaml>

# Validate a fleet profile
uv run pmlogsynth fleet --validate <fleet-profile.yaml>

# Generate fleet archives (--seed for reproducibility)
uv run pmlogsynth fleet --seed 42 -o ./generated-archives/<fleet-name> <fleet-profile.yaml>

# Dry-run fleet (preview host assignments)
uv run pmlogsynth fleet --dry-run <fleet-profile.yaml>
```

## Troubleshooting

If `uv run pmlogsynth` fails with an import error for `cpmapi` or `pcp`, PCP's Python
bindings are not installed system-wide. On macOS, run `./setup-venv.sh` first — it
creates a venv that links to Homebrew's PCP Python bindings.

If `uv` is not available, fall back to:
```bash
pip install -e ".[dev]" && pmlogsynth ...
```
