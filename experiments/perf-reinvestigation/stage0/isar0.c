/* Stage-0 probe: detect FEAT_TLBIRANGE from EL0.
 *
 * Reads ID_AA64ISAR0_EL1 via the kernel's MRS emulation (arm64 traps and emulates
 * EL0 reads of the sanitized ID registers) and decodes the TLB field [59:56]:
 *   0b0000 = no TLBIOS/TLBIRANGE   0b0001 = FEAT_TLBIOS only   0b0010 = +FEAT_TLBIRANGE
 *
 * Why it matters: with FEAT_TLBIRANGE the kernel coalesces teardown into a few range
 * TLBIs and the per-page-TLBI pKVM penalty largely vanishes. Absent -> the regression
 * can appear. Kaitian (FTC862): 0x0000111110212120, TLB=0 -> ABSENT (go).
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
    printf("  TLB[59:56] = %u => ", tlb);
    if (tlb >= 2)      printf("FEAT_TLBIRANGE PRESENT (range TLBI available)\n");
    else if (tlb == 1) printf("FEAT_TLBIOS only (no range TLBI)\n");
    else               printf("ABSENT (no TLBIOS/TLBIRANGE)\n");
    return 0;
}
