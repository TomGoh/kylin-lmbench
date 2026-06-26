/* Stage-0 probe: read ID_AA64ISAR0_EL1 from EL0.
 *
 * !!! This does NOT reliably detect FEAT_TLBIRANGE. !!!
 * The TLB field [59:56] is FTR_HIDDEN in the kernel
 * (arch/arm64/kernel/cpufeature.c: ftr_id_aa64isar0[]), so the userspace-visible
 * MRS-emulated value masks it to 0 on EVERY core, whether or not the hardware
 * implements range TLBI. Confirmed false-negative on Qualcomm Oryon (SM8850),
 * which HAS FEAT_TLBIRANGE yet reads TLB=0 here (see results/android-sm8850/).
 *
 * Reliable alternatives:
 *   - behavioral (preferred, root-free): the 2 MB munmap "cliff" (op_sweep /
 *     munmap_only). NO cliff => range TLBI in use => FEAT_TLBIRANGE present;
 *     a sharp DROP at 2.0 MB => absent (kernel falls back to a whole-ASID flush
 *     at MAX_DVM_OPS because it has no range TLBI).
 *   - kernel cpucap (unmasked, reads at EL1): dmesg | grep -i
 *     "TLB range maintenance instructions"  (may be gone if log_buf wrapped).
 *
 * The other ID_AA64ISAR0 fields (RNDR, ATOMICS, crypto) ARE userspace-visible,
 * so the raw value is still informative for those.
 *
 * Build: gcc -O2 -o isar0 isar0.c ; run: ./isar0
 */
#include <stdio.h>
#include <stdint.h>

int main(void)
{
    uint64_t isar0;
    __asm__ volatile("mrs %0, ID_AA64ISAR0_EL1" : "=r"(isar0));
    unsigned tlb = (isar0 >> 56) & 0xf;

    printf("ID_AA64ISAR0_EL1 = 0x%016lx\n", (unsigned long)isar0);
    printf("  TLB[59:56] = %u  <-- FTR_HIDDEN: masked to 0 for EL0; this is NOT a\n", tlb);
    printf("                    valid FEAT_TLBIRANGE check. Use the 2 MB munmap-cliff\n");
    printf("                    test (op_sweep) or the kernel cpucap (dmesg) instead.\n");
    return 0;
}
