# Stage 0 — capability & platform probe (Kaitian)

Establishes, with stock perf only, whether the pKVM `lat_mmap` regression *can* appear on this
board and whether the perf-native EL2 attribution (Stage 3) is trustworthy. See the playbook:
[../../../docs/mmap/perf-playbook/perf-only-mmap-investigation-playbook.md](../../../docs/mmap/perf-playbook/perf-only-mmap-investigation-playbook.md).

Run on the board (gcc/as/objcopy present): `make` then the commands below.

## Results (2026-06-24, Kaitian, FTC862, kernel 6.6.30-pkvm-clean, `kvm-arm.mode=protected`)

### 1. FEAT_TLBIRANGE — ABSENT on Kaitian → **GO**

**Evidence (corrected — the reliable signal is *behavioral*):** Kaitian's `munmap` shows the sharp
**2 MB cliff** (results §1: 1.9 MB 148.7 µs → 2.0 MB **88.2** µs). That drop is the kernel falling
back to a whole-ASID flush at `MAX_DVM_OPS` *because it has no range TLBI* — i.e. FEAT_TLBIRANGE is
absent. Same FTC862 core as N80. Without range TLBI the kernel issues per-page TLBI for sub-2 MB
teardown → the penalty can manifest. The investigation is worth running.

> ⚠ **The `isar0` EL0 register read is NOT valid evidence.** `ID_AA64ISAR0_EL1=0x0000111110212120`
> (TLB=0) looks like "absent", but the TLB field is `FTR_HIDDEN` — masked to 0 for userspace on
> *every* core. It agreed with reality here only because Kaitian genuinely lacks the feature; on
> Qualcomm Oryon (SM8850), which *has* FEAT_TLBIRANGE, the same read also returns 0 — a false
> negative (see [../android-sm8850/](../android-sm8850/)). Detect FEAT_TLBIRANGE behaviorally
> (the 2 MB cliff) or via the kernel cpucap (`dmesg | grep -i "TLB range maintenance instructions"`).

### 2. `:h` EL2 counting — VALIDATED
The PMU `:h` (EL2/hyp) modifier is accepted and reads **0 at rest**. Under a known-EL2 workload
(100,000 `KVM_RUN`s through the pKVM hypervisor) it lights up:
```
$ taskset -c 0 perf stat -e cycles,cycles:u,cycles:k,cycles:h,instructions:h ./kvm_el2_probe 100000
       498,122,488      cycles
         9,292,414      cycles:u          (host EL0)
       320,200,198      cycles:k          (host EL1)
       392,139,024      cycles:h          (EL2)        <-- 0 during sleep, 392M here
       672,148,644      instructions:h    # 1.71 IPC
       0.379 s elapsed     (guest=16B KVM_RUNs=100000 mmio_exits=100000)
```
`cycles:h` 0 → 392M proves pKVM does **not** zero EL2 self-counting. So Stage 3 ("is the munmap
time in EL2?") is a one-line `perf stat -e cycles:h` — no hypervisor patch, unlike the original
investigation's custom EL2-cycle hypercall. (The `u+k+h` sum exceeding plain `cycles` is the
expected perf guest/host-exclusion nuance; the conclusion rests only on `cycles:h ≫ 0`.)

### 3. Event availability (FTC862)
`cycles`, raw `r0024` (STALL_BACKEND), and named `stall_backend`, `stall_frontend`, `l1d_tlb`,
`l2d_tlb_refill`, `mem_access` all work. **`dtlb_walk` is not exposed by name → use raw `r0034`.**

## Files
- `isar0.c` — reads ID_AA64ISAR0_EL1 (⚠ TLB field is `FTR_HIDDEN`/masked — NOT a valid
  FEAT_TLBIRANGE detector; use the behavioral 2 MB-cliff test, see §1).
- `guest.S` + `kvm_el2_probe.c` — minimal KVM guest + driver for the `:h` positive control.
- `Makefile` — builds all three.
