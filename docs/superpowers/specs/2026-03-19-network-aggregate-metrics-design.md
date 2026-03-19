# Network Aggregate & Error Metrics Design

**Date:** 2026-03-19
**Status:** Approved

## Problem

pmlogsynth generates per-interface network metrics (`network.interface.*`) but no
aggregate `network.all.*` counterparts. Real PCP archives from Linux hosts include
both levels. Additionally, `network.interface.{in,out}.errors` — part of the "big 3"
of network interface monitoring (bytes, packets, errors) — are missing entirely.

Separately, the existing 4 per-interface PMIDs don't match the real Linux PMDA
assignments. Since pmlogsynth aims to mimic real Linux host archives, these should
be corrected.

## Scope

- Add 8 new metrics to `NetworkMetricModel`
- Fix 4 existing per-interface PMIDs to match Linux PMDA
- Add `error_rate` stressor field for error injection

## Metric Table

### Existing Per-Interface (PMID fix only)

| Metric | Old PMID | Corrected PMID |
|--------|----------|---------------|
| `network.interface.in.bytes` | (60, 3, 3) | (60, 3, 0) |
| `network.interface.out.bytes` | (60, 3, 11) | (60, 3, 8) |
| `network.interface.in.packets` | (60, 3, 0) | (60, 3, 1) |
| `network.interface.out.packets` | (60, 3, 8) | (60, 3, 9) |

### New Per-Interface

| Metric | PMID | Type | Sem | Units | InDom |
|--------|------|------|-----|-------|-------|
| `network.interface.in.errors` | (60, 3, 2) | U64 | counter | count | (60, 2) |
| `network.interface.out.errors` | (60, 3, 10) | U64 | counter | count | (60, 2) |

### New Aggregates (scalar, no indom)

| Metric | PMID | Type | Sem | Units |
|--------|------|------|-----|-------|
| `network.all.in.bytes` | (60, 90, 0) | U64 | counter | bytes |
| `network.all.out.bytes` | (60, 90, 4) | U64 | counter | bytes |
| `network.all.in.packets` | (60, 90, 1) | U64 | counter | count |
| `network.all.out.packets` | (60, 90, 5) | U64 | counter | count |
| `network.all.in.errors` | (60, 90, 2) | U64 | counter | count |
| `network.all.out.errors` | (60, 90, 6) | U64 | counter | count |

PMID source: `https://github.com/performancecopilot/pcp` →
`src/pmdas/linux/linux.h` (CLUSTER_NET_DEV=3, CLUSTER_NET_ALL=90) and
`src/pmdas/linux/pmda.c` metric table.

## Stressor Change

Add `error_rate: Optional[float]` to `NetworkStressor`:

- Fraction of packets that are errors (e.g. `0.001` = 0.1%)
- `None` at parse time → `0.0` at compute time (stressor-defaults-at-compute-time invariant)

## Compute Flow

1. Compute total `in_bytes`, `out_bytes` from `rx_mbps`/`tx_mbps` + noise (existing)
2. Compute total `in_packets`, `out_packets` from bytes / mean_packet_bytes (existing)
3. Compute total `in_errors = in_packets * error_rate`, `out_errors = out_packets * error_rate` (new)
4. Accumulate 6 `network.all.*` counters as scalar values (new)
5. Split all 6 values evenly across interfaces, accumulate per-interface (existing pattern for bytes/packets, new for errors)

Pattern matches disk domain: compute totals first, then subdivide to per-device.
Guarantees `sum(per-interface) == all.*` exactly.

## Files Changed

| File | Change |
|------|--------|
| `pmlogsynth/profile.py` | Add `error_rate: Optional[float]` to `NetworkStressor` |
| `pmlogsynth/domains/network.py` | Fix 4 PMIDs, add 8 descriptors, update `compute()` |
| `pmlogsynth/cli.py` | Add 8 metric names to `_ALL_METRIC_NAMES` |
| `docs/profile-format.md` | Document `error_rate` field |
| `man/pmlogsynth.1` | Update network metrics list |
| `README.md` | Update metric count |
| Tests | Full TDD |

## What This Does NOT Change

- Disk domain (already has its aggregates)
- `writer.py` (stays dumb, no domain logic)
- No new model classes or abstractions

## Decision Log

- **Aggregate computation**: totals first, split to per-device (matches disk pattern)
- **Error rate default**: 0.0 (most networks are clean; noisy links are the exception)
- **PMID correction**: fix existing per-interface PMIDs to match real Linux PMDA
  (breaking change for existing archives, but correctness wins)
- **Cluster 90**: real Linux `CLUSTER_NET_ALL`, not a made-up number
