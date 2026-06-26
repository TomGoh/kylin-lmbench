#include <stdio.h>
int main(void)
{
    unsigned long isar0;
    asm("mrs %0, ID_AA64ISAR0_EL1" : "=r"(isar0));
    unsigned long tlb = (isar0 >> 56) & 0xf;
    printf("ID_AA64ISAR0_EL1 = 0x%016lx\n", isar0);
    printf("TLB field [59:56] = %lu  (0=none, 1=TLBI-OS, 2=TLBI-OS+RANGE)\n", tlb);
    printf("FEAT_TLBIRANGE: %s\n", tlb >= 2 ? "YES (内核可用 RVAE1IS range TLBI)"
                                            : "NO (逐页 TLBI 或升级为 ASID flush)");
    return 0;
}
