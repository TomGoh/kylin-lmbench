# 核查报告：audit:probe-code

## Summary

Scope. Everything audited here is class (D): programs run on the N80 host Linux booted with kvm-arm.mode=protected, no VM. None of it ran inside an x-kernel guest and none of it ran on the N90, so it supports Figure 7 (N90 host with pKVM on) only by inference and says nothing about Figure 8 (inside the x-kernel VM). The only place where classes are combined is the last two columns of Exp A in device-tables.md, which divide N90 host increments (H) by N80 refill rates (D). No guest data (G) is mixed in.

Verdict. I found no coding bug in probe.c, probe2.c, layout.c or frames.c, and every number in device-tables.md reproduces from the raw logs. No defect invalidates a measured result. Four interpretations lose support:
- the named mechanism for the layout effect ("prefetch cannot cross the 4 KiB boundary");
- the per-walk cost of 3-4 ns at 2-4 MB;
- "physical placement does not matter for random access";
- any use of event 0x2a as a count of memory fetches.

1. Chain construction. I compiled lmbench's own lib_mem.c and lib_timing.c and the unmodified probe.c and probe2.c into a harness that logs the first write to each page and dumps the finished chain. For rand 0.5, 2 and 8 MB (stride 16, maxlen 64 MB) and seq 8 MB/256 and 4 MB/128:
- the normalised chains are byte-identical and form one cycle of npages x (4096/stride) hops;
- the used pages are spread over the whole 64 MB buffer in both;
- first-touch order equals chain order in both (ascending for seq).

Differences from lat_mem_rd, none of which changes the page-walk rate:
- Allocation: mmap + MADV_NOHUGEPAGE instead of malloc under THP=never. lmbench's buffer starts one page into the mapping and malloc touches the header page first.
- Permutation: an unbiased Fisher-Yates shuffle with fixed seeds instead of lmbench's biased, pid-seeded swap. Simulated TLB miss rates differ by at most 0.005.
- Initialisation: the probe builds the chain once; lmbench rewrites it before every timed interval (lib_timing.c:757-759).
- Timing: clock_gettime and a one-load loop instead of gettimeofday and 100 unrolled loads.
- Reported value: the tables use the median of 11 repetitions of about 120 ms; lmbench reports the minimum of 11 intervals of at least 100 ms. The two are 0.1-0.5% apart in undisturbed runs.
- ASLR on (N80) against off (N90), and a different sequence of sizes before each point.

2. PMU. 0x2d = L2D_TLB_REFILL, 0x05 = L1D_TLB_REFILL, 0x2a = L3D_CACHE_REFILL, 0x17 = L2D_CACHE_REFILL, 0x13 = MEM_ACCESS (include/linux/perf/arm_pmuv3.h:20,34,38,57,60). tools/perf/pmu-events/arch/arm64/common-and-microarch.json describes them as "Attributable Level 2 data TLB refill", "Attributable Level 1 data TLB refill", "Attributable Level 3 data cache refill", "Level 2 data refill" and "Data memory access". The walk event proper is 0x34 DTLB_WALK, which this core does not advertise.
- 0x2d can be read as "accesses whose translation missed the last TLB level", one count per access. It does not count table reads, says nothing about walk cost, and on this machine is not determined by the page sequence alone (see threats).
- exclude_kernel does not hide walks for user accesses: filtering is by exception level (drivers/perf/arm_pmuv3.c:1017-1036), and a hardware walk for an EL0 load happens at EL0.
- PERF_TYPE_RAW is not routed to the arm PMU by type; perf_init_event falls through to the PMU list and drivers/perf/arm_pmu.c:193 accepts it. On this machine it does arrive: one CPU PMU covers cpus 0-7, and the Phytium uncore PMU drivers reject foreign types. The values confirm it: MEM_ACCESS is 1.000003-1.000106 per hop, cycles x 0.527 ns equals ns per hop (1.896-1.900 GHz), and refills equal stride/4096 in Exp D.
- The enabled/running scaling is correct and was never exercised: none of the 315 probe/probe2 rows shows multiplexing.

3. pagemap and colours. PFN in bits 0-54, present in bit 63, offset (va/4096)*8: correct. 8192 sets x 64 B / 4096 B gives 128 colours and 16 ways gives 16 pages per colour, also for stride 256: correct. contig_frac counts ascending adjacency only (first defect).

4. layout.c. The bookkeeping is correct. Run unprivileged against a fake pagemap that stores each page's "PFN" inside the page, the unmodified program presented the same 1024 pages in five layouts, none dropped or duplicated, in the requested order. Layouts do differ in the number of VMAs (1384 against 1683 for 1024 pages in my test) and in the order in which the 2-17 leaf page tables are allocated. The reversed layout shares both with shuffled and is as fast as sorted, so neither explains the latency difference. The pool remainder stays mapped but untouched. The log fields show the kernel moved pages in 3 of 27 invocations (second defect).

5. frames.c. The policies select what the header says (verified with the fake pagemap). region:N is the N-th most populated 1 GiB-aligned PFN window among the pool's frames, then the lowest PFNs inside it; N is a population rank, not an address. In the logs region:0/1/2 were windows 0x84, 0x83 and 0x85 in all three repetitions.

6. Scripts. Order is fixed with no randomisation. In Exp A seed is confounded with allocator state. Successive processes reuse the same frames, so runs are serially dependent. Laps 26-30 of Exp B were disturbed. The desktop session and THP=always were left running.

Local checks ran unprivileged on an aarch64 workstation (uname -m; the task text says x86). ASan/UBSan runs of all four programs were clean.

## Defects

- **weakens** | experiments/memlat-probe/probe.c:230-233 (contig_frac); used by analyze-device-logs.py:151-166 for Exp B and by the not-yet-run run5-mode-compare.sh / analyze-mode-compare.py:241: contig_frac counts only ascending adjacency (pfn[k+1] == pfn[k]+1). Descending adjacency is not measured by probe.c (rcontig_frac exists only in probe2.c and layout.c), and in rand mode the field prints 0.0000 without being computed. The logs show descending adjacency is common and matters. In Exp D all 15 fresh 64 MB processes received the same frame range (pfn_min 0x20ad820, pfn_max 0x2368f36), and contig_frac alternated 0.380, 0.0012, 0.379, 0.0013, 0.376, 0.0012, 0.375, 0.0012, 0.374 with no latency difference (stride 256: 9.93 against 10.05 ns). In Exp T the first default-order 64 MB run has contig 0.009 but rcontig 0.293 and takes 10.14 ns against 10.48-10.69 ns for the other 14. Exp L shows descending order is as fast as ascending. Effect: Exp B's correlations (worklog 6.4, device-tables Exp B) are computed against an incomplete measure of adjacency. The sign of the result stands, and Exp L tests it causally. The numbers are not usable: the fitted line ns = 9.57 - 4.32 x contiguity predicts 5.25 ns at full contiguity, while 8.0 ns was measured at 0.988 (hand-run trial) and 8.37 ns at 0.89 (lap 14). The count of distinct 2 MiB regions predicts latency at least as well (rho +0.95, +0.97, +0.94, +0.82 at 8, 12, 16, 64 MB) and absorbs contig_frac in partial rank correlation (-0.02 at 8 MB).
- **cosmetic** | experiments/memlat-probe/layout.c:227-258 (remap and verification); worklog 6.5 ('页颜色和内存条位置因此完全相同'); device-tables Exp L: Nothing stops the kernel from migrating the selected pages between layouts (the N80 ran THP=always with a desktop session), and the program never compares the PFNs it re-reads against the list it selected. The log fields show it happened in 3 of 27 invocations. rep=2 size=6: color_max 21 -> 22, thrash_pages_frac 0.1322 -> 0.1367, sorted contiguity 0.6945 -> 0.5453 with reverse contiguity 0.1368. rep=1 size=16: color_max 47 -> 46, contiguity 0.7214 -> 0.7189. rep=2 size=32: contiguity 0.6015 -> 0.5816, reverse 0.0143. probe.c has the same exposure, since it reads PFNs once before the measurement. Effect: 'The same frames in every layout' is false for those three invocations, so the wording needs correcting. The numbers do not: removing the three changes the Exp L table by at most 0.6 percentage points (6 MB: +3.9% -> +4.5%; all other rows unchanged to 0.1).
- **weakens** | docs/memlat/memlat-investigation-worklog.zh-CN.md section 6.5, last paragraph, and hypothesis H-c ('影响预取跨页'); derived/device-tables.md Exp L: The stated mechanism, that the difference is whether the hardware prefetcher can continue across the 4 KiB boundary, is not what the experiment isolates, and three of its own results argue against the simple form of it. (1) Physically descending order is as fast as ascending (-1.1% to +0.1% on group means), which an ascending physical stream continuing into the next frame cannot produce. (2) The shuffled penalty per page crossing falls from 22.4 ns at stride 128 to 11.2, 7.1 and 2.5 ns at strides 256, 512 and 1024, so it is 0.6-0.9 ns per access however often a boundary is crossed. (3) At stride 256 the penalty is 11-16 ns per crossing, about one eighth of one unprefetched memory access (about 135 ns in the 64 MB random runs), so prefetching continues across page boundaries in every layout. Effect: What stands: with the same frames, a virtual order in which consecutive pages are physically adjacent in either direction is 8-11% faster from 8 MB up (20% at 0.99 contiguity), 3.9% at 6 MB, and no different at 4 MB. What does not stand is the named mechanism; it should be withdrawn or marked as a hypothesis. Because only protected mode was measured, a contribution from stage-2 translation or from the memory system cannot be separated either.
- **weakens** | PMU event 0x2a as used in experiments/memlat-probe/README.zh-CN.md (event table), worklog 6.4 and 6.5, and the 'L3 refills' columns of device-tables.md: L3D_CACHE_REFILL is read as the number of fetches from memory. The logs rule that reading out. In the random chase at 3 and 4 MB it counts 0.41 and 0.62 per access while latency is only 29 and 37 ns. The latency above the 20 ns L3-hit level per counted refill is 23-27 ns there, against 134-137 ns from 16 MB up. In the sequential chase it follows 1 - 2 MB/size (0.483, 0.678, 0.774, 0.861, 0.901, 0.986 for 4 to 64 MB) with no feature at 8 MB, where latency has its knee. Effect: 'L3 refills are equal across layouts' and 'L3 refills barely vary between runs (median 0.774 at 8 MB)' are statements about this counter, not about memory fetches. They cannot carry the argument against the page-colour hypothesis or for the prefetch mechanism. The colour hypothesis is still contradicted by the partial correlations and by Exp L (same frames, same colours, different latency).
- **weakens** | experiments/memlat-probe/run_all.sh:12-17 (Exp A: seed is the outer loop, sizes ascend, three fixed seeds): Seed is confounded with time and with the allocator's state. Seed 101 ran on compact memory (3-25 distinct 2 MiB regions up to 4 MB); seeds 202 and 303 ran on scattered memory (71-386). L2 TLB refills per access differ accordingly: at 4 MB 0.34 / 0.46-0.50 / 0.51-0.53, at 3 MB 0.135-0.139 / 0.165-0.194 / 0.238-0.270. For the same seed at 6 MB the rate is 0.769 with 249 regions and 0.883 with 564. Effect: The walk-rate curve between 2 and 6 MB (worklog 6.1) is uncertain by roughly 25-40%. 'Increment / walk rate' becomes 1.8-5.9 ns at 2 MB, 2.6-5.3 at 3 MB and 3.2-5.1 at 4 MB, not 3.3, 3.7, 3.9, so 'each walk costs 3-4 ns more at small working sets' is not established. From 16 MB up the refill rate is 1.000 in every run and the 6.5-8.1 ns figures are unaffected as arithmetic.
- **weakens** | experiments/memlat-probe/frames.c:272-275 and 291-314: frames.c lays the selected frames out in ascending PFN order and then visits the pages in a random permutation, so consecutive hops go to unrelated frames. lmbench and probe.c first-touch pages in chain order, so the i-th hop goes to the i-th allocated frame. frames.c therefore changes the frame set but does not reproduce lmbench's physical visiting order. It also controls data frames only. The 32 leaf page-table pages of the measured mapping are whatever the allocator returns and are not recorded, yet the differences it measures are in page-walk-related L2 refills. Effect: Exp F (worklog 6.7) answers 'does the frame set matter when frames are visited in random physical order'. It does not answer 'does lmbench -t change with the allocation', so it cannot by itself settle hypothesis H-h.
- **weakens** | experiments/memlat-probe/frames.c:230-232 ('scatter' policy); frames.c prints no colour statistics: 'scatter' takes every 16th frame of the PFN-sorted pool. 16 divides both the L2 colour period (16 pages) and the L3 colour period (128 pages), so inside any contiguous run the chosen frames share one L2 colour and 8 of 128 L3 colours. Because frames.c logs no colour statistics, the logs cannot show whether this happened. Effect: The scatter row of Exp F (+3.2% against compact, 1.41 against 1.16 L2 refills per access) cannot be attributed to physical spread alone.
- **weakens** | worklog 6.7 and hypothesis H-h ('N80 上未复现'); device-tables Exp F: '155-161 ns, less than 4% apart' hides a reproducible two-level result. compact, low, high, region:0 and region:2 give 154.5-157.2 ns with 1.15-1.21 L2 refills per access. scatter and region:1 give 160.2-161.1 ns with 1.33-1.42. Each policy has three runs, the two groups do not overlap, and latency correlates with L2 refills at r = +0.955 over the 21 runs. region:1 is as compact as region:0 (contiguity 0.993, 33 regions of 2 MiB) and 5.7 ns slower. Effect: Physical placement does change random-access latency on the N80 in protected mode, by 4.8 ns on average (3.1%), through page-walk-related cache refills. That is the size of the N90 pkvm increment it is compared with (6.5 ns at 64 MB, the paper's 3.25%). 'Not reproduced' holds only for an effect of 20%. The cause of the split is not identified.
- **cosmetic** | experiments/memlat-probe/run_all.sh:18-39 (Exp C before D and B; Exp B laps), results/memlat-n80-20260930/meta.log: Exp B runs are neither independent nor all clean. Successive processes get the same frames back, so the 30 laps contain a handful of allocator states. Laps 26-30 were disturbed: at 4 MB lap 30 reads 4.62 / 5.31 / 19.18 ns (min/median/max), the 8 MB lap 30 has an L3 count of 0.924 against a median of 0.774, and the load average ended at 2.02. Exp C, whose MADV_HUGEPAGE faults can trigger compaction, runs between A and B. Effect: The quoted ranges are inflated: 8 MB is 8.31-10.24 ns with all laps and 8.31-9.54 without laps 26-30. The correlations get stronger without those laps (-0.90, -0.91, -0.99, -0.91, -0.90 at 6, 8, 12, 16, 64 MB), so the reported values are conservative. n = 30 still overstates the evidence; Exp L is the causal test.
- **cosmetic** | experiments/memlat-probe/probe.c:55-74 (comment 'as lmbench permutation()') and README.zh-CN.md ('逐行照搬'); choice of ns_med in analyze-device-logs.py: Two documented equivalences are not exact. The probe's permutation() is a Fisher-Yates shuffle with fixed seeds. lmbench's (src/lib_timing.c:1631-1668) swaps every position with a random position of the whole array and is seeded from the pid; it is biased, with the first n pages having a mean index of 0.45-0.47 of the buffer instead of 0.50. The tables also use the median of 11 repetitions where lmbench reports the minimum (src/lat_mem_rd.c:148). Effect: None on the page-walk rate: under eight TLB models and 400 seeds the two permutations differ by at most 0.005 in miss rate. Median against minimum is 0.1-0.5% in undisturbed runs.
- **cosmetic** | experiments/memlat-probe/layout.c:192-196 and 277-308; frames.c:327-363: layout.c and frames.c scale counts by time_enabled/time_running but never print whether multiplexing occurred. layout.c reuses the same event descriptors for all layouts, and PERF_EVENT_IOC_RESET does not reset the two times, so a scaling factor would be cumulative across layouts. Effect: No effect on these logs: none of the 315 probe/probe2 rows that use the same six-event sets carries the (mux) marker.

## Discrepancies

- Reproduced without change from the raw logs: Exp A means (refills 0.0000, 0.0057, 0.0058, 0.0457, 0.190, 0.447, 0.838, 0.967, 0.998, then 1.000), Exp D (refills per page crossing 1.000, 0.993, 1.000, 1.000, 0.983), Exp C, all Exp B correlations and the 8 MB fit (9.57 - 4.32 x contiguity, r = -0.852), the Exp L table, the Exp F table, and the median 8 MB L3 count of 0.774. The N90 host increments used in Exp A (+0.15, +0.71, +1.73, +5.24, +7.05, +7.03, +7.73 ... +6.50 ns) also reproduce from results/n90-day3-host.
- Claim 'identical set of physical frames, same colour statistics in every layout of a run' (device claim 5, worklog 6.5): false for 3 of 27 invocations. Colour statistics differ in two of them, and contiguity differs in all three.
- Claim 'contig_frac below 0.01 for all three first-touch orders' (device claim 7): one default-order 8 MB run has 0.0132. The statement also omits that reverse contiguity was 0.293 (64 MB) and 0.071 (8 MB) in the first default-order pair. The 8 MB latencies are 9.52-9.66 ns as claimed.
- Worklog 6.6 says physical contiguity was near zero whatever the touch order. That is true for forward contiguity only: the first default-order 64 MB run was 29% reverse-contiguous and 3-5% faster (10.14 ns against 10.48-10.69 ns).
- Worklog 6.5 attributes the layout effect to prefetch crossing the 4 KiB boundary. The same log shows descending order equal to ascending and a penalty per page crossing that shrinks from 22.4 ns (stride 128) to 2.5 ns (stride 1024).
- Exp B slope against Exp L. Exp B implies -4.3 ns per unit of forward contiguity. Exp L measures -0.7 ns at 0.70 adjacency and -1.6 ns at 0.99. The two agree only if forward contiguity in Exp B stands in for three to four times as much total adjacency.
- Worklog 6.4 quotes the 8 MB range as 8.31-10.24 ns. The 10.24 ns value is lap 30, a disturbed run (L3 count 0.924, ns_min 9.74). Laps 1-25 span 8.31-9.54 ns.
- Worklog 6.7 and device claim 6 say 'less than 4%'. Numerically correct (largest difference between policy means 3.7%), but the 21 runs fall into two non-overlapping levels 4.8 ns apart.
- results/memlat-n80-20260930/README.md says the background load was 0.3-1.2. meta.log records 2.02 at the end of run_all.sh.
- The Exp A row for 0.5 MB (10.99 ns) averages two regimes: 8.0 and 9.5 ns for seed 101 on compact memory, 11.8-12.4 ns for the other two seeds. 0.5 MB of data is exactly the L2 size, so this row reflects L2 page colouring.
- In Exp L at 8 MB, L2 TLB refills per page crossing fall from 0.95 at stride 128 to 0.82, 0.76 and 0.69 at strides 256, 512 and 1024, for the same 2048 pages in the same order. The count is therefore not fixed by the page sequence; the device tables list these rates without comment.
- README.zh-CN.md says the chain construction is copied line by line from lib_mem.c. The chain is identical, but permutation() is a different algorithm from lmbench's.
- The task text calls the local workstation x86; uname -m reports aarch64. All local runs were unprivileged functional checks, with no PFN or PMU data of my own.

## Threats to validity

- Only protected mode was measured on the N80. Every statement about a difference between KVM modes combines N80 protected-mode counters with N90 times from four separate boots; walk rate and walk cost in the other modes were never counted.
- The N80 is not the paper's machine or software. It is an N80F3 with 16 GB (2 x 8 GB at 6400 MT/s) against the N90's 32 GB. It ran kernel 6.6.0-79 #93 (September) against 6.6.0-73 #76 (May), and arch/arm64/kvm differs between those tags, including the hypervisor runtime. The N80 had THP=always, ASLR on, LSM and audit on and a desktop session; the N90 had THP=never, ASLR off and services masked. Absolute latencies differ (64 MB random 155 ns against 185 ns).
- Interconnect state. The N80's NoC was at 1800 MHz under the 'performance' governor for all runs. This rests on more than the sysfs read at 17:24: trans_stat accounts for only 16.5 s out of 62 min of uptime, and in this kernel (drivers/devfreq/devfreq.c) accounting stops when monitoring stops while any later frequency change would add the elapsed time, so no change occurred after the first seconds. The N80 data were therefore taken in a platform state that the N90 June runs probably did not have, and they cannot test the NoC hypothesis H-i.
- CPU clock: cpu0 ran at 1.896-1.900 GHz in every run (wall time per hop divided by user-mode cycles per hop), with at most 0.2% of time outside user mode. This threat is closed for the N80.
- PMU semantics on the FTC862 are implementation defined and no vendor event description exists in the tree (tools/perf has no Phytium file). 0x2d counts refills per access, not table reads or walk cost, and it is unknown whether prefetch-initiated walks are counted. So 'one refill per page crossing' in Exp D shows a walk per page, not that the demand access waited for it.
- L2 TLB refills are not a function of the virtual page sequence alone on this machine. In Exp L the shuffled layout has more refills than the sorted one in 20 of 24 invocations at 6 MB and above (sign test p = 0.0015). In Exp B at 12 and 16 MB refills per crossing range 0.62-0.97 and 0.79-0.99 and track contiguity (rho -0.92, -0.90). In Exp L they fall with stride at 8 MB. The assumption that N80 protected-mode walk rates between 2 and 12 MB equal those of all four N90 configurations is untested.
- N90 side: one boot per mode. On the N80 successive processes received the same frames, so the ten iterations per mode are probably not independent with respect to physical placement, and placement alone moved the 64 MB random latency by 4.8 ns in protected mode. The size of the protected-mode increment may depend on where the buffer lands. The three baseline boots agree within 0.3 ns up to 12 MB, which argues that placement matters little without stage 2.
- Exp L ran on fragmented memory (runs of about 3 adjacent pages, contiguity 0.62-0.78) except for one hand-run trial at 0.99. The N80 shows a continuous 8.3-9.5 ns at 8 MB, not the two discrete levels of the N90 (about 10.2 and 12.4 ns). Physical adjacency is a candidate cause of the N90 bimodality, not a demonstrated one.
- Environment noise on the N80: a desktop session with a load of 0.3-2.0, the L3 shared with seven other cores, and THP=always with 3.9 GB of anonymous huge pages, so background compaction is active and page migration was observed.
- Small samples and fixed order: three seeds in Exp A, three repetitions in Exp L and Exp F, five in Exp T, no randomisation of run order anywhere.
- Exp C obtained huge pages only partly, and huge pages also change the physical layout. The 21 ns (8 MB) and 17 ns (64 MB) saved per access cannot be attributed to walks alone.
- The proposed run5-mode-compare.sh, which would remove the single-mode limitation, calls ./probe and keeps seed as the outer loop. It would inherit the forward-only contiguity metric and the seed/allocator confound unless changed before it is run.

## Recomputed tables

All tables are class (D) data: N80 host Linux, kvm-arm.mode=protected, no VM, recomputed from results/memlat-n80-20260930/exp*.log. The N90 increments in the last column of the first table are class (H) and were re-derived from results/n90-day3-host.

### Exp A (random chase, stride 16): L2D_TLB_REFILL per access over the 6 runs (3 seeds x 2 event sets)

| size | pages | ns_med mean | refills mean | min | max | seed 101 | seed 202 | seed 303 | distinct 2 MiB regions, seed 101 / 202 / 303 | L3D_CACHE_REFILL per access | (ns - 20) per L3 refill | N90 increment / refill rate: at mean [at max .. at min] (ns) |
|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|---|
| 0.5 MB | 128 | 10.99 | 0.0000 | 0.0000 | 0.0000 | 0.000/0.000 | 0.000/0.000 | 0.000/0.000 | 3+3 / 79+71 / 89+86 | 0.000 | | |
| 1 MB | 256 | 18.89 | 0.0057 | 0.0000 | 0.0195 | 0.000/0.000 | 0.000/0.000 | 0.015/0.020 | 3+3 / 134+119 / 164+165 | 0.001 | | |
| 1.5 MB | 384 | 20.01 | 0.0058 | 0.0000 | 0.0130 | 0.008/0.007 | 0.000/0.000 | 0.013/0.006 | 5+5 / 178+174 / 209+212 | 0.003 | | |
| 2 MB | 512 | 21.34 | 0.0457 | 0.0256 | 0.0835 | 0.026/0.026 | 0.038/0.041 | 0.059/0.083 | 12+10 / 211+210 / 248+238 | 0.060 | 22 | 3.3 [1.8 .. 5.9] |
| 3 MB | 768 | 29.27 | 0.1900 | 0.1346 | 0.2698 | 0.139/0.135 | 0.165/0.194 | 0.238/0.270 | 13+14 / 287+287 / 319+320 | 0.407 | 23 | 3.7 [2.6 .. 5.3] |
| 4 MB | 1024 | 37.07 | 0.4469 | 0.3382 | 0.5327 | 0.343/0.338 | 0.500/0.456 | 0.512/0.533 | 20+25 / 326+326 / 386+382 | 0.624 | 27 | 3.9 [3.2 .. 5.1] |
| 6 MB | 1536 | 68.17 | 0.8384 | 0.7693 | 0.8825 | 0.769/0.882 | 0.820/0.824 | 0.859/0.876 | 249+564 / 404+406 / 473+477 | 0.789 | 61 | 6.2 [5.9 .. 6.8] |
| 8 MB | 2048 | 106.73 | 0.9671 | 0.9584 | 0.9780 | 0.966/0.978 | 0.961/0.958 | 0.963/0.975 | 644+651 / 493+491 / 569+570 | 0.879 | 99 | 7.3 [7.2 .. 7.4] |
| 12 MB | 3072 | 137.59 | 0.9982 | 0.9973 | 0.9990 | 0.998/0.998 | 0.998/0.998 | 0.997/0.999 | 718+718 / 667+691 / 742+777 | 0.930 | 127 | 7.0 |
| 16 MB | 4096 | 150.49 | 1.0000 | 0.9997 | 1.0000 | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | 742+773 / 858+858 / 964+966 | 0.974 | 134 | 7.7 |
| 24 MB | 6144 | 154.55 | 1.0000 | 1.0000 | 1.0000 | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | 841+840 / 924+925 / 1037+1038 | 0.980 | 137 | 8.1 |
| 32 MB | 8192 | 154.36 | 1.0000 | 1.0000 | 1.0001 | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | 850+849 / 964+963 / 1067+1068 | 0.979 | 137 | 7.9 |
| 48 MB | 12288 | 155.09 | 1.0000 | 0.9999 | 1.0001 | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | 907+903 / 973+975 / 1085+1262 | 0.994 | 136 | 6.9 |
| 64 MB | 16384 | 155.61 | 1.0001 | 1.0000 | 1.0003 | 1.000/1.000 | 1.000/1.000 | 1.000/1.000 | 915+911 / 989+991 / 1274+1275 | 0.997 | 136 | 6.5 |

### Exp D (sequential, 64 MB): refills per page crossing and forward contiguity of each run

| stride | ns_med (3 runs) | L2D_TLB_REFILL per access | per 4 KiB crossing | contig_frac of the 3 runs (forward only) |
|---:|---|---:|---:|---|
| 64 | 4.398 4.373 4.434 | 0.01562 | 1.000 | 0.3800 0.0012 0.2467 |
| 128 | 9.365 9.387 9.370 | 0.03103 | 0.993 | 0.0012 0.3745 0.1785 |
| 256 | 9.932 10.046 10.001 | 0.06250 | 1.000 | 0.3788 0.0012 0.2601 |
| 512 | 10.298 10.348 10.366 | 0.12500 | 1.000 | 0.0013 0.3743 0.2058 |
| 1024 | 11.906 11.917 12.061 | 0.24581 | 0.983 | 0.3762 0.1744 0.2554 |

### Exp B (sequential stride 256, 30 laps): rank correlations of ns_med

| size | rho(ns, contig) all laps | laps 1-25 | rho(ns, 2 MiB regions) all laps | laps 1-25 | rho(ns, lap) | partial rank r(ns, contig given regions) | partial rank r(ns, regions given contig) | TLB refills per crossing, laps 1-25 | rho(TLB refills, contig), laps 1-25 | L3 count per access, laps 1-25 | 1 - 2 MB/size |
|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 4 MB | +0.34 | +0.30 | +0.20 | +0.43 | +0.60 | +0.32 | +0.16 | 0.000-0.005 | +0.50 | 0.483 | 0.500 |
| 6 MB | -0.60 | -0.90 | +0.59 | +0.88 | +0.66 | -0.16 | +0.06 | 0.571-0.829 | +0.34 | 0.678 | 0.667 |
| 8 MB | -0.84 | -0.91 | +0.95 | +0.98 | +0.53 | -0.02 | +0.82 | 0.704-0.897 | -0.11 | 0.774 | 0.750 |
| 12 MB | -0.95 | -0.99 | +0.97 | +0.98 | +0.50 | -0.31 | +0.67 | 0.621-0.969 | -0.92 | 0.861 | 0.833 |
| 16 MB | -0.88 | -0.91 | +0.94 | +0.97 | +0.49 | -0.29 | +0.71 | 0.790-0.992 | -0.90 | 0.901 | 0.875 |
| 64 MB | -0.84 | -0.90 | +0.82 | +0.94 | +0.49 | -0.55 | +0.46 | 0.938-1.000 | -0.20 | 0.986 | 0.969 |

### Exp L (same frames, three virtual orders), all 27 invocations

| size | stride | sorted ns | reversed ns | shuffled ns | shuffled vs sorted | reversed vs sorted | penalty per access (ns) | per page crossing (ns) | L2 TLB refills per crossing sorted / reversed / shuffled | runs |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 4 MB | 256 | 4.50 | 4.48 | 4.48 | -0.4% | -0.5% | -0.02 | -0.3 | 0.000 / 0.000 / 0.000 | 6/3/6 |
| 6 MB | 256 | 7.19 | 7.15 | 7.47 | +3.9% | -0.5% | +0.28 | +4.5 | 0.707 / 0.727 / 0.784 | 6/3/6 |
| 8 MB | 128 | 8.52 | 8.49 | 9.22 | +8.2% | -0.3% | +0.70 | +22.4 | 0.954 / 0.958 / 0.960 | 3/3/3 |
| 8 MB | 256 | 8.86 | 8.76 | 9.56 | +7.9% | -1.1% | +0.70 | +11.2 | 0.819 / 0.804 / 0.854 | 6/3/6 |
| 8 MB | 512 | 9.04 | 9.05 | 9.93 | +9.8% | +0.1% | +0.89 | +7.1 | 0.755 / 0.758 / 0.787 | 3/3/3 |
| 8 MB | 1024 | 10.23 | 10.18 | 10.85 | +6.1% | -0.4% | +0.62 | +2.5 | 0.694 / 0.698 / 0.689 | 3/3/3 |
| 12 MB | 256 | 9.47 | 9.48 | 10.49 | +10.8% | +0.1% | +1.02 | +16.3 | 0.932 / 0.936 / 0.959 | 6/3/6 |
| 16 MB | 256 | 9.47 | 9.42 | 10.48 | +10.7% | -0.5% | +1.01 | +16.2 | 0.984 / 0.984 / 0.988 | 6/3/6 |
| 32 MB | 256 | 9.61 | 9.59 | 10.58 | +10.1% | -0.2% | +0.97 | +15.5 | 1.000 / 1.000 / 1.000 | 6/3/6 |

With the three migration-affected invocations removed, the rows that change are 6 MB (7.24 / 7.24 / 7.57, +4.5%), 16 MB (9.44 / 9.42 / 10.45, +10.7%) and 32 MB (9.64 / 9.59 / 10.61, +10.1%).

Invocations whose own log fields show that the frame set changed between layouts:

| invocation | sorted contiguity, 1st -> 2nd round | reverse contiguity in 2nd sorted round | color_max values | thrash_pages_frac values |
|---|---|---:|---|---|
| rep=1 size=16 stride=256 | 0.7214 -> 0.7189 | 0.0010 | 46, 47 | 1.0000 |
| rep=2 size=6 stride=256 | 0.6945 -> 0.5453 | 0.1368 | 21, 22 | 0.1322, 0.1367 |
| rep=2 size=32 stride=256 | 0.6015 -> 0.5816 | 0.0143 | 87 | 1.0000 |

### Exp F (64 MB random chase, frame set by policy): two levels

| policy | ns_med (3 runs) | mean | L2D_CACHE_REFILL per access | PFN range (first run) | 1 GiB windows (PFN>>18) | contiguity | 2 MiB regions |
|---|---|---:|---:|---|---|---:|---:|
| compact | 155.7 155.7 155.4 | 155.58 | 1.164 | 0x213440e-0x214711d | 0x84..0x85 | 1.000 | 35 |
| scatter | 161.1 160.4 160.2 | 160.59 | 1.412 | 0x20ad800-0x2368e9a | 0x82..0x8d | 0.000 | 1191 |
| low | 157.2 157.1 156.5 | 156.90 | 1.209 | 0x20ad800-0x20de222 | 0x82..0x83 | 0.984 | 36 |
| high | 156.9 156.8 155.9 | 156.54 | 1.159 | 0x231370e-0x2368f36 | 0x8c..0x8d | 0.843 | 214 |
| region:0 | 155.3 155.1 154.8 | 155.06 | 1.169 | 0x2105a00-0x2116445 | 0x84 | 0.994 | 34 |
| region:1 | 161.1 160.3 160.9 | 160.76 | 1.370 | 0x20c0200-0x20e4cd8 | 0x83 | 0.993 | 33 |
| region:2 | 156.5 155.3 154.5 | 155.43 | 1.159 | 0x2140000-0x2144e16 | 0x85 | 0.999 | 34 |

Pearson r(ns_med, L2 refills per access) over the 21 runs = +0.955. Fast group 154.5-157.2 ns (15 runs), slow group 160.2-161.1 ns (6 runs), mean difference 4.77 ns (3.06%).

### Counter sanity (all logs)

| log | rows | rows with (mux) marker | MEM_ACCESS per hop | median ns_med / cycles per hop (ns) | implied clock (GHz) |
|---|---:|---:|---|---:|---:|
| expA.log | 84 | 0 | 1.000007-1.000102 | 0.5263 | 1.900 |
| expB.log | 180 | 0 | not recorded | 0.5272 | 1.897 |
| expC.log | 6 | 0 | 1.000062-1.000096 | 0.5264 | 1.900 |
| expD.log | 15 | 0 | 1.000006-1.000013 | 0.5274 | 1.896 |
| expL.log | 117 | not printed by layout.c | 1.000003-1.000015 | 0.5271 | 1.897 |
| expT.log | 30 | 0 | 1.000009-1.000013 | 0.5274 | 1.896 |
| expF.log | 21 | not printed by frames.c | 1.000084-1.000106 | 0.5272 | 1.897 |

### Permutation comparison (simulation, 400 seeds, 16384-page buffer)

| pages used | lmbench permutation: mean page index / buffer | probe permutation | TLB 128 sets x 8 ways LRU miss rate, lmbench / probe | TLB 256 x 5 LRU, lmbench / probe |
|---:|---:|---:|---|---|
| 512 | 0.451 | 0.500 | 0.0456 / 0.0447 | 0.0470 / 0.0476 |
| 1024 | 0.453 | 0.500 | 0.5418 / 0.5436 | 0.3564 / 0.3579 |
| 2048 | 0.459 | 0.500 | 0.9925 / 0.9926 | 0.9096 / 0.9084 |
| 4096 | 0.469 | 0.500 | 1.0000 / 1.0000 | 0.9999 / 0.9999 |
