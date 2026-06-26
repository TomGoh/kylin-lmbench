# Cross-platform check — Oryon SM8850 (Android / Gunyah) HAS FEAT_TLBIRANGE

| | |
|---|---|
| Date | 2026-06-24 |
| Device | Xiaomi "pandora" (model `25098PN5AC`), Snapdragon 8 Elite Gen 5 (SM8850, "canoe") |
| CPU | Qualcomm **Oryon**, Armv9 (implementer `0x51`, part `0x002`), 8 cores |
| Kernel | `6.12.23-android16`, build type `user`; root via KernelSU |
| Hypervisor | **Gunyah** — NOT pKVM/KVM |
| Question | Does the Oryon core implement **FEAT_TLBIRANGE** (the lever FTC862 lacks)? |
| Answer | **YES — PRESENT** (authoritative: kernel cpucap) |

## Authoritative evidence — kernel cpucap (unmasked EL1 read at boot)
```
[    0.013505] CPU features: detected: TLB range maintenance instructions
```
The kernel's `has_cpuid_feature()` reads the **real, unmasked** `ID_AA64ISAR0_EL1.TLB` at EL1
during boot and sets `ARM64_HAS_TLB_RANGE`; the cpucap's `.desc` is logged. This is the CPU-feature
check, not an inference. (Reading it required a reboot: the 2 MB `log_buf` had wrapped after ~2.5 h
uptime and pstore was empty, so the boot lines were gone from the live buffer.)

## Why the userspace register read CANNOT show this (false-negative trap)
An EL0 `mrs ID_AA64ISAR0_EL1` returns a sanitised value whose **TLB field [59:56] is `FTR_HIDDEN`**
(`arch/arm64/kernel/cpufeature.c: ftr_id_aa64isar0[]`) — masked to 0 for userspace on *every* core.
On Oryon it reads `0x1021111110212120` → TLB=0, a **false negative** (the core *has* the feature).
This retro-corrects the Kaitian Stage-0 register method (see [../../stage0/README.md](../../stage0/README.md) §1):
the real evidence there was the behavioral 2 MB cliff, not the register.

## Behavioral corroboration — no 2 MB cliff
Pinned cpu7 @ performance (2.67 GHz), anon dense 4 K, 500 iters, mean µs/iter:

| flush range | Oryon SM8850 | Kaitian FTC862 |
|---:|---:|---:|
| 1.0 MB | 57.7 | 79.6 |
| 1.8 MB | 99.6 | — |
| 1.9 MB | 102.1 | 148.7 |
| 1.95 MB | 103.9 | — |
| **2.0 MB** | **108.5** | **88.2** ⬅ drop |
| 2.05 MB | 111.3 | — |
| 2.5 MB | 135.9 | — |
| 4.0 MB | 213.4 | 174.6 |

Oryon rises **smoothly and monotonically through 2.0 MB** (1.95→2.0→2.05 = 103.9→108.5→111.3,
on-trend) — the kernel uses range TLBI for all sizes, so there is no per-page→whole-ASID fallback.
Kaitian *drops* at 2.0 MB (the no-TLBIRANGE signature). Consistent with the cpucap.

## Hypervisor: Gunyah, not pKVM
```
[    0.000000] KVM is not available. Ignoring kvm-arm.mode
… reserved mem: … gunyah_hyp_region@80000000
```
`/dev/gunyah` present, `/dev/kvm` absent, `ro.boot.hypervisor.version=gunyah`. The
`kvm-arm.mode=protected` cmdline flag is **inert** (the HLOS runs as a Gunyah guest at EL1, no EL2,
so KVM never initialises). The pKVM protected-vs-nvhe contrast is therefore impossible on this
device — this is purely a CPU-feature / kernel-TLBI-path data point.

## Conclusion
SM8850 / Oryon **implements FEAT_TLBIRANGE** → the kernel uses range TLBI → the FTC862 per-page-TLBI
`munmap` penalty **does not exist on this core**. Confirms the "modern Armv9 core is immune; the fix
is silicon" thesis from the upstream-status analysis.

## Build / run (no NDK needed)
A static glibc aarch64 binary runs on the Android kernel for these tiny benches:
```
aarch64-linux-gnu-gcc -O2 -static -o munmap_only_android experiments/munmap-tlbi/munmap_only.c
adb push munmap_only_android /data/local/tmp/munmap_only && adb shell chmod 755 /data/local/tmp/munmap_only
# governor=performance + taskset (toybox hex mask, e.g. 0x80 = cpu7) need root (KernelSU su)
# authoritative cpucap (after a fresh boot, before log_buf wraps):
adb shell su -c dmesg | grep -i "TLB range maintenance"
```
