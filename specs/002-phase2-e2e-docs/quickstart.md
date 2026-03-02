# Quickstart: Phase 2 Planning Notes

**Date**: 2026-03-02

## Decision

No standalone quickstart document is delivered in Phase 2.

The README `Quick Start` section IS the quickstart. It already covers the core workflow;
it needs only a one-liner `--validate` preamble before the generate step and a one-sentence
`repeat:daily` callout. That's ~3 lines added to an existing section — not a new document.

`specs/001-pmlogsynth-phase1/quickstart.md` was reviewed and found accurate (no CLI drift),
but it lives in `specs/` where users don't look. It receives no further maintenance and is
considered a historical planning artifact.

## Automated Test

The `test_quickstart_workflow` E2E test validates the workflow the README Quick Start
describes. It runs the four steps as subprocesses:

```
1. pmlogsynth --validate -C <hw_dir> <profile>   → rc 0
2. pmlogsynth -C <hw_dir> -o <tmpdir>/out <profile>  → rc 0
3. pmlogcheck <tmpdir>/out   → rc 0
4. pmval -a <tmpdir>/out kernel.all.load   → rc 0
```

If the README's Quick Start ever drifts from the CLI, this test catches it.
See `contracts/e2e-test-contract.md` for the full test contract.
