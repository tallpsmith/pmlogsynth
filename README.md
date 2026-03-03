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

```yaml
# spike.yaml
meta:
  hostname: demo-host
  timezone: UTC
  duration: 600
  interval: 60

host:
  profile: generic-small

phases:
  - name: baseline
    duration: 300
    cpu:
      utilization: 0.15

  - name: spike
    duration: 300
    cpu:
      utilization: 0.90
```

### 2. Validate your profile

```bash
pmlogsynth --validate spike.yaml
# Exit 0 = valid, Exit 1 = error (stderr shows what's wrong)
```

> **Note**: `repeat: daily` cannot be combined with other phases — validation will reject it.

### 3. Generate the archive

```bash
pmlogsynth -o ./out spike.yaml
# Creates: out.0  out.index  out.meta
```

### 4. Verify with PCP tools

```bash
pmlogcheck ./out
pmval -a ./out kernel.all.cpu.user
pmrep -a ./out -o csv kernel.all.cpu.user mem.util.used
```

### 5. Explore available options

```bash
pmlogsynth --list-profiles   # show hardware profiles
pmlogsynth --list-metrics    # show all producible PCP metrics
```

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

---

## Metrics

24 PCP metrics — `pmlogsynth --list-metrics` or `man pmlogsynth`.

---

## CLI Reference

Full CLI reference — `man pmlogsynth`.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, test structure, and PR conventions.
