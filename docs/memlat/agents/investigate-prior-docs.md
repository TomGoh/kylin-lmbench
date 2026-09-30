# 调查代理报告：prior-docs

> 这是多代理调查阶段的原始报告，英文原文照录。它的结论在使用前还要经过独立核查，
> 核查结果见同目录下的 verify-*.md。

## Headline

One conclusion in the team's docs still stands and I reproduced it from raw data: on the N90 host, protected mode makes lmbench random pointer chasing about 3.5% slower at 64 MB and 6.3% slower at 8 MB than kvmoff, nVHE and VHE alike (about +6.2 to +6.9 ns per access at 64 MB). Its stated cause (one extra stage-2 walk per TLB miss) was never measured in those docs: every PMU, EL2-cycle, stage-2-histogram and TLBI experiment was done for munmap on N80 or Kaitian with a different kernel tree, none for lat_mem_rd and none on the N90. The LLC-boundary +3.55% is a mean over a bimodal point (about 10.4 vs 12.5 ns in all four modes; exact permutation p = 0.40; VHE vs kvmoff alone differs by +6.8%), so it is not a protected-mode effect. The 'one-off stochastic fast state' the docs tie to pKVM is mode-independent: the nVHE 'noisy' host run, all day-1/day-2 host runs and the pVM guest run behind Figure 8 sit entirely in it, so Figure 8's negative pVM overhead is a machine-state artifact and the docs' 'lucky stage-2 alignment' explanation is contradicted by the repository's own raw data.

## Findings

### prior-docs#1 (MEASURED, confidence high)

D1 / STILL STANDING (as a measurement): the docs' final conclusion that the protected-mode host is 3-7% slower on lmbench random pointer chasing (lat_mem_rd -t, stride 16) for working sets of 4 MB and above. Recomputed from raw data: try2 medians 49.31 / 119.59 / 176.28 / 188.66 / 191.73 ns at 4 / 8 / 16 / 32 / 64 MB versus kvmoff 47.59 / 112.54 / 168.54 / 180.61 / 185.23 (+3.6 / +6.3 / +4.6 / +4.5 / +3.5%); standalone reruns 49.74 / 120.01 / 176.72 / 189.57 / 192.41 versus 47.70 / 112.90 / 169.80 / 181.55 / 185.32. At 4 MB and 8 MB all 10 protected iterations exceed all kvmoff iterations (exact permutation p = 1.1e-5). At 64 MB the mean difference is +3.25% (p = 0.093, bootstrap 95% CI -0.4 to +6.6%) and the median difference +3.51% (p = 0.031). Restricted to iterations in the normal slow state the 64 MB difference is +6.2 to +6.4 ns (CONFIG.host) and +6.5 to +6.9 ns (standalone), i.e. +3.35 to +3.7%, about 12-13 cycles at 1.9 GHz, with within-state SD 0.5-0.8 ns.

Evidence: Docs: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/SUMMARY.md:207-261, FINAL-REPORT.md:374-394 and 604-630, pkvm.md:198-232, standalone-memory-bench-validation.md:143-155 and 374-411 (evidence type there: N=10 lmbench CONFIG.host, one boot per mode, plus 10 standalone runs on a second boot; no counters). Raw: /home/jose/Dev/kylin-lmbench/results/n90-day3-host/n90-{kvmoff,nvhe,vhe}-noLSM-full-cpu0.csv, n90-pkvm-noLSM-try2-cpu0.csv; results/standalone-mem-bench/standalone-*.log. Computation: scratch wf1/prior-docs/host_stats.py, standalone.py, significance.py (exact permutation over all 184756 splits; 20000 bootstrap resamples) and their .out files.

### prior-docs#2 (DOCUMENTED, confidence high)

D1 / NEVER VERIFIED in the June docs: the mechanism attached to that overhead ('every TLB miss pays one more stage-2 walk layer, +5-10 ns'). It is an architectural expectation; no PMU counter, EL2 count or stage-2 inspection was ever taken for lat_mem_rd in any mode on any machine. The '5-10 ns' is the observed latency difference restated, not an independently measured walk cost. The only counter data for this workload was added to the repo today (N80, protected mode only, no baseline mode) and is self-labelled pending verification.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/FINAL-REPORT.md:612-630 (mechanism paragraph without any data source); SUMMARY.md:211, 241-242, 259; pkvm-memory-access-speedup.md:168-173 ('我们没有直接证据 ... 需要 ARM PMU counter'); docs/memlat/README.md ('当时没有硬件计数器数据'); results/memlat-n80-20260930/README.md ('只测了一种模式').

### prior-docs#3 (DOCUMENTED, confidence high)

D1 / RETRACTED: 'pKVM is 17-33% faster on random access at the LLC boundary and in DRAM' (random 4 MB 31.89 vs 47.59 ns = -33.0%, 8 MB 91.01 = -19.1%, 64 MB 154.40 = -16.6%; sequential 8 MB 10.01 vs 10.82; bw_mem_rd 8.39 MB 20321 vs 16445 MB/s = +23.6%). Evidence type: one N=10 lmbench run ('try1'), no counters. Retracted by standalone-memory-bench-validation.md and by the banner of the doc itself. The raw try1 data were deliberately excluded from the repository, so none of these numbers can be re-derived.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm-memory-access-speedup.md:3-15 (banner '本文已作废'), 35-56, 64-87; retraction in standalone-memory-bench-validation.md:3-10, 232-247, 345-428 and SUMMARY.md:207-265. Raw data absence: git commit 18e4c3a6 message ('Excluded: n90-pkvm-noLSM-try1-*'); `git log --all --name-only` shows no try1 path; `find /home/jose/Dev /home/jose/Documents -iname '*pkvm-noLSM-try1*'` returns nothing.

### prior-docs#4 (DOCUMENTED, confidence high)

D1 / NEVER VERIFIED (and retracted with the claim above): the four candidate mechanisms for the speedup (stage-2 1 GB blocks improving walk-cache hits; DRAM bank layout shifted by the 166 MiB hyp reservation; ASID+VMID tagging; prefetcher reacting to VTCR). A stale copy of the first two survives in the mmap analysis, which still explains 'why pkvm is slightly faster at 8 MB (10.01 ns)' although a note in the same file says 10.01 was a try1 outlier.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm-memory-access-speedup.md:112-173; /home/jose/Dev/kylin-lmbench/docs/mmap/pkvm-mmap-overhead-analysis.md:403-431 (stale section 5) versus 60-63 (note calling 10.01 an outlier).

### prior-docs#5 (MEASURED, confidence high)

D1 / RETRACTED: 'the speedup is a side effect of the CONFIG.host sequence warming the host stage-2 tables' (second-round hypothesis). Retracted by the try2 rerun in section 9 of the same document ('stage-2 暖机能稳定加速 ... 机制假说不成立'). The document is internally inconsistent: its header, section 4.1 and section 5 still assert the warm-up explanation, and pkvm.md still calls the effect a 'CONFIG.host 序列副产品'. The standalone logs (fresh process, nothing run before) themselves contain fast excursions in every mode, which also refutes it.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/standalone-memory-bench-validation.md:3-6, 44-45, 172-197, 242-261 versus 345-436 (line 428); pkvm.md:29-32. Raw standalone excursions: results/standalone-mem-bench/standalone-kvmoff.log run 6 rand 32 MB = 151.342 and run 9 rand 64 MB = 169.476; standalone-vhe.log run 10 rand 16 MB = 134.475; standalone-pkvm.log run 3 rand 16 MB = 140.372 (parsed by scratch wf1/prior-docs/standalone.py).

### prior-docs#6 (MEASURED, confidence high)

D1 / PARTLY STANDING, PARTLY CONTRADICTED: the final wording 'the try1 fast values are a one-off stochastic state, probably the page allocator placing the 64 MB heap inside a prepopulated stage-2 1 GB block (幸运对齐); it exists but cannot be reproduced'. What stands: it is not a benefit of pKVM. What is contradicted by raw data in the same repository: it is neither one-off nor tied to host stage-2. The same latency profile appears (a) in all 10 iterations of the nVHE 'noisy' host run, which has no host stage-2, (b) in all day-1/day-2 host runs, (c) in all 10 iterations of the pVM guest run, and (d) as single-iteration excursions in every clean run including kvmoff.

Evidence: Doc: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/SUMMARY.md:221-223, 263-265, 392-396; pkvm.md:224-226, 273-275; standalone-memory-bench-validation.md:413-416. Raw: results/n90-day3-host/n90-nvhe-noisy-full-cpu0.csv (random 64 MB 149.9-151.9 ns in all 10 iterations versus 185.0 in the clean nVHE run); results/n90-day1 and n90-day2 CSVs; results/xkernel-n90-pkvm-pvm-20260605-163040/*.txt. Computation: scratch wf1/prior-docs/faststate.py, noisy_vs_clean.py, final_tables.py, day12.out.

### prior-docs#7 (MEASURED, confidence high)

D1 / NEVER VERIFIED, now shown to be a mixture artifact: 'LLC 8 MB sequential: try2 12.12 vs kvmoff 10.82 = +12.1% real overhead' and 'sequential memory access 0 to +14%'. The same document's standalone table gives 12.05 vs 12.35 ('~0%'). The point is bimodal in every mode (see the two-state finding below); the median jumps by 12% and the mean by 3.55% only because of how many of the 10 iterations fell in the upper mode.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm.md:205-214 (column header '真实开销'); standalone-memory-bench-validation.md:152 versus 376-386 and 409; docs/n90-kvm-host/lmbench-N10-4config-all-metrics.csv:452 (MAD% 6.39 / 9.37 / 1.44 / 3.65, pkvm_vs_kvmoff +12.09%). Recomputed in scratch wf1/prior-docs/host_stats.out and significance.out.

### prior-docs#8 (MEASURED, confidence high)

D1 / STALE AND INTERNALLY INCONSISTENT: SUMMARY.md still lists the LLC-boundary row as 10.82 / 11.41 / 12.45 / 10.01 ('vhe slowest, pkvm fastest') and DRAM 64 MB pkvm = 10.11, which are try1 values, although the same file says the pkvm column is try2 and FINAL-REPORT.md gives 12.12 and 10.34. The pkvm column of the syscall/process/fault tables in SUMMARY.md, FINAL-REPORT.md and pkvm.md also does not match the try2 CSV: fork 134.83 (try2 median 139.07), exec 376.38 (385.84), shell 787.11 (807.61), page fault 0.2547 (0.2599), prot fault 0.1607 (0.1594); the bandwidth and random-latency rows do match try2. The '±1%' statements for fork and page fault therefore rest on the discarded run; with try2 they are +2.1% each (page fault p = 0.0001).

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/SUMMARY.md:49-56, 97-105, 143; FINAL-REPORT.md:298-304, 364-372; pkvm.md:145-155; docs/lmbench-overall-summary.zh-CN.md:66-73 (uses try2: 0.2599, 139.07). Check: scratch wf1/prior-docs/doc_table_check.py output (table 'Stale try1 values' below).

### prior-docs#9 (MEASURED, confidence high)

D1 / STANDING: L1, L2 and sizes up to 1 MB and the lmbench tlb figure are identical in all four modes (64 KB 2.224 ns in every iteration; 1 MB 4.433-4.437; tlb = 48, also in the noisy run). NOT accurate: 'bw_mem DRAM segment equal within ±0.5%': medians at 67 MB are 18446 / 18404 / 17837 / 18154 MB/s (VHE -3.3%, pkvm -1.6%) and bzero 41913 / 41913 / 40660 / 41329.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/SUMMARY.md:267-273; FINAL-REPORT.md:396-415, 655-661; raw CSVs in results/n90-day3-host; scratch wf1/prior-docs/host_stats.out, noisy_vs_clean.out (tlb rows).

### prior-docs#10 (DOCUMENTED, confidence high)

D1 / STANDING FOR SEQUENTIAL ACCESS ONLY, with a tension: the mmap investigation documents state that steady-state access is unaffected by protected mode (lat_mem_rd 64 MB about 10.3 ns in all modes, bw_mem peak within 0.5%, TLB-hit path costs nothing extra, nested walk increment 'very small' with 1 GB blocks), and one of them says accesses after mapping are 'no different at all' and that the two-stage walk costs 'at most 2-3 cycles'. They never mention the +3-7% random-access result of the n90-kvm-host documents. Supporting data for the sequential statement: D3000 paired anchors (5 boot pairs, 64 MiB, stride 128) +0.57% and +0.18%; Pixel +0.05 ns. The '2-3 cycles' figure was never measured and is below the roughly 12-13 cycles per TLB-missing access seen at 64 MB.

Evidence: /home/jose/Dev/kylin-lmbench/docs/mmap/pkvm-mmap-overview.zh-CN.md:160-171, 577, 754-769, 2429; docs/mmap/pkvm-mmap-overhead-analysis.md:341-344, 512-515; docs/mmap/README.md:24-26; docs/mmap/d3000-thp-never-full-results.zh-CN.md:26, 237-246.

### prior-docs#11 (DOCUMENTED, confidence high)

D1 / RETRACTED (relevant because it is the only place the docs tested a nested-walk explanation): hypothesis a-2 'munmap is slower because every stage-1 walk is nested through stage-2'. Retracted by the dense-touch control (40 times more PTEs, gap about 0) and the 2 MB threshold sweep; the cause is per-page TLBI cost. A residual gap of +0.4 to +4% (one data set) or +5 to +6% (another) remains in the dense region of 2 MB and above and is attributed, without any measurement, to 'stage-2 amplification of page-freeing memory accesses'.

Evidence: Wrong attribution: /home/jose/Dev/kylin-lmbench/docs/mmap/n80-gate-c0-results.zh-CN.md:32, 290-295, 307; c1-host-stage2-granularity.zh-CN.md:27-41, 204-215. Retraction: c1-tlbi-threshold.zh-CN.md:5-7, 33-68, 116-135; pkvm-mmap-overview.zh-CN.md:1603-1644. Residual: c1-tlbi-threshold.zh-CN.md:126-129, 145, 156; pkvm-mmap-overview.zh-CN.md:1897-1907, 1997-2021.

### prior-docs#12 (DOCUMENTED, confidence high)

D1 / RETRACTED but still printed as the mechanism in SUMMARY.md and FINAL-REPORT.md: 'lat_mmap is slow because every touched page takes a stage-2 abort of about 500 ns'. Retracted by the life-cycle split (first write touch only +3.78%) and the EL2 gate (zero EL2 cycles). Relevance here: it establishes that host accesses to already mapped memory do not enter EL2.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/SUMMARY.md:173-187; FINAL-REPORT.md:562-602; docs/mmap/pkvm-mmap-overhead-analysis.md:203-333; retraction in docs/mmap/pkvm-mmap-overview.zh-CN.md:896-907, 1275-1289.

### prior-docs#13 (MEASURED, confidence high)

D1 / RETRACTED: day-2 finding 'explicit kvm-arm.mode=nvhe adds +16% to every host metric; the pKVM host is built on VHE'. Replaced on day 3 by 'VHE, nVHE and kvmoff are indistinguishable'. The run metadata show that the day-2 nVHE run had all CPUs capped at 1.9 GHz while the other day-2 runs were at 2.1 GHz, which the docs never mention.

Evidence: /home/jose/Dev/kylin-lmbench/docs/findings-2026-06-02.md:32-39, 164-214; docs/n90-kvm-host/SUMMARY.md:189-205, 294-306; results/n90-day2/n90-nvhe-noLSM-N5-20260602-093817-summary.txt (cpu_max_freqs 1900000 x8) versus results/n90-day2/n90-baremetal-noLSM-N5-20260602-090813-summary.txt (2100000 x8).

### prior-docs#14 (DOCUMENTED, confidence high)

D1 / STANDING WITH LIMITS: 'the host stage-2 is 99.5% 1 GB blocks' (1019 one-gigabyte blocks, 2486 two-megabyte blocks, 8046 four-kilobyte pages). Limits: measured on N80 in June with the 'common' 6.6.30 tree, not on the N90 and not with the klinux xhypervisor kernel; the percentage is of the whole 40-bit IPA space (about 1 TB including MMIO holes), not of RAM, so the 2 MB share of RAM could be much larger than 0.5% (up to about 4.9 GB of a 16 GB machine); klinux has no op=3 histogram code, so this cannot currently be repeated on the paper's kernel without porting the patch.

Evidence: /home/jose/Dev/kylin-lmbench/docs/mmap/c1-host-stage2-granularity.zh-CN.md:27-41, 167-184; pkvm-mmap-overview.zh-CN.md:1583-1601; experiments/munmap-tlbi/INVESTIGATION-LOG.md:34-35. Source check: `grep host_stage2_level_histogram` over /home/jose/Dev/klinux/arch/arm64 returns nothing; xcore_stats ops exist only under CONFIG_XCORE_STATS in /home/jose/Dev/klinux/arch/arm64/kvm/hyp/xhypervisor/src/hyp_main.rs:1836-1869; prepopulation logic matches the docs at /home/jose/Dev/klinux/arch/arm64/kvm/hyp/xhypervisor/src/mem_protect/host.rs:375-404.

### prior-docs#15 (DOCUMENTED, confidence high)

D1 / WARNING THAT STANDS, CAUSE NEVER EXPLAINED IN THE DOCS: the VM methodology document reports the pVM guest as about 20% faster than the nVHE guest on 64 MB random access (ratio 0.798), says the reason is unknown and that the data set's ENV_TAG is wrong (it says xkernel-pkvm-np), and asks for confirmation before use. The overall summary analyses only the NP guest (+0.17% at 64 MB) and does not list the pVM directory at all.

Evidence: /home/jose/Dev/kylin-lmbench/docs/vm-lmbench-methodology.zh-CN.md:35, 182-196, 264-266; docs/lmbench-overall-summary.zh-CN.md:104-112, 133-136; docs/vm-ratio-comparison-highlights.csv:29-33 (pVM/nVHE -15.6% LLC boundary, -20.2% random 64 MB, -22.5% 8 MB, -31.2% 4 MB).

### prior-docs#16 (DOCUMENTED, confidence medium)

D1 / NEVER VERIFIED: 'overall macro overhead 5-15%' for mixed workloads. The only application data in the repo (D3000, 5 boot pairs) show Redis saturation throughput +1.9%, RabbitMQ throughput +1.6 to +2.6%, Geekbench wall time +0.33%.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/FINAL-REPORT.md:708-712; SUMMARY.md:398-402; docs/mmap/d3000-thp-never-full-results.zh-CN.md:9-24.

### prior-docs#17 (MEASURED, confidence medium)

D1 / NEVER FOLLOWED UP: on Kaitian, repeated touching of an already established mapping at a 16 KiB stride is slower under protected mode once the number of touched pages exceeds the 48-entry first-level TLB: write touch 52 pages 2.50 to 4.19 ns per touch (+67%), 410 pages 5.72 to 6.63 (+15.8%); read touch 410 pages 6.39 to 7.49 (+17.4%); no difference at 26 pages or fewer for writes. The document dismisses it because the absolute time is small. The environment was uncontrolled (THP always, ASLR on).

Evidence: /home/jose/Dev/kylin-lmbench/docs/mmap/mmap-split-kaitian-pkvm-comparison.zh-CN.md:409-421, 452-460, 597; raw /home/jose/Dev/kylin-lmbench/results/mmap-split-kaitian/{nvhe,pkvm}.csv (header lines 7-8 record thp=[always], aslr=2); computed in scratch wf1/prior-docs/kaitian_hot.out.

### prior-docs#18 (DOCUMENTED, confidence high)

D1 / NEW MATERIAL THAT APPEARED DURING THIS RUN (not in my assigned list, produced by the launching session and a sibling session, self-labelled pending verification): llc-boundary-8mb-analysis.md concludes that +3.55% is bimodal noise (p about 0.40) caused by physical page placement (stated as inference); docs/memlat worklog adds N80 measurements and marks 'H-c bimodality = physical contiguity' as holding on N80 only and 'H-d random increment = extra stage-2 translation per walk' as holding but unverified. My independent recomputation agrees on the statistics (p = 0.3995) but not on a pure per-allocation page-placement cause for the N90 (see the machine-state findings).

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/llc-boundary-8mb-analysis.md:3-11, 65-76, 150-166 (git commit e107eab8, file mtime 2026-09-30 17:02:31 +0800); /home/jose/Dev/kylin-lmbench/docs/memlat/memlat-investigation-worklog.zh-CN.md:50-69, 111-126, 144-206 (git commit 84362ecf, 2026-09-30 17:08:38 +0800).

### prior-docs#19 (MEASURED, confidence high)

D2 / PMU counters between modes exist only for munmap. N80 (FTC862, Kylin V10 SP1, kernel 6.6.30xcore-stat+ from the 'common' tree, 1.8 GHz), 2026-06-11, one perf stat run per mode of 'mmap_split_bench munmap_after_write_touch 64 50': cycles 49.03M (nVHE) vs 88.81M (protected), instructions 81.89M vs 81.94M, stall_backend 18.17M vs 59.06M, page-faults 21013 vs 21011, l1d_tlb_refill 47702 vs 55870, l2d_tlb_refill 21658 vs 21614, raw 0x34 DTLB walks 21453 vs 21371. It proves that the munmap slowdown is backend stall with equal instruction, fault and walk counts. It does not measure any memory-read workload, is a single unrepeated run, and is on a different machine and kernel tree from the paper's host data. Raw files match the documented numbers.

Evidence: /home/jose/Dev/kylin-lmbench/results/n80-munmap-gate-c0/nvhe/c0-nvhe/perf-munmap_after_write_touch-64mb-nvhe.txt and .../protected/c0-protected/perf-munmap_after_write_touch-64mb-protected.txt; documented at docs/mmap/n80-gate-c0-results.zh-CN.md:250-261 and pkvm-mmap-overview.zh-CN.md:1322-1340.

### prior-docs#20 (MEASURED, confidence high)

D2 / EL2 measurements are cycle counts, not entry counts, and only for mmap/touch/munmap. N80, protected, 2026-06-11: EL2-only PMCCNTR delta = 0 for munmap_after_write_touch at 8/16/64 MB (100 iterations) and for mmap_write_touch_unmap and write_touch_cold (20 iterations), with a positive control of 168,083,659 cycles for 200 page-table-walk hypercalls. Kaitian, kernel 6.6.30-pkvm-clean, 2026-06-24: perf cycles:h = 0 for sparse munmap in both modes, positive control 392M for 100000 KVM_RUN. They prove the host does not enter EL2 on those paths. No EL2 measurement exists for lat_mem_rd, none on the N90, none on the klinux xhypervisor kernel, and the optional hyp trace events (hyp_enter, host_mem_abort) have no recorded results.

Evidence: /home/jose/Dev/kylin-lmbench/results/n80-munmap-gate-c0/protected/gate-out/el2-gate-protected.csv (three rows, el2_cycles_net = 0); docs/mmap/n80-gate-c0-results.zh-CN.md:164-172, 232-244; docs/mmap/el2-gate-instrumentation.zh-CN.md:78-80; experiments/perf-reinvestigation/results/README.zh-CN.md:60-69; experiments/perf-reinvestigation/stage0/README.zh-CN.md (392,139,024 cycles:h).

### prior-docs#21 (DOCUMENTED, confidence high)

D2 / TLBI experiments (all N80 unless noted, June 2026): threshold sweep shows the protected minus nVHE munmap gap grows linearly below a 2 MB flush range (about +0.27 us per 4 KiB slot) and collapses at 2 MB; direct in-kernel timing gives 10.0 / 23.2 ns per slot (nVHE, non-shareable / inner-shareable) versus 288.8 / 288.9 ns (protected); core scaling is flat by mean; Kaitian repeats it at about +0.13 us per slot; THP on shmem removes it. They prove that TLB invalidation of combined stage-1 x stage-2 entries is about 12 times more expensive locally. They say nothing about TLB refill or walk cost, and lat_mem_rd's timed loop issues no TLBI, so they do not explain the random-access overhead. The in-kernel 'cold dependent load' control (617 ns per 4 loads = 154 ns per load, flat across online cores) was taken in protected mode only and its raw file is not in the repo.

Evidence: /home/jose/Dev/kylin-lmbench/docs/mmap/pkvm-mmap-overview.zh-CN.md:1893-1928, 2136-2151, 2153-2206; experiments/munmap-tlbi/results/tlbi-ab-n80/tlbi-ab-{nvhe,protected}.txt (raw values verified); experiments/munmap-tlbi/INVESTIGATION-LOG.md:189-203 (protected-only memwork table); docs/mmap/pkvm-thp-mitigation.zh-CN.md:57-94.

### prior-docs#22 (MEASURED, confidence high)

D2 / Kaitian perf-only repeat (2026-06-24, kernel 6.6.30-pkvm-clean, 1.9 GHz, 300 iterations): sparse munmap protected vs nVHE instructions 463.7M vs 463.1M, page-faults 123050 both, raw 0x34 walks 122556 vs 123506, l2d_tlb_refill 122944 vs 123609, stall_backend 206.2M vs 87.5M, cycles 369.8M vs 250.3M. Same scope limits as the N80 data: munmap only. Open item recorded there: in dense teardown of 2 MB and above the gap grows with freed pages (64 MB mean gap +532 us, min gap +83 us), unexplained.

Evidence: /home/jose/Dev/kylin-lmbench/experiments/perf-reinvestigation/results/protected/cost_layering.txt and nvhe/cost_layering.txt (raw perf output verified); README.zh-CN.md:71-87, 169-171 in the same directory.

### prior-docs#23 (MEASURED, confidence high)

D2 / Counter data for the actual workload exists only since today and only for one mode. N80F3 (kernel 6.6.0-79-generic with CONFIG_X1_RMS, protected mode, desktop session running, no service masking, THP system setting 'always' with MADV_NOHUGEPAGE on the buffer), 2026-09-30: for the lmbench random pattern, L2-TLB refills per access are 0.006 at 1 MB, 0.046 at 2 MB, 0.19 at 3 MB, 0.45 at 4 MB, 0.84 at 6 MB, 0.97 at 8 MB and 1.00 from 16 MB; L3 refills per access rise over the same range (0.06, 0.41, 0.62, 0.79, 0.88, 0.97); sequential access takes exactly one walk per page crossing. It proves how many walks the workload performs on this core type. It does not prove that a walk costs more under protected mode, because no non-protected mode was measured on that machine; the walk rate and the L3 miss rate rise together, so timing alone cannot separate 'per walk' from 'per DRAM access' cost. I checked the 8 MB rows of the raw log against the derived table (0.966, 0.978, 0.961, 0.958).

Evidence: /home/jose/Dev/kylin-lmbench/results/memlat-n80-20260930/expA.log lines 15-16 and 43-44 (ev2d field); derived/device-tables.md (Exp A, Exp D); README.md in the same directory ('只测了一种模式', '桌面会话在运行 ... 没有做服务屏蔽'); hw-survey-n80.txt.

### prior-docs#24 (MEASURED, confidence high)

D2 / Measurements that do not exist anywhere in the repository: (1) any PMU comparison between protected and a non-protected mode for lat_mem_rd, random or sequential; (2) any host stage-2 granularity histogram for the N90 or for the klinux xhypervisor kernel; (3) any EL2 cycle or entry count during lat_mem_rd; (4) the second-level TLB and walk-cache geometry of FTC862; (5) any record of the memory-subsystem power or frequency state during the N90 runs (the run summaries record only kernel, cmdline and CPU max frequencies).

Evidence: Full read of the listed docs plus `grep -rn lat_mem_rd` over /home/jose/Dev/kylin-lmbench (all perf outputs are for mmap_split_bench, munmap_only or op_sweep); /home/jose/Dev/kylin-lmbench/results/n90-day3-host/*-summary.txt (contents: env, kernel, cmdline, cpu_max_freqs only).

### prior-docs#25 (DOCUMENTED, confidence high)

D3 / Where the docs warn about instability: (a) try1 vs try2 for the protected host, with per-iteration random 64 MB values 'try1 194 179 194 154 154 155 155 154 154 154; try2 193 193 192 192 191 166 191 192 192 191'; (b) 'a single N=10 is not enough to detect stochastic states'; (c) nVHE 8 MB sequential MAD 9.37% and the VHE 8 MB value called 'probably single-iteration jitter'; (d) the day-3 'noisy' nVHE run kept as a contamination counter-example (the docs compare only syscall and TCP numbers); (e) QUICK-START rule: re-run protected mode as try2 if its random latency looks more than 10% faster than the baselines; (f) the munmap investigation's lesson that min statistics fabricated a 2x core-scaling effect; (g) the VM docs' warning about the pVM data set and about mean versus median tables; (h) D3000 boot-start versus boot-end drift of about 1.9%.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm.md:10-20, 216-226; standalone-memory-bench-validation.md:29-45, 359-372, 430-436; nvhe.md:156-164; vhe.md:196-197; SUMMARY.md:294-306; /home/jose/Dev/kylin-lmbench/QUICK-START.md:137, 228-243; experiments/munmap-tlbi/INVESTIGATION-LOG.md:223-260; docs/vm-lmbench-methodology.zh-CN.md:95-103, 195, 264-266; docs/mmap/d3000-thp-never-full-results.zh-CN.md:246.

### prior-docs#26 (MEASURED, confidence high)

D3 / Cross-check 1 (does NOT fully match): the documented try2 per-iteration series for random 64 MB ends '... 192 192 191' and the text says try2 had 'only one blip at iteration 6'. The raw CSV and the raw iteration reports give 192.634 193.091 191.564 191.895 191.131 166.436 191.336 192.266 192.199 178.793: iterations 1-9 agree after rounding, iteration 10 is 178.8, not 191, so try2 has two low iterations. The try1 series cannot be checked at all because the raw data were never committed.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm.md:218-222 and standalone-memory-bench-validation.md:363-369 versus /home/jose/Dev/kylin-lmbench/results/n90-day3-host/n90-pkvm-noLSM-try2-cpu0.csv lines 685, 1369, 2053, 2737, 3421, 4105, 4789, 5473, 6157, 6841 and the 'Random load latency' 64.00000 row of n90-pkvm-noLSM-try2-cpu0-iter10.txt (178.793).

### prior-docs#27 (MEASURED, confidence high)

D3 / Cross-check 2 (does NOT match): the statement 'kvmoff / nvhe / vhe have no such transition, all 10 iterations are stable'. In the raw CSVs each non-protected mode has 3 of 10 iterations more than 4% below its median at random 64 MB (kvmoff iterations 1, 3, 6 = 176.3, 168.7, 176.5; nvhe 3, 6, 7 = 164.5, 172.2, 175.2; vhe 4, 8, 10 = 175.4, 159.9, 176.6), and kvmoff shows excursions of -17 to -21% at 12-48 MB (for example 12 MB iteration 2 = 121.4 vs 154.7; 32 MB iterations 1-2 = 142.3, 143.0 vs 180.6). Over the six sizes from 12 to 64 MB the count of low iterations is kvmoff 16/60, nvhe 7/60, vhe 6/60, protected 5/60. There is no persistent transition in those runs, but they are not stable, and the baseline has more fast excursions than the protected run.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/standalone-memory-bench-validation.md:42 versus raw CSVs in results/n90-day3-host; scratch wf1/prior-docs/faststate.out (census tables) and final_tables.out (counts).

### prior-docs#28 (MEASURED, confidence high)

D3 / Cross-checks that DO match: iteration durations in FINAL-REPORT 5.1 agree with the differences between the uptime stamps of consecutive raw reports for all four modes (first nine intervals, maximum deviation 1 s); the MAD percentages quoted for 8 MB and 64 MB sequential in nvhe.md and vhe.md (9.37, 1.82, 1.44, 3.16) are exact; the VHE iteration-3 anomalies (lat_unix 10.89, bw_tcp 2039) are exact, although the quoted comparison value 2380 is iteration 2, not the median (2182.6); all standalone medians quoted in the docs match the logs; the four host CSVs are identical to a fresh parse of the raw reports for all 2630 memory-latency rows per mode.

Evidence: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/FINAL-REPORT.md:281-292; nvhe.md:156-164; vhe.md:88-92, 158-166; standalone-memory-bench-validation.md:92-115. Raw: header line '[ hh:mm:ss up ...]' of each results/n90-day3-host/*-iterN.txt; scratch wf1/prior-docs/rawparse.py output ('HOST CSV vs RAW (memory rows): IDENTICAL'), standalone.out, and the inline checks recorded in host_stats.out.

### prior-docs#29 (MEASURED, confidence high)

D3 / The machine has a mode-independent 'fast state' and the clean runs are in the 'slow state'. Random-latency medians at 3 / 4 / 6 / 8 / 16 / 64 MB: clean nVHE 36.6 / 47.7 / 67.4 / 112.6 / 168.6 / 185.0 ns; nVHE 'noisy' run of the same day, same kernel, same 1.9 GHz lock: 26.4 / 30.8 / 48.6 / 83.9 / 134.2 / 150.1 ns in all 10 iterations (-28 / -35 / -28 / -25 / -20 / -19%). Every host data set collected before the full service masking is also at the fast level: day-2 nVHE at 1.9 GHz 26.1 / 30.1 / 46.2 / 81.1 (3 / 4 / 6 / 8 MB), day-1 protected host and day-2 default-mode hosts at 2.1 GHz 23.1-23.4 / 27.4-28.1 / 43.4-47.2 / 78.5-84.6, day-1 protected host single run 64 MB = 133.95. The fast state therefore does not depend on KVM mode or on host stage-2; it correlates with the host not being fully quiesced.

Evidence: /home/jose/Dev/kylin-lmbench/results/n90-day3-host/n90-nvhe-noisy-full-cpu0.csv and n90-nvhe-noLSM-full-cpu0.csv; results/n90-day1/n90-host-N5-cpu0.csv, n90-host-cpu0.csv; results/n90-day2/n90-baremetal-N5-cpu0.csv, n90-baremetal-noLSM-N5-cpu0.csv, n90-nvhe-noLSM-N5-cpu0.csv and their *-summary.txt (kernel 6.6.0-52, cpu_max_freqs); scratch wf1/prior-docs/noisy_vs_clean.out, day12.out, final_tables.out. Masking context: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/SUMMARY.md:294-306 ('当时 mask 不全').

### prior-docs#30 (MEASURED, confidence high)

D3 / The fast state has a recognisable signature beyond random latency, and the three data sets that show it agree: sequential stride-256 latency lower at 3-8 MB (noisy vs clean nVHE -7.5% at 4 MB, -9.6% at 8 MB with 10 of 10 iterations in the lower LLC-boundary mode; pVM vs nVHE guest -12.2% and -19.2%); bw_mem_rd at 8.39 MB higher (+15.9% host noisy, +22.9% pVM guest, +23.6% in the retracted try1 doc); bw_mem_wr at 4.19 MB +19.5% / +19.7%; par_mem at 8.39 MB -26.7% / -20.2%; lmbench tlb unchanged at 48; whole-suite iteration time shorter (584-599 s noisy vs 606-625 s clean; the docs give 579-602 s for try1 iterations 6-10). The slow-minus-fast difference saturates at about 35 ns per access from 12 MB upward, and is absent at 1-2 MB.

Evidence: Scratch wf1/prior-docs/noisy_vs_clean.out, guest_parse_all.out, faststate.out; iteration durations from raw report headers of /home/jose/Dev/kylin-lmbench/results/n90-day3-host/n90-nvhe-noisy-full-cpu0-iter*.txt; try1 values from /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm-memory-access-speedup.md:42-56, 82-87 and pkvm.md:108-116 (documented only).

### prior-docs#31 (MEASURED, confidence high)

D3 / The pVM guest data set behind Figure 8 is in that fast state in every iteration and at every size from 3 MB: random 64 MB 152.2-155.5 ns in all 10 iterations versus 191.3-192.5 (nVHE guest), 186.7-193.7 (VHE guest), 180.4-193.1 (NP guest). Mean-based overhead versus the nVHE guest: -26.4% (3 MB), -31.2% (4 MB), -31.7% (6 MB), -22.5% (8 MB), -16.7 to -20.7% (12-64 MB); NP versus nVHE stays within -1.3 to +3.6%. The other three guest runs show only sporadic excursions (3/60, 7/60, 6/60 low iterations at 12 MB and above; pVM 0/60 because it is always low). These values reproduce the Figure 8 curves.

Evidence: /home/jose/Dev/kylin-lmbench/results/xkernel-n90-pkvm-pvm-20260605-163040/xkernel-pkvm-np-cpu0-iter*.txt and the three other xkernel-n90-* directories, parsed independently by scratch wf1/prior-docs/rawparse.py (faststate.out) and by a scratch copy of the repo parser (guest_parse_all.out); figure at scratchpad/paper/x/word/media/image8.png.

### prior-docs#32 (MEASURED, confidence medium)

D3 / The protected-mode increment is present in both machine states, which is the strongest existing argument that it is real and separate from the state problem. Slow state (clean runs): +0.7 / +1.7 / +5.5 / +7.1 / +7.0 / +7.7 / +8.1 / +6.5 ns at 3 / 4 / 6 / 8 / 12 / 16 / 32 / 64 MB, zero at 1-2 MB. Fast state: documented try1 medians minus measured nVHE-noisy medians give +0.5 / +1.1 / +1.3 / +7.1 / +6.3 / +6.2 / +4.0 / +4.3 ns at the same sizes; day-1 protected host minus day-2 default-mode host (2.1 GHz, N=5 each, different boots) gives +0.6 ns at 4 MB and +3.8 ns at 8 MB. In addition every configuration that runs under a stage-2 translation lands at the same 64 MB value: host protected 191.7, guests on VHE / nVHE / NP 192.9 / 192.0 / 192.4, versus 185.0-185.4 for the three hosts without stage-2.

Evidence: Scratch wf1/prior-docs/final_tables.out (table), day12.out, guest_parse_all.out. The fast-state protected values are DOCUMENTED only (/home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm-memory-access-speedup.md:42-56), since the try1 raw data are gone; the nVHE-noisy, day-1/day-2 and guest values are from raw files.

### prior-docs#33 (MEASURED, confidence high)

D3 / The LLC-boundary point (sequential, stride 256, 8 MB) is a two-level measurement in every mode. CONFIG.host: kvmoff 6 low / 4 high (means 10.45 / 12.33 ns), nVHE 5 / 5 (10.16 / 12.40), VHE 2 low / 2 middle / 6 high (10.61 / 12.53), protected 4 low / 1 middle / 5 high (10.40 / 12.52); standalone: kvmoff 4 / 1 / 5, nVHE 3 / 0 / 7, VHE 3 / 1 / 6, protected 4 / 0 / 6. The level means agree across modes within 0.25 ns. Protected vs kvmoff: mean +3.55% (p = 0.40, bootstrap 95% CI -4.1 to +11.3%), median +12.09% (p = 0.49), standalone mean +0.65% (p = 0.82); VHE vs kvmoff on the same point is +6.77% (p = 0.08) although neither has a host stage-2. In the nVHE noisy run all 10 iterations are at the lower level (10.10-10.81).

Evidence: Raw CSVs in /home/jose/Dev/kylin-lmbench/results/n90-day3-host and logs in results/standalone-mem-bench; scratch wf1/prior-docs/significance.out (sections 'LLC boundary: two-state description' and the permutation tests), faststate.out.

### prior-docs#34 (MEASURED, confidence high)

D3 / Memory bandwidth shows the same two levels, which the docs never flag: bw_mem_rd at 16.78 MB is bimodal in all four clean runs (about 15.1k vs 18.9k MB/s; low iterations kvmoff 4, nVHE 3, VHE 5-7, protected 6-7 of 10), and at 33.55 and 67.11 MB each baseline has exactly one low iteration (kvmoff iteration 9: 14692 and 14826; nVHE iteration 5: 14714 and 14805; VHE iteration 10: 14291 and 14522) while protected has none. The ratio between levels is about 1.25, the same as for random latency at 16-64 MB (1.23-1.26) and for the LLC-boundary point (1.20).

Evidence: /home/jose/Dev/kylin-lmbench/results/n90-day3-host/*.csv rows bench=bw_mem_rd variants sz16.78, sz33.55, sz67.11 (printed per iteration during this session; host_stats.py series()); ratios from scratch wf1/prior-docs/final_tables.out.

### prior-docs#35 (INFERRED, confidence low)

D3 / Candidate cause of the two levels that the docs never considered (unverified): the klinux tree, which is the source of the Kylin 6.6.0-7x kernels, contains Phytium devfreq drivers for the SoC interconnect ('NoC') and the DDR memory unit, built as modules in the Kylin defconfig. The NoC driver uses the simple_ondemand governor by default with a 100 ms polling period and up-threshold 80, and its v1 load metric is read from a register named V1_WR_NOLAST_HANDSHARK_NUM (apparently write-channel traffic); the DDR driver used simple_ondemand until a 2025-05 commit made 'performance' the default for v1. The benchmark preparation script pins only CPU frequency, idle states, THP and ASLR, the clean-environment script masks about 100 services including upower and the display manager, and no run records devfreq state. A load-dependent interconnect or DDR clock would produce exactly a mode-independent slow level on a quiesced host and a fast level on a busy one, but whether the N90 exposes these devices and loads these modules is not recorded anywhere.

Evidence: /home/jose/Dev/klinux/drivers/devfreq/phytium_noc.c:82-102, 381-408, 476, 528, 537-541, 624-625; /home/jose/Dev/klinux/drivers/devfreq/phytium_dmu.c:479-484, 556, 564-565, 635-636; git history of that file (bb8c897711bef 2024-07-19 simple_ondemand; 3b3abf3c26ee2 2025-05-07 default changed to performance); /home/jose/Dev/klinux/arch/arm64/configs/kylinos_generic_defconfig:1943-1944; /home/jose/Dev/kylin-lmbench/prepare-host.sh:21-48; scripts/apply-masks.sh:49, 57, 147; scripts/verify-clean-env.sh:40-45; `grep -ri devfreq` over /home/jose/Dev/kylin-lmbench returns no run record.

### prior-docs#36 (MEASURED, confidence high)

D4 / Statistic and LLC boundary: the paper reports 10-run means; the team's reports state that medians are used because they are robust to single-iteration anomalies. For the LLC boundary the team's own material gives four different answers for the same comparison: +12.09% (median tables and pkvm.md, labelled real overhead), about 0% (standalone table), 'pkvm fastest' (stale SUMMARY.md row) and +3.55% (mean workbook, used in the paper). The paper presents +3.55% as a notable overhead; no June document claims a protected-mode effect at that point on the basis of means, nvhe.md reports MAD 9.37% for it, and today's analysis doc calls it noise.

Evidence: Paper: scratchpad/paper/paper.txt lines 209-212 (P147-P149). Docs: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/FINAL-REPORT.md:90-96; pkvm.md:212; standalone-memory-bench-validation.md:152, 383; SUMMARY.md:104; nvhe.md:163; lmbench-N10-4config-all-metrics.csv:452; llc-boundary-8mb-analysis.md:3-11. Recomputation: scratch wf1/prior-docs/host_stats.out.

### prior-docs#37 (MEASURED, confidence high)

D4 / Figure 8 and its text contradict the docs. Paper: 'KylinX各模式延续低开销特征,且在10MB以上区间出现约10%–20%的负开销' and, for pVM, 'LLC边界(约8MB)延迟降低10%以上'. Docs: the host-side reports say a faster-than-baseline result 'must not be reported' because it is a non-reproducible state; the VM methodology doc says the pVM result is unexplained and the data set label is doubtful; the overall summary reports the NP guest as +0.17% on 64 MB random. The raw data show the negative overhead only in the pVM series (NP is within about ±2%), so 'all modes' is wrong as well, and the magnitude at 12-64 MB is -17 to -21% with -26 to -32% at 3-6 MB.

Evidence: Paper: scratchpad/paper/paper.txt lines 223 and 229 (P161, P167). Docs: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/standalone-memory-bench-validation.md:418-428; SUMMARY.md:250-251, 263-265; docs/vm-lmbench-methodology.zh-CN.md:195, 264-266; docs/lmbench-overall-summary.zh-CN.md:133-136. Data: scratch wf1/prior-docs/guest_parse_all.out.

### prior-docs#38 (MEASURED, confidence high)

D4 / Memory bandwidth: the paper says memory read bandwidth improves by about 0.55% and lists it among 'results that surpass native'. That value is the mean of bw_mem_rd at 67 MB and comes from one low outlier iteration in the kvmoff baseline (iteration 9 = 14826 MB/s against 18327-18579 for the other nine); by median the protected host is 1.58% lower, which is what the docs report ('-1.58%', 'bandwidth not affected by KVM mode, within 3%'). The same applies to the +4.0% versus VHE bar (VHE iteration 10 = 14522; median difference +1.78%).

Evidence: Paper: scratchpad/paper/paper.txt line 212 (P150) and Figure 7 panel 'Memory Bandwidth' (scratchpad/paper/x/word/media/image7.png). Docs: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm.md:237-246; FINAL-REPORT.md:396-415; lmbench-N10-4config-all-metrics.csv:176. Raw per-iteration values: results/n90-day3-host/*.csv bench=bw_mem_rd variant=sz67.11.

### prior-docs#39 (MEASURED, confidence high)

D4 / Smaller tensions in the same paragraph: (a) the paper reads the +0.29% sequential result as 'no observable address-translation loss'; the docs list sequential access as '0 to +14%' and explain that the translation cost exists per page walk but is amortised over 16 accesses per page; (b) the paper counts the protection-fault result (-1.08%) as KylinX beating native, while the docs call it within ±1% and the raw data give p = 0.40 for the mean and +0.22% for the median; (c) the paper's page-fault +1.99% agrees with try2 (p = 0.0001) but contradicts SUMMARY.md and FINAL-REPORT.md, which still print the try1 value (equal to kvmoff); (d) the random 64 MB figure itself (+3.25% mean) is consistent with the docs (+3.5% median, +3.7 to +3.9% standalone); (e) the docs disagree among themselves about the LLC size of this platform (8 MB in one, 4 MB in another, 2 MB for N80 in two others) while the hardware survey reports one 8 MiB L3 shared by 8 cores, and the N80 counters show L3 refills on 62% of random accesses already at 4 MB, so '8 MB = LLC boundary' is a loose label.

Evidence: Paper: scratchpad/paper/paper.txt lines 211-213 (P149-P151). Docs: /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/standalone-memory-bench-validation.md:409; SUMMARY.md:99-100; FINAL-REPORT.md:400; docs/findings-2026-06-01.md:33; experiments/munmap-tlbi/INVESTIGATION-LOG.md:191-192; docs/mmap/pkvm-mmap-overview.zh-CN.md:2157; results/memlat-n80-20260930/hw-survey-n80.txt and derived/device-tables.md (Exp A). Statistics: scratch wf1/prior-docs/significance.out.

### prior-docs#40 (INFERRED, confidence medium)

D5 / Statements about the 64 MB random-access number that existing evidence supports: (1) the slowdown is reproducible (+3.3 to +3.8%, about +6 to +7 ns per access, in the full-suite run and in the standalone rerun on a separate boot) and appears against all three baselines, which agree with each other within 0.4 ns, so it is specific to protected mode rather than to KVM being enabled or to the host running at EL1 or EL2; (2) it is absent for working sets up to 2 MB and for L1/L2-resident sizes, appears from 3-4 MB and saturates at about 7-8 ns from 8 MB; (3) protected mode is the only mode in which the host runs under a stage-2 translation (HCR_EL2.VM is set only there), and the host takes no trap to EL2 on these paths (no TLB or VM trap bits in the host HCR; zero EL2 cycles measured on touch and munmap paths on N80 and Kaitian), so the extra time is spent in hardware address translation, not in hypervisor software; (4) sequential 64 MB access shows no significant change (+0.29%, p = 0.77), consistent with one page walk per 16 accesses; (5) guests, which always run under stage-2, show the same 64 MB value as the protected host. The wording should be 'consistent with the extra stage-2 lookups of a nested walk on a TLB miss', not 'caused by'.

Evidence: Measured parts: scratch wf1/prior-docs/significance.out, final_tables.out, guest_parse_all.out. Source: /home/jose/Dev/klinux/arch/arm64/include/asm/kvm_arm.h:108-109 (host HCR flags: protected adds only HCR_TSC); /home/jose/Dev/kylin-lmbench/docs/mmap/pkvm-mmap-overview.zh-CN.md:133-160, 949-981 (HCR_VM only in protected finalize; no TLB traps). EL2 gate: /home/jose/Dev/kylin-lmbench/results/n80-munmap-gate-c0/protected/gate-out/el2-gate-protected.csv. Benchmark semantics: /home/jose/Dev/kylin-lmbench/src/lib_mem.c:207-272 (each hop lands on a different page), src/lat_mem_rd.c:143-149 (minimum of 11 repetitions).

### prior-docs#41 (INFERRED, confidence medium)

D5 / Statement about the LLC-boundary number that existing evidence supports: it should not be presented as a protected-mode overhead. The point is bimodal in all four modes, the +3.55% is the difference between two mixtures (p = 0.40; interval -4% to +11%), its sign reverses against VHE (-3.0%), VHE differs from kvmoff by more (+6.8%) although neither has a host stage-2, the standalone rerun gives +0.65%, and within each level protected and kvmoff differ by less than 2% (low level 10.40 vs 10.45 ns, high level 12.52 vs 12.33 ns). A unimodal neighbour can be reported instead (sequential 6 MB: +1.2% median, +1.0% mean). The physical cause of the two levels on the N90 is not established: today's N80 experiments point to physical page contiguity affecting prefetch across page boundaries, but on the N90 the level is set for a whole run by machine state (10 of 10 lower-level iterations in the noisy nVHE run, and a uniform -7.5% shift at 3-4 MB where the clean runs vary by only 0.1%), which per-allocation page placement alone does not explain.

Evidence: Scratch wf1/prior-docs/significance.out, host_stats.out, faststate.out (stride-256 census including the noisy run); N80 claims from /home/jose/Dev/kylin-lmbench/results/memlat-n80-20260930/derived/device-tables.md (Exp B continuous range 8.31-10.24 ns at 8 MB, Exp L +7.9%) and docs/memlat/memlat-investigation-worklog.zh-CN.md:144-206.

### prior-docs#42 (INFERRED, confidence medium)

D5 / What is still missing before either number can be called a root cause: (1) counters for lat_mem_rd -t on one machine in protected and in at least one non-protected mode: equal l2d_tlb_refill and raw 0x34 walk counts with higher cycles and stall_backend per walk would show that the time is in the walk; (2) the host stage-2 block sizes on the N90 with the klinux kernel (the op=3 patch exists only for the other tree); (3) a huge-page control in both modes (if the cost is per walk it should vanish with 2 MiB pages in both; today's N80 run is protected-only); (4) the second-level TLB and walk-cache behaviour of FTC862; (5) control of the machine's two-level memory state: record and pin any devfreq device, record background load, and classify iterations by level instead of averaging across levels; (6) more than one boot per mode: each mode has one full-suite boot and one standalone boot, and the only mode that was booted twice for the full suite (protected) gave two radically different runs; (7) a repeat of the pVM guest run with the host state recorded, since the existing one is entirely in the fast state and mislabelled.

Evidence: Synthesis of the findings above; gaps documented in /home/jose/Dev/kylin-lmbench/docs/n90-kvm-host/pkvm-memory-access-speedup.md:168-173 and 252-259 (follow-up list never executed for N90), docs/mmap/c1-host-stage2-granularity.zh-CN.md:3 (N80 only), results/memlat-n80-20260930/README.md ('只测了一种模式'), docs/vm-lmbench-methodology.zh-CN.md:264-266.

## Caveats

- Path legend used in the tables: L = /home/jose/Dev/kylin-lmbench, K = /home/jose/Dev/klinux, S = <scratch>/wf1/prior-docs. Line numbers refer to the files as they were during this run (2026-09-30).
- I broke the read-only rule once, by accident: importing the repo's parse-lmbench.py with importlib made Python write a bytecode cache at /home/jose/Dev/kylin-lmbench/__pycache__/parse-lmbench.cpython-314.pyc (created 16:51:09 +0800, git-ignored, 14.8 KB). I did not delete it because the rules also forbid deleting; it can be removed with `rm -r /home/jose/Dev/kylin-lmbench/__pycache__`. After that I used a scratch copy of the parser. No other file in either repository was touched; klinux shows a clean `git status`.
- The kylin-lmbench repository changed while I was working: commit e107eab8 (docs/n90-kvm-host/llc-boundary-8mb-analysis.md, README edit) and commit 84362ecf at 17:08:38 +0800 (docs/memlat, experiments/memlat-probe, results/memlat-n80-20260930) appeared, plus further uncommitted files in those directories. They were not in my assigned reading list; I read and partly spot-checked them and report them as unverified same-day material from the launching session and a sibling session, not as independent prior evidence.
- The raw data of the first protected-mode run (try1) were never committed. Every try1 number in this report is quoted from the docs and cannot be checked; the fast-state comparison 'try1 minus nVHE noisy' mixes a documented value with a measured one.
- Each host mode has one boot for the full-suite run and one boot for the standalone rerun. The permutation tests and bootstrap intervals treat the 10 iterations within a boot as independent draws, which they are not strictly (shared boot state, and the machine-state excursions cluster in time). The p-values describe within-boot scatter only; between-boot variation is sampled by two boots per mode.
- The explanation of the two memory performance levels by dynamic frequency scaling of the interconnect or DDR controller is my inference from kernel source and from the pattern of the data. I could not check whether the N90 exposes those ACPI devices or loads those modules (no device access, and the repo holds no such record). THP state was also not recorded in the run summaries; I infer THP=never for the fast-level runs only from the fact that the same script that locks the CPU frequency (which the summaries do record) also disables THP, and from lmbench tlb = 48.
- All mechanism measurements in the June docs come from N80 or Kaitian running the 'common' 6.6.30 tree (Rust EL2 under hyp/nvhe/rust), while the paper's host data come from the N90 running the Kylin 6.6.0-73 kernel built from klinux (hyp/xhypervisor). The code is of the same lineage and the prepopulation logic matches, but no instrumented measurement was taken on the paper's kernel before today's N80 run on 6.6.0-79.
- Absolute latencies of N80 and N90 are not comparable (different memory configuration); I use N80 data only for per-access event rates.
- I did not compute significance tests for the bandwidth rows or for the guest data; the guest statements rest on per-iteration values and medians or means of 10.

## Open questions

- What sets the two memory performance levels on the N90 (random 64 MB about 185 vs 150 ns, streaming read about 14.8k vs 18.4k MB/s, LLC-boundary 12.5 vs 10.4 ns)? Checks on the device: list /sys/class/devfreq and read governor, cur_freq and trans_stat during lat_mem_rd; lsmod for phytium_noc and phytium_dmu; repeat the random test with a busy loop or a write-heavy load on another core; repeat with the services unmasked.
- Is the protected-mode increment the same at both levels? The only fast-level protected host data (try1) were deleted. A protected run and a kvmoff run with the level held fixed (whatever fixes it) would answer this and would give the paper a cleaner number than a mean across levels.
- Do l2d_tlb_refill and raw 0x34 walk counts for lat_mem_rd -t match between protected and nVHE or kvmoff on one machine, with cycles and stall_backend per walk higher under protected? This is the missing direct test of the nested-walk explanation.
- What are the host stage-2 block sizes for RAM on the N90 with the klinux kernel? The op=3 histogram patch exists only for the other tree, and the N80 figure is a share of the whole IPA space, not of RAM.
- Why does the per-walk increment implied by the data grow from about 3-4 ns at 2-4 MB to 7-8 ns at 8 MB and above, and why is it only about 1.6-2 ns per walk in sequential access? L3 miss rate rises together with walk rate, so part of the increment may depend on where the walker's own reads are served from.
- Why was the pVM guest run entirely at the fast level while the VHE, nVHE and NP guest runs were at the slow level? Host-side state for the guest runs was not recorded; the NP directory is named 'clean', which suggests the pVM run predates an environment clean-up. The pVM data set also carries the NP tag.
- Why is the VHE full-suite run 3-4% slower than kvmoff and nVHE on sequential DRAM metrics (seq 64 MB +3.9%, p = 0.011; bw_mem_rd 67 MB -3.3%; bzero -3.0%) when the standalone rerun shows only +1.8% by mean and +0.6% by median? It is a between-boot difference of the same size as the effects the paper reports.
- Is the Kaitian observation (hot touches beyond 48 pages cost 0.9-1.7 ns more per touch under protected mode) real under controlled conditions? On the N90 the 1-2 MB random points, which also miss the first-level TLB on every access, show no increment.
- What explains the residual +0.4 to +6% protected-mode gap in dense munmap of 2 MB and above on N80 and the growing gap with freed pages on Kaitian? Both are memory-access-heavy kernel paths and were left unexplained.

## Tables

Path legend: L = /home/jose/Dev/kylin-lmbench, K = /home/jose/Dev/klinux, S = <scratch>/wf1/prior-docs. All latencies in ns unless stated. 'try2' is the accepted protected-mode run; 'try1' raw data are not in the repository.

### T1. Paper's host memory numbers recomputed from raw CSVs (N90, N=10 per mode, protected = try2)

| Paper label | lmbench row | kvmoff mean / median | protected mean / median | delta of means (paper) | exact perm. p (means) | bootstrap 95% CI of mean delta | delta of medians | exact perm. p (medians) | mean delta vs VHE / vs nVHE | standalone rerun: mean delta (p) |
|---|---|---|---|---|---|---|---|---|---|---|
| LLC Bnd | lat_mem_rd_load stride256 8 MB | 11.203 / 10.815 | 11.600 / 12.123 | +3.55% | 0.3995 | -4.06 .. +11.34% | +12.09% | 0.490 | -3.02% / +2.87% | +0.65% (0.82) |
| Main Mem | lat_mem_rd_load stride256 64 MB | 10.381 / 10.357 | 10.411 / 10.345 | +0.29% | 0.768 | -1.45 .. +2.10% | -0.12% | 0.995 | -3.46% (p 0.013) / +1.06% | +1.11% (0.49) |
| Rand Mem | lat_mem_rd_rand stride16 64 MB | 182.209 / 185.233 | 188.135 / 191.730 | +3.25% | 0.093 | -0.39 .. +6.55% | +3.51% | 0.031 | +3.82% / +3.88% | +3.24% (0.011) |
| (not in paper) | lat_mem_rd_rand 8 MB | 112.600 / 112.545 | 119.651 / 119.595 | +6.26% | 1.1e-5 | +5.87 .. +6.67% | +6.26% | 0.0008 | +6.48% / +6.18% | +4.99% (0.0045) |
| (not in paper) | lat_mem_rd_rand 4 MB | 47.702 / 47.588 | 49.311 / 49.314 | +3.37% | 1.1e-5 | +2.78 .. +3.97% | +3.63% | 0.0008 | +3.80% / +3.47% | +4.24% (1.1e-5) |
| Page Fault | lat_pagefault minor (us) | 0.2548 / 0.2545 | 0.2599 / 0.2599 | +1.99% | 0.0001 | +1.33 .. +2.58% | +2.12% | 0.0008 | +1.03% / +1.92% | n/a |
| Prot Fault | lat_sig prot (us) | 0.1609 / 0.1590 | 0.1591 / 0.1594 | -1.08% | 0.40 | -3.44 .. +1.05% | +0.22% | 0.93 | -1.17% / -0.76% | n/a |
| Mem read | bw_mem_rd 67.11 MB (MB/s) | 18095.7 / 18446.0 | 18195.5 / 18153.9 | +0.55% | not computed | not computed | -1.58% | not computed | +4.02% / +0.77% | n/a |

Null comparisons between modes without host stage-2 (means): LLC Bnd VHE vs kvmoff +6.77% (p 0.082), nVHE vs kvmoff +0.66% (p 0.92); Main Mem VHE vs kvmoff +3.88% (p 0.011); Rand 64 MB nVHE vs kvmoff -0.61% (p 0.74), VHE vs kvmoff -0.55% (p 0.76).
Random 64 MB, slow-level iterations only (values within 3% of the run median): kvmoff 7 kept, mean 185.80 (SD 0.68); nVHE 7, 185.59; VHE 7, 185.74; protected 8, 192.01 (SD 0.67): +6.22 / +6.42 / +6.27 ns = +3.35 / +3.46 / +3.38%. Standalone: +6.88 / +6.81 / +6.53 ns = +3.71 / +3.67 / +3.51%.

### T2. Per-iteration raw values (iterations 1..10)

| Metric | Run | values |
|---|---|---|
| seq stride256 8 MB | kvmoff | 12.242 10.498 10.186 12.370 12.205 10.980 10.650 12.486 10.062 10.350 |
| | nVHE | 10.296 12.434 12.623 9.985 9.925 12.267 12.352 10.553 12.308 10.020 |
| | VHE | 11.474 12.622 11.727 12.473 12.446 12.575 10.919 12.448 10.297 12.631 |
| | protected try2 | 10.704 11.772 12.570 12.561 12.521 10.557 10.252 12.496 10.095 12.474 |
| | nVHE noisy | 10.812 10.343 10.342 10.311 10.270 10.255 10.327 10.282 10.098 10.330 |
| rand 64 MB | kvmoff | 176.314 185.641 168.704 185.315 185.150 176.485 185.057 186.795 186.202 186.426 |
| | nVHE | 186.204 185.862 164.520 186.567 185.579 172.185 175.195 185.915 184.511 184.506 |
| | VHE | 186.579 185.599 185.568 175.439 185.106 186.034 185.288 159.877 186.011 176.568 |
| | protected try2 | 192.634 193.091 191.564 191.895 191.131 166.436 191.336 192.266 192.199 178.793 |
| | nVHE noisy | 150.669 150.240 150.303 149.863 150.276 149.945 149.951 151.851 150.006 149.893 |
| seq stride256 64 MB | kvmoff | 10.240 10.473 9.981 10.731 10.241 10.217 10.586 10.522 10.633 10.190 |
| | nVHE | 10.523 10.069 10.442 10.038 10.230 10.136 10.153 10.536 10.252 10.641 |
| | VHE | 11.126 10.623 10.445 11.128 10.839 10.362 10.836 10.726 11.480 10.274 |
| | protected try2 | 10.169 10.186 10.294 10.662 10.617 10.318 10.743 10.371 10.271 10.479 |
| bw_mem_rd 67.11 MB (MB/s) | kvmoff | 18579 18565 18520 18472 18477 18420 18357 18411 14826 18327 |
| | nVHE | 18503 18450 18482 18369 14805 18436 18371 18545 18344 18251 |
| | VHE | 17572 17707 17762 17831 17891 17843 17980 17897 17915 14522 |
| | protected try2 | 18537 18103 18213 18169 18154 18108 18410 18074 18154 18034 |
| bw_mem_rd 16.78 MB (MB/s) | kvmoff | 15334 15281 18460 19025 18954 18906 18816 18786 15262 15138 |
| | protected try2 | 19284 15094 14982 15058 18726 14993 16036 14712 15074 18587 |
| guest rand 64 MB | VHE guest | 192.840 192.721 189.683 193.240 193.239 193.725 193.437 192.751 193.049 186.682 |
| | nVHE guest | 191.336 191.334 191.462 192.047 191.907 191.976 192.027 192.386 192.354 192.543 |
| | NP guest | 186.551 180.422 192.211 192.355 180.427 192.823 192.346 192.445 193.079 192.782 |
| | pVM guest | 152.194 155.472 152.563 152.501 153.082 152.604 152.898 153.200 152.917 154.926 |

### T3. LLC-boundary point as two levels (low < 11.2 <= middle < 12.0 <= high)

| Data set | Mode | n low / middle / high | mean of low | mean of high | overall mean | overall median |
|---|---|---|---|---|---|---|
| CONFIG.host | kvmoff | 6 / 0 / 4 | 10.454 | 12.326 | 11.203 | 10.815 |
| CONFIG.host | nVHE | 5 / 0 / 5 | 10.156 | 12.397 | 11.276 | 11.410 |
| CONFIG.host | VHE | 2 / 2 / 6 | 10.608 | 12.533 | 11.961 | 12.447 |
| CONFIG.host | protected | 4 / 1 / 5 | 10.402 | 12.524 | 11.600 | 12.123 |
| standalone | kvmoff | 4 / 1 / 5 | 10.133 | 12.442 | 11.446 | 12.051 |
| standalone | nVHE | 3 / 0 / 7 | 10.270 | 12.532 | 11.854 | 12.532 |
| standalone | VHE | 3 / 1 / 6 | 10.275 | 12.710 | 11.878 | 12.407 |
| standalone | protected | 4 / 0 / 6 | 10.117 | 12.456 | 11.520 | 12.348 |
| CONFIG.host | nVHE noisy | 10 / 0 / 0 | 10.337 | n/a | 10.337 | 10.319 |

### T4. Random-access medians by data set: slow level, fast level, protected increment

| size MB | kvmoff | nVHE | VHE | protected try2 | protected - kvmoff (ns / %) | nVHE noisy (fast) | try1 per docs (fast) | try1 - noisy (ns) | clean nVHE / noisy | VHE guest | nVHE guest | NP guest | pVM guest | pVM - nVHE guest (ns) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 19.41 | 19.48 | 19.48 | 19.43 | +0.02 / +0.11% | 19.05 | n/a | n/a | 1.023 | 19.59 | 19.70 | 19.58 | 19.73 | +0.03 |
| 2 | 20.68 | 20.75 | 20.73 | 20.88 | +0.21 / +1.00% | 21.10 | n/a | n/a | 0.984 | 23.69 | 23.96 | 23.76 | 22.38 | -1.57 |
| 3 | 36.60 | 36.63 | 36.56 | 37.31 | +0.71 / +1.94% | 26.41 | 26.87 | +0.46 | 1.387 | 39.39 | 39.44 | 39.44 | 29.00 | -10.44 |
| 4 | 47.59 | 47.69 | 47.45 | 49.31 | +1.73 / +3.63% | 30.80 | 31.89 | +1.09 | 1.548 | 51.84 | 52.30 | 52.62 | 35.97 | -16.33 |
| 6 | 67.14 | 67.35 | 67.37 | 72.59 | +5.45 / +8.12% | 48.61 | 49.87 | +1.26 | 1.385 | 78.88 | 81.13 | 80.68 | 55.34 | -25.79 |
| 8 | 112.54 | 112.60 | 112.32 | 119.59 | +7.05 / +6.26% | 83.90 | 91.01 | +7.11 | 1.342 | 124.97 | 126.83 | 126.53 | 97.85 | -28.97 |
| 12 | 154.65 | 154.81 | 154.65 | 161.68 | +7.03 / +4.54% | 121.82 | 128.1 | +6.28 | 1.271 | 164.41 | 165.03 | 164.76 | 129.49 | -35.54 |
| 16 | 168.54 | 168.56 | 169.71 | 176.28 | +7.74 / +4.59% | 134.23 | 140.4 | +6.17 | 1.256 | 176.90 | 176.73 | 177.05 | 141.20 | -35.53 |
| 24 | 177.23 | 177.47 | 180.27 | 185.59 | +8.36 / +4.72% | 143.08 | 147.4 | +4.32 | 1.240 | 185.11 | 184.54 | 185.92 | 147.25 | -37.29 |
| 32 | 180.61 | 180.78 | 182.72 | 188.66 | +8.05 / +4.46% | 146.20 | 150.2 | +4.00 | 1.236 | 187.93 | 189.92 | 189.23 | 150.18 | -39.73 |
| 48 | 182.66 | 182.44 | 183.85 | 189.56 | +6.90 / +3.78% | 149.10 | 151.2 | +2.10 | 1.224 | 192.80 | 191.46 | 191.47 | 151.07 | -40.40 |
| 64 | 185.23 | 185.05 | 185.43 | 191.73 | +6.50 / +3.51% | 150.12 | 154.4 | +4.28 | 1.233 | 192.94 | 192.00 | 192.35 | 152.91 | -39.09 |

Iterations more than 4% below the run median, sizes 12-64 MB (6 sizes x 10 iterations): kvmoff 16/60, nVHE 7/60, VHE 6/60, protected try2 5/60; guests VHE 3/60, nVHE 7/60, NP 6/60, pVM 0/60 (always at the fast level).

Earlier host data sets, random medians at 1 / 2 / 3 / 4 / 6 / 8 MB:

| Data set | kernel, CPU lock | 1 | 2 | 3 | 4 | 6 | 8 |
|---|---|---|---|---|---|---|---|
| day-1 protected host, N=5 | 6.6.0-52, 2.1 GHz | 16.15 | 18.00 | 23.36 | 28.07 | 45.74 | 82.34 |
| day-2 default mode (no kvm-arm.mode), ksaf LSM, N=5 | 6.6.0-52, 2.1 GHz | 16.30 | 18.47 | 23.36 | 27.44 | 47.20 | 84.59 |
| day-2 default mode, no LSM, N=5 | 6.6.0-52, 2.1 GHz | 16.39 | 18.11 | 23.07 | 27.43 | 43.42 | 78.54 |
| day-2 nVHE, no LSM, N=5 | 6.6.0-52, 1.9 GHz | 18.66 | 21.33 | 26.06 | 30.07 | 46.23 | 81.10 |
| day-3 nVHE noisy, N=10 | 6.6.0-73, 1.9 GHz | 19.05 | 21.10 | 26.41 | 30.80 | 48.61 | 83.90 |
| day-3 nVHE clean, N=10 | 6.6.0-73, 1.9 GHz | 19.48 | 20.75 | 36.63 | 47.69 | 67.35 | 112.60 |
| day-3 kvmoff clean, N=10 | 6.6.0-73, 1.9 GHz | 19.41 | 20.68 | 36.60 | 47.59 | 67.14 | 112.54 |
| day-3 protected try2 clean, N=10 | 6.6.0-73, 1.9 GHz | 19.43 | 20.88 | 37.31 | 49.31 | 72.59 | 119.59 |

### T5. Signature of the fast level in three independent data sets

| Metric | host: nVHE noisy vs nVHE clean (measured) | guest: pVM vs nVHE guest (measured, medians) | host: try1 vs kvmoff (documented only) |
|---|---|---|---|
| rand 3 MB | -27.9% | -26.5% | -26.6% |
| rand 4 MB | -35.4% | -31.2% | -33.0% |
| rand 6 MB | -27.8% | -31.8% | -25.7% |
| rand 8 MB | -25.5% | -22.8% | -19.1% |
| rand 16 MB | -20.4% | -20.1% | -16.7% |
| rand 64 MB | -18.9% | -20.4% | -16.6% |
| seq stride256 4 MB | -7.5% | -12.2% | -9.6% |
| seq stride256 6 MB | -9.2% | -17.3% | -16.7% |
| seq stride256 8 MB | -9.6% | -19.2% | -7.4% |
| seq stride256 64 MB | +8.5% | +1.0% | -2.3% |
| bw_mem_rd 8.39 MB | +15.9% | +22.9% | +23.6% |
| bw_mem_rd 67 MB | -7.1% | -0.6% | -0.2% |
| bw_mem_wr 4.19 MB | +19.5% | +19.7% | n/a |
| par_mem 8.39 MB | -26.7% | -20.2% | n/a |
| lmbench tlb (pages) | 48 vs 48 | 48 vs 48 | 48 vs 48 |
| suite iteration time | 584-599 s vs 606-625 s | n/a | 579-602 s (iter 6-10) vs 610-621 s (iter 1-5) |

### T6. Inventory of direct mechanism measurements

| # | What | Machine / kernel / date | Workload | Result | Proves | Does not prove |
|---|---|---|---|---|---|---|
| 1 | perf stat, protected vs nVHE | N80, 6.6.30xcore-stat+ ('common' tree), 2026-06-11, single run each | munmap_after_write_touch 64 MB x 50 | cycles +81%, stall_backend +225%, instructions / faults / l2d_tlb_refill / 0x34 walks equal, l1d_tlb_refill +17% | munmap slowdown is backend stall with equal walk counts | anything about memory-read latency; N90; klinux kernel |
| 2 | EL2-only cycle counter | N80, same kernel, 2026-06-11 | munmap, write touch, full mmap cycle | delta = 0; positive control 168.1M cycles | no EL2 execution on these host paths | EL2 behaviour during lat_mem_rd; entry counts (none exist) |
| 3 | host stage-2 histogram (op=3) | N80, same tree, 2026-06-12, rechecked 06-15 | static inspection | 1 GB: 1019, 2 MB: 2486, 4 KB: 8046 | S2 not fragmented to 4 KB on N80 | share of RAM in 1 GB blocks; N90; klinux kernel (no op=3 there) |
| 4 | dense-touch control and 2 MB threshold sweep | N80, 2026-06-12 and 06-16 | munmap_only / op_sweep | gap per 4 KiB slot +0.27 us below 2 MB; about 0 at 2 MB; residual +0.4..+6% above | per-page TLBI is the munmap cause; nested walk is not | cause of the residual; read latency |
| 5 | in-kernel TLBI timing, core scaling, cold-load control | N80, 6.6.30xcore-stat2+, 2026-06-15 | tlbi_ab.ko | nVHE 10.0 / 23.2 ns per slot, protected 288.8 / 288.9; flat with cores; cold loads 154 ns each (protected only) | invalidating combined entries is about 12x dearer, locally | TLB refill or walk cost; no nVHE counterpart for the cold-load number |
| 6 | perf-only repeat incl. cycles:h | Kaitian, 6.6.30-pkvm-clean, 2026-06-24 | munmap_only, op_sweep | cycles:h = 0; stall_backend +118.7M of +119.5M cycles; walks equal | same as 1, 2, 4 on a second board | same limits |
| 7 | life-cycle split, LMDB, THP mitigation | Kaitian, 2026-06-11 / 06-26 | mmap_split_bench, LMDB, munmap_only | first touch +3.78%; hot touch +0.9..+1.7 ns per page beyond 48 pages; LMDB read +1.41% | steady access is a small effect there | mechanism of the small effect (never followed up) |
| 8 | paired application campaign anchors | D3000, 5 boot pairs, 2026-07-14..17 | lat_mem_rd 64 MiB stride 128 | +0.57% / +0.18% | sequential access unaffected | random access (not measured) |
| 9 | 4-mode lmbench N=10 and standalone reruns | N90, 6.6.0-73, 2026-06-03/04 | full lmbench | timing only | size profile of the protected increment | any counter-level cause |
| 10 | perf_event_open probes with pagemap | N80F3, 6.6.0-79 klinux kernel, protected only, 2026-09-30 | lmbench patterns re-implemented | walks per access 0.006 (1 MB) .. 0.97 (8 MB) .. 1.00 (16 MB+); L3 refills rise in parallel; one walk per page crossing in sequential mode; contiguity correlates with 8 MB sequential latency (rho -0.84) | how many walks the workload makes on FTC862 | that a walk costs more under protected mode (no second mode); N90 behaviour |

### T7. Ledger of doc conclusions on host memory latency / LLC boundary

| # | Conclusion | Where | Evidence type | Status |
|---|---|---|---|---|
| 1 | protected host random access +3..7% slower | SUMMARY 207-261, FINAL-REPORT 374-394, 604-630 | N=10 lmbench + standalone rerun | stands (reproduced) |
| 2 | cause = one more stage-2 walk per TLB miss, +5..10 ns | FINAL-REPORT 612-630 | none (reasoning) | never verified in June docs |
| 3 | protected host 17-33% faster | pkvm-memory-access-speedup 35-110 | try1 N=10 (raw deleted) | retracted by standalone-memory-bench-validation |
| 4 | four mechanisms for the speedup | same file 112-173; mmap overhead analysis 403-431 | none | never verified; retracted with 3 |
| 5 | speedup = stage-2 warm-up by the benchmark sequence | standalone doc 3-6, 172-197 | standalone rerun | retracted by section 9 of the same doc |
| 6 | fast values = one-off stochastic 'lucky alignment' in a stage-2 1 GB block | SUMMARY 221-223, 392-396; pkvm.md 224-226 | try2 rerun | 'not a pKVM benefit' stands; 'one-off, stage-2 related' contradicted by raw data |
| 7 | LLC 8 MB sequential +12.1% real overhead; sequential 0..+14% | pkvm.md 205-214; standalone doc 376-386, 409 | medians of bimodal data | never verified; mixture artifact |
| 8 | LLC 8 MB: pkvm fastest (10.01); DRAM 64 MB 10.11 | SUMMARY 104-105 | try1 | stale, contradicts FINAL-REPORT 371-372 |
| 9 | VHE 8 MB value is single-iteration jitter | vhe.md 196-197 | none | never verified; point is bimodal |
| 10 | L1/L2/1 MB and tlb identical; bw DRAM ±0.5% | SUMMARY 267-273 | N=10 | first part stands; bandwidth part inaccurate (-1.6%, -3.3%) |
| 11 | steady access unaffected; nested walk increment very small; at most 2-3 cycles | mmap overview 160-171, 754-769; overhead analysis 341-344, 512-515 | sequential lmbench, D3000, Pixel | stands for sequential only; silent on random; cycle estimate never verified |
| 12 | munmap slowdown = nested walk (a-2) | n80-gate-c0 290-295; c1-granularity 204-215 | perf stat | retracted by c1-tlbi-threshold |
| 13 | lat_mmap slowdown = 500 ns stage-2 abort per touched page | SUMMARY 173-187; FINAL-REPORT 562-602 | arithmetic fit | retracted by life-cycle split and EL2 gate, still printed |
| 14 | munmap penalty is cross-core broadcast (74%) | INVESTIGATION-LOG 22-25, 70-90 | min statistics | retracted in the same log (min artifact) |
| 15 | nVHE +16% on all host metrics; pKVM host built on VHE | findings-2026-06-02 164-214 | N=5, mismatched CPU frequency | retracted by day-3 SUMMARY |
| 16 | host stage-2 99.5% 1 GB blocks | c1-granularity 27-41 | hypervisor instrumentation, N80 | stands for N80 / IPA space; not measured for N90 |
| 17 | pVM guest 20% faster on random 64 MB, reason unknown | vm-lmbench-methodology 195, 264-266 | 10-run means | warning stands; unexplained there |
| 18 | macro overhead 5-15% | FINAL-REPORT 708-712 | none | never verified; D3000 shows 1-3% |
| 19 | LLC +3.55% = bimodal noise from page placement | llc-boundary-8mb-analysis (2026-09-30) | reanalysis of CSVs | statistics confirmed; physical cause unverified for N90 |

### T8. Instability warnings in the docs and cross-check result

| Doc claim | Where | Raw-data check | Match? |
|---|---|---|---|
| try2 random 64 MB: 193 193 192 192 191 166 191 192 192 191, 'only one blip' | pkvm.md 218-222; standalone doc 363-369 | 192.6 193.1 191.6 191.9 191.1 166.4 191.3 192.3 192.2 178.8 | iterations 1-9 yes; iteration 10 no (178.8) |
| try1 random 64 MB: 194 179 194 154 154 155 155 154 154 154 | standalone doc 31-40 | raw data excluded from repo (commit 18e4c3a6) | cannot be checked |
| kvmoff / nVHE / VHE 'have no transition, all 10 iterations stable' | standalone doc 42 | 3 of 10 iterations >4% low at 64 MB in each; kvmoff 16/60 low at 12-64 MB | no |
| iteration durations per mode | FINAL-REPORT 281-292 | differences of raw header time stamps, first 9 intervals | yes (max 1 s off) |
| nVHE 8 MB MAD 9.37%, 64 MB 1.82%; VHE 8 MB 1.44%, 64 MB 3.16% | nvhe.md 163-164; vhe.md 165-166 | recomputed | yes |
| VHE iteration 3: lat_unix 10.89, bw_tcp 2039 'vs 2380' | vhe.md 88-92 | 10.8901 and 2039.01; median bw_tcp is 2182.6, 2380 is iteration 2 | values yes, comparison value no |
| noisy vs clean nVHE: null syscall 0.1028 vs 0.1029, lat_tcp 28.36 vs 22.70 | SUMMARY 300-303 | 0.10285 vs 0.1029; 28.355 vs 22.695 | yes (memory metrics of the noisy run never examined by the docs) |
| standalone medians table | standalone doc 92-115 | recomputed from logs | yes |
| host CSVs equal raw reports | derived-data-audit 32-46 | independent parse of 2630 memory rows per mode | yes |

### T9. Paper sections 5.2 / 5.3 versus the docs (memory latency and bandwidth only)

| Paper statement | Docs | Raw data |
|---|---|---|
| 10-run averages | medians, chosen for robustness (FINAL-REPORT 90-96) | mean vs median changes LLC Bnd from +3.55% to +12.09% |
| LLC boundary +3.55% is a marked overhead | +12.1% / about 0% / 'pkvm fastest' in three docs; MAD 9.37% noted; today's doc: noise | bimodal; p = 0.40 |
| random 64 MB +3.25% | +3.5% (median), +3.7..+3.9% (standalone); mechanism asserted, not measured | reproduced; slow-level difference +6.2..+6.9 ns |
| sequential 64 MB +0.29%: no observable translation loss | 'sequential 0..+14%'; cost amortised per page | +0.29% (p 0.77) |
| memory read bandwidth +0.55% (better than native) | -1.58% (median); 'not affected' | one kvmoff outlier iteration produces the +0.55% |
| protection fault -1.08% (better than native) | within ±1% | p = 0.40; median +0.22% |
| page fault +1.99% | SUMMARY/FINAL print the try1 value (no change); overall summary prints try2 (+2.1%) | +1.99% mean, p = 0.0001 |
| Fig. 8: all KylinX modes show about -10..-20% overhead above 10 MB on random load | 'faster than baseline must not be reported'; pVM result unexplained and mislabelled; NP +0.17% | only pVM is negative (-17..-32%); NP within about ±2%; pVM run sits in the fast machine state |
| pVM: LLC boundary latency more than 10% lower | no support | same fast-state signature (-19% median) |

### T10. Stale try1 values still printed for the protected column

| Metric | SUMMARY / FINAL-REPORT / pkvm.md | try2 CSV median | kvmoff median | try2 vs kvmoff |
|---|---|---|---|---|
| lat_proc fork (us) | 134.83 | 139.07 | 136.19 | +2.11% |
| lat_proc exec (us) | 376.38 | 385.84 | 377.31 | +2.26% |
| lat_proc shell (us) | 787.11 | 807.61 | 796.71 | +1.37% |
| lat_pagefault minor (us) | 0.2547 | 0.2599 | 0.2545 | +2.12% |
| lat_sig prot (us) | 0.1607 | 0.1594 | 0.1590 | +0.22% |
| lat_unix rt (us) | 10.267 | 9.965 | 10.388 | -4.07% |
| seq 8 MB stride256 (ns) | 10.01 (SUMMARY) / 12.12 (FINAL) | 12.123 | 10.815 | +12.09% |
| seq 64 MB stride256 (ns) | 10.11 (SUMMARY) / 10.34 (FINAL) | 10.345 | 10.357 | -0.12% |
| bw_mem_rd 67 MB (MB/s) | 18154 | 18153.9 | 18446.0 | -1.58% (matches try2) |
| rand 64 MB (ns) | 191.73 | 191.73 | 185.23 | +3.51% (matches try2) |
