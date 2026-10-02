# 逐条核查结果

每条调查结论交给最多两名独立核查者：一名抛开原有依据，从原始数据、源码或规范重新推导（"重新推导"）；
另一名专门找反例和别的解释（"找反例"）。下表是汇总。"需修正"表示至少一名核查者给出了更准确的表述，
结论文档采用的是修正后的表述；修正后的全文在对应的 `verify-*.md` 里。

| 调查角度 | 条数 | 通过 | 需修正 | 被推翻 | 无法核实 | 未核查 |
|---|---:|---:|---:|---:|---:|---:|
| 宿主机（N90）数据的统计 | 28 | 13 | 15 | 0 | 0 | 0 |
| lmbench 测量语义 | 30 | 16 | 14 | 0 | 0 | 0 |
| 内核与监视器源码 | 28 | 15 | 13 | 0 | 0 | 0 |
| Arm 体系结构规范与文献 | 25 | 12 | 13 | 0 | 0 | 0 |
| 客户机内（N90）数据，图 8 | 23 | 13 | 10 | 0 | 0 | 0 |
| 仓库里已有的分析文档 | 42 | 22 | 20 | 0 | 0 | 0 |
| 补充测量（N80，2026-09-30 下午） | 8 | 4 | 4 | 0 | 0 | 0 |
| 综合结论草稿 | 13 | 5 | 7 | 0 | 1 | 0 |
| 补充测量（N80，2026-09-30 傍晚：实验 R、BG、H、S、V、V2、W） | 15 | 4 | 11 | 0 | 0 | 0 |
| 傍晚实验背后的内核机制 | 7 | 4 | 2 | 1 | 0 | 0 |
| 补充测量（N80，2026-09-30 晚：实验 X、Y、V3、Z） | 8 | 2 | 6 | 0 | 0 | 0 |
| 补充测量与对照测量（N80 和工作站，2026-09-30 夜：实验 N–N5、T2、L2、H2–H6） | 17 | 4 | 13 | 0 | 0 | 0 |
| 补充测量（N80，2026-10-01 凌晨：实验 H7、H8，以及 N90 数据里 8 MB 高值之后的读数） | 4 | 2 | 2 | 0 | 0 | 0 |
| 互连调频实验（N80，2026-10-02，用户执行：实验 G5） | 4 | 1 | 3 | 0 | 0 | 0 |
| 合计 | 252 | 117 | 133 | 1 | 1 | 0 |

## 宿主机（N90）数据的统计

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| host-stats#1 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The three paper numbers are means over 10 iterations of these rows: LLC Bnd = bench lat_mem_rd_load, variant stride256_sz8.00000MB: kvmoff 11.2029, nv… |
| host-stats#2 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | The metric definitions and the estimator used by the paper are the ones above: the figure pipeline names these three variants, and the paper states th… |
| host-stats#3 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The long-format CSVs agree value for value with the raw lmbench reports, and every configuration was measured in one single boot session per campaign … |
| host-stats#4 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The LLC-boundary metric is two-valued, not unimodal. CONFIG.host, 40 pooled values: 17 in 9.93-10.98 ns (mean 10.37, sd 0.32) and 23 in 11.47-12.63 ns… |
| host-stats#5 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | At the LLC boundary the pkvm-minus-kvmoff difference is not distinguishable from zero: d(mean) = +0.397 ns (+3.55 %), Welch t = 0.86, df 17.9, p = 0.4… |
| host-stats#6 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The pkvm-kvmoff difference at the LLC boundary is smaller than differences among the configurations that have no host stage-2: vhe - kvmoff = +0.758 n… |
| host-stats#7 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The +0.397 ns is a mixture effect, not a shift of the values: +0.387 ns comes from pkvm having 6 rather than 4 iterations on the high value, +0.010 ns… |
| host-stats#8 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | The neighbouring cells show no consistent pkvm effect either. At 8 MB the other strides are two-valued as well and pkvm - kvmoff is -5.00 % (stride 12… |
| host-stats#9 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The standalone campaign and the session-level view confirm this. Standalone 8 MB: pkvm - kvmoff = +0.074 ns (+0.65 %), Welch p = 0.89, bootstrap CI [-… |
| host-stats#10 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Which of the two values a measurement takes is decided per measurement, not by a slowly varying state of the session: the 8 MB stride-256 value is unc… |
| host-stats#11 | INFERRED | 通过 | 找反例：通过；重新推导：通过 | The host data alone do not identify the physical cause of the two values. It is an arithmetic fact that 8 MiB at stride 256 touches 32768 lines, which… |
| host-stats#12 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Random access: the pkvm-minus-baseline difference becomes distinguishable at 3 MB (768 pages): d(median) = +0.709 ns (+1.94 %) vs kvmoff, bootstrap CI… |
| host-stats#13 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | The random-access difference saturates. Difference of medians vs kvmoff for 8, 12, 16, 24, 32, 48, 64 MB: +7.05, +7.03, +7.74, +8.36, +8.05, +6.90, +6… |
| host-stats#14 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | At 64 MB the effect is real but the paper's own estimator is imprecise. Mean: +5.93 ns (+3.25 %), bootstrap CI [-0.74, +11.75] ns = [-0.4 %, +6.6 %], … |
| host-stats#15 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The standalone campaign reproduces the random-access increment: differences of medians vs kvmoff / nvhe / vhe are +2.04 / +2.35 / +2.25 ns at 4 MB (+4… |
| host-stats#16 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | With the boot session as the unit of replication the random-access increment stands far outside the between-session spread: at 64 MB the six no-stage-… |
| host-stats#17 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | Per-iteration outliers occur in all four configurations and are almost all fast. CONFIG.host, sizes >= 12 MB (60 cells per configuration): kvmoff 16 f… |
| host-stats#18 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | A discrete fast state of random access exists on hosts without stage-2. The extra nVHE session n90-nvhe-noisy-full is faster than the clean sessions i… |
| host-stats#19 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Because a state that is 18-35 % faster from 3 MB upward occurs on an nVHE host with no pVM, and sporadically in kvmoff, nvhe, vhe and pkvm hosts, a ra… |
| host-stats#20 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The pkvm increment appears to persist inside the fast state: the pkvm runs that reach it sit at 140.37 ns (16 MB, standalone run 3) and 151.46 ns (32 … |
| host-stats#21 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Sequential access at 64 MB: pkvm minus kvmoff by stride 16, 32, 64, 128, 256, 512, 1024 is -0.000, +0.003, +0.050, +0.175, +0.030, +0.262, +0.368 ns (… |
| host-stats#22 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Taken at face value against kvmoff or nvhe, the implied extra cost per sequential page crossing is 1.1-1.9 ns at 64 MB, 2.1-3.5 ns at 32 MB and 1.2-4.… |
| host-stats#23 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | The sequential stride trend cannot be attributed to the host stage-2 with these data, because sessions without stage-2 show the same kind of trend at … |
| host-stats#24 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The paper's Main Mem figure (+0.29 %) is the stride-256 point, where the difference is indistinguishable from zero (Welch p = 0.77, bootstrap CI [-0.1… |
| host-stats#25 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Verdict. Of the two highlighted numbers, the 64 MB random-access +3.25 % reflects a systematic effect of protected mode (robust size about +6.2 to +7.… |
| host-stats#26 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The size profile of the random-access increment is what a fixed extra cost per page-table walk would produce: no difference while the pages of the cha… |
| host-stats#27 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Side result for the two fault metrics named in the same paper sentence: minor page-fault latency is higher under pkvm in both campaigns (CONFIG.host +… |
| host-stats#28 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Two statements in an older internal document are not supported by the raw data: it lists 'LLC 8MB seq' as +12.1 % for pkvm and summarises sequential a… |

## lmbench 测量语义

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| lmbench-semantics#1 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Commands: 'Memory load latency' = lat_mem_rd -P 1 64 16 32 64 128 256 512 1024 and 'Random load latency' = lat_mem_rd -t -P 1 64 16, run once per lmbe… |
| lmbench-semantics#2 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：通过 | Size grid: 33 sizes from 512 B to 64 MiB (x2 below 1 KiB, +1 KiB up to 4 KiB, then +1/4 of the next power of two, i.e. ... 3, 4, 6, 8, 12, 16, 24, 32,… |
| lmbench-semantics#3 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Process model: every (stride,size) point is measured in its own forked child that allocates its own buffer, malloc(maxlen + 2 pages) = 64 MiB + 8 KiB … |
| lmbench-semantics#4 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | The chain is rebuilt before every timed interval: benchmp_interval calls initialize(iterations,..) and then start(); stride_initialize and thrash_init… |
| lmbench-semantics#5 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Sequential pattern (stride_initialize): addr[i] -> addr[i+stride] over [0,range), wrapping to addr[0]. One lap = range/stride loads visiting range/409… |
| lmbench-semantics#6 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Random pattern (thrash_initialize, all sizes that are multiples of 4096): it uses the FIRST size/4096 entries of a random permutation of ALL 16384 pag… |
| lmbench-semantics#7 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | TLB consequences. Sequential order costs at most one TLB miss per page (stride/4096 per load: 0.4% at stride 16, 6.25% at stride 256, 25% at stride 10… |
| lmbench-semantics#8 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Prefetching: the sequential test is a prefetcher-throughput measurement, the random test is not prefetchable (the next address is known only when the … |
| lmbench-semantics#9 | INFERRED | 通过 | 找反例：通过；重新推导：通过 | Page-table footprint: a sequential run of S bytes uses S/2MiB contiguous leaf tables and S/32KiB PTE cache lines (8 MiB: 4 tables, 256 lines; 64 MiB: … |
| lmbench-semantics#10 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Reported value: each printed number is the MINIMUM over 11 timed intervals (TRIES = 11) of elapsed time per load, every interval at least 95 ms (resca… |
| lmbench-semantics#11 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The four CSVs behind Figure 7 are byte-identical to a fresh parse of the raw iter1..10 reports. |
| lmbench-semantics#12 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Controls applied to the host runs: whole lmbench script pinned with taskset -c 0; all 8 cpufreq policies set to governor performance with min = max = … |
| lmbench-semantics#13 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Each host configuration is ONE boot: its 10 iterations ran back to back starting 5-7 minutes after boot (vhe 06-03 22:20 to 00:03, kvmoff 06-04 00:11 … |
| lmbench-semantics#14 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：通过 | Not controlled and not recorded: physical frame placement (no pagemap dump, no drop_caches or compaction, page cache deliberately not flushed), page c… |
| lmbench-semantics#15 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Figure 7 memory-latency bars are the PAPER_TABLE rows of the xlsx builder, in the same order: Prot Fault = lat_sig prot; Page Fault = lat_pagefault mi… |
| lmbench-semantics#16 | INFERRED | 通过 | 找反例：通过；重新推导：通过 | Cache arithmetic: a page-aligned buffer walked with stride s touches 4096/s line offsets per page (64 for s <= 64), so it reaches colours x 4096/s set… |
| lmbench-semantics#17 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Measured kvmoff curve vs the arithmetic: latency leaves the L1 plateau (2.223-2.224 ns) between 64 and 96 KiB for every stride (the 64 KiB point itsel… |
| lmbench-semantics#18 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The LLC Bnd point is bimodal in every mode. Pooling the four Figure-7 boots, the second nVHE boot and the four standalone boots (90 samples, stride 25… |
| lmbench-semantics#19 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The mode is decided per child, not per lmbench run: at 8 MiB the number of slow strides (of 5) per (config, iteration) is distributed 1/10/11/12/5/1 o… |
| lmbench-semantics#20 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | Sequential DRAM-regime rows differ between boots that all lack host stage 2: Main Mem (stride 256, 64 MiB) vhe vs kvmoff +3.9% (permutation p = 0.011)… |
| lmbench-semantics#21 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | On the N80 sibling (30 fresh processes per size with physical frame numbers read from pagemap) the fraction of pages in over-subscribed L3 colours at … |
| lmbench-semantics#22 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | The set-overflow model is confirmed in the N90 data at the L1 level, where the colour is a virtual-address bit pair and therefore random in the -t tes… |
| lmbench-semantics#23 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | Random test, pkvm minus the three non-protected modes (medians, ns per load): -0.03 (1 MiB), +0.08 (1.5), +0.16 (2), +0.71 (3), +1.74 (4), +5.30 (6), … |
| lmbench-semantics#24 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The published +3.25% is a blurred version of that offset because it is a mean over iterations containing sporadic fast outliers that occur in every mo… |
| lmbench-semantics#25 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | In sequential page order the extra cost is not visible even though a walk still occurs on every page (N80: l2d_tlb_refill = stride/4096 per load): str… |
| lmbench-semantics#26 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | A whole-boot 'fast state' of the random test exists independent of KVM mode. The second nVHE boot kept as n90-nvhe-noisy (same kernel, cmdline and CON… |
| lmbench-semantics#27 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Figure 8 uses the same two commands inside the x-kernel guest (MB=64, stride-16 rows, mean of 10). The protected-VM random curve (29.0 / 36.0 / 55.3 /… |
| lmbench-semantics#28 | INFERRED | 通过 | 找反例：通过；重新推导：通过 | The cpu0 clock during the day-3 runs was effectively 1.80 GHz, not 1.9: L1 load 2.223 ns, float add 1.11, float mul 1.67, float div 4.45 and double di… |
| lmbench-semantics#29 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | The benchmark repo records uname -r and cmdline but not the kernel config of the measured N90 kernel (6.6.0-73-generic #76-KYLINOS, built 2026-05-15).… |
| lmbench-semantics#30 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Stale or wrong statements in the internal docs: docs/PIPELINE.md:94-99 says BENCHMARK_OS is never set, but configs/CONFIG.host:36-37 sets BENCHMARK_HA… |

## 内核与监视器源码

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| kernel-mechanism#1 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q1 (protected): the host is switched to two-stage translation per CPU by the late_initcall finalize_pkvm -> pkvm_drop_host_privileges -> on_each_cpu(_… |
| kernel-mechanism#2 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q1 (nvhe, vhe, kvm-off): stage-2 is off for the host. nvhe: host HCR_EL2 = HCR_HOST_NVHE_FLAGS (RW,API,APK,ATA; no VM), params vttbr=vtcr=0, and __loa… |
| kernel-mechanism#3 | INFERRED | 通过 | 找反例：通过；重新推导：通过 | kvm-off and vhe are the SAME translation regime for host user code. kvm-arm.mode=none only sets KVM_MODE_NONE; the EL2/VHE decision is taken in __fina… |
| kernel-mechanism#4 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q2: host VTCR_EL2 is built by prepare_host_vtcr -> kvm_get_vtcr(mmfr0, mmfr1, phys_shift) with phys_shift = PARange of the sanitised ID_AA64MMFR0_EL1 … |
| kernel-mechanism#5 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Q2 computed geometry: IPA 40 bits -> T0SZ 24, 3 levels, SL0 1, start level 1, 2 concatenated level-1 pages (1024 entries of 1 GiB each). IPA 44 or 48 … |
| kernel-mechanism#6 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The N90 uses a 40-bit IPA: its boot log prints IPA Size Limit: 40 bits in nvhe, vhe and protected modes (kvm_ipa_limit comes straight from PARange), a… |
| kernel-mechanism#7 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q3: host RAM is mapped EAGERLY. kvm_host_prepare_stage2 (called from __pkvm_init_finalise, before the host is deprivileged) runs prepopulate_host_stag… |
| kernel-mechanism#8 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q3 lazy path and block choice: a host access to an IPA whose stage-2 entry is empty traps to EL2 (handle_host_mem_abort -> host_stage2_idmap), and hos… |
| kernel-mechanism#9 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Q3 what breaks host blocks: only ownership changes and non-default protections. kvm_pgtable_stage2_annotate always sets force_pte, so each page donate… |
| kernel-mechanism#10 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q3 what restores blocks: returning a page to the host (reclaim, hyp-to-host donation) re-installs the default mapping through kvm_pgtable_stage2_map, … |
| kernel-mechanism#11 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | Model of the boot-time host stage-2 on an N90-class memory map (9 memblock regions, 32,704 MiB; layout taken from a same-core D80F3 because no N90 mem… |
| kernel-mechanism#12 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：通过 | A direct EL2 read-out exists only for the sibling N80 running a different kernel with the Rust hypervisor (6.6.30xcore-stat+): 1019 blocks of 1 GiB (9… |
| kernel-mechanism#13 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q3 steady state: an ordinary host memory access never enters EL2. RAM is valid in stage-2 before HCR_EL2.VM is set, so not even a first touch traps; p… |
| kernel-mechanism#14 | DOCUMENTED | 需修正 | 找反例：通过；重新推导：部分成立 | Q4: there is no per-access and no per-context-switch software cost in protected mode. Host HCR_EL2 has no TVM, TTLB, IMO or FMO, so TTBR/ASID writes, … |
| kernel-mechanism#15 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Q4: everything that differs between protected and nvhe on the host path: (1) HCR_EL2.VM=1 with the host VTTBR/VTCR, i.e. hardware two-stage walks and … |
| kernel-mechanism#16 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Host raw data, random page order (stride 16), medians of 10 iterations, pkvm minus the median of the three stage-1-only modes: within -0.12 to +0.15 n… |
| kernel-mechanism#17 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Host raw data, sequential stride 256: pkvm minus baseline is within 0.1 ns up to 6 MB; at 8 MB (the LLC-boundary row) it is +0.71 ns by median but the… |
| kernel-mechanism#18 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Root-cause reading of the two reviewer numbers. The 64 MB random +3.25% is the stage-2 cost: with 4 KiB stage-1 pages the TLB entry size and therefore… |
| kernel-mechanism#19 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | On the N80 (Rust hypervisor, other kernel) the counts of TLB walks were identical in nvhe and protected modes while backend stalls grew, and the extra… |
| kernel-mechanism#20 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q5a regular KVM guest (nvhe or vhe host): user_mem_abort takes the pfn with gup (no pin kept), chooses the mapping size from the VMA (hugetlbfs: PUD o… |
| kernel-mechanism#21 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Q5b/c guests under pKVM (both non-protected and protected): every stage-2 translation fault goes to pkvm_mem_abort. It tops up the per-vCPU memcache, … |
| kernel-mechanism#22 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Q5 at EL2: donation (protected VM) invalidates the host stage-2 entries page by page with owner = guest and maps the range in the guest table as RWX, … |
| kernel-mechanism#23 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Q5 other details: prefault ranges exist in two forms. KVM_PGTABLE_S2_PREFAULT_BLOCK is set on pKVM guest tables as well as on the host table, so a spl… |
| kernel-mechanism#24 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Guest stage-2 geometry: in protected mode kvm_init_stage2_mmu forces phys_shift = kvm_ipa_limit for every VM (40 bits on the N90); otherwise the VMM-r… |
| kernel-mechanism#25 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | For Figure 8: nothing in the hypervisor gives a protected VM larger stage-2 mappings or cheaper walks than a non-protected VM or a regular KVM guest w… |
| kernel-mechanism#26 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Commit history with dates (klad-v11-stable): the Android pKVM series (334 commits touching arch/arm64/kvm, including THP support for pKVM guests, rang… |
| kernel-mechanism#27 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The kernel used for the measurements (uname 6.6.0-73-generic, runs of 2026-06-03 to 06-06) corresponds to release 6.6.0-73.76. In that source CONFIG_X… |
| kernel-mechanism#28 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | C versus Rust differences found in the host memory path: (1) Rust prepopulate also maps MMIO gaps and the IPA tail, C maps RAM only; (2) Rust handle_h… |

## Arm 体系结构规范与文献

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| arch-literature#1 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Item 1a (which addresses need stage 2). In a two-stage EL1&0 regime stage 1 maps VA->IPA and stage 2 maps IPA->PA. The base address in TTBR_EL1 and ev… |
| arch-literature#2 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Item 1b (worst-case count). The Arm ARM states that when caching of translation table entries is ineffective the number of lookups is (S1+1)*(S2+1)-1,… |
| arch-literature#3 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Item 1c (stage-2 geometry). For stage 2 up to 16 translation tables can be concatenated at the initial lookup level; a 40-bit IPA with the 4 KiB granu… |
| arch-literature#4 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Item 1d (what may be cached). The architecture does not specify the form of TLB structures and permits caching any translation table entry that does n… |
| arch-literature#5 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Item 1e (stage-2-only versus combined caches are architecturally distinct). A TLB invalidation that applies to stage-2 entries only is not required to… |
| arch-literature#6 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Item 1f (size of a combined TLB entry). The Arm ARM does not dictate the size at which a TLB stores an entry (it explicitly mentions splintering a pag… |
| arch-literature#7 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Item 1g (example of a real Arm implementation; not FTC862). Cortex-A53 has 10-entry micro TLBs, a 512-entry 4-way main TLB holding combined entries (V… |
| arch-literature#8 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Only the pkvm configuration runs host processes under two-stage translation. With stage 2 disabled the IPA maps flat to the PA; classic KVM/ARM disabl… |
| arch-literature#9 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Premise check for item 5 from source code: the host stage 2 uses the CPU PARange as IPA size; for 40 bits the code yields 3 levels, SL0=1 (start level… |
| arch-literature#10 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Item 5 derivation. Host process with 4-level stage 1 (4 KiB leaf) under a 40-bit, level-1-start stage 2 made of 1 GiB blocks: each stage-2 translation… |
| arch-literature#11 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | Raw host data show a fixed per-access penalty that appears only beyond TLB reach. lat_mem_rd -t (stride 16) medians, pkvm minus kvmoff: 1 MB +0.02 ns … |
| arch-literature#12 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The measured penalty fits the two-stage-walk model but does not pin down the FTC862 walker. lmbench's random mode touches a different page on every ac… |
| arch-literature#13 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The LLC-boundary figure is not a resolvable effect. Sequential stride 256 at 8 MB: pkvm minus kvmoff mean +0.397 ns (+3.55%, exactly the paper's numbe… |
| arch-literature#14 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | Sequential access cannot show the stage-2 cost in this data set. At 64 MB, for strides 64 to 1024, pkvm minus the median of the three baseline medians… |
| arch-literature#15 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Applying Kessler and Hill's binomial page-placement model to the given L3 geometry (128 page colours, 16 pages per colour): with random physical place… |
| arch-literature#16 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Verified literature on the cost of two-dimensional walks. Bhargava et al.: a 2D walk needs nm+n+m references (24 for 4+4), an uncached nested walk is … |
| arch-literature#17 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Verified literature that directly measures a deprivileged host or primary OS under an identity nested/stage-2 map. HyperEnclave (x86, AMD EPYC 7601, h… |
| arch-literature#18 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | pKVM-specific sources state the design but give no host-side number. AOSP: 'The host stage 2 is identity-mapped... This architecture allows the use of… |
| arch-literature#19 | DOCUMENTED | 需修正 | 找反例：通过；重新推导：部分成立 | Related verified Arm results on stage-2 granularity. SeKVM: removing stage-2 huge pages adds 35-50% overhead for hackbench, MySQL and MongoDB in guest… |
| arch-literature#20 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Verified literature on page placement and cache-capacity boundaries. Kessler and Hill: arbitrary page placement causes up to 30% unnecessary cache con… |
| arch-literature#21 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：通过 | lmbench-specific primary statements. The lmbench paper: results varied 'up to 30%' and the authors 'suspect that the operating system is not using the… |
| arch-literature#22 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Verified literature on run-to-run and between-boot bias. Kalibera, Bulej and Tuma: the assignment of physical pages changes cache hits and misses, 'is… |
| arch-literature#23 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Two further placement-related mechanisms have verified literature and local source evidence. (a) Prefetchers working on physical addresses do not pref… |
| arch-literature#24 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Item 4. Public information on FTC862 / D3000 is limited to product-level facts: 8 FTC862 cores, ARMv8 64-bit with ARM64 and ARM32, hardware virtualiza… |
| arch-literature#25 | DOCUMENTED | 需修正 | 找反例：通过；重新推导：部分成立 | Items I could not verify and therefore do not list as verified: Pham et al. MICRO 2015 (page splintering; all PDF URLs returned 404 or 403); Merrifiel… |

## 客户机内（N90）数据，图 8

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| guest-fig8#1 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Figure 8 N90 series = ratio of 10-iteration MEANS: 'pVM/nVHE' = results/xkernel-n90-pkvm-pvm-20260605-163040 over results/xkernel-n90-kvm-nvhe-2026060… |
| guest-fig8#2 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Random access, stride 16: the pVM dataset is faster than both baselines at every size from 3 MB up. Mean-based (as plotted) pVM/nVHE: -26.4% (3 MB), -… |
| guest-fig8#3 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | NP VM is equal to the regular-VM baselines in random access: NP/nVHE at 3-64 MB is -1.25..+3.62% on means and -0.56..+0.75% on medians; NP/VHE is -2.2… |
| guest-fig8#4 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Sequential access, stride 16: every N90 series stays within +-1%. pVM/nVHE ranges from -0.98% (4 MB) to +0.99% (48 MB); pVM/VHE -0.95..+0.84%; NP/nVHE… |
| guest-fig8#5 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Per-iteration stability: the pVM random values do not switch state. All 100 measurements (10 sizes 3-64 MB x 10 iterations) sit on the fast curve, CV … |
| guest-fig8#6 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The +-10..20% spikes of all N90 series at 0.03-0.06 MB in the random panel are not overheads: at the L1D boundary each dataset's per-iteration values … |
| guest-fig8#7 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Absolute random latency: the three regular guests are slower than the host, the pVM guest is faster than the host. Medians at 4/8/16/64 MB (ns): host … |
| guest-fig8#8 | INFERRED | 需修正 | 找反例：部分成立；重新推导：通过 | A guest that is 7.6 ns (3 MB) to 32 ns (64 MB) faster than the same machine with KVM off cannot be explained by a cheaper stage-2 path: a perfect stag… |
| guest-fig8#9 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The same fast curve exists in a host-only dataset with kvm-arm.mode=nvhe (no pKVM, benchmark pinned to cpu0): results/n90-day3-host/n90-nvhe-noisy-ful… |
| guest-fig8#10 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The fingerprint matches across unrelated benchmarks. Host noisy-vs-clean nVHE next to guest pVM-vs-NP (medians): bw_mem_wr 4 MB +19.5% / +19.9%; bw_me… |
| guest-fig8#11 | DOCUMENTED | 需修正 | 找反例：通过；重新推导：部分成立 | The internal docs describe the conditions of two host fast-state episodes. The 'noisy' nVHE run was taken with incomplete service masking, with pvm-ma… |
| guest-fig8#12 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | The fast level is not confined to those runs: it appears sporadically in every clean dataset, including the host with KVM off. Host 12-64 MB cells tha… |
| guest-fig8#13 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The pVM run is the only guest run with host-side interference on the benchmark CPU. Pure-core metrics have CV 0.7-1.6% in the pVM set (integer_add 1.1… |
| guest-fig8#14 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | What the result directories record about the four runs: identical lmbench config (CONFIG.xkernel.used md5 40b058db... in all four), identical environm… |
| guest-fig8#15 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The host CPU-frequency lock of prepare-host.sh was in effect during all four guest runs, so the same script's top-level THP=never setting was probably… |
| guest-fig8#16 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The only launch script for an x-kernel protected VM that exists locally starts it through pvm-manage without any CPU pinning: pvm-manage run --protect… |
| guest-fig8#17 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | Kernel code gives protected and non-protected guests the same stage-2 mapping granularity. With pKVM enabled every non-permission stage-2 fault of eit… |
| guest-fig8#18 | INFERRED | 通过 | 找反例：通过；重新推导：通过 | Larger TLB entries are not the reason the pVM guest is fast. x-kernel maps anonymous private mmap memory with 4 KiB pages, one page per fault, and lmb… |
| guest-fig8#19 | DOCUMENTED | 通过 | 找反例：通过；重新推导：通过 | The host preparation and verification scripts control only the top-level THP switch, while the kernel tree has per-size anonymous and shmem THP contro… |
| guest-fig8#20 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | The size dependence of the normal-minus-fast shift is described by about 35 ns x (1 - 512 pages / working-set pages): zero up to 2 MB, then rising and… |
| guest-fig8#21 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | Evidence-ranked explanations for pVM versus regular VM in random access: (1) a run-level 'fast memory state' of the machine unrelated to protection, w… |
| guest-fig8#22 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | Related host numbers of Figure 7 are reproduced exactly by mean ratios and are affected by the same bimodality. 'LLC Bnd +3.55/-3.0/+2.9' = sequential… |
| guest-fig8#23 | DOCUMENTED | 需修正 | 找反例：部分成立；重新推导：通过 | The internal documentation never endorsed the pVM speed-up: the overall summary compares only VHE, nVHE and the NP run and reports random 64 MB as +0.… |

## 仓库里已有的分析文档

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| prior-docs#1 | MEASURED | 通过 | 重新推导：通过 | D1 / STILL STANDING (as a measurement): the docs' final conclusion that the protected-mode host is 3-7% slower on lmbench random pointer chasing (lat_… |
| prior-docs#2 | DOCUMENTED | 通过 | 重新推导：通过 | D1 / NEVER VERIFIED in the June docs: the mechanism attached to that overhead ('every TLB miss pays one more stage-2 walk layer, +5-10 ns'). It is an … |
| prior-docs#3 | DOCUMENTED | 需修正 | 重新推导：部分成立 | D1 / RETRACTED: 'pKVM is 17-33% faster on random access at the LLC boundary and in DRAM' (random 4 MB 31.89 vs 47.59 ns = -33.0%, 8 MB 91.01 = -19.1%,… |
| prior-docs#4 | DOCUMENTED | 需修正 | 重新推导：部分成立 | D1 / NEVER VERIFIED (and retracted with the claim above): the four candidate mechanisms for the speedup (stage-2 1 GB blocks improving walk-cache hits… |
| prior-docs#5 | MEASURED | 需修正 | 重新推导：部分成立 | D1 / RETRACTED: 'the speedup is a side effect of the CONFIG.host sequence warming the host stage-2 tables' (second-round hypothesis). Retracted by the… |
| prior-docs#6 | MEASURED | 通过 | 重新推导：通过 | D1 / PARTLY STANDING, PARTLY CONTRADICTED: the final wording 'the try1 fast values are a one-off stochastic state, probably the page allocator placing… |
| prior-docs#7 | MEASURED | 通过 | 重新推导：通过 | D1 / NEVER VERIFIED, now shown to be a mixture artifact: 'LLC 8 MB sequential: try2 12.12 vs kvmoff 10.82 = +12.1% real overhead' and 'sequential memo… |
| prior-docs#8 | MEASURED | 通过 | 重新推导：通过 | D1 / STALE AND INTERNALLY INCONSISTENT: SUMMARY.md still lists the LLC-boundary row as 10.82 / 11.41 / 12.45 / 10.01 ('vhe slowest, pkvm fastest') and… |
| prior-docs#9 | MEASURED | 通过 | 重新推导：通过 | D1 / STANDING: L1, L2 and sizes up to 1 MB and the lmbench tlb figure are identical in all four modes (64 KB 2.224 ns in every iteration; 1 MB 4.433-4… |
| prior-docs#10 | DOCUMENTED | 需修正 | 重新推导：部分成立 | D1 / STANDING FOR SEQUENTIAL ACCESS ONLY, with a tension: the mmap investigation documents state that steady-state access is unaffected by protected m… |
| prior-docs#11 | DOCUMENTED | 通过 | 重新推导：通过 | D1 / RETRACTED (relevant because it is the only place the docs tested a nested-walk explanation): hypothesis a-2 'munmap is slower because every stage… |
| prior-docs#12 | DOCUMENTED | 通过 | 重新推导：通过 | D1 / RETRACTED but still printed as the mechanism in SUMMARY.md and FINAL-REPORT.md: 'lat_mmap is slow because every touched page takes a stage-2 abor… |
| prior-docs#13 | MEASURED | 通过 | 重新推导：通过 | D1 / RETRACTED: day-2 finding 'explicit kvm-arm.mode=nvhe adds +16% to every host metric; the pKVM host is built on VHE'. Replaced on day 3 by 'VHE, n… |
| prior-docs#14 | DOCUMENTED | 通过 | 重新推导：通过 | D1 / STANDING WITH LIMITS: 'the host stage-2 is 99.5% 1 GB blocks' (1019 one-gigabyte blocks, 2486 two-megabyte blocks, 8046 four-kilobyte pages). Lim… |
| prior-docs#15 | DOCUMENTED | 需修正 | 重新推导：部分成立 | D1 / WARNING THAT STANDS, CAUSE NEVER EXPLAINED IN THE DOCS: the VM methodology document reports the pVM guest as about 20% faster than the nVHE guest… |
| prior-docs#16 | DOCUMENTED | 需修正 | 重新推导：部分成立 | D1 / NEVER VERIFIED: 'overall macro overhead 5-15%' for mixed workloads. The only application data in the repo (D3000, 5 boot pairs) show Redis satura… |
| prior-docs#17 | MEASURED | 需修正 | 重新推导：部分成立 | D1 / NEVER FOLLOWED UP: on Kaitian, repeated touching of an already established mapping at a 16 KiB stride is slower under protected mode once the num… |
| prior-docs#18 | DOCUMENTED | 通过 | 重新推导：通过 | D1 / NEW MATERIAL THAT APPEARED DURING THIS RUN (not in my assigned list, produced by the launching session and a sibling session, self-labelled pendi… |
| prior-docs#19 | MEASURED | 需修正 | 重新推导：部分成立 | D2 / PMU counters between modes exist only for munmap. N80 (FTC862, Kylin V10 SP1, kernel 6.6.30xcore-stat+ from the 'common' tree, 1.8 GHz), 2026-06-… |
| prior-docs#20 | MEASURED | 通过 | 重新推导：通过 | D2 / EL2 measurements are cycle counts, not entry counts, and only for mmap/touch/munmap. N80, protected, 2026-06-11: EL2-only PMCCNTR delta = 0 for m… |
| prior-docs#21 | DOCUMENTED | 需修正 | 重新推导：部分成立 | D2 / TLBI experiments (all N80 unless noted, June 2026): threshold sweep shows the protected minus nVHE munmap gap grows linearly below a 2 MB flush r… |
| prior-docs#22 | MEASURED | 通过 | 重新推导：通过 | D2 / Kaitian perf-only repeat (2026-06-24, kernel 6.6.30-pkvm-clean, 1.9 GHz, 300 iterations): sparse munmap protected vs nVHE instructions 463.7M vs … |
| prior-docs#23 | MEASURED | 通过 | 重新推导：通过 | D2 / Counter data for the actual workload exists only since today and only for one mode. N80F3 (kernel 6.6.0-79-generic with CONFIG_X1_RMS, protected … |
| prior-docs#24 | MEASURED | 通过 | 重新推导：通过 | D2 / Measurements that do not exist anywhere in the repository: (1) any PMU comparison between protected and a non-protected mode for lat_mem_rd, rand… |
| prior-docs#25 | DOCUMENTED | 需修正 | 重新推导：部分成立 | D3 / Where the docs warn about instability: (a) try1 vs try2 for the protected host, with per-iteration random 64 MB values 'try1 194 179 194 154 154 … |
| prior-docs#26 | MEASURED | 通过 | 重新推导：通过 | D3 / Cross-check 1 (does NOT fully match): the documented try2 per-iteration series for random 64 MB ends '... 192 192 191' and the text says try2 had… |
| prior-docs#27 | MEASURED | 通过 | 重新推导：通过 | D3 / Cross-check 2 (does NOT match): the statement 'kvmoff / nvhe / vhe have no such transition, all 10 iterations are stable'. In the raw CSVs each n… |
| prior-docs#28 | MEASURED | 通过 | 重新推导：通过 | D3 / Cross-checks that DO match: iteration durations in FINAL-REPORT 5.1 agree with the differences between the uptime stamps of consecutive raw repor… |
| prior-docs#29 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | D3 / The machine has a mode-independent 'fast state' and the clean runs are in the 'slow state'. Random-latency medians at 3 / 4 / 6 / 8 / 16 / 64 MB:… |
| prior-docs#30 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | D3 / The fast state has a recognisable signature beyond random latency, and the three data sets that show it agree: sequential stride-256 latency lowe… |
| prior-docs#31 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | D3 / The pVM guest data set behind Figure 8 is in that fast state in every iteration and at every size from 3 MB: random 64 MB 152.2-155.5 ns in all 1… |
| prior-docs#32 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | D3 / The protected-mode increment is present in both machine states, which is the strongest existing argument that it is real and separate from the st… |
| prior-docs#33 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | D3 / The LLC-boundary point (sequential, stride 256, 8 MB) is a two-level measurement in every mode. CONFIG.host: kvmoff 6 low / 4 high (means 10.45 /… |
| prior-docs#34 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | D3 / Memory bandwidth shows the same two levels, which the docs never flag: bw_mem_rd at 16.78 MB is bimodal in all four clean runs (about 15.1k vs 18… |
| prior-docs#35 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | D3 / Candidate cause of the two levels that the docs never considered (unverified): the klinux tree, which is the source of the Kylin 6.6.0-7x kernels… |
| prior-docs#36 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | D4 / Statistic and LLC boundary: the paper reports 10-run means; the team's reports state that medians are used because they are robust to single-iter… |
| prior-docs#37 | MEASURED | 需修正 | 找反例：部分成立；重新推导：通过 | D4 / Figure 8 and its text contradict the docs. Paper: 'KylinX各模式延续低开销特征,且在10MB以上区间出现约10%–20%的负开销' and, for pVM, 'LLC边界(约8MB)延迟降低10%以上'. Docs: the hos… |
| prior-docs#38 | MEASURED | 通过 | 找反例：通过；重新推导：通过 | D4 / Memory bandwidth: the paper says memory read bandwidth improves by about 0.55% and lists it among 'results that surpass native'. That value is th… |
| prior-docs#39 | MEASURED | 需修正 | 找反例：部分成立；重新推导：部分成立 | D4 / Smaller tensions in the same paragraph: (a) the paper reads the +0.29% sequential result as 'no observable address-translation loss'; the docs li… |
| prior-docs#40 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | D5 / Statements about the 64 MB random-access number that existing evidence supports: (1) the slowdown is reproducible (+3.3 to +3.8%, about +6 to +7 … |
| prior-docs#41 | INFERRED | 通过 | 找反例：通过；重新推导：通过 | D5 / Statement about the LLC-boundary number that existing evidence supports: it should not be presented as a protected-mode overhead. The point is bi… |
| prior-docs#42 | INFERRED | 需修正 | 找反例：部分成立；重新推导：部分成立 | D5 / What is still missing before either number can be called a root cause: (1) counters for lat_mem_rd -t on one machine in protected and in at least… |

## 补充测量（N80，2026-09-30 下午）

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| device#1 |  | 通过 | 找反例：通过；重新推导：通过 | [N80 host, protected mode, Exp A, expA.log] For the random page-order chase (lmbench -t pattern, stride 16, 4 KiB pages) the mean L2 TLB refills per a… |
| device#2 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [N80, Exp D, expD.log] For the sequential chase over 64 MB with 4 KiB pages, L2 TLB refills per access equal stride/4096 to within 2% for strides 64, … |
| device#3 |  | 通过 | 找反例：通过；重新推导：通过 | [N80, Exp C, expC.log] With MADV_HUGEPAGE the 8 MB random chase shows essentially zero L2 TLB refills per access (below 0.0001) and about 85 to 88 ns … |
| device#4 |  | 需修正 | 找反例：部分成立；重新推导：通过 | [N80, Exp B, expB.log, sequential stride 256, 30 fresh-process runs per size] For 8, 12, 16 and 64 MB the per-run latency (ns_med) is strongly negativ… |
| device#5 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [N80, Exp L, expL.log and expL-smoke.log] With the identical set of physical frames (same colour statistics in every layout of a run), the shuffled vi… |
| device#6 |  | 通过 | 找反例：通过；重新推导：通过 | [N80, Exp F, expF.log] The 64 MB random chase takes between 154 and 162 ns per access for all tested frame-selection policies (physically compact, max… |
| device#7 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [N80, Exp T, expT.log] At the time of that run freshly allocated buffers had contig_frac below 0.01 for all three first-touch orders (none, rand, desc… |
| device#8 |  | 通过 | 找反例：通过；重新推导：通过 | [cross-machine] The N80 used for these measurements reports MIDR 0x700f8620 on all 8 cores, L3 8 MiB 16-way 8192 sets shared by 8 cores, 2 x 8 GB DIMM… |

## 综合结论草稿

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| concl#1 |  | 通过 | 找反例：通过；重新推导：通过 | [N90 host data] The three memory-latency numbers of Figure 7 are 10-iteration MEANS from results/n90-day3-host: 'LLC Bnd' = lat_mem_rd_load stride 256… |
| concl#2 |  | 通过 | 找反例：通过；重新推导：通过 | [N90 host data] The LLC-boundary point is bimodal in all four modes with the same two levels (about 9.9 to 10.7 ns and 12.2 to 12.6 ns, a few runs in … |
| concl#3 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [N90 host data] For random access the pkvm median exceeds the median of the three baseline medians by less than 0.2 ns up to 2 MB, by 0.7 ns at 3 MB, … |
| concl#4 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [N90 increments combined with N80 walk rates] Dividing the N90 increment at each size by the N80 page-walk rate at that size gives about 3.3, 3.7, 3.9… |
| concl#5 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [N90 host data] For sequential access at 64 MB the pkvm median exceeds the mean of the kvmoff and nvhe medians by about 0.24 ns at stride 512 and 0.40… |
| concl#6 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [reasoning] The random-access increment cannot be an extra cost per DRAM access: the 64 MB sequential test also fetches a new cache line from memory o… |
| concl#7 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [N90 host data] The non-quiesced nVHE data set (n90-nvhe-noisy-full) versus the quiesced nVHE data set, medians: random access is within 2.5% up to 2 … |
| concl#8 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [N90 host data] In the four quiesced data sets single random-access runs are occasionally more than 4% faster than their configuration's median: 0 of … |
| concl#9 |  | 需修正 | 找反例：部分成立；重新推导：部分成立 | [guest data] In the x-kernel guest data the protected VM's random-access medians are 20 to 32% below those of the other three guests from 3 MB to 64 M… |
| concl#10 |  | 通过 | 找反例：通过；重新推导：通过 | [x-kernel source, commit 9bab5da3 of ~/Dev/x-kernel, inspect with git show only] sys_mmap maps private anonymous memory with 4 KiB pages unle… |
| concl#11 |  | 通过 | 找反例：通过；重新推导：通过 | [kernel source and device] The platform has a NoC devfreq device (drivers/devfreq/phytium_noc.c, ACPI id PHYT0047, 600 to 1800 MHz); the driver regist… |
| concl#12 |  | 无法核实 | 找反例：无法核实；重新推导：无法核实 | [hypothesis, to be judged as a hypothesis] The fast/slow memory-latency states and the 8 MB bimodality on the N90 are caused by the NoC frequency-scal… |
| concl#13 |  | 通过 | 找反例：通过；重新推导：通过 | [earlier document docs/n90-kvm-host/llc-boundary-8mb-analysis.md] Its statistical conclusion (the +3.55% is bimodal mixture noise, p about 0.40) is co… |

## 补充测量（N80，2026-09-30 傍晚：实验 R、BG、H、S、V、V2、W）

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| ev#1 | MEASURED (N80 device, Exp R, expR.log) | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp R (probe3, sequential stride 256, fresh process per point, 20 laps, interconnect governor 'performance' at 1800 MHz): rewriting the pointer chain … |
| ev#2 | MEASURED (N80 device, Exp R) | 通过 | 找反例：通过；重新推导：通过 | In Exp R the 8 MB stride-256 point is single-valued on the N80: the 40 values lie in 9.22 to 9.43 ns (coefficient of variation 0.4 to 0.5%), the large… |
| ev#3 | MEASURED (N80 device, Exp R) | 需修正 | 找反例：通过；重新推导：部分成立 | In Exp R the 12 and 16 MB points spread over 8% (9.41 to 10.21 ns and 9.32 to 10.09 ns) and the latency tracks the physical layout of the buffer: Spea… |
| ev#4 | MEASURED (N80 device, Exp BG, expBG.log) | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp BG: with the interconnect already at its highest frequency, memory traffic generated on other cores (one core reading 256 MB in a loop, one core w… |
| ev#5 | MEASURED (N80 device, Exp H, expH-rand.log) compared with MEASURED (N90 host data) | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp H, lmbench's own lat_mem_rd built from the repository source (lat_mem_rd -t -P 1 64 16), buffer on 4 KiB pages (THP disabled for the process with … |
| ev#6 | MEASURED (N80 device, Exp H, expH-seq256.log and expH-seqall.log) compared with MEASURED (N90 host data) | 通过 | 找反例：通过；重新推导：通过 | Exp H, lmbench's own lat_mem_rd, stride 256, 4 KiB pages, interconnect at 1800 MHz: the 8 MB point was measured 18 times (16 dedicated sweeps plus the… |
| ev#7 | INFERRED (hypothesis H-i: the N90 'fast state' is the on-chip interconnect running at its highest frequency) | 需修正 | 找反例：部分成立；重新推导：部分成立 | All 17367 samples of /sys/class/devfreq/nocfreq/cur_freq taken every 100 ms during Exp H read 1800000 and the governor was 'performance'. Two conseque… |
| ev#8 | MEASURED (N80 device: vm-frames-n80.txt, vm-process-n80.txt) | 通过 | 找反例：通过；重新推导：通过 | A protected VM was running on the N80 during every N80 measurement of 2026-09-30: process 2341 (crosvm, started Wed Sep 30 16:21:55 2026, i.e. at boot… |
| ev#9 | MEASURED (N80 device, Exp S, expS.log, iomem-n80.txt) | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp S (frames2: 32 MB random chase on pool pages taken from one 1 GiB physical slot at a time, pages spread evenly over the slot's pool pages): 13 of … |
| ev#10 | MEASURED (N80 device, Exp V, expV.log) | 通过 | 找反例：通过；重新推导：通过 | Exp V (frames2 with the list of 2 MiB regions that hold VM pages; same process, same GiB slot 0x20c0000000, 32 MB random chase, pages spread evenly, 3… |
| ev#11 | MEASURED (N80 device, Exp V2, expV2.log) | 需修正 | 找反例：部分成立；重新推导：通过 | Exp V2 (the shared-against-clear comparison at working sets from 2 to 64 MB; extra = median of class shared minus median of class clear over all slots… |
| ev#12 | INFERRED from ev#10 and ev#11 plus kernel source | 需修正 | 找反例：部分成立；重新推导：通过 | Interpretation of Exp V and V2: (a) the two classes differ only where the chase needs page walks (no difference at 2 to 4 MB where walks per access ar… |
| ev#13 | INFERRED (implication for the paper) plus procedure-only fact about the N90 | 需修正 | 找反例：部分成立；重新推导：部分成立 | Implication: while a protected VM runs, host memory that shares 2 MiB regions with guest pages pays more per TLB miss (random access 7% to 13% slower … |
| ev#14 | MEASURED (N80 device, Exp W, expW.log) | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp W (frames2, sequential chase with stride 256 over one page set mapped either in ascending physical order ('sorted') or in a random virtual order (… |
| ev#15 | MEASURED consistency check between Exp S and Exp V | 需修正 | 找反例：部分成立；重新推导：部分成立 | The slow slot of Exp S is explained by Exp V: in Exp S the pages of slot 0x20c0000000 were taken without regard to class; in Exp V the pool of that sl… |

## 傍晚实验背后的内核机制

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| ek#1 | SOURCE (tag 6.6.0-79.93) | 通过 | 找反例：通过；重新推导：通过 | When a page is donated to a protected guest (__pkvm_host_donate_guest, reached from the host's pkvm_mem_abort on a guest stage-2 fault), the host stag… |
| ek#2 | SOURCE (tag 6.6.0-79.93) | 通过 | 找反例：通过；重新推导：通过 | After such a split the rest of the former block stays mapped for the host one level down: (a) host pages in the same 2 MiB region as a guest-owned pag… |
| ek#3 | SOURCE (tag 6.6.0-79.93) | 通过 | 找反例：通过；重新推导：通过 | Pages that the host donates to the hypervisor for a VM's metadata (guest stage-2 page-table pages and other memcache pages, __pkvm_host_donate_hyp and… |
| ek#4 | SOURCE (tag 6.6.0-79.93) | 被推翻 | 找反例：推翻；重新推导：推翻 | Nothing merges the host stage-2 back into blocks: when a guest page is returned to the host (__pkvm_host_reclaim_page and VM teardown), the page is ma… |
| ek#5 | SOURCE (tag 6.6.0-79.93) | 需修正 | 找反例：部分成立；重新推导：部分成立 | The donation size follows the host-side backing of the guest memory: pkvm_mem_abort (arch/arm64/kvm/mmu.c) pins the faulting page and donates PMD_SIZE… |
| ek#6 | SOURCE (tags 6.6.0-79.93 and 6.6.0-73.76) | 需修正 | 找反例：部分成立；重新推导：部分成立 | For the paths in ek#1 to ek#5 the C EL2 implementation (arch/arm64/kvm/hyp/nvhe/mem_protect.c, used when CONFIG_X1_RMS is off, which is the configurat… |
| ek#7 | SOURCE (tag 6.6.0-79.93) plus N80 memory map (results/memlat-n80-20260930/iomem-n80.txt) | 通过 | 找反例：通过；重新推导：通过 | At EL2 initialisation the host stage-2 identity map is pre-populated for every memory region with the largest aligned block that fits inside the regio… |

## 补充测量（N80，2026-09-30 晚：实验 X、Y、V3、Z）

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| nx#1 | MEASURED (N80 device, Exp X1 and X3: expX1.log, expX3.log) | 需修正 | 重新推导：部分成立 | lmbench times 100 load instructions in a row (the HUNDRED macro in benchmark_loads, src/lat_mem_rd.c); probe3 and frames2 by default time one load ins… |
| nx#2 | INFERRED | 需修正 | 重新推导：部分成立 | Consequence of nx#1: the difference between lmbench's own lat_mem_rd and the probes for sequential access (first noticed as 8% to 16% between Exp H an… |
| nx#3 | MEASURED (N80 device: expH-seq256.log, expX3.log, expR.log, expX1.log) plus INFERENCE | 需修正 | 重新推导：部分成立 | lmbench's own lat_mem_rd is itself sensitive to the physical layout of its buffer. Between Exp H (about 18:50 to 19:15) and Exp X3 (19:56 to 20:07), i… |
| nx#4 | MEASURED (N80 device, Exp X2: expX2.log) plus a withdrawn argument | 需修正 | 重新推导：部分成立 | Exp X2 (frames2, sequential stride 256, the same selection of pages mapped in ascending physical order or in shuffled virtual order, class clear, medi… |
| nx#5 | MEASURED (N80 device, Exp Y: expY.log) | 通过 | 重新推导：通过 | Exp Y (frames2, lmbench's loop form, 8 MB, physically adjacent pages, sorted against shuffled virtual order, class all, 12 slots x 2 passes): the shuf… |
| nx#7 | MEASURED (N80 device, Exp V3: expV3.log together with expV2.log) | 通过 | 重新推导：通过 | Exp V3 repeats the shared-against-clear random-chase comparison of Exp V2 with three more page sets per size (seeds 41, 43, 47; a new pool each time; … |
| nx#8 | MEASURED observation plus HYPOTHESIS | 需修正 | 重新推导：部分成立 | In the random chase (class clear or no class separation; logs expS, expV, expV2, expV3) the GiB slots at 0x22c0000000 and 0x2300000000 are slower than… |
| nx#9 | MEASURED (N80 device, Exp Z: expZ.log) plus INFERENCE and one PREDICTION | 需修正 | 重新推导：部分成立 | Exp Z (frames2 mode tlb<L>: every hop goes to another page and only L cache lines of each page are used, so the data stay in the L1/L2 caches; class c… |

## 补充测量与对照测量（N80 和工作站，2026-09-30 夜：实验 N–N5、T2、L2、H2–H6）

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| nn#1 | MEASURED (N80 device and D80F3 workstation, Exp N: expN-n80.log, results/memlat-d80f3-20260930/expN-d80f3.log) | 通过 | 找反例：通过；重新推导：通过 | Exp N runs the same unprivileged program (probe3 mode tlb: every hop goes to another page, only a few cache lines per page are used, pages first touch… |
| nn#2 | MEASURED (N80 device, Exp N2: expN2.log) and a FAILED PREDICTION | 通过 | 找反例：通过；重新推导：通过 | Exp N2 (probe3 tlb as root, 12 repetitions, a stopped process holding back (rep-1) x 192 MB so that the probe gets other frames; one process per cell)… |
| nn#3 | MEASURED (N80 device, Exp N3: expN3.log) | 需修正 | 找反例：部分成立；重新推导：通过 | Exp N3 (frames2, 2048 pages x 1 line, class clear, a fixed percentage of the pages from a slot that can still be a 1 GiB host stage-2 block and the re… |
| nn#4 | MEASURED (N80 device and workstation, Exp N4: expN4-n80.log, results/memlat-d80f3-20260930/expN4-d80f3.log) plus MECHANISM read from probe3.c | 需修正 | 找反例：部分成立；重新推导：通过 | Exp N4 compares probe3 tlb with the pages first touched in chain order (as in N and N2) and in ascending virtual order (TLB_PREFAULT=1). l2over is the… |
| nn#5 | MEASURED (N80 device, Exp N5: expN5.log) and a REFUTED GUESS | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp N5 (probe3 tlb as root, REGIONS file listing the 2 MiB regions that hold pages of the running VM; 12 repetitions x chain and ascending first touch… |
| nn#6 | DERIVED from nn#1, nn#3, nn#4 and Exp Z, plus INFERENCE about the N90 | 需修正 | 找反例：部分成立；重新推导：部分成立 | Cost of one page walk on the N80 in protected mode by the host stage-2 mapping of the page, from the 2048 x 1 configuration minus the no-walk referenc… |
| nn#7 | MEASURED (workstation, Exp T2: results/memlat-d80f3-20260930/expT2.log), no conclusion | 需修正 | 找反例：通过；重新推导：部分成立 | Exp T2 (workstation, unprivileged, probe2 sequential stride 256, pages first touched in ascending, random or descending order, with 0, 1024 or 2048 MB… |
| nn#8 | MEASURED (N80 device and workstation, Exp L2: expL2-n80.log, results/memlat-d80f3-20260930/expL2-d80f3.log) | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp L2 (thplayout: a pool faulted in as 2 MiB transparent huge pages, every 4 KiB page then moved with mremap into a range that starts one page after … |
| nn#9 | SOURCE and DEVICE FACT (results/memlat-n80-20260930/thp-contpte-n80.txt; klinux tags 6.6.0-79.93 and 6.6.0-73.76) plus INFERENCE | 通过 | 找反例：通过；重新推导：通过 | The N80 kernel has CONFIG_ARM64_CONTPTE=y and multi-size THP; all sizes other than 2048 kB are set to 'never'; arch/arm64/mm/contpte.c exists at both … |
| nn#10 | MEASURED (N80 device, Exp H2: expH2.log) and a FAILED PREDICTION | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp H2 (lmbench's own lat_mem_rd -P 1 64 256 under nothp, 16 sweeps: 4 rounds x 0, 1024, 2048, 2560 MB held back; probe3 sequential 8 MB in lmbench's … |
| nn#11 | MEASURED (N80 device, Exp H3: expH3.log, expH3-frames.log, pagealloc-n80.txt) plus INFERENCE about the cause | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp H3 reads the frame numbers of the buffer of every lat_mem_rd child from /proc/<pid>/pagemap (lmb-frames.py) during 12 sweeps as in H2. Total adjac… |
| nn#12 | SOURCE (klinux tags 6.6.0-73.76 and 6.6.0-79.93) plus ESTIMATE | 需修正 | 找反例：部分成立；重新推导：部分成立 | By mm/page_alloc.c (zone_highsize) the default limit of the per-CPU free list is the zone's low watermark divided by the number of CPUs; the low water… |
| nn#13 | MEASURED (N80 device and workstation, Exp H4: expH4.log, expH4-shim.log, results/memlat-d80f3-20260930/expH4-d80f3.log) | 需修正 | 找反例：部分成立；重新推导：部分成立 | Exp H4 runs the unmodified lat_mem_rd (-P 1 64 256) with layoutshim.so preloaded, which hands its 64 MB malloc a buffer of 4 KiB pages taken from 2 Mi… |
| nn#14 | MEASURED (N80 device: expH5.log with expH4.log; N90 host data of June) plus a FAILED PREDICTION | 通过 | 找反例：通过；重新推导：通过 | Exp H5 repeats H4 for the other strides of the paper's command (sorted and shuffled8, two repetitions each). Ratio shuffled8 / sorted of lmbench's own… |
| nn#15 | MEASURED (N80 device, Exp H6: expH6.log) | 需修正 | 找反例：部分成立；重新推导：通过 | Exp H6 runs lmbench's own random-access test (lat_mem_rd -t -P 1 64 16) on sorted pages, on pages shuffled over the whole buffer and without the libra… |
| nn#16 | DERIVED (N90 host data of June and Exp H4/H5; section 'Two-factor check' of derived/state-tables.md), post hoc | 需修正 | 找反例：部分成立；重新推导：部分成立 | For strides 64 to 1024 and sizes 3 to 64 MB, the ratio of the N90 non-quiesced ('fast state') nVHE run to the low level of the four quiesced boots ran… |
| nn#17 | INFERRED (judgement between the two candidate explanations of the two levels of the N90 8 MB sequential point; replaces an earlier judgement) | 需修正 | 找反例：部分成立；重新推导：部分成立 | Two candidates remain for the two levels of the 8 MB sequential point on the quiesced N90 hosts: E1, a platform state (for example the interconnect fr… |

## 补充测量（N80，2026-10-01 凌晨：实验 H7、H8，以及 N90 数据里 8 MB 高值之后的读数）

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| nh#1 | measured | 通过 | 找反例：通过；重新推导：通过 | Exp H8 (run32-lmbench-partial-layout.sh, N80, protected, interconnect 1800 MHz at start and end of every run, 2026-10-01 00:58-01:12; logs results/mem… |
| nh#2 | measured | 通过 | 找反例：通过；重新推导：通过 | N90 quiesced host data (four boots x ten iterations, strides 64-1024 = 200 sweeps; experiments/memlat-probe/analyze-host-memlat.py section 9; each val… |
| nh#3 | inference | 需修正 | 找反例：部分成立；重新推导：部分成立 | If the high 8 MB level on the N90 came from scattered frames (E2), and the 12 MB child took those frames back as every 12 MB child did on the N80 (Exp… |
| nh#4 | judgement | 需修正 | 找反例：部分成立；重新推导：部分成立 | Judgement on the two levels of the N90's 8 MB sequential point (LLC boundary): more likely a platform state that changes from one lmbench child to the… |

## 互连调频实验（N80，2026-10-02，用户执行：实验 G5）

| 编号 | 类别 | 结果 | 各核查者 | 结论原文（英文，截取开头） |
|---|---|---|---|---|
| ng#1 | measured | 需修正 | 找反例：通过；重新推导：部分成立 | Exp G5 (run33-noc-lmbench-frames.sh, N80, protected, run as root by the user on 2026-10-02 08:49-09:12; logs results/memlat-n80-20260930/expG5.log, ex… |
| ng#2 | measured | 通过 | 找反例：通过；重新推导：通过 | Under simple_ondemand the 13 8 MB stride-256 points (12 single-stride sweeps and the stride-256 part of the full command) fall into 10.29-10.71 ns (6)… |
| ng#3 | inference | 需修正 | 找反例：部分成立；重新推导：部分成立 | Random access: N80 simple_ondemand / performance at 4, 6, 8, 12, 16, 64 MB is 1.63, 1.60, 1.37, 1.29, 1.27, 1.26; the N90 quiesced (kvmoff, nvhe, vhe … |
| ng#4 | judgement | 需修正 | 找反例：部分成立；重新推导：部分成立 | The interconnect devfreq driver (drivers/devfreq/phytium_noc.c in ~/Dev/klinux) registers simple_ondemand as its governor with polling 100 ms… |

