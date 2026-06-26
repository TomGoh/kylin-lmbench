# Core-scaling sweep — is the pKVM munmap penalty cross-core TLB-broadcast sync?

Data from N80 (Phytium FTC862, 8 cores / 1 socket / **2 clusters** {0-3}=56 {4-7}=572,
bench core cpu0 ∈ cluster 56), kernel `6.6.30xcore-stat2+`. Driver:
`../run-core-scaling.sh`. Metric: `munmap`-only time, **min** µs over N iters
(min = least background-DVM-contended run = cleanest read).

## The claim being verified (report §8.1)

> 写触摸后的 munmap … 对小于 2 MB 的刷新范围逐页发出 TLBI … host stage-2 使能后，TLB 中为带
> VMID 标记的两级合成条目，每个 4K flush slot 对应的逐页失效序列**与广播等待**代价显著增加
> （**约 +0.27 µs/slot，约 490 周期/slot**），等待表现为后端访存停顿。

The report attributes the **+0.27 µs/slot** pKVM extra to "per-slot invalidation **+ broadcast
wait**" but does **not** prove the broadcast (cross-core) part. This experiment isolates it:
vary the number of cores in the Inner-Shareable domain and watch whether the cost scales.

## Design rationale (the controls *are* the argument)

- **Fixed points stay < 2 MB single-flush** (`stride=16 KB` sparse): keeps munmap on the
  per-page TLBI / broadcast-heavy path. A ≥2 MB point switches to one `aside1is` and erases
  the signal — so we never use one.
- **Re-lock governor+freq after every hotplug change**: a hotplug-onlined core returns at the
  default governor; without re-locking we'd silently benchmark at the wrong frequency.
- **`cpuidle.off=1`** (boot cmdline): an idle remote core's wakeup latency would masquerade as
  broadcast cost and fake the hypothesis.
- **Cluster-aware sets, esp. the `0,1` vs `0,4` pair**: same remote count (=1), differs *only*
  by the cluster boundary — the cleanest "same-chip / cross-cluster fabric" probe.

## Files

| file | what |
|---|---|
| `protected-main-sweep.csv` | first full sweep, sets 0 / 0,1 / 0,4 / 0-3 / 0-4 / 0-7, points 1.0:4 & 6.4:16 |
| `protected-recheck-6p4MB-run{1,2,3}.csv` | 6.4 MB, n=1/2/8, 200 iters ×3 (reproducibility) |
| `protected-recheck-1p0MB-run{1,2,3}.csv` | 1.0 MB, n=1/2/8, 200 iters ×3 |
| `protected-sizesweep-0p5to6p4MB.csv` | sparse size sweep, n=1 vs n=8 |
| `protected-sizesweep-8to64MB.csv` | extended sizes (n=8 stays linear; n=1 noisy >6.4 MB) |

## Protected-mode findings

1. **The penalty is a cross-core effect** — at 6.4 MB it vanishes when cpu0 is alone:
   n=1 ≈ **220 µs**, any remote core ≈ **540 µs** (+320 µs), reproducible ×3.
2. **Binary in core count** — n=2 ≈ n=8, and **intra-cluster `0,1` ≈ cross-cluster `0,4`**.
   Adding cores / crossing the cluster boundary adds nothing.
3. **Saturation-like in slot count** — broadcast Δ(n8−n1): 0.5 MB ≈ 0, 1 MB +21, 2 MB +54,
   4 MB +175, 6.4 MB +323 µs. Small TLBI batches broadcast cheaply (pipelined); large batches
   serialize. (Explains why 256-slot points show ~no effect but 1638-slot points show a big one.)
4. **n=8 munmap is linear at ~85 µs/MB** (0.5→64 MB); the alone cost is ~34 µs/MB + ~30 µs fixed.

## Per-slot reconciliation with the report (sparse, 6.4 MB = 1638 4K slots)

| quantity | µs/slot | source |
|---|---|---|
| protected, full cores | **0.33** | 540 µs / 1638 |
| nvhe, full cores (report §7.5 = 108.6 µs) | **0.066** | 108.6 / 1638 |
| **pKVM extra (protected − nvhe)** | **0.27** | matches report's +0.27 ✓ |
| protected, alone (n=1) | 0.134 | 219.7 / 1638 |
| protected **broadcast** (full − alone) | **0.198** | this experiment |

**Decomposition the nvhe sweep must confirm.** If nvhe is *flat* with core count
(nvhe-alone ≈ nvhe-full ≈ 0.066, i.e. stage-1-only entries are cheap to invalidate remotely):

```
pKVM extra 0.27 = broadcast 0.198 (protected-only)  +  local 0.068 (prot_alone − nvhe_alone)
                ≈ 74% cross-core broadcast           +  ≈ 26% local combined-entry cost
```

→ the broadcast (cross-core) would be the **dominant** component of the +0.27 µs/slot. If instead
nvhe *also* slows with cores by ~0.198/slot, the broadcast is **not** pKVM-specific and the 0.27
is local — refuting the hypothesis. **nvhe n=1 vs n=8 is the linchpin** (Phase B).

## Phase B result (nvhe) — VERDICT: hypothesis CONFIRMED

nvhe is **flat** with core count at every size (broadcast Δ = n8−n1 stays ~0–5 µs vs protected's
up to +323 µs). nvhe-alone ≈ nvhe-full ≈ 105 µs at 6.4 MB, reproducible ×3. So broadcasting
stage-1-only entries is nearly free; the expensive cross-core wait exists **only** under pKVM's
combined VMID-tagged entries. Final per-slot decomposition (6.4 MB, 1638 slots):

| µs/slot | protected | nvhe |
|---|---|---|
| full cores (n=8) | 0.332 | 0.068 |
| alone (n=1) | 0.134 | 0.065 |
| **broadcast (full−alone)** | **0.198** | **0.003** |

```
pKVM extra  = protected_full − nvhe_full      = 0.332 − 0.068 = 0.264  (≈ report's +0.27 ✓)
            = broadcast extra + local extra
  broadcast extra = prot_bcast − nvhe_bcast   = 0.198 − 0.003 = 0.195   → ~74%   CROSS-CORE
  local extra     = prot_alone − nvhe_alone   = 0.134 − 0.065 = 0.069   → ~26%   local combined-entry
```

Independent cross-check: protected_full − nvhe_full across the size sweep = 85 − 17.4 = **67.6 µs/MB
= 0.264 µs/slot**, reproducing the report's threshold-scan +0.27 µs/slot from a completely
different method (core-scaling instead of the 2 MB threshold scan).

**Conclusion: ~74% of the +0.27 µs/slot pKVM munmap penalty IS the cross-core TLB-broadcast
(`dsb ish`) wait** — vanishes when cpu0 is alone, present whenever ≥1 remote core, insensitive to
cluster placement, saturation-like in slot count. The remaining ~26% is the local cost of
invalidating combined VMID-tagged entries. Phase C (IRQ-off IS-vs-NSH built-in) will confirm the
74/26 split by a second independent method.

## Caveats / next

- **n=1 single-core noise** grows with op length; clean only ≤ ~6.4 MB. The saturated per-slot
  broadcast cost is better pinned by **Experiment 2** (IRQ-off IS-vs-NSH TLBI built-in), which
  needs no core-offlining and avoids this noise.
- **Hotplug-DVM-domain caveat**: an offlined core may not leave the interconnect's DVM domain on
  every implementation. The clean n=1↔n=8 separation here suggests offline *does* remove cores,
  but Exp 2 confirms broadcast-vs-local independently of hotplug semantics.
