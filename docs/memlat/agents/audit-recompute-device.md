# 核查报告：audit:recompute-device

## Summary

The numbers hold. I re-derived every N80 table from the raw logs with my own parser before reading the analyst's scripts, then compared.

**Tables.** A cell-by-cell check of `derived/device-tables.md` and `derived/state-tables.md` covered 2,496 cells (experiments A, B, C, D, L, T, F, R, BG, H, S, V, V2, W, and V3 from 6 MB up). No cell differs beyond half a unit in the last printed digit. The N90 figures of part (j) also reproduce. Experiments V3, X, Y and Z, which landed while I worked, reproduce as well (Z within 0.3 cycles).

**Documents.** The figures quoted in rootcause 3.2, 3.7, 4.3, 5.3 and worklog 6 and 11 reproduce, apart from the items under `discrepancies`. None of those changes a conclusion. I compared against kylin-lmbench commit a81989ba (21:15:51); the documents changed several times during the audit.

**Log integrity.** Each raw log was committed once and never modified; `meta.log` was only appended to.

**What does not hold as written:**
- The "probability below 1e-5" for 18 lmbench sweeps without a high 8 MB value assumes independent sweeps. The same 18 sweeps are serially dependent at 6 MB (lag-1 correlation +0.84).
- "Extra cycles per walk ≈ 8 + 22 × extra L2 refills" is not reproduced from the four-run data (about 13–15 + 15–20×).
- The "pages apart" distances in rootcause 4.3 are selection steps in the pool's frame list, not measured physical distances.
- The drift-corrected Exp R correlations (−0.62, −0.77) are Pearson values set beside Spearman ones; the rank-based partials are −0.24 and −0.47.
- In `evening.json`, three figures are off: ev#3 (114, should be 118 by its own definition), ev#5 (30–34 ns, should be 29.6–31.6) and ev#15 (0.23, should be 0.21). The inferences of ev#1 and ev#9 do not stand; the current documents already withdraw both.

**What the data do support:**
- Host pages sharing a 2 MiB region with VM pages are slower in random access only where page walks occur. The extra L2 refills are reproducible: +0.08 to +0.92 per access, all 32 runs at 6 MB and above positive.
- The order effect in sequential access is equally large for both page classes.
- Background traffic only slows cpu0.

**Main limits:** one machine, one boot, one mode; every "shared" set at 6 MB and above comes from one GiB slot; the class labels are inferred, never read from EL2; and "two passes" are not independent samples.

## Defects

- **weakens** | docs/memlat/memlat-rootcause.zh-CN.md 5.3 and 1.4; evening.json ev#6; data expH-seq256.log, expH-seqall.log: The statement that 18 measurements without a high 8 MB value have probability below 1e-5 treats the 18 lmbench sweeps as independent draws with p about 0.5. They are 16 back-to-back processes 40 s apart (18:47:38 to 18:58:23) plus 2 full-command sweeps. In the same 18 sweeps the 6 MB values have lag-1 autocorrelation +0.84 and Spearman rho -0.83 with time order (permutation p = 0.0002; median 7.80 ns in the first four sweeps, 7.26 in the last four). Exp R shows consecutive processes get the previous process's frames back (114 to 118 of 120 pairs). Only 2 of the 18 used the paper's seven-stride command. Effect: The observation stands (18 values in 10.16-10.51 ns, none high; recomputed). The probability figure is unsupported and should be dropped. The run cannot separate the interconnect candidate from the page-layout candidate, which section 4.3 already concedes.
- **weakens** | rootcause 3.7 and worklog 11.14: 'extra cycles per walk is roughly 8 + 22 x extra L2 refills': Not reproduced from the data the sentence is attached to. Least squares on the four runs per size (expV2 + expV3; 6, 8, 12, 32, 48, 64 MB) gives 13.0 + 16.7x on per-size medians and 15.4 + 15.0x on the 24 per-run points (13.6 + 20.1x when 16 and 24 MB are included). 8 + 22x comes out only from the single V2 run with the same-slot estimator (9.1 + 21.5x), whose 6-12 MB points are n = 2 each and fall as x rises (15.1, 12.8, 10.7). Effect: The formula under-predicts the measured extra cost at 6, 8 and 12 MB (9.9, 11.9, 16.1 against medians of 12.8, 17.3, 20.2 cycles per walk). The qualitative statement that the cost rises with the extra L2 refills holds. The coefficients, and in particular the intercept of 8 cycles, should not be quoted.
- **weakens** | rootcause 4.3 (bullet on how far apart neighbouring virtual pages are physically) and worklog 11.15 (Exp W); data expW.log: 'Less than 2 pages apart on average ... 3 pages ... 7 pages' are not measured physical distances. They are the selection step k (every k-th pool frame of the slot in ascending PFN order). The mean physical distance (PFN span / pages) is 15.5-16.0 frames in 11 of the 12 sets at 64 MB (10.2 in the twelfth) and does not track the effect (Spearman +0.04), while k does (-0.99). Per-page PFNs were not logged, so the distribution of neighbour distances is unknown. Effect: The monotone dependence of the order effect on k is real (k 1.4-1.9: +12.6 to +16.6%; k 3.0-3.2: +6.8 to +8.2%; k 4.0-5.4: +3.8 to +5.0%; k 6.9-8.0: -1.3 to -0.2%), so 'strict adjacency is not required' stands. The wording 'how far apart physically, on average' overstates what was measured.
- **weakens** | worklog 11.15 (Exp R): 'after removing the drift the correlations are -0.62 and -0.77': Estimator mismatch. -0.62 and -0.77 are Pearson correlations of linearly detrended values (reproduced: -0.621, -0.770), set beside Spearman values (-0.94, -0.92). The rank-based equivalents are -0.24 and -0.47 (partial Spearman given lap) or -0.58 and -0.67 (Spearman of the residuals). Adjacency and the number of 2 MiB regions are near-deterministic functions of the lap at 12-64 MB (rho with lap -0.98 to -0.99 and +0.998). Effect: Once drift is removed, Exp R alone gives only weak evidence for the layout effect at 12 MB. The causal evidence is Exp L and W. No conclusion changes.
- **weakens** | worklog 6.4 and derived/device-tables.md Exp B (afternoon): The correlation analysis uses contig_frac (ascending adjacency only in probe.c) and page colour, and omits the number of distinct 2 MiB regions recorded in the same log. That count is the stronger predictor (rho with ns_med +0.95, +0.97, +0.94 at 8, 12, 16 MB) and absorbs contiguity: partial rho(ns, contig given regions) = -0.02, -0.31, -0.29, against +0.82, +0.67, +0.71 for regions given contig. Effect: 'Layout decides the latency' is not overturned. Exp B cannot tell exact adjacency from physical compactness, which agrees with the evening finding that near-adjacency is enough.
- **invalidates** | evening.json ev#9 (as written before the verification round); data expS.log: 'A 2 MiB-block stage-2 mapping is not measurably slower than a 1 GiB block' compares slots by /proc/iomem only. With VM pages in nine slots, only 0x22c0000000 and 0x2300000000 can still be 1 GiB blocks. Those two are the slowest clear slots in 31 of 32 runs at 12-64 MB (+1.8 to +2.4 ns), and in Exp Z they cost +3.4 to +4.0 cycles per hop with data in cache. Effect: The inference is invalid as designed and the data point the other way. The current documents already withdraw it (worklog 11.15, rootcause 3.7). The measured numbers in ev#9 reproduce.
- **weakens** | evening.json ev#1 (as written before the verification round); data expR.log, expBG.log: 'Rewriting the chain gives about 5% more at 64 MB' cannot be attributed to the rewrite. rebuild=1 is always the second process of a pair and receives the first one's frames in reverse order (rebuild 0: ascending adjacency 0.82; rebuild 1: descending 0.82). A fit over the 40 rows plus the three rebuild=1 rows of Exp BG gives a rebuild term of -0.02 ns once ascending and descending adjacency are separate covariates. Effect: The medians reproduce (8.64 against 9.09 ns, +5.2%, 20 of 20 laps). The attribution is already withdrawn in worklog 11.15; no current conclusion depends on it.
- **cosmetic** | derived/state-tables.md Exp V3 table, rows 2, 3, 4 MB; rootcause 3.7 row '2, 3, 4 MB: -0.1 to +0.3': The three V3-table rows reproduce only with the shared set of slot 0x2080000000 alone (4 regions), although each of these runs has three shared sets. With all three (the V2 table) the extras are -0.1, -0.0, +0.3 ns. For the set from slot 0x20c0000000, the slot used at every larger size, they are +0.7, -0.0, +0.9 ns against the pooled clear class. One clear set (4 MB, slot 0x20c0000000) reads 38-39 ns in both passes against 30-31 ns for the other 11 slots, with no walks and no extra L2 refills. Effect: The 'no walks, no difference' evidence in time units sits inside set-to-set noise of about 1 ns (one outlier of +8 ns), not 0.3 ns. The L2-refill evidence (1.000 in both classes) and the tlb4 result of Exp Z are unaffected.
- **cosmetic** | worklog 11.14, table and text on the two slots 0x22c0000000 and 0x2300000000: (a) 2 MB is left out: there the two slots are 1.1 ns (5%) slower without page walks (L3 refills +0.06), while the text says there is no difference when no walk is needed and lists only 3 and 4 MB. (b) '14 slots, the other 12 at 151.4-152.3 ns, chance 1/91': the class-clear data have 12 slots, the other 10 at 151.2-152.3 ns (1/66); with Exp S pooled in there are 14 and the others are at 151.1-152.1 ns; in Exp S alone the mixed slot 0x20c0000000 lies between the two. (c) The contiguous run of Exp V is included, those of V3 are not; the 16 MB median of the five listed runs is +1.9, not +2.0. Effect: None on the observation: in 31 of 32 runs at 12-64 MB both slots are slower than the median of the others (+1.8 to +2.4 ns, +3.2 to +4.8 cycles, no extra refills).
- **cosmetic** | derived/state-tables.md line 31; evening.json ev#3: The frame-reuse count does not match its stated definition. 'Ascending adjacency of one equals descending adjacency of the next within 0.02' holds in 118 of 120 pairs. 114 is the count for descending-of-first against ascending-of-second, and for both conditions together. Effect: None. Rootcause 4.3 says 'at least 114'.
- **cosmetic** | results/memlat-n80-20260930/README.md line 76; rootcause 3.7 first table; worklog 6.2 line 153; worklog 11.2 line 394; state-tables line 385 and worklog 11.10; device-tables Exp B 64 MB: Small internal inconsistencies. README says ns_min/ns_med/ns_max are over 11 repetitions, but frames2 (expS, V, V2, V3, W, X2, Y, Z) times 5. The 32 MB difference '+16.8 ns' is taken against the same-slot clear median 151.5, while the row above it shows the 12-slot median 151.7 (difference 16.6). Worklog 6.2 still says the walk count equals stride/4096 exactly (13 of 15 runs; the other two are 2.1% and 5.1% lower). The plan for Exp H says 3 full-command sweeps; 2 were run. 'Exp H (about 18:00)' ran 18:44:38 to 19:13:39. The Exp H 64 MB median appears as 10.27 (16 sweeps) and 10.29 (18 sweeps). The Exp B 64 MB 'partial r given colour' (-0.80) is a plain Pearson r (-0.803) because the colour fraction is constant there. Effect: None.

## Discrepancies

- No table cell differs beyond rounding: 2,496 cells of derived/device-tables.md and derived/state-tables.md were compared at half a unit in the last printed digit (1,226 in Exp S, V, V2, W; 1,270 in Exp R, BG, H, V3 from 6 MB, A, D, C, B, L, T, F). Everything below concerns prose, definitions or derived statements.
- derived/state-tables.md line 31 and evening.json ev#3: '114 of 120 pairs: ascending adjacency of one equals descending adjacency of the next within 0.02'. Recomputed for that definition: 118 of 120. 114 is obtained for descending-of-first against ascending-of-second, and for both together.
- evening.json ev#5: N80 random access is '30 to 34 ns below the N90 quiesced nVHE curve' from 24 MB up. Recomputed: 29.6, 30.4, 31.3, 31.6 ns at 24, 32, 48, 64 MB. Rootcause 5.3 ('more than 30 ns') is within rounding except at 24 MB (29.6).
- evening.json ev#15 and worklog 11.2 (line 409): Exp F pages from slot 0x20c0000000 have '0.23 more L2 refills'. Recomputed: 0.21 (means 1.370 against 1.169 and 1.159; medians +0.21). Only the first of the three runs gives 0.23-0.24. Rootcause 3.7 already says 0.21.
- derived/state-tables.md, Exp V3 table, rows 2, 3, 4 MB (-0.1, -0.1, -0.1; -0.3%, -0.5%, -0.4%; same slot +0.3, -0.2, -0.7): reproduced only with the shared set of slot 0x2080000000 alone. With the table's stated definition and all three shared sets the values are -0.1, -0.0, +0.3 ns, as in the V2 table and rootcause 3.7.
- rootcause 3.7 and worklog 11.14: 'extra cycles per walk is roughly 8 + 22 x extra L2 refills'. Recomputed on V2 + V3: 13.0 + 16.7x (per-size medians without 16 and 24 MB), 15.4 + 15.0x (per-run points), 13.6 + 20.1x (all eight sizes). At 6, 8, 12 MB the formula gives 9.9, 11.9, 16.1 against measured medians of 12.8, 17.3, 20.2.
- worklog 11.15: 'after removing the drift the Exp R correlations are -0.62 and -0.77'. Reproduced only as Pearson on linearly detrended values. Rank-based: partial Spearman given lap -0.24 and -0.47; Spearman of residuals -0.58 and -0.67.
- rootcause 4.3: 'pages less than 2 apart on average: 13-17%; 3 apart: 7-9%; 7 or more: none'. The percentages reproduce against the selection step k, not against physical distance. The mean physical distance is about 16 frames for every 64 MB spread set.
- worklog 11.14 two-slot table: the 16 MB median is quoted as +2.0; recomputed +1.9 for the five listed runs (1.42, 1.95, 2.95, 2.81, 1.71) and +1.8 with the contiguous V3 run. The 32 MB cycles figure is +3.5; recomputed +3.6. '14 slots, the other 12 at 151.4-152.3 ns, 1/91': the class-clear data have 12 slots (others 151.2-152.3; 1/66); with Exp S pooled in, the others are 151.1-152.1. The 2 MB size is omitted: there the two slots are +1.1 ns (+5%) without walks.
- rootcause 3.7, 32 MB table: the difference '+16.8 ns' is not the difference of the two rows shown (168.3 - 151.7 = 16.6). It is relative to the same-slot clear median 151.5.
- worklog 11.8 text: 'when the pages are not adjacent the order makes no difference'. The 64 MB spread-evenly sets show +5.1% (clear) and +8.2% (shared), and single slots up to +16.6%. This is corrected in worklog 11.15 and rootcause 4.3 but is not listed in the corrections table at the top of the worklog; neither is the withdrawal of the Exp S conclusion of 11.3.
- worklog 6.2 (line 153): walk count 'exactly equals stride/4096'. Recomputed: 13 of 15 runs; stride 128 run 2 is 0.030592 (-2.1%) and stride 1024 run 1 is 0.237303 (-5.1%). Rootcause 3.5 has the corrected wording.
- worklog 11.2 (line 394): Exp H planned with 3 full-command sweeps; expH-seqall.log holds 2.
- state-tables line 385 and worklog 11.10: 'Exp H (about 18:00)'. The stride-256 sweeps ran 18:47:38 to 18:58:23 and the whole of Exp H 18:44:38 to 19:13:39 (timestamps in the logs and meta.log).
- Exp H 64 MB stride-256 median is quoted as 10.27 (rootcause 4.3, worklog 11.10; 16 sweeps) and as 10.29 (state-tables H table, worklog 11.9; 18 sweeps). Both reproduce; the +13.3% against Exp X3 becomes +13.1% with 10.29.
- results/memlat-n80-20260930/README.md line 76: 'ns_min, ns_med, ns_max over 11 repetitions'. frames2 uses 5 (REPS 5), which is what state-tables says.
- derived/device-tables.md Exp B, 64 MB: 'partial r(ns, contiguity given colour) = -0.80' is the plain Pearson r (-0.803); the colour fraction is 1.0 in all 30 rows, so a partial correlation is undefined.
- rootcause 3.7 (Exp Z table, outside the stated round): '10 slots that are certainly 2 MiB blocks' and '2 slots' apply to the 4-16 MB configurations. At 32 MB there are 9 other slots; at 64 MB there are 8, and only one of the two special slots (0x2300000000) has enough pages. All cycle values reproduce within 0.3.
- rootcause 3.5 (outside the assigned sections): stride 16, protected against the other modes at 12-64 MB 'differs by less than 0.003 ns'. Recomputed medians differ by up to 0.005 ns (32 MB against nVHE).

## Threats to validity

- One machine, one boot, one boot mode (protected), with an idle protected VM and a desktop session running. One-minute load was 0.2-2.7 and cpu0 was not isolated. The N80 differs from the N90 in clock (1.9 against 1.8 GHz), memory, kernel and EL2 implementation.
- Run counts per cell are small. expA: 3 seeds x 2 counter groups (the second group is a separate process; ns differs by up to 8% at 0.5 MB and 3% at 6 MB). expD: 3 per stride. expF: 3 per policy. expL: 3 processes per cell. expBG: 3 per setting, 2 for random 64 MB (148.1 and 154.1 ns with no background). expH: random 5 sweeps, system-THP 2 and 3 sweeps, full command 2 sweeps.
- n = 2 cells are two passes over the same pages in one process, not independent samples. This applies to every 'shared' cell of expV2 from 6 MB up, every 'shared' cell of expW, and every slot of the expS spread-evenly block. Pass-to-pass differences at 6-12 MB have a median of 1.1-1.5 ns and reach 13-22 ns.
- From 6 MB up every 'shared' page set comes from one GiB slot (0x20c0000000). Independent sets per size: 4 for spread pages (V2 + V3), 1 or 2 for contiguous pages. The same-slot clear control exists and agrees with the pooled one.
- Which pages have 4 KiB stage-2 leaves is inferred from the VMM's pagemap plus kernel source; it was never read from EL2. Pages the hypervisor took for VM metadata are invisible to the list. expW reused the region list written at 19:29; the VM's regions grew from 386 (19:24) to 392 (21:05).
- Outliers and unstable points. expV2 4 MB clear set of slot 0x20c0000000: 38-39 ns against 30-31. expS contiguous sets: maxima of 156-164 ns in five slots. V3 single runs: +10.7 (6 MB), +12.8 (8 MB), +17.6 (12 MB), +10.9 (16 MB), +17.1 (64 MB) against medians of +6.5, +8.4, +10.9, +18.6, +13.4. expB 8 MB: one row at 10.24 ns with 0.924 L3 refills.
- Estimator choices move some numbers. frames2 tables use the median of 5 cycles, probe3 and lmbench the minimum of 11: the expV2 32 MB extra is +14.2 ns by median and +16.7 by minimum. Cycles per walk at 6, 8, 12 MB are 11.4, 15.4, 18.2 against the all-slot clear class and 15.1, 12.8, 10.7 against the same-slot clear set (V2); over four runs 12.8, 17.3, 20.2 against 17.1, 13.2, 17.4. CVs in the tables use the population SD.
- The 'high' rule depends on the pooling unit. Applied to the pooled 40 N90 values at 8 MB it gives 22 high (kvmoff 4, nvhe 5, vhe 7, pkvm 6). Applied per set of 10 it gives 14 (4, 5, 0, 5): vhe gets 0 because most of its values are high, so its own lower half is already high.
- ev2d (l2d_tlb_refill) is not an exact walk count. It falls below the page-crossing rate for physically contiguous frames: expD 2 of 15 runs (-2.1%, -5.1%); expR 64 MB rebuild 0, 5 of 20 runs at 0.0475-0.0570 instead of 0.0625; expS contiguous sets in slots 0x2 and 0x8a at 0.905-0.907 (other 12 slots 0.995-0.999); V3 contiguous 16 MB shared 0.809 against clear 0.992; V2 6 MB shared 0.870 against clear 0.935. 'Equal walks in both classes' is exact only for spread sets from 8 MB up.
- Counters are user-mode only (exclude_kernel, exclude_hv). frames, frames2 and layout scale counts by enabled/running time without printing a marker, so multiplexing cannot be read off those logs. There is no sign of it: events that must be 1 per hop are 1.0000 within 0.0001 in every log, and the probe logs carry no multiplex marker.
- The meaning of ev2a (L3 refills) on this core is unverified. It is 0.41 and 0.62 per access at 3 and 4 MB, where latency is 29 and 37 ns, so it cannot be read as 'fetched from memory'.
- Time order. expR: layout drifts monotonically over the laps, and rebuild is aliased with position in the pair and so with adjacency direction. expB: rho(ns, run order) is +0.35 to +0.50. expH: the 6 MB value drifts down 7% and random 16-32 MB is 1.5-2.7 ns higher in the late sweeps. V2 and V3 sizes are always run in ascending order. Inside frames2 the clear class is measured before the shared class. expBG settings ran in fixed order.
- In expW, sorted and shuffled are separate processes with their own 3 GiB pools, so the page sets are similar, not identical. In expL, 3 of 27 blocks changed adjacency mid-block (for example 0.6945 to 0.5453), so frames are not perfectly stable inside a process either.
- expH: only 2 of the 18 stride-256 values come from the paper's seven-stride command. The buffer's physical layout was not recorded by lmbench; the 'adjacency then' figures are probe3's from Exp R, 5 to 20 minutes earlier.
- Interconnect frequency is the sysfs cur_freq value: 17,367 samples at 1800000 during Exp H, and every per-interval reading in expR and expBG. The afternoon state is inferred from trans_stat frozen at 16.5 s. No measurement exists at any other frequency on any machine.
- probe3 and frames2 in 'loop' form read 4-9% lower than lmbench in sequential tests (Exp X1). Absolute sequential values of Exp B, L, R, W are not comparable with lmbench or N90 numbers.
- Cross-machine quantities: 'increment per walk' divides N90 time differences by N80 walk counts, and the N80 walk counts at 2-4 MB differ 1.6x to 3.3x between seeds. The non-quiesced N90 CSV carries the same env label (n90-nvhe-noLSM-full) as the quiesced one; only the file name tells them apart.
- expBG background loads ran on cpu5 and cpu6 (the other cluster) as 256 MB streaming reads or writes only. The slowdown includes shared-L3 eviction (4 MB sequential L2 refills rise from 0.008 to 0.17), not only bus traffic.
- 'The VM is idle' rests on a CPU-time figure (50 s in 3 h) that is not in the archived files; vm-process-n80.txt has no CPU-time column.

## Recomputed tables

All tables below were recomputed by the verifier from the raw logs with an independent parser (kv.py). ns_min / ns_med = minimum / median of the timed repetitions of one process (11 for probe, probe2, probe3, frames, layout; 5 for frames2). ev2d = l2d_tlb_refill ('walks'), ev05 = l1d_tlb_refill, ev03 / ev17 / ev2a = L1 / L2 / L3 data-cache refills, ev11 = cycles; all per pointer hop.

### (a) expA.log - random chase, stride 16, 4 KiB pages; 3 seeds x 2 counter groups = 6 processes per size
| MB | pages | n | ev2d mean | ev2d median | ev2d min-max | ns_min mean | ns_min median | ns_med mean | ns_med median | ns_med min-max |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 128 | 6 | 0.0000 | 0.0000 | 0.0000-0.0000 | 10.93 | 11.82 | 10.99 | 11.84 | 8.04-12.41 |
| 1 | 256 | 6 | 0.0057 | 0.0000 | 0.0000-0.0195 | 18.85 | 18.88 | 18.89 | 18.90 | 18.53-19.33 |
| 1.5 | 384 | 6 | 0.0058 | 0.0068 | 0.0000-0.0130 | 20.00 | 19.99 | 20.01 | 20.01 | 19.94-20.08 |
| 2 | 512 | 6 | 0.0457 | 0.0396 | 0.0256-0.0835 | 21.27 | 21.61 | 21.34 | 21.70 | 20.31-21.94 |
| 3 | 768 | 6 | 0.1900 | 0.1796 | 0.1346-0.2698 | 28.87 | 28.95 | 29.27 | 29.14 | 28.23-30.48 |
| 4 | 1024 | 6 | 0.4469 | 0.4777 | 0.3382-0.5327 | 36.52 | 37.09 | 37.07 | 37.61 | 34.85-38.82 |
| 6 | 1536 | 6 | 0.8384 | 0.8411 | 0.7693-0.8825 | 65.20 | 65.63 | 68.17 | 68.35 | 64.26-70.83 |
| 8 | 2048 | 6 | 0.9671 | 0.9647 | 0.9584-0.9780 | 103.35 | 103.38 | 106.73 | 106.27 | 104.81-110.89 |
| 12 | 3072 | 6 | 0.9982 | 0.9982 | 0.9973-0.9990 | 136.12 | 136.01 | 137.59 | 137.57 | 136.99-138.32 |
| 16 | 4096 | 6 | 1.0000 | 1.0000 | 0.9997-1.0000 | 147.65 | 146.82 | 150.49 | 150.25 | 146.99-154.39 |
| 24 | 6144 | 6 | 1.0000 | 1.0000 | 1.0000-1.0000 | 153.39 | 152.74 | 154.55 | 154.22 | 152.82-157.67 |
| 32 | 8192 | 6 | 1.0000 | 1.0000 | 1.0000-1.0001 | 154.07 | 154.30 | 154.36 | 154.63 | 152.30-155.44 |
| 48 | 12288 | 6 | 1.0000 | 1.0000 | 0.9999-1.0001 | 154.47 | 154.62 | 155.09 | 155.66 | 152.97-157.05 |
| 64 | 16384 | 6 | 1.0001 | 1.0000 | 1.0000-1.0003 | 155.32 | 155.69 | 155.61 | 156.08 | 153.34-156.94 |

### (b) expD.log - sequential 64 MB, 3 processes per stride
| stride | stride/4096 | ev2d of the 3 runs | mean | mean / (stride/4096) | runs within 0.1% | ns_med mean |
|---|---|---|---|---|---|---|
| 64 | 0.015625 | 0.015625 0.015625 0.015625 | 0.015625 | 1.0000 | 3 | 4.402 |
| 128 | 0.031250 | 0.031251 0.030592 0.031251 | 0.031031 | 0.9930 | 2 | 9.374 |
| 256 | 0.062500 | 0.062501 0.062502 0.062501 | 0.062501 | 1.0000 | 3 | 9.993 |
| 512 | 0.125000 | 0.125001 0.125011 0.125001 | 0.125004 | 1.0000 | 3 | 10.337 |
| 1024 | 0.250000 | 0.237303 0.250072 0.250043 | 0.245806 | 0.9832 | 2 | 11.961 |

### (c) expB.log - sequential stride 256, fresh process per point, 30 laps (Spearman rho; contig_frac counts ascending adjacency only)
| MB | n | ns_med min-max | CV% (n) | rho(ns_med, contig) | rho(ns_med, 2MiB regions) | rho(ns_min, contig) | rho(ns_min, 2MiB regions) | partial rho(ns_med, contig given regions) | partial rho(ns_med, regions given contig) | rho(contig, regions) | rho(ns_min, run order) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 30 | 4.42-5.83 | 6.7 | +0.34 | +0.20 | +0.37 | +0.34 | +0.32 | +0.16 | +0.14 | +0.50 |
| 6 | 30 | 6.56-9.19 | 7.7 | -0.60 | +0.59 | -0.87 | +0.86 | -0.16 | +0.06 | -0.96 | +0.38 |
| 8 | 30 | 8.31-10.24 | 5.1 | -0.84 | +0.95 | -0.86 | +0.96 | -0.02 | +0.82 | -0.88 | +0.46 |
| 12 | 30 | 8.81-10.86 | 5.7 | -0.95 | +0.97 | -0.99 | +0.98 | -0.31 | +0.67 | -0.96 | +0.38 |
| 16 | 30 | 8.58-11.82 | 6.4 | -0.88 | +0.94 | -0.93 | +0.97 | -0.29 | +0.71 | -0.89 | +0.35 |
| 64 | 30 | 8.37-11.57 | 4.9 | -0.84 | +0.82 | -0.92 | +0.75 | -0.55 | +0.46 | -0.79 | +0.20 |

### (d) expL.log - same frames in three virtual orders (3 processes per cell; sorted and shuffled measured twice per process at stride 256); mean of ns_med
| MB | stride | n sorted/shuffled/reversed | sorted | shuffled | reversed | shuffled vs sorted | same, per process (%) | reversed vs sorted | adjacency when sorted |
|---|---|---|---|---|---|---|---|---|---|
| 4 | 256 | 6/6/3 | 4.503 | 4.484 | 4.480 | -0.4% | -0.5 -0.4 -0.4 | -0.5% | 0.749 |
| 6 | 256 | 6/6/3 | 7.188 | 7.468 | 7.153 | +3.9% | +5.8 +2.6 +3.2 | -0.5% | 0.706 |
| 8 | 128 | 3/3/3 | 8.521 | 9.222 | 8.493 | +8.2% | +8.5 +8.3 +7.8 | -0.3% | 0.692 |
| 8 | 256 | 6/6/3 | 8.859 | 9.562 | 8.761 | +7.9% | +8.4 +8.0 +7.3 | -1.1% | 0.711 |
| 8 | 512 | 3/3/3 | 9.040 | 9.926 | 9.046 | +9.8% | +11.0 +9.4 +9.0 | +0.1% | 0.683 |
| 8 | 1024 | 3/3/3 | 10.226 | 10.846 | 10.182 | +6.1% | +7.3 +5.6 +5.3 | -0.4% | 0.688 |
| 12 | 256 | 6/6/3 | 9.474 | 10.493 | 9.484 | +10.8% | +11.5 +10.2 +10.5 | +0.1% | 0.707 |
| 16 | 256 | 6/6/3 | 9.472 | 10.484 | 9.424 | +10.7% | +10.6 +11.4 +10.1 | -0.5% | 0.678 |
| 32 | 256 | 6/6/3 | 9.610 | 10.577 | 9.586 | +10.1% | +10.7 +10.1 +9.4 | -0.2% | 0.616 |

### (e) expF.log - 64 MB random chase, frame set chosen by policy (3 processes each; region:3 unavailable in all 3)
| policy | ns_med per run | ns_med mean | ns_min mean | ev17 (L2 refills) per run | ev17 mean | ev2d mean | 2MiB regions | lowest pfn |
|---|---|---|---|---|---|---|---|---|
| compact | 155.7 155.7 155.4 | 155.58 | 155.20 | 1.164 1.173 1.155 | 1.164 | 0.998 | 35 | 0x213440e |
| scatter | 161.1 160.4 160.2 | 160.59 | 160.35 | 1.425 1.404 1.407 | 1.412 | 1.000 | 1191 | 0x20ad800 |
| low | 157.2 157.1 156.5 | 156.90 | 156.66 | 1.215 1.212 1.201 | 1.209 | 0.998 | 36 | 0x20ad800 |
| high | 156.9 156.8 155.9 | 156.54 | 156.04 | 1.164 1.161 1.153 | 1.159 | 0.998 | 214 | 0x231370e |
| region:0 | 155.3 155.1 154.8 | 155.06 | 154.67 | 1.157 1.168 1.182 | 1.169 | 0.993 | 34 | 0x2105a00 |
| region:1 | 161.1 160.3 160.9 | 160.76 | 160.58 | 1.395 1.334 1.379 | 1.370 | 0.994 | 33 | 0x20c0200 |
| region:2 | 156.5 155.3 154.5 | 155.43 | 155.27 | 1.166 1.147 1.166 | 1.159 | 0.997 | 34 | 0x2140000 |

### (f) expR.log - sequential stride 256, fresh process per point, 20 laps x {rebuild 0, 1}; latency = ns_min; adjacency = contig_frac + rcontig_frac
| MB | rebuild | n | min | median | max | CV% sample / population | largest gap between neighbouring sorted values | rho(ns, adjacency) | rho(ns, 2MiB regions) | median ascending adj. | median descending adj. | ev2d median | ev2d min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 0 | 20 | 4.433 | 4.448 | 4.649 | 1.04 / 1.02 | 0.152 (4.497 to 4.649) | -0.18 | +0.22 | 0.001 | 0.499 | 0.0000 | 0.0000 |
| 4 | 1 | 20 | 4.433 | 4.449 | 4.645 | 1.16 / 1.13 | 0.104 (4.541 to 4.645) | -0.29 | +0.30 | 0.496 | 0.002 | 0.0000 | 0.0000 |
| 6 | 0 | 20 | 6.852 | 6.973 | 7.102 | 1.06 / 1.03 | 0.048 (6.879 to 6.927) | -0.51 | +0.37 | 0.010 | 0.349 | 0.0470 | 0.0449 |
| 6 | 1 | 20 | 6.831 | 6.994 | 7.149 | 1.20 / 1.17 | 0.073 (7.076 to 7.149) | -0.48 | +0.15 | 0.348 | 0.010 | 0.0432 | 0.0389 |
| 8 | 0 | 20 | 9.222 | 9.370 | 9.428 | 0.46 / 0.45 | 0.115 (9.222 to 9.337) | -0.51 | +0.31 | 0.010 | 0.261 | 0.0528 | 0.0518 |
| 8 | 1 | 20 | 9.216 | 9.354 | 9.423 | 0.47 / 0.46 | 0.086 (9.216 to 9.302) | -0.80 | +0.39 | 0.260 | 0.010 | 0.0485 | 0.0474 |
| 12 | 0 | 20 | 9.415 | 9.875 | 10.164 | 2.19 / 2.14 | 0.124 (9.415 to 9.539) | -0.94 | +0.94 | 0.157 | 0.175 | 0.0578 | 0.0450 |
| 12 | 1 | 20 | 9.454 | 9.886 | 10.205 | 2.16 / 2.11 | 0.103 (9.454 to 9.557) | -0.95 | +0.95 | 0.175 | 0.157 | 0.0563 | 0.0553 |
| 16 | 0 | 20 | 9.324 | 9.672 | 10.093 | 2.52 / 2.45 | 0.232 (9.712 to 9.944) | -0.93 | +0.91 | 0.329 | 0.131 | 0.0600 | 0.0484 |
| 16 | 1 | 20 | 9.435 | 9.654 | 10.092 | 2.19 / 2.13 | 0.249 (9.683 to 9.932) | -0.91 | +0.89 | 0.132 | 0.330 | 0.0596 | 0.0589 |
| 64 | 0 | 20 | 8.527 | 8.639 | 8.918 | 1.39 / 1.35 | 0.052 (8.717 to 8.769) | -0.89 | +0.88 | 0.823 | 0.033 | 0.0625 | 0.0475 |
| 64 | 1 | 20 | 8.897 | 9.086 | 9.288 | 1.09 / 1.07 | 0.082 (9.160 to 9.242) | -0.67 | +0.69 | 0.033 | 0.821 | 0.0625 | 0.0621 |

Both rebuild settings pooled (n = 40 per size), and the same after removing the drift over the 20 laps:

| MB | rho(ns, adjacency) | rho(ns, 2MiB regions) | rho(ns, lap) | rho(adjacency, lap) | partial rho(ns, adjacency given lap) | Spearman of linearly detrended residuals | Pearson of linearly detrended residuals |
|---|---|---|---|---|---|---|---|
| 4 | -0.22 | +0.24 | +0.50 | -0.15 | -0.17 | -0.19 | -0.24 |
| 6 | -0.49 | +0.27 | -0.27 | +0.31 | -0.45 | -0.49 | -0.46 |
| 8 | -0.61 | +0.36 | +0.07 | -0.05 | -0.61 | -0.67 | -0.77 |
| 12 | -0.94 | +0.94 | +0.94 | -0.99 | -0.24 | -0.58 | -0.62 |
| 16 | -0.92 | +0.90 | +0.90 | -0.98 | -0.47 | -0.67 | -0.77 |
| 64 | -0.37 | +0.42 | +0.40 | -0.98 | +0.08 | -0.08 | -0.05 |

Frame reuse: the 120 pairs of consecutive processes at the same size are all (rebuild 0 then rebuild 1) of one lap.

| MB | pairs | rho(ascending adj. of first, descending adj. of second) | median abs. difference | within 0.02: asc(first) vs desc(second) | within 0.02: desc(first) vs asc(second) | both |
|---|---|---|---|---|---|---|
| 4 | 20 | +0.814 | 0.0010 | 20 | 18 | 18 |
| 6 | 20 | +0.998 | 0.0000 | 20 | 20 | 20 |
| 8 | 20 | +0.987 | 0.0002 | 20 | 20 | 20 |
| 12 | 20 | +1.000 | 0.0006 | 19 | 17 | 17 |
| 16 | 20 | +1.000 | 0.0011 | 20 | 20 | 20 |
| 64 | 20 | +0.991 | 0.0006 | 19 | 19 | 19 |
| all | 120 | +0.995 | 0.0006 | 118 | 114 | 114 |

| MB | median rebuild 0 | median rebuild 1 | rebuild 1 vs 0 | laps with rebuild 1 slower |
|---|---|---|---|---|
| 4 | 4.448 | 4.449 | +0.01% | 8/20 |
| 6 | 6.973 | 6.994 | +0.30% | 12/20 |
| 8 | 9.370 | 9.354 | -0.18% | 1/20 |
| 12 | 9.875 | 9.886 | +0.11% | 9/20 |
| 16 | 9.672 | 9.654 | -0.19% | 10/20 |
| 64 | 8.639 | 9.086 | +5.17% | 20/20 |

### (g) expBG.log - median of ns_min over the runs of each background setting (all runs rebuild=1)
| point | none | r1 | w1 | w2 |
|---|---|---|---|---|
| seq 4 MB | 4.43 [4.42-4.46] n=3 | 12.38 [12.36-12.42] n=3 (+180%) | 16.28 [16.18-16.29] n=3 (+268%) | 23.30 [23.07-23.41] n=3 (+426%) |
| seq 8 MB | 9.57 [8.37-9.68] n=3 | 14.20 [14.18-14.23] n=3 (+48%) | 20.38 [20.36-20.39] n=3 (+113%) | 26.92 [26.08-26.93] n=3 (+181%) |
| seq 64 MB | 9.12 [8.85-9.42] n=3 | 13.43 [13.33-13.46] n=3 (+47%) | 20.56 [20.44-20.59] n=3 (+125%) | 27.05 [26.83-27.16] n=3 (+196%) |
| rand 8 MB | 96.35 [95.73-97.02] n=3 | 180.66 [179.88-182.50] n=3 (+88%) | 217.16 [217.08-217.79] n=3 (+125%) | 310.20 [305.21-316.80] n=3 (+222%) |
| rand 64 MB | 151.11 [148.08-154.14] n=2 | 196.96 [196.73-197.19] n=2 (+30%) | 246.77 [246.42-247.12] n=2 (+63%) | 334.94 [334.64-335.24] n=2 (+122%) |

### (h) expH - lmbench lat_mem_rd; sweeps per log: rand off 5 / system 2; seq256 off 16 / system 3; seqall off 2
Random (-t, stride 16):

| MB | thp=off: 5 sweeps in time order | median | range | thp=system: 2 sweeps | median |
|---|---|---|---|---|---|
| 1 | 18.9 18.6 18.8 19.5 18.4 | 18.82 | 18.43-19.48 | 15.2 15.4 | 15.28 |
| 2 | 21.5 21.0 21.4 20.3 21.5 | 21.41 | 20.34-21.53 | 17.6 17.5 | 17.56 |
| 3 | 28.3 27.4 28.1 28.6 29.6 | 28.28 | 27.42-29.61 | 23.0 23.0 | 23.02 |
| 4 | 34.7 34.7 34.4 34.1 35.5 | 34.67 | 34.10-35.46 | 27.8 27.2 | 27.48 |
| 6 | 62.6 62.3 63.5 60.0 63.0 | 62.62 | 60.00-63.46 | 49.4 49.9 | 49.66 |
| 8 | 101.2 100.0 102.1 102.0 101.5 | 101.48 | 100.04-102.15 | 81.7 82.0 | 81.86 |
| 12 | 131.7 131.6 132.1 132.3 133.5 | 132.05 | 131.65-133.45 | 112.9 112.2 | 112.57 |
| 16 | 142.3 142.1 143.5 143.8 143.9 | 143.46 | 142.11-143.88 | 122.1 121.9 | 121.99 |
| 24 | 147.7 147.9 147.9 150.4 150.8 | 147.92 | 147.66-150.78 | 129.3 128.8 | 129.08 |
| 32 | 148.8 149.6 150.4 151.7 152.1 | 150.39 | 148.80-152.10 | 131.7 130.9 | 131.29 |
| 48 | 149.9 151.8 150.8 151.2 152.9 | 151.17 | 149.87-152.86 | 134.0 133.7 | 133.84 |
| 64 | 152.4 152.5 154.2 153.5 153.5 | 153.45 | 152.40-154.16 | 134.9 134.6 | 134.75 |

Sequential stride 256 (off: the 16 dedicated sweeps followed by the stride-256 part of the 2 full-command sweeps; 'high' = more than 12% above the median of the lower half of the row):

| MB | n off | min | median | max | CV% (n) | high | rho(value, time order) | thp=system: 3 sweeps | median |
|---|---|---|---|---|---|---|---|---|---|
| 4 | 18 | 4.81 | 4.827 | 4.95 | 0.6 | 0/18 | +0.12 | 4.66 4.74 4.70 | 4.70 |
| 6 | 18 | 7.02 | 7.680 | 7.89 | 3.0 | 0/18 | -0.83 | 6.74 6.88 6.81 | 6.81 |
| 8 | 18 | 10.16 | 10.383 | 10.51 | 0.8 | 0/18 | -0.10 | 8.86 9.16 8.95 | 8.95 |
| 12 | 18 | 10.90 | 11.224 | 11.43 | 1.2 | 0/18 | -0.27 | 9.38 9.60 9.42 | 9.42 |
| 16 | 18 | 10.92 | 11.209 | 11.32 | 1.1 | 0/18 | -0.44 | 9.49 9.68 9.51 | 9.51 |
| 24 | 18 | 10.75 | 11.041 | 11.27 | 1.1 | 0/18 | -0.06 | 9.58 9.71 9.55 | 9.58 |
| 32 | 18 | 10.40 | 10.718 | 11.09 | 1.9 | 0/18 | +0.28 | 9.60 9.60 9.54 | 9.60 |
| 48 | 18 | 10.31 | 10.457 | 10.54 | 0.7 | 0/18 | +0.08 | 9.67 9.61 9.52 | 9.61 |
| 64 | 18 | 10.01 | 10.293 | 10.49 | 1.2 | 0/18 | -0.00 | 9.71 9.57 9.56 | 9.57 |

8 MB stride 256, thp=off, in the order taken: 10.39 10.48 10.34 10.36 10.29 10.36 10.43 10.38 10.41 10.46 10.39 10.16 10.32 10.40 10.46 10.51 10.25 10.27

8 MB at every stride (2 full-command sweeps): stride 16: 2.18 / 2.18; stride 32: 2.56 / 2.55; stride 64: 4.31 / 4.24; stride 128: 9.21 / 9.50; stride 256: 10.25 / 10.27; stride 512: 9.70 / 9.72; stride 1024: 10.82 / 10.96

expH-noc-samples.log: {'1800000': 17367} (samples per frequency); 17367 samples over 1741 s, largest interval 0.114 s.

### (i) expS.log - random chase on pages of one GiB slot at a time (class = all pages of the slot); median over runs x passes
| MB | pick | slot (GiB number) | n | ns_med median (range) | ns_min median | cycles | walks | L1 refills | L2 refills | L3 refills | adjacency | 2MiB regions |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 32 | even | 0x2 | 2 | 151.8 (151.2-152.4) | 151.0 | 288.4 | 1.000 | 1.000 | 1.051 | 0.980 | 0.00 | 135 |
| 32 | even | 0x3 | 2 | 151.9 (151.5-152.4) | 151.0 | 288.8 | 1.000 | 1.000 | 1.044 | 0.981 | 0.00 | 107 |
| 32 | even | 0x82 | 2 | 154.1 (153.1-155.2) | 153.4 | 292.3 | 1.000 | 1.000 | 1.061 | 0.991 | 0.28 | 33 |
| 32 | even | 0x83 | 2 | 164.3 (164.3-164.4) | 164.2 | 311.7 | 1.000 | 1.000 | 1.674 | 1.000 | 0.00 | 194 |
| 32 | even | 0x84 | 2 | 152.3 (151.4-153.2) | 151.2 | 288.4 | 1.000 | 1.000 | 1.045 | 0.980 | 0.00 | 229 |
| 32 | even | 0x85 | 2 | 154.1 (153.5-154.7) | 151.7 | 291.2 | 1.000 | 1.000 | 1.067 | 0.989 | 0.00 | 302 |
| 32 | even | 0x86 | 2 | 153.1 (151.6-154.6) | 153.0 | 290.7 | 1.000 | 1.000 | 1.072 | 0.986 | 0.00 | 270 |
| 32 | even | 0x87 | 2 | 152.6 (151.8-153.3) | 151.6 | 289.7 | 1.000 | 1.000 | 1.058 | 0.984 | 0.00 | 272 |
| 32 | even | 0x88 | 2 | 152.2 (151.5-152.9) | 151.2 | 288.8 | 1.000 | 1.000 | 1.052 | 0.981 | 0.00 | 282 |
| 32 | even | 0x89 | 2 | 152.1 (151.5-152.7) | 151.1 | 288.2 | 1.000 | 1.000 | 1.047 | 0.978 | 0.00 | 295 |
| 32 | even | 0x8a | 2 | 151.3 (151.2-151.4) | 151.0 | 287.8 | 1.000 | 1.000 | 1.042 | 0.977 | 0.00 | 295 |
| 32 | even | 0x8b | 2 | 154.6 (153.0-156.2) | 153.0 | 292.6 | 1.000 | 1.000 | 1.043 | 0.981 | 0.00 | 287 |
| 32 | even | 0x8c | 2 | 154.2 (153.7-154.8) | 153.2 | 292.5 | 1.000 | 1.000 | 1.051 | 0.982 | 0.00 | 272 |
| 32 | even | 0x8d | 2 | 151.9 (151.7-152.1) | 151.1 | 288.5 | 1.000 | 1.000 | 1.041 | 0.982 | 0.00 | 160 |
| 32 | low | 0x2 | 6 | 150.9 (149.6-159.7) | 150.0 | 286.1 | 0.907 | 1.000 | 1.044 | 0.979 | 1.00 | 17 |
| 32 | low | 0x3 | 6 | 151.9 (150.6-158.1) | 150.9 | 287.7 | 0.996 | 1.000 | 1.042 | 0.978 | 0.96 | 26 |
| 32 | low | 0x82 | 6 | 152.6 (151.5-154.4) | 152.0 | 290.0 | 0.995 | 1.000 | 1.053 | 0.980 | 0.97 | 23 |
| 32 | low | 0x83 | 6 | 153.3 (152.2-154.4) | 152.7 | 291.0 | 0.997 | 1.000 | 1.071 | 0.979 | 0.97 | 22 |
| 32 | low | 0x84 | 6 | 151.8 (149.6-152.3) | 150.8 | 287.4 | 0.996 | 1.000 | 1.043 | 0.979 | 0.99 | 17 |
| 32 | low | 0x85 | 6 | 151.0 (150.5-152.3) | 150.4 | 286.6 | 0.997 | 1.000 | 1.041 | 0.976 | 0.96 | 20 |
| 32 | low | 0x86 | 6 | 151.3 (150.7-153.1) | 150.6 | 287.2 | 0.997 | 1.000 | 1.040 | 0.979 | 0.86 | 84 |
| 32 | low | 0x87 | 6 | 151.3 (150.6-151.5) | 150.7 | 287.0 | 0.998 | 1.000 | 1.041 | 0.977 | 0.93 | 88 |
| 32 | low | 0x88 | 6 | 151.1 (150.3-151.8) | 150.6 | 287.0 | 0.997 | 1.000 | 1.040 | 0.978 | 0.89 | 59 |
| 32 | low | 0x89 | 6 | 151.9 (150.6-152.4) | 151.2 | 288.3 | 0.997 | 1.000 | 1.049 | 0.979 | 0.89 | 119 |
| 32 | low | 0x8a | 6 | 150.6 (148.8-151.2) | 149.6 | 285.9 | 0.905 | 1.000 | 1.037 | 0.977 | 1.00 | 17 |
| 32 | low | 0x8b | 6 | 153.4 (153.1-164.1) | 152.9 | 291.1 | 0.999 | 1.000 | 1.040 | 0.977 | 0.95 | 58 |
| 32 | low | 0x8c | 6 | 154.1 (153.2-160.6) | 153.2 | 292.0 | 0.996 | 1.000 | 1.041 | 0.981 | 0.87 | 82 |
| 32 | low | 0x8d | 6 | 151.6 (150.9-156.2) | 150.9 | 287.3 | 0.996 | 1.000 | 1.042 | 0.977 | 0.89 | 47 |
| 64 | low | 0x2 | 2 | 155.5 (155.4-155.7) | 155.2 | 295.1 | 0.997 | 1.000 | 1.178 | 0.996 | 0.99 | 33 |
| 64 | low | 0x3 | 2 | 155.7 (155.7-155.8) | 155.7 | 295.4 | 0.981 | 1.000 | 1.174 | 1.000 | 0.97 | 72 |
| 64 | low | 0x83 | 2 | 160.5 (160.3-160.6) | 160.5 | 304.4 | 0.998 | 1.000 | 1.340 | 1.000 | 0.93 | 49 |
| 64 | low | 0x84 | 2 | 155.8 (155.5-156.2) | 155.5 | 295.5 | 0.992 | 1.000 | 1.197 | 0.998 | 0.98 | 33 |
| 64 | low | 0x85 | 2 | 155.3 (155.0-155.7) | 155.2 | 294.7 | 0.998 | 1.000 | 1.151 | 0.997 | 0.94 | 37 |
| 64 | low | 0x86 | 2 | 155.9 (155.9-156.0) | 155.6 | 295.6 | 0.998 | 1.000 | 1.163 | 1.000 | 0.86 | 117 |
| 64 | low | 0x87 | 2 | 155.1 (155.0-155.1) | 155.0 | 294.4 | 0.990 | 1.000 | 1.165 | 0.995 | 0.96 | 107 |
| 64 | low | 0x88 | 2 | 155.9 (155.9-155.9) | 155.8 | 295.8 | 0.998 | 1.000 | 1.157 | 1.000 | 0.90 | 114 |
| 64 | low | 0x89 | 2 | 155.9 (155.7-156.1) | 155.8 | 295.7 | 0.999 | 1.000 | 1.174 | 0.998 | 0.93 | 136 |
| 64 | low | 0x8a | 2 | 155.8 (155.7-155.9) | 155.8 | 295.7 | 0.997 | 1.000 | 1.156 | 1.000 | 1.00 | 34 |
| 64 | low | 0x8b | 2 | 158.0 (157.7-158.3) | 157.8 | 299.5 | 0.998 | 1.000 | 1.151 | 1.000 | 0.96 | 94 |
| 64 | low | 0x8c | 2 | 157.2 (157.1-157.3) | 157.1 | 298.4 | 0.998 | 1.000 | 1.181 | 0.993 | 0.88 | 138 |
| 64 | low | 0x8d | 2 | 155.1 (154.9-155.4) | 154.8 | 294.3 | 0.998 | 1.000 | 1.173 | 0.994 | 0.85 | 120 |

### (i) expV.log - class shared (only slot 0x83 = 0x20c0000000 has enough pages) against class clear
| MB | pick | set | n | ns_med median (range) | ns_min median | cycles | walks | L1 refills | L2 refills | L3 refills | 2MiB regions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 32 | even | shared, slot 0x83 | 6 | 168.3 (166.4-168.4) | 168.2 | 319.1 | 1.000 | 1.000 | 1.877 | 1.000 | 135 |
| 32 | even | clear, slot 0x83 | 6 | 151.5 (150.9-154.4) | 151.0 | 287.8 | 1.000 | 1.000 | 1.040 | 0.979 | 56 |
| 32 | even | clear, all 12 slots | 72 | 151.7 (150.9-154.7) | 151.2 | 288.2 | 1.000 | 1.000 | 1.043 | 0.978 | 284 |
| 32 | even | shared minus clear (same slot) |  | +16.8 | +17.2 | +31.4 | -0.000 | -0.000 | +0.837 | +0.021 |  |
| 32 | even | shared minus clear (all slots) |  | +16.6 | +17.0 | +30.9 | -0.000 | -0.000 | +0.834 | +0.022 |  |
| 16 | even | shared, slot 0x83 | 2 | 155.9 (155.4-156.4) | 154.9 | 295.7 | 1.000 | 1.000 | 1.562 | 0.950 | 134 |
| 16 | even | clear, slot 0x83 | 2 | 144.4 (143.7-145.0) | 142.8 | 274.8 | 1.000 | 1.000 | 1.005 | 0.951 | 52 |
| 16 | even | clear, all 12 slots | 24 | 144.0 (142.9-146.8) | 142.9 | 274.3 | 1.000 | 1.000 | 1.007 | 0.943 | 272 |
| 16 | even | shared minus clear (same slot) |  | +11.5 | +12.2 | +21.0 | +0.000 | -0.000 | +0.557 | -0.001 |  |
| 16 | even | shared minus clear (all slots) |  | +11.9 | +12.0 | +21.5 | +0.000 | -0.000 | +0.555 | +0.007 |  |
| 32 | low | shared, slot 0x83 | 2 | 156.3 (156.1-156.5) | 156.1 | 297.1 | 0.948 | 1.000 | 1.144 | 0.978 | 18 |
| 32 | low | clear, slot 0x83 | 2 | 151.4 (150.9-151.9) | 150.8 | 288.1 | 0.957 | 1.000 | 1.043 | 0.983 | 19 |
| 32 | low | clear, all 12 slots | 24 | 151.8 (150.7-154.7) | 151.1 | 288.2 | 0.996 | 1.000 | 1.041 | 0.978 | 44 |
| 32 | low | shared minus clear (same slot) |  | +4.9 | +5.4 | +9.0 | -0.009 | -0.000 | +0.101 | -0.005 |  |
| 32 | low | shared minus clear (all slots) |  | +4.5 | +5.0 | +8.9 | -0.048 | -0.000 | +0.104 | +0.000 |  |

### (i) expV2.log - one process per size, pages spread evenly; shared sets: slots 0x82, 0x83, 0x89 at 2-4 MB (n = 6), slot 0x83 only from 6 MB (n = 2, two passes of one set)
| MB | walks clear / shared | clear ns_med median (range) | shared ns_med median (range) | extra ns (ns_med) | extra ns (ns_min) | extra ns vs same-slot clear | extra cycles | cycles per walk (all-slot clear) | cycles per walk (same-slot clear) | extra L2 refills | extra L3 refills |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 0.000 / 0.000 | 21.0 (20.3-24.1) n=24 | 20.9 (20.5-21.7) n=6 | -0.1 | -0.1 | +0.0 | -0.1 | - | - | +0.000 | -0.003 |
| 3 | 0.000 / 0.000 | 26.5 (26.2-26.9) n=24 | 26.5 (26.1-27.0) n=6 | -0.0 | -0.0 | -0.0 | -0.0 | - | - | +0.000 | +0.000 |
| 4 | 0.000 / 0.000 | 30.6 (30.2-39.4) n=24 | 30.9 (30.4-32.4) n=6 | +0.3 | -0.1 | -0.3 | +0.5 | - | - | +0.000 | +0.005 |
| 6 | 0.935 / 0.870 | 65.9 (63.5-76.5) n=24 | 71.7 (71.3-72.1) n=2 | +5.8 | +5.8 | +6.6 | +9.9 | 11.4 | 15.1 | +0.080 | +0.008 |
| 8 | 0.994 / 0.989 | 102.4 (100.6-106.6) n=24 | 110.6 (109.7-111.6) n=2 | +8.2 | +8.3 | +8.0 | +15.2 | 15.4 | 12.8 | +0.171 | +0.006 |
| 12 | 1.000 / 1.000 | 133.9 (132.6-145.5) n=24 | 143.3 (143.2-143.4) n=2 | +9.4 | +10.2 | +6.5 | +18.2 | 18.2 | 10.7 | +0.366 | +0.002 |
| 16 | 1.000 / 1.000 | 143.7 (141.4-148.1) n=24 | 162.1 (161.9-162.3) n=2 | +18.4 | +19.2 | +18.3 | +34.5 | 34.5 | 33.5 | +0.563 | +0.062 |
| 24 | 1.000 / 1.000 | 149.3 (148.6-151.7) n=24 | 168.9 (168.7-169.1) n=2 | +19.6 | +19.7 | +20.0 | +35.8 | 35.8 | 35.7 | +0.918 | +0.035 |
| 32 | 1.000 / 1.000 | 154.0 (150.7-156.0) n=24 | 168.2 (168.2-168.2) n=2 | +14.2 | +16.7 | +15.8 | +28.1 | 28.1 | 30.2 | +0.834 | +0.012 |
| 48 | 1.000 / 1.000 | 155.2 (153.7-157.4) n=22 | 168.6 (168.5-168.7) n=2 | +13.4 | +13.4 | +13.6 | +25.6 | 25.6 | 26.1 | +0.822 | +0.001 |
| 64 | 1.000 / 1.000 | 156.0 (154.9-158.3) n=22 | 169.3 (169.3-169.4) n=2 | +13.4 | +13.4 | +13.6 | +25.5 | 25.5 | 26.2 | +0.809 | +0.001 |

### (i) expW.log - sequential stride 256; sorted and shuffled are two processes (own pools); shared = slot 0x83 only (n = 2 per cell); ns_med medians
| MB | pick | class | n sorted/shuffled | sorted (range) | shuffled (range) | shuffled vs sorted | cycles s/sh | walks s/sh | L1 refills s/sh | L2 refills s/sh | L3 refills s/sh | adjacency sorted |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | low | clear | 24/24 | 8.18 (7.96-8.42) | 9.69 (9.59-9.81) | +18.5% | 15.52 / 18.38 | 0.0509 / 0.0545 | 0.439 / 0.412 | 0.279 / 0.265 | 0.772 / 0.786 | 0.91 |
| 8 | low | shared | 2/2 | 8.11 (8.11-8.11) | 9.73 (9.72-9.74) | +20.0% | 15.40 / 18.45 | 0.0374 / 0.0484 | 0.442 / 0.413 | 0.285 / 0.265 | 0.773 / 0.787 | 0.95 |
| 8 | even | clear | 24/24 | 9.64 (9.38-9.87) | 9.65 (9.59-9.68) | +0.1% | 18.29 / 18.30 | 0.0539 / 0.0551 | 0.411 / 0.414 | 0.260 / 0.261 | 0.782 / 0.786 | 0.00 |
| 8 | even | shared | 2/2 | 9.69 (9.66-9.71) | 9.69 (9.69-9.69) | +0.0% | 18.35 / 18.39 | 0.0420 / 0.0426 | 0.411 / 0.416 | 0.264 / 0.267 | 0.787 / 0.790 | 0.00 |
| 16 | low | clear | 24/24 | 8.38 (8.05-8.69) | 10.49 (10.36-10.59) | +25.2% | 15.90 / 19.89 | 0.0571 / 0.0606 | 0.686 / 0.582 | 0.580 / 0.498 | 0.897 / 0.903 | 0.92 |
| 16 | low | shared | 2/2 | 8.19 (8.19-8.19) | 10.40 (10.40-10.41) | +27.0% | 15.54 / 19.72 | 0.0500 / 0.0582 | 0.699 / 0.593 | 0.595 / 0.519 | 0.898 / 0.906 | 0.97 |
| 16 | even | clear | 24/24 | 10.54 (9.66-10.69) | 10.51 (10.49-10.54) | -0.2% | 19.99 / 19.94 | 0.0607 / 0.0614 | 0.569 / 0.575 | 0.480 / 0.493 | 0.902 / 0.904 | 0.00 |
| 16 | even | shared | 2/2 | 10.74 (10.74-10.74) | 10.68 (10.68-10.69) | -0.5% | 20.35 / 20.25 | 0.0566 / 0.0572 | 0.554 / 0.573 | 0.474 / 0.504 | 0.918 / 0.920 | 0.00 |
| 64 | low | clear | 22/22 | 8.45 (8.14-8.70) | 10.61 (10.60-10.66) | +25.6% | 15.96 / 20.13 | 0.0592 / 0.0625 | 0.761 / 0.619 | 0.671 / 0.552 | 0.984 / 0.986 | 0.94 |
| 64 | low | shared | 2/2 | 8.36 (8.35-8.36) | 10.62 (10.61-10.62) | +27.0% | 15.87 / 20.13 | 0.0576 / 0.0625 | 0.763 / 0.615 | 0.670 / 0.561 | 0.986 / 0.988 | 0.98 |
| 64 | even | clear | 22/22 | 10.13 (9.11-10.80) | 10.65 (10.61-10.82) | +5.1% | 19.23 / 20.19 | 0.0625 / 0.0625 | 0.618 / 0.617 | 0.522 / 0.549 | 0.988 / 0.986 | 0.00 |
| 64 | even | shared | 2/2 | 9.92 (9.92-9.93) | 10.74 (10.74-10.74) | +8.2% | 18.82 / 20.37 | 0.0625 / 0.0625 | 0.630 / 0.611 | 0.537 / 0.568 | 0.992 / 0.995 | 0.00 |

Shared minus clear in the same slot (0x83), ns_med medians of the two passes:

| MB | pick | order | clear | shared | shared vs clear | adjacency clear / shared |
|---|---|---|---|---|---|---|
| 8 | low | sorted | 8.03 | 8.11 | +0.9% | 0.97 / 0.95 |
| 8 | low | shuffled | 9.69 | 9.73 | +0.4% | 0.00 / 0.00 |
| 8 | even | sorted | 9.68 | 9.69 | +0.1% | 0.00 / 0.00 |
| 8 | even | shuffled | 9.68 | 9.69 | +0.1% | 0.00 / 0.00 |
| 16 | low | sorted | 8.16 | 8.19 | +0.4% | 0.96 / 0.97 |
| 16 | low | shuffled | 10.45 | 10.40 | -0.4% | 0.00 / 0.00 |
| 16 | even | sorted | 10.39 | 10.74 | +3.3% | 0.00 / 0.00 |
| 16 | even | shuffled | 10.53 | 10.68 | +1.4% | 0.00 / 0.00 |
| 64 | low | sorted | 8.24 | 8.36 | +1.4% | 0.98 / 0.98 |
| 64 | low | shuffled | 10.60 | 10.62 | +0.1% | 0.00 / 0.00 |
| 64 | even | sorted | 9.14 | 9.92 | +8.6% | 0.38 / 0.00 |
| 64 | even | shuffled | 10.65 | 10.74 | +0.8% | 0.00 / 0.00 |

Spread-evenly sets at 64 MB, per slot: the order effect follows the selection step k (every k-th pool frame of the slot in ascending PFN order), not the mean physical distance:

| slot | class | k | mean physical distance (frames) | adjacency sorted | sorted | shuffled | shuffled vs sorted |
|---|---|---|---|---|---|---|---|
| 0x8d | clear | 1.36 | 10.2 | 0.53 | 9.33 | 10.61 | +13.8% |
| 0x83 | clear | 1.61 | 15.8 | 0.38 | 9.14 | 10.65 | +16.6% |
| 0x86 | clear | 1.87 | 16.0 | 0.11 | 9.48 | 10.67 | +12.6% |
| 0x83 | shared | 3.03 | 15.5 | 0.00 | 9.92 | 10.74 | +8.2% |
| 0x8c | clear | 3.19 | 16.0 | 0.00 | 9.91 | 10.64 | +7.4% |
| 0x8b | clear | 3.23 | 15.8 | 0.00 | 9.96 | 10.64 | +6.8% |
| 0x88 | clear | 4.01 | 15.8 | 0.00 | 10.13 | 10.64 | +5.0% |
| 0x85 | clear | 4.05 | 16.0 | 0.00 | 10.27 | 10.67 | +3.9% |
| 0x89 | clear | 4.50 | 16.0 | 0.00 | 10.20 | 10.64 | +4.3% |
| 0x87 | clear | 5.42 | 15.7 | 0.00 | 10.37 | 10.76 | +3.8% |
| 0x84 | clear | 6.90 | 15.7 | 0.00 | 10.70 | 10.68 | -0.2% |
| 0x8a | clear | 7.97 | 15.6 | 0.00 | 10.79 | 10.65 | -1.3% |

### (extra, outside the stated round) expV3.log with expV2.log - four processes per size, pages spread evenly, shared set always in slot 0x83; per-run extra = median(shared) - median(clear, all slots of that run)
| MB | extra ns per run (ns_med) | median | extra ns per run (ns_min) | median | cycles per walk per run (all-slot clear) | median | cycles per walk per run (same-slot clear) | median | extra L2 refills per run |
|---|---|---|---|---|---|---|---|---|---|
| 6 | +5.8 +5.2 +10.7 +7.2 | +6.5 | +5.8 +5.8 +9.3 +7.7 | +6.8 | 11.4 12.0 24.2 13.6 | 12.8 | 15.1 18.4 15.9 22.4 | 17.1 | +0.08 +0.07 +0.07 +0.08 |
| 8 | +8.2 +8.2 +8.5 +12.8 | +8.4 | +8.3 +9.1 +9.0 +9.0 | +9.0 | 15.4 18.4 16.1 25.2 | 17.3 | 12.8 13.5 12.3 21.3 | 13.2 | +0.17 +0.18 +0.18 +0.17 |
| 12 | +9.4 +11.1 +17.6 +10.7 | +10.9 | +10.2 +10.4 +15.7 +10.3 | +10.4 | 18.2 19.8 30.4 20.5 | 20.2 | 10.7 16.5 27.0 18.4 | 17.4 | +0.37 +0.37 +0.35 +0.37 |
| 16 | +18.4 +10.9 +18.7 +19.5 | +18.6 | +19.2 +12.2 +19.6 +20.3 | +19.4 | 34.5 20.9 33.9 35.7 | 34.2 | 33.5 23.7 32.2 38.4 | 32.9 | +0.56 +0.56 +0.55 +0.55 |
| 24 | +19.6 +17.9 +19.4 +19.5 | +19.5 | +19.7 +19.0 +19.9 +19.7 | +19.7 | 35.8 34.1 35.6 37.0 | 35.7 | 35.7 32.9 36.6 37.3 | 36.1 | +0.92 +0.89 +0.87 +0.88 |
| 32 | +14.2 +14.7 +14.1 +16.7 | +14.4 | +16.7 +14.7 +14.5 +17.0 | +15.7 | 28.1 27.4 27.6 32.1 | 27.9 | 30.2 27.8 28.2 31.9 | 29.2 | +0.83 +0.84 +0.84 +0.83 |
| 48 | +13.4 +14.7 +14.1 +13.8 | +14.0 | +13.4 +15.1 +14.5 +13.9 | +14.2 | 25.6 27.5 26.7 26.2 | 26.4 | 26.1 27.8 27.4 26.9 | 27.1 | +0.82 +0.81 +0.78 +0.81 |
| 64 | +13.4 +17.1 +13.4 +13.1 | +13.4 | +13.4 +15.1 +13.4 +13.2 | +13.4 | 25.5 33.0 25.2 24.9 | 25.3 | 26.2 33.9 26.1 25.1 | 26.2 | +0.81 +0.82 +0.81 +0.79 |

### (extra, outside the stated round) expZ.log - translation-only chase, class clear, user-mode cycles per hop; 3 seeds x 2 passes
| pages x lines per page | walks per hop | other slots (10; 9 at 32 MB; 8 at 64 MB): median of slot medians (range) | slot 0x8b | slot 0x8c | two slots minus others, per seed | shared minus clear |
|---|---|---|---|---|---|---|
| 1024 x 4 | 0.000 | 14.5 (14.4-14.6) | 14.4 | 14.5 | -0.10 -0.03 +0.01 | -0.0 |
| 2048 x 1 | 0.956 | 37.0 (36.7-37.4) | 40.6 | 40.5 | +3.59 +3.50 +3.61 | +9.5 |
| 2048 x 2 | 0.937 | 37.7 (37.5-38.0) | 41.1 | 41.3 | +3.42 +3.46 +3.56 | +12.9 |
| 4096 x 1 | 0.996 | 39.1 (38.9-39.3) | 43.0 | 43.0 | +3.92 +3.95 +3.88 | +24.5 |
| 8192 x 1 | 1.013 | 49.2 (49.0-49.3) | 53.2 | 53.1 | +3.98 +4.04 +3.92 | +36.6 |
| 16384 x 1 | 1.015 | 61.8 (61.6-61.9) | - | 65.7 | +3.98 +3.93 +3.94 | +28.3 |

### (j) N90 host CSVs (results/n90-day3-host), 10 iterations per set
Random access (lat_mem_rd_rand, stride 16), median of 10 iterations, ns:

| MB | nvhe quiesced | nvhe non-quiesced (noisy) | pkvm try2 | kvmoff | vhe | pkvm minus median of the 3 baselines | noisy vs quiesced nvhe |
|---|---|---|---|---|---|---|---|
| 0.5 | 10.612 | 11.331 | 11.246 | 10.697 | 10.249 | +0.63 | +6.8% |
| 1 | 19.480 | 19.045 | 19.429 | 19.409 | 19.479 | -0.05 | -2.2% |
| 2 | 20.752 | 21.100 | 20.883 | 20.677 | 20.733 | +0.15 | +1.7% |
| 3 | 36.633 | 26.413 | 37.311 | 36.602 | 36.562 | +0.71 | -27.9% |
| 4 | 47.688 | 30.800 | 49.314 | 47.587 | 47.455 | +1.73 | -35.4% |
| 6 | 67.350 | 48.614 | 72.589 | 67.137 | 67.374 | +5.24 | -27.8% |
| 8 | 112.601 | 83.900 | 119.595 | 112.544 | 112.325 | +7.05 | -25.5% |
| 12 | 154.810 | 121.820 | 161.678 | 154.651 | 154.647 | +7.03 | -21.3% |
| 16 | 168.556 | 134.226 | 176.282 | 168.543 | 169.708 | +7.73 | -20.4% |
| 24 | 177.470 | 143.077 | 185.589 | 177.229 | 180.272 | +8.12 | -19.4% |
| 32 | 180.776 | 146.201 | 188.659 | 180.613 | 182.721 | +7.88 | -19.1% |
| 48 | 182.444 | 149.101 | 189.558 | 182.662 | 183.849 | +6.90 | -18.3% |
| 64 | 185.045 | 150.123 | 191.730 | 185.233 | 185.428 | +6.50 | -18.9% |

8 MB, stride 256 (lat_mem_rd_load), iteration order; * = high with the rule applied to the 10 values of the set, + = high with the rule applied to the pooled 40 values:

| set | values | median of the set's lower half | set threshold | high (per-set rule) | high (pooled rule) | median | mean |
|---|---|---|---|---|---|---|---|
| kvmoff | 12.24*+ 10.50 10.19 12.37*+ 12.21*+ 10.98 10.65 12.49*+ 10.06 10.35 | 10.350 | 11.592 | 4 | 4 | 10.815 | 11.203 |
| nvhe | 10.30 12.43*+ 12.62*+ 9.98 9.93 12.27*+ 12.35*+ 10.55 12.31*+ 10.02 | 10.020 | 11.222 | 5 | 5 | 11.410 | 11.276 |
| vhe | 11.47 12.62+ 11.73+ 12.47+ 12.45+ 12.57+ 10.92 12.45+ 10.30 12.63+ | 11.474 | 12.851 | 0 | 7 | 12.447 | 11.961 |
| pkvm | 10.70 11.77+ 12.57*+ 12.56*+ 12.52*+ 10.56 10.25 12.50*+ 10.10 12.47*+ | 10.557 | 11.824 | 5 | 6 | 12.123 | 11.600 |

Pooled rule: median of the 20 lowest of the 40 values = 10.424 ns, threshold 11.675 ns, 22/40 high; per-set rule: 14/40 high.

