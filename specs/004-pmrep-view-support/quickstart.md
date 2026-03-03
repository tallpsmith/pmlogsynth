# Quickstart: Validating pmrep Views

**Feature**: 004-pmrep-view-support
**Target**: Developer or CI engineer verifying the feature end-to-end

---

## Prerequisites

```bash
# Linux only (macOS has no pcp.pmi for archive generation)
sudo apt-get install pcp python3-pcp

# Install pmlogsynth
cd /path/to/pmlogsynth
pip install -e ".[dev]"
```

---

## Step 1: Generate the complete-example archive

```bash
pmlogsynth -o ./generated-archives/complete-example docs/complete-example.yml
```

Expected output: three files created:
```
generated-archives/complete-example.0
generated-archives/complete-example.index
generated-archives/complete-example.meta
```

Verify archive integrity:
```bash
pmlogcheck ./generated-archives/complete-example
# Expected: exits 0, no warnings
```

---

## Step 2: Validate pmstat view (SC-001)

```bash
pmrep -c pmstat -a ./generated-archives/complete-example
```

**Expected**: all columns populated with numeric values — no dashes, no `unknown metric` warnings.

Key columns to check: `load avg`, `swpd`, `free`, `buff`, `cache`, `pi/k`, `po/k`, `bi/k`, `bo/k`, `in/k`, `cs/k`, `us`, `sy`, `id`

---

## Step 3: Validate vmstat view (SC-002)

```bash
pmrep -c vmstat -a ./generated-archives/complete-example
```

**Expected**: all columns populated including `r`, `b`, `swpd`, `free`, `buff`, `cache`, `si`, `so`, `bi`, `bo`, `in`, `cs`, `us`, `sy`, `id`, `wa`, `st`, `gu`.

```bash
pmrep -c vmstat-a -a ./generated-archives/complete-example
# Check: inact and active columns populated
```

```bash
pmrep -c vmstat-d -a ./generated-archives/complete-example
# Check: per-device rows with rtotal, rmerged, rsectors, rms, wtotal, wmerged, wsectors, wms, cur, sec columns
```

---

## Step 4: Verify phase fluctuations (SC-003)

The archive spans 1200 seconds at 60s intervals = 20 samples.

- Samples 1-5: baseline (utilization ≈ 15%)
- Samples 6-10: ramp (utilization linearly increasing 15% → 80%)
- Samples 11-20: peak (utilization ≈ 90%)

Inspect with pmval:
```bash
# CPU user time should be much higher in peak vs baseline
pmval -a ./generated-archives/complete-example kernel.all.cpu.user

# Running processes should scale with utilization
pmval -a ./generated-archives/complete-example kernel.all.running

# Swap should be non-zero during peak (memory used_ratio = 0.80 > 0.70 threshold)
pmval -a ./generated-archives/complete-example swap.used
```

---

## Step 5: Run the full quality gate

```bash
./pre-commit.sh
```

**Expected**: all green — lint, mypy, Tier 1 unit tests, Tier 2 integration tests, Tier 3 E2E (if PCP available).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `unknown metric` for `hinv.ncpu` | Discrete metric not written at archive open | Check writer `_write_discrete_sample` runs before sample loop |
| All CPU% columns show 0 or dashes | `hinv.ncpu` = 0 or absent | Verify `hardware.cpus` is set in the hardware profile |
| Swap columns empty | `used_ratio` not exceeding 0.70 | Update `complete-example.yml` peak phase to `used_ratio: 0.80` |
| `disk.dev.*` columns empty | No disk stressor in baseline/ramp phases | Add `disk` stressor to all phases |
| `mem.util.slab` absent | Wrong PMID | Verify `pminfo -d mem.util.slab` matches (58, 0, 12) |
