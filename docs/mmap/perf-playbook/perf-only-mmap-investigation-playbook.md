# Perf-only pKVM `lat_mmap` investigation playbook (design spec)

| | |
|---|---|
| Date | 2026-06-24 |
| Status | **Design approved; setup (perf) complete; execution pending** |
| Goal | A **reusable, zero-kernel-patch procedure** that takes any installed pKVM board from "is there an mmap regression?" to "here is the mechanism", using only `perf` + standard sysfs/userspace |
| First target | Kaitian (Phytium **FTC862**, Kylin V10 SP1, kernel `6.6.30-pkvm-clean`, `kvm-arm.mode=protected`) |
| Constraint | **No modification of the `common` kernel source.** Only `perf` (built from `common/tools/perf`, see [build-perf-on-kaitian.md](build-perf-on-kaitian.md)), benches under `kylin-lmbench`, and runtime/boot controls. |
| Relation to prior work | Independent perf-only re-run of the investigation documented in [../pkvm-mmap-overview.zh-CN.md](../pkvm-mmap-overview.zh-CN.md). The original used **two custom hypervisor hypercalls** (EL2-cycle gate; `op=3` host-stage-2 introspection); this playbook replaces both with stock perf. |

---

## 1. Why redo it, and why this is feasible

The original investigation reached a complete, evidenced root cause (sub-2 MB teardown issues a
per-page `TLBI` per 4 KB flush slot; under host stage-2 each costs ~+0.27 µs more; the lever is
FEAT_TLBIRANGE, absent on these boards). But two of its five stages needed a **patched
hypervisor**:

- **Stage 3 (EL2 attribution)** — a custom `xcore_stats` hypercall set `PMCCFILTR_EL0` to count
  EL2-only cycles.
- **Stage 5 (mechanism)** — a custom `op=3` hypercall walked the host stage-2 page table to
  histogram block sizes.

A **stock pKVM board cannot be patched** (e.g. Kaitian's installed kernel). The value of this
playbook is a methodology that needs **nothing but perf**, so it runs anywhere. The two
hypercall-dependent stages have clean perf-native replacements:

| Original mechanism | Perf-only replacement |
|---|---|
| EL2-cycle hypercall (Stage 3) | `perf stat -e cycles:h` — the **`:h` exception-level modifier counts EL2/hyp directly** (validated: accepted on Kaitian, reads 0 during `sleep`). Positive control = faulting fresh pages → host-stage-2 abort → EL2. |
| `op=3` host-stage-2 introspection (Stage 5) | **Behavioral** refutation of the nested-walk hypothesis: perf TLB-walk counters (`r0034` DTLB_WALK, `l2d_tlb_refill`) + the dense-vs-sparse touch control. No table read needed. |

Stages 1, 2, and 4 of the original were already pure userspace-timing / perf, so they port for
free (Stage 4 literally used `perf`).

**Platform note (de-risks the re-run):** Kaitian is CPU part `0x862` = **the same FTC862 core as
N80**, where the original deep mechanism work was done. Same PMU event set, and almost certainly
the same FEAT_TLBIRANGE status — so we *expect* reproduction rather than divergence. Stage 0 still
verifies empirically; the "platform divergence" branch is a tail case, not the base case.

---

## 2. Deliverables

1. **This spec** — the staged procedure, exact perf events, decision tree, fallbacks.
2. **The perf build record** — [build-perf-on-kaitian.md](build-perf-on-kaitian.md) +
   [build-perf-on-kaitian.sh](build-perf-on-kaitian.sh) (done).
3. **Scripts + dataset** — self-contained run scripts under
   `kylin-lmbench/experiments/perf-reinvestigation/` and the Kaitian results they produce.

All artifacts live in **`kylin-lmbench`**; `common` is never written to.

---

## 3. Environment & controls (the methodological spine)

Applied before every measurement run:

- **Pin** `taskset -c 0`; **governor** `performance`, frequency locked, **re-locked after any CPU
  hotplug** (an onlined core returns at the default governor).
- **THP=never**, **ASLR=0**, `perf_event_paranoid=-1`, `kptr_restrict=0` (runtime, root).
- Boot-param controls (`cpuidle.off=1`, optional `isolcpus`) added to the GRUB entry — free,
  because we reboot to switch modes anyway.
- **Report the MEAN** over ≥300 iters, never the `min`. This is the exact trap that produced the
  original false "broadcast" conclusion (offlining cores changes per-iteration *variance*, so
  `min` compares a best-case sample on one side to a typical sample on the other). Baked into
  every harness; cross-check with `perf` **process** counters (which measure work, not wall time).

**Baseline strategy:** the backbone is the **protected ↔ nvhe** contrast. We reboot Kaitian
between the GRUB `protected` and `nvhe` entries (a dual setup exists). nvhe has no host stage-2,
so its TLB entries are pure stage-1/ASID-only — the control that isolates the host-stage-2 cost.

---

## 4. Stage 0 — capability & platform probe (the keystone of "stock-kernel")

This is what makes the playbook portable: it tells you what a given board can and can't support
**before** you trust any later stage. (Partly executed already during the perf build.)

| Probe | Command / method | Why |
|---|---|---|
| perf events exist | `perf list`; `perf stat -e r0024,r0034,stall_backend,l2d_tlb_refill -- true` | FTC862 ≠ other cores; confirm the events the playbook needs. **Known: `dtlb_walk` not named → use `r0034`.** |
| `:h` EL2 counting | `perf stat -e cycles:h` under a known-EL2 workload (fault fresh `MAP_ANON` pages → `host_mem_abort`) | Distinguishes "EL2 counting works" from "pKVM silently zeroes it". **Known: `:h` accepted, 0 during sleep; positive control still TODO.** |
| **FEAT_TLBIRANGE** | tiny EL0 `mrs ID_AA64ISAR0_EL1` reader, decode TLB field [59:56] (`0b0010` ⇒ present) | **The one ISA bit that decides whether the regression appears at all.** If present, the kernel uses range-TLBI and the per-page penalty likely vanishes — a valid finding, not a failure. |

`ID_AA64ISAR0_EL1` is readable from EL0 via the kernel's MRS emulation (sanitised value). This
~10-line probe is itself part of the deliverable.

---

## 5. Stages 1–6 — perf event mapping

| Stage | Question | Bench (in `kylin-lmbench`) | Key perf / measurement | Expected (if FTC862 reproduces N80) |
|---|---|---|---|---|
| **1 Symptom** | Real gap? Lifecycle vs steady-state? | `lat_mmap` 0.5–64 MB; `lat_mem_rd`, `bw_mem` | wall-time, **protected vs nvhe** | lifecycle gap grows with size; steady-state flat |
| **2 Localize** | Which phase? | `mmap_split_bench` (12 sub-tests) | mean phase time | gap concentrates in `munmap_after_write_touch` |
| **3 EL2 attribution** | Time in EL2? | munmap-only loop + fresh-anon positive control | `perf stat -e cycles:h,instructions:h,cycles,cycles:k` | `:h` ≈ 0 in steady munmap; > 0 in control |
| **4 Cost layering** | More work, or slower work? | `munmap_only` | `instructions, page-faults, r0034(DTLB_WALK), l2d_tlb_refill, stall_backend(r0024), cycles` | equal work; protected's extra cycles ≈ extra backend stall |
| **5 Mechanism** | a-1 (TLBI) vs a-2 (walk)? | `munmap_only` size sweep + dense-vs-sparse | gap vs flush-range; dense(4K) vs sparse(16K) at fixed span | **2 MB cliff**; gap ∝ TLBI count not page/walk count ⇒ a-1; walk counters refute a-2 |
| **6 Generality** | munmap-specific? local or broadcast? | `op_sweep` (munmap/MADV_DONTNEED/mprotect); core-scaling | per-op gap table; mean munmap + perf **process** counters at n=1 vs n=max online cores | op-independent < 2 MB; flat with cores ⇒ local, not broadcast |

Notes:
- Benches already exist as source in the repo: `src/lat_mmap.c`, `experiments/mmap-split/`,
  `experiments/munmap-tlbi/{munmap_only.c,op_sweep.c}`. Build natively on Kaitian (gcc present).
- Stage 6's core-scaling reproduces the local-vs-broadcast finding **with perf only** (the
  original's decisive evidence was already perf at n=1 vs n=8); the original's IRQ-off kernel
  module is **out of scope** here (it isn't perf).

---

## 6. Decision tree (so the run adapts)

```
Stage 0: FEAT_TLBIRANGE present?
  ├─ yes ─> kernel uses range-TLBI; per-page penalty likely absent.
  │         Pivot: document "why this board is immune", confirm with a flat Stage-1 sweep, stop.
  └─ no  ─> proceed.
Stage 1: protected - nvhe gap present?
  ├─ no  ─> re-check Stage 0 / controls; if truly flat, that is the finding.
  └─ yes ─> Stages 2..6.
Stage 3: ':h' usable?
  ├─ yes ─> EL2 attribution by perf.
  └─ no  ─> degrade to architectural argument (steady munmap enters no EL2) + absence of kvm
            tracepoints; rest of the chain is unaffected.
```

---

## 7. Risks / fallbacks

- distro `perf` missing / mismatched → **build matched perf from `common/tools/perf`** (done).
- raw event absent on FTC862 → `cycles − frontend` proxy or `perf record` localization.
- `:h` blocked under pKVM → architectural argument (Stage 3 fallback above).
- **FEAT_TLBIRANGE present → reframe, not failure** (decision tree).
- single-core variance → **mean, not min** + perf process counters (control §3).

---

## 8. What "done" looks like

A committed playbook doc (this file) + the perf build record + a `perf-reinvestigation/` dataset
that, on Kaitian, either (a) reproduces the original chain end-to-end using only perf — including
a perf-native `cycles:h ≈ 0` EL2 result and a 2 MB per-slot cliff — or (b) shows, with Stage-0
evidence (FEAT_TLBIRANGE), why Kaitian behaves differently, with the methodology intact either way.

---

## 9. Current status (2026-06-24)

- [x] Design approved (full perf-only chain, "Approach A").
- [x] **perf built & validated** on Kaitian — see [build-perf-on-kaitian.md](build-perf-on-kaitian.md).
- [x] **Stage 0 complete** — see [../../../experiments/perf-reinvestigation/stage0/](../../../experiments/perf-reinvestigation/stage0/):
  - **FEAT_TLBIRANGE ABSENT** (`ID_AA64ISAR0_EL1=0x0000111110212120`, TLB[59:56]=0) → **GO** (same as N80).
  - **`:h` EL2 counting VALIDATED** — `cycles:h` 0 at rest → **392M** under 100k `KVM_RUN`s. Stage 3 is perf-only, no hypercall.
  - Events: `r0024`/`stall_backend`/`l1d_tlb`/`l2d_tlb_refill`/`mem_access` OK; `dtlb_walk` not named → use `r0034`.
- [ ] Stages 1–6 execution (build benches on board; protected-side suite; one reboot to nvhe baseline; reboot back).
- [ ] `kylin-lmbench/experiments/perf-reinvestigation/` run scripts + dataset.

## 10. Index

- Perf build runbook: [build-perf-on-kaitian.md](build-perf-on-kaitian.md) ·
  script: [build-perf-on-kaitian.sh](build-perf-on-kaitian.sh)
- Original investigation: [../pkvm-mmap-overview.zh-CN.md](../pkvm-mmap-overview.zh-CN.md)
- Original follow-ups: [../pkvm-munmap-corescaling-followup.en.md](../pkvm-munmap-corescaling-followup.en.md),
  [../pkvm-teardown-op-generality.en.md](../pkvm-teardown-op-generality.en.md)
