# Metric Inventory Contract

**Feature**: 004-pmrep-view-support
**Contract type**: Archive metric completeness — what pmrep views require vs. what pmlogsynth emits

---

## pmstat view (`/etc/pcp/pmrep/pmstat.conf [pmstat]`)

All metrics directly referenced in the config section, plus metrics used in derived formula columns.

| Metric | Status | Domain | Notes |
|--------|--------|--------|-------|
| `kernel.all.load` (1 minute) | ✅ existing | system.py | load indom, instance "1 minute" |
| `swap.used` | 🆕 add | memory.py | instant, UNITS_KBYTE |
| `mem.util.free` | ✅ existing | memory.py | |
| `mem.util.bufmem` | ✅ existing | memory.py | |
| `mem.util.cached` | ✅ existing | memory.py | part of allcache formula |
| `mem.util.slab` | 🆕 add | memory.py | part of allcache formula |
| `swap.pagesin` | 🆕 add | memory.py | counter |
| `swap.pagesout` | 🆕 add | memory.py | counter |
| `mem.vmstat.pgpgin` | 🆕 add | memory.py | counter |
| `mem.vmstat.pgpgout` | 🆕 add | memory.py | counter |
| `kernel.all.intr` | 🆕 add | system.py | counter |
| `kernel.all.pswitch` | 🆕 add | system.py | counter |
| `kernel.all.cpu.user` | ✅ existing | cpu.py | reduced by sub-metric carve |
| `kernel.all.cpu.nice` | 🆕 add | cpu.py | carved from user |
| `kernel.all.cpu.sys` | ✅ existing | cpu.py | reduced by intr carve |
| `kernel.all.cpu.intr` | 🆕 add | cpu.py | carved from sys |
| `kernel.all.cpu.steal` | ✅ existing | cpu.py | |
| `kernel.all.cpu.idle` | ✅ existing | cpu.py | |
| `kernel.all.cpu.wait.total` | ✅ existing | cpu.py | |
| `hinv.ncpu` | 🆕 add | cpu.py | discrete; divisor in all CPU% formulae |

**Derived formula metrics** (pmrep computes from above; not emitted by pmlogsynth):
- `allcache` = `mem.util.cached + mem.util.slab`
- `usr` = `100 * (kernel.all.cpu.user + kernel.all.cpu.nice) / hinv.ncpu`
- `sys` = `100 * (kernel.all.cpu.sys + kernel.all.cpu.intr + kernel.all.cpu.steal) / hinv.ncpu`
- `idle` = `100 * (kernel.all.cpu.idle + kernel.all.cpu.wait.total) / hinv.ncpu`

---

## vmstat view (`/etc/pcp/pmrep/vmstat.conf [vmstat]`)

| Metric | Status | Notes |
|--------|--------|-------|
| `kernel.all.running` | 🆕 add | instant, count |
| `kernel.all.blocked` | 🆕 add | instant, count |
| `swap.used` | 🆕 add | (same as pmstat) |
| `mem.util.free` | ✅ existing | |
| `mem.util.bufmem` | ✅ existing | |
| `mem.util.cached` + `mem.util.slab` | 🆕 slab only | allcache formula |
| `swap.pagesin` | 🆕 add | |
| `swap.pagesout` | 🆕 add | |
| `mem.vmstat.pgpgin` | 🆕 add | |
| `mem.vmstat.pgpgout` | 🆕 add | |
| `kernel.all.intr` | 🆕 add | |
| `kernel.all.pswitch` | 🆕 add | |
| `kernel.all.cpu.vuser` | 🆕 add | vmstat usr formula uses vuser+vnice |
| `kernel.all.cpu.vnice` | 🆕 add | |
| `kernel.all.cpu.sys` | ✅ existing | |
| `kernel.all.cpu.intr` | 🆕 add | vmstat sys formula: sys+intr |
| `kernel.all.cpu.idle` | ✅ existing | |
| `kernel.all.cpu.wait.total` | ✅ existing | |
| `kernel.all.cpu.steal` | ✅ existing | |
| `kernel.all.cpu.guest` | 🆕 add | vmstat guest formula: guest+guest_nice |
| `kernel.all.cpu.guest_nice` | 🆕 add | |
| `hinv.ncpu` | 🆕 add | divisor in all CPU% formulae |

---

## vmstat-a view (`/etc/pcp/pmrep/vmstat.conf [vmstat-a]`)

Adds two metrics beyond `[vmstat]`:

| Metric | Status | Notes |
|--------|--------|-------|
| `mem.util.inactive` | 🆕 add | instant, UNITS_KBYTE |
| `mem.util.active` | 🆕 add | instant, UNITS_KBYTE |

---

## vmstat-d view (`/etc/pcp/pmrep/vmstat.conf [vmstat-d]`)

Per-device disk metrics — all per-device with indom (60, 1):

| Metric | Status | Notes |
|--------|--------|-------|
| `disk.dev.read` | 🆕 add | counter, count |
| `disk.dev.read_merge` | 🆕 add | counter, count |
| `disk.dev.blkread` | 🆕 add | counter, count (512-byte sectors) |
| `disk.dev.read_rawactive` | 🆕 add | counter, UNITS_MSEC |
| `disk.dev.write` | 🆕 add | counter, count |
| `disk.dev.write_merge` | 🆕 add | counter, count |
| `disk.dev.blkwrite` | 🆕 add | counter, count (512-byte sectors) |
| `disk.dev.write_rawactive` | 🆕 add | counter, UNITS_MSEC |
| `disk.dev.avg_qlen` | 🆕 add | instant, DOUBLE |
| `disk.dev.avactive` | 🆕 add | counter, UNITS_MSEC |

`disk.dev.secactive` is a **derived** metric (`instant(disk.dev.avactive)`) — not emitted by pmlogsynth.

---

## Summary Counts

| Category | Existing | New | Total |
|----------|----------|-----|-------|
| cpu.py metrics | 8 | 7 (6 sub + hinv.ncpu) | 15 |
| system.py metrics | 1 | 4 | 5 |
| memory.py metrics | 5 | 8 | 13 |
| disk.py metrics | 6 | 10 | 16 |
| **Total** | **20** | **29** | **49** |
