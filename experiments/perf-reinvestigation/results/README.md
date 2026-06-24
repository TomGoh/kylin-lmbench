# Perf-only re-investigation — results (Kaitian, protected vs nvhe)

| | |
|---|---|
| Date | 2026-06-24 |
| Board | Kaitian, Phytium FTC862, Kylin V10 SP1, kernel `6.6.30-pkvm-clean` |
| Tool | **only** the perf we built from `common/tools/perf` (`perf 6.6.30.gda966ce9a047`) |
| Modes | `protected/` (host stage-2 on) vs `nvhe/` (no host stage-2) — same kernel, GRUB-switched |
| Controls | `taskset -c 0`, governor performance @1.9 GHz, THP=never, ASLR=0, paranoid=-1, **mean of 300 iters** |
| Bench | `op_sweep`/`munmap_only` (flush range ≈ touched extent; sweep `touch_mb` across the 2 MB gate) |

**Result: the entire original root cause reproduces with perf only.** The pKVM `lat_mmap`
penalty is a per-slot surcharge on sub-2 MB teardown TLB invalidation, operation-independent,
gone at the 2 MB integer-flush threshold, costing **≈ +0.13 µs per 4 K flush slot on this board**,
spent entirely as **host-EL1 backend (memory) stall** — not in EL2, not in extra page-table walks.

---

## 1. The 2 MB cliff in the protected − nvhe gap (`op_sweep.txt`)

Mean µs/iter; **gap = protected − nvhe**. Dense 4 K touch (flush range = touch size) + the
lat_mmap-like sparse point.

### munmap
| flush range | slots | protected | nvhe | **gap** | µs/slot |
|---:|---:|---:|---:|---:|---:|
| 0.25 MB | 64 | 23.1 | 15.5 | **+7.6** | 0.119 |
| 0.5 MB | 128 | 43.5 | 25.8 | **+17.7** | 0.138 |
| 1.0 MB | 256 | 79.6 | 46.6 | **+33.0** | 0.129 |
| **1.9 MB** | 486 | 148.7 | 87.3 | **+61.4** | 0.126 |
| **2.0 MB** | integer | 88.2 | 86.6 | **+1.6** | — |
| 4 MB | integer | 174.6 | 168.4 | +6.2 | — |
| 8 MB | integer | 354.6 | 334.9 | +19.7 | — |
| sparse 6.4/16K | per-PMD | 294.8 | 89.2 | **+205.6** | — |

The gap rises linearly with flush slots below 2 MB and **collapses at exactly 2.0 MB**
(+61.4 → +1.6) — the kernel switching from a per-page `tlbi` per 4 K slot to a single
whole-ASID integer flush (`MAX_DVM_OPS=512` = 2 MB). This is the original root cause, seen
purely in timing.

### Operation-independence — the strongest cross-check (gap at each range)
| flush range | munmap | dontneed | mprotect |
|---:|---:|---:|---:|
| 0.25 MB | +7.6 | +7.8 | +7.7 |
| 1.0 MB | +33.0 | +31.1 | +31.9 |
| **1.9 MB** | **+61.4** | **+61.0** | **+61.0** |
| 2.0 MB | +1.6 | +1.2 | +0.2 |
| sparse 6.4/16K | +205.6 | +205.5 | **+0.1** |

Below 2 MB the gap is **identical across three different syscalls** (+61 µs at 1.9 MB for all
three) → the cost is the per-slot combined-entry TLBI itself, not anything specific to munmap.
`MADV_DONTNEED` is a full victim (tracks munmap to ~1%); **`mprotect` escapes the sparse case**
(+0.1 µs) because it does not dirty-zap, so it accumulates one ≥2 MB flush → integer path. This
reproduces the original op-generality rule exactly.

**Per-slot pKVM surcharge ≈ +0.13 µs/slot** (Kaitian). The original N80 work measured ≈ +0.27 µs/slot;
same FTC862 core and same mechanism, ~half the magnitude — a board-level difference, not a
mechanism difference.

## 2. EL2 attribution — `cycles:h = 0` (`el2_h.txt`)

300 iterations of sparse munmap, `perf stat -e cycles:h`:
- protected: `cycles:h = 0`, `instructions:h = 0` (all 339M cycles are `cycles:k`, host EL1)
- nvhe: `cycles:h = 0` as well

The teardown spends **zero EL2 time** in either mode → the penalty is host-side (EL1), not in the
hypervisor. This is the original Stage-3 gate result, now a one-line `perf stat` — and trustworthy
because Stage 0 proved the same counter reads 392M when EL2 *is* busy.

## 3. Cost layering — equal work, extra backend stall (`cost_layering.txt`)

Sparse munmap (6.4 MB / 16 K), 300 iters, protected vs nvhe:

| event | protected | nvhe | Δ (P − N) |
|---|---:|---:|---:|
| instructions | 463.7 M | 463.1 M | +0.6 M (≈0) |
| page-faults | 123,050 | 123,050 | **0** |
| **DTLB-walk** (`r0034`) | 122,556 | 123,506 | **≈0** |
| l2d_tlb_refill | 122,944 | 123,609 | ≈0 |
| **stall_backend** (`r0024`) | 206.2 M | 87.5 M | **+118.7 M** |
| **cycles** | 369.8 M | 250.3 M | **+119.5 M** |

Identical instructions, faults, **and page-table walks** — the entire +119.5 M cycle gap is
+118.7 M extra **backend (memory) stalls** (99.3 %). Walks being identical **refutes the
nested-walk hypothesis (a-2)**: protected does not do more walks. The surcharge is the per-slot
TLBI cost (a-1) surfacing as a backend stall while the slower combined-entry invalidation retires.

## 4. Closed loop

The three independent measurements agree numerically:
- wall-time gap (sparse munmap): ~203 µs/iter ≈ 386 k cycles @1.9 GHz
- perf cycle gap: 119.5 M / 300 = **398 k cycles/iter**
- per-slot from cycles (1 MB dense, +18.9 M cyc / 256 slots / 300 iters) = **246 cyc ≈ 0.13 µs/slot**,
  matching the timing-derived 0.13 µs/slot.

## 5. Mapping to the original five stages (all reproduced, perf-only)

| Original stage (needed) | Perf-only result here |
|---|---|
| 1 Symptom | protected−nvhe gap, grows with size, gone for steady ops |
| 2 Localize → munmap | `op_sweep` isolates the gap to the teardown op |
| 3 EL2 gate (custom hypercall) | `cycles:h = 0` — **stock perf** |
| 4 Cost layering | equal instructions/faults/**walks**, +118.7 M backend stall |
| 5 Mechanism a-1 vs a-2 | 2 MB cliff + gap ∝ slots + **walks identical** ⇒ a-1 (per-slot TLBI) |
| 6 Generality | dontneed full victim; mprotect geometry-gated; gap op-independent |

Host-stage-2 introspection (original `op=3`) was **not needed** — the nested-walk hypothesis is
refuted behaviorally by the identical `r0034` walk counts plus the per-slot/2 MB-cliff structure.

## 6. Core-scaling — the penalty is LOCAL, not cross-core broadcast (`corescaling/corescaling.txt`)

Sparse munmap pinned to cpu0, 1000 iters, protected, varying the online-core set (the rest
offlined via CPU hotplug; frequency re-locked after each change):

| online set | mean µs | min µs | cycles | **stall_backend** (`r0024`) | instructions |
|---|---:|---:|---:|---:|---:|
| n8 all | 294.2 | 290.5 | 1,187.6 M | **680.8 M** | 1,442.6 M |
| n2 intra {0,1} | 294.7 | 290.4 | 1,187.9 M | **680.0 M** | 1,442.3 M |
| n2 cross {0,4} | 295.3 | 290.6 | 1,188.8 M | **681.9 M** | 1,442.6 M |
| n1 solo {0} | 303.3 | 209.3 | 1,208.1 M | **676.4 M** | 1,451.2 M |

- **Mean, cycles, and `stall_backend` are flat across online-core count and cluster placement**
  (intra {0,1} ≈ cross {0,4}). A cross-core DVM broadcast / `dsb ish` completion wait would grow
  with participating cores; it does not. → the +118.7 M backend stall (§3) is the **local** cost
  of invalidating the combined, VMID-tagged TLB entry, **not** a broadcast wait. This reproduces
  the original follow-up's correction — with perf only, no IRQ-off kernel module.
- **The `min` trap reproduces exactly:** n1 solo `min`=209 µs sits far below its `mean`=303 µs
  (single-core variance), while n8's `min`≈`mean`. A min-based reading would manufacture a fake
  "+81 µs going 1→8 cores"; the **mean** shows flat. (Original lesson: never compare `min` across
  configs whose variance differs.)

## 7. `mmap_split` phase breakdown (protected) — the cost is the touched-page teardown (`protected/mmap_split.csv`)

`lat_mmap` decomposed into separately-timed phases (lat_mmap geometry: 64 MB, touch size/10 =
6.4 MB at 16 K stride, 300 iters), protected:

| phase | protected µs/iter |
|---|---:|
| `mmap_unmap` (VMA create+delete, no touch) | 3.54 |
| `write_touch_cold` (first-touch faults only) | 330.35 |
| `munmap_after_no_touch` (teardown, nothing mapped) | **1.66** |
| `munmap_after_write_touch` (teardown after touch) | **292.84** |
| `mmap_write_touch_unmap` (full path) | 625.01 |

- The full path (625) ≈ touch (330) + teardown (293) + setup (3) — additive.
- **Untouched munmap is ~free (1.66 µs); touched munmap is 293 µs.** The munmap cost is entirely
  the teardown of touched PTEs (clear + per-page TLBI), not the syscall/VMA machinery — exactly
  where §1's protected−nvhe gap lives. This is the original Stage-2 localization.

**nvhe leg not collected (operational caveat):** the GRUB one-shot (`grub-reboot`) switched to
nvhe on its first use this session, then refused to consume `next_entry` on three later attempts
(board booted protected with the one-shot still armed, even after `sync` and a settle delay) — a
board-level grubenv reliability quirk. The teardown localization does **not** depend on this leg:
op_sweep + cost-layering (§1, §3, §4) already isolate the gap to touched-page teardown **in both
modes**, and the within-protected breakdown above (untouched ~0 vs touched 293 µs) independently
confirms the cost is the touched-PTE teardown.

## Files
`protected/` and `nvhe/`: `op_sweep.txt`, `el2_h.txt`, `cost_layering.txt`, `kernel.txt`
(+ `protected/mmap_split.csv`); `corescaling/corescaling.txt`. Scripts:
`../setup-controls.sh`, `../run-suite.sh`, `../core-scaling.sh`, `../run-mmapsplit.sh`.
Open item: large dense ≥2 MB gaps grow with pages-freed (e.g. munmap 64 MB +532 µs mean) but are
inflated by single-core variance (min gap only +83 µs) — a noisier secondary effect outside the
lat_mmap-relevant small/sparse regime.
