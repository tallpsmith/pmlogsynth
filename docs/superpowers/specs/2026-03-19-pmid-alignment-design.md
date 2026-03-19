# Full PMID Alignment With Linux PMDA

**Date:** 2026-03-19
**Status:** Approved

## Problem

pmlogsynth aims to generate archives that mimic real Linux PCP hosts, but most
metric PMIDs don't match the real Linux PMDA assignments. PR #11 fixed network
PMIDs; this completes the job for all remaining domains.

## Scope

Fix 47 PMIDs across 5 domain modules + rename `disk.dev.avg_qlen` → `disk.dev.aveq`
to match the real Linux metric name. No functional changes — only PMID tuples and
one metric name.

## Already Correct (no changes)

- `kernel.all.load` — (60, 2, 0) matches CLUSTER_LOADAVG=2
- `kernel.all.intr` — (60, 0, 12) matches CLUSTER_STAT item 12
- `kernel.all.running` — (60, 0, 15) matches CLUSTER_STAT item 15
- `kernel.all.blocked` — (60, 0, 16) matches CLUSTER_STAT item 16
- `hinv.ncpu` — (60, 0, 32) matches CLUSTER_STAT item 32
- `hinv.ndisk` — (60, 0, 33) matches CLUSTER_STAT item 33
- `kernel.all.cpu.user` — (60, 0, 20)
- `kernel.all.cpu.sys` — (60, 0, 22)
- `kernel.all.cpu.wait.total` — (60, 0, 35)
- `kernel.all.cpu.vuser` — (60, 0, 78)
- `kernel.all.cpu.vnice` — (60, 0, 82)
- `kernel.all.cpu.guest` — (60, 0, 60)
- `kernel.all.cpu.guest_nice` — (60, 0, 81)
- `kernel.all.cpu.intr` — (60, 0, 34)
- All 12 `network.*` metrics (fixed in PR #11)

## CPU Domain Corrections (cpu.py)

| Metric | Old PMID | Corrected PMID | Source |
|--------|----------|---------------|--------|
| `kernel.all.cpu.idle` | (60, 0, 21) | (60, 0, 23) | CLUSTER_STAT item 23 |
| `kernel.all.cpu.nice` | (60, 0, 27) | (60, 0, 21) | CLUSTER_STAT item 21 |
| `kernel.all.cpu.steal` | (60, 0, 58) | (60, 0, 55) | CLUSTER_STAT item 55 |
| `kernel.percpu.cpu.user` | (60, 10, 20) | (60, 0, 0) | CLUSTER_STAT item 0 |
| `kernel.percpu.cpu.sys` | (60, 10, 22) | (60, 0, 2) | CLUSTER_STAT item 2 |
| `kernel.percpu.cpu.idle` | (60, 10, 21) | (60, 0, 3) | CLUSTER_STAT item 3 |

Note: percpu metrics move from invented cluster 10 to real CLUSTER_STAT=0.
They share the same cluster as kernel.all.cpu.* — differentiated by indom
(percpu has cpu_indom, all has indom=None), which is how the real PMDA works.

## System Domain Corrections (system.py)

| Metric | Old PMID | Corrected PMID | Source |
|--------|----------|---------------|--------|
| `kernel.all.pswitch` | (60, 0, 7) | (60, 0, 13) | CLUSTER_STAT item 13 |

## Disk Domain Corrections (disk.py)

All 16 disk metrics move from invented clusters 4/5 to real CLUSTER_STAT=0.

**Aggregate (disk.all.*) — old cluster 4 → cluster 0:**

| Metric | Old PMID | Corrected PMID |
|--------|----------|---------------|
| `disk.all.read` | (60, 4, 0) | (60, 0, 24) |
| `disk.all.write` | (60, 4, 1) | (60, 0, 25) |
| `disk.all.read_bytes` | (60, 4, 5) | (60, 0, 41) |
| `disk.all.write_bytes` | (60, 4, 6) | (60, 0, 42) |

**Per-device (disk.dev.*) — old cluster 5 → cluster 0:**

| Metric | Old PMID | Corrected PMID |
|--------|----------|---------------|
| `disk.dev.read` | (60, 5, 0) | (60, 0, 4) |
| `disk.dev.write` | (60, 5, 1) | (60, 0, 5) |
| `disk.dev.read_merge` | (60, 5, 2) | (60, 0, 49) |
| `disk.dev.write_merge` | (60, 5, 3) | (60, 0, 50) |
| `disk.dev.read_bytes` | (60, 5, 5) | (60, 0, 38) |
| `disk.dev.write_bytes` | (60, 5, 6) | (60, 0, 39) |
| `disk.dev.blkread` | (60, 5, 7) | (60, 0, 6) |
| `disk.dev.blkwrite` | (60, 5, 8) | (60, 0, 7) |
| `disk.dev.read_rawactive` | (60, 5, 9) | (60, 0, 72) |
| `disk.dev.write_rawactive` | (60, 5, 10) | (60, 0, 73) |
| `disk.dev.avactive` | (60, 5, 12) | (60, 0, 46) |
| `disk.dev.avg_qlen` **→ `disk.dev.aveq`** | (60, 5, 11) | (60, 0, 47) |

**Metric rename:** `disk.dev.avg_qlen` → `disk.dev.aveq` to match the real Linux
metric name (`disk.dev.aveq` in the linux PMDA). Touches: disk.py, cli.py,
test_domain_disk.py, test_list_metrics.py, test_cli.py, man page.

## Memory Domain Corrections (memory.py)

All 13 memory metrics move from invented domain 58 to real domain 60.

**mem.util.* and mem.physmem — domain 58 cluster 0 → domain 60 CLUSTER_MEMINFO=1:**

| Metric | Old PMID | Corrected PMID |
|--------|----------|---------------|
| `mem.physmem` | (58, 0, 0) | (60, 1, 0) |
| `mem.util.used` | (58, 0, 6) | (60, 1, 1) |
| `mem.util.free` | (58, 0, 2) | (60, 1, 2) |
| `mem.util.bufmem` | (58, 0, 4) | (60, 1, 4) |
| `mem.util.cached` | (58, 0, 13) | (60, 1, 5) |
| `mem.util.active` | (58, 0, 15) | (60, 1, 14) |
| `mem.util.inactive` | (58, 0, 16) | (60, 1, 15) |
| `mem.util.slab` | (58, 0, 12) | (60, 1, 25) |

**swap.used — domain 58 cluster 1 → domain 60 CLUSTER_MEMINFO=1:**

| Metric | Old PMID | Corrected PMID |
|--------|----------|---------------|
| `swap.used` | (58, 1, 0) | (60, 1, 7) |

**swap.pagesin/out — domain 58 cluster 1 → domain 60 CLUSTER_STAT=0:**

| Metric | Old PMID | Corrected PMID |
|--------|----------|---------------|
| `swap.pagesin` | (58, 1, 1) | (60, 0, 8) |
| `swap.pagesout` | (58, 1, 2) | (60, 0, 9) |

**mem.vmstat.* — domain 58 cluster 2 → domain 60 CLUSTER_VMSTAT=28:**

| Metric | Old PMID | Corrected PMID | Note |
|--------|----------|---------------|------|
| `mem.vmstat.pgpgin` | (58, 2, 0) | (60, 28, 0) | Item from /proc/vmstat field ordering |
| `mem.vmstat.pgpgout` | (58, 2, 1) | (60, 28, 1) | Item from /proc/vmstat field ordering |

Note: vmstat items are dynamically assigned in real PCP from /proc/vmstat field
ordering. Items 0/1 are a reasonable convention — the exact values don't matter
for self-contained archives, and we cannot determine the real assignment from source.

## Metadata Domain Corrections (metadata.py)

| Metric | Old PMID | Corrected PMID | Source |
|--------|----------|---------------|--------|
| `kernel.uname.sysname` | (60, 9, 0) | (60, 12, 2) | CLUSTER_KERNEL_UNAME=12 |
| `kernel.uname.nodename` | (60, 9, 1) | (60, 12, 4) | CLUSTER_KERNEL_UNAME=12 |
| `kernel.uname.release` | (60, 9, 2) | (60, 12, 0) | CLUSTER_KERNEL_UNAME=12 |
| `kernel.uname.version` | (60, 9, 3) | (60, 12, 1) | CLUSTER_KERNEL_UNAME=12 |
| `kernel.uname.machine` | (60, 9, 4) | (60, 12, 3) | CLUSTER_KERNEL_UNAME=12 |
| `kernel.uname.distro` | (60, 9, 5) | (60, 12, 7) | CLUSTER_KERNEL_UNAME=12 |
| `hinv.physmem` | (60, 0, 36) | (60, 1, 9) | CLUSTER_MEMINFO=1 |
| `hinv.pagesize` | (60, 0, 37) | (60, 1, 11) | CLUSTER_MEMINFO=1 |
| `hinv.ninterface` | (60, 0, 38) | (60, 3, 27) | CLUSTER_NET_DEV=3 |

Note: `hinv.ndisk` (60, 0, 33) is already correct — no change needed.

## CLAUDE.md Update

The "PCP Metric PMIDs" section of CLAUDE.md must be updated to reflect that
pmlogsynth now aligns with real Linux PMDA assignments. The "existing code
deviates from real PMIDs — intentionally and safely" note should be replaced
with documentation of the alignment approach and the vmstat caveat.

## Files Changed

| File | Change |
|------|--------|
| `pmlogsynth/domains/cpu.py` | Fix 6 PMIDs |
| `pmlogsynth/domains/system.py` | Fix 1 PMID |
| `pmlogsynth/domains/disk.py` | Fix 16 PMIDs, rename avg_qlen→aveq |
| `pmlogsynth/domains/memory.py` | Fix 13 PMIDs (domain 58→60) |
| `pmlogsynth/domains/metadata.py` | Fix 9 PMIDs (uname cluster 9→12, hinv fixes) |
| `pmlogsynth/cli.py` | Rename disk.dev.avg_qlen→disk.dev.aveq |
| `tests/unit/test_domain_cpu.py` | Update PMID assertions |
| `tests/unit/test_domain_disk.py` | Update PMID assertions + rename |
| `tests/unit/test_domain_memory.py` | Update PMID assertions |
| `tests/unit/test_domain_metadata.py` | Update PMID assertions |
| `tests/unit/test_domain_system.py` | Update PMID assertions if present |
| `tests/unit/test_list_metrics.py` | Rename avg_qlen→aveq |
| `tests/unit/test_cli.py` | Rename if referenced |
| `man/pmlogsynth.1` | Rename avg_qlen→aveq |
| `CLAUDE.md` | Update PMID documentation |

## PMID Source

All corrected values from: `https://github.com/performancecopilot/pcp` →
`src/pmdas/linux/linux.h` (cluster constants) and `src/pmdas/linux/pmda.c`
(metric table PMDA_PMID entries).
