# pmlogsynth

[![CI](https://github.com/tallpsmith/pmlogsynth/actions/workflows/ci.yml/badge.svg)](https://github.com/tallpsmith/pmlogsynth/actions/workflows/ci.yml)

Generate synthetic [PCP](https://pcp.io/) v3 archives from declarative YAML workload
profiles — no running `pmcd`, no root access, no real hardware required.

Designed for testing PCP-based monitoring pipelines, reproducing incidents at arbitrary
historical timestamps, and generating load-shaped datasets for analysis tooling.

---

## Installation

**Prerequisites**: PCP (`python3-pcp` / `cpmapi`) is a **hard dependency** — it is
required at import time for metric type and unit constants, not just for archive
writing.  All tests (unit, integration, and E2E) need PCP's Python bindings available.

**Linux (Debian/Ubuntu)**:
```bash
sudo apt-get install pcp python3-pcp
pip install pmlogsynth
```

**Linux (RHEL/Fedora)**:
```bash
sudo dnf install pcp python3-pcp
pip install pmlogsynth
```

**macOS** (Homebrew): PCP compiles its Python bindings against Homebrew's Python.
The bindings are **only** available to that specific Python — if you run pmlogsynth
or its tests from a different Python (system, pyenv, conda), `import cpmapi` will fail.

Use the provided setup script, which handles venv creation correctly on all platforms:
```bash
./setup-venv.sh
source .venv/bin/activate
```

**From source**:
```bash
git clone https://github.com/tallpsmith/pmlogsynth
cd pmlogsynth
./setup-venv.sh
source .venv/bin/activate
```

---

## Quick Start

### 1. Create a profile

[`docs/spike.yml`](docs/spike.yml) is ready to use — or write your own:

```yaml
# docs/spike.yml
meta:
  hostname: demo-host
  timezone: UTC
  duration: 10m
  interval: 60

host:
  profile: generic-small

phases:
  - name: baseline
    duration: 5m
    cpu:
      utilization: 0.15

  - name: spike
    duration: 5m
    cpu:
      utilization: 0.90
```

### 2. Validate your profile

```bash
pmlogsynth --validate docs/spike.yml
# Exit 0 = valid, Exit 1 = error (stderr shows what's wrong)
```

> **Note**: `repeat: daily` cannot be combined with other phases — validation will reject it.

### 3. Generate the archive

```bash
pmlogsynth -o ./generated-archives/spike docs/spike.yml
# Creates: generated-archives/spike.0  spike.index  spike.meta
```

> **Note**: `generated-archives/` is gitignored — a safe scratch space for locally
> generated archives.

### 4. Verify with PCP tools

```bash
pmlogcheck ./generated-archives/spike
pmval -a ./generated-archives/spike kernel.all.cpu.user
pmrep -a ./generated-archives/spike -o csv kernel.all.cpu.user mem.util.used
```

### 5. Explore available options

```bash
pmlogsynth --list-profiles   # show hardware profiles
pmlogsynth --list-metrics    # show all producible PCP metrics
pmlogsynth --show-schema     # dump the full profile schema (for AI agents)
```

### 6. Generate a profile with AI

If you're using [Claude Code](https://claude.ai/claude-code), the `/generate-profile`
skill can turn a plain-English description into a valid YAML profile:

```
/generate-profile a 1-hour archive of a memory-constrained host under heavy disk I/O
```

The skill feeds `--show-schema` output to the model as context, so the generated profile
is always valid against the current schema.

---

## Bundled Hardware Profiles

| Name | CPUs | RAM | Disks | NICs |
|------|------|-----|-------|------|
| `generic-small` | 2 | 8 GB | 1× NVMe | 1× 10GbE |
| `generic-medium` | 4 | 16 GB | 1× NVMe | 1× 10GbE |
| `generic-large` | 8 | 32 GB | 2× NVMe | 1× 10GbE |
| `generic-xlarge` | 16 | 64 GB | 2× NVMe | 2× 10GbE |
| `compute-optimized` | 8 | 16 GB | 1× NVMe | 1× 10GbE |
| `memory-optimized` | 4 | 64 GB | 1× NVMe | 1× 10GbE |
| `storage-optimized` | 4 | 16 GB | 4× HDD | 1× 10GbE |

Use `host.profile: <name>` in your profile, or add your own profiles to
`~/.pcp/pmlogsynth/profiles/`.

---

## Profile Format

Full YAML schema documentation — all fields, types, defaults, valid ranges,
and constraints — is in [`docs/profile-format.md`](docs/profile-format.md).

A complete, ready-to-run example covering all four stressor domains is in
[`docs/complete-example.yml`](docs/complete-example.yml).

### Relative start times

The `meta.start` field accepts a **relative offset** in addition to absolute
ISO 8601 timestamps.  A relative offset is a PCP interval string prefixed with
`-`, resolved against the clock at invocation time:

```yaml
meta:
  start: -90m      # 90 minutes ago
  start: -2h       # 2 hours ago
  start: -1h30m    # 1 hour 30 minutes ago
  start: -3d       # 3 days ago
  start: -2days    # same — PCP interval strings accepted
```

This is useful for replaying realistic-looking archives anchored to "now" —
for example, a simulated spike that started an hour ago.  Positive offsets
(`+30m`) and bare `-` are rejected with a descriptive error.

---

## Metrics

53 PCP metrics — `pmlogsynth --list-metrics` or `man pmlogsynth`.

---

## CLI Reference

Full CLI reference — `man pmlogsynth`.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, test structure, and PR conventions.
