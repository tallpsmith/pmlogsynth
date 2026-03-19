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

### Existing Per-Interface (PMID correction)

The current per-interface PMIDs were assigned arbitrarily. The corrected values match
the real Linux PMDA (`src/pmdas/linux/pmda.c`, `CLUSTER_NET_DEV=3`), where the item
numbers follow `/proc/net/dev` field ordering:

- Items 0-7: inbound (bytes=0, packets=1, errors=2, drops=3, ...)
- Items 8-15: outbound (bytes=8, packets=9, errors=10, drops=11, ...)

**This is a semantic correctness fix, not just renumbering.** The old code had item 0
mapped to `in.packets` and item 3 to `in.bytes` — the reverse of what the Linux PMDA
expects. Archives generated before this change will have different PMID-to-name mappings.
This is a **breaking change** for any tooling that reads old pmlogsynth archives by
raw PMID rather than metric name.

**Implementation order:** Apply all PMID corrections first, then add new descriptors
that slot into the corrected numbering scheme.

| Metric | Old PMID | Corrected PMID | Linux PMDA item meaning |
|--------|----------|---------------|------------------------|
| `network.interface.in.bytes` | (60, 3, 3) | (60, 3, 0) | ifInOctets |
| `network.interface.in.packets` | (60, 3, 0) | (60, 3, 1) | ifInUcastPkts |
| `network.interface.out.bytes` | (60, 3, 11) | (60, 3, 8) | ifOutOctets |
| `network.interface.out.packets` | (60, 3, 8) | (60, 3, 9) | ifOutUcastPkts |

### New Per-Interface

| Metric | PMID | Type | Sem | Units | InDom |
|--------|------|------|-----|-------|-------|
| `network.interface.in.errors` | (60, 3, 2) | U64 | counter | count | (60, 2) |
| `network.interface.out.errors` | (60, 3, 10) | U64 | counter | count | (60, 2) |

Same indom `(60, 2)` as existing per-interface metrics. Items 2 and 10 match the
Linux PMDA's `ifInErrors` and `ifOutErrors` respectively.

### New Aggregates (scalar, no indom)

| Metric | PMID | Type | Sem | Units |
|--------|------|------|-----|-------|
| `network.all.in.bytes` | (60, 90, 0) | U64 | counter | bytes |
| `network.all.in.packets` | (60, 90, 1) | U64 | counter | count |
| `network.all.in.errors` | (60, 90, 2) | U64 | counter | count |
| `network.all.out.bytes` | (60, 90, 4) | U64 | counter | bytes |
| `network.all.out.packets` | (60, 90, 5) | U64 | counter | count |
| `network.all.out.errors` | (60, 90, 6) | U64 | counter | count |

**Item gap note:** Items 3 and 7 are intentionally skipped. In the real Linux PMDA,
item 3 = `network.all.in.drops` and item 7 = `network.all.out.drops`. These are
omitted from this iteration — pmlogsynth does not generate drop counters. The gaps
preserve alignment with real PMDA numbering for future additions.

**Units note:** `network.all.*.bytes` uses `UNITS_BYTES`, not `UNITS_KBYTE`. This
differs from `disk.all.*_bytes` which uses `UNITS_KBYTE`. Both match their respective
real Linux PMDA conventions — the linux PMDA reports disk throughput in kilobytes but
network throughput in bytes.

PMID source: `https://github.com/performancecopilot/pcp` →
`src/pmdas/linux/linux.h` (CLUSTER_NET_DEV=3, CLUSTER_NET_ALL=90) and
`src/pmdas/linux/pmda.c` metric table.

## Stressor Change

Add `error_rate: Optional[float]` to `NetworkStressor`:

- Fraction of packets that are errors (e.g. `0.001` = 0.1%)
- `None` at parse time → `0.0` at compute time (stressor-defaults-at-compute-time invariant)
- **Valid range:** `0.0 <= error_rate <= 1.0` (same validation pattern as `noise`)
- `_parse_network_stressor()` must read `error_rate` from YAML and validate range

## Compute Flow

1. Compute total `in_bytes`, `out_bytes` from `rx_mbps`/`tx_mbps` + noise (existing)
2. Compute total `in_packets`, `out_packets` from bytes / mean_packet_bytes (existing)
3. Compute total `in_errors = in_packets * error_rate`, `out_errors = out_packets * error_rate` (new)
4. Accumulate 6 `network.all.*` counters as scalar values (new)
5. Split all 6 values evenly across interfaces, accumulate per-interface (existing pattern for bytes/packets, new for errors)

Note: error counts are floats that accumulate across samples before becoming visible
as integer counter increments. At low traffic rates with low error_rate, sub-integer
deltas are expected — the accumulator handles this correctly.

Pattern matches disk domain: compute totals first, then subdivide to per-device.
Guarantees `sum(per-interface) == all.*` exactly.

## Files Changed

| File | Change |
|------|--------|
| `pmlogsynth/profile.py` | Add `error_rate: Optional[float]` to `NetworkStressor`; update `_parse_network_stressor()` with range validation |
| `pmlogsynth/domains/network.py` | Fix 4 PMIDs, add 8 descriptors, update `compute()` for aggregates + errors |
| `pmlogsynth/cli.py` | Add 8 metric names to `_ALL_METRIC_NAMES` (63 → 71) |
| `docs/profile-format.md` | Document `error_rate` field |
| `man/pmlogsynth.1` | Update network metrics list |
| `README.md` | Update metric count (63 → 71) |
| Tests | Full TDD (see test plan below) |

## Test Plan

Tests written before implementation per mandatory TDD workflow.

**Descriptor tests:**
- Verify total descriptor count = 12 (was 4; update existing `test_metric_descriptors_count`)
- Verify corrected PMIDs for all 4 existing per-interface metrics
- Verify PMIDs for 2 new per-interface error metrics
- Verify PMIDs for 6 new aggregate metrics
- Verify aggregate descriptors have `indom=None`
- Verify per-interface error descriptors have `indom=(60, 2)`

**Compute tests — aggregates:**
- `network.all.in.bytes` accumulates correctly across samples
- `network.all.out.bytes` accumulates correctly across samples
- `network.all.in.packets` / `network.all.out.packets` accumulate
- `sum(network.interface.in.bytes per-iface) == network.all.in.bytes` (exact match)
- `sum(network.interface.out.bytes per-iface) == network.all.out.bytes` (exact match)
- Same sum invariant for packets and errors

**Compute tests — errors:**
- `error_rate=None` → zero errors in both aggregate and per-interface
- `error_rate=0.0` → zero errors
- `error_rate=0.001` at known packet count → exact expected error accumulation
- Errors split evenly across interfaces

**Compute tests — edge cases:**
- Zero interfaces → aggregates still computed, no per-interface values
- Zero traffic (`rx_mbps=0, tx_mbps=0`) → all counters zero

**Stressor parsing tests:**
- `error_rate` parsed from YAML correctly
- `error_rate` missing → `None`
- `error_rate` out of range (< 0 or > 1) → `ValidationError`

## What This Does NOT Change

- Disk domain (already has its aggregates)
- `writer.py` (stays dumb, no domain logic)
- No new model classes or abstractions

## Decision Log

- **Aggregate computation**: totals first, split to per-device (matches disk pattern)
- **Error rate default**: 0.0 (most networks are clean; noisy links are the exception)
- **Error rate validation**: 0.0–1.0, same pattern as noise field
- **PMID correction**: fix existing per-interface PMIDs to match real Linux PMDA
  (breaking change for existing archives, but correctness wins)
- **Cluster 90**: real Linux `CLUSTER_NET_ALL`, not a made-up number
- **Item gaps**: 3/7 in cluster 90 intentionally skipped (drops metrics, not implemented)
- **UNITS_BYTES for network**: matches Linux PMDA convention (differs from disk's UNITS_KBYTE)
