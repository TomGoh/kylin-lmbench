# 核查报告：audit:evening-code

## Summary

Verdict: no defect in the evening programs invalidates the central evening results (shared-versus-clear in Exp V/V2, the order effect in Exp W, the lmbench runs of Exp H, 'load only slows' in Exp BG). One run-script design fault invalidates one sub-claim (Exp R, rewrite cost at 64 MB), and five weaknesses limit how far the results generalise. Verdicts refer to the evening logs (byte-identical to commit 7ef1be47) and to the analyst documents at commit 91d58f3d (21:02:41); the repository kept moving during the audit (HEAD a81989ba at 21:15:51, experiments V3 and Z).

What I re-derived and found correct:
- Chains: for the same page order, frames2 (measure) and probe3 (build_chain) write chains word-for-word identical to lmbench's stride_initialize and thrash_initialize (0 mismatches; random pattern and strides 64-1024). lmbench does rewrite the chain before every interval (src/lib_timing.c:757-760; only base_initialize returns early, src/lib_mem.c:138).
- Page moves: a test copy of frames2 with synthetic frame numbers moved 6,144 pages in each of 16 pick/mode/order/layout combinations with no page dropped, duplicated or mislabelled, in both passes. The kernel moves the page-table entry without copying (mm/mremap.c move_ptes, tag 6.6.0-79.93).
- Pagemap bit layout, PMU event numbers and the EL0-only filter are right per the kernel source at the tag. Cycles per hop at 1.9 GHz lie inside [ns_min, ns_max] in 863 of 866 frames2 records (the other 3 within 0.5%); cycles/ns is 1.891-1.898 in all 296 probe3 records. So: no multiplexing, no time outside EL0, no CPU sharing.
- Class confounds in Exp V: within class clear (72 measurements, 12 slots) latency does not depend on the number of 2 MiB regions (29-344, rho +0.13), candidate count or span. Clear sets measured right after the shared set are normal (150.9-152.4 ns). Every set of a run uses the same two virtual ranges. From 6 MB up the shared set's L2 refills lie far outside the range of all clear sets (1.88 against 1.03-1.07 at 32 MB).
- THP wrapper: the flag survives fork and exec in this kernel. lmbench under the wrapper matches the MADV_NOHUGEPAGE probe (18.8 vs 18.9 ns at 1 MB, 153.5 vs 155.7 at 64 MB), not the system-THP runs (15.3, 134.8).
- The discarded first start of run9 left nothing in the final logs.
- CHASE_UNROLL unset changes nothing in the timed loop (same four instructions in both versions, gcc 15.2 on aarch64); only the output gains a chase=loop field.

The documents at 91d58f3d already carry the Exp R confound, the reinterpretation of Exp S and the hypervisor metadata pages. New here: repeated runs re-measure nearly the same frames; a spacing artefact in the Exp W same-slot table; four frames2 revisions behind the four logs; no frame re-check at measurement time (with evidence it did not bite); the 64 MB threshold and snapshot nature of the region list; the unrecorded background rate; the doubtful meaning of the L3 refill event.

Not verifiable here: that the device binaries were built from these sources (no hash or compiler version stored), the N80's vm.max_map_count, the real host stage-2 state, and page colours of the frames2 sets.

## Defects

- **invalidates** | experiments/memlat-probe/run6-current-state.sh lines 21-27 (Exp R loop); results/memlat-n80-20260930/expR.log: Every size is run as rebuild=0 immediately followed by rebuild=1, and each new process receives the frames the previous one freed, in reverse order. The rebuild setting is therefore confounded with the direction of physical adjacency. At 64 MB rebuild=0 had ascending adjacency in 20 of 20 runs (median ascending 0.823, descending 0.033) and rebuild=1 descending in 20 of 20 (0.033, 0.821). At 4, 6 and 8 MB the assignment is the opposite in 19 of 20 runs, at 16 MB in 20 of 20. A model with a rebuild term and a model with separate ascending and descending slopes fit the 40 runs equally well (rms 0.062 vs 0.063 ns). On the three rebuild=1 runs of Exp BG (bg=none, 64 MB), which have mostly ascending layouts, the direction model errs by -0.00, +0.07 and -0.13 ns, the rebuild model by -0.36, -0.13 and -0.42 ns. Effect: Invalidates the reading that rewriting the chain costs about 5% at 64 MB (evening.json ev#1, second half; the 64 MB rows of the Exp R table in state-tables.md carry no caveat). Worklog 11.15 at 91d58f3d already withdraws it. The statement of no difference at 4 to 16 MB stands only as: no difference although direction was flipped as well. Rootcause 3.7, 4.3 and 5.3 do not use the number. Open point: afternoon Exp L shows descending equal to ascending up to 32 MB (ratio 0.992-1.001), while the BG runs suggest ascending is faster at 64 MB.
- **weakens** | frames2.c at 7ef1be47 lines 330, 337, 378; run11-vm-shared.sh lines 24-27; run12-vm-shared-sizes.sh line 24 (and the comment in run16-vm-shared-repeat.sh lines 3-4, outside this round): The seed only sets the chase order and the shuffled virtual order. Page selection is deterministic: sel[k] = cand[k*n/npages] over the class candidates sorted by frame number. Repeated runs therefore re-measure nearly the same frames. In Exp V runs 1-3 the shared set has pfn_min 0x20c0200, pfn_max 0x20fe1f9 and 135 regions all three times; clear sets likewise (slot 0x2300000000: 286, 286, 286 regions, same first and last frame). The shared sets of V2 and of the three V3 seeds start at 0x20c0200 or 0x20c0201, end within 3 frames of each other and span 131-137 of the same 165 listed regions. Effect: Weakens the replication behind rootcause 3.7 and worklog 11.6 and 11.14. '3 runs x 2 passes' and 'four page sets' are repeat measurements of one population of at most about 57.7 thousand frames in 165 regions of one GiB slot, under one VM and one boot. They show that the measurement repeats (extra L2 refills agree within about 0.05 between runs), not that the effect holds for other memory. The numbers in state-tables.md are unaffected.
- **weakens** | frames2.c at 7ef1be47 lines 306-327 (pool and the single frame-number read), 397-403 (re-read used only for statistics), 404-420 (pass 2): Frame numbers and class are read once at program start, up to about 110 s before the last set is measured. The pool is not mlocked, the return value of madvise is ignored, and nothing compares the frames after the moves or after either pass with the first read, or re-checks is_shared. Compaction, swap or a CMA allocation could move a page unnoticed. The only built-in cross-check is in the Exp W revision: for sorted order va_region_changes must equal mb2_regions-1. Effect: Weakens S, V and V2 slightly; there is no sign that it happened. In expW.log the identity holds in 76 of 76 sorted sets. In Exp V the region count computed from the re-read frames is identical across three independent runs for several sets (29, 56, 135, 286) and differs by at most 13 elsewhere. Cycles per ns rule out page faults during timing. A silent frame change would move pages between classes and shrink the difference, not create one. The conclusions of 3.7 stand.
- **weakens** | vm-frames.py lines 36 and 41-54; run13-vm-shared-seq.sh (does not refresh the list): The list holds the 2 MiB regions of frames that are present in the VMM's own page table, for mappings of at least 64 MB. For those it is right: bit 63 present, bits 0-54 frame number, swapped or untouched pages skipped. The saved guest-regions.txt has 386 regions (80/165/96/9/9/7/4/14/2 per slot) and all 728 class labels in expV, expV2 and expW agree with it at pfn_min and pfn_max. It is incomplete by construction. (a) Pages the host donates to the hypervisor for this VM (guest stage-2 tables, VM and vCPU state) are kernel pages outside any VMM mapping. (b) Guest memory mapped in pieces below 64 MB, for example a separate firmware region, is skipped; /proc/<pid>/maps was not saved, so this cannot be checked. (c) It is a snapshot: 386 regions at 19:24 and 19:29, 391 at 20:09; Exp W used a list 8-11 minutes old. (d) Any mapping of 64 MB or more would be taken as guest memory and short reads are not detected; neither occurred (one mapping, 65,249 pages). Effect: Weakens the magnitudes, not the direction. Hidden split regions put 4 KiB-mapped pages into class clear; listed but never donated pages put block-mapped pages into class shared. Both dilute the contrast, so the shared-minus-clear differences are lower bounds and 386 is a lower bound on the regions the VM split. The uniform L2 refill rate of class clear across all 12 slots (1.038-1.049 at 32 MB) limits contamination to a few percent of pages. Rootcause 3.7 already states (a) and its direction; (b) and (c) are not mentioned.
- **weakens** | frames2.c at 7ef1be47 line 378 (pick even): 'Spread evenly' takes every (n/npages)-th candidate of the class, so the physical spacing of a set depends on how many candidates the class has in the slot. At 64 MB the step is 1.5 for class clear and 3.0 for class shared in slot 0x20c0000000, and 1.4-8.0 elsewhere. In slot 0x2080000000 at 32 MB it degenerates to nearly contiguous pages (adjacency 0.44). In sequential mode latency follows the step among clear sets alone (Exp W, 64 MB, sorted: step 1.4-1.9 gives 9.17-9.47 ns, 3.2 gives 9.90-9.96, 4-5.4 gives 10.15-10.37, 6.9-8 gives 10.69-10.80). Effect: Weakens the 'Same slot, both classes' table of Exp W in state-tables.md: its +8.6% (64 MB) and +3.3% (16 MB) for 'spread evenly, sorted' are spacing artefacts. Against clear sets of equal step the shared set differs by about 0 (9.92 vs 9.90-9.96 ns at 64 MB), which supports the statement in 3.7 that sequential access shows no class difference. In random mode (V, V2) the step has no effect among clear sets (rho between -0.27 and +0.31 at 16-64 MB), so the shared-versus-clear result is untouched. The step does decide how many pages share one stage-2 descriptor cache line (one per line up to about 24-32 MB, two to three at 48-64 MB), which matters when reading the size dependence or the per-walk cost formula.
- **weakens** | frames2.c at 7ef1be47 lines 79-86; probe3.c at 7ef1be47 lines 120-127; src/lat_mem_rd.c lines 87-106: The timed loop has one load per iteration; lmbench times 100 loads in a row. Everything else matches lmbench: the chain, the rewrite before each interval, whole-lap intervals of about 110 ms (lmbench aims at 1.1 x 100 ms, src/lib_timing.c:714-717), 11 intervals in probe3. frames2 reports the median of 5 intervals; lmbench and the probe3 analysis use the minimum of 11. Effect: Weakens only comparisons of absolute sequential values from R, BG and W with lmbench or N90 numbers (the analyst measured 4-9% lower in Exp X). Comparisons inside one program are unaffected. The documents at 91d58f3d carry this caveat (worklog 11.10, rootcause section 2 and 4.3).
- **weakens** | bgload.c lines 50-62; run6-current-state.sh lines 32-52: bgload prints its achieved rate only on normal exit; the script sends its output to /dev/null and kills it, so the traffic level was never recorded. The load is a sequential stream over 256 MB on cpu5 (and cpu6), which also evicts cpu0's data from the shared L3. Conditions run in a fixed order (none, r1, w1, w2) with 3 runs each (2 for random 64 MB). The probe's buffer layout differs by condition (the 64 MB buffer spans 538-542 regions without load, 144-257 with load). No sampler runs in this part; the interconnect values come from probe3's own reads (all 1800000). Effect: Does not affect the statement drawn in rootcause 5.3 and worklog 11.15: with the interconnect already at its highest frequency, load on other cores only slows cpu0. The loaded minimum is above the unloaded maximum in all five tests (14.18 vs 8.37-9.68 ns at 8 MB sequential, 196.7 vs 148.1-154.1 ns at 64 MB random), and cycles/ns of 1.893-1.898 shows cpu0 was not shared. It limits what BG can show: not the reaction of a traffic-driven governor, not bus traffic separately from L3 eviction, and no dose-response.
- **cosmetic** | results/memlat-n80-20260930/expS.log, expV.log, expV2.log; git history of experiments/memlat-probe/frames2.c; results/memlat-n80-20260930/README.md lines 72-90: The four frames2 logs come from four source revisions, not from 7ef1be47. expS matches 58c45b76 (field frames_in_slot, no classes), expV 3a0fabf5 (classes; one cycle per interval), expV2 8ec9fe31 (adds the 100 ms minimum interval), expW 58d25d2a (identical to 7ef1be47). Field meanings changed: contig_frac counts ascending adjacency only in S, V, V2 and either direction in W (documented); mb2_regions is computed from the re-read frames in virtual order in S, V, V2 and from the initial sorted list in W (not documented). The README says ns_min/med/max are over 11 repetitions and that each line is one process; frames2 uses 5 intervals and prints many lines per process. Effect: Does not affect the numbers: for sorted order without migration the two mb2 definitions agree, and the intervals in S and V are one full cycle of at least 0.15 s. Provenance only.
- **cosmetic** | frames2.c at 7ef1be47 lines 64-77, 243-260, 269: The counters are opened once and reused for every set. The scaling factor time_enabled/time_running is cumulative since creation, and frames2 prints no multiplexing marker (probe3 does, lines 333-336). Counts are averages over all five intervals while the reported time is the median, so a disturbed interval enters the counters but not the time (cycles/ns_med reaches 2.08 in one expV2 record). Effect: No effect here: no probe3 line has a mux marker and the cycle counts agree with wall time in all frames2 records, so nothing was multiplexed. It would mis-scale silently on a PMU with fewer counters, and it adds a little noise to the 'extra cycles' columns.
- **cosmetic** | probe3.c at 7ef1be47 lines 81-99 and 255-270: In random mode contig_frac and rcontig_frac are printed as 0.0000 although they are computed only for sequential mode. The page order uses a Fisher-Yates shuffle, not lmbench's own permutation (src/lib_timing.c:1646-1652), which is biased: of the first 2,048 entries of a 16,384-page order 56.6% lie in the lower half of the buffer, against 50.1% for the probe. The probe README documents the different shuffle. Effect: No effect: the analysis does not use adjacency for random rows, and the share of consecutive pages that are adjacent, within 16 pages or in the same 2 MiB agrees between the two shuffles.
- **cosmetic** | frames2.c at 7ef1be47 lines 311, 320-326, 387-391: Each moved page becomes its own VMA and leaves a hole in the pool: 'even' runs add about one VMA per page (my test: 7,186 VMAs after 6,144 moved pages). The 64 MB 'even' runs moved 196,608 pages, so they need vm.max_map_count above about 213 thousand; the kernel default is 65,530 (mm/util.c:894, refusal at mm/mremap.c:730 and 959). The N80 value is not recorded. A page that is swapped or under migration at the first read produces the message 'no PFN (need root)'. Effect: No effect on the evening logs: all 33 runs measured every slot that had enough pages and no log contains an error line. Portability and diagnosis only.
- **cosmetic** | run9-lmbench-current-state.sh lines 16 and 25-40; build-lmbench-tools.sh line 9: All sweeps with the system THP setting come last (19:09-19:13) instead of being interleaved. The time-stamp helper forks date and cut, unpinned, for every output line. Neither the compiler version nor a hash of lat_mem_rd or of the probes was stored with the results, so 'built from the repository source' rests on the procedure. The build itself is equivalent to lmbench's default for this program (-O; LMBENCH_SCHED unset, and the N90 reports record DEFAULT). Effect: No effect on rootcause 5.3. The contaminated first start left nothing behind: the first data line is at 18:44:38.537 (the restart); every line carries a time stamp, whereas a leftover process of run6 would have written bare lmbench lines; the 17,367 interconnect samples are 100-114 ms apart, so one sampler was writing; sweep 1 equals sweeps 2-5 within 1.5% from 0.75 MB up and shows 2.107 ns (4 cycles) at the smallest sizes.
- **cosmetic** | run13-vm-shared-seq.sh lines 16-24; results/memlat-n80-20260930/expW.log: The sorted and the shuffled order are measured in separate processes with separate pools, so they are not the same pages: first and last frame are identical in only 5 to 11 of the 12-13 sets of a pair of runs. In the three 'low, shuffled' runs some sets also sit at different virtual addresses. Effect: Does not affect the Exp W conclusion used in rootcause 4.3 (the order effect is equally large for both classes and appears only when sorted order makes neighbours physically close); my recomputation reproduces every row of the Exp W table. 'The same pages' should read 'the same selection rule'; worklog 11.15 already says so.

## Discrepancies

- The task text says the evening logs were produced by frames2.c at commit 7ef1be47. Only expW.log matches that source; expS, expV and expV2 match three earlier revisions (58c45b76, 3a0fabf5, 8ec9fe31), identified by their output fields and commit times.
- The task text calls this workstation x86. It is aarch64 with the same core type as the devices (Phytium FTC862, Great Wall D80F3, kernel 7.0.0-34-generic). Local tests therefore ran on the same architecture but another kernel, without root and without PMU access (perf_event_paranoid=4).
- run6 as it ran (commit 8b708298) still contained an lmbench part, which is where the leftover process of meta.log line 12 came from. The committed script (5cca9000, 18:45:59, after the run) has that part removed; the R and BG parts are identical in both versions.
- evening.json ev#1 and the Exp R table of state-tables.md still present 8.64 against 9.09 ns at 64 MB as an effect of rewriting the chain; worklog 11.15 at 91d58f3d withdraws it, and my check confirms the confound (20 of 20 runs in each group).
- state-tables.md, Exp S header, still says a slot that is not entirely RAM cannot be one 1 GiB stage-2 block, as the basis of a 1 GiB against 2 MiB comparison that worklog 11.15 and rootcause 3.7 withdrew.
- Rootcause 3.7 at 91d58f3d says the two classes differ only in host stage-2 granularity. As built, the sets also differ in frames, in physical density (61 against 146 pages per 2 MiB region in slot 0x20c0000000; 135 against 56 regions) and in order of measurement (clear always first). My log tests show that none of these produces the effect, so the accurate wording is: no other difference that the logs show to matter.
- Rootcause 3.7 and the comment in run16-vm-shared-repeat.sh speak of three more page sets from other seeds. In frames2 the seed does not influence which pages are selected; the sets overlap almost completely (see the second defect).
- Rootcause 3.7 says the sequential class difference is mostly within 1%. The same-slot table of state-tables.md shows +3.3% and +8.6% for 'spread evenly, sorted' at 16 and 64 MB; these are spacing artefacts of the 'even' rule, and with matched spacing the difference is about 0.
- results/memlat-n80-20260930/README.md says ns_min/med/max are over 11 repetitions and that each log line is one process; for frames2 it is 5 intervals and one process prints all lines of a run.
- The header of run9 says about 50 minutes; it ran 29 minutes (18:44:38 to 19:13:39). Worklog 11.2 planned three full-stride sweeps; run9 made two.
- The analyst documents changed while this round ran: HEAD moved from 77c3bf31 (with uncommitted edits) through 91d58f3d (21:02:41) to a81989ba (21:15:51, experiment Z). My assessments of the documents refer to 91d58f3d.

## Threats to validity

- The mapping from class to stage-2 granularity is inferred from kernel source and from the VMM's page table. It was never read from EL2, so 'shared means 4 KiB leaves, clear means blocks' is an inference the measurements are consistent with, not an observation.
- One GiB slot (0x20c0000000) supplies every shared set at the sizes that need page walks, under one idle 1 GiB VM, one boot and one machine. Nothing shows how the effect varies with other regions, VM sizes or VM activity.
- The machine was not quiesced (desktop session, background VM, load 0.2-2.7). Transients exist: in Exp S six consecutive sets around 19:15 read 154-164 ns with L3 refills at 1.00 where 151 ns is normal; in Exp V2 the two passes over one clear set differ by up to 11.9 ns at 12 MB; a clear set at 4 MB with no page walks is 8 ns slower than the others. Timing differences from single sets at 6-16 MB are therefore unreliable; the L2 refill differences are stable.
- PMU event meanings on FTC862 are assumed, not validated. Page walks are proxied by l2d_tlb_refill (the PMU advertises no dtlb_walk event). That l2d_cache_refill counts fetches by the table walker is inferred from the result itself. l3d_cache_refill fires on 38% and 59% of accesses at 3 and 4 MB, inside the 8 MiB L3, and costs only about 17-20 ns per event there (ns = 19.4 + 20.1 x events over 90 measurements with no walks), so it is not a fetch from DRAM. Explanations built on it, such as descriptors displacing data from L3 at 16-24 MB, remain interpretations.
- Page colours of the frames2 sets were not logged, so an L3 colour imbalance of the shared set cannot be tested directly. It is bounded: at 32 MB the L3 refill rate can only move between about 0.97 and 1.00 (the whole class difference is +0.02), and colours of data pages cannot add L2 refills.
- All orders are fixed: clear before shared, slots in ascending order, none then r1, w1, w2, wrapper sweeps before system-THP sweeps, rebuild 0 before 1. Only the clear sets measured before and after the shared set control drift in V and V2.
- Free memory changed through the evening and sequential latency depends on it: in Exp R the 64 MB buffer went from adjacency 0.86 and 413 regions to 0.76 and 538 regions within five minutes, and was at 0.00 by 20:00. Comparisons across times (Exp H against later runs, BG conditions) carry this.
- The lmbench buffer on the N80 may itself contain pages from regions shared with the VM, so the N80 random-access curve of Exp H includes an unknown share of the 4 KiB-mapped cost.
- Only one interconnect state (governor performance, 1800 MHz) was measured on any machine, and every cross-machine statement in rootcause 5.3 also carries the N80/N90 differences (16 vs 32 GB, 1.9 vs 1.8 GHz, kernel, background VM).
- No record exists of swap, compaction or migration counters, of vm.max_map_count, or of binary hashes and compiler versions on the device; the match between logs and source revisions rests on output formats and commit times.
- The VM was alive during the measurements: its region list grew from 386 to 391 in 45 minutes, and each new donation also flushes host TLB entries on cpu0.
- The frames that hold the stage-1 page tables of each set were not logged. 'Pass 2 uses new page-table pages' holds for the leaf tables by construction, but where those tables sit in physical memory is unknown.

## Recomputed tables

All tables are recomputed from the raw logs with my own parser (parse.py and the chk_*.py scripts; outputs in out/).

### A. Exp R: direction of physical adjacency by rebuild setting (expR.log, 20 runs per row)

| size | rebuild | median ascending adjacency | median descending adjacency | runs with ascending > descending | median ns (minimum of 11) |
|---:|---:|---:|---:|---:|---:|
| 4 MB | 0 | 0.001 | 0.499 | 1/20 | 4.448 |
| 4 MB | 1 | 0.496 | 0.002 | 19/20 | 4.449 |
| 6 MB | 0 | 0.010 | 0.349 | 1/20 | 6.973 |
| 6 MB | 1 | 0.348 | 0.010 | 19/20 | 6.994 |
| 8 MB | 0 | 0.010 | 0.261 | 1/20 | 9.370 |
| 8 MB | 1 | 0.260 | 0.010 | 19/20 | 9.354 |
| 12 MB | 0 | 0.157 | 0.175 | 8/20 | 9.875 |
| 12 MB | 1 | 0.175 | 0.157 | 12/20 | 9.886 |
| 16 MB | 0 | 0.329 | 0.131 | 20/20 | 9.672 |
| 16 MB | 1 | 0.132 | 0.330 | 0/20 | 9.654 |
| 64 MB | 0 | 0.823 | 0.033 | 20/20 | 8.639 |
| 64 MB | 1 | 0.033 | 0.821 | 0/20 | 9.086 |

### B. 64 MB: the three rebuild=1 runs of Exp BG (bg=none) against two models fitted on Exp R only

| ascending | descending | measured ns | model: rewrite costs +0.41 ns, direction irrelevant | model: direction matters, rewrite irrelevant |
|---:|---:|---:|---:|---:|
| 0.699 | 0.104 | 8.850 | 9.211 (error -0.361) | 8.851 (error -0.001) |
| 0.343 | 0.332 | 9.416 | 9.546 (error -0.130) | 9.347 (error +0.069) |
| 0.517 | 0.160 | 9.124 | 9.543 (error -0.419) | 9.252 (error -0.128) |

Both models fit the 40 Exp R runs equally (rms residual 0.062 and 0.063 ns).

### C. Exp V2: the shared set of slot 0x20c0000000 against the range of all clear sets (both passes)

| size | clear ns, min-max (n) | shared ns, pass 1 / pass 2 | clear values at or above the lowest shared value | clear L2 refills, min-max | shared L2 refills | page walks per access, clear range / shared |
|---:|---|---|---:|---|---|---|
| 2 MB | 20.3-24.1 (24) | 21.6 / 21.7 | 4 | 1.000-1.000 | 1.000 / 1.000 | 0 / 0 |
| 3 MB | 26.2-26.9 (24) | 26.5 / 26.4 | 18 | 1.000-1.000 | 1.000 / 1.000 | 0 / 0 |
| 4 MB | 30.2-39.4 (24) | 31.8 / 31.2 | 6 | 1.000-1.000 | 1.000 / 1.000 | 0 / 0 |
| 6 MB | 63.5-76.5 (24) | 71.3 / 72.1 | 2 | 0.998-1.000 | 1.082 / 1.075 | 0.848-0.964 / 0.889, 0.851 |
| 8 MB | 100.6-106.6 (24) | 111.6 / 109.7 | 0 | 0.999-1.005 | 1.174 / 1.167 | 0.977-0.999 / 0.991, 0.986 |
| 12 MB | 132.6-145.5 (24) | 143.4 / 143.2 | 1 | 1.001-1.008 | 1.376 / 1.360 | 1.000 / 1.000 |
| 16 MB | 141.4-148.1 (24) | 162.3 / 161.9 | 0 | 1.004-1.011 | 1.569 / 1.571 | 1.000 / 1.000 |
| 24 MB | 148.6-151.7 (24) | 169.1 / 168.7 | 0 | 1.015-1.031 | 1.934 / 1.940 | 1.000 / 1.000 |
| 32 MB | 150.7-156.0 (24) | 168.2 / 168.2 | 0 | 1.034-1.069 | 1.878 / 1.878 | 1.000 / 1.000 |
| 48 MB | 153.7-157.4 (22) | 168.5 / 168.7 | 0 | 1.083-1.134 | 1.921 / 1.938 | 1.000 / 1.000 |
| 64 MB | 154.9-158.3 (22) | 169.3 / 169.4 | 0 | 1.146-1.205 | 1.963 / 1.977 | 1.000 / 1.000 |

In time, the shared set is inside the clear range at 6 and 12 MB; in L2 refills it is outside the clear range at every size from 6 MB.

### D. Which frames2 revision produced which log

| log | run script and time | fields that identify the revision | revision (commit time) |
|---|---|---|---|
| expS.log | run10, 19:14-19:20 | frames_in_slot, no class | 58c45b76 (19:00:18) |
| expV.log | run11, 19:24-19:28 | class, frames_in_class; no mode or order | 3a0fabf5 (19:24:26) |
| expV2.log | run12, 19:29-19:36 | same format; about 0.6 s per measurement at 2 MB, which needs the 100 ms minimum interval | 8ec9fe31 (19:27:30) |
| expW.log | run13, 19:37-19:40 | mode, stride, order, va_region_changes | 58d25d2a, identical to 7ef1be47 |

### E. lmbench under the THP wrapper against the MADV_NOHUGEPAGE probe (random access, ns)

| size | lmbench under the wrapper (median of 5) | probe with MADV_NOHUGEPAGE (afternoon expA, median of 6) | lmbench, system THP (median of 2) |
|---:|---:|---:|---:|
| 0.5 MB | 11.48 | 11.82 | 8.82 |
| 1 MB | 18.82 | 18.88 | 15.28 |
| 2 MB | 21.41 | 21.61 | 17.56 |
| 8 MB | 101.48 | 103.38 | 81.86 |
| 64 MB | 153.45 | 155.69 | 134.75 |

8 MB sequential, stride 256, under the wrapper: 18 values, 10.162 to 10.511 ns, median 10.38, CV 0.83%. Interconnect samples during Exp H: 17,367, all 1800000.

### F. Exp W, 64 MB, spread evenly, sorted order (pass 1): latency follows the candidate step, not the class

| slot | class | candidates per selected page | ns |
|---|---|---:|---:|
| 0x2340000000 | clear | 1.4 | 9.37 |
| 0x20c0000000 | clear | 1.6 | 9.17 |
| 0x2180000000 | clear | 1.9 | 9.47 |
| 0x20c0000000 | shared | 3.0 | 9.92 |
| 0x22c0000000 | clear | 3.2 | 9.96 |
| 0x2300000000 | clear | 3.2 | 9.90 |
| 0x2140000000 | clear | 4.0 | 10.31 |
| 0x2200000000 | clear | 4.0 | 10.15 |
| 0x2240000000 | clear | 4.5 | 10.20 |
| 0x21c0000000 | clear | 5.4 | 10.37 |
| 0x2100000000 | clear | 6.9 | 10.69 |
| 0x2280000000 | clear | 8.0 | 10.80 |

### G. Exp BG (medians of the minimum of 11 intervals, ns; change against none)

| test on cpu0 | none | r1 | w1 | w2 |
|---|---:|---:|---:|---:|
| sequential stride 256, 4 MB | 4.43 | 12.38 (+180%) | 16.28 (+268%) | 23.30 (+426%) |
| sequential stride 256, 8 MB | 9.57 | 14.20 (+48%) | 20.38 (+113%) | 26.92 (+181%) |
| sequential stride 256, 64 MB | 9.12 | 13.43 (+47%) | 20.56 (+125%) | 27.05 (+196%) |
| random, 8 MB | 96.35 | 180.66 (+88%) | 217.16 (+125%) | 310.20 (+222%) |
| random, 64 MB | 151.11 | 196.96 (+30%) | 246.77 (+63%) | 334.94 (+122%) |

These reproduce the analyst's Exp BG table exactly.
