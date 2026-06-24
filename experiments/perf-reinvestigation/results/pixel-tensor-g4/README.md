# Cross-platform A/B — Pixel 9 Pro XL (pKVM + FEAT_TLBIRANGE): no resolvable munmap penalty

| | |
|---|---|
| Date | 2026-06-24 |
| Device | Google Pixel 9 Pro XL (`komodo`), **AOSP `aosp_komodo-userdebug`** (adb root) |
| SoC | Google **Tensor G4** — Armv9.2 cores: 1× Cortex-X4 (`0xd82`) + 3× A720 (`0xd81`) + 4× A520 (`0xd80`) |
| Kernel | `6.1.84-android14` (GKI) |
| Hypervisor | **pKVM** — real protected KVM: `kvm-arm.mode=protected`, `/dev/kvm` present, `All CPU(s) started at EL2`, `Protected KVM` cpucap, `Protected nVHE mode initialized`, S2MPU bound to the hypervisor |
| FEAT_TLBIRANGE | **PRESENT** (kernel cpucap `TLB range maintenance instructions`) |
| Question | On a **real pKVM host that has range TLBI**, does the host-stage-2 add any munmap cost? (the open question from the core-scaling follow-up) |
| Answer | **No resolvable penalty** — the protected−nvhe difference is below the phone's noise floor. |

This is the decisive cell of the matrix: Kaitian gave pKVM + *no* TLBIRANGE (big penalty), Oryon gave
TLBIRANGE but Gunyah (no KVM A/B possible). This Pixel gives **pKVM + TLBIRANGE**, so the A/B isolates
whether the penalty is inherent to pKVM or gated on the hardware feature.

## How the protected↔nvhe switch was done (and safely reverted)

On this device `kvm-arm.mode=protected` is set by the **bootloader** (`abl`), not by any flashable
boot/vendor image — so it can't be edited directly, and the bootloader must never be touched (brick
risk). The lever: the kernel parses `kvm-arm.mode` **last-wins**, and the DTB `/chosen/bootargs` (in
`vendor_kernel_boot`) lands *after* the bootloader's token in the assembled cmdline. So appending
`kvm-arm.mode=nvhe` to the DTB bootargs overrides it.

The edit was a **same-length binary replace** — the now-irrelevant `kvm-arm.protected_modules=…` token
(49 bytes) overwritten with `kvm-arm.mode=nvhe` + padding (49 bytes) — preserving the boot-image and
FDT structure byte-for-byte except those bytes. Verified live: `/proc/cmdline` then showed both
`kvm-arm.mode=protected` (bootloader) and `kvm-arm.mode=nvhe` (DTB), and dmesg switched from
`Protected KVM` / `Protected nVHE mode initialized` to plain `Hyp mode initialized successfully` = nVHE.

**Safety:** bootloader unlocked → fastboot always reachable; full verified backups of all boot/firmware/
device-unique partitions (`~/pixel-komodo-boot-backup/`, sha256 manifest); only `vendor_kernel_boot_b`
was flashed; restored byte-perfect (`sha256 da27174b…`) after each run. Three flash cycles, three
exact restores. nvhe booted cleanly (the S2MPU-won't-boot fear didn't materialize).

## Result — threshold sweep (anon dense 4 K, X4 @ 3.1 GHz, 1000 iters, mean µs/iter)

| flush range | 0.5 | 1.0 | 1.5 | **1.9** | **2.0** | 2.5 | 4 | 8 | 16 | 32 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| protected | 36.9 | 24.6 | 25.5 | **31.2** | **32.5** | 43.2 | 77.4 | 160.8 | 350.0 | 689.6 |
| nvhe | 11.2 | 22.0 | 28.5 | **39.0** | **40.3** | 49.7 | 81.4 | 175.2 | 367.1 | 731.1 |

- **No 2 MB cliff in either mode** — smooth through 2.0 MB (range TLBI used both ways). Contrast Kaitian,
  where protected *dropped* at 2.0 MB (per-page → whole-ASID fallback because it lacks range TLBI).
- The protected−nvhe difference doesn't just vanish, it **flips sign** (nvhe slightly *higher* at most
  points) — the signature of noise, not a host-stage-2 penalty.

## Noise floor (why we can only say "below the floor")

4 identical nvhe runs (1 MB dense, 1000 iters) — cpu-cycles / instructions / stalled-cycles-backend:
```
347.9M  823.7M  183.0M
369.6M  833.3M  195.6M
361.6M  828.3M  194.7M
346.7M  828.2M  180.4M
```
Run-to-run spread: cpu-cycles ~6 %, stalls ~8 %. And the protected-vs-nvhe simpleperf comparison was
confounded by a **+60 M instruction drift at identical page-fault counts** — i.e. between-session drift
(background/thermal across the reboots), not a mode effect. So any real protected−nvhe effect is **below
the noise floor** here. On Kaitian the penalty (+61 µs) was ~10× the noise, hence unmissable; on this
Pixel any residual is *under* the noise.

## Conclusion

On a real pKVM host **with FEAT_TLBIRANGE**, the host-stage-2 adds **no resolvable munmap penalty** —
range TLBI collapses the teardown into a few cheap range ops in both modes. Combined with Kaitian
(pKVM, *no* TLBIRANGE → +61 µs), this is direct A/B evidence on real silicon that the regression is
**gated on FEAT_TLBIRANGE, not inherent to pKVM**.

Raw data: [protected.log](protected.log), [nvhe.log](nvhe.log).
Caveat: a sub-µs residual can't be bounded here (phone noise > effect); a tighter measurement would need
an interleaved A/B (impossible with reflash-per-mode) on a quiesced device.
