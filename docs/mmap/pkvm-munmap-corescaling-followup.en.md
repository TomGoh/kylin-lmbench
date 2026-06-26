# pKVM munmap penalty: core-scaling follow-up — the cost is LOCAL, not cross-core broadcast

| | |
|---|---|
| Date | 2026-06-15 |
| Platform | N80 (Phytium FTC862, 8 cores / 1 socket / 2 clusters, 1.8 GHz), Kylin V10 SP1, kernel `6.6.30xcore-stat2+` (Rust nVHE hyp), **protected** + **nvhe** |
| Question | The overview report (`pkvm-mmap-overview.zh-CN.md` §8.1) attributes the +0.27 µs/slot pKVM munmap penalty to "逐页失效序列**与广播等待** (per-slot invalidation **+ broadcast wait**)". Is the penalty actually the **cross-core TLB-broadcast sync** latency? |
| Verdict | **No.** The penalty does **not** scale with cores and is **not** broadcast. It is the **local microarchitectural cost of invalidating a combined stage-1×stage-2, VMID-tagged TLB entry** (~289 ns/slot protected vs ~23 ns/slot nvhe ⇒ ≈ the report's +0.27 µs/slot). The report's "broadcast wait" attribution is **wrong**; the "per-slot invalidation" half is right. |
| Data/code | `kylin-lmbench/experiments/munmap-tlbi/` — `INVESTIGATION-LOG.md` (chronological), `results/corescaling-n80/` (CSVs), `tlbi_ab/` (TLBI-timing kernel module + user driver), `run-core-scaling.sh`. |

> **Note on rigor:** this investigation reached a *wrong* intermediate conclusion (a cross-core
> broadcast mechanism) by trusting `munmap`'s **minimum** time, then corrected it with the **mean**
> and `perf`. Both the wrong path and the correction are documented here in full, because the
> methodological trap (the `min`) is the most reusable lesson.

---

## 1. What we set out to verify

The overview report localized the pKVM munmap degradation to a single mechanism it labels **a-1**:
for sub-2 MB sparse teardown the kernel issues a per-page `TLBI` for each 4 K flush slot (no
FEAT_TLBIRANGE on this platform), and under host stage-2 each slot costs **+0.27 µs** more than in
nvhe. The report's §8.1 phrasing folds two ideas into that number — "per-slot invalidation
**sequence** + **broadcast wait**" — but §2.3/§7.7 explicitly decline to prove the broadcast part.

The user's sharpened hypothesis: the +0.27 µs/slot is specifically the **cross-core** sync — the
Inner-Shareable `tlbi vae1is` is DVM-broadcast to the other cores and the issuing core's `dsb ish`
waits for them. The discriminating prediction: a cross-core cost **scales with the number of
participating cores**; a purely local cost does **not**.

## 2. Method & platform controls

`munmap`-only timing via `experiments/munmap-tlbi/munmap_only.c` (and the per-phase
`experiments/mmap-split/mmap_split_bench.c`). Controls each run: `taskset -c 0`, governor
`performance` + frequency locked to 1.8 GHz **and re-locked after every CPU hotplug change** (a
hotplug-onlined core returns at the default governor — otherwise you silently benchmark at the wrong
clock), THP=never, ASLR=0, `cpuidle.off=1` (so an idle remote core's wake-up latency can't be
mistaken for broadcast cost). Core count varied by `echo 0/1 > /sys/devices/system/cpu/cpuN/online`.
N80 has **two clusters** ({0-3}=56, {4-7}=572, bench core cpu0 in 56), so the `{0,1}` vs `{0,4}`
pair holds remote-count fixed and varies only the cluster boundary.

The TLBI-timing kernel module (`tlbi_ab.ko`) measures the bare instruction directly: on cpu0 with
IRQs off, it times a batch of `vae1is`/`vae1` invalidations via `CNTVCT_EL0`. (A loadable module
works on this kernel — the earlier `BTF:-22` failure was a stale-module mismatch on the previous
build, not a config problem.)

## 3. Experiments, in order (including the false trail)

### 3.1 Core-scaling of munmap, by `min` — *apparent* scaling (later shown to be an artifact)
Protected, sparse 6.4–8 MB / 16 K, `min` µs vs online cores: alone (n=1) ≈ 220, any remote core
≈ 540; flat n=2→n=8; `{0,1}` ≈ `{0,4}`. nvhe stayed flat (~105). This *looked* like a binary
cross-core effect and reproduced ×3 — **on the `min`.** It drove an (incorrect) "≈74 % broadcast"
decomposition.

### 3.2 IS-vs-NSH TLBI module — bare invalidation is LOCAL and flat
Bare `tlbi` cost (IRQ-off, module):

| per slot (reps=2) | NSH (local) | IS (broadcast) | IS−NSH |
|---|---|---|---|
| nvhe | 10 ns | 23 ns | +13 ns |
| **protected** | **289 ns** | **289 ns** | **~0** |

In protected the per-slot cost is **289 ns, flat across n=1/2/8 and intra/cross cluster, IS=NSH,
and a per-slot `dsb` doesn't raise it.** So the bare TLBI + `dsb` is **local and core-independent**;
broadcast adds ~0. (The same holds with faithful user-VA + process-ASID invalidation — matching
exactly what munmap tears down.) This *contradicted* §3.1 and should have been believed.

### 3.3 dense vs sparse, by `min` — *apparent* "broadcast ∝ TLBIs"
Same 8 MB span: dense 4 K (integer `aside1is`, ~4 TLBIs, 2048 pages) `min` flat with cores; sparse
16 K (~2036 `vae1is`, 512 pages) `min` scaled +367 µs. This *looked* like the scaling tracks TLBI
count, not page count. **Also a `min` artifact** (see §3.5).

### 3.4 Cache-cold memory + TLBI — refutes "broadcast stalls memory"
A 128 MB LCG-permuted random dependent pointer-chase (misses the 2 MB L3, defeats prefetch),
seeded per-iteration so each batch is fresh-cold; core-scaled in protected:

| per slot | n=1 | n=2 cross | n=8 |
|---|---|---|---|
| mem-only (4 cold loads) | 617 | 621 | 617 |
| TLBI-only | 289 | 289 | 289 |
| TLBI + cold mem | 881 | 875 | 878 |

All flat; TLBI+mem (881) is *sub-additive* vs 617+289. The broadcast does **not** stall concurrent
memory and does **not** scale with cores. This killed the "broadcast traffic → backend stall"
synthesis outright.

### 3.5 perf + the `mean` — the `min` was the trap
perf-profiling the **real** munmap loop at n=1 vs n=8 (protected, raw PMU events):

| whole-run (300 iters) | n=1 | n=8 |
|---|---|---|
| wall time | 0.362 s | 0.348 s |
| cycles | 636 M | 625 M |
| `stall_backend` (r0024) | 427 M | 431 M |
| instructions | 552 M | 549 M |

**The entire run is the same at n=1 and n=8 (n=8 slightly faster).** `stall_backend` is flat.
Measuring the **mean** instead of the min confirms it for each phase:

| µs/iter (mean) | n=1 | n=8 |
|---|---|---|
| touch | 485 | 465 |
| **munmap (mmap_split)** | **699** | **681** |
| **munmap (munmap_only, 1000 iters)** | **mean 696** / min 269 | **mean 680** / min 396 |

**munmap's mean is flat — it does NOT scale with cores.** And the `min` is not even stable: n=8's
min fell from 676 (200 iters) to 396 (1000 iters) as more samples caught faster outliers.

**Why the `min` lied:** at n=1 the single core's background activity gives the per-iter munmap
*work* high variance (min ~250, mean ~700); at n=8 it is tight (~545). §3.1/§3.3 compared n=1's
**best-case** min to n=8's **typical** min and manufactured a fake ~2× "core-scaling." perf
(process cycles, which exclude preemption) shows equal work at n=1 and n=8 — there is no extra work
to attribute to other cores. Every metric that excludes single-core variance (mean, IRQ-off module,
perf) agrees: **flat with cores.**

## 4. The definitive conclusion

> **The pKVM munmap penalty is the local cost of invalidating a combined stage-1×stage-2,
> VMID-tagged TLB entry. It is core-independent — not cross-core, not broadcast, not a `dsb ish`
> completion wait.**

Quantitatively, from the IRQ-off module (§3.2): protected bare TLBI **289 ns/slot** vs nvhe
**23 ns/slot**, and **289 − 23 = 266 ns ≈ the report's +0.27 µs/slot.** So the report's number is
real, but it is the **per-slot invalidation** cost (combined entries are ≈12× costlier to invalidate
*locally*), **not** the "broadcast wait." The §6.2 `stall_backend` increase (protected vs nvhe) is
that slower TLBI **executing locally** (it retires over more cycles, surfacing as a backend stall),
not a cross-core completion wait — consistent with §3.5's flat n=1↔n=8 `stall_backend`.

## 5. Code examination — *why* the local cost is ≈12× nvhe's

The kernel-side path is **identical** in both modes: `arch/arm64/include/asm/tlbflush.h` has no
stage-2/mode awareness; munmap issues the same `tlbi vae1is` (×2 under KPTI) in nvhe and protected.
So the cost difference is entirely the **TLB entry type**, which is set by the host stage-2 config:

- **What flips it on** — `__pkvm_prot_finalize()` (`mem_protect/host.rs:2249`): sets
  `params.vttbr = kvm_get_vttbr(...)` (host stage-2 base **+ VMID**), `params.vtcr = host_mmu.arch.vtcr`,
  and `params.hcr_el2 |= HCR_VM` (`kvm_arm.h:74`, `HCR_VM = 1<<0`), then `__load_stage2(...)`.
- **What it is in nvhe** — `__load_host_stage2()` (`host.rs:2521`) takes the else branch:
  `VTTBR_EL2.set(0)`, and the host HCR (`HCR_HOST_NVHE_FLAGS`, `kvm_arm.h:101`) has **no** `HCR_VM`.

So in **protected** the host EL1&0 TLB entries are **combined (VA→PA, two stages folded) and
VMID-tagged**; in **nvhe** they are **pure stage-1 (VA→PA, one stage), ASID-only**. The host stage-2
itself is shallow (op=3 self-introspection: 99.5 % 1 GB blocks), so this is **not** about deep
nested walks — it's about the entry *class*. Per ARM DDI 0487 D8.16/D8.17, a VA-based `tlbi vae1is`
with stage-2 active must:
1. **match VMID** in addition to VA/ASID (extra tag comparison on every candidate), and
2. invalidate **two entry classes** that are keyed by VA — the **combined** VA→PA *and* the
   **stage-1-only** VA→IPA intermediate — whereas nvhe has only the single stage-1 class.

More tag matching + more structures to clear ⇒ the per-instruction execution latency rises from
~21 cyc (nvhe) to ~260 cyc (protected) here. The **exact ≈12× factor is FTC862 TLB
microarchitecture** (how it stores/searches VMID-tagged combined entries) — pinning it further would
need the Phytium TRM or core-specific TLB-invalidation PMU events, which N80 does not expose by name.

## 6. Methodological lesson (reusable)

**Never use `min` to compare a workload across machine configurations whose *variance* differs.**
Offlining cores changes the per-iteration variance (single-core → noisy, many-core → tight), and the
`min` then compares a best-case sample on one side to a typical sample on the other. Use the **mean**
(or median), and cross-check with `perf` **process** counters, which exclude preemption and measure
*work*, not wall time. Here the `min` produced a fully reproducible — and fully wrong — 2× "scaling."

## 7. Correction to the overview report

- §8.1 / §7.7: the "+0.27 µs/slot ... 广播等待 (broadcast wait)" attribution is **incorrect**. The
  +0.27 µs/slot is the **local** combined-entry invalidation cost (289 − 23 ns). The "逐页失效序列
  (per-slot invalidation sequence)" half is correct.
- The mechanism is **core-independent**; there is **no** dependence on online-core count or cluster
  placement. Any text implying a cross-core/broadcast/DSB-completion cost should be revised.
- Everything else stands: host stage-2 → slower sub-2 MB sparse munmap via the per-page TLBI path;
  FEAT_TLBIRANGE absent; nvhe and dense/integer-flush teardown unaffected; magnitude +0.27 µs/slot.

## 8. Open questions / future work

- **Pin the ≈12×** to a microarchitectural cause (VMID-tag match vs extra entry class vs TLB
  organization) — needs the Phytium TLB TRM or a core that exposes TLBI-cost PMU events.
- **Mitigations** are unchanged and now better motivated: FEAT_TLBIRANGE (collapses N per-page
  TLBIs into a few range TLBIs — fewer expensive combined-entry invalidations) is the lever;
  lowering `MAX_DVM_OPS` to push more munmaps onto the single `aside1is` integer-flush path trades
  per-slot cost for a whole-ASID refill. Neither is about broadcast.

## 9. Index

- Chronological log (with the false trail): `kylin-lmbench/experiments/munmap-tlbi/INVESTIGATION-LOG.md`
- Core-scaling CSVs + per-experiment README: `.../results/corescaling-n80/`
- TLBI-timing module + user driver: `.../tlbi_ab/{tlbi_ab.c, tlbi_user.c, Makefile}`
- Benches: `.../munmap_only.c`, `experiments/mmap-split/mmap_split_bench.c`
- Host stage-2 config: `arch/arm64/kvm/hyp/nvhe/rust/src/mem_protect/host.rs:2249,2521`;
  `arch/arm64/include/asm/kvm_arm.h:74,101`
- Report corrected: `pkvm_mmap_opt_docs/pkvm-mmap-overview.zh-CN.md` §7.7, §8.1
