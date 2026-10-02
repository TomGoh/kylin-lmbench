# 调查代理报告：arch-literature

> 这是多代理调查阶段的原始报告，英文原文照录。它的结论在使用前还要经过独立核查，
> 核查结果见同目录下的 verify-*.md。

## Headline

Architecture: with stage 2 enabled for EL1&0, the TTBR base, every stage-1 next-level table address and the final output address are IPAs that each need a stage-2 walk; the Arm ARM (DDI 0487E.a, D5.2.5) gives (S1+1)*(S2+1)-1 lookups when caching is ineffective (24 for 4+4 levels, 19 for 4+3, 9 when each stage-2 walk ends at a level-1 1 GiB block), and it explicitly permits TLBs to hold stage-1, stage-2-only (IPA->PA), combined and intermediate (walk-cache) entries in any form, a combined entry covering at most the smaller of the two mapping sizes. Derived for a pKVM host process with 4 KiB stage-1 pages and a 40-bit, level-1-start, 1 GiB-block stage 2: +5 memory references per TLB miss with no caching, +1 to +2 with only a stage-1 walk cache, 0 with ideal walk/IPA caches, all to an 8 KiB L1-resident table and with no loss of TLB reach. The raw N90 data carry exactly that signature (random-access latency identical at 1 MB, then a constant +7.0 ns = about 13 cycles at 1.9 GHz from 8 MB to 64 MB against all three baselines; rank test p about 0.01 at 64 MB, complete separation at 8 MB), whereas the LLC-boundary +3.55% is statistically indistinguishable from zero (Welch p=0.40, bimodal iterations, CV 7-11%, negative versus VHE). Thirty sources were opened and verified: none publishes a host-side overhead figure for pKVM itself (closest analogues HyperEnclave, BlackBox, TrustVisor, XMHF report under 1-3% typically with page-fault and TLB-heavy outliers), lmbench's own authors plus Brown and Seltzer, Kessler and Hill, and Kalibera et al. document capacity-boundary and page-placement instability, and nothing reliable is public about FTC862 TLB sizes, walk caches or prefetchers.

## Findings

### arch-literature#1 (DOCUMENTED, confidence high)

Item 1a (which addresses need stage 2). In a two-stage EL1&0 regime stage 1 maps VA->IPA and stage 2 maps IPA->PA. The base address in TTBR_EL1 and every table base address returned by a stage-1 table descriptor are IPAs, so each stage-1 descriptor fetch first requires a (recursive) stage-2 translation, and the final stage-1 output address requires one more. A 4-level stage-1 walk therefore triggers 5 stage-2 translations (4 table addresses + 1 output address).

Evidence: ARM DDI 0487E.a (ID070919), full text obtained from archive.org item armv8-a-reference-manual and saved as S/armarm/DDI0487E_a_searchtext.txt, where S=<scratch>/wf1/arch-literature. D5.2.1 p.D5-2513 (text line 54550); D5.2.5 p.D5-2534 (line 55071: '...is the IPA of the base of the translation table. This means that if stage 2 address translation is enabled, each of these OAs is subject to second stage translation.'); D5.8.2 p.D5-2625 (line 57434: '...the descriptor address is in the IPA address space, and is subject to a stage 2 translation to obtain the required PA. This stage 2 translation requires a recursive entry to the fault checking sequence.'); HCR_EL2.PTW p.D13-3081 (line 68422). Same five nested walks stated for x86 by Bhargava et al., S/papers/bhargava-asplos08.txt:112.

### arch-literature#2 (DOCUMENTED, confidence high)

Item 1b (worst-case count). The Arm ARM states that when caching of translation table entries is ineffective the number of lookups is (S1+1)*(S2+1)-1, S1 and S2 being the numbers of lookup levels of each stage. Arithmetic: 4-level stage 1 with 4-level stage 2 = 24; with 3-level stage 2 = 19; with every stage-2 walk ending at a level-1 block (S2=1) = 9.

Evidence: S/armarm/DDI0487E_a_searchtext.txt lines 55073-55075 (D5.2.5 Note, p.D5-2534): 'The number of lookups required is given by the following equation: (S1+1)*(S2+1) - 1'. Independent cross-checks read directly: Bhargava et al. 'a 2D walk requires nm + n + m page entry references' (S/papers/bhargava-asplos08.txt:52); Simner et al. 'with four levels, up to 24 with both stages enabled' (S/papers/simner-relaxed-vm-esop22.txt:562); Gandhi et al. 'up to 24 memory references on x86-64' (S/papers/gandhi-micro14.txt:18). The 24/19/9 values are my arithmetic on the documented formula.

### arch-literature#3 (DOCUMENTED, confidence high)

Item 1c (stage-2 geometry). For stage 2 up to 16 translation tables can be concatenated at the initial lookup level; a 40-bit IPA with the 4 KiB granule can start at level 1 with two concatenated tables (8 KiB, 1024 entries, T0SZ=24, SL0=1). With the 4 KiB granule a level-1 block maps 1 GiB and a level-2 block maps 2 MiB.

Evidence: S/armarm/DDI0487E_a_searchtext.txt lines 55023 and 55029 (D5.2.4, Example D5-2, p.D5-2532: 'Two translation tables are concatenated, giving a total size of 8KB'); line 55185 (Table D5-13, pp.D5-2537-2538: initial lookup level 1 (SL0 value 1), two-tables column T0SZ 24, IA[39:12]); line 55959 (D5.3, p.D5-2565, block descriptor sizes).

### arch-literature#4 (DOCUMENTED, confidence high)

Item 1d (what may be cached). The architecture does not specify the form of TLB structures and permits caching any translation table entry that does not itself fault, explicitly including (a) entries pointing to subsequent tables (intermediate caching, i.e. walk caches), (b) stage-2 entries used during a stage-1 walk, (c) stage-2 entries used for the stage-1 output address, and caching structures that hold stage-1 information, stage-2-only information, or combined stage-1+stage-2 information, at any level. Entries are tagged with VMID (and ASID).

Evidence: S/armarm/DDI0487E_a_searchtext.txt line 57596 (D5.9 p.D5-2632); line 57649 and 57656 (D5.9.2 p.D5-2634: 'The Arm architecture does not specify the exact form of the TLB structures for any design'; 'This is referred to as intermediate caching of TLB entries'); lines 57719 and 57721 (D5.10.1 p.D5-2638: list of cacheable entries and the three kinds of caching structure). Consistent secondary statement co-authored by Arm's chief architect: Simner et al., S/papers/simner-relaxed-vm-esop22.txt:637 ('TLB implementations might cache any combination of individual page-table entries and partial or complete translations').

### arch-literature#5 (DOCUMENTED, confidence high)

Item 1e (stage-2-only versus combined caches are architecturally distinct). A TLB invalidation that applies to stage-2 entries only is not required to touch structures that combine stage 1 and stage 2, which is why the architecture prescribes TLBI IPAS2E1 followed by TLBI VMALLE1; Linux KVM implements exactly that sequence and its comment names the complete (S1 + S2) cached walk.

Evidence: S/armarm/DDI0487E_a_searchtext.txt lines 57731-57733 (D5.10.1 p.D5-2639), 57937 (IPAS2 scope, p.D5-2648), 57994 (sequence, p.D5-2650). Kernel: klinux/arch/arm64/kvm/hyp/nvhe/tlb.c:156-172 ('...a table walk on another CPU could refill a TLB with a complete (S1 + S2) walk based on the old Stage-2 mapping...').

### arch-literature#6 (INFERRED, confidence medium)

Item 1f (size of a combined TLB entry). The Arm ARM does not dictate the size at which a TLB stores an entry (it explicitly mentions splintering a page and only requires invalidation to cover at least the size in the translation table entry). A single combined VA->PA entry can be linear only where both stages are single leaf mappings, so it covers at most min(stage-1 size, stage-2 size), further limited to sizes the TLB supports. Consequence for the pKVM host: 4 KiB stage-1 pages over 1 GiB stage-2 blocks give 4 KiB combined entries, i.e. the same TLB reach as native; reach is lost only where stage 2 is finer than stage 1 (for example kernel block mappings over stage-2 regions shattered to 4 KiB).

Evidence: Documented inputs: S/armarm/DDI0487E_a_searchtext.txt line 57727 (p.D5-2638, 'as could occur from splintering a page when caching in the TLB') and line 57887 (p.D5-2646, minimum invalidation size). Arm Ltd patent US 10,649,907 B2 (opened twice via https://patents.google.com/patent/US10649907B2/en): 'The final page size will be chosen to be the smaller of the first stage page size and the second stage page size used when determining the address translation data.' x86 statement read directly: 'the TLB must consider the page size for a given translation to be the smaller of the nested and guest page sizes, referred to as splintering' (S/papers/bhargava-asplos08.txt:216). Cortex-A53 main TLB descriptor stores S1 Size, S2 Level and its own Size separately (S/papers/arm-ddi0500j-cortex-a53-trm.txt:21450 ff.). The min() rule itself is my inference, not an Arm ARM rule.

### arch-literature#7 (DOCUMENTED, confidence high)

Item 1g (example of a real Arm implementation; not FTC862). Cortex-A53 has 10-entry micro TLBs, a 512-entry 4-way main TLB holding combined entries (VA, block size, PA, ASID, VMID), a 64-entry walk cache that stores the physical address of the last-level stage-1 table tagged with ASID and VMID, and a separate 64-entry IPA cache used only for stage-2 translations; the main TLB does not hold 1 GiB entries (a 1 GiB block is split into 512 MiB).

Evidence: Arm Cortex-A53 MPCore TRM, DDI 0500J, read directly: S/papers/arm-ddi0500j-cortex-a53-trm.txt:20422-20430 (structures), 20461 (1 GiB split), 20472 (IPA cache RAM), 20481 (walk cache RAM), 21450 ff. (Table 6-13 main TLB descriptor), 21636 (Table 6-15 'PA Physical Address of second, last translation level'). Opened from https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/Layerscape/8583/1/DDI0500J_cortex_a53_trm.pdf (mirror of the Arm document).

### arch-literature#8 (DOCUMENTED, confidence high)

Only the pkvm configuration runs host processes under two-stage translation. With stage 2 disabled the IPA maps flat to the PA; classic KVM/ARM disables stage 2 while the host runs; a VHE host uses the single-stage EL2&0 regime. In this kernel only kvm-arm.mode=nvhe and =protected force the kernel out of VHE, so kvmoff (mode=none) and vhe both use EL2&0 and nvhe uses EL1&0 with stage 2 off.

Evidence: S/armarm/DDI0487E_a_searchtext.txt line 55820 (D5.2.9 p.D5-2559) and line 54597 (D5.2.1 p.D5-2515). Dall et al. ISCA 2016: 'the hypervisor must disable traps to EL2 and Stage-2 translation from EL2 while switching from the VM to the hypervisor' (S/papers/dall-isca16.txt:320, also :187); Dall et al. ATC 2017 (S/papers/dall-atc17.txt:140). AOSP AVF architecture page (fetched twice): 'Historically, KVM runs with stage 2 translation enabled while running guests and with stage 2 disabled while running the host Linux kernel.' Kernel: klinux/arch/arm64/kernel/idreg-override.c:241-242 (aliases only for nvhe and protected); that the N90 kvmoff boot actually stayed in VHE is my inference from that table.

### arch-literature#9 (DOCUMENTED, confidence high)

Premise check for item 5 from source code: the host stage 2 uses the CPU PARange as IPA size; for 40 bits the code yields 3 levels, SL0=1 (start level 1) and a 2-page concatenated root (1024 entries); 1 GiB level-1 blocks are allowed with 4 KiB pages and the fault/prepopulation path picks the largest block that fits inside a memory region, falling back to 2 MiB or 4 KiB; non-default permissions force page-level mappings. The Rust EL2 code mirrors the C logic. Whether the pages used by the benchmark on the N90 were in fact under 1 GiB blocks was not verified by me.

Evidence: K=klinux. K/arch/arm64/kvm/hyp/nvhe/mem_protect.c:143-153 ('The host stage 2 is id-mapped, so use parange for T0SZ'), 635-668 (host_stage2_adjust_range), 725-741 (host_stage2_force_pte comment), 762-780; K/arch/arm64/kvm/hyp/pgtable.c:587-638 (kvm_get_vtcr), 65-81 (kvm_pgd_pages), 1835-1845; K/arch/arm64/include/asm/stage2_pgtable.h:23; pgtable-hwdef.h:26; kvm_arm.h:157-167 and 218-223; kvm_pgtable.h:17-27 ('4K (level 1): 1GB'); K/arch/arm64/kvm/reset.c:285-288 (IPA Size Limit from PARange). Rust: K/arch/arm64/kvm/hyp/xhypervisor/src/mem_protect/host.rs:375-409, 415-431, 485-488, 1749-1818, 1838-1866; utils.rs:412-421, 581-583, 954-996. My computation of the macros for phys_shift=40: levels=3, SL0=1, pgd pages=2, 1024 entries. Commit messages: 1025c8c0c6ac ('created lazily using large block mappings if possible'), 2fcb3a59401d, 0916891094c4 ('pre-populate the host stage-2 ... using as many block mappings as possible'), e054adc5821b ('reducing the TLB pressure at host stage2').

### arch-literature#10 (INFERRED, confidence medium)

Item 5 derivation. Host process with 4-level stage 1 (4 KiB leaf) under a 40-bit, level-1-start stage 2 made of 1 GiB blocks: each stage-2 translation is one descriptor read. (i) No caching at all: 9 references per TLB miss instead of 4, i.e. +5. With a stage-1 walk cache but no stage-2 caching: 3 instead of 1, i.e. +2. With a stage-1 walk cache that stores the physical address of the last-level table but no IPA->PA cache: 2 instead of 1, i.e. +1. (ii) Ideal walk caches (walk cache holding the PA plus an IPA->PA cache hit for the output address): 1 instead of 1, i.e. 0 extra. All extra reads go to the level-1 stage-2 table (8 KiB; at most about 32-34 entries in use on a 32 GiB machine), so each costs roughly one L1 data-cache hit. If stage 2 were 2 MiB blocks or 4 KiB pages the uncached extras would be +10 or +15.

Evidence: Arithmetic on the documented formula (S1+1)*(S2+1)-1 with S1=4 and S2=1, 2, 3, plus the walk-cache models documented for Cortex-A53 (walk cache stores a PA; separate IPA cache). Time conversion assumes a 4-cycle L1 hit, which is NOT documented for FTC862: +1 = 2.1 ns, +2 = 4.2 ns, +5 = 10.5 ns at 1.9 GHz (0.526 ns per cycle). See table 3.

### arch-literature#11 (MEASURED, confidence high)

Raw host data show a fixed per-access penalty that appears only beyond TLB reach. lat_mem_rd -t (stride 16) medians, pkvm minus kvmoff: 1 MB +0.02 ns (+0.1%, Welch p=0.97); 2 MB +0.21; 4 MB +1.73 (+3.6%); 6 MB +5.45; 8 MB +7.05 (+6.3%); 12 MB +7.03; 16 MB +7.74; 32 MB +8.05; 64 MB +6.50 ns (+3.5%). The penalty is the same against kvmoff, nvhe and vhe (7.05, 6.99, 7.27 ns at 8 MB), the three baselines agree with one another within 0.3 ns up to 12 MB, and at 8 MB all 10 pkvm iterations exceed all 30 baseline iterations. At 64 MB the mean-based figure of the paper is reproduced (+5.93 ns, +3.25%); Welch p=0.098 because each mode has 1-3 low outliers, but Mann-Whitney permutation p=0.011 / 0.009 / 0.009 versus the three baselines and p=0.001 versus the pooled 30, Hodges-Lehmann shift +6.3 to +6.6 ns. The percentage falls with size only because the baseline grows from 112 ns to 185 ns while the absolute extra stays near 7 ns (13 cycles at 1.9 GHz).

Evidence: Computed from kylin-lmbench/results/n90-day3-host/n90-{kvmoff,nvhe,vhe}-noLSM-full-cpu0.csv and n90-pkvm-noLSM-try2-cpu0.csv with S/anchor_numbers.py, S/welch_and_model.py, S/ranktest_64mb.py (outputs S/anchor_numbers.out, S/welch_and_model.out, S/ranktest_64mb.out). Metric mapping confirmed in kylin-lmbench/scripts/build-xlsx-mean.py:219-221.

### arch-literature#12 (INFERRED, confidence low)

The measured penalty fits the two-stage-walk model but does not pin down the FTC862 walker. lmbench's random mode touches a different page on every access, so beyond TLB reach each access takes one TLB miss; +7.0 ns is then about 13 cycles per TLB miss, inside the architectural envelope of +1 to +5 extra descriptor reads (4 to 20 cycles at an assumed 4-cycle L1 hit) and most simply matched by 2 to 4 serialized extra reads, or fewer reads with a fixed per-step cost. It is not explained by lost TLB reach (combined entries stay 4 KiB) and not by memory-hierarchy latency (no penalty at 1 MB, no growth from 8 MB to 64 MB).

Evidence: lmbench source comment, kylin-lmbench/src/lib_mem.c:222-234 ('Access a different page each time. This will eventually cause a tlb miss each page'). Internal, not verified by me: docs/memlat/memlat-investigation-worklog.zh-CN.md section 6.1 reports PMU l2d_tlb_refill per access of 0.006 / 0.447 / 0.967 / 1.000 at 1 / 4 / 8 / 16 MB on an N80 booted in protected mode. Envelope from the item-5 derivation; 7.05 ns x 1.9 GHz = 13.4 cycles from my measurement.

### arch-literature#13 (MEASURED, confidence high)

The LLC-boundary figure is not a resolvable effect. Sequential stride 256 at 8 MB: pkvm minus kvmoff mean +0.397 ns (+3.55%, exactly the paper's number) with SE 0.463 ns, Welch t=0.86, p=0.40, permutation p=0.40, Mann-Whitney p=0.22; versus nvhe +2.87% (p=0.53); versus vhe -3.02% (p=0.41). Iterations are bimodal in every mode (about 10.0-10.7 ns or 12.2-12.6 ns): slow-cluster counts are kvmoff 4/10, nvhe 5/10, vhe 6/10, pkvm 5/10. Within-mode CV is 6.9-10.6% at 8 MB versus 0.07-0.15% at 4 MB and 0.9-1.7% at 6 MB. The same capacity-boundary noise appears at the L2 size (0.5 MB random: CV 5.4-7.2% in all modes, 0.7-1.0% at 1 MB).

Evidence: S/welch_and_model.out, S/ranktest_64mb.out (sorted iteration values printed), S/anchor_numbers.out; same CSVs as above.

### arch-literature#14 (MEASURED, confidence high)

Sequential access cannot show the stage-2 cost in this data set. At 64 MB, for strides 64 to 1024, pkvm minus the median of the three baseline medians is +0.04, +0.15, -0.01, +0.22, +0.38 ns, but the spread among the three baselines that have no host stage 2 is larger in every row (0.11, 0.25, 0.54, 0.41, 0.59 ns), vhe being the slowest configuration in every row. For the paper's Main Mem metric (stride 256, 64 MB) pkvm versus kvmoff is +0.29% (p=0.77) and pkvm is 3.5% faster than vhe (p=0.017). Inter-boot state, not the virtualization mode, dominates sequential results.

Evidence: S/seq_walk_cost.py and S/seq_walk_cost.out; S/welch_and_model.out; S/ranktest_64mb.out.

### arch-literature#15 (MEASURED, confidence medium)

Applying Kessler and Hill's binomial page-placement model to the given L3 geometry (128 page colours, 16 pages per colour): with random physical placement the expected share of pages in over-subscribed colours is 0.08% at 4 MiB, 2.0% at 6 MiB, 9.9% at 8 MiB (95% range over placements 8.6-11.2%), 15.8% at 9 MiB of which 11.1% is unavoidable, and 33.6% at 12 MiB of which 33.3% is unavoidable. Unnecessary conflicts therefore peak exactly when the footprint equals the cache size. For stride 256 at 8 MB the touched lines (32768) also equal the capacity of the sets they map to. This shows the 8 MB point is structurally placement-sensitive; it does not prove that colour conflicts are the dominant cause on this machine.

Evidence: Computation S/welch_and_model.py (exact binomial sum of their Eq. 1-2 plus 4000 Monte-Carlo placements), output S/welch_and_model.out; model read in S/papers/kessler-hill-tocs92.txt:308-380. Counter-evidence that I did not verify: the internal worklog (sections 6.4-6.5, 9) reports that on an N80 L3 refills did not change with page arrangement, that physical contiguity (prefetch across 4 KiB boundaries) changed latency by 8-20%, and raises an unverified interconnect-frequency hypothesis.

### arch-literature#16 (DOCUMENTED, confidence high)

Verified literature on the cost of two-dimensional walks. Bhargava et al.: a 2D walk needs nm+n+m references (24 for 4+4), an uncached nested walk is 3.9-4.6 times slower than a native one, nested page-walk caching improves guest performance 15-38%, a nested TLB a further 3-7%, 2 MiB nested pages a further 3-22% and cut TLB misses 21-43%. Barr, Cox and Rixner: MMU caches cut memory accesses per TLB miss from 4.00 to at most 1.13 (SPEC CFP2006), and with a nested TLB hit on every guest table access the accesses equal native execution. Gandhi et al.: native 4 versus up to 24 references; cycles per TLB miss rise 2.4x, 1.5x and 1.6x for guest 4K over host 4K, 2M and 1G pages; graph500 translation overhead 28% native versus 113% (4K+4K) and 53% (4K+2M); TLB misses themselves rise 1.29-1.62x because nested entries share the TLB.

Evidence: Read directly after download: S/papers/bhargava-asplos08.txt:52, 84, 252, 498, 672 (from https://pages.cs.wisc.edu/~remzi/Classes/838/Spring2013/Papers/p26-bhargava.pdf; Crossref 10.1145/1346281.1346286, ASPLOS XIII 2008, pp.26-35); S/papers/barr-isca10.txt:493, 499, 776 (https://cs.rice.edu/CS/Architecture/docs/barr-isca10.pdf; Crossref 10.1145/1815961.1815970, ISCA 2010, pp.48-59); S/papers/gandhi-micro14.txt:18, 527, 535, 663, 673 (https://pages.cs.wisc.edu/~swift/papers/micro14-virtualization.pdf; Crossref 10.1109/MICRO.2014.37, MICRO-47 2014, pp.178-189).

### arch-literature#17 (DOCUMENTED, confidence high)

Verified literature that directly measures a deprivileged host or primary OS under an identity nested/stage-2 map. HyperEnclave (x86, AMD EPYC 7601, huge pages in the NPT): overhead on the demoted primary OS is 'less than 1% in most benchmarks'; lmbench null call -0.25%, fork +0.82%, context switch +2.88%, mmap +0.43%, page fault +1.15%, AF_UNIX -0.70%, kernel build +0.50%; SPEC CPU 2017 per-benchmark -0.3% to +3.7%. BlackBox (Arm Cortex-A72 and A57, lmbench 3.0-a9, identity stage-2 for the OS with transparent 2 MiB blocks): page fault is 'the one microbenchmark for which there is noticeable overhead' from the OS NPT alone. TrustVisor (x86 2010, identity NPT with 2 MiB pages): most lmbench operations under 6%, fork/exec/ctxsw 34%/27%/15%, most SPECint under 3% but mcf 29%. XMHF (x86 2013): most SPEC under 3%, 2 MiB nested mappings better than 4 KiB.

Evidence: S/papers/hyperenclave-atc22.txt:1074-1100 (Appendix A.2, Table 3; https://www.usenix.org/system/files/atc22-jia-yuekai.pdf, USENIX ATC 2022 pp.437-454); S/papers/blackbox-osdi22.txt:537, 597, 660, 663, 757, 763 (https://www.usenix.org/system/files/osdi22-vant-hof.pdf, OSDI 2022 pp.683-700; the figure values are not in the text); S/papers/trustvisor-sp10.txt:471-473, 703, 716-718 and Figure 6 (https://netsec.ethz.ch/publications/papers/MLQZDGP2010.pdf; Crossref 10.1109/SP.2010.17, pp.143-158); S/papers/xmhf-sp13.txt:670, 697-699 (https://www.ieee-security.org/TC/SP2013/papers/4977a430.pdf; Crossref 10.1109/SP.2013.36, pp.430-444).

### arch-literature#18 (DOCUMENTED, confidence medium)

pKVM-specific sources state the design but give no host-side number. AOSP: 'The host stage 2 is identity-mapped... This architecture allows the use of large mappings in the page table and consequently reduces pressure on the translation lookaside buffer (TLB).' Kernel documentation: the host runs with an identity mapping at stage 2. KVM Forum 2022 slides: host stage-2 mappings are created lazily. The only peer-reviewed AVF evaluation (Wei et al., SAC 2024, Pixel 6/7) compares protected with unprotected guests, not host with and without pKVM: hypercall 1,497 vs 1,641 cycles, block I/O 25% worse, network 75% worse, low overhead for CPU and memory-intensive workloads. In every pKVM source I opened there is no published figure for host overhead under stage 2; that such a figure does not exist anywhere is an inference.

Evidence: https://source.android.com/docs/core/virtualization/architecture (two fetches, identical wording); https://www.kernel.org/doc/html/next/virt/kvm/arm/pkvm.html (two fetches) and klinux/Documentation/virt/kvm/arm/pkvm.rst:20-23; S/papers/perret-pkvm-deepdive-kvmforum22.txt:752 (https://gitlab.com/qemu-project/kvm-forum/-/raw/main/_attachments/2022/KVM%20forum%202022%20-%20pKVM%20deep%20dive.pdf); https://lwn.net/Articles/837552/ (RFC cover letter, two fetches, no performance statement); S/papers/wei-avf-sac24.txt:13, 41, 68, 136 (https://liswei.sh/files/sac24wei.pdf; Crossref 10.1145/3605098.3636097, SAC 2024 pp.1533-1535); S/papers/simner-relaxed-vm-esop22.txt:1038.

### arch-literature#19 (DOCUMENTED, confidence high)

Related verified Arm results on stage-2 granularity. SeKVM: removing stage-2 huge pages adds 35-50% overhead for hackbench, MySQL and MongoDB in guests (Cortex-A57). HypSec: host confined by a flat identity stage-2 map; 5-19% on hypervisor microbenchmarks, under 10% on most guest applications; host-native overhead not reported. Martins and Pinto (Cortex-A53, Jailhouse/Xen/Bao/seL4): with 2 MiB stage-2 superpages overhead is under 1%; without superpages TLB misses and degradation rise (up to 7%); guest TLB misses correlate with degradation (r up to 0.96); cache colouring by itself costs up to about 20%, partly because it forces 4 KiB stage-2 pages.

Evidence: S/papers/sekvm-sp21.txt:742, 790 (https://www.cs.columbia.edu/~nieh/pubs/ieeesp2021_kvm.pdf; Crossref 10.1109/SP40001.2021.00049, pp.1782-1799); S/papers/hypsec-sec19.txt:328, 705, 709 (https://www.usenix.org/system/files/sec19-li-shih-wei.pdf, USENIX Security 2019 pp.1357-1374); S/papers/martins-pinto-rtas23.txt:30, 272, 285, 400 (https://arxiv.org/pdf/2303.11186; Crossref 10.1109/RTAS58335.2023.00011, RTAS 2023 pp.40-53).

### arch-literature#20 (DOCUMENTED, confidence high)

Verified literature on page placement and cache-capacity boundaries. Kessler and Hill: arbitrary page placement causes up to 30% unnecessary cache conflicts; careful mapping removes 10-20% of misses in a direct-mapped cache, 4-10% in 2-way and 2-5% in 4-way; random mappings, not the workload, cause bursts and variance of misses. Brown and Seltzer: cache conflicts in an lmbench-derived buffer 'produced a bimodal distribution'; when pages are randomly assigned to physical addresses 'there is a good probability that pages of the buffer will conflict in the cache, even when the size of the buffer is smaller than the size of the caches'; random page mapping gave 5% standard deviations.

Evidence: S/papers/kessler-hill-tocs92.txt:26, 29, 1020, 1200 (https://pages.cs.wisc.edu/~markhill/papers/tocs92_coloring_original.pdf, author-hosted version; Crossref 10.1145/138873.138876, ACM TOCS 10(4) 1992 pp.338-359); S/papers/brown-seltzer-sigmetrics97.txt:176, 189, 201 (https://www.seltzer.com/assets/publications/Operating-System-Benchmarking-in-the-Wake-of-Lmbench.pdf; Crossref 10.1145/258612.258690, SIGMETRICS 1997 pp.214-224).

### arch-literature#21 (DOCUMENTED, confidence high)

lmbench-specific primary statements. The lmbench paper: results varied 'up to 30%' and the authors 'suspect that the operating system is not using the same set of physical pages each time ... and we are seeing the effects of collisions in the external caches'; measuring TLB miss time with lat_mem_rd 'is problematic because different systems map different amounts of memory with their TLB hardware'. The lmbench 3 documentation shipped in the benchmark repo: 'pages often collide in the cache and the fraction of pages that have collisions often increases as the amount of memory nears the cache size', 'Factoring out page placement affects on average memory latency is very difficult'; the man page warns about stride-sensitive prefetching and lists TLB miss latency as the last plateau; the authors' rebuttal: 'The real issue is cache conflicts due to page placement in the cache. Page placement is something not under our control'.

Evidence: S/papers/mcvoy-lmbench-usenix96.txt:164-173, 466-473 (https://www.usenix.org/legacy/publications/library/proceedings/sd96/full_papers/mcvoy.pdf, USENIX 1996 Annual Technical Conference, San Diego; page numbers not verified). Local lmbench 3.0-a9 files in L=kylin-lmbench: L/doc/memhier.ms:939-954 and 1119-1135 (Carl Staelin, 'Micro-architecture analysis', draft), L/doc/lat_mem_rd.8:27-30, 50-56, 63-82, L/hbench-REBUTTAL:139-145, L/src/lib_mem.c:222-234.

### arch-literature#22 (DOCUMENTED, confidence high)

Verified literature on run-to-run and between-boot bias. Kalibera, Bulej and Tuma: the assignment of physical pages changes cache hits and misses, 'is not reproducible without nontrivial modifications of the operating system', and the ratio of between-run to within-run standard deviation for an FFT benchmark was 25.8 (P4/Linux), 94.7 (P4/Windows 2000) and 35.9 (Itanium) even after reboot on an idle system. Hocko and Kalibera: Linux's default cache-unaware page allocation is a significant source of non-determinism (30% between executions in their example); page colouring and bin hopping reduce it; colouring was rejected for Linux 2.2 and 2.4. Mytkowicz et al.: layout-induced measurement bias averages 2% (Core 2) to 8% (Pentium 4) for link order and 1% to 4% for environment size, enough to flip conclusions (0.92 vs 1.10). Curtsinger and Berger: one binary is one sample of layout space; -O3 versus -O2 is indistinguishable from noise.

Evidence: S/papers/kalibera-spects05.txt:160-166, 230-241, 248-257, 313 (http://www.cs.kent.ac.uk/pubs/2005/3143/content.pdf; SPECTS 2005; page numbers disagree between sources and are not verified); S/papers/hocko-kalibera-wosp10.txt:96, 113, 133 (https://research.spec.org/icpe_proceedings/2010/p223.pdf; Crossref 10.1145/1712605.1712640, pp.223-234); S/papers/mytkowicz-asplos09.txt:318, 353, 390 (https://users.cs.northwestern.edu/~robby/courses/322-2013-spring/mytkowicz-wrong-data.pdf; Crossref 10.1145/1508244.1508275, pp.265-276); S/papers/stabilizer-asplos13.txt:25, 42 (https://people.cs.umass.edu/~emery/pubs/stabilizer-asplos13.pdf; Crossref 10.1145/2451116.2451141, pp.219-228).

### arch-literature#23 (DOCUMENTED, confidence medium)

Two further placement-related mechanisms have verified literature and local source evidence. (a) Prefetchers working on physical addresses do not prefetch beyond 4 KiB physical page boundaries because physical contiguity is not guaranteed, so sequential latency depends on whether consecutive virtual pages are physically contiguous. (b) Memory frequency scaling driven by bandwidth utilisation changes the latency of dependent-load cache misses; the kernel tree contains Phytium devfreq drivers that scale both the network-on-chip and the DDR memory unit with a load-based governor (100 ms polling, 80% up-threshold), a platform variable independent of the KVM mode.

Evidence: (a) Vavouliotis et al., S/papers/vavouliotis-micro22.txt:72-80, 232-236 (https://gvavou5.github.io/Documents/Vavouliotis_MICRO22.pdf; Crossref 10.1109/MICRO56248.2022.00070, MICRO 2022 pp.956-974). (b) David et al., S/papers/david-memdvfs-icac11.txt:31-36 and section 5.2 (https://users.ece.cmu.edu/~omutlu/pub/memory-dvfs_icac11.pdf; Crossref 10.1145/1998582.1998590, ICAC 2011 pp.31-40); klinux/drivers/devfreq/phytium_noc.c:1-6, 528, 537-540; drivers/devfreq/phytium_dmu.c:556, 564, 657; drivers/devfreq/Kconfig:160-176; arch/arm64/configs/kylinos_generic_defconfig:1943-1944. Whether either mechanism acted on the N90 during the June runs is not established by me.

### arch-literature#24 (DOCUMENTED, confidence medium)

Item 4. Public information on FTC862 / D3000 is limited to product-level facts: 8 FTC862 cores, ARMv8 64-bit with ARM64 and ARM32, hardware virtualization, up to 2.5 GHz (D3000) or 'over 2.9 GHz' (D3000M), '二级缓存 4MB' (8 x 512 KiB) and '末级缓存 8MB'. An OEM sheet says ARMv8.2-compatible. I found nothing reliable on first- or second-level TLB sizes, page-walk or IPA caches, cache inclusivity, L1 latency or prefetchers, so every microarchitectural statement about FTC862 address translation must be measured, not cited.

Evidence: https://www.phytium.com.cn/homepage/production/15/ and https://www.phytium.com.cn/homepage/production/16/ (the latter fetched twice); S/papers/zte-d3000-intro.txt:19-23, 40 (ZTE product sheet, third party); https://www.163.com/dy/article/JID8V9N3055635W4.html (third party, no microarchitecture); kernel: klinux/arch/arm64/include/asm/cputype.h:162, 246 (part 0x862) and arch/arm64/kernel/cpuid.c:183. Web searches for FTC862/FTC860/FTC870 TLB, ROB, prefetcher returned no vendor or peer-reviewed specification.

### arch-literature#25 (DOCUMENTED, confidence high)

Items I could not verify and therefore do not list as verified: Pham et al. MICRO 2015 (page splintering; all PDF URLs returned 404 or 403); Merrifield and Taheri VEE 2016; Buell et al. VMware 2013 (seen only as quoted by Gandhi et al.); Hypernel DAC 2018 (search snippets only); Dall and Nieh ASPLOS 2014; any Intel pKVM-IA or Google talk with host overhead numbers; Cortex-A76/Neoverse N1 TRM text; the current issue of DDI 0487 (Arm site is script-rendered and the PDF exceeds the fetch limit); ACM DL and DBLP pages (blocked), for which Crossref metadata was used instead.

Evidence: Fetch attempts in this session returned HTTP 403/404/429, a 10 MB size limit, or script-only pages; see sources list S/sources.tsv for everything that was actually opened.

## Caveats

- Arm ARM wording was verified against issue E.a (July 2019) from the Internet Archive full text, not the current issue: the Arm site is script-rendered and the PDF exceeds the 10 MB fetch limit. Later issues renumber chapter D5 as D8 and use rule identifiers; I believe the substance is unchanged but did not check it.
- The rule that a combined TLB entry is the smaller of the two mapping sizes is my inference supported by an Arm patent, x86 literature and the Cortex-A53 TLB format; the Arm ARM only says the TLB form is not dictated and mentions splintering.
- FTC862 microarchitecture (second-level TLB size, walk cache, IPA cache, L1 latency, prefetchers, L3 inclusivity) is not public, so the item-5 result is an envelope of 0 to +5 references; the 4-cycle L1 latency used for time conversion is an assumption.
- The premise that the benchmark's pages sit under 1 GiB stage-2 blocks was taken from the task and from code that permits and prefers such blocks; I did not see a stage-2 page-table dump. Hypervisor-owned pages split the surrounding regions into 2 MiB or 4 KiB mappings, where the uncached extras would be +10 or +15.
- That one TLB miss occurs per access in the random test above 8 MB comes from the lmbench source comment and from PMU counts in an internal worklog measured on an N80 in protected mode only; I did not measure it and no baseline-mode count exists.
- The internal worklog (kylin-lmbench/docs/memlat/memlat-investigation-worklog.zh-CN.md) was being edited by the parent session while I worked; its device results (physical contiguity and prefetch explaining the 8 MB bimodality on N80, page-colour conflicts not confirmed, an unverified interconnect frequency-scaling hypothesis) are reported here as documented-but-unverified. My Kessler-Hill numbers show placement sensitivity at 8 MiB, not that colour conflicts are the actual cause on the N90.
- Each mode is one boot with 10 iterations, so between-boot variation is confounded with mode; this matters for sequential metrics (baseline-to-baseline spread up to 0.6 ns) and much less for random access at 8 MB and above (baselines agree within 0.3 ns up to 12 MB).
- Papers were read from author, university, USENIX or arXiv copies because ACM DL returned 403; bibliographic data for DOI-bearing papers were cross-checked through the Crossref API. Page numbers for McVoy and Staelin 1996 and Kalibera et al. 2005 are not verified. Quotes from web pages (AOSP, kernel.org, LWN, Phytium, Google Patents) passed through the fetch tool's summarising model; the key ones were fetched twice with matching wording. PDF-based quotes were read directly from converted text.
- BlackBox gives its stage-2-only overhead only in a figure, so the statement is qualitative; the HyperEnclave per-benchmark SPEC values could not be matched to benchmark names from the extracted text.

## Open questions

- What does the FTC862 walker actually cache? A same-machine PMU comparison of pkvm versus nvhe (l2d_tlb_refill, l1d and l2d cache events, mem_access, stall_backend per access in the random test) would show whether TLB-miss counts are identical and how many extra reads each walk makes (+1, +2 or +5).
- What are the real host stage-2 leaf sizes on the N90 for the physical pages backing the benchmark and its page tables (1 GiB, 2 MiB or 4 KiB)? A host stage-2 dump or the hyp stats would settle the premise of item 5.
- Does the number of TLB misses per access differ between pkvm and the baselines (IPA entries competing for TLB capacity, as Gandhi et al. saw on Intel), or only the cost per miss?
- Which mechanism produces the bimodal 8 MB sequential results on the N90: page-colour conflicts, physical contiguity and prefetch at 4 KiB boundaries, or the load-governed NoC/DDR frequency scaling present in the kernel tree? The state of /sys/class/devfreq during the June runs was not recorded.
- Figure 8: which stage-2 granule did each guest configuration use? The guest fault path in this tree can install 2 MiB blocks for protected guests when the VMM mapping is large (klinux arch/arm64/kvm/mmu.c:1773-1791), and the literature shows nested page size is a first-order effect on guest TLB-miss cost (SeKVM 35-50%, Bhargava 21-43% fewer misses); the internal worklog instead suspects a different platform state. Unresolved.
- Does the current issue of DDI 0487 still carry the (S1+1)*(S2+1)-1 note and the same TLB caching text, and under which rule identifiers?

## Tables

Legend: S = <scratch>/wf1/arch-literature ; K = klinux ; L = kylin-lmbench ; ARM = S/armarm/DDI0487E_a_searchtext.txt (full text of ARM DDI 0487E.a, ID070919).

### Table 1. Arm ARM rules used (DOCUMENTED; ARM DDI 0487E.a)

| # | Topic | Section, page | ARM text line | Verbatim |
|---|---|---|---|---|
| 1 | Two stages | D5.2.1, D5-2513 | 54550 | "Stage 1 maps an input VA to an output IPA. — Stage 2 maps an input IPA to an output PA." |
| 2 | Stage-1 table addresses are IPAs | D5.2.5, D5-2534 | 55071 | "For EL1&0, when EL2 is enabled, stage 1 translations, the output address held in the TTBR_ELx, and any translation table base address returned by a translation table descriptor, is the IPA of the base of the translation table. This means that if stage 2 address translation is enabled, each of these OAs is subject to second stage translation." |
| 3 | Lookup count | D5.2.5 Note, D5-2534 | 55073-55075 | "...if the caching of translation table entries is ineffective, a VA to PA address translation with two stages of translation can give rise to multiple translation table lookups. The number of lookups required is given by the following equation: (S1+1)*(S2+1) - 1 Where ... S1 is the number of levels of lookup required for a stage 1 translation, and S2 is the number of levels of lookup required for a stage 2 translation." |
| 4 | Recursive stage 2 on descriptor fetch | D5.8.2, D5-2625 | 57434 | "...the descriptor address is in the IPA address space, and is subject to a stage 2 translation to obtain the required PA. This stage 2 translation requires a recursive entry to the fault checking sequence." |
| 5 | HCR_EL2.PTW | D13.2, D13-3081 | 68422 | "In the EL1&0 translation regime, a translation table access made as part of a stage 1 translation table walk is subject to a stage 2 translation." |
| 6 | Concatenated stage-2 tables | D5.2.4, D5-2532 | 55023, 55029 | "For stage 2 address translations, for the initial lookup, up to 16 translation tables can be concatenated." Example D5-2: "to extend the IA width to 40 bits and resolve IA[39:30] with the first lookup: • Two translation tables are concatenated, giving a total size of 8KB." |
| 7 | T0SZ/SL0 table, 4KB granule | D5.2.6 Table D5-13, D5-2537/2538 | 55185 | Row "initial lookup level 1 (SL0 value 1)": one table T0SZ 25-33; two tables T0SZ 24, IA[39:12] |
| 8 | Block sizes | D5.3, D5-2565 | 55959 | "A block descriptor: • In a level 1 table describes the mapping of the associated 1GB input address range. • In a level 2 table describes the mapping of the associated 2MB input address range." |
| 9 | What a TLB may hold | D5.9, D5-2632 | 57596 | "The Arm architecture permits TLBs to hold any translation table entry that does not directly cause a Translation fault, an Address size fault, or an Access flag fault." |
| 10 | TLB form unspecified | D5.9.2, D5-2634 | 57649 | "The Arm architecture does not specify the exact form of the TLB structures for any design." |
| 11 | Walk caches | D5.9.2 Note, D5-2634 | 57656 | "A TLB can hold a translation table entry that does not itself generate a Translation fault but that points to a subsequent table in the translation table walk. This is referred to as intermediate caching of TLB entries." |
| 12 | Stage-2 entries are cacheable | D5.10.1, D5-2638 | 57719 | "...the entries that can be cached include: • Entries in translation tables that point to subsequent tables to be used in that stage of translation. • Stage 2 translation table entries used as part of a stage 1 translation table walk • Stage 2 translation table entries used to translate the output address of the stage 1 translation." |
| 13 | Three kinds of structure | D5.10.1, D5-2638 | 57721 | "...such caching structures might contain: • Entries containing information from stage 1 translation table entries, at any level of the translation table walk. • Entries containing information from stage 2 translation table entries, at any level of the translation table walk. • Entries that combine information from stage 1 and stage 2 translation table entries, at any level of the translation table walk." |
| 14 | Splintering | D5.10.1 Note, D5-2638 | 57727 | "Where stage 1 information has been cached in multiple TLB entries, as could occur from splintering a page when caching in the TLB, then the invalidation must apply to each cached entry..." |
| 15 | Stage-2-only invalidation | D5.10.1, D5-2639 | 57731-57733 | "Required to apply to stage 2 entries only, then: — It is not required to apply to caching structures that combine stage 1 and stage 2 translation table entries. — It must apply to caching structures that contain information only from stage 2 translation table entries." |
| 16 | TLB entry size | D5.10.2, D5-2646 | 57887 | "The Arm architecture does not dictate the form in which the TLB stores translation table entries. However, when a TLB maintenance instruction is executed, the minimum size of the table entry that is invalidated from the TLB must be at least the size that appears in the translation table entry." |
| 17 | IPAS2 scope and sequence | D5.10.2, D5-2648 and D5-2650 | 57937, 57994 | "...Are held in TLB caching structures holding stage 2 only entries." ; "TLBI IPAS2E1, Xt DSB TLBI VMALLE1" |
| 18 | Stage 2 disabled | D5.2.9, D5-2559 | 55820 | "When stage 2 address translation is disabled: • The IPA output from the stage 1 translation maps flat to the PA." |
| 19 | VHE host regime | D5.2.1, D5-2515 | 54597 | "When ARMv8.1-VHE is implemented, this regime has a single stage of translation, stage 1, that maps VAs to PAs..." |

### Table 2. Memory references per TLB miss with no caching (INFERRED from rule 3; S1 = 4 levels, 4 KiB leaf)

| Configuration | S2 lookups per IPA | Total = (S1+1)(S2+1)-1 | Extra vs single stage |
|---|---|---|---|
| Single stage (kvmoff and VHE host: EL2&0; nVHE host: EL1&0 with stage 2 disabled) | 0 | 4 | 0 |
| Two-stage, stage-2 leaf = level-1 1 GiB block (start level 1) | 1 | 9 | +5 |
| Two-stage, stage-2 leaf = level-2 2 MiB block | 2 | 14 | +10 |
| Two-stage, stage-2 leaf = level-3 4 KiB page (3-level stage 2, 40-bit IPA) | 3 | 19 | +15 |
| Two-stage, 4-level stage 2 (start level 0), 4 KiB page | 4 | 24 | +20 |

### Table 3. Item 5: extra references per TLB miss for a pKVM host process, stage 2 = 1 GiB blocks (INFERRED)

| Caching assumption | Native refs | Two-stage refs | Extra refs | Extra time at 1.9 GHz if each is a 4-cycle L1 hit (assumption, not documented for FTC862) |
|---|---|---|---|---|
| (i) No caching at all (no walk cache, no IPA cache) | 4 | 9 | +5 | about 20 cycles = 10.5 ns |
| Stage-1 walk cache hit that yields only the IPA of the level-3 table; no stage-2 caching | 1 | 3 | +2 | about 8 cycles = 4.2 ns |
| Stage-1 walk cache hit that yields the PA of the level-3 table (as in Cortex-A53); no IPA->PA cache | 1 | 2 | +1 | about 4 cycles = 2.1 ns |
| (ii) Ideal: walk cache (PA) plus IPA->PA cache hit for the output address | 1 | 1 | 0 | 0 |
| No stage-1 walk cache but ideal IPA->PA cache | 4 | 4 | 0 | 0 |
| MEASURED for comparison: pkvm minus baselines, random access at 8 MB and above | | | | +7.0 ns = 13.4 cycles per access |

### Table 4. MEASURED: lat_mem_rd -t (random, stride 16), medians of 10 iterations, ns

| Size | kvmoff | nvhe | vhe | pkvm | pkvm-kvmoff ns | % | cycles at 1.9 GHz |
|---|---|---|---|---|---|---|---|
| 1 MB | 19.41 | 19.48 | 19.48 | 19.43 | +0.02 | +0.11 | 0.04 |
| 2 MB | 20.68 | 20.75 | 20.73 | 20.88 | +0.21 | +1.00 | 0.39 |
| 4 MB | 47.59 | 47.69 | 47.46 | 49.31 | +1.73 | +3.63 | 3.28 |
| 6 MB | 67.14 | 67.35 | 67.37 | 72.59 | +5.45 | +8.12 | 10.36 |
| 8 MB | 112.54 | 112.60 | 112.33 | 119.60 | +7.05 | +6.26 | 13.40 |
| 12 MB | 154.65 | 154.81 | 154.65 | 161.68 | +7.03 | +4.54 | 13.35 |
| 16 MB | 168.54 | 168.56 | 169.71 | 176.28 | +7.74 | +4.59 | 14.70 |
| 32 MB | 180.61 | 180.78 | 182.72 | 188.66 | +8.05 | +4.46 | 15.29 |
| 64 MB | 185.23 | 185.05 | 185.43 | 191.73 | +6.50 | +3.51 | 12.34 |

64 MB by means (the paper's statistic): kvmoff 182.21, pkvm 188.13, +5.93 ns = +3.25%. Figure 7 bars reproduced from raw means (vs kvmoff / vs VHE / vs nVHE): LLC Bnd +3.55 / -3.02 / +2.87 %; Main Mem +0.29 / -3.46 / +1.06 %; Rand Mem +3.25 / +3.82 / +3.88 %.

### Table 5. MEASURED: tests of pkvm against each baseline (n = 10 per mode)

| Metric | Baseline | Mean diff ns (%) | Welch t, df, p | Mann-Whitney permutation p | Hodges-Lehmann shift ns | Bootstrap 95% CI of median diff ns |
|---|---|---|---|---|---|---|
| LLC Bnd: sequential stride 256, 8 MB | kvmoff | +0.397 (+3.55) | +0.86, 17.9, 0.40 | 0.22 | +0.24 | [-1.50, +2.09] |
| | nvhe | +0.324 (+2.87) | +0.64, 17.8, 0.53 | 0.25 | +0.21 | [-1.71, +2.35] |
| | vhe | -0.361 (-3.02) | -0.85, 16.9, 0.41 | 0.53 | -0.09 | [-1.92, +0.93] |
| Main Mem: sequential stride 256, 64 MB | kvmoff | +0.030 (+0.29) | +0.30, 17.5, 0.77 | 0.74 | +0.03 | [-0.28, +0.32] |
| | nvhe | +0.109 (+1.06) | +1.16, 17.9, 0.26 | 0.19 | +0.12 | [-0.20, +0.40] |
| | vhe | -0.373 (-3.46) | -2.73, 13.7, 0.017 | 0.018 | -0.36 | [-0.78, -0.01] |
| Rand Mem: random stride 16, 64 MB | kvmoff | +5.93 (+3.25) | +1.76, 16.2, 0.098 | 0.011 | +6.29 | [-0.09, +15.32] |
| | nvhe | +7.03 (+3.88) | +1.91, 17.7, 0.072 | 0.009 | +6.61 | [+0.45, +16.85] |
| | vhe | +6.93 (+3.82) | +1.80, 18.0, 0.089 | 0.009 | +6.39 | [-0.14, +15.45] |
| | pooled 30 | | | 0.001 | +6.43 | |
| Random stride 16, 8 MB | kvmoff | +7.05 (+6.26) | +29.7, 16.6, 8.6e-16 | 2e-5 (U = 100 of 100) | +6.99 | [+6.27, +7.73] |
| | nvhe | +6.97 (+6.18) | +32.4, 13.4, 3.8e-14 | 2e-5 | +6.88 | [+6.44, +7.46] |
| | vhe | +7.28 (+6.48) | +36.2, 10.9, 1.0e-12 | 2e-5 | +7.18 | [+6.78, +7.73] |
| Random stride 16, 4 MB | kvmoff | +1.61 (+3.37) | +10.7, 14.6, 2.7e-8 | | | |
| Random stride 16, 1 MB | kvmoff | +0.003 (+0.01) | +0.03, 17.7, 0.97 | | | |

Sorted iteration values at the LLC boundary (ns): kvmoff 10.06 10.19 10.35 10.50 10.65 10.98 12.21 12.24 12.37 12.49; nvhe 9.93 9.98 10.02 10.30 10.55 12.27 12.31 12.35 12.43 12.62; vhe 10.30 10.92 11.47 11.73 12.45 12.45 12.47 12.57 12.62 12.63; pkvm 10.10 10.25 10.56 10.70 11.77 12.47 12.50 12.52 12.56 12.57. Within-mode CV of sequential stride 256: 4 MB 0.07-0.15%; 6 MB 0.9-1.7%; 8 MB 6.9-10.6%; 12 MB 2.2-10.3%; 16 MB 2.4-2.9%; 64 MB 2.0-3.5%.

### Table 6. MEASURED: sequential lat_mem_rd at 64 MB by stride, medians, ns

| Stride | kvmoff | nvhe | vhe | pkvm | pkvm minus median of baselines | Spread of the three baseline medians |
|---|---|---|---|---|---|---|
| 64 | 4.217 | 4.230 | 4.328 | 4.274 | +0.044 | 0.111 |
| 128 | 9.034 | 9.014 | 9.261 | 9.180 | +0.147 | 0.247 |
| 256 | 10.357 | 10.241 | 10.781 | 10.345 | -0.012 | 0.540 |
| 512 | 9.573 | 9.517 | 9.926 | 9.789 | +0.216 | 0.409 |
| 1024 | 10.473 | 10.518 | 11.066 | 10.899 | +0.381 | 0.593 |

### Table 7. Kessler-Hill binomial model applied to the L3 (8 MiB, 16-way, 8192 sets, 64 B lines, 4 KiB pages: 128 colours x 16 pages)

| Footprint | Pages | Expected share of pages in over-subscribed colours, random placement | Unavoidable share | Unnecessary share | SD over 4000 random placements |
|---|---|---|---|---|---|
| 4 MiB | 1024 | 0.08% | 0 | 0.08% | |
| 6 MiB | 1536 | 2.02% | 0 | 2.02% | 0.53% |
| 7 MiB | 1792 | 5.13% | 0 | 5.13% | 0.67% |
| 8 MiB | 2048 | 9.88% | 0 | 9.88% | 0.67% |
| 9 MiB | 2304 | 15.75% | 11.11% | 4.64% | 0.57% |
| 12 MiB | 3072 | 33.64% | 33.33% | 0.31% | 0.16% |
| 16 MiB | 4096 | 50.00% | 50.00% | 0.00% | |

L2 (512 KiB, 8-way, 16 colours x 8 pages): 13.5% at 0.5 MiB, 0.7% at 0.25 MiB.

### Table 8. Verified literature: nested walks and hosts under stage 2 (every item opened and read)

| Key | Citation | Verified quantitative claim | Opened |
|---|---|---|---|
| Bhargava08 | R. Bhargava, B. Serebrin, F. Spadini, S. Manne. Accelerating two-dimensional page walks for virtualized systems. ASPLOS XIII, 2008, pp. 26-35. DOI 10.1145/1346281.1346286 | nm+n+m references; uncached 2D walk 3.9-4.6x a native walk; +15-38% from nested page-walk cache, +3-7% nested TLB, +3-22% and 21-43% fewer TLB misses from 2 MiB nested pages; TLB must use the smaller page size | pages.cs.wisc.edu/~remzi/Classes/838/Spring2013/Papers/p26-bhargava.pdf; Crossref |
| Barr10 | T. W. Barr, A. L. Cox, S. Rixner. Translation caching: skip, don't walk (the page table). ISCA 2010, pp. 48-59. DOI 10.1145/1815961.1815970 | 4.00 -> at most 1.13 memory accesses per walk with an MMU cache; with nested-TLB hits the accesses equal native | cs.rice.edu/CS/Architecture/docs/barr-isca10.pdf; Crossref |
| Gandhi14 | J. Gandhi, A. Basu, M. D. Hill, M. M. Swift. Efficient Memory Virtualization: Reducing Dimensionality of Nested Page Walks. MICRO-47, 2014, pp. 178-189. DOI 10.1109/MICRO.2014.37 | 4 vs up to 24 references; cycles per TLB miss 2.4x / 1.5x / 1.6x for 4K+4K / 4K+2M / 4K+1G; graph500 28% -> 113% (4K+4K), 53% (4K+2M); TLB misses 1.29-1.62x | pages.cs.wisc.edu/~swift/papers/micro14-virtualization.pdf; Crossref |
| Dall16 | C. Dall, S.-W. Li, J. T. Lim, J. Nieh, G. Koloventzos. ARM Virtualization: Performance and Architectural Implications. ISCA 2016, pp. 304-316. DOI 10.1109/ISCA.2016.35 | KVM/ARM disables stage 2 while the host runs; hypercall 6,500 cycles (KVM ARM) vs 376 (Xen ARM) | cs.columbia.edu/~cdall/pubs/isca2016-dall.pdf; Crossref |
| Dall17 | C. Dall, S.-W. Li, J. Nieh. Optimizing the Design and Implementation of the Linux ARM Hypervisor. USENIX ATC 2017, pp. 221-233 | EL2 can 'completely disable the stage 2 translations when running the hypervisor OS kernel' | usenix.org/system/files/conference/atc17/atc17-dall.pdf |
| Simner22 | B. Simner, A. Armstrong, J. Pichon-Pharabod, C. Pulte, R. Grisenthwaite, P. Sewell. Relaxed virtual memory in Armv8-A. ESOP 2022, LNCS 13240, pp. 143-173. DOI 10.1007/978-3-030-99336-8_6 | 'up to 24 with both stages enabled'; TLBs may cache individual entries and partial or complete translations; pKVM encapsulates the Linux kernel in a stage-2 map built on demand | arxiv.org/pdf/2203.00642 (extended version); Crossref |
| Jia22 | Y. Jia, S. Liu, W. Wang, Y. Chen, Z. Zhai, S. Yan, Z. He. HyperEnclave: An Open and Cross-platform Trusted Execution Environment. USENIX ATC 2022, pp. 437-454 | Demoted primary OS: under 1% in most benchmarks; lmbench page fault +1.15%, ctxsw +2.88%, fork +0.82%; kernel build +0.50%; SPEC CPU 2017 -0.3% to +3.7% | usenix.org/system/files/atc22-jia-yuekai.pdf |
| VantHof22 | A. Van't Hof, J. Nieh. BlackBox: A Container Security Monitor for Protecting Containers on Untrusted Operating Systems. OSDI 2022, pp. 683-700 | Arm, lmbench 3.0-a9, identity stage 2 for the OS with 2 MiB blocks: page fault is the one microbenchmark with noticeable overhead from the OS stage 2 (qualitative; bar values not in text) | usenix.org/system/files/osdi22-vant-hof.pdf |
| McCune10 | J. M. McCune, Y. Li, N. Qu, Z. Zhou, A. Datta, V. Gligor, A. Perrig. TrustVisor: Efficient TCB Reduction and Attestation. IEEE S&P 2010, pp. 143-158. DOI 10.1109/SP.2010.17 | Identity NPT with 2 MiB pages; lmbench mostly under 6%, fork/exec/ctxsw 34/27/15%; SPECint mostly under 3%, mcf 29% | netsec.ethz.ch/publications/papers/MLQZDGP2010.pdf; Crossref |
| Vasudevan13 | A. Vasudevan, S. Chaki, L. Jia, J. McCune, J. Newsome, A. Datta. Design, Implementation and Verification of an eXtensible and Modular Hypervisor Framework. IEEE S&P 2013, pp. 430-444. DOI 10.1109/SP.2013.36 | Most SPEC under 3%; 2 MiB nested mappings outperform 4 KiB | ieee-security.org/TC/SP2013/papers/4977a430.pdf; Crossref |
| Li19 | S.-W. Li, J. S. Koh, J. Nieh. Protecting Cloud Virtual Machines from Hypervisor and Host Operating System Exploits. USENIX Security 2019, pp. 1357-1374 | Host under flat identity stage 2; 5-19% on microbenchmarks; host-native overhead not reported | usenix.org/system/files/sec19-li-shih-wei.pdf |
| Li21 | S.-W. Li, X. Li, R. Gu, J. Nieh, J. Z. Hui. A Secure and Formally Verified Linux KVM Hypervisor. IEEE S&P 2021, pp. 1782-1799. DOI 10.1109/SP40001.2021.00049 | No stage-2 huge pages: +35-50% overhead (hackbench, MySQL, MongoDB); 17-28% on microbenchmarks | cs.columbia.edu/~nieh/pubs/ieeesp2021_kvm.pdf; Crossref |
| Martins23 | J. Martins, S. Pinto. Shedding Light on Static Partitioning Hypervisors for Arm-based Mixed-Criticality Systems. RTAS 2023, pp. 40-53. DOI 10.1109/RTAS58335.2023.00011 | Under 1% with 2 MiB stage-2 superpages; up to 7% without; colouring costs up to about 20% | arxiv.org/pdf/2303.11186; Crossref |
| Wei24 | H.-J. Wei, L.-K. Lin, C.-Y. Lin, S.-W. Li. Measuring and Optimizing the Performance of the Android Virtualization Framework. ACM SAC 2024, pp. 1533-1535. DOI 10.1145/3605098.3636097 | pVM vs VM on Pixel 6 Pro: hypercall 1,641 vs 1,497 cycles; block I/O 25% worse, network 75% worse; no host-side number | liswei.sh/files/sac24wei.pdf; Crossref |
| AOSP | Android Open Source Project, AVF architecture | Host stage 2 is identity-mapped, allowing large mappings and reducing TLB pressure; no numbers | source.android.com/docs/core/virtualization/architecture |
| A53TRM | Arm Cortex-A53 MPCore Processor TRM, DDI 0500J | 512-entry main TLB, 64-entry walk cache (stores PA), 64-entry IPA cache | NXP community mirror of the Arm PDF |
| ArmPatent | R. Abhishek (Arm Ltd). US 10,649,907 B2, granted 2020-05-12 | Final TLB page size is the smaller of the first-stage and second-stage page sizes | patents.google.com/patent/US10649907B2/en |

### Table 9. Verified literature: measurement instability, page placement, lmbench

| Key | Citation | Verified claim | Opened |
|---|---|---|---|
| Kessler92 | R. E. Kessler, M. D. Hill. Page placement algorithms for large real-indexed caches. ACM TOCS 10(4), 1992, pp. 338-359. DOI 10.1145/138873.138876 | Up to 30% unnecessary conflicts; careful mapping removes 10-20% (direct-mapped), 4-10% (2-way), 2-5% (4-way) of misses; random mappings cause miss bursts and variance | pages.cs.wisc.edu/~markhill/papers/tocs92_coloring_original.pdf; Crossref |
| McVoy96 | L. McVoy, C. Staelin. lmbench: Portable Tools for Performance Analysis. USENIX 1996 Annual Technical Conference (pages not verified) | Results vary up to 30%, attributed to different physical pages and cache collisions; TLB-miss measurement with lat_mem_rd is problematic | usenix.org/legacy/publications/library/proceedings/sd96/full_papers/mcvoy.pdf |
| lmbench3 docs | C. Staelin, Micro-architecture analysis (draft in lmbench 3.0-a9), man page lat_mem_rd(8), hbench-REBUTTAL, lib_mem.c | Collisions grow as memory nears the cache size; page placement is outside the benchmark's control; random mode takes a TLB miss per page | L/doc/memhier.ms:939-954, 1119-1135; L/doc/lat_mem_rd.8; L/hbench-REBUTTAL:139-145; L/src/lib_mem.c:222-234 |
| Brown97 | A. B. Brown, M. I. Seltzer. Operating system benchmarking in the wake of lmbench: a case study of the performance of NetBSD on the Intel x86 architecture. SIGMETRICS 1997, pp. 214-224. DOI 10.1145/258612.258690 | Bimodal distribution from cache conflicts; conflicts likely even below cache size with random page assignment; 5% standard deviations | seltzer.com/assets/publications/Operating-System-Benchmarking-in-the-Wake-of-Lmbench.pdf; Crossref |
| Kalibera05 | T. Kalibera, L. Bulej, P. Tuma. Benchmark Precision and Random Initial State. SPECTS 2005 (pages not verified) | Physical page assignment is not reproducible; between-run to within-run SD ratio 25.8 / 94.7 / 35.9 | cs.kent.ac.uk/pubs/2005/3143/content.pdf |
| Hocko10 | M. Hocko, T. Kalibera. Reducing performance non-determinism via cache-aware page allocation strategies. WOSP/SIPEW 2010, pp. 223-234. DOI 10.1145/1712605.1712640 | Linux default allocation is cache-unaware; 30% between executions; colouring reduces non-determinism | research.spec.org/icpe_proceedings/2010/p223.pdf; Crossref |
| Mytkowicz09 | T. Mytkowicz, A. Diwan, M. Hauswirth, P. F. Sweeney. Producing wrong data without doing anything obviously wrong! ASPLOS XIV, 2009, pp. 265-276. DOI 10.1145/1508244.1508275 | Layout bias averages 2-8% (link order), 1-4% (environment size) | users.cs.northwestern.edu/~robby/courses/322-2013-spring/mytkowicz-wrong-data.pdf; Crossref |
| Curtsinger13 | C. Curtsinger, E. D. Berger. STABILIZER: statistically sound performance evaluation. ASPLOS 2013, pp. 219-228. DOI 10.1145/2451116.2451141 | One binary is one layout sample; -O3 vs -O2 indistinguishable from noise | people.cs.umass.edu/~emery/pubs/stabilizer-asplos13.pdf; Crossref |
| Vavouliotis22 | G. Vavouliotis, G. Chacon, L. Alvarez, P. V. Gratz, D. A. Jimenez, M. Casas. Page Size Aware Cache Prefetching. MICRO 2022, pp. 956-974. DOI 10.1109/MICRO56248.2022.00070 | Physical-address prefetchers do not prefetch beyond 4 KiB page boundaries because physical contiguity is not guaranteed | gvavou5.github.io/Documents/Vavouliotis_MICRO22.pdf; Crossref |
| David11 | H. David, C. Fallin, E. Gorbatov, U. R. Hanebutte, O. Mutlu. Memory power management via dynamic voltage/frequency scaling. ICAC 2011, pp. 31-40. DOI 10.1145/1998582.1998590 | Memory frequency chosen from bandwidth utilisation; latency of dependent-load misses depends on memory frequency | users.ece.cmu.edu/~omutlu/pub/memory-dvfs_icac11.pdf; Crossref |

### Table 10. Not verified (do not cite from this report)

| Item | Reason |
|---|---|
| Pham, Vesely, Loh, Bhattacharjee, MICRO 2015 (page splintering) | every PDF URL returned 404/403 |
| Merrifield and Taheri, VEE 2016 | ACM DL blocked |
| Buell et al., VMware Technical Journal 2013 | seen only as quoted in Gandhi14 |
| Kwon et al., Hypernel, DAC 2018 | search snippets only |
| Dall and Nieh, ASPLOS 2014 | not fetched |
| Current issue of DDI 0487, Cortex-A76 / Neoverse N1 TRMs | Arm site is script-rendered; PDF above the 10 MB fetch limit |
| Any pKVM host-overhead figure from Google, Intel pKVM-IA, or a vendor | none found in opened sources |

### Table 11. Public information on FTC862 / D3000

| Fact | Source | Status |
|---|---|---|
| 8 x FTC862, ARMv8 64-bit (ARM64 and ARM32), hardware virtualization, PSPA 2.0, up to 2.5 GHz | phytium.com.cn/homepage/production/15/ | vendor page, opened |
| D3000M: 8 x FTC862, 'over 2.9 GHz', '二级缓存 4MB', '末级缓存 8MB' | phytium.com.cn/homepage/production/16/ | vendor page, opened twice |
| 'FTC862, 兼容 ARMv8.2 指令集', LLC 8 MB | ZTE product sheet (S/papers/zte-d3000-intro.txt:19-23, 40) | third party |
| MIDR part 0x862 mapped to 'Phytium,FT-D3000' | K/arch/arm64/include/asm/cputype.h:162; K/arch/arm64/kernel/cpuid.c:183 | source code |
| Load-governed frequency scaling of the NoC and of the DDR memory unit | K/drivers/devfreq/phytium_noc.c, phytium_dmu.c, Kconfig:160-176 | source code |
| L1/L2 TLB sizes, walk cache, IPA cache, L1 latency, cache inclusivity, prefetchers | nothing found | not available |

### Table 12. 中文摘要（论文段落素材，仅引用已核实文献）

在 AArch64 的 EL1&0 转换域启用第二阶段后，TTBR 以及各级第一阶段页表描述符给出的表基址都是 IPA，必须先经第二阶段翻译才能读取；Arm 体系结构手册（ARM DDI 0487E.a，D5.2.5）给出在页表项缓存失效时一次 VA 到 PA 翻译所需的查表次数为 (S1+1)×(S2+1)−1，即 4 级加 4 级为 24 次、4 级加 3 级为 19 次，这与 x86 嵌套分页的 nm+n+m 公式一致[Bhargava08]。KylinX 沿用 pKVM 的做法，使宿主机也运行在第二阶段之下，宿主机第二阶段为恒等映射并尽量使用大块映射[AOSP]；在 40 位 IPA、自第 1 级起始并以 1 GiB 块映射的配置下，每次第二阶段翻译只需一次查表，因此宿主进程的一次 TLB 缺失在完全无缓存时需要 9 次访存（比原生的 4 次多 5 次），在页表遍历缓存与 IPA 到 PA 缓存理想命中时与原生相同。由于组合后的 TLB 项大小取两阶段映射中较小者，宿主机的 4 KiB 页并不因第二阶段而损失 TLB 覆盖范围，开销只体现为每次 TLB 缺失的遍历代价；本文数据与此吻合：随机访问延迟在 1 MB（尚无 TLB 缺失）时与基线无差异（+0.01%，p=0.97），在 8 MB 至 64 MB 时相对 kvmoff、nVHE、VHE 三个基线均稳定多出约 7 ns（1.9 GHz 下约 13 个时钟周期，8 MB 处十次迭代与基线完全分离，64 MB 处秩和检验 p≈0.01），相对开销随工作集增大而由 6.3% 降至约 3.3%–3.5% 只是因为基线延迟本身变大。已有工作表明嵌套页表遍历的代价集中于 TLB 缺失密集的负载：客户机 4 KiB 页配合宿主 1 GiB 页时每次 TLB 缺失的周期数约为原生的 1.6 倍[Gandhi14]；对被降权的主操作系统的直接测量中，HyperEnclave 报告多数基准开销低于 1%，lmbench 缺页 +1.15%、上下文切换 +2.88%[Jia22]，BlackBox 在 Arm 平台上用 lmbench 3.0-a9 观察到仅缺页延迟因第二阶段页表出现可见开销[VantHof22]。LLC 边界（8 MB）处的 +3.55% 不具统计显著性（Welch t 检验 p=0.40，相对 VHE 反而为 −3.0%），该点各模式十次迭代均呈双峰，变异系数为 7%–11%，而 4 MB 处仅约 0.1%。lmbench 的作者早已指出，当工作集接近缓存容量时物理页放置造成的缓存冲突会使结果波动（最高 30%）[McVoy96]，Brown 与 Seltzer 在缓存容量附近同样观察到双峰分布[Brown97]；Kessler 与 Hill 的页放置模型表明不必要的冲突恰在工作集等于缓存容量时最多（按本平台 L3 参数计算，8 MiB 时约 9.9% 的页处于冲突状态，6 MiB 时仅 2.0%）[Kessler92]，Linux 默认的缓存无关页分配以及物理页是否连续还会影响硬件预取能否跨越 4 KiB 页边界[Hocko10][Vavouliotis22]。因此，64 MB 随机访问的 +3.25% 可归因于宿主机处于第二阶段翻译之下所增加的每次 TLB 缺失的遍历代价，而 LLC 边界的 +3.55% 属于缓存容量边界处由物理页布局引起的测量不稳定，不应解释为 KylinX 的固有开销。
