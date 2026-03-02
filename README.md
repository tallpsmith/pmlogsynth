# pmlogsynth

[![CI](https://github.com/tallpsmith/pmlogsynth/actions/workflows/ci.yml/badge.svg)](https://github.com/tallpsmith/pmlogsynth/actions/workflows/ci.yml)

Generate synthetic [PCP](https://pcp.io/) v3 archives from declarative YAML workload
profiles — no running `pmcd`, no root access, no real hardware required.

Designed for testing PCP-based monitoring pipelines, reproducing incidents at arbitrary
historical timestamps, and generating load-shaped datasets for analysis tooling.

---

## Installation

**Prerequisites**: PCP must be installed to write archives (`libpcp_import`) and to
verify them (`pmlogcheck`, `pmval`).

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

**macOS** (Homebrew): PCP's Python bindings are installed into Homebrew's Python only.
Use `pmpython` or a virtualenv built from the Homebrew Python:
```bash
$(readlink -f $(which pmpython)) -m venv .venv
source .venv/bin/activate
pip install pmlogsynth
```

**From source**:
```bash
git clone https://github.com/tallpsmith/pmlogsynth
cd pmlogsynth
pip install -e ".[dev]"
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

### 2. Generate the archive

```bash
pmlogsynth -o ./out spike.yaml
# Creates: out.0  out.index  out.meta
```

### 3. Verify with PCP tools

```bash
pmlogcheck ./out
pmval -a ./out kernel.all.cpu.user
pmrep -a ./out -o csv kernel.all.cpu.user mem.util.used
```

### 4. Explore available options

```bash
pmlogsynth --list-profiles   # show hardware profiles
pmlogsynth --list-metrics    # show all producible PCP metrics
pmlogsynth --validate spike.yaml && echo valid
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

## Running Tests

```bash
# Tier 1: unit tests (no PCP needed)
pytest tests/tier1/ -v

# Tier 1 + Tier 2: all non-E2E tests (PCP mocked)
pytest tests/tier1/ tests/tier2/ -v

# All tiers (Tier 3 auto-skipped if pcp.pmi unavailable)
pytest -v

# Run the full local quality gate (lint + types + Tier 1 + Tier 2)
./pre-commit.sh
```

---

## Contributing

Issues and pull requests welcome at
[github.com/tallpsmith/pmlogsynth](https://github.com/tallpsmith/pmlogsynth).
