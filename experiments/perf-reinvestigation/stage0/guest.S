/* Minimal arm64 KVM guest payload for the Stage-0 ':h' EL2 positive control.
 *
 * Loops storing to an unmapped IPA (0x40000000) so every store causes a stage-2
 * fault -> KVM_EXIT_MMIO. The host driver (kvm_el2_probe.c) re-enters KVM_RUN each
 * time, so each iteration is one EL2 world-switch round trip.
 *
 * Build: as guest.S -o guest.o && objcopy -O binary guest.o guest.bin   (16 bytes)
 */
.text
.global _start
_start:
    movz x1, #0x4000, lsl #16      // x1 = 0x40000000 (unmapped IPA -> MMIO)
    mov  w0, #0x42
1:  str  w0, [x1]                  // each store -> KVM_EXIT_MMIO
    b    1b
