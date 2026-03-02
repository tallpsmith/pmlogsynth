# Quickstart: pmlogsynth

**Date**: 2026-03-01

This guide gets you from zero to a verified PCP archive in under 5 minutes.

---

## Prerequisites

- Python 3.8+
- PCP installed (provides `pmlogcheck`, `pmval`, `libpcp_import.so`)
- `python3-pcp` system package (provides `pcp.pmi` Python bindings)

**Linux (Debian/Ubuntu)**:
```bash
sudo apt-get install pcp python3-pcp
```

**Linux (RHEL/Fedora)**:
```bash
sudo dnf install pcp python3-pcp
```

**macOS**: Full E2E archive generation works via Homebrew. Install PCP with Homebrew and
use `pmpython` (Homebrew's Python) as your interpreter — the `pcp` Python package is
installed into Homebrew's Python site-packages (e.g. `/opt/homebrew/lib/python3.x/site-packages/pcp/`)
and is not visible to the system `python3` (Xcode). Either invoke `pmlogsynth` via
`pmpython`, or create your virtualenv using the Homebrew Python that `pmpython` points to:

```bash
# Confirm pcp.pmi is available
pmpython -c "import pcp.pmi; print('OK')"

# Create a venv using the same Python pmpython uses
$(readlink -f $(which pmpython)) -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Installation

```bash
# From source (development)
git clone https://github.com/<org>/pmlogsynth
cd pmlogsynth
pip install -e .

# From PyPI (when published)
pip install pmlogsynth
```

---

## 5-Minute Demo

### 1. Create a profile

```yaml
# spike.yaml
meta:
  hostname: demo-host
  timezone: UTC
  duration: 600    # 10 minutes
  interval: 60
  noise: 0.03

host:
  profile: generic-small

phases:
  - name: baseline
    duration: 300
    cpu:
      utilization: 0.15
      user_ratio: 0.70
      sys_ratio: 0.20
      iowait_ratio: 0.10
    memory:
      used_ratio: 0.40

  - name: spike
    duration: 300
    cpu:
      utilization: 0.90
      user_ratio: 0.85
      sys_ratio: 0.10
      iowait_ratio: 0.05
    memory:
      used_ratio: 0.60
```

### 2. Validate the profile (optional)

```bash
pmlogsynth --validate spike.yaml
echo "Exit code: $?"   # 0 = valid
```

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

During the `spike` phase, `kernel.all.cpu.user` values should be ~85% of total CPU ticks.

---

## Hardware Profiles

### List available profiles

```bash
pmlogsynth --list-profiles
```

### Use a different bundled profile

```yaml
host:
  profile: generic-large    # 8 CPUs, 32 GB RAM, 2× NVMe
```

### Add per-CPU verification

```bash
pmval -a ./out kernel.percpu.cpu.user
# Shows 8 CPU instances for generic-large
```

### Override profile fields

```yaml
host:
  profile: generic-large
  overrides:
    cpus: 16          # override just the CPU count
```

### User-defined profiles

```bash
mkdir -p ~/.pcp/pmlogsynth/profiles/
cat > ~/.pcp/pmlogsynth/profiles/my-server.yaml <<EOF
name: my-server
cpus: 32
memory_kb: 134217728
disks:
  - name: nvme0n1
    type: nvme
interfaces:
  - name: bond0
    speed_mbps: 25000
EOF
pmlogsynth --list-profiles   # my-server appears as "user"
```

---

## Advanced Usage

### Anchor archive to a historical time window

```bash
pmlogsynth --start "2024-01-15 09:00:00 UTC" -o ./incident-replay spike.yaml
```

### Linear phase transitions (gradual ramp)

```yaml
phases:
  - name: baseline
    duration: 300
    cpu:
      utilization: 0.15

  - name: ramp-up
    duration: 300
    transition: linear   # interpolates from 15% to 90% over 5 minutes
    cpu:
      utilization: 0.90
```

### Repeating phases

```yaml
meta:
  duration: 86400     # 24 hours

phases:
  - name: background
    duration: 82800   # 23 hours

  - name: noon-peak
    duration: 3600    # 1 hour
    repeat: daily
    cpu:
      utilization: 0.93
```

### Per-domain noise

```yaml
phases:
  - name: noisy-cpu
    duration: 300
    cpu:
      utilization: 0.80
      noise: 0.10      # noisier CPU; other domains use meta.noise
```

### CI pipeline integration

```yaml
# .github/workflows/integration-test.yml
- run: pip install pmlogsynth
- run: pmlogsynth -o /tmp/test-archive tests/profiles/spike.yaml
- run: pmlogcheck /tmp/test-archive
- run: python3 tests/verify_archive.py /tmp/test-archive
```

### Test-specific hardware profiles (via -C)

```bash
# Use profiles from a local directory without touching ~/.pcp/pmlogsynth/profiles/
pmlogsynth -C ./tests/fixtures/profiles -o ./out test-profile.yaml
```

---

## Discovering Metrics

```bash
# See all PCP metrics the tool can produce
pmlogsynth --list-metrics

# Then query any of them against a generated archive
pmval -a ./out disk.all.read_bytes
pmval -a ./out network.interface.in.bytes
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `output files already exist` | `out.0`, `out.index`, or `out.meta` exist | Use `--force` to overwrite, or choose a different `-o` path |
| `hardware profile 'X' not found` | Profile name misspelled or not installed | Run `--list-profiles` to see available names |
| `cpu ratios sum to N > 1.0` | `user_ratio + sys_ratio + iowait_ratio > 1.0` | Reduce one of the ratios |
| `first phase cannot use linear transition` | First phase has `transition: linear` | Remove `transition:` from first phase |
| `pcp.pmi not available` | Wrong Python interpreter | On Linux: install `python3-pcp`. On macOS: use `pmpython` or a venv built from Homebrew Python (see Prerequisites) |
| Archive fails `pmlogcheck` | Bug in writer | File an issue with the profile and `pmlogcheck` output |

---

## Running Tests

```bash
# Tier 1: unit tests (no PCP needed)
pytest tests/tier1/ -v

# Tier 1 + Tier 2: all non-E2E tests (PCP mocked)
pytest tests/tier1/ tests/tier2/ -v

# All tiers (Tier 3 auto-skipped if pcp.pmi unavailable)
pytest -v

# Run pre-commit quality gate locally
./pre-commit.sh
```
