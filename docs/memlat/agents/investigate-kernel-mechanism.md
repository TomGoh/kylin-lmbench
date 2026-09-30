# 调查代理报告：kernel-mechanism

> 这是多代理调查阶段的原始报告，英文原文照录。它的结论在使用前还要经过独立核查，
> 核查结果见同目录下的 verify-*.md。

## Headline

Only kvm-arm.mode=protected puts the HOST under stage-2: the late_initcall finalize_pkvm -> __pkvm_prot_finalize sets HCR_EL2.VM and loads VTTBR (identity map, VMID 0) and VTCR on every CPU; nvhe (no VM bit, VTTBR=0), vhe and kvm-off are stage-1 only, and kvm-off and vhe are the same regime because mode=none and the unrecognised mode=vhe both leave the kernel at EL2/VHE. Host RAM is identity-mapped eagerly at EL2 init with the largest aligned blocks (40-bit IPA gives a 3-level table entered at level 1; a model of the N90-class memory map puts about 91% of RAM under 1 GiB blocks), and ordinary host accesses, task switches and timer ticks never enter EL2, so the only steady-state cost is the hardware two-stage walk per TLB miss (worst case 9 references instead of 4). The raw host CSVs match this: pkvm equals all three baselines up to 2 MB of random-order access and is a flat +6.5 to +8.1 ns (about 12-15 cycles at 1.9 GHz) from 8 to 64 MB, whereas the 8 MB sequential LLC-boundary row already differs by +6.8% between two stage-1-only baselines (vhe vs kvmoff), so its +3.55% cannot be attributed to stage-2. Two provenance points: the Rust EL2 (CONFIG_X1_RMS) was default n and in no arm64 defconfig in release 6.6.0-73.76 (enabled in 6.6.0-76.85, 2026-07-07), so the June runs most likely used the C pKVM EL2; and guest stage-2 leaf size (4 KiB vs 2 MiB) depends only on host backing through one shared pkvm_mem_abort path, so the pVM-only negative overhead in Figure 8 is not explained by hypervisor code.

## Findings

### kernel-mechanism#1 (DOCUMENTED, confidence high)

Q1 (protected): the host is switched to two-stage translation per CPU by the late_initcall finalize_pkvm -> pkvm_drop_host_privileges -> on_each_cpu(_kvm_host_prot_finalize) -> HVC __pkvm_prot_finalize. At EL2 this stores VTTBR (host pgd, VMID 0) and VTCR in the per-CPU kvm_init_params, ORs HCR_VM into params->hcr_el2, writes HCR_EL2, loads VTCR_EL2 and VTTBR_EL2 (__load_stage2) and issues TLBI VMALLS12E1. Before that (from kvm_arm_init at device_initcall_sync) the host stage-2 tables already exist but HCR_EL2.VM is 0 (initial params: HCR_HOST_NVHE_PROTECTED_FLAGS = RW,API,APK,ATA,TSC; vttbr=vtcr=0). The same values are re-installed after every guest exit and on CPU_ON/resume. C and Rust are equivalent step for step.

Evidence: arch/arm64/kvm/pkvm.c:473-492,496-529; arch/arm64/kvm/hyp/nvhe/mem_protect.c:447-484; arch/arm64/include/asm/kvm_mmu.h:313-341; arch/arm64/kvm/arm.c:2059-2065,2396-2416,2481-2528,2760,3004; arch/arm64/kvm/hyp/nvhe/setup.c:334-395,397-433; hyp-init.S:94-95,120-124; nvhe/switch.c:206,455; hyp/include/nvhe/mem_protect.h:98-104; kvm_arm.h:75,108-109. Rust: xhypervisor/src/mem_protect/host.rs:2160-2215,2435-2448; kvm_mmu.rs:151,200-208; setup.rs:206-257,685-772; hyp_main.rs:719-722; switch.rs:1488-1491,2700

### kernel-mechanism#2 (DOCUMENTED, confidence high)

Q1 (nvhe, vhe, kvm-off): stage-2 is off for the host. nvhe: host HCR_EL2 = HCR_HOST_NVHE_FLAGS (RW,API,APK,ATA; no VM), params vttbr=vtcr=0, and __load_host_stage2 writes 0 to VTTBR_EL2 because the kvm_protected_mode_initialized key is false. vhe: HCR_EL2 = HCR_HOST_VHE_FLAGS (RW,TGE,E2H), restored after each guest exit; guest VTTBR is loaded only at vcpu load. kvm-off: kvm_arm_init returns -ENODEV before any hyp init; early EL2 setup wrote VTTBR_EL2 = 0.

Evidence: kvm_arm.h:108-110; arm.c:2062,2065,2862-2865; mem_protect.h:98-104 (Rust host.rs:2435-2448); arch/arm64/kernel/hyp-stub.S:97-100; arch/arm64/kvm/hyp/vhe/switch.c:129,197-201; arch/arm64/include/asm/el2_setup.h:112-115; arch/arm64/kernel/head.S:298

### kernel-mechanism#3 (INFERRED, confidence high)

kvm-off and vhe are the SAME translation regime for host user code. kvm-arm.mode=none only sets KVM_MODE_NONE; the EL2/VHE decision is taken in __finalise_el2 from ID_AA64MMFR1_EL1.VH, which is overridden to 0 only by the aliases for mode=nvhe and mode=protected. kvm-arm.mode=vhe is not an accepted value (early_kvm_mode_cfg has no such branch and returns -EINVAL, which prints Malformed early option) and the kernel simply boots in its default VHE mode. So on the VHE-capable FTC862 both configurations run the kernel at EL2 with E2H,TGE and EL0 in the single-stage EL2&0 regime. This contradicts the internal docs, which say the kvm-off kernel runs at EL1.

Evidence: arm.c:2947-2983 (none at 2952-2955; no vhe branch; -EINVAL at 2981); arch/arm64/kernel/pi/idreg-override.c:241-242; hyp-stub.S:76-100; head.S:241,402; init/main.c:773. N90 boot lines: docs/n90-kvm-host/vhe.md:36-40 (VHE mode initialized successfully) and :61 (Malformed early option 'kvm-arm.mode'); kvmoff.md:39-40. D80F3 (same MIDR) boots VHE with no kvm-arm.mode at all and prints the VH override only for nvhe/protected: experiments/d3000-pkvm-apps/results/smoke/pair-vhe/vhe/anchors-start/rep-00/metadata/dmesg.txt:69,584 and metadata/mode-smoke-nvhe/dmesg.txt:65. Contradicted docs: docs/n90-kvm-host/kvmoff.md:4,48; README.md:17

### kernel-mechanism#4 (DOCUMENTED, confidence high)

Q2: host VTCR_EL2 is built by prepare_host_vtcr -> kvm_get_vtcr(mmfr0, mmfr1, phys_shift) with phys_shift = PARange of the sanitised ID_AA64MMFR0_EL1 (capped at 48 bits without LPA2): PS = PARange, T0SZ = 64 - phys_shift, levels = stage2_pgtable_levels(ipa) = (ipa - 8) / 9 (minimum 2), SL0 = 2 - (4 - levels), HA set (CONFIG_ARM64_HW_AFDBM=y), VS from VMID width. __kvm_pgtable_stage2_init derives start_level = 2 - SL0 and allocates kvm_pgd_pages() concatenated first-level pages. Block mappings are allowed from level 1 (1 GiB) with 4K pages.

Evidence: mem_protect.c:143-153 (Rust host.rs:415-431); arch/arm64/kvm/hyp/pgtable.c:587-638,65-81,1828-1854; kvm_arm.h:213-214,218-226; stage2_pgtable.h:14-24; pgtable-hwdef.h:26,41; cpufeature.h:837-856; kvm_pgtable.h:23-45,180-183

### kernel-mechanism#5 (MEASURED, confidence high)

Q2 computed geometry: IPA 40 bits -> T0SZ 24, 3 levels, SL0 1, start level 1, 2 concatenated level-1 pages (1024 entries of 1 GiB each). IPA 44 or 48 bits -> 4 levels, start level 0, one PGD page. Stage-2 descriptor reads to resolve one IPA: 40-bit: 1 (1 GiB block), 2 (2 MiB block), 3 (4 KiB page); 44/48-bit: 2, 3, 4. A full two-dimensional walk for a 4-level stage-1 without any caching is 4 references with stage-1 only, and 9 / 14 / 19 (40-bit IPA) or 14 / 19 / 24 (44 or 48-bit IPA) with stage-2 leaves of 1 GiB / 2 MiB / 4 KiB. The N90 host VTCR_EL2 value is 0x80223558 (8-bit VMID) or 0x802a3558 (16-bit VMID).

Evidence: scratch script s2_geometry.py re-implementing the macros cited above; output in s2_geometry.out

### kernel-mechanism#6 (DOCUMENTED, confidence high)

The N90 uses a 40-bit IPA: its boot log prints IPA Size Limit: 40 bits in nvhe, vhe and protected modes (kvm_ipa_limit comes straight from PARange), and the host stage-2 histogram measured on the sibling N80 sums to 268,405,614 pages, i.e. 2^28 pages = 1 TiB minus hyp-owned pages. Another FTC862 machine (Great Wall D80F3 desktop, other kernel) reports 48 bits, so the 4-level column of the geometry table is the right one for that machine, not for the N90.

Evidence: kylin-lmbench/docs/n90-kvm-host/pkvm.md:59, nvhe.md:38, vhe.md:38; arch/arm64/kvm/reset.c:250-290; docs/mmap/c1-host-stage2-granularity.zh-CN.md:170-174; experiments/d3000-pkvm-apps/metadata/mode-smoke-protected/dmesg.txt:581

### kernel-mechanism#7 (DOCUMENTED, confidence high)

Q3: host RAM is mapped EAGERLY. kvm_host_prepare_stage2 (called from __pkvm_init_finalise, before the host is deprivileged) runs prepopulate_host_stage2, which identity-maps every memblock region with default RWX protection through kvm_pgtable_stage2_map; the walker installs a 1 GiB block whenever the address is 1 GiB aligned and at least 1 GiB of the region remains, else a 2 MiB block, else 4 KiB pages. Host table flags are NOFWB | IDMAP | PREFAULT_BLOCK and the host VMID is 0. The Rust version additionally pre-maps the MMIO gaps and the rest of the IPA space (RW); the C version maps memory only and leaves MMIO to the lazy path.

Evidence: C: mem_protect.c:23-25,155-168,170-197 (VMID 0 at 194),603-608,670-674; pgtable.c:41-55,932-941,1204-1239. Rust: host.rs:375-411 (MMIO gap 386-393, memory 396, tail 405-409),503-547; consts.rs:96-98,155-157

### kernel-mechanism#8 (DOCUMENTED, confidence high)

Q3 lazy path and block choice: a host access to an IPA whose stage-2 entry is empty traps to EL2 (handle_host_mem_abort -> host_stage2_idmap), and host_stage2_adjust_range picks the largest granule (1 GiB, 2 MiB, 4 KiB) that is fully inside the memblock region or hole containing the address. force_pte (page granularity) is applied only when the requested protection differs from the default (host_stage2_force_pte). In the C build this path maps MMIO on first use and ranges dropped by host_stage2_unmap_unmoveable_regs (non-RAM only); RAM never needs it.

Evidence: C: mem_protect.c:486-519,616-627,635-668,725-742,762-779,835-871; pgtable.c:1402-1440. Rust: host.rs:253-301,485-488,1749-1820,1838-1869,1974-2035

### kernel-mechanism#9 (DOCUMENTED, confidence high)

Q3 what breaks host blocks: only ownership changes and non-default protections. kvm_pgtable_stage2_annotate always sets force_pte, so each page donated to the hypervisor or to a protected guest becomes a 4 KiB invalid entry carrying the owner id; the containing 1 GiB and 2 MiB blocks are split and the sibling entries are refilled as valid mappings one level down (PREFAULT_BLOCK), so the split itself causes no later faults. Sources of donation: boot-time fix_host_ownership (hyp pool, hyp image, per-CPU, stacks), __pkvm_host_donate_hyp (guest stage-2 table pages via the memcache, VM metadata, hyp allocator), __pkvm_host_donate_guest. Module protection changes and lazy_pte also force pages. SHARES do not touch host stage-2 at all: host page state lives in the hyp vmemmap (host_state), so share with hyp, with a non-protected guest or with FF-A only updates that array.

Evidence: pgtable.c:1241-1264 (force_pte at 1249),1027-1064,1066-1108; setup.c:209-244,283-301; mem_protect.c:689-718,971-984,1188-1216,1346-1372,1408-1483,1485-1515,1562-1578,1674-1706,1852-1890; nvhe/mm.c:544-567; memory.h:53-59. Rust: host.rs:752-816,996-1009,1302-1307,1395-1406,1429-1478,1579-1633,2284-2427,2476-2520; setup.rs:305-346,431-448; permissions.rs:659-714

### kernel-mechanism#10 (DOCUMENTED, confidence high)

Q3 what restores blocks: returning a page to the host (reclaim, hyp-to-host donation) re-installs the default mapping through kvm_pgtable_stage2_map, which replaces a fully covered table by a block on the way down (TABLE_PRE) and collapses a table left with only default entries on the way up (TABLE_POST, host_stage2_pte_is_counted ignores default entries). Coalescing is disabled before finalisation, and pin_host_tables takes an extra reference on every table that exists at the end of EL2 init, so regions split at boot stay split for the lifetime of the system.

Evidence: pgtable.c:1009-1025,1127-1176 (static key test at 1138),1187-1202; mem_protect.c:699-701,744-760,1374-1400,1920-1966; setup.c:260-281,378. Rust: host.rs:447-468,766-770,1887-1956; setup.rs:262-281,390-409,754

### kernel-mechanism#11 (MEASURED, confidence medium)

Model of the boot-time host stage-2 on an N90-class memory map (9 memblock regions, 32,704 MiB; layout taken from a same-core D80F3 because no N90 memory map is in the repo): the kvm_hyp_reserve formula gives 42,097 pages = 164.44 MiB, PMD-aligned 166 MiB, exactly the logged Reserved 166 MiB at 0x2775800000 on both machines, which also confirms the 4-byte struct hyp_page (ownership in vmemmap). After prepopulation and annotation of the 166 MiB hyp pool: 29 blocks of 1 GiB cover 90.8% of RAM, 2 MiB blocks 8.67% (the low 2 GiB, which is cut by memblock boundaries, plus the GiB holding the pool), valid 4 KiB pages 0.02%, hyp-owned 0.51%. If 8 further small hyp-owned allocations each landed in a different untouched GiB (worst case) the split is 65.8% / 33.7% / 0.07%. The RAM regions use only 32 level-1 entries (5 cache lines of the 8 KiB level-1 table).

Evidence: scratch script host_s2_sim.py (output host_s2_sim.out) implementing pkvm.c:150-200, kvm_pkvm.h:288-409, mem_protect.c:155-168, pgtable.c:41-55,1027-1064,1241-1264; inputs: experiments/d3000-pkvm-apps/metadata/mode-smoke-protected/dmesg.txt:28,37-45 and docs/n90-kvm-host/pkvm.md:55

### kernel-mechanism#12 (DOCUMENTED, confidence high)

A direct EL2 read-out exists only for the sibling N80 running a different kernel with the Rust hypervisor (6.6.30xcore-stat+): 1019 blocks of 1 GiB (99.52% of the mapped 1 TiB), 2486 blocks of 2 MiB, 8046 pages of 4 KiB. It agrees with the code reading (large blocks, 5 GiB regions split) but is not a measurement of the N90 kernel used for the paper.

Evidence: kylin-lmbench/docs/mmap/c1-host-stage2-granularity.zh-CN.md:3,27-38,167-182

### kernel-mechanism#13 (DOCUMENTED, confidence high)

Q3 steady state: an ordinary host memory access never enters EL2. RAM is valid in stage-2 before HCR_EL2.VM is set, so not even a first touch traps; page faults, mmap and munmap of the host change only stage-1. The EL2 host vector handles only synchronous exceptions (HVC, SMC, FP/SVE/SME trap, stage-2 instruction or data abort); IRQ, FIQ and SError slots for the lower EL are invalid (host interrupts are taken at EL1 because IMO/FMO/AMO are clear). An EL2 cycle counter on the N80 measured zero EL2 cycles for page-touch and munmap workloads. The internal statements that pKVM must update host stage-2 when the host creates a new VA range, and that the identity map is built on first host access, are not what the code does for RAM.

Evidence: hyp-main.c:1635-1691 (tag 6.6.0-73.76: 1645-1672); host.S:221-234,285-305 (tag: 171-184,235-255); Rust hyp_main.rs:3232-3275; kvm_arm.h:70-72,108-109; docs/mmap/n80-gate-c0-results.zh-CN.md:20,66. Statements corrected: docs/n90-kvm-host/pkvm.md:190-191, SUMMARY.md:179-180, llc-boundary-8mb-analysis.md:111

### kernel-mechanism#14 (DOCUMENTED, confidence high)

Q4: there is no per-access and no per-context-switch software cost in protected mode. Host HCR_EL2 has no TVM, TTLB, IMO or FMO, so TTBR/ASID writes, TLBI instructions and interrupts stay at EL1; the host VMID is the constant 0 and VTTBR_EL2 is written only by finalize, guest entry/exit and the EL2 TLB helper; mm/context.c, __switch_to and entry-common.c contain no KVM, HVC or SMCCC call; the arch timer PPI selection is the same for nvhe and protected (EL1 physical timer).

Evidence: kvm_arm.h:22-23,49-50,70-72,108-109; mem_protect.c:194; kvm_mmu.h:313-341; nvhe/tlb.c:19-142; nvhe/pkvm.c:677; grep of arch/arm64/mm/context.c, arch/arm64/kernel/process.c (__switch_to) and entry-common.c returned no kvm/hvc/smccc/vttbr match; arch/arm64/include/asm/tlbflush.h:32-50; drivers/clocksource/arm_arch_timer.c:1400-1412; el2_setup.h:51-58; experiments/d3000-pkvm-apps/metadata/mode-smoke-protected/dmesg.txt:105

### kernel-mechanism#15 (DOCUMENTED, confidence high)

Q4: everything that differs between protected and nvhe on the host path: (1) HCR_EL2.VM=1 with the host VTTBR/VTCR, i.e. hardware two-stage walks and combined TLB entries tagged VMID 0; (2) HCR_EL2.TSC, so host SMCs (PSCI, SDEI, TRNG, FF-A) trap to EL2 and are relayed; (3) a 166 MiB hypervisor pool is taken from the top of RAM by memblock before the buddy allocator starts, plus other hyp-owned pages, which changes which physical pages the host allocator hands out; (4) any change of host stage-2 (donation, reclaim) flushes IPAS2E1IS plus VMALLE1IS, i.e. the whole host TLB on all CPUs, but this happens only when VMs or hyp allocations are active; (5) a pKVM shrinker makes a hypercall when the MM shrinker runs. At HEAD (not in the June kernel) every EL2 entry also masks and unmasks SDEI with two SMCs. None of 2 to 5 occurs inside a pinned user-space read loop.

Evidence: arm.c:2059-2065,2467-2475,2514-2524; hyp-main.c:1635-1662; pkvm.c:150-200; arch/arm64/mm/init.c:342; nvhe/tlb.c:148-176,208-233; pgtable.c:802-840; host.S:42-62,83-98 (absent at tag: 0 SDEI matches in the 6.6.0-73.76 host.S). Rust: tlb.rs:290-315,550-555

### kernel-mechanism#16 (MEASURED, confidence high)

Host raw data, random page order (stride 16), medians of 10 iterations, pkvm minus the median of the three stage-1-only modes: within -0.12 to +0.15 ns for 0.75 to 2 MB (192 to 512 pages), then +0.71 ns (3 MB), +1.73 (4 MB), +5.24 (6 MB), +7.05 (8 MB), +7.03 (12), +7.73 (16), +8.12 (24), +7.88 (32), +6.90 (48), +6.50 ns (64 MB). The three baselines agree with each other within 0.3 ns up to 12 MB. The plateau is 12 to 15 CPU cycles at 1.9 GHz per load and turns into +6.3% at 8 MB and +3.5% at 64 MB only because the base latency grows from 112.5 to 185.2 ns. Means at 64 MB: kvmoff 182.21, vhe 181.21, nvhe 181.10, pkvm 188.13 ns, i.e. +3.25% / +3.82% / +3.88%, reproducing Figure 7.

Evidence: scratch scripts delta_profile.py and quick_host_check.py over kylin-lmbench/results/n90-day3-host/n90-{kvmoff,nvhe,vhe}-noLSM-full-cpu0.csv and n90-pkvm-noLSM-try2-cpu0.csv (bench lat_mem_rd_rand, variant stride16_sz*); outputs delta_profile.out, quick_host_check.out

### kernel-mechanism#17 (MEASURED, confidence high)

Host raw data, sequential stride 256: pkvm minus baseline is within 0.1 ns up to 6 MB; at 8 MB (the LLC-boundary row) it is +0.71 ns by median but the three stage-1-only baselines themselves spread over 1.63 ns (kvmoff 10.82, nvhe 11.41, vhe 12.45); at 12 to 64 MB it is -0.12 to +0.27 ns with baseline spreads of 0.33 to 0.81 ns. By means, the 8 MB row gives pkvm/kvmoff +3.55%, pkvm/vhe -3.02%, pkvm/nvhe +2.87%, and vhe/kvmoff +6.77% although vhe and kvmoff are the same translation regime; by medians pkvm/kvmoff is +12.09% and vhe/kvmoff +15.09%. The 64 MB row gives pkvm/kvmoff +0.29% and vhe/kvmoff +3.88%.

Evidence: same scripts and CSVs (bench lat_mem_rd_load, variants stride256_sz8.00000MB and stride256_sz64.00000MB and the full size sweep)

### kernel-mechanism#18 (INFERRED, confidence medium)

Root-cause reading of the two reviewer numbers. The 64 MB random +3.25% is the stage-2 cost: with 4 KiB stage-1 pages the TLB entry size and therefore the number of TLB misses are the same in all four modes, but under pKVM every miss needs a nested walk; the overhead is zero while the working set fits the TLB (up to about 2 MB), ramps between 768 and 2048 pages (second-level TLB reach of the order of 1000 to 2000 entries) and then stays at a constant 6.5 to 8 ns per load, which is what a fixed extra walk cost of one to three cached descriptor reads per miss looks like; a software trap would cost hundreds of ns, not 13 cycles. The 8 MB sequential +3.55% is not a stage-2 effect: a stride-256 walk misses the TLB once per 16 loads, so stage-2 can add at most 7.05/16 = 0.44 ns (3.9%) if fully exposed, the 12 to 64 MB sequential rows show only about +0.1 ns on average, and at 8 MB two baselines with identical translation regimes differ by twice the pkvm effect.

Evidence: combination of the code findings above with delta_profile.out and quick_host_check.out; arithmetic 7.05 ns / 16 loads per 4 KiB page; mean of the six sequential deltas from 12 to 64 MB = +0.099 ns

### kernel-mechanism#19 (DOCUMENTED, confidence medium)

On the N80 (Rust hypervisor, other kernel) the counts of TLB walks were identical in nvhe and protected modes while backend stalls grew, and the extra cost of host munmap was traced to each host TLBI instruction being slower when stage-2 is enabled, not to more EL2 work. This matters for mmap/munmap/mprotect style rows, not for read-only pointer chasing, which executes no TLBI.

Evidence: kylin-lmbench/docs/mmap/n80-gate-c0-results.zh-CN.md:20-31; docs/mmap/c1-tlbi-threshold.zh-CN.md:5,21-25

### kernel-mechanism#20 (DOCUMENTED, confidence high)

Q5a regular KVM guest (nvhe or vhe host): user_mem_abort takes the pfn with gup (no pin kept), chooses the mapping size from the VMA (hugetlbfs: PUD or PMD if the memslot alignment allows) or from THP via transparent_hugepage_adjust (PMD only, based on the size of the VMM stage-1 mapping of the hva), forces 4 KiB when dirty logging is active, and calls kvm_pgtable_stage2_map(pgt, fault_ipa, vma_pagesize, ...). Result: 4 KiB host backing gives 4 KiB stage-2 pages, 2 MiB THP gives 2 MiB blocks, 1 GiB hugetlbfs can give 1 GiB blocks. Mappings can be removed or aged later through MMU notifiers.

Evidence: arch/arm64/kvm/mmu.c HEAD:1426-1484,1495-1545,1547-1576,1911-2155 (1974-1977,1980-2001,2073-2080,2131-2138),2321-2364,976-979; same code at tag 6.6.0-73.76 lines 1887-2131 (2053,2111)

### kernel-mechanism#21 (DOCUMENTED, confidence high)

Q5b/c guests under pKVM (both non-protected and protected): every stage-2 translation fault goes to pkvm_mem_abort. It tops up the per-vCPU memcache, pins exactly one page with pin_user_pages (at the measurement tag FOLL_LONGTERM for all VMs; at HEAD only for protected VMs), requires a swap-backed folio (anon or shmem) for protected VMs, sets the size to PMD_SIZE when the VMM maps the hva with a PMD-level leaf and the memslot alignment allows (tag: transparent_hugepage_adjust; HEAD: get_user_mapping_size) and otherwise PAGE_SIZE, then issues the hypercall __pkvm_host_map_guest(pfn, gfn, nr_pages, R) and records a kvm_pinned_page with its order. At EL2 the handler refills the memcache (donating page-table pages from host to hyp) and calls __pkvm_host_donate_guest for a protected vCPU or __pkvm_host_share_guest otherwise.

Evidence: mmu.c HEAD:1620-1634,1697-1848 (flags 1705-1714, pin 1741, swap-backed 1752-1771, size 1779-1791, hypercall 1820-1821),2303-2307; tag 6.6.0-73.76: 1697-1824 (1705,1734,1745,1766-1768,1796),2279-2280; hyp-main.c:142-149,1068-1095 (tag 1067); Rust hyp_main.rs:1044-1085

### kernel-mechanism#22 (DOCUMENTED, confidence high)

Q5 at EL2: donation (protected VM) invalidates the host stage-2 entries page by page with owner = guest and maps the range in the guest table as RWX, state OWNED; sharing (non-protected VM) leaves host stage-2 untouched (vmemmap state SHARED_OWNED) and maps the range read-only as SHARED_BORROWED, a later write fault being resolved by pkvm_relax_perms -> __pkvm_host_relax_guest_perms without changing the granule. In both cases the guest mapping is one kvm_pgtable_stage2_map call over nr_pages and guest_stage2_force_pte_cb returns false, so 512 aligned pages become one 2 MiB block and a single page a 4 KiB entry; EL2 accepts only order 0 or PMD order. Leaf size therefore depends only on host backing: 4 KiB backing gives 4 KiB leaves, PMD-mapped THP gives 2 MiB blocks, identically for protected and non-protected guests, and identically in C and Rust (both call the C pgtable.c).

Evidence: mem_protect.c:199-203,332-368,1674-1706,1708-1727,1779-1803,1852-1890; mmu.c:1659-1695,2112-2119. Rust: mem_protect/guest.rs:487-489,516-575,1111-1130,1165-1227; permissions.rs:659-714; host.rs:1579-1633

### kernel-mechanism#23 (DOCUMENTED, confidence high)

Q5 other details: prefault ranges exist in two forms. KVM_PGTABLE_S2_PREFAULT_BLOCK is set on pKVM guest tables as well as on the host table, so a split block is refilled. A protected guest that issues MEM_SHARE for a range not yet mapped makes EL2 post a KVM_HYP_REQ_TYPE_MAP request, which the host serves with pkvm_mem_abort_range (loop of pkvm_mem_abort over the range). Under pKVM, MMU-notifier unmapping was disabled for all guests at the measurement tag (kvm_unmap_gfn_range returns false when protected mode is enabled) and aging is always disabled, so after first touch a pKVM guest takes no further stage-2 faults; at HEAD non-protected guests can be unshared again.

Evidence: mem_protect.c:358-360; pgtable.c:1092-1093; nvhe/pkvm.c:1303-1369; arch/arm64/kvm/handle_exit.c:378-382; mmu.c HEAD:1850-1909,2321-2364; tag mmu.c:1826-1885,2297-2307,2309-2325

### kernel-mechanism#24 (MEASURED, confidence high)

Guest stage-2 geometry: in protected mode kvm_init_stage2_mmu forces phys_shift = kvm_ipa_limit for every VM (40 bits on the N90); otherwise the VMM-requested size or the default KVM_PHYS_SHIFT = 40 is used. On the N90 every guest therefore has the same 3-level stage-2 entered at level 1 as the host map. A guest TLB miss with a 4-level guest stage-1 costs at worst 19 references with 4 KiB stage-2 leaves and 14 with 2 MiB blocks (15 and 11 for a 3-level guest stage-1).

Evidence: mmu.c:1011-1040 (1022-1024); kvm_mmu.h:157; nvhe/pkvm.c:677; computed in s2_geometry.py (section guest two-stage walk)

### kernel-mechanism#25 (INFERRED, confidence medium)

For Figure 8: nothing in the hypervisor gives a protected VM larger stage-2 mappings or cheaper walks than a non-protected VM or a regular KVM guest with the same host backing; the mapping policy is shared. A 20 to 30% lower random-access latency of the pVM series from about 3 MB upward (exactly where TLB misses start) would need a difference outside the protection mechanism, e.g. 2 MiB host backing in that run only (the distro default for anon THP is always and the host THP state of the guest runs was not recorded), a different guest-kernel stage-1 page size, or a different data set (the pVM directory carries the ENV_TAG of the non-protected run).

Evidence: code paths above; mm/Kconfig:890-892 (THP sysfs default always) with CONFIG_TRANSPARENT_HUGEPAGE=y in arch/arm64/configs/generic_defconfig:187 and kylinos_generic_defconfig:230; kylin-lmbench/docs/vm-lmbench-methodology.zh-CN.md:35,195,349; results/xkernel-n90-pkvm-pvm-20260605-163040/started.txt

### kernel-mechanism#26 (DOCUMENTED, confidence high)

Commit history with dates (klad-v11-stable): the Android pKVM series (334 commits touching arch/arm64/kvm, including THP support for pKVM guests, range mapping, pkvm_mem_abort_range, block prefault, vmemmap ownership tracking, no MMIO prepopulation) was committed 2026-04-24 and first shipped in 6.6.0-66.66; the Rust EL2 source (KYLIN: pKVM: Integrate with X Core, 2dd9455c9aabd) was committed 2026-05-15 and is in tag 6.6.0-73.76 of the same day; CONFIG_RUST was enabled in the arm64 kylinos config on 2026-06-02 (release 6.6.0-75.78); CONFIG_X1_RMS=y and the rename of hyp/nvhe/rust to hyp/xhypervisor were committed 2026-07-07 (release 6.6.0-76.85); SDEI masking on the EL2 entry path arrived 2026-09-02 (6.6.0-79.93); removal of transparent_hugepage_adjust from pkvm_mem_abort, FOLL_LONGTERM only for protected VMs and notifier unmapping for non-protected VMs arrived 2026-09-25 (6.6.0-79.98). Between the tag and HEAD, mem_protect.c, pgtable.c, setup.c, tlb.c, switch.c, hyp-init.S, reset.c and the Rust mem_protect/*.rs, setup.rs, tlb.rs, switch.rs are byte-identical.

Evidence: git log (read-only) with author and commit dates; debian.master/changelog:13,17,3585,3596-3597,4435,4442,5755,5771,5850,5952; git diff --quiet 6.6.0-73.76 HEAD per file and md5 comparison of the Rust sources against the tag path arch/arm64/kvm/hyp/nvhe/rust/src

### kernel-mechanism#27 (INFERRED, confidence medium)

The kernel used for the measurements (uname 6.6.0-73-generic, runs of 2026-06-03 to 06-06) corresponds to release 6.6.0-73.76. In that source CONFIG_X1_RMS is default n, no arm64 defconfig sets it (generic_defconfig, the KBUILD default and the file the packaging uses for the generic flavour, still does not at HEAD), and the nvhe Makefile then links the C objects (mem_protect.o, setup.o, hyp-main.o, ...) instead of the Rust object. Unless the N90 image was built with a private config, the pkvm numbers behind Figures 7 and 8 were produced by the C pKVM EL2, not by the Rust re-implementation. For the memory path this does not change the explanation: the page-table code (hyp/pgtable.c) is C in both builds and the Rust host.rs drives it with the same arguments.

Evidence: kylin-lmbench/results/n90-day3-host/*-summary.txt (kernel=6.6.0-73-generic, started 2026-06-03/04); git show 6.6.0-73.76:arch/arm64/kvm/Kconfig lines 76-79; grep X1_RMS in the tag's generic_defconfig and kylinos_generic_defconfig (no match); commit b1b2979f0c0bf (message: enable ... in place of the upstream C EL2 implementation); arch/arm64/kvm/hyp/nvhe/Makefile:6-8,11-18,36-39; Makefile:713; debian/rules.d/2-binary-arch.mk:23; debian.master/rules.d/arm64.mk:5

### kernel-mechanism#28 (DOCUMENTED, confidence high)

C versus Rust differences found in the host memory path: (1) Rust prepopulate also maps MMIO gaps and the IPA tail, C maps RAM only; (2) Rust handle_host_mem_abort always tries host_stage2_idmap first and then runs the permission-fault handlers, C switches on the fault type; (3) Rust ORs the FAR page offset into the fault address, C uses the page-aligned IPA; (4) Rust keeps the older PkvmMemTransition (do_share / do_donate) framework while C uses the direct functions, with the same resulting page-table calls; (5) Rust marks IOMMU-mapped MMIO pages through PTE software bits (forces 4 KiB), C only refcounts, and the Rust iommu module is not compiled. Flags, VMID, VTCR computation, finalize sequence, block selection, annotation, coalescing and the guest map calls are the same; pgtable.c, hyp-init.S, host.S and the vGIC code are shared C/asm objects in both builds.

Evidence: host.rs:375-411,914-948,982-1070,1974-2035 versus mem_protect.c:155-168,835-871,1597-1672; xhypervisor/src/lib.rs:28; nvhe/Makefile:6-8

## Caveats

- Source reading cannot tell how the FTC862 page-table walker caches stage-2 results (walk cache, IPA-to-PA cache, second-level TLB size are undocumented). The worst-case reference counts are architectural; attributing the measured 12 to 15 cycles per TLB miss to a specific number of extra descriptor reads is inference.
- The N90 memory map is not in the repos. The stage-2 model uses the memblock layout of a Great Wall D80F3 with the same cores and memory size; the match of the computed and logged hypervisor reservation (166 MiB at 0x2775800000 on both machines) supports but does not prove that the layouts are equal. Physical positions of hyp-owned pages outside the pool (hyp image sections, per-CPU areas, stacks) are unknown, hence the two scenarios.
- Which EL2 implementation was in the 6.6.0-73-generic binary on the N90 cannot be verified offline. The git and packaging history say the in-tree configs built the C implementation at that release; the internal docs assume the Rust runtime without evidence.
- Line numbers are for klinux HEAD 2c6aff8a0ae7c. mem_protect.c, pgtable.c, setup.c, tlb.c, switch.c, hyp-init.S, reset.c and the Rust mem_protect, setup, tlb and switch sources are byte-identical at tag 6.6.0-73.76 (Rust path there: arch/arm64/kvm/hyp/nvhe/rust/src). arm.c, mmu.c, hyp-main.c, host.S and pkvm.c differ; tag line numbers are given where they matter and the tag copies are under the scratch directory tag73/.
- The N80 documents cited (stage-2 histogram, EL2 cycle gate, TLBI cost) come from a different machine and a different kernel tree (6.6.30xcore-stat+ with the Rust hypervisor) and are used only as corroboration.
- The guest kernel (x-kernel) is not in the klinux tree, so its stage-1 page size and number of levels are unknown; host THP state and crosvm memory options during the four guest runs were not recorded.
- The statement that EL0 under HCR_EL2.TGE=1 is single-stage and that a combined TLB entry has the smaller of the stage-1 and stage-2 sizes is Arm architecture knowledge, not something a repo file states.
- The small positive deltas at 0.375 and 0.5 MB in the random test (about +0.4 and +0.6 ns) sit at the 512 KiB L2-cache boundary where the baselines themselves spread by 0.45 ns; I did not analyse them further.
- The benchmark repo received a new commit from another session while I was working (e107eab8, docs/n90-kvm-host/llc-boundary-8mb-analysis.md). I did not modify either repository. That document's statement that the host identity map is built on first access is not what the code does for RAM.
- The hugetlbfs entry for protected guests in Table 2 (-EIO) rests on my reading that hugetlb folios are not swap-backed; I did not trace that flag through the hugetlb code.

## Open questions

- Which EL2 implementation was in the N90's 6.6.0-73-generic image in June: check CONFIG_X1_RMS in that kernel's config (boot config or the ostree deployment). If it is not set, Figures 7 and 8 were measured on the C pKVM EL2 and the paper text should say so or be re-measured on a release from 6.6.0-76.85 on.
- Confirm on the device that the kvm-off kernel runs at EL2 (VHE), as the source says: arch_timer interrupt in /proc/interrupts (hyp PPI versus phys), or absence of the boot line SYS_ID_AA64MMFR1_EL1[11:8]: forced to 0.
- FTC862 second-level TLB size and walk-cache behaviour under stage-2: does l2d_tlb_refill per load match between protected and nvhe (only the cost per miss changes), and how many extra descriptor reads make up the 12 to 15 cycles?
- Why does the sequential stride-256 walk expose only about 0.1 to 0.27 ns instead of the 0.44 ns upper bound (translation prefetch for the next page, overlap with the cache miss)?
- What is the real host stage-2 block histogram on the N90 at benchmark time (klinux has no stage-2 dump interface; the N80 read-out needed an extra hypercall), and in which GiB regions do the benchmark's pages and page-table pages lie?
- For Figure 8: host transparent_hugepage enabled and shmem_enabled settings, crosvm memory options (hugepages, memfd versus anonymous) and the x-kernel stage-1 page size for each of the four guest runs; is the pVM data set really a protected-VM run given its ENV_TAG xkernel-pkvm-np?
- Does the host stage-2 fragmentation caused by a running protected guest (per-page invalidation of donated pages, split of the surrounding 1 GiB and 2 MiB blocks) measurably slow the host while guests run? Not covered by the host-only runs.

## Tables

### Table 1. Translation regime of a HOST user process in each mode (Q6, host side)

| mode | how the cmdline is handled | host kernel EL | HCR_EL2 while the host runs | VTTBR_EL2 / VTCR_EL2 | regime of host EL0 | stage-1 | stage-2 | memory references per data-TLB miss: worst case / with warm stage-1 walk cache |
|---|---|---|---|---|---|---|---|---|
| kvmoff | `kvm-arm.mode=none` sets KVM_MODE_NONE only; VH is not overridden, kernel stays at EL2 (VHE), KVM never initialised | EL2 | RW, TGE, E2H | 0 | EL2&0, single stage | 48-bit VA, 4 levels, 4 KiB leaves (THP=never) | none | 4 / 1 |
| vhe | `kvm-arm.mode=vhe` is rejected (-EINVAL, "Malformed early option"); default VHE boot with KVM | EL2 | RW, TGE, E2H | guest tables only while a vCPU is loaded | EL2&0, single stage | same | none | 4 / 1 |
| nvhe | alias forces id_aa64mmfr1.vh=0 | EL1 | RW, API, APK, ATA (VM=0) | 0 | EL1&0, stage-2 disabled | same | none | 4 / 1 |
| pkvm (protected) | alias forces vh=0, KVM_MODE_PROTECTED | EL1 | RW, API, APK, ATA, TSC, plus VM after finalize | host identity map, VMID 0; VTCR T0SZ=24, SL0=1, PS=40 bit | EL1&0, two stages | same (owned by the host kernel) | IPA=PA identity map, 40-bit, 3 levels entered at level 1 (2 concatenated tables); leaves 1 GiB / 2 MiB / 4 KiB; TLB entry size = min(S1,S2) = 4 KiB | 1 GiB leaf: 9 / 2; 2 MiB leaf: 14 / 3; 4 KiB leaf: 19 / 4 |

### Table 2. GUEST user process: stage-2 mapping per mode (Q5, Q6 guest side)

| host mode | VM type | fault path | ownership and pinning | stage-2 geometry on N90 | leaf if host backs with 4 KiB pages | leaf if host backs with 2 MiB THP (PMD-mapped in the VMM) | hugetlbfs | worst-case references per guest TLB miss (4-level guest S1) |
|---|---|---|---|---|---|---|---|---|
| vhe or nvhe | regular KVM | user_mem_abort -> kvm_pgtable_stage2_map | none kept; MMU notifiers may unmap or age | IPA from VMM, default 40 bit: 3 levels from level 1 | 4 KiB page | 2 MiB block | 2 MiB -> 2 MiB block; 1 GiB -> 1 GiB block | 19 (4 KiB) / 14 (2 MiB) / 9 (1 GiB) |
| pkvm | non-protected | pkvm_mem_abort -> HVC __pkvm_host_map_guest -> __pkvm_host_share_guest (R first; write fault -> pkvm_relax_perms) | one page pinned per fault (long-term at the June tag); host stays owner, host stage-2 untouched | IPA = kvm_ipa_limit = 40 bit | 4 KiB page | 2 MiB block | capped at 2 MiB | 19 / 14 |
| pkvm | protected | pkvm_mem_abort -> HVC __pkvm_host_map_guest -> __pkvm_host_donate_guest (RWX, OWNED) | long-term pin; page donated; host stage-2 entry invalidated per 4 KiB page | same | 4 KiB page | 2 MiB block (anon or shmem THP only) | rejected, -EIO (not swap-backed; inferred for hugetlb folios) | 19 / 14 |

The guest stage-1 (page size, number of levels) is set by the guest kernel (x-kernel) and is not in the klinux tree.

### Table 3. Stage-2 geometry versus IPA size (computed from kvm_get_vtcr and __kvm_pgtable_stage2_init)

| PARange | IPA bits | T0SZ | levels | SL0 | start level | concatenated PGD pages | PGD entries | one PGD entry covers |
|---|---|---|---|---|---|---|---|---|
| 0b0001 | 36 | 28 | 3 | 1 | 1 | 1 | 512 | 1 GiB |
| 0b0010 (N90, N80) | 40 | 24 | 3 | 1 | 1 | 2 | 1024 | 1 GiB |
| 0b0011 | 42 | 22 | 3 | 1 | 1 | 8 | 4096 | 1 GiB |
| 0b0100 | 44 | 20 | 4 | 2 | 0 | 1 | 512 | 512 GiB |
| 0b0101 (D80F3 log) | 48 | 16 | 4 | 2 | 0 | 1 | 512 | 512 GiB |

### Table 4. Hardware walk cost (computed)

Stage-2 descriptor reads to resolve one IPA:

| IPA bits | start level | 1 GiB block | 2 MiB block | 4 KiB page |
|---|---|---|---|---|
| 40 | 1 | 1 | 2 | 3 |
| 42 | 1 | 1 | 2 | 3 |
| 44 | 0 | 2 | 3 | 4 |
| 48 | 0 | 2 | 3 | 4 |

Full two-dimensional walk, 4-level stage-1, no TLB or walk-cache help (each of the 4 stage-1 table addresses and the final output address needs its own stage-2 walk):

| regime | S2 leaf for table pages and data page | memory references per TLB miss | extra vs stage-1 only |
|---|---|---|---|
| stage-1 only (kvmoff, vhe, nvhe host) | - | 4 | 0 |
| two-stage, IPA 40 | 1 GiB | 9 | 5 |
| two-stage, IPA 40 | 2 MiB | 14 | 10 |
| two-stage, IPA 40 | 4 KiB | 19 | 15 |
| two-stage, IPA 44 or 48 | 1 GiB | 14 | 10 |
| two-stage, IPA 44 or 48 | 2 MiB | 19 | 15 |
| two-stage, IPA 44 or 48 | 4 KiB | 24 | 20 |

Guest, 40-bit IPA stage-2: 3-level guest S1: 15 (4 KiB) / 11 (2 MiB) / 7 (1 GiB); 4-level guest S1: 19 / 14 / 9.

### Table 5. What builds, breaks and restores host stage-2 mappings

| event | effect on host stage-2 | C (arch/arm64/kvm/hyp/nvhe, hyp/pgtable.c) | Rust (arch/arm64/kvm/hyp/xhypervisor/src) |
|---|---|---|---|
| EL2 init: prepopulate | every memblock region identity-mapped RWX with the largest aligned blocks; Rust also maps MMIO gaps and the IPA tail (RW) | mem_protect.c:155-168, 170-197 | mem_protect/host.rs:375-411, 503-547 |
| EL2 init: fix_host_ownership | each hyp-owned 4 KiB page becomes an invalid entry with owner HYP; the 1 GiB and 2 MiB blocks around it are split, siblings refilled | setup.c:209-244, 283-301; pgtable.c:1241-1264, 1027-1064 | setup.rs:305-346, 431-448 |
| EL2 init: pin_host_tables | all tables existing at that time get an extra reference, never coalesced later | setup.c:260-281 | setup.rs:262-281, 390-409 |
| host to hyp donation (memcache pages for guest tables, VM metadata, hyp allocator) | per-page annotation, block split | mem_protect.c:1346-1372; mm.c:544-567 | host.rs:1429-1478 |
| host to protected-guest donation | per-page annotation owner GUEST (512 entries for a 2 MiB donation) | mem_protect.c:1852-1890 | host.rs:1579-1633, 996-1009 |
| share with hyp, non-protected guest, FF-A | no page-table change; hyp_vmemmap host_state only | mem_protect.c:971-984, 1188-1216, 1674-1706, 1562-1578 | host.rs:1395-1406, 1302-1307; permissions.rs:659-714 |
| module protection change, lazy_pte | non-default prot, force_pte, 4 KiB | mem_protect.c:725-742, 1408-1483, 1485-1515 | host.rs:485-488, 2284-2427, 2476-2520 |
| page returned to host | default mapping re-installed; covered table replaced by block (TABLE_PRE); table with only default entries collapsed (TABLE_POST) unless pinned at init | mem_protect.c:699-701, 1374-1400, 1920-1966; pgtable.c:1009-1025, 1127-1176 | host.rs:766-770, 1887-1956 |
| host access to an empty entry | stage-2 abort, EL2 maps the largest granule inside the memblock region or hole (MMIO in the C build) | mem_protect.c:635-668, 762-779, 835-871 | host.rs:1749-1820, 1838-1869, 1974-2035 |
| stage-2 pool exhausted | non-RAM leaf tables dropped and re-faulted; RAM untouched | mem_protect.c:486-519, 616-627; pgtable.c:1402-1440 | host.rs:253-301, 879-899 |

### Table 6. Model of the boot-time host stage-2 on an N90-class memory map (host_s2_sim.py)

Input: 9 memblock regions, 32,704 MiB (layout from the D80F3 dmesg), hyp pool 166 MiB at 0x2775800000. kvm_hyp_reserve computed: hyp_s1 16,939 + host_s2 16,955 + vm_table 1 + vmemmap 8,183 + ffa 19 = 42,097 pages = 164.44 MiB, PMD-aligned 166 MiB (logged: 166 MiB).

| scenario | build | 1 GiB blocks | 2 MiB blocks | 4 KiB pages | invalid owner entries | level-2 tables | level-3 tables | RAM under 1 GiB | RAM under 2 MiB | RAM under 4 KiB | hyp-owned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pool only | C | 29 | 1417 | 2048 | 42,496 | 3 | 87 | 90.80% | 8.67% | 0.02% | 0.51% |
| pool only | Rust (whole 1 TiB mapped) | 1021 | 1449 | 2048 | 42,496 | 3 | 87 | 90.80% | 8.67% | 0.02% | 0.51% |
| pool + 8 small hyp allocations in 8 other GiB regions (worst case) | C | 21 | 5505 | 6016 | 42,624 | 11 | 95 | 65.75% | 33.67% | 0.07% | 0.51% |
| same | Rust | 1013 | 5537 | 6016 | 42,624 | 11 | 95 | 65.75% | 33.67% | 0.07% | 0.51% |

Reference point measured on the N80 with the Rust hypervisor and another kernel (docs/mmap/c1-host-stage2-granularity.zh-CN.md:170-174): 1019 x 1 GiB, 2486 x 2 MiB, 8046 x 4 KiB, total 268,405,614 pages.
Level-1 entries used by RAM: index 2..3 (16 bytes, 1 cache line) and 128..157 (240 bytes, 4 cache lines) of the 8 KiB concatenated level-1 table.

### Table 7. Reasons for the host to enter EL2 in protected mode

| reason | EL2 handler | happens in a pinned user-space read loop? |
|---|---|---|
| HVC from the host kernel (KVM ioctls, share/unshare, shrinker count) | handle_host_hcall | no |
| SMC from the host kernel (PSCI, SDEI, TRNG, FF-A), trapped only in protected mode (HCR_TSC) | handle_host_smc, relay or forward to EL3 | no (deep cpuidle states were disabled; a rare TRNG reseed is possible) |
| FP/SIMD, SVE, SME access trap | fpsimd_host_restore | only after a guest ran on that CPU |
| stage-2 instruction or data abort | handle_host_mem_abort | no for RAM (pre-mapped); first access to an MMIO block in the C build |
| IRQ, FIQ, SError | not routed to EL2 for the host (invalid vector slots, IMO/FMO/AMO clear) | timer ticks are handled entirely at EL1, same as nvhe |

### Table 8. Host raw data: pkvm minus baseline versus working-set size (delta_profile.py; medians of 10 iterations; baseline = median of the three stage-1-only medians)

Random page order, stride 16 (ns per load):

| size MB | 4 KiB pages | kvmoff | vhe | nvhe | pkvm | spread of 3 baselines | pkvm - baseline | percent | cycles at 1.9 GHz |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 64 | 7.938 | 7.937 | 7.964 | 7.923 | 0.027 | -0.014 | -0.18% | -0.0 |
| 0.375 | 96 | 8.261 | 8.255 | 8.329 | 8.624 | 0.075 | +0.364 | +4.41% | +0.7 |
| 0.5 | 128 | 10.697 | 10.249 | 10.612 | 11.246 | 0.447 | +0.634 | +5.97% | +1.2 |
| 0.75 | 192 | 16.735 | 16.922 | 16.676 | 16.614 | 0.246 | -0.121 | -0.72% | -0.2 |
| 1 | 256 | 19.409 | 19.479 | 19.480 | 19.429 | 0.071 | -0.050 | -0.25% | -0.1 |
| 1.5 | 384 | 20.186 | 20.125 | 20.176 | 20.241 | 0.061 | +0.065 | +0.32% | +0.1 |
| 2 | 512 | 20.677 | 20.733 | 20.752 | 20.883 | 0.075 | +0.151 | +0.73% | +0.3 |
| 3 | 768 | 36.602 | 36.562 | 36.633 | 37.311 | 0.071 | +0.709 | +1.94% | +1.3 |
| 4 | 1024 | 47.587 | 47.455 | 47.688 | 49.314 | 0.233 | +1.727 | +3.63% | +3.3 |
| 6 | 1536 | 67.137 | 67.374 | 67.350 | 72.589 | 0.237 | +5.239 | +7.78% | +10.0 |
| 8 | 2048 | 112.544 | 112.325 | 112.601 | 119.595 | 0.276 | +7.050 | +6.26% | +13.4 |
| 12 | 3072 | 154.651 | 154.647 | 154.810 | 161.678 | 0.163 | +7.026 | +4.54% | +13.4 |
| 16 | 4096 | 168.543 | 169.708 | 168.556 | 176.282 | 1.165 | +7.725 | +4.58% | +14.7 |
| 24 | 6144 | 177.229 | 180.272 | 177.470 | 185.589 | 3.043 | +8.119 | +4.57% | +15.4 |
| 32 | 8192 | 180.613 | 182.721 | 180.776 | 188.659 | 2.108 | +7.883 | +4.36% | +15.0 |
| 48 | 12288 | 182.662 | 183.849 | 182.444 | 189.558 | 1.406 | +6.896 | +3.78% | +13.1 |
| 64 | 16384 | 185.233 | 185.428 | 185.045 | 191.730 | 0.383 | +6.497 | +3.51% | +12.3 |

Sequential, stride 256 (ns per load):

| size MB | 4 KiB pages | kvmoff | vhe | nvhe | pkvm | spread of 3 baselines | pkvm - baseline | percent |
|---|---|---|---|---|---|---|---|---|
| 1 | 256 | 4.437 | 4.433 | 4.437 | 4.435 | 0.004 | -0.002 | -0.03% |
| 2 | 512 | 4.703 | 4.697 | 4.699 | 4.699 | 0.005 | +0.000 | +0.00% |
| 4 | 1024 | 5.486 | 5.483 | 5.483 | 5.482 | 0.003 | -0.002 | -0.04% |
| 6 | 1536 | 8.248 | 8.296 | 8.224 | 8.345 | 0.072 | +0.096 | +1.16% |
| 8 (LLC Bnd) | 2048 | 10.815 | 12.447 | 11.410 | 12.123 | 1.632 | +0.713 | +6.25% |
| 12 | 3072 | 10.918 | 11.278 | 10.855 | 11.123 | 0.423 | +0.205 | +1.88% |
| 16 | 4096 | 11.041 | 11.331 | 10.692 | 11.148 | 0.639 | +0.107 | +0.96% |
| 24 | 6144 | 10.852 | 11.184 | 10.872 | 11.141 | 0.332 | +0.269 | +2.47% |
| 32 | 8192 | 10.704 | 11.311 | 10.503 | 10.854 | 0.808 | +0.150 | +1.41% |
| 48 | 12288 | 10.451 | 10.953 | 10.541 | 10.418 | 0.502 | -0.123 | -1.16% |
| 64 (Main Mem) | 16384 | 10.357 | 10.781 | 10.241 | 10.345 | 0.540 | -0.012 | -0.12% |

Upper bound for a sequential stride-256 load if the random-test extra cost were fully exposed: 7.05 ns per TLB miss / 16 loads per page = 0.44 ns (3.9% of 11.2 ns).

### Table 9. The three Figure 7 rows against each baseline (quick_host_check.py, n=10 per mode)

| row | statistic | kvmoff | vhe | nvhe | pkvm | pkvm/kvmoff | pkvm/vhe | pkvm/nvhe | vhe/kvmoff | nvhe/kvmoff |
|---|---|---|---|---|---|---|---|---|---|---|
| LLC Bnd (seq 8 MB, stride 256) | mean | 11.203 | 11.961 | 11.276 | 11.600 | +3.55% | -3.02% | +2.87% | +6.77% | +0.66% |
| LLC Bnd | median | 10.815 | 12.447 | 11.410 | 12.123 | +12.09% | -2.60% | +6.25% | +15.09% | +5.50% |
| Main Mem (seq 64 MB, stride 256) | mean | 10.381 | 10.784 | 10.302 | 10.411 | +0.29% | -3.46% | +1.06% | +3.88% | -0.76% |
| Main Mem | median | 10.357 | 10.781 | 10.241 | 10.345 | -0.12% | -4.05% | +1.01% | +4.09% | -1.12% |
| Rand Mem (random 64 MB, stride 16) | mean | 182.209 | 181.207 | 181.104 | 188.135 | +3.25% | +3.82% | +3.88% | -0.55% | -0.61% |
| Rand Mem | median | 185.233 | 185.428 | 185.045 | 191.730 | +3.51% | +3.40% | +3.61% | +0.11% | -0.10% |
| random 8 MB, stride 16 | mean | 112.600 | 112.374 | 112.683 | 119.651 | +6.26% | +6.48% | +6.18% | -0.20% | +0.07% |
| random 1 MB, stride 16 | mean | 19.462 | 19.485 | 19.480 | 19.465 | +0.01% | -0.10% | -0.08% | +0.12% | +0.09% |

vhe and kvmoff are the same translation regime (kernel at EL2, stage-1 only), yet differ by +6.77% (mean) on the LLC-boundary row.

### Table 10. Timeline of relevant changes (klad-v11-stable; commit date, first release from debian.master/changelog)

| commit date | commit | first release | change |
|---|---|---|---|
| 2026-04-24 | 334 commits incl. 54f14f15524f5, 62ff1bcb31807, a85e5f779e436, 2884260c9568a, 0f192f134bde2, 7b213cdf02fe4, 952b0eedc8a7d | 6.6.0-66.66 (2026-04-25) | Android pKVM import: THP support for pKVM guests, huge pinned pages, range map hypercall, pkvm_mem_abort_range, prefault on block split, host ownership in hyp vmemmap, no MMIO prepopulation |
| 2026-05-15 | 2dd9455c9aabd | 6.6.0-73.76 (2026-05-15) | Rust EL2 source added (hyp/nvhe/rust); CONFIG_X1_RMS default n |
| 2026-06-02 | 2e91f5ec6bc05 | 6.6.0-75.78 (2026-06-04) | CONFIG_RUST enabled in the arm64 kylinos config |
| 2026-06-03 to 06-06 | - | kernel in use: 6.6.0-73-generic | host and guest measurements |
| 2026-07-07 | b1b2979f0c0bf, daf0405c4301f | 6.6.0-76.85 (2026-07-07) | CONFIG_X1_RMS=y in kylinos_generic_defconfig (Rust EL2 replaces C EL2); directory renamed to hyp/xhypervisor |
| 2026-09-02 | 6b2c3ebba6023 | 6.6.0-79.93 | SDEI relay under pKVM; EL2 entry path masks and unmasks SDEI |
| 2026-09-25 | 6de53b7d70cc2 | 6.6.0-79.98 (2026-09-25) | pkvm_mem_abort no longer calls transparent_hugepage_adjust (same size rule via get_user_mapping_size); FOLL_LONGTERM only for protected VMs; MMU-notifier unmap enabled for non-protected VMs |

### Table 11. C versus Rust in the host memory path

| aspect | C (nvhe/mem_protect.c) | Rust (xhypervisor/src/mem_protect/host.rs) | effect on steady-state host memory access |
|---|---|---|---|
| page-table walker and mapper | hyp/pgtable.c | same C object, called through FFI (host.rs:10-14, 323-333) | none |
| host table flags, VMID 0, VTCR | :23-25, :143-153, :194 | consts.rs:155-157; host.rs:415-431, :543 | none |
| prepopulation | RAM only (:155-168) | RAM + MMIO gaps + IPA tail (:375-411) | none for RAM; C takes one lazy abort per MMIO block |
| finalize (HCR_VM, VTTBR, VTCR, TLBI) | :447-484 | :2160-2215 | none |
| host abort handling | switch on fault type (:835-871) | idmap attempt first, then perm handlers (:1974-2035) | none (no aborts in steady state) |
| share / donate bookkeeping | direct functions | PkvmMemTransition do_share / do_donate | none |
| IOMMU MMIO DMA state | refcount only (:1597-1672) | PTE software bits, forces 4 KiB (:914-948); iommu module not compiled (lib.rs:28) | none |
