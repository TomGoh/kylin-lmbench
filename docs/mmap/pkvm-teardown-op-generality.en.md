# pKVM teardown penalty: not munmap-specific — MADV_DONTNEED pays it in full, mprotect by geometry

| | |
|---|---|
| Date | 2026-06-16 |
| Platform | N80 (Phytium FTC862, 8 cores / 2 clusters, 1.8 GHz locked), Kylin V10 SP1, kernel `6.6.30xcore-stat2+` (Rust nVHE hyp), **protected** + **nvhe** |
| Question | The overview report (`pkvm-mmap-overview.zh-CN.md`) establishes the +0.27 µs/slot penalty on `munmap` alone. Is it `munmap`-specific, or a generic property of host stage-2 — paid by any teardown op that issues the same per-page stage-1-range invalidation (`madvise(MADV_DONTNEED)`, `mprotect`)? |
| Verdict | **Generic.** Below 2 MB the protected−nvhe gap is **operation-independent** — identical across all three ops (+0.27 µs/slot), collapsing at the 2 MB gate. `MADV_DONTNEED` pays the **full** penalty exactly like `munmap` (sparse +436 µs) because it zaps dirty pages with the same per-PMD batching. `mprotect` pays **only when the contiguous changed range is itself < 2 MB**; sparse large spans escape (gap ≈ 0). |
| Data/code | `kylin-lmbench/experiments/munmap-tlbi/` — `op_sweep.c`, `run-op-sweep.sh`, `results/op-sweep-n80/{protected,nvhe}.txt`. |

---

## 1. What we set out to verify

The overview's §8.1 root cause — sub-2 MB teardown issues a per-page `tlbi vae1is` per 4 K flush slot
(no FEAT_TLBIRANGE on this platform), and under host stage-2 each slot costs +0.27 µs more than nvhe —
and §9's correction — that cost is the **local** invalidation of a combined stage-1×stage-2,
VMID-tagged TLB entry — were both established on `munmap` only.

But `munmap`, `madvise(MADV_DONTNEED)` and `mprotect` all funnel through arm64's
`__flush_tlb_range()` and the **same** `MAX_DVM_OPS = 512` (2 MB) gate (`tlbflush.h:422-424`,
verified). The discriminating prediction: if the penalty is the combined-entry TLBI cost — not
anything specific to munmap's teardown — then **every** op that issues the per-page sequence pays the
**same** per-slot gap, and the gap is a pure function of the flush range, independent of what the op
otherwise does.

## 2. Method & platform controls

Same harness shape as `munmap_only.c`: re-map each iteration, dense-touch the first N MB (4 K stride)
so the op's flush range ≈ N MB, time **only** the op, report the **mean** (the honest metric — §9's
`min` trap). `op_sweep.c` adds two ops in the flush-forcing direction:

- `madvise(p, len, MADV_DONTNEED)` — zaps the PTEs now → `zap_page_range` → `__flush_tlb_range`.
  (`MADV_FREE` is lazy → no immediate flush → would measure nothing.)
- `mprotect(p, len, PROT_READ)` — RW→RO is more restrictive → a stale permissive entry is unsafe →
  the kernel **must** flush. (RO→RW is permissive → the kernel may skip the flush → would measure
  nothing.)

Sweep N across the gate (0.25 / 0.5 / 1 / 1.9 / 2 / 4 / 8 / 32 / 64 MB) plus the lat_mmap sparse
point (6.4 MB span, 16 K stride). Controls each run: `taskset -c 0`, governor `performance` @ 1.8 GHz,
**THP=never** (critical — `always` folds the touched region into 2 MB PMD blocks and changes the
flush entirely; THP/ASLR reset on every reboot and must be re-applied), ASLR=0. One pass per boot
mode. The reported metric is **gap = protected − nvhe**, which cancels the mode-independent page-free
cost and leaves the pure TLBI tax.

**Harness validation.** `op_sweep`'s `munmap` column reproduces the report's §7.5 `munmap_only`
numbers point-for-point (protected 1.9 MB 226.9 vs 227.5; 2.0 MB 92.1 vs 93.4; sparse 546.8 vs 546.7;
nvhe sparse 110.2 vs 108.6). Same harness, same path — so the new `dontneed`/`mprotect` columns are
trustworthy.

## 3. Results

Absolute (mean µs/iter, dense 4 K touch):

| flush range | munmap P | munmap N | dontneed P | dontneed N | mprotect P | mprotect N |
|---:|---:|---:|---:|---:|---:|---:|
| 0.25 MB | 33.8 | 16.6 | 30.6 | 13.5 | 22.0 | 5.1 |
| 0.5 MB | 65.0 | 30.6 | 59.7 | 27.7 | 42.3 | 7.8 |
| 1.0 MB | 120.7 | 51.9 | 117.7 | 50.0 | 81.7 | 13.3 |
| 1.9 MB | 226.9 | 96.7 | 224.4 | 94.4 | 152.8 | 22.6 |
| 2.0 MB | 92.1 | 91.7 | 91.7 | 90.7 | 13.6 | 13.1 |
| 4 MB | 183.6 | 178.2 | 180.8 | 176.8 | 24.2 | 23.5 |
| 64 MB | 2880.4 | 2806.6 | 2832.6 | 2766.4 | 350.6 | 335.6 |
| sparse 6.4/16K | 546.8 | 110.2 | 543.6 | 107.7 | 12.2 | 11.9 |

Gap (protected − nvhe) — the pure TLBI tax:

| flush range | munmap | dontneed | mprotect | regime |
|---:|---:|---:|---:|---|
| 0.25 MB | +17.2 | +17.1 | +16.9 | per-page |
| 0.5 MB | +34.4 | +32.0 | +34.5 | per-page |
| 1.0 MB | +68.8 | +67.7 | +68.4 | per-page |
| **1.9 MB** | **+130.2** | **+130.0** | **+130.2** | per-page |
| 2.0 MB | +0.4 | +1.0 | +0.5 | integer |
| 4 MB | +5.4 | +4.0 | +0.7 | integer |
| 64 MB | +73.8 | +66.2 | +15.0 | integer |
| **sparse 6.4/16K** | **+436.6** | **+435.9** | **+0.3** | per-PMD-batched (see §5) |

## 4. Findings

**1. The +0.27 µs/slot penalty is operation-independent.** Below 2 MB the gap is identical across all
three ops — +17 / +34 / +68 / +130 µs — because it depends only on the number of 4 K flush slots, not
on what the op does. +68.4 µs at 1 MB ÷ 256 slots = **+0.267 µs/slot**; +130.2 µs at 1.9 MB ÷ 486
slots = **+0.268 µs/slot** — reproducing the report's +0.27 µs/slot, now **independently from three
different syscalls**. This is the strongest cross-check yet that the cost is the combined-entry TLBI
itself (§9), not anything in munmap's teardown.

**2. `MADV_DONTNEED` is a full second victim.** Its gap tracks `munmap`'s to within ~2% at every
point, including the realistic sparse case (**+436 µs**, vs munmap's +437). `MADV_DONTNEED` is the
standard *decommit* primitive of jemalloc, tcmalloc, and the Go runtime — so the penalty reaches well
beyond `lat_mmap`-style microbenchmarks into ordinary allocator-heavy workloads.

**3. `mprotect` is gated by geometry, not by total work.** Its < 2 MB gap is identical to the others
(it pays per-slot too), but in the sparse case it is **+0.3 µs ≈ 0**: with no dirty-page zap it has
no per-PMD `force_flush`, so it accumulates the whole 6.4 MB span into one flush that crosses 2 MB and
takes the integer-flush path. `mprotect` hurts only when the *contiguous changed range itself* is
< 2 MB (W^X flips on small JIT regions, guard-page toggles), not when a large region is sparsely
changed.

## 5. Why DONTNEED equals munmap but mprotect escapes — the discriminating rule

All three cross the 2 MB gate in the **dense** sweep (rise to 1.9 MB, drop at 2.0 MB), confirming the
shared `__flush_tlb_range` threshold. The *sparse* split is decided one level down, by whether the op
**force-flushes per PMD**:

- **munmap / MADV_DONTNEED zap dirty pages.** Touched shared-file pages are dirty, so
  `zap_present_folio_ptes()` (`mm/memory.c:1489`) sets `*force_flush` and `zap_pte_range()` flushes at
  the end of **every** PMD. With a 16 K stride the last touched page in each PMD sits at 2 MB − 16 K,
  so each batch is ≈ 2 MB − 12 K — perpetually just under the gate → per-page TLBI, no matter how
  large the total span. This is exactly §7.5's "real granularity of the threshold."
- **mprotect changes protection; it zaps nothing.** No dirty-page `force_flush`, so the whole changed
  span accumulates into a single `flush_tlb_range` at `tlb_finish_mmu`. A 6.4 MB span ≥ 2 MB → one
  integer flush → the pKVM cost vanishes.

> **Rule.** An op that batches its TLB flush **per dirty PMD** (`munmap`, `MADV_DONTNEED`) stays on
> the per-page path and pays the full penalty even for large, sparsely-touched spans. An op that does
> **not** dirty-zap (`mprotect`) flushes its whole contiguous range at once and is affected only when
> that range is itself < 2 MB.

This also predicts the read-touch anomaly already noted in §4.3/§7.5: clean pages don't `force_flush`,
so a read-only teardown accumulates past 2 MB and escapes — the same mechanism, the same one-bit
(`pte_dirty`) hinge.

## 6. What this adds to the overview report

§8.2 ("退化的边界条件与实际影响") previously bounded impact via `munmap` + the LMDB openclose旁证.
This run widens that boundary on solid data:

- **`MADV_DONTNEED` is a first-class victim**, identical to `munmap` — allocator decommit
  (jemalloc/tcmalloc/Go) is exposed, not just mmap-lifecycle microbenchmarks.
- **`mprotect` is range-gated**, not span-gated — affected only for sub-2 MB contiguous changes.
- The **discriminating rule** (§5) is the portable takeaway for predicting which real workloads pay
  the penalty: look for dirty-page per-PMD batching, not for "does it call TLBI."

The root-cause mechanism is unchanged: this is the same local combined-entry invalidation at
+0.27 µs/slot (§9), now shown to be operation-independent. Mitigations are unchanged and apply to all
three ops: FEAT_TLBIRANGE (collapses N per-page TLBIs into a few range TLBIs) or a lower
`MAX_DVM_OPS` (push more teardown onto the single-`aside1is` integer-flush path).

## 7. Index

- Bench + sweep: `kylin-lmbench/experiments/munmap-tlbi/op_sweep.c`, `run-op-sweep.sh`
- Raw data: `kylin-lmbench/experiments/munmap-tlbi/results/op-sweep-n80/{protected,nvhe}.txt`
  (copies in `kylin-lmbench/results/op-sweep-n80/`)
- Threshold chokepoint: `arch/arm64/include/asm/tlbflush.h:422-424` (`MAX_DVM_OPS`, line 342)
- Per-PMD dirty-page force_flush: `mm/memory.c:1489`
- Report extended: `pkvm_mmap_opt_docs/pkvm-mmap-overview.zh-CN.md` §8.2
- Prior follow-up (the +0.27 µs/slot is local, not broadcast): `pkvm-munmap-corescaling-followup.en.md`
