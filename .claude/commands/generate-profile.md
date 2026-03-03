Generate a valid pmlogsynth YAML workload profile from a natural language description,
then validate it with `pmlogsynth --validate`.

## Arguments

`$ARGUMENTS` — workload description (optional; prompted if absent)

## Step 1 — Acquire Schema Context

Run the following command and capture its stdout as the schema context:

```bash
pmlogsynth --show-schema
```

If this command fails (exit code ≠ 0), report the error and stop. Do not proceed.

## Step 2 — Acquire Workload Description

- If `$ARGUMENTS` is non-empty, use it as the workload description.
- Otherwise, ask the user: "Describe the workload you want to simulate."

## Step 3 — (Optional) Acquire Existing Profile for Iterative Refinement

If the user's description references an existing profile (e.g., "update my-workload.yaml
to add a network spike"), ask: "Provide the path to the existing profile, or press Enter
to generate from scratch."

If a path is provided, read the file contents and include the existing YAML in the
generation prompt alongside the modification request.

## Step 4 — Generate Profile

Using the current Claude session, generate a valid pmlogsynth YAML profile.

The generation prompt MUST include:
1. The full schema context (from Step 1) as reference
2. The workload description (from Step 2)
3. The existing profile content (from Step 3, if provided)
4. Instruction to produce ONLY the YAML profile, no explanation or markdown fences
5. Instruction that the sum of all phase durations MUST equal `meta.duration`, unless
   a phase uses `repeat`

## Step 5 — Save Profile

Create the `generated-archives/` directory if it does not exist.

Slugify the workload description to create a filename:
- Lowercase, replace spaces and special characters with hyphens
- Trim to a reasonable length (≤ 50 characters)
- Append `.yaml`

Example: "10-minute CPU spike at 90%" → `generated-archives/10-minute-cpu-spike-at-90.yaml`

If the target file already exists, append a numeric suffix (`_1`, `_2`, etc.) before `.yaml`.

Write the generated YAML to the chosen path.

## Step 6 — Validate Profile

```bash
pmlogsynth --validate generated-archives/<filename>.yaml
```

**If exit code 0**: proceed to Step 7.

**If exit code 1** (validation error): capture the stderr output and feed the error
back to the AI with: "The profile failed validation with this error: `<error>`. Please
correct the profile." Then retry Steps 4–6 once. If validation fails again, report both
the error message and the generated profile YAML to the user and stop.

**If exit code 2** (I/O error): report the error and stop.

## Step 7 — Report Success

Report to the user:
- Profile saved to: `<path>`
- Generate the archive:
  ```bash
  pmlogsynth -o ./generated-archives/<name> <path>
  ```
- Inspect the archive:
  ```bash
  pmstat -a ./generated-archives/<name>
  ```
