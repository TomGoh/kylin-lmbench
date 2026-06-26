# Investigation log — is the pKVM munmap penalty cross-core TLB-broadcast sync?

Running lab notebook for the follow-up to the mmap-overview report
(`common/pkvm_mmap_opt_docs/pkvm-mmap-overview.zh-CN.md`). Append entries as we go.
Plan: `~/.claude/plans/lexical-sauteeing-micali.md`. Detailed data writeup:
`results/corescaling-n80/README.md`.

---

## Question

The report concluded the pKVM munmap slowdown is mechanism **a-1** — each per-page `TLBI`
(+ its `dsb ish` wait) costs more once host stage-2 makes TLB entries combined/VMID-tagged
(**+0.27 µs/slot**, ~490 cyc/slot) — but **deliberately did not** pin *where* the extra wait
lives (§2.3/§7.7 refuse to attribute it to "broadcast network").

**Hypothesis under test (user's):** the extra is specifically the **cross-core** sync — the
Inner-Shareable `TLBI` is DVM-broadcast to other cores and the issuing core's `dsb ish` waits
for them. Split into: **a-1-broadcast** (remote, scales with cores) vs **a-1-local** (issuing
core only, core-count-independent).

## STATUS (2026-06-15): hypothesis CONFIRMED by core-scaling (Phase A+B). Phase C pending.

> **~74% of the +0.27 µs/slot pKVM penalty is the cross-core broadcast wait; ~26% is local.**
> Reproduces the report's +0.27 µs/slot by an independent method.

---

## Platform & setup (reproducibility-critical)

- **N80**: Phytium FTC862, 8 cores / 1 socket / **2 clusters** {0-3}=cluster56, {4-7}=cluster572.
  Bench core **cpu0 ∈ cluster56**. 1.8 GHz locked. No FEAT_TLBIRANGE. KPTI **on** (2 `vae1is`/slot).
  `REPEAT_TLBI` workaround inactive.
- **Kernel**: `6.6.30xcore-stat2+` (Rust nVHE hyp), freshly built/deployed this session.
  `op=3` (host-s2 granularity) instrumentation live; matches report §7.1 (4K 8046 / 2M 2486 / 1G 1019).
- **Mode switching = reboot + GRUB menu selection.** Firmware boots the **ESP** grub.cfg
  (`/boot/efi/boot/grub/grub.cfg`, synced by Kylin `42_osloader`), NOT `/boot/grub/grub.cfg`.
  ESP grubenv is `/boot/efi/boot/grub/grubenv` (prefix-relative) — plain `grub-reboot` (writes
  `/boot/grub/grubenv`) does NOT work; one-shot needs `grub-editenv /boot/efi/boot/grub/grubenv
  set next_entry=…`, and `/boot/efi` only mounts under stock 5.4.18 (or any kernel with working
  modules). GRUB default = stock 5.4.18 (safe fallback).
- **Modules DO load on xcore-stat2+** (vfat mounts the ESP). The earlier `BTF:-22` failure was a
  *stale-module mismatch* on the previous kernel, not a config problem → Phase C can be a `.ko`.
- **`/tmp` is wiped on reboot** — re-ship `munmap_only.c` + `run-core-scaling.sh` after each boot.
- Env controls each run: THP=never, ASLR=0, governor=performance + freq re-locked after every
  hotplug change, `cpuidle.off=1` (boot). Metric = munmap-only **min** µs (cleanest).

## Method

`run-core-scaling.sh` (this dir): offline/online cores via `/sys/.../cpuN/online`, re-lock freq,
run `munmap_only` at fixed sub-2MB per-page points, emit CSV; restore all cores at end.
Cluster-aware sets, incl. the **`0,1` vs `0,4`** pair (1 remote, intra- vs cross-cluster).
Fixed points stay < 2 MB single-flush so munmap takes the per-page TLBI path.

---

## Phase A — protected core-scaling (2026-06-15) ✓

**Did:** main sweep + ×3 rechecks (6.4MB & 1.0MB) + size sweep 0.5–64 MB, all in protected.
**Found:**
- 6.4 MB: alone (n=1) ≈ **220 µs**, any remote core ≈ **540 µs** (+320), reproducible ×3.
- **Binary** in core count (n2 = n8), **intra = cross cluster** (`0,1` ≈ `0,4`).
- **Saturation-like** in slots: broadcast Δ = 0.6→21→54→175→323 µs at 0.5→6.4 MB.
- n=8 munmap linear at **~85 µs/MB**; n=1 ~34 µs/MB + ~30 µs fixed. (n=1 too noisy >6.4 MB —
  single-core contention; clean range ≤6.4 MB.)
**Means:** a cross-core effect exists in protected, but it's binary/saturation, not linear in
cores or cluster-distance. Needs nvhe to know if it's pKVM-specific.
**Data:** `results/corescaling-n80/protected-*.csv`.

## Phase B — nvhe core-scaling (2026-06-15) ✓ — VERDICT

**Did:** same sweeps in nvhe (booted via GRUB menu select of `xcore2-nvhe`).
**Found:** nvhe is **flat** with core count at every size — broadcast Δ = n8−n1 stays **0–5 µs**
(vs protected's up to +323). nvhe alone ≈ full ≈ 105 µs at 6.4 MB (×3 reproducible).
**Decomposition (6.4 MB, 1638 slots, µs/slot):**

| | protected | nvhe |
|---|---|---|
| full (n8) | 0.332 | 0.068 |
| alone (n1) | 0.134 | 0.065 |
| broadcast (n8−n1) | **0.198** | **0.003** |

```
pKVM extra 0.264 (≈report's 0.27) = broadcast 0.195 (~74%) + local 0.069 (~26%)
```
**Independent cross-check:** protected−nvhe at full cores = 85−17.4 = 67.6 µs/MB = 0.264 µs/slot,
reproducing the report's threshold-scan +0.27 by a different method.
**Means:** broadcasting stage-1-only entries is ~free; the expensive `dsb ish` wait is specific to
pKVM's combined VMID-tagged entries → **hypothesis confirmed, broadcast is the dominant ~3/4.**
**Data:** `results/corescaling-n80/nvhe-*.csv`.

---

## Phase C — IS-vs-NSH TLBI timing module (2026-06-15) ⚠️ COMPLICATES the story

**Did:** out-of-tree `tlbi_ab.ko` (loads on xcore-stat2+, no rebuild). On cpu0, IRQ-off, time
N-slot TLBI batches: IS=`vae1is`+`dsb ish` vs NSH=`vae1`+`dsb nsh`. Added a `dsb_per_slot` mode
and core-scaled it. `results/tlbi-ab-n80/`.

**Found (per slot, reps=2, cntvct timer):**

| | NSH (local) | IS (broadcast) | IS−NSH |
|---|---|---|---|
| nvhe | 10 ns | 23 ns | **+13 ns** |
| **protected** | **289 ns** | **289 ns** | **~0** |

- Protected per-slot cost is **289 ns, FLAT across n=1/2/8 and intra/cross cluster, IS=NSH**,
  and `dsb_per_slot=1` doesn't raise it → the `dsb ish` completion wait is **negligible**.
- So the *isolated* TLBI cost in pKVM is **LOCAL** (29× nvhe's) and **core-independent** — the
  broadcast/`dsb` adds ~0. nvhe shows a tiny (13 ns) broadcast cost; in protected it's lost
  under the 289 ns local cost.

**Tension with Phase B:** munmap's core-scaling (220→540 µs) said broadcast; the module says the
TLBI itself is local/flat. Both are real → **munmap's core-dependence is NOT in the TLBI/`dsb`
latency.** Working hypothesis: the TLBI *broadcast traffic* creates interconnect back-pressure
that stalls munmap's **concurrent page-free memory accesses** (reduces TLBI/work overlap), scaling
with online cores. The tight-loop module has no concurrent memory work to stall → flat. This would
*refine* the report's "广播等待→后端访存停顿": the stall is broadcast-traffic interference on
concurrent memory ops, not the `dsb ish` completion wait itself.

**Next to confirm:** interleave memory accesses (pointer-chase / cache-missing loads) with the
TLBIs in the module; if IS-with-memory scales with cores while NSH-with-memory stays flat, the
back-pressure mechanism is confirmed.

**CORRECTION (same day, user caught it):** the bare-TLBI IS/NSH method is **confounded in
protected** and its "IS=NSH, flat" is a *blind spot, not* evidence that broadcast is free —
broadcast demonstrably costs (nvhe IS−NSH=13 ns; Phase B munmap scales with cores). Confounds:
1. `tlbi vae1` (NSH) almost certainly **also broadcasts** for combined VMID-tagged entries on
   this Phytium (impl-defined over-invalidation) → IS≈NSH by construction; the IS−NSH trick only
   works in nvhe (stage-1 NSH is truly local).
2. Test VAs are **kernel-global, ASID 0, touched only by cpu0** → remote cores hold no matching
   entries, so the broadcast finds nothing and `dsb ish` completes instantly regardless of cores
   (≠ real munmap). Need user-ASID VAs that remote cores have actually cached.
3. The 289 ns is likely the **local instruction cost** of invalidating a combined entry
   (~520 cyc, genuinely core-independent), which *coexists* with a broadcast cost the tight loop
   doesn't expose. memwork=4 pointer-chase added only ~20 ns/slot (cache-WARM; min-over-iters
   defeats cold access) → didn't test the stall hypothesis.

**Revised plan:** (a) core-scale the **nvhe** IS−NSH (confirm the 13 ns is cross-core: ~0 at n=1
→ 13 at n=8) to validate the method where it works; (b) for protected, treat **Phase B munmap
core-scaling as the primary broadcast evidence**, and if a module confirmation is wanted, redo it
with user-VA + process-ASID invalidation (matching munmap) and cache-cold concurrent loads
measured without min-over-iters.

## Option C — dense vs sparse munmap core-scaling (2026-06-15) ✓ broadcast ∝ TLBIs, CONFIRMED

**Did:** core-scale munmap at the SAME 8 MB span, dense (4 KB → per-PMD 2 MB → integer
`aside1is`, few TLBIs, 2048 pages freed) vs sparse (16 KB → per-page, ~2036 TLBIs, 512 pages).
`results/corescaling-n80/protected-dense-vs-sparse.csv`. Protected, min µs:

| touch | TLBIs | pages | n=1 | n=8 | Δ |
|---|---|---|---|---|---|
| 8MB/4K dense | ~4 | 2048 | 373.8 | 361.7 | **≈0 flat** |
| 8MB/16K sparse | ~2036 | 512 | 308.9 | 676.0 | **+367 scales** |

**Result:** dense frees 4× more pages yet is **flat** with cores; sparse frees fewer pages yet
**scales +367 µs**. So munmap's core-dependence tracks **TLBI count, not page count** → it is the
per-page-TLBI **broadcast**, not page-free work. Magnitude: 367/2036 = **0.180 µs/slot**, matching
Phase B's 0.195. Clean, module-free confirmation of the broadcast mechanism (resolves the Phase C
method confound — the bare-TLBI module's blind spot, not the physics). **Next: Option B** — redo
the module faithfully (user-VA + process-ASID, remote cores pre-touch, cache-cold) as the
independent second method.

## Option B — faithful user-VA module (2026-06-15) ✓ resolves the mechanism

**Did:** module now invalidates the **caller's user VAs with its process ASID** (nG combined
entries, exactly what munmap tears down), driven by `tlbi_user.c`; core-scaled in protected.
**Found:** still **289 ns/slot, IS=NSH, flat n=1→n=8, intra=cross** (asid was a real ~23000 value).
So matching munmap's invalidation exactly doesn't change it: the **bare per-page TLBI cost in
pKVM is local and core-independent** (~520 cyc, the combined-entry invalidation instruction).

### Synthesis (B + C) — the mechanism, refined

| measurement | result | says |
|---|---|---|
| bare TLBI, isolated (B) | 289 ns/slot, **flat** with cores | the instruction/`dsb` is **local** |
| munmap, TLBIs + page-free (C, Phase B) | **+0.18 µs/slot, scales** with cores, ∝ TLBI count | cross-core cost is real |

Both true ⇒ the cross-core cost is **not** the `dsb ish` completion wait or the TLBI instruction
itself (local, flat in isolation). It is the **per-page TLBI broadcast *traffic* contending with /
stalling munmap's concurrent page-free memory accesses**, scaling with online cores and ∝ TLBI
count. This **refines** the report's "广播等待→后端访存停顿": the backend stall (report §6.2:
+40.9M stall_backend, instructions/dtlb_walk unchanged) is broadcast-traffic-vs-memory contention,
not the completion wait per se. Answer to the hypothesis: **yes, the munmap penalty is cross-core
and broadcast-driven — but via broadcast-traffic-induced memory stall (∝ TLBIs × cores), measured
at ~0.18–0.20 µs/slot**, consistent across Phase B, Option C, and the report's +0.27 µs/slot
(which also folds in the ~0.07 local combined-entry cost the module isolates as the 289 ns floor).

## Task 14 — direct memory-stall test (2026-06-15) ✗ REFUTES the synthesis

**Did:** rebuilt `tlbi_ab` with a 128 MB LCG-permuted **random dependent** pointer-chase (misses
the 2 MB L3, defeats prefetch), seeded per-iter so every batch is fresh-cold; added reps=0
(mem-only). Core-scaled mem-only / TLBI-only / TLBI+mem in protected.

| config | n=1 | n=2 cross | n=8 |
|---|---|---|---|
| mem-only (4 cold loads/slot) | 617 | 621 | 617 |
| TLBI-only | 289 | 289 | 289 |
| TLBI + cold mem | 881 | 875 | 878 |

**All flat with cores; TLBI+mem (881) is SUB-additive vs 617+289=906.** So the per-page broadcast
does NOT stall concurrent (cold or, earlier, warm) memory, and does not scale with cores in this
synthetic setting. **The "broadcast traffic stalls concurrent memory" synthesis is REFUTED.**

### Where this leaves the investigation (honest)

SOLID: munmap's pKVM penalty **scales with cores, is ∝ per-page TLBI count (sparse vs dense), and
is pKVM-specific (nvhe flat)** — Phase B + Option C, robust & reproduced. Bare TLBI and TLBI+generic
memory are **flat** (Option B, task 14). So the core-scaling is **NOT** the bare `dsb ish`
completion latency, and **NOT** broadcast-stalling-generic-memory — both are flat/instant here.

OPEN: the mechanism linking "many per-page combined-entry TLBIs" to "munmap time scales with
online cores" is **not identified**. The synthetic module cannot reproduce it with private cold/warm
memory, so it is something specific to munmap's real teardown path — candidates not yet tested:
cache-coherence/snoop traffic on **shared** kernel page-free structures (folio refcount atomics, LRU/
zone locks, page-cache xarray) that scales with online cores; or loss of TLBI/page-free instruction
**overlap** under broadcast back-pressure that only the real (overlappable) page-free exhibits
(munmap's effective per-slot at n=1 ≈ 152 ns is *below* the isolated 289 ns TLBI → it overlaps; the
synthetic cold-chase doesn't overlap, so it can't lose overlap). NEXT: profile munmap's teardown at
n=1 vs n=8 (perf raw events: stall_backend, L2/L3 snoop, bus) to find what actually scales — the
module approach has run its course.

## ★ DEFINITIVE FINDING (2026-06-15) — the core-scaling was a MIN ARTIFACT; cost is LOCAL

perf-profiled real munmap at n=1 vs n=8 (protected, 5.4 perf binary, raw events). **The whole run
is the same at n=1 and n=8** — wall 0.362 vs 0.348 s, cycles 636M vs 625M, `stall_backend` 427M vs
431M: all FLAT (n=8 if anything faster). Then measured the **mean** (not min):

| µs/iter (mean) | n=1 | n=8 |
|---|---|---|
| touch (mmap_split) | 485 | 465 |
| **munmap (mmap_split)** | **699** | **681** |
| munmap (munmap_only, 1000 iters) | mean **696** / min 269 | mean **680** / min 396 |

**munmap's MEAN is flat with cores (≈690, n=8 slightly faster). It does NOT scale.** Phases A/B and
Option C used **min**, and at n=1 the per-iter munmap *work* has high variance (min ~250–270, mean
~700) while n=8 is tight — so comparing n=1's best-case min to n=8's typical min **manufactured a
fake ~2× "core-scaling."** The min is also iter-count-unstable (n=8 min 676→396 as iters 200→1000).
perf (process cycles, excludes preemption) confirms: equal work n=1↔n=8.

### Corrected conclusion — answers "exactly why"

The pKVM munmap penalty is **NOT cross-core / NOT broadcast / does NOT scale with cores.** It is the
**local microarchitectural cost of invalidating a combined stage-1×stage-2, VMID-tagged TLB entry**:
the bare per-slot TLBI is **289 ns/slot in protected vs ~23 ns/slot in nvhe** (Option B module, IRQ-off,
core-independent) — and **289 − 23 = 266 ns ≈ the report's +0.27 µs/slot.** So the report's +0.27 is
real but is the **local invalidation** cost (combined entries are ~12× costlier to invalidate locally,
the hw walks more TLB structures); its attribution to **"广播等待 / broadcast wait" is wrong** — the
module shows IS=NSH (broadcast adds ~0), dsb_per_slot flat, TLBI+memory flat, all core-independent.
The §6.2 `stall_backend` is the combined-entry TLBI taking more cycles to *execute locally* (shows up
as backend stall), not a cross-core completion wait.

**Every clean (mean / IRQ-off / perf) measurement agrees: local, flat with cores.** The only thing that
ever said "cross-core" was the min, and the min was an artifact. User's push for perf + "exactly why"
is what exposed it.

### What still stands from the report
host stage-2 → pKVM munmap slower for sub-2MB sparse teardown (per-page TLBI path; FEAT_TLBIRANGE
absent); magnitude +0.27 µs/slot; nvhe/dense unaffected. CORRECTED mechanism: local combined-entry
invalidation cost, not broadcast/cross-core.

## Open questions / next

- **Phase C (Exp 2, pending):** IRQ-off **IS-vs-NSH** TLBI cycle-timing on a fixed core to confirm
  the 74/26 split *without* the hotplug-DVM-domain assumption. Now feasible as an out-of-tree
  `.ko` (modules load) — no kernel rebuild. Needs protected mode (currently nvhe). Cross-checks:
  Exp1 n=1 ↔ Exp2 NSH, Exp1 full ↔ Exp2 IS.
- **Caveat being retired by Phase C:** Phase A/B assume hotplug-offline removes a core from the DVM
  domain. The clean n1↔n8 separation suggests it does, but Exp 2 doesn't depend on it.
- **Why binary, not linear in cores?** DVM `dsb ish` completion appears dominated by the
  local→interconnect round-trip once ≥1 remote core exists, not by #ACKs. (Open: confirm via Exp 2
  / PMU snoop counters — N80 only exposes raw `armv8_pmuv3_0` codes.)
- **KPTI-off lever (optional):** `nokaslr kpti=off` → 1 `vae1is`/slot; broadcast-bound cost should ~halve.

## Index

- Driver: `run-core-scaling.sh`; bench: `munmap_only.c`.
- Data + detailed writeup: `results/corescaling-n80/` (README.md has the full decomposition).
- Report being verified: `common/pkvm_mmap_opt_docs/pkvm-mmap-overview.zh-CN.md` §7.4–7.7, §8.1.
- Plan: `~/.claude/plans/lexical-sauteeing-micali.md`.
