/* Stage-0 ':h' EL2 positive control: prove perf's cycles:h actually counts EL2.
 *
 * Creates a minimal KVM VM with one vcpu and a tiny guest (guest.bin) that loops on
 * an MMIO store, then issues KVM_RUN N times. Every KVM_RUN world-switches through the
 * pKVM EL2 hypervisor. Measure with:
 *
 *   taskset -c 0 perf stat -e cycles,cycles:u,cycles:k,cycles:h,instructions:h \
 *       ./kvm_el2_probe 100000
 *
 * Expected (Kaitian, kvm-arm.mode=protected): cycles:h >> 0 (vs 0 during sleep),
 * confirming EL2 self-counting is NOT zeroed by pKVM, so Stage 3 can attribute munmap
 * time to EL2 with stock perf and no hypervisor patch.
 *
 * Build: gcc -O2 -o kvm_el2_probe kvm_el2_probe.c    (needs guest.bin in cwd)
 */
#include <stdio.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <linux/kvm.h>

#define GSIZE 0x10000UL

int main(int argc, char **argv)
{
    long n = argc > 1 ? atol(argv[1]) : 200000;

    int kvm = open("/dev/kvm", O_RDWR);
    if (kvm < 0) { perror("open /dev/kvm"); return 1; }
    int vm = ioctl(kvm, KVM_CREATE_VM, 0);
    if (vm < 0) { perror("KVM_CREATE_VM"); return 1; }

    void *mem = mmap(0, GSIZE, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    memset(mem, 0, GSIZE);
    FILE *f = fopen("guest.bin", "rb");
    if (!f) { perror("guest.bin"); return 1; }
    size_t gl = fread(mem, 1, GSIZE, f);
    fclose(f);

    struct kvm_userspace_memory_region r = {0};
    r.slot = 0; r.guest_phys_addr = 0; r.memory_size = GSIZE; r.userspace_addr = (uint64_t)mem;
    if (ioctl(vm, KVM_SET_USER_MEMORY_REGION, &r) < 0) { perror("SET_MEM"); return 1; }

    int vcpu = ioctl(vm, KVM_CREATE_VCPU, 0);
    if (vcpu < 0) { perror("CREATE_VCPU"); return 1; }
    struct kvm_vcpu_init init;
    memset(&init, 0, sizeof init);
    if (ioctl(vm, KVM_ARM_PREFERRED_TARGET, &init) < 0) { perror("PREF_TARGET"); return 1; }
    if (ioctl(vcpu, KVM_ARM_VCPU_INIT, &init) < 0) { perror("VCPU_INIT"); return 1; }

    uint64_t pc = 0;
    struct kvm_one_reg reg;
    reg.id = KVM_REG_ARM64 | KVM_REG_SIZE_U64 | KVM_REG_ARM_CORE | KVM_REG_ARM_CORE_REG(regs.pc);
    reg.addr = (uint64_t)&pc;
    if (ioctl(vcpu, KVM_SET_ONE_REG, &reg) < 0) { perror("SET_PC"); return 1; }

    int ms = ioctl(kvm, KVM_GET_VCPU_MMAP_SIZE, 0);
    struct kvm_run *run = mmap(0, ms, PROT_READ | PROT_WRITE, MAP_SHARED, vcpu, 0);

    long mmio = 0;
    for (long i = 0; i < n; i++) {
        if (ioctl(vcpu, KVM_RUN, 0) < 0) { perror("KVM_RUN"); printf("at i=%ld\n", i); break; }
        if (run->exit_reason == KVM_EXIT_MMIO)
            mmio++;
        else { printf("unexpected exit_reason=%u at i=%ld\n", run->exit_reason, i); break; }
    }
    printf("guest=%zuB KVM_RUNs=%ld mmio_exits=%ld\n", gl, n, mmio);
    return 0;
}
