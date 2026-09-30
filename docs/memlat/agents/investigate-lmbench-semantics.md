# 调查代理报告：lmbench-semantics

> 这是多代理调查阶段的原始报告，英文原文照录。它的结论在使用前还要经过独立核查，
> 核查结果见同目录下的 verify-*.md。

## Headline

Both reviewer-cited numbers are differences of 10-run MEANS of lmbench's min-of-11 pointer-chase timings, each run measured in a freshly forked child on a freshly allocated 64 MiB buffer: 'LLC Bnd' is the sequential stride-256 chain over the first 8 MiB (2048 pages, 32768 lines = exactly the 16-way capacity of the 2048 L3 sets that stride can reach), 'Rand Mem' is the -t chain over all 16384 pages in which every load lands on a different page and line (one first-level DTLB miss, one page walk and one DRAM line per load). The +3.55% is not a hypervisor effect: that point is bimodal (about 10.3 vs 12.4 ns) in all four modes and in the standalone reruns, each child lands in the slow mode independently with p about 0.47, pkvm drew it 6/10 times and kvmoff 4/10 (exact permutation p = 0.40; VHE, which has no host stage 2, is +6.8%; the median of the same data gives +12.1%). The +3.25% is the blurred, mean-based view of a stable additive offset of about +6.5 to +7.3 ns per load at every size >= 8 MiB (8 MiB: +6.26%, 95% CI +5.9..+6.7, all 10 pkvm runs above all 30 baseline runs) that grows in step with the page-walk rate (zero up to 2 MiB) and is absent in sequential page order (stride 16, 64 MiB: +0.001 ns). Physical placement, the effective THP state and the SoC interconnect (NoC) frequency governor were neither controlled nor recorded, and a whole-boot 'fast state' (random 64 MiB about 150 instead of 185 ns) exists under nVHE too and coincides with the protected-VM curve behind Figure 8's negative overhead.

## Findings

### lmbench-semantics#1 (DOCUMENTED, confidence high)

Commands: 'Memory load latency' = lat_mem_rd -P 1 64 16 32 64 128 256 512 1024 and 'Random load latency' = lat_mem_rd -t -P 1 64 16, run once per lmbench iteration inside 'taskset -c 0 bash scripts/lmbench configs/CONFIG.host' with stderr captured as the report. The lmbench sources involved are unmodified upstream 3.0-a9.

Evidence: kylin-lmbench scripts/lmbench:439,470-477 (FASTMEM=NO branch at 473, -t at 477); configs/CONFIG.host:15-20,24,33 (ENOUGH=10000, TIMING_O=0, LOOP_O=0, SYNC_MAX=1, LMBENCH_SCHED=DEFAULT, MB=64, FASTMEM=NO); bench.sh:62-71 (taskset at 68); raw report results/n90-day3-host/n90-kvmoff-noLSM-full-cpu0-iter1.txt:5-27 echoes [ENOUGH: 10000] [FASTMEM: NO] [MB: 64] [SYNC_MAX: 1], banners at lines 551 and 797; git log shows only the import commit 3328c6a9 touching src/lat_mem_rd.c, src/lib_mem.c, src/lib_timing.c, scripts/lmbench.

### lmbench-semantics#2 (DOCUMENTED, confidence high)

Size grid: 33 sizes from 512 B to 64 MiB (x2 below 1 KiB, +1 KiB up to 4 KiB, then +1/4 of the next power of two, i.e. ... 3, 4, 6, 8, 12, 16, 24, 32, 48, 64 MiB). Sequential strides 16..1024 give 230 points per invocation (512 B skipped for stride 1024), the random test 33 points at stride 16. The L3 region is sampled only at 4, 6, 8 and 12 MiB.

Evidence: src/lat_mem_rd.c:19 (LOWER 512), 64-65, 74-82, 121, 154-169; emulation in chain_sim.py reproduces the 33 sizes; each CSV has 2300 lat_mem_rd_load and 330 lat_mem_rd_rand rows = 10 iterations x (230+33).

### lmbench-semantics#3 (DOCUMENTED, confidence high)

Process model: every (stride,size) point is measured in its own forked child that allocates its own buffer, malloc(maxlen + 2 pages) = 64 MiB + 8 KiB regardless of the size under test, plus a 128 KiB page-permutation array. Only 'range' bytes are touched: sequential = the first range bytes, first-touched in ascending address order; random = range/4096 pages scattered over the whole 64 MiB, first-touched in chain order with all 256 words of each page written. The parent never touches the buffer and the child exits after reporting, so every data point has its own physical page assignment. Children inherit the cpu0 affinity.

Evidence: src/lat_mem_rd.c:123-127,143-144 (state.len=range, state.maxlen=len, benchmp(fpInit, benchmark_loads, mem_cleanup, 100000, ...)); src/lib_timing.c:225-263 (fork at 231, handle_scheduler at 244), 627-628 (initialize(0,cookie) in the child), 745-754 (child exits); src/lib_mem.c:145-153 (npages, nmpages, srand(getpid()), permutation(nmpages,..), malloc(maxlen + 2*pagesize)), 169-172 (page alignment), 198-201, 254-269; src/lib_timing.c:1631-1668; src/lib_sched.c:49-53 (DEFAULT = do nothing). That glibc serves the 64 MiB request with a fresh anonymous mmap is INFERRED (glibc is not in the repo).

### lmbench-semantics#4 (DOCUMENTED, confidence high)

The chain is rebuilt before every timed interval: benchmp_interval calls initialize(iterations,..) and then start(); stride_initialize and thrash_initialize have no early return of their own (only base_initialize returns when iterations != 0), so every pointer is rewritten outside the timed region, all touched lines are dirtied and p[0] is reset to the chain head. thrash_initialize also re-mallocs its 2 KiB words array each time without freeing it.

Evidence: src/lib_timing.c:757-760; src/lib_mem.c:138, 194-203, 218-219, 248-249, 270.

### lmbench-semantics#5 (DOCUMENTED, confidence high)

Sequential pattern (stride_initialize): addr[i] -> addr[i+stride] over [0,range), wrapping to addr[0]. One lap = range/stride loads visiting range/4096 pages in ascending VA order, 4096/stride consecutive loads per page, range/max(stride,64) distinct lines. For the LLC Bnd row (stride 256, 8 MiB): 32768 loads per lap, 2048 pages, 16 loads per page each on a different line (every 4th line), 32768 distinct lines = 2 MiB of line data; one benchmark iteration is 32800 loads and one timed interval is about 311 laps (110 ms).

Evidence: src/lib_mem.c:185-204; src/lat_mem_rd.c:94-110,128 (count = 100*(len/(line*100)+1)); chain_sim.py and point_anatomy.py outputs in the scratch dir.

### lmbench-semantics#6 (DOCUMENTED, confidence high)

Random pattern (thrash_initialize, all sizes that are multiples of 4096): it uses the FIRST size/4096 entries of a random permutation of ALL 16384 pages of the 64 MiB buffer, so an 8 MiB run uses 2048 pages spread over the full 64 MiB of virtual address space. The chain is a single cycle of size/16 words: each load goes to the next page of a fixed cyclic page order and to the next word index in bit-reversed order (in-page offsets 0, 2048, 1024, 3072, 512, ...). Hence no two consecutive loads share a page, one pass over the pages touches exactly one new cache line per page, all size/64 lines are used and a line is revisited only every 64 passes. For Rand Mem (64 MiB): 4194304 loads per cycle, 16384 pages, 1048576 lines; one benchmark iteration = one full cycle = 256 passes over the page sequence = about 0.78 s, and each of the 11 timed intervals is exactly one iteration.

Evidence: src/lib_mem.c:145-152 (permutation over nmpages, which is derived from maxlen), 206-273 (branch at 235, chain at 254-269, source comment at 222-234 'Access a different page each time ... maximal thrashing in the cache between the user data stream and the page table entries'), 525-546 (bit reversal); src/lat_mem_rd.c:42-44. Emulation (chain_sim.py, 8 MiB): cycle length 524288 = len/16, 0 consecutive loads on the same page, 2048 pages spanning 63.98 MiB, identical page order on successive passes, first-touch order equals chain order, line reuse distance exactly 64 passes. Sizes 512, 1024, 2048, 3072 and 6144 B take the other branch (word permutation inside the first len bytes).

### lmbench-semantics#7 (MEASURED, confidence medium)

TLB consequences. Sequential order costs at most one TLB miss per page (stride/4096 per load: 0.4% at stride 16, 6.25% at stride 256, 25% at stride 1024). The -t order is a fixed cycle over npages distinct pages, so with LRU-like replacement every load misses once npages exceeds the capacity. The N80 PMU logs (same core type) confirm both: l1d_tlb_refill = 1.000 per load for every random size >= 0.5 MiB; l2d_tlb_refill per load = 0.000 (256 pages), 0.007 (384), 0.04 (512), 0.18 (768), 0.48 (1024), 0.84 (1536), 0.965 (2048), 0.998 (3072), 1.000 (>= 4096 pages); sequential 64 MiB gives exactly stride/4096 (0.0156, 0.0313, 0.0625, 0.125, 0.25). A set-overflow fit of the random curve puts the second-level TLB at roughly 1.0k-1.2k 4K entries (about 4-4.6 MiB of reach).

Evidence: results/memlat-n80-20260930/expA.log and expD.log parsed independently (n80_logs.py, out-n80_logs.txt). N90 side: 'tlb: 48 pages' at raw report line 514 and the +1.2 ns step between 48 and 64 pages in the kvmoff random curve (6.739 -> 7.938 ns). The TLB-size figure is INFERRED from a Poisson set-overflow model (best candidates 1152 and 1024 entries 8-way, SSE 0.004-0.02).

### lmbench-semantics#8 (MEASURED, confidence high)

Prefetching: the sequential test is a prefetcher-throughput measurement, the random test is not prefetchable (the next address is known only when the previous load completes and neither page order nor in-page offset has a stride). At equal footprint the kvmoff medians are 4.44 ns (sequential, stride 256) vs 19.4 ns (random) at 1 MiB and 10.36 vs 185.2 ns at 64 MiB. In the N80 logs sequential latency equals L3 refills per load divided by about 0.085-0.11 lines per ns from 4 to 64 MiB, i.e. it is set by a DRAM line-throughput limit.

Evidence: results/n90-day3-host/n90-kvmoff-noLSM-full-cpu0.csv medians (curve_spread.py); results/memlat-n80-20260930/expB.log: 0.109, 0.098, 0.085, 0.089, 0.091, 0.096 refills per ns at 4/6/8/12/16/64 MiB; src/lib_mem.c:178-184 (comment that the stride pattern should be predicted by any decent hardware prefetcher).

### lmbench-semantics#9 (INFERRED, confidence high)

Page-table footprint: a sequential run of S bytes uses S/2MiB contiguous leaf tables and S/32KiB PTE cache lines (8 MiB: 4 tables, 256 lines; 64 MiB: 32 tables, 2048 lines = 128 KiB). A random run touches PTEs in all 32 leaf tables (33 if the buffer is not 2 MiB aligned) for any size >= 1 MiB and about 2048*(1-(1-n/16384)^8) PTE lines: 826 at 4 MiB, 1344 at 8 MiB, 2048 at 64 MiB; consecutive walks almost always use a different leaf table and a different PTE line.

Evidence: chain_sim.py, 20 permutations per size: 823.3 / 1332.0 / 2048.0 lines and 32.0 tables at 4 / 8 / 64 MiB; follows from src/lib_mem.c:152,254-262. Consistent with N80 l2d_cache_refill per load in the random test rising from 1.07 at 8 MiB to 1.23 at 64 MiB (one data line plus 7-23% of PTE reads missing the L2 cache), results/memlat-n80-20260930/expA.log.

### lmbench-semantics#10 (DOCUMENTED, confidence high)

Reported value: each printed number is the MINIMUM over 11 timed intervals (TRIES = 11) of elapsed time per load, every interval at least 95 ms (rescaled towards 110 ms; for Rand Mem one 0.78 s traversal), all in the same child on the same physical pages: result = 1000 * usec / (count * iterations) ns, printed with 3 decimals. No overhead is subtracted (TIMING_O=0, LOOP_O=0), timing is gettimeofday, and ENOUGH=10000 has no effect because lat_mem_rd requests 100000 us. The CSV 'value' is that printed number; the 10 values per (bench,variant) per config are 10 different children from 10 lmbench iterations about 10 minutes apart. Min-of-11 removes transient slowdowns inside a child, keeps transient speed-ups, and cannot remove anything that is constant for the child (its page placement).

Evidence: src/lat_mem_rd.c:143-150 (save_minimum at 148, formula at 149, print at 150); src/lib_timing.c:173,178-179, 662-670, 702-726 (accept if result > 0.95*enough, rescale to 1.1*enough), 777-807, 1219-1241 (insertsort biggest to smallest), 1259-1269 (save_minimum takes v[N-1]), 1326-1327, 1376-1377, 1406-1411, 1540-1542; src/bench.h:198; parse-lmbench.py:69-70,88-89,187-194; bench.sh:62-74.

### lmbench-semantics#11 (MEASURED, confidence high)

The four CSVs behind Figure 7 are byte-identical to a fresh parse of the raw iter1..10 reports.

Evidence: parse-lmbench.py run on results/n90-day3-host/<env>-cpu0-iter{1..10}.txt into the scratch dir and compared with cmp against the committed CSVs for kvmoff, nvhe, vhe and pkvm-try2: all four identical.

### lmbench-semantics#12 (DOCUMENTED, confidence medium)

Controls applied to the host runs: whole lmbench script pinned with taskset -c 0; all 8 cpufreq policies set to governor performance with min = max = 1900000 kHz; cpuidle states >= 1 disabled; the global THP knob written to never; ASLR set to 0; about 90 system and 12 user services masked and killed, default target multi-user; cmdline lsm= audit=0 kvm-arm.mode=<mode>. Per run only kernel release, cmdline and cpu_max_freqs are recorded; the THP and ASLR state at measurement time rests on procedure (bench.sh --no-prep after a manual prepare-host.sh and verify-clean-env.sh) and is not stored in any result artifact.

Evidence: bench.sh:42-44,49-54,68; prepare-host.sh:19-32,34-39,41-44,46-49; scripts/apply-masks.sh:12-108 (90 entries),110-124,147-151; scripts/verify-clean-env.sh:38-57; QUICK-START.md:105-125; results/n90-day3-host/*-summary.txt (cpu_max_freqs 1900000 x 8, cmdline with kvm-arm.mode).

### lmbench-semantics#13 (MEASURED, confidence high)

Each host configuration is ONE boot: its 10 iterations ran back to back starting 5-7 minutes after boot (vhe 06-03 22:20 to 00:03, kvmoff 06-04 00:11 to 01:54, nvhe 02:02 to 03:44, pkvm try2 06-04 12:05 to 13:47), about 10 min 13 s per iteration with the memory-latency section last. Mode is therefore confounded with boot.

Evidence: date and uptime lines 37-38 and the closing date line of every results/n90-day3-host/*-iterN.txt (e.g. kvmoff iter1 '00:11:49 up 7 min', iter10 'up 1:39').

### lmbench-semantics#14 (DOCUMENTED, confidence high)

Not controlled and not recorded: physical frame placement (no pagemap dump, no drop_caches or compaction, page cache deliberately not flushed), page colour and VA-to-PA adjacency; activity on the other seven cores, which share the single 8 MiB L3 (no isolcpus, nohz_full or irqaffinity in any recorded cmdline); per-size mTHP knobs; the interconnect (NoC) devfreq governor. In the kernel lineage of the measured build the defaults are THP=always, multi-size THP and contpte are present, and the Phytium NoC devfreq driver defaults to the simple_ondemand governor polled every 100 ms (upthreshold 80), the same time scale as lmbench's 110 ms timing interval; the N80 sibling on the same OS shows 'THP enabled: [always]' with 3.8 GB of AnonHugePages and a nocfreq device with 600-1800 MHz operating points.

Evidence: grep over bench.sh, prepare-host.sh, quiet-host.sh, scripts/apply-masks.sh, scripts/verify-clean-env.sh, scripts/lmbench finds no drop_caches, compaction, pagemap, isolcpus or devfreq handling; docs/EXPERIMENT.md:64. klinux at the commit of the measured version (1e6773d13b560, 6.6.0-73.76): arch/arm64/configs/kylinos_generic_defconfig:222 (CONFIG_TRANSPARENT_HUGEPAGE=y) and :1855 (CONFIG_ARM_PHYTIUM_NOC_DEVFREQ=m), drivers/devfreq/phytium_noc.c:307,344,351 (HEAD: 476,528,537-541), mm/huge_memory.c contains huge_anon_orders_*; HEAD mm/Kconfig:889-897 (default TRANSPARENT_HUGEPAGE_ALWAYS), mm/huge_memory.c:80-83,749-754, arch/arm64/Kconfig:2430-2433. results/memlat-n80-20260930/hw-survey-n80.txt and devfreq-survey-n80.txt.

### lmbench-semantics#15 (MEASURED, confidence high)

Figure 7 memory-latency bars are the PAPER_TABLE rows of the xlsx builder, in the same order: Prot Fault = lat_sig prot; Page Fault = lat_pagefault minor; L1 Cache = lat_mem_rd_load stride256_sz0.06250MB; L2 Cache = stride256_sz0.50000MB; LLC = stride256_sz1.00000MB; LLC Bnd = stride256_sz8.00000MB; Main Mem = stride256_sz64.00000MB; Rand Mem = lat_mem_rd_rand stride16_sz64.00000MB. The statistic is the arithmetic MEAN of the 10 iteration values; overhead = 100*(mean_pkvm - mean_base)/mean_base. Recomputing from the raw CSVs reproduces the paper exactly: -1.08, +1.99, +3.55, +0.29, +3.25 vs kvmoff; LLC Bnd -3.02 / +2.87, Main Mem -3.46 / +1.06, Rand Mem +3.82 / +3.88 vs VHE / nVHE. With the median (the other spreadsheet) LLC Bnd is +12.09% and Rand Mem +3.51%. L1 Cache, L2 Cache and LLC Bnd sit exactly at the nominal capacity of L1d (16 pages), L2 (128 pages) and L3 (2048 pages).

Evidence: scripts/build-xlsx-mean.py:21,28-33,53-61,160,214-223,268,377-379; docs/n90-kvm-host/lmbench-N10-4config-mean.xlsx sheet Highlights rows 30-37 read with zipfile (J35 = 3.546403, J36 = 0.285125, J37 = 3.252091, K35 = -3.018092, L35 = 2.872396); fig7_rows.py on the four CSVs; paper.txt [P147]-[P149] (mean of 10 repetitions; the figure shows means). The English bar labels are not in the repo (the plotting script is absent); the mapping rests on row order plus exact numeric agreement.

### lmbench-semantics#16 (INFERRED, confidence high)

Cache arithmetic: a page-aligned buffer walked with stride s touches 4096/s line offsets per page (64 for s <= 64), so it reaches colours x 4096/s sets of a cache; the capacity of those sets divided by the lines per page is colours x ways pages for EVERY stride: 16 pages = 64 KiB for L1d (4 colours x 4 ways), 128 pages = 512 KiB for L2 (16 x 8), 2048 pages = 8 MiB for L3 (128 x 16). Footprint over capacity of the reachable L3 sets is 0.5 / 0.75 / 1.0 / 1.5 / 2.0 at 4 / 6 / 8 / 12 / 16 MiB for strides 64..1024 (stride 256 at 8 MiB: 32768 lines into 2048 sets x 16 ways) and likewise for the random test. Fitting at 8 MiB needs exactly 16 pages of each of the 128 physical colours. With independent random colours and LRU-like replacement under a cyclic order, the fraction of loads hitting an over-subscribed set is P(Poisson(pages/128) >= 16) = 0.008 / 0.155 / 0.53 / 0.97 / 1.00 at 4 / 6 / 8 / 12 / 16 MiB with a run-to-run SD of only about 0.03; with contiguous frames it is 0 up to 8 MiB and 1 beyond. 8 MiB is therefore the most placement-sensitive size for every stride, but the colour histogram by itself predicts a nearly constant miss fraction from run to run, not two modes.

Evidence: cache_arith.py (out-cache_arith.txt), 2000 Monte Carlo placements per size; geometry L1d 256 sets x 4, L2 1024 x 8, L3 8192 x 16, 64 B lines from results/memlat-n80-20260930/hw-survey-n80.txt (lscpu -C and sysfs index0-3).

### lmbench-semantics#17 (MEASURED, confidence high)

Measured kvmoff curve vs the arithmetic: latency leaves the L1 plateau (2.223-2.224 ns) between 64 and 96 KiB for every stride (the 64 KiB point itself fits in every run); the L3 transition lies between 4 and 8 MiB for every stride >= 64 (step 4->6 MiB +44..+50%, 6->8 MiB +31..+46% for strides 128-1024) and the curve is flat or falling beyond 8 MiB (stride 128: -13% from 8 to 12 MiB). Run-to-run RSD at 4 / 6 / 8 / 12 / 64 MiB is 0.07 / 1.7 / 8.9 / 3.9 / 2.3% for stride 256; 8 MiB is the most variable point of the whole curve for strides 64, 128 and 256 and the second for 512 (behind a separate anomaly at 0.25 MiB), with a min-max range of 16-23% at every stride >= 64. Boundary location and spread maximum match the arithmetic.

Evidence: jumps_kvmoff.py and curve_spread.py on results/n90-day3-host/n90-kvmoff-noLSM-full-cpu0.csv (table below).

### lmbench-semantics#18 (MEASURED, confidence high)

The LLC Bnd point is bimodal in every mode. Pooling the four Figure-7 boots, the second nVHE boot and the four standalone boots (90 samples, stride 256, 8 MiB) gives two clusters, 9.93-11.47 ns (n = 42, mean 10.33) and 11.69-13.07 ns (n = 48, mean 12.44), ratio 1.20; even the fast cluster is at the 64 MiB level (kvmoff 9.98-10.73), so the L3 gives no latency benefit at this point in any run. Slow-mode counts in the Figure-7 data are kvmoff 4/10, nvhe 5/10, vhe 7/10, pkvm 6/10 (threshold 11.5 ns; 8/10 for vhe with an 11.3 threshold), which reproduces the ordering of the means (11.20 < 11.28 < 11.60 < 11.96); one run changing mode moves a 10-run mean by 1.9%. pkvm vs kvmoff: +0.40 ns, Welch t = 0.86, exact permutation p = 0.40, bootstrap 95% CI -4.1%..+11.3%, Fisher p = 0.66 for 6/10 vs 4/10. A two-point mixture gives SE 4.2% for the difference of two 10-run means, so +3.55% is 0.85 sigma and about 108 iterations per mode would be needed to resolve a 3.5% shift. The same statistic at the other strides has mixed signs (+3.5, -5.0, +3.55, +2.8, -1.8%; mean +0.6%), and over strides 64-1024 pkvm has the FEWEST slow draws (20/50 vs 24, 21, 28).

Evidence: all_runs_8mb.py, llc_bnd_extra.py, stats_tests.py, slow_mode.py on results/n90-day3-host/*.csv and results/standalone-mem-bench/standalone-*.log; per-iteration values in the table below.

### lmbench-semantics#19 (MEASURED, confidence high)

The mode is decided per child, not per lmbench run: at 8 MiB the number of slow strides (of 5) per (config, iteration) is distributed 1/10/11/12/5/1 over 0..5, against a binomial expectation of 1.8/7.6/13.2/11.5/5.0/0.9 for independent draws with p = 0.465. The same +20% slow state also occurs at 12-64 MiB, less often (11%, 6%, 6.5%, 3.5%, 3.5%, 2.5% of 200 samples) and clustered in time: P(next larger size slow | this one slow) = 0.20-0.71 against 0.00-0.03 otherwise, and 13 of the 22 slow samples at 12 MiB come from the vhe boot. It never occurs at 4 or 6 MiB (0/200 each) nor for strides 16 and 32.

Evidence: slow_adjacency.py and slow_mode.py (threshold 1.12 x the lower-half median of the 40 pooled samples per point).

### lmbench-semantics#20 (MEASURED, confidence high)

Sequential DRAM-regime rows differ between boots that all lack host stage 2: Main Mem (stride 256, 64 MiB) vhe vs kvmoff +3.9% (permutation p = 0.011), vhe vs nvhe +4.7% (p = 0.002); LLC Bnd vhe vs kvmoff +6.8%. The medians of kvmoff, nvhe and vhe spread by 2.6-5.2% (stride 64), 3-7.5% (stride 256) and 5.5-12.5% (stride 1024) at 12-64 MiB. The Figure-7 bars 'LLC Bnd -3.0%' and 'Main Mem -3.5%' against VHE are this boot-to-boot floor, not a KylinX gain.

Evidence: stats_tests.py (pairwise block among the three non-protected configs), delta_curve.py column spread3.

### lmbench-semantics#21 (MEASURED, confidence medium)

On the N80 sibling (30 fresh processes per size with physical frame numbers read from pagemap) the fraction of pages in over-subscribed L3 colours at 8 MiB is 0.45-0.61 (median 0.536), the value the random-colour model predicts (0.53), and 0.09-0.42 at 6 MiB, 0.92-1.0 at 12 MiB. Latency does not follow colour: Spearman(ns, colour overflow) is +0.51 raw and +0.21 after controlling for contiguity, whereas Spearman(ns, fraction of VA-adjacent pages that are PA-adjacent) is -0.86 (-0.82 controlling for colour; -0.87, -0.99, -0.93, -0.92 at 6, 12, 16, 64 MiB) and l3d_cache_refill per load is nearly constant (0.767-0.808 in 29 of 30 runs). Re-mapping the SAME frames in physically sorted vs shuffled virtual order changes the 8 MiB stride-256 latency from 8.84 to 9.50 ns (+7.4%, contiguity 0.68) and from 7.98 to 9.62 ns (+20.5%, contiguity 0.99) with identical colour histogram and L3 refills (0.777 vs 0.783); +10-11% at 12-32 MiB, nothing at 4 MiB. So the colour arithmetic locates the boundary, but on that machine the two latency states are not L3 set conflicts; VA-order physical adjacency is a demonstrated driver (its NoC governor was fixed at performance during these runs).

Evidence: results/memlat-n80-20260930/expB.log, expL.log, expL-smoke.log parsed independently by n80_logs.py (out-n80_logs.txt); prediction from cache_arith.py. Transfer to the N90 is INFERRED: no pagemap or PMU data exist for the N90 runs.

### lmbench-semantics#22 (MEASURED, confidence high)

The set-overflow model is confirmed in the N90 data at the L1 level, where the colour is a virtual-address bit pair and therefore random in the -t test: the predicted probability that no L1 colour holds more than 4 of n random pages is 0.981 / 0.890 / 0.402 / 0.014 for n = 6 / 8 / 12 / 16, and the measured fraction of runs still at L1 latency (< 2.24 ns, 40 runs over 4 configs) is 0.975 / 0.775 / 0.300 / 0.025, while the sequential test (VA-contiguous, perfectly balanced colours) stays at 2.223-2.224 ns in all 40 runs up to and including 64 KiB.

Evidence: l1_colour_check.py (200000 Monte Carlo draws per n) on the four day3 CSVs, rows lat_mem_rd_rand stride16_sz0.02344..0.06250MB and lat_mem_rd_load stride16 at the same sizes.

### lmbench-semantics#23 (MEASURED, confidence high)

Random test, pkvm minus the three non-protected modes (medians, ns per load): -0.03 (1 MiB), +0.08 (1.5), +0.16 (2), +0.71 (3), +1.74 (4), +5.30 (6), +7.11 (8), +6.98 (12), +7.35 (16), +7.27 (24), +7.29 (32), +6.57 (48), +6.49 (64 MiB), while kvmoff, nvhe and vhe agree with each other within 0.1-0.7% up to 16 MiB. In percent vs kvmoff: +3.6% at 4 MiB, +8.1% at 6, +6.3% at 8, +4.5% at 12-32, +3.5% at 64 MiB; the percentage falls only because the denominator grows. At 4, 8, 12 and 16 MiB all 10 pkvm runs lie above all 30 baseline runs (8 MiB: +6.26%, bootstrap CI +5.87..+6.67). The standalone reruns in other boots agree (8 MiB 120.0 vs 112.6-112.9; 64 MiB 192.4 vs 185.3-186.0). Divided by the N80 walk rate this is about 3.6-4 ns extra per walk at 2-4 MiB and 6.5-7.4 ns at >= 8 MiB.

Evidence: delta_curve.py, stats_tests.py, out-separation.txt, all_runs_8mb.py on the day3 CSVs and standalone logs; walk rates from results/memlat-n80-20260930/expA.log (the cross-machine division is INFERRED).

### lmbench-semantics#24 (MEASURED, confidence high)

The published +3.25% is a blurred version of that offset because it is a mean over iterations containing sporadic fast outliers that occur in every mode: at 64 MiB kvmoff has 176.3, 168.7 and 176.5 among values of 185.0-186.8, pkvm has 166.4 and 178.8 among 191.1-193.1. Mean-based: +3.25%, Welch p = 0.098, bootstrap CI -0.4..+6.6%; median-based +3.51% (permutation p = 0.031); main mode pooled with the standalone boots 185.76 +- 0.64 ns (46 of 70 runs) vs 192.19 +- 0.58 ns (16 of 20 runs), i.e. +6.43 ns = +3.46%.

Evidence: fig7_rows.py, stats_tests.py, all_runs_8mb.py.

### lmbench-semantics#25 (MEASURED, confidence high)

In sequential page order the extra cost is not visible even though a walk still occurs on every page (N80: l2d_tlb_refill = stride/4096 per load): stride 16 at 12-64 MiB, pkvm minus the other modes is -0.003..+0.001 ns per load with 256 loads per page, i.e. below about 1 ns per page walk; stride 256 at 64 MiB +0.29% (mean) / -0.12% (median). At strides 512-1024 pkvm is 0.2-0.7 ns above kvmoff and nvhe but VHE is higher still, so that gap cannot be attributed. The extra cost therefore appears only when successive walks go to unrelated pages and leaf tables, which is what the -t chain enforces on every load.

Evidence: delta_curve.py tables for strides 16, 64, 256, 1024; results/memlat-n80-20260930/expD.log.

### lmbench-semantics#26 (MEASURED, confidence high)

A whole-boot 'fast state' of the random test exists independent of KVM mode. The second nVHE boot kept as n90-nvhe-noisy (same kernel, cmdline and CONFIG.host, services not fully masked) has random medians 26.4 / 30.8 / 48.6 / 83.9 / 121.8 / 134.2 / 150.1 ns at 3 / 4 / 6 / 8 / 12 / 16 / 64 MiB against 36.6 / 47.7 / 67.4 / 112.6 / 154.8 / 168.6 / 185.0 in the clean nVHE boot (-19% to -35%, identical up to 2 MiB), and the day-1/day-2 boots (kernel 6.6.0-52; baremetal, nvhe and protected) show the same low values (4 MiB 27-30 ns, 8 MiB 78-85 ns). In that state the 8 MiB sequential bimodality is absent (0 slow of 50 at strides 64-1024 against 93 of 200 in the clean boots). The internal docs attribute this state to pKVM stage 2 ('lucky alignment', try1) and state that kvmoff/nvhe/vhe show no such transition; the raw data contradict both: it occurs under nVHE, and single fast children (more than 5% below the upper-half median) occur in the clean boots at 12-64 MiB in every mode (kvmoff 16, nvhe 7, vhe 6, pkvm 4 of 60) and never at <= 8 MiB.

Evidence: noisy_vs_clean.py, noisy_slow_count.py, slow_mode.py; results/n90-day3-host/n90-nvhe-noisy-full-cpu0.csv and its summary (started 2026-06-03T16:17:58, kvm-arm.mode=nvhe, cpu_max_freqs 1900000); results/n90-day1/*.csv and results/n90-day2/*.csv; docs/n90-kvm-host/standalone-memory-bench-validation.md:42,413-416 and docs/n90-kvm-host/SUMMARY.md:296-302 for the contradicted statements.

### lmbench-semantics#27 (MEASURED, confidence high)

Figure 8 uses the same two commands inside the x-kernel guest (MB=64, stride-16 rows, mean of 10). The protected-VM random curve (29.0 / 36.0 / 55.3 / 97.9 / 129.5 / 141.2 / 152.9 ns at 3 / 4 / 6 / 8 / 12 / 16 / 64 MiB) is the host fast-state curve plus 3-14 ns, while the three non-protected guests (39.4 / 52.3 / 81.1 / 126.8 / 165.0 / 176.7 / 192.0) are the host normal-state curve plus 3-14 ns. The mean-based 'overhead' is -26% at 3 MiB, -31% at 4-6 MiB and -17 to -21% from 12 MiB up, NP VM within +-4%. The pVM run was the first of the four guest runs (2026-06-05 05:31 UTC); the others followed up to a day later and the host state during each is not recorded.

Evidence: guest_rand.py on a fresh parse of results/xkernel-n90-*/*-iterN.txt (CSV copies in the scratch dir); CONFIG.xkernel.used and started.txt in each directory; host curves from the day3 CSVs.

### lmbench-semantics#28 (INFERRED, confidence medium)

The cpu0 clock during the day-3 runs was effectively 1.80 GHz, not 1.9: L1 load 2.223 ns, float add 1.11, float mul 1.67, float div 4.45 and double div 6.67 ns are 4, 2, 3, 8 and 12 cycles of 0.5556 ns (at 1.9 GHz they would be 2.105, 1.05, 1.58, 4.21, 6.32 ns). Runs with scaling_max 2100000 show L1 = 1.906 ns (4 cycles at 2.1 GHz). The '[MHZ: 1900 MHz]' line in the reports is the hand-written CONFIG value. All four modes show the same 2.223 ns, so relative comparisons are unaffected.

Evidence: lat_ops rows and stride*_sz0.00049MB rows of results/n90-day3-host/n90-kvmoff-noLSM-full-cpu0.csv; results/n90-day1/n90-host-N5-cpu0.csv with its summary; configs/CONFIG.host:7; cpu_max_freqs lines of the summaries.

### lmbench-semantics#29 (DOCUMENTED, confidence medium)

The benchmark repo records uname -r and cmdline but not the kernel config of the measured N90 kernel (6.6.0-73-generic #76-KYLINOS, built 2026-05-15). At the klinux commit carrying that version (1e6773d13b560) CONFIG_X1_RMS is 'default n', no config file in the tree sets it, and the nVHE Makefile compiles the C pKVM objects when it is unset (the Rust code lived in hyp/nvhe/rust then); CONFIG_X1_RMS=y entered kylinos_generic_defconfig on 2026-06-29 (b1b2979f0c0bf), after the 06-03/04 host measurements. Whether the Figure-7 'pkvm' runs exercised the Rust EL2 cannot be confirmed from either repository.

Evidence: klinux: git show 1e6773d13b560:arch/arm64/kvm/Kconfig line 76 (config X1_RMS, default n); git grep X1_RMS 1e6773d13b560 finds no config file; git show 1e6773d13b560:arch/arm64/kvm/hyp/nvhe/Makefile lines 11-35; git log -S CONFIG_X1_RMS=y -- arch/arm64/configs/kylinos_generic_defconfig -> b1b2979f0c0bf 2026-06-29. kylin-lmbench: results/n90-day3-host/*-summary.txt, docs/EXPERIMENT.md:91-93 (open TODO to capture the .config). The consequence for the running binary is INFERRED.

### lmbench-semantics#30 (DOCUMENTED, confidence high)

Stale or wrong statements in the internal docs: docs/PIPELINE.md:94-99 says BENCHMARK_OS is never set, but configs/CONFIG.host:36-37 sets BENCHMARK_HARDWARE=YES and BENCHMARK_OS=YES; docs/PIPELINE.md:70 says blank lines reset all parser mode state, whereas the parser resets only sub-state (parse-lmbench.py:148-157); scripts/standalone-mem-bench.sh and the n90-pkvm-noLSM-try1-* files referenced by standalone-memory-bench-validation.md:83,339 exist neither in the tree nor in git history; apply-masks.sh now lists 90 system services while the docs and xlsx README say 72.

Evidence: file:line references in the claim; git log --all -- 'results/*try1*' is empty; ls scripts shows no standalone-mem-bench.sh; awk count of SYS_NOISY entries in scripts/apply-masks.sh = 90.

## Caveats

- The N80 probe logs come from a sibling machine, not the paper's N90: different DIMMs (2 x 8 GB), kernel 6.6.0-79, protected mode only, desktop session running, system THP=always with MADV_NOHUGEPAGE on the probe buffer, NoC governor fixed at performance. I use them only for event counts per load and same-machine contrasts; transferring the adjacency-vs-colour conclusion to the N90 is an inference.
- The benchmark repo changed while I worked (four new commits between 17:08 and 17:26 +0800 on 2026-09-30, HEAD b81e27e5, adding experiments/memlat-probe, results/memlat-n80-20260930 and docs/memlat). All primary files I cite for the lmbench semantics and the N90 data are unchanged (git diff b01cae90..HEAD is empty for src, scripts/lmbench, configs, bench.sh, prepare-host.sh, parse-lmbench.py, build-xlsx*.py, results/n90-day3-host, results/standalone-mem-bench). My conclusions on LLC Bnd agree with the newly committed docs/n90-kvm-host/llc-boundary-8mb-analysis.md and worklog but were derived independently from the raw data.
- Each mode is a single boot, so every between-mode difference is confounded with boot. THP, ASLR, masked-service state and NoC frequency at measurement time are not stored in any result artifact; only kernel release, cmdline and cpu_max_freqs are.
- The lmbench binary that ran on the N90 is not in the repo (bin/ is git-ignored); compiler and flags are inferred from src/Makefile (CFLAGS=-O). glibc behaviour (64 MiB malloc served by a fresh anonymous mmap, identical addresses in every child with ASLR off) is inferred, not read from source.
- Cache geometry is the kernel-reported cacheinfo of the N80 (given in the task). The N80 l3d_cache_refill counter reads 0.48 per load at 4 MiB sequential, where latency is 4.4 ns, so either the effective L3 capacity for one core is far below 8 MiB or the event does not mean 'fetched from DRAM'; I did not resolve this, and it limits how far the L3 arithmetic can be pushed.
- The slow/fast classifications use heuristic thresholds (1.12 x lower-half median; 11.5 ns for the stride-256 8 MiB row; 0.95 x upper-half median for fast outliers). vhe has two intermediate values (11.47, 11.73), so its slow count is 7 or 8 depending on the threshold.
- The chain emulation uses Python's PRNG in place of glibc rand(); structural properties (cycle length, page change on every load, 64-pass line reuse) do not depend on the generator, the PTE-line counts are statistical means.
- The second-level TLB size (about 1.0k-1.2k entries) is a model fit to N80 counter data, not a documented figure.
- Dividing the N90 pkvm offset by the N80 walk rate mixes two machines; it is indicative only.
- No device or remote host was contacted; the conclusions rest on files in the two repositories. Scripts and outputs are under the scratch directory.

## Open questions

- What decides the slow/fast state of the sequential DRAM-regime points on the N90 (about 47% slow at 8 MiB in every clean boot, 3-11% at larger sizes, 0 of 50 in the 'noisy' boot)? Candidates: VA-order physical adjacency of the frames (demonstrated on the N80), the NoC simple_ondemand governor crossing its threshold (unverified; 100 ms polling vs 110 ms timing intervals; the large-size slow states are clustered in time), or L3 conflicts. Needs an N90 run that logs pagemap adjacency, l3d_cache_refill and /sys/class/devfreq/nocfreq/cur_freq per child.
- What is the whole-boot fast state of the random test (150 vs 185 ns at 64 MiB; present in day-1/day-2 boots, the 'noisy' nVHE boot, pkvm try1 from iteration 4, and the pVM guest run), and why do single children enter it at 12-64 MiB in clean boots (kvmoff 27%, nvhe 12%, vhe 10%, pkvm 7% of children) but never at <= 8 MiB? Candidates: THP effectively on (kernel default is always; N80 with 2 MiB pages gives 84 ns at 8 MiB, the N90 fast-state value) or the NoC frequency held high. The offset starts at 3 MiB, where both page walks and DRAM fetches begin, so the onset does not discriminate. Record THP (global and per-size knobs), AnonHugePages of the benchmark process and nocfreq governor/cur_freq/trans_stat before and after every run.
- Figure 8: the protected VM sits in the fast state and the three non-protected VMs in the normal state; the pVM run was the earliest of the four. Is this a property of protected VMs or of the host state on that day? It needs a re-run with the host state recorded.
- Why is the pkvm extra cost about 4 ns per walk at 2-4 MiB, about 7 ns per walk at >= 8 MiB and below about 1 ns per page in sequential order? This is for the kernel/architecture investigators (stage-2 granularity of the host identity map, walk-cache coverage, where leaf-table reads are served from).
- Was CONFIG_X1_RMS enabled in the N90's 6.6.0-73-generic #76 kernel used on 2026-06-03/04? At that version's commit the option defaults to n and no config in the tree sets it; it entered kylinos_generic_defconfig on 2026-06-29. Check /boot/config-6.6.0-73-generic or the build record of that package.
- What does l3d_cache_refill count on FTC862, and what is the effective L3 capacity available to one core (N80: 0.48 refills per load at a 4 MiB sequential footprint, 0.41 at 3 MiB random)?
- The script that draws Figure 7 (English labels 'LLC Bnd', 'Main Mem', 'Rand Mem') is not in the benchmark repo; the row mapping rests on order and exact numeric agreement with the mean spreadsheet.
- The N90 core clock appears to be 1.80 GHz when cpufreq reports 1900000 kHz; confirm with a cycle counter (on the N80 cycles per ns = 1.90 at the same setting).

## Tables

### T1. What one data point is (kvmoff medians; interval logic emulated from lib_timing.c:702-726)

| Fig.7 label | bench / variant | stride | size | pages touched | chain elements | distinct 64 B lines | loads per benchmark iteration | kvmoff median ns/load | ms per iteration | iterations per accepted interval | interval ms | chain traversals per interval | 11 intervals total s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L1 Cache | lat_mem_rd_load stride256_sz0.06250MB | 256 | 0.0625 MiB | 16 | 256 | 256 | 300 | 2.224 | 0.001 | 164869 | 110 | 193206 | 1.21 |
| L2 Cache | lat_mem_rd_load stride256_sz0.50000MB | 256 | 0.5 MiB | 128 | 2048 | 2048 | 2100 | 3.971 | 0.008 | 13193 | 110 | 13528 | 1.21 |
| LLC | lat_mem_rd_load stride256_sz1.00000MB | 256 | 1 MiB | 256 | 4096 | 4096 | 4100 | 4.437 | 0.018 | 6047 | 110 | 6053 | 1.21 |
| LLC Bnd | lat_mem_rd_load stride256_sz8.00000MB | 256 | 8 MiB | 2048 | 32768 | 32768 | 32800 | 10.815 | 0.355 | 311 | 110 | 311 | 1.21 |
| Main Mem | lat_mem_rd_load stride256_sz64.00000MB | 256 | 64 MiB | 16384 | 262144 | 262144 | 262200 | 10.357 | 2.716 | 41 | 111 | 41 | 1.22 |
| (Rand 4MB) | lat_mem_rd_rand stride16_sz4.00000MB | 16 | 4 MiB | 1024 (random, over 64 MiB of VA) | 262144 | 65536 | 262200 | 47.587 | 12.48 | 9 | 112 | 9 | 1.24 |
| (Rand 8MB) | lat_mem_rd_rand stride16_sz8.00000MB | 16 | 8 MiB | 2048 (random, over 64 MiB of VA) | 524288 | 131072 | 524300 | 112.544 | 59.0 | 2 | 118 | 2 | 1.30 |
| Rand Mem | lat_mem_rd_rand stride16_sz64.00000MB | 16 | 64 MiB | 16384 | 4194304 | 1048576 | 4194400 | 185.233 | 776.9 | 1 | 777 | 1 | 8.55 |

Every row: fresh fork, malloc(64 MiB + 8 KiB), 11 intervals, minimum reported, 10 such children per config (one per lmbench iteration).

### T2. Figure 7 memory-latency panel: row mapping and values (10 iterations per config)

| Fig.7 label | CSV row | kvmoff mean | nvhe mean | vhe mean | pkvm mean | mean: pkvm/kvmoff % | pkvm/vhe % | pkvm/nvhe % | median: /kvmoff, /vhe, /nvhe % | RSD % k/n/v/p |
|---|---|---|---|---|---|---|---|---|---|---|
| Prot Fault | lat_sig prot (us) | 0.16088 | 0.16036 | 0.16102 | 0.15914 | -1.08 | -1.17 | -0.76 | +0.22, -0.50, -0.34 | 3.29/1.44/3.91/2.13 |
| Page Fault | lat_pagefault minor (us) | 0.25481 | 0.25497 | 0.25722 | 0.25987 | +1.99 | +1.03 | +1.92 | +2.12, +0.81, +2.02 | 0.61/0.66/0.79/0.84 |
| L1 Cache | lat_mem_rd_load stride256_sz0.06250MB | 2.2238 | 2.2238 | 2.2239 | 2.2237 | -0.00 | -0.01 | -0.00 | 0, 0, 0 | 0.02/0.02/0.01/0.02 |
| L2 Cache | lat_mem_rd_load stride256_sz0.50000MB | 3.9753 | 3.9524 | 3.9451 | 3.9401 | -0.89 | -0.13 | -0.31 | -1.03, -0.28, -0.83 | 0.68/0.87/0.94/0.75 |
| LLC | lat_mem_rd_load stride256_sz1.00000MB | 4.4365 | 4.4363 | 4.4330 | 4.4335 | -0.07 | +0.01 | -0.06 | -0.05, +0.05, -0.03 | 0.15/0.11/0.16/0.16 |
| LLC Bnd | lat_mem_rd_load stride256_sz8.00000MB | 11.2029 | 11.2763 | 11.9612 | 11.6002 | **+3.55** | -3.02 | +2.87 | **+12.09**, -2.60, +6.25 | 8.93/10.62/6.91/9.21 |
| Main Mem | lat_mem_rd_load stride256_sz64.00000MB | 10.3814 | 10.3020 | 10.7839 | 10.4110 | +0.29 | -3.46 | +1.06 | -0.12, -4.05, +1.01 | 2.31/2.10/3.53/1.96 |
| Rand Mem | lat_mem_rd_rand stride16_sz64.00000MB | 182.2089 | 181.1044 | 181.2069 | 188.1345 | **+3.25** | +3.82 | +3.88 | **+3.51**, +3.40, +3.61 | 3.39/4.25/4.71/4.63 |
| (xlsx only) Rand 8MB | lat_mem_rd_rand stride16_sz8.00000MB | 112.5996 | 112.6825 | 112.3740 | 119.6511 | +6.26 | +6.48 | +6.18 | +6.26, +6.47, +6.21 | 0.40/0.28/0.18/0.51 |
| (xlsx only) Rand 4MB | lat_mem_rd_rand stride16_sz4.00000MB | 47.7021 | 47.6562 | 47.5050 | 49.3114 | +3.37 | +3.80 | +3.47 | +3.63, +3.92, +3.41 | 0.51/0.49/0.45/0.83 |

### T3. Per-iteration raw values (ns), iterations 1..10

| row | config | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LLC Bnd | kvmoff | 12.242 | 10.498 | 10.186 | 12.370 | 12.205 | 10.980 | 10.650 | 12.486 | 10.062 | 10.350 |
| LLC Bnd | nvhe | 10.296 | 12.434 | 12.623 | 9.985 | 9.925 | 12.267 | 12.352 | 10.553 | 12.308 | 10.020 |
| LLC Bnd | vhe | 11.474 | 12.622 | 11.727 | 12.473 | 12.446 | 12.575 | 10.919 | 12.448 | 10.297 | 12.631 |
| LLC Bnd | pkvm | 10.704 | 11.772 | 12.570 | 12.561 | 12.521 | 10.557 | 10.252 | 12.496 | 10.095 | 12.474 |
| LLC Bnd | nvhe-noisy (2nd nVHE boot) | 10.812 | 10.343 | 10.342 | 10.311 | 10.270 | 10.255 | 10.327 | 10.282 | 10.098 | 10.330 |
| LLC Bnd | standalone kvmoff | 10.087 | 10.197 | 12.383 | 10.158 | 10.092 | 12.529 | 11.719 | 12.441 | 12.469 | 12.389 |
| LLC Bnd | standalone pkvm | 12.257 | 12.472 | 10.058 | 12.497 | 12.438 | 12.561 | 10.105 | 10.140 | 12.511 | 10.165 |
| Main Mem | kvmoff | 10.240 | 10.473 | 9.981 | 10.731 | 10.241 | 10.217 | 10.586 | 10.522 | 10.633 | 10.190 |
| Main Mem | pkvm | 10.169 | 10.186 | 10.294 | 10.662 | 10.617 | 10.318 | 10.743 | 10.371 | 10.271 | 10.479 |
| Rand Mem | kvmoff | 176.314 | 185.641 | 168.704 | 185.315 | 185.150 | 176.485 | 185.057 | 186.795 | 186.202 | 186.426 |
| Rand Mem | nvhe | 186.204 | 185.862 | 164.520 | 186.567 | 185.579 | 172.185 | 175.195 | 185.915 | 184.511 | 184.506 |
| Rand Mem | vhe | 186.579 | 185.599 | 185.568 | 175.439 | 185.106 | 186.034 | 185.288 | 159.877 | 186.011 | 176.568 |
| Rand Mem | pkvm | 192.634 | 193.091 | 191.564 | 191.895 | 191.131 | 166.436 | 191.336 | 192.266 | 192.199 | 178.793 |
| Rand Mem | nvhe-noisy | 150.669 | 150.240 | 150.303 | 149.863 | 150.276 | 149.945 | 149.951 | 151.851 | 150.006 | 149.893 |
| Rand 8MB | kvmoff | 112.720 | 113.054 | 112.369 | 112.137 | 113.291 | 112.041 | 112.844 | 112.258 | 112.232 | 113.050 |
| Rand 8MB | pkvm | 119.966 | 119.990 | 118.866 | 120.224 | 119.377 | 119.216 | 119.220 | 119.050 | 120.789 | 119.813 |

### T4. Cache arithmetic (L1d 64 KiB 4-way 256 sets; L2 512 KiB 8-way 1024 sets; L3 8 MiB 16-way 8192 sets; 64 B lines; 4 KiB pages)

| stride | lines touched per page | L1d reachable sets / capacity (lines) | L2 reachable sets / capacity | L3 reachable sets / capacity | size at footprint == capacity: L1d / L2 / L3 |
|---|---|---|---|---|---|
| 16, 32, 64 | 64 | 256 / 1024 | 1024 / 8192 | 8192 / 131072 | 64 KiB / 512 KiB / 8 MiB |
| 128 | 32 | 128 / 512 | 512 / 4096 | 4096 / 65536 | 64 KiB / 512 KiB / 8 MiB |
| 256 | 16 | 64 / 256 | 256 / 2048 | 2048 / 32768 | 64 KiB / 512 KiB / 8 MiB |
| 512 | 8 | 32 / 128 | 128 / 1024 | 1024 / 16384 | 64 KiB / 512 KiB / 8 MiB |
| 1024 | 4 | 16 / 64 | 64 / 512 | 512 / 8192 | 64 KiB / 512 KiB / 8 MiB |

Page colours: L1d 4 (address bits 13:12), L2 16 (15:12), L3 128 (18:12). Footprint/capacity of the reachable L3 sets = pages / 2048 for every stride >= 64 and for the random test: 0.5 (4 MiB), 0.75 (6), 1.0 (8), 1.5 (12), 2.0 (16), 8.0 (64 MiB); pages per colour if perfectly balanced: 8, 12, 16, 24, 32, 128 against 16 ways.

### T5. Colour model (fraction of pages in colours holding more than 16 pages = predicted L3 miss ratio under LRU-like + cyclic order) vs N80 measurement

| size | pages | mean per colour | model, iid colours: mean (SD over placements) | model, runs of 32 contiguous frames | model, fully contiguous | N80 measured colour-overflow fraction, 30 fresh processes: min / median / max | N80 l3d_cache_refill per load (seq, stride 256): min / median / max |
|---|---|---|---|---|---|---|---|
| 4 MiB | 1024 | 8 | 0.008 (0.012) | 0.001 (0.011) | 0 | 0.000 / 0.000 / 0.074 | 0.475 / 0.484 / 0.615 |
| 6 MiB | 1536 | 12 | 0.155 (0.032) | 0.109 (0.110) | 0 | 0.091 / 0.192 / 0.421 | 0.670 / 0.678 / 0.758 |
| 8 MiB | 2048 | 16 | 0.532 (0.028) | 0.521 (0.076) | 0 | 0.446 / 0.536 / 0.605 | 0.767 / 0.774 / 0.924 |
| 12 MiB | 3072 | 24 | 0.966 (0.011) | 0.978 (0.031) | 1 | 0.922 / 0.964 / 1.000 | 0.856 / 0.863 / 0.988 |
| 16 MiB | 4096 | 32 | 0.999 (0.002) | 1.000 (0.002) | 1 | 0.993 / 1.000 / 1.000 | 0.893 / 0.901 / 0.993 |

The colour statistics match the model; the refill counts do not (0.48 per load already at half the nominal capacity), and latency does not track either (T12).

### T6. kvmoff measured curve: medians (ns) and spread

| test | stride | 64 KiB | step 64->96 KiB | 1 MiB | 2 MiB | 3 MiB | 4 MiB | step 4->6 | 6 MiB | step 6->8 | 8 MiB median [min..max] | step 8->12 | 12 MiB | 16 MiB | 32 MiB | 64 MiB | RSD % at 4 / 6 / 8 / 12 / 64 MiB | size of max RSD (value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| seq | 16 | 2.224 | +3.3% | 2.295 | 2.296 | 2.303 | 2.307 | +0.2% | 2.312 | -0.4% | 2.303 [2.301..2.306] | +0.1% | 2.306 | 2.308 | 2.314 | 2.317 | 0.05 / 0.18 / 0.07 / 0.08 / 0.20 | 0.094 MiB (0.53) |
| seq | 32 | 2.224 | +6.8% | 2.539 | 2.535 | 2.544 | 2.543 | +2.3% | 2.603 | +1.3% | 2.638 [2.630..2.674] | +1.3% | 2.671 | 2.670 | 2.678 | 2.675 | 0.03 / 0.08 / 0.47 / 0.28 / 0.24 | 8 MiB (0.47) |
| seq | 64 | 2.224 | +15.0% | 2.713 | 2.728 | 2.744 | 2.776 | +44.0% | 3.998 | +3.9% | 4.152 [4.092..5.054] | +4.4% | 4.335 | 4.338 | 4.280 | 4.217 | 0.07 / 0.47 / 6.84 / 0.99 / 0.51 | 8 MiB (6.84) |
| seq | 128 | 2.224 | +55.3% | 4.274 | 4.479 | 5.003 | 5.180 | +47.4% | 7.636 | +46.4% | 11.182 [9.131..11.332] | -13.2% | 9.707 | 9.549 | 9.319 | 9.034 | 0.09 / 0.29 / 6.87 / 1.96 / 1.30 | 8 MiB (6.87) |
| seq | 256 | 2.224 | +67.7% | 4.437 | 4.703 | 5.315 | 5.486 | +50.3% | 8.248 | +31.1% | 10.815 [10.062..12.486] | +0.9% | 10.918 | 11.041 | 10.704 | 10.357 | 0.07 / 1.68 / 8.93 / 3.87 / 2.31 | 8 MiB (8.93) |
| seq | 512 | 2.223 | +197.8% | 5.080 | 5.292 | 5.417 | 5.498 | +45.7% | 8.011 | +31.4% | 10.527 [9.466..11.636] | -4.0% | 10.102 | 10.079 | 9.754 | 9.573 | 0.17 / 1.08 / 9.76 / 0.93 / 0.96 | 0.25 MiB (13.74); 8 MiB second |
| seq | 1024 | 2.223 | +204.3% | 5.374 | 5.513 | 5.662 | 5.729 | +48.4% | 8.501 | +44.2% | 12.255 [10.599..12.596] | -8.5% | 11.207 | 11.230 | 10.742 | 10.473 | 0.23 / 2.83 / 6.35 / 6.73 / 1.16 | 0.25 MiB (9.12); 8 MiB sixth |
| rand | 16 | 3.833 | +57.2% | 19.409 | 20.677 | 36.602 | 47.587 | +41.1% | 67.137 | +67.6% | 112.544 [112.041..113.291] | +37.4% | 154.651 | 168.543 | 180.613 | 185.233 | 0.51 / 1.10 / 0.40 / 6.94 / 3.39 | 0.031 MiB (44.2, L1 colour lottery) |

### T7. Slow state of the sequential test (value > 1.12 x lower-half median of the 40 pooled samples), strides 64..1024, 4 Figure-7 boots

| size | slow / 200 | kvmoff / 50 | nvhe / 50 | vhe / 50 | pkvm / 50 | P(next larger size slow given this slow) | P(next slow given this not slow) | nvhe-noisy boot slow / 50 |
|---|---|---|---|---|---|---|---|---|
| 4 MiB | 0 | 0 | 0 | 0 | 0 | - | - | - |
| 6 MiB | 0 | 0 | 0 | 0 | 0 | - | - | 0 |
| 8 MiB | 93 (46.5%) | 24 | 21 | 28 | 20 | 0.204 | 0.028 | 0 |
| 12 MiB | 22 (11.0%) | 1 | 3 | 13 | 5 | 0.273 | 0.034 | 0 |
| 16 MiB | 12 (6.0%) | 0 | 1 | 9 | 2 | 0.667 | 0.027 | 0 |
| 24 MiB | 13 (6.5%) | 0 | 0 | 11 | 2 | 0.385 | 0.011 | (whole-boot level shift) |
| 32 MiB | 7 (3.5%) | 0 | 0 | 6 | 1 | 0.429 | 0.021 | (level shift) |
| 48 MiB | 7 (3.5%) | 0 | 0 | 4 | 3 | 0.714 | 0.000 | (level shift) |
| 64 MiB | 5 (2.5%) | 0 | 0 | 4 | 1 | - | - | (level shift) |

8 MiB, number of slow strides (of 5) per (config, iteration), 40 cells: observed 1 / 10 / 11 / 12 / 5 / 1 for 0..5; binomial(5, 0.465) expectation 1.8 / 7.6 / 13.2 / 11.5 / 5.0 / 0.9.

8 MiB mean of 10 iterations by stride (ns) and the Figure-7 statistic:

| stride | kvmoff | nvhe | vhe | pkvm | pkvm/kvmoff % | pkvm/nvhe % | pkvm/vhe % | slow counts k / n / v / p |
|---|---|---|---|---|---|---|---|---|
| 64 | 4.240 | 4.181 | 4.473 | 4.387 | +3.46 | +4.91 | -1.93 | 1 / 0 / 2 / 1 |
| 128 | 10.837 | 10.932 | 11.006 | 10.295 | -5.00 | -5.83 | -6.46 | 8 / 8 / 8 / 4 |
| 256 | 11.203 | 11.276 | 11.961 | 11.600 | +3.55 | +2.87 | -3.02 | 4 / 5 / 7 / 6 |
| 512 | 10.534 | 10.224 | 10.751 | 10.834 | +2.84 | +5.96 | +0.77 | 5 / 3 / 4 / 5 |
| 1024 | 11.834 | 11.858 | 12.119 | 11.625 | -1.77 | -1.97 | -4.08 | 6 / 5 / 7 / 4 |

### T8. Random test: medians (ns per load), pkvm offset, and N80 PMU counts per load at the same size

| size | pages | kvmoff | nvhe | vhe | pkvm | pkvm minus mean of the three (ns) | pkvm/kvmoff % | pkvm runs above all 30 baseline runs | N80 l2d_tlb_refill (page walks) | N80 l1d_tlb_refill | N80 l3d_cache_refill | offset / walk rate (ns) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 MiB | 256 | 19.409 | 19.480 | 19.479 | 19.429 | -0.027 | +0.11 | - | 0.000 | 1.000 | 0.000 | - |
| 1.5 MiB | 384 | 20.186 | 20.176 | 20.125 | 20.241 | +0.079 | +0.27 | - | 0.007 | 1.000 | 0.002 | - |
| 2 MiB | 512 | 20.677 | 20.752 | 20.733 | 20.883 | +0.162 | +1.00 | 1/10 | 0.040 | 1.000 | 0.082 | 4.1 |
| 3 MiB | 768 | 36.602 | 36.633 | 36.562 | 37.311 | +0.712 | +1.94 | 7/10 | 0.180 | 1.000 | 0.409 | 4.0 |
| 4 MiB | 1024 | 47.587 | 47.688 | 47.455 | 49.314 | +1.737 | +3.63 | 10/10 | 0.478 | 1.000 | 0.625 | 3.6 |
| 6 MiB | 1536 | 67.137 | 67.350 | 67.374 | 72.589 | +5.302 | +8.12 | 6/10 | 0.841 | 1.000 | 0.788 | 6.3 |
| 8 MiB | 2048 | 112.544 | 112.601 | 112.325 | 119.595 | +7.105 | +6.26 | 10/10 | 0.965 | 1.000 | 0.873 | 7.4 |
| 12 MiB | 3072 | 154.651 | 154.810 | 154.647 | 161.678 | +6.975 | +4.54 | 10/10 | 0.998 | 1.000 | 0.928 | 7.0 |
| 16 MiB | 4096 | 168.543 | 168.556 | 169.708 | 176.282 | +7.346 | +4.59 | 10/10 | 1.000 | 1.000 | 0.977 | 7.3 |
| 24 MiB | 6144 | 177.229 | 177.470 | 180.272 | 185.589 | +7.265 | +4.72 | 9/10 | 1.000 | 1.000 | 0.970 | 7.3 |
| 32 MiB | 8192 | 180.613 | 180.776 | 182.721 | 188.659 | +7.289 | +4.46 | 9/10 | 1.000 | 1.000 | 0.980 | 7.3 |
| 48 MiB | 12288 | 182.662 | 182.444 | 183.849 | 189.558 | +6.573 | +3.78 | 9/10 | 1.000 | 1.000 | 0.993 | 6.6 |
| 64 MiB | 16384 | 185.233 | 185.045 | 185.428 | 191.730 | +6.494 | +3.51 | 8/10 | 1.000 | 1.000 | 0.997 | 6.5 |

Sequential counterpart (stride 16, medians): 64 MiB kvmoff 2.317, nvhe 2.318, vhe 2.312, pkvm 2.317; pkvm minus mean of three at 12 / 16 / 24 / 32 / 48 / 64 MiB = +0.000 / -0.003 / -0.003 / -0.002 / -0.001 / +0.001 ns (N80: walks per load = stride/4096 = 0.0039).

### T9. L1-level check of the set-overflow model (random test; L1 colour = VA bits 13:12, 4 colours, 4 ways; 40 runs over 4 configs)

| pages (size) | predicted P(no colour holds more than 4 pages) | predicted mean miss fraction | measured fraction of runs at L1 latency (< 2.24 ns) | measured median / mean / max (ns) | sequential stride 16, same size (min..max, 40 runs) |
|---|---|---|---|---|---|
| 4 (16 KiB) | 1.000 | 0.000 | 37/40 = 0.925 | 2.223 / 2.268 / 2.820 | 2.223..2.224 |
| 6 (23 KiB) | 0.981 | 0.016 | 39/40 = 0.975 | 2.224 / 2.333 / 6.618 | 2.223..2.224 |
| 8 (31 KiB) | 0.890 | 0.071 | 31/40 = 0.775 | 2.224 / 2.686 / 6.339 | 2.223..2.224 |
| 12 (47 KiB) | 0.402 | 0.287 | 12/40 = 0.300 | 3.998 / 3.649 / 5.065 | 2.224..2.224 |
| 16 (62.5 KiB) | 0.014 | 0.539 | 1/40 = 0.025 | 4.126 / 4.371 / 5.846 | 2.224..2.224 |
| 24 (94 KiB) | 0.000 | 0.863 | 0/40 | 6.078 / 6.086 / 6.791 | 2.287..2.321 |

### T10. The two states of the random test (medians, ns per load)

| size | host nVHE, clean boot (Fig. 7 data) | host nVHE, 'noisy' boot | change | guests nVHE VM / VHE VM / NP VM | guest pVM | pVM vs nVHE VM, mean-based (Fig. 8 statistic) | N80 host, 4K pages | N80 host, 2 MiB pages |
|---|---|---|---|---|---|---|---|---|
| 1 MiB | 19.480 | 19.045 | -2.2% | 19.70 / 19.59 / 19.58 | 19.73 | +0.5% | 18.9 | - |
| 2 MiB | 20.752 | 21.100 | +1.7% | 23.96 / 23.69 / 23.76 | 22.39 | -5.5% | 21.6 | - |
| 3 MiB | 36.633 | 26.413 | -27.9% | 39.44 / 39.39 / 39.44 | 29.00 | -26.4% | 29.0 | - |
| 4 MiB | 47.688 | 30.800 | -35.4% | 52.30 / 51.84 / 52.63 | 35.97 | -31.2% | 37.1 | - |
| 6 MiB | 67.350 | 48.614 | -27.8% | 81.13 / 78.88 / 80.68 | 55.34 | -31.7% | 65.6 | - |
| 8 MiB | 112.601 | 83.900 | -25.5% | 126.83 / 124.97 / 126.53 | 97.86 | -22.5% | 103.4 | 82.5-84.2 (walks 0.000) |
| 12 MiB | 154.810 | 121.820 | -21.3% | 165.03 / 164.41 / 164.76 | 129.49 | -20.0% | 136.0 | - |
| 16 MiB | 168.556 | 134.226 | -20.4% | 176.73 / 176.90 / 177.05 | 141.20 | -18.7% | 146.8 | - |
| 64 MiB | 185.045 | 150.123 | -18.9% | 192.00 / 192.95 / 192.35 | 152.91 | -20.2% | 155.7 | 137.5-138.1 (walks 0.09-0.12) |

Sequential stride 256 in the same two host boots: 3 MiB 5.315 -> 4.919, 4 MiB 5.483 -> 5.072, 8 MiB 11.41 (bimodal, RSD 10.6%) -> 10.32 (RSD 1.8%, no slow draws), 16 MiB 10.69 -> 11.47, 64 MiB 10.24 -> 11.11. Fast outliers (more than 5% below the upper-half median) in the clean boots, random test: 1 MiB to 8 MiB 0 in every mode; 12 / 16 / 24 / 32 / 48 / 64 MiB: kvmoff 1/3/2/4/3/3, nvhe 0/0/0/1/3/3, vhe 0/1/1/0/1/3, pkvm 0/0/1/1/0/2 (each out of 10).

### T11. Significance tests (pkvm vs baseline, 10 vs 10 iterations; exact permutation over C(20,10) splits; bootstrap 20000 resamples)

| row | baseline | delta of means % | bootstrap 95% CI (mean) % | Welch t | p (t) | p (permutation, mean) | delta of medians % | bootstrap 95% CI (median) % | p (permutation, median) |
|---|---|---|---|---|---|---|---|---|---|
| LLC Bnd | kvmoff | +3.55 | -4.06..+11.34 | +0.86 | 0.402 | 0.400 | +12.09 | -12.30..+20.00 | 0.490 |
| LLC Bnd | nvhe | +2.87 | -5.27..+11.82 | +0.64 | 0.532 | 0.482 | +6.25 | -13.78..+23.14 | 0.671 |
| LLC Bnd | vhe | -3.02 | -9.45..+3.68 | -0.85 | 0.410 | 0.403 | -2.60 | -15.28..+7.83 | 0.982 |
| Main Mem | kvmoff | +0.29 | -1.45..+2.10 | +0.30 | 0.770 | 0.768 | -0.12 | -2.65..+3.12 | 0.995 |
| Main Mem | nvhe | +1.06 | -0.62..+2.77 | +1.16 | 0.261 | 0.257 | +1.01 | -1.95..+3.89 | 0.515 |
| Main Mem | vhe | -3.46 | -5.76..-1.18 | -2.73 | 0.017 | 0.013 | -4.05 | -7.02..-0.12 | 0.007 |
| Rand Mem (64 MiB) | kvmoff | +3.25 | -0.39..+6.55 | +1.76 | 0.098 | 0.093 | +3.51 | -0.03..+8.64 | 0.031 |
| Rand Mem (64 MiB) | nvhe | +3.88 | -0.03..+7.69 | +1.91 | 0.072 | 0.073 | +3.61 | +0.30..+9.62 | 0.045 |
| Rand Mem (64 MiB) | vhe | +3.82 | -0.22..+8.00 | +1.80 | 0.089 | 0.087 | +3.40 | -0.12..+8.68 | 0.033 |
| Rand 8 MiB | kvmoff | +6.26 | +5.87..+6.67 | +29.7 | <0.0001 | <0.0001 | +6.26 | +5.57..+6.89 | 0.0008 |
| Rand 4 MiB | kvmoff | +3.37 | +2.78..+3.97 | +10.7 | <0.0001 | <0.0001 | +3.63 | +2.57..+4.29 | 0.0008 |
| Prot Fault | kvmoff | -1.08 | -3.47..+1.05 | -0.87 | 0.395 | 0.404 | +0.22 | -3.02..+1.84 | 0.927 |
| Page Fault | kvmoff | +1.99 | +1.33..+2.59 | +5.94 | <0.0001 | 0.0001 | +2.12 | +1.37..+2.71 | 0.0008 |

Noise floor among the three modes without host stage 2: LLC Bnd vhe vs kvmoff +6.77% (p 0.082); Main Mem vhe vs kvmoff +3.88% (p 0.011), vhe vs nvhe +4.68% (p 0.002); Rand Mem nvhe / vhe vs kvmoff -0.61% / -0.55% (p 0.74 / 0.76); Rand 8 MiB within 0.3%. LLC Bnd two-point mixture (10.33 / 12.44 ns, P(slow) 0.47): SD of one draw 9.3%, SE of the difference of two 10-run means 4.15%, observed +3.55% = 0.85 sigma, 80%-power detectable difference 11.6%, 108 iterations per mode needed for a 3.55% shift; under the null P(|delta| >= 3.55%) = 0.50.

### T12. N80: same physical frames, different virtual order (sequential; medians; colour set identical within a row)

| size | stride | physically sorted ns (VA-PA adjacency) | reversed ns | shuffled ns | shuffled vs sorted | l3d_cache_refill per load sorted / shuffled | colour-overflow fraction |
|---|---|---|---|---|---|---|---|
| 4 MiB | 256 | 4.479 (0.71) | 4.471 | 4.468 | -0.3% | 0.481 / 0.481 | 0.034 |
| 6 MiB | 256 | 7.124 (0.69) | 7.069 | 7.349 | +3.2% | 0.684 / 0.686 | 0.176 |
| 8 MiB | 128 | 8.497 (0.69) | 8.503 | 9.200 | +8.3% | 0.797 / 0.795 | 0.539 |
| 8 MiB | 256 | 8.844 (0.68) | 8.819 | 9.502 | +7.4% | 0.777 / 0.783 | 0.548 |
| 8 MiB | 256 (first trial) | 7.968-7.995 (0.99) | 8.180 | 9.611-9.624 | +20.5% | 0.757 / 0.773 | 0.458 |
| 8 MiB | 512 | 9.057 (0.68) | 9.059 | 9.910 | +9.4% | 0.775 / 0.783 | 0.557 |
| 8 MiB | 1024 | 10.196 (0.68) | 10.184 | 10.843 | +6.3% | 0.795 / 0.800 | 0.530 |
| 12 MiB | 256 | 9.350 (0.68) | 9.308 | 10.373 | +10.9% | 0.864 / 0.870 | 0.946 |
| 16 MiB | 256 | 9.474 (0.67) | 9.432 | 10.493 | +10.8% | 0.902 / 0.904 | 1.000 |
| 32 MiB | 256 | 9.620 (0.59) | 9.559 | 10.569 | +9.9% | 0.958 / 0.959 | 1.000 |

N80 fresh-process runs (30 per size, stride 256): Spearman(ns, adjacency) = -0.87 / -0.86 / -0.99 / -0.93 / -0.92 at 6 / 8 / 12 / 16 / 64 MiB; Spearman(ns, colour overflow) = -0.13 / +0.51 / -0.44 / -0.43; partial (colour given adjacency) = -0.15 / +0.21 / +0.17 / +0.17; partial (adjacency given colour) = -0.87 / -0.82 / -0.99 / -0.91.

### T13. Page-table footprint of the two tests (leaf level, 4 KiB pages; 8 PTEs per 64 B line; 512 PTEs per leaf table)

| size | pages | sequential: PTE lines / leaf tables | random: PTE lines (mean of 20 permutations) / leaf tables | analytic 2048*(1-(1-n/16384)^8) |
|---|---|---|---|---|
| 1 MiB | 256 | 32 / 1 | 242.2 / 31.9 | 242.4 |
| 2 MiB | 512 | 64 / 1 | 457.0 / 32.0 | 459.4 |
| 4 MiB | 1024 | 128 / 2 | 823.3 / 32.0 | 825.9 |
| 6 MiB | 1536 | 192 / 3 | 1108.7 / 32.0 | 1116.2 |
| 8 MiB | 2048 | 256 / 4 | 1332.0 / 32.0 | 1344.3 |
| 12 MiB | 3072 | 384 / 6 | 1649.5 / 32.0 | 1659.0 |
| 16 MiB | 4096 | 512 / 8 | 1835.8 / 32.0 | 1843.0 |
| 32 MiB | 8192 | 1024 / 16 | 2038.5 / 32.0 | 2040.0 |
| 64 MiB | 16384 | 2048 / 32 | 2048.0 / 32.0 | 2048.0 |

### T14. Environment controls for the host runs

| variable | applied how | evidence that it held during the runs | status |
|---|---|---|---|
| CPU affinity | taskset -c 0 around scripts/lmbench (bench.sh:68); children inherit (LMBENCH_SCHED=DEFAULT) | summary 'cores=0'; file names cpu0 | controlled |
| CPU frequency | prepare-host.sh:19-32, performance governor, min = max = 1900000 kHz | summaries record cpu_max_freqs 1900000 x 8; measured cycle is 0.5556 ns = 1.80 GHz | controlled (nominal value off by 5%) |
| deep idle | prepare-host.sh:34-39 | not recorded | procedure only |
| THP | prepare-host.sh:41-44 writes never to the global knob; verify-clean-env.sh:49-53 checks it | not recorded per run; kernel default is always; per-size mTHP knobs untouched | procedure only |
| ASLR | prepare-host.sh:46-49; verify-clean-env.sh:54-57 | not recorded | procedure only |
| background services | apply-masks.sh (90 system + 12 user units masked, pkill, multi-user target) | not recorded; one earlier boot kept as 'noisy' | procedure only |
| LSM / audit | cmdline lsm= audit=0 | cmdline in summaries | controlled |
| KVM mode | cmdline kvm-arm.mode= | cmdline in summaries | the variable under test; one boot per mode |
| physical page placement, colour, VA-PA adjacency | nothing | nothing (no pagemap) | uncontrolled, unrecorded |
| other cores / shared L3 | nothing (no isolcpus, nohz_full, irqaffinity) | cmdline in summaries | uncontrolled |
| page cache / allocator state | deliberately not flushed (docs/EXPERIMENT.md:64) | - | uncontrolled |
| interconnect (NoC) frequency | nothing; kernel default governor simple_ondemand, 100 ms polling | nothing | uncontrolled, unrecorded |
| kernel .config (CONFIG_X1_RMS etc.) | - | not recorded (docs/EXPERIMENT.md:91-93 TODO) | unrecorded |
