# 调查代理报告：host-stats

> 这是多代理调查阶段的原始报告，英文原文照录。它的结论在使用前还要经过独立核查，
> 核查结果见同目录下的 verify-*.md。

## Headline

The three Figure 7 numbers are reproduced exactly as 10-iteration means: LLC Bnd = lat_mem_rd_load stride256 8 MB (+3.546 % vs kvmoff, -3.018 % vs vhe, +2.872 % vs nvhe), Main Mem = stride256 64 MB (+0.285 / -3.458 / +1.058 %), Rand Mem = lat_mem_rd_rand stride16 64 MB (+3.252 / +3.823 / +3.882 %). The LLC-boundary +3.55 % is not a systematic effect of protected mode: the metric takes two values (about 10.3 and 12.4 ns) in all four configurations and in both campaigns, pkvm simply had 6/10 iterations on the slow value against 4/10 for kvmoff (Fisher p = 0.66, Welch p = 0.40, exact permutation p = 0.40, bootstrap 95 % CI -0.49 to +1.24 ns), and the sign reverses against VHE, at strides 128 and 1024, and in the standalone re-run. The 64 MB random-access increase is systematic: it appears at 3 MB (768 pages), saturates at about 7 ns per access (6.2-8.4 ns) from 8 MB upward, is the same against all three baselines, is reproduced in the standalone campaign, and at the boot-session level is 19 between-session standard deviations (t(6) = 21.9, p = 6e-7). Sequential access shows at most 1-3 ns per page crossing, a trend no larger than the one between sessions without stage-2; separately, all four configurations contain sporadic fast random-access iterations (up to -21 %) and one nVHE session sits entirely in that fast state (-19 % at 64 MB), so a roughly -20 % state exists with no host stage-2 and no pVM.

## Findings

### host-stats#1 (MEASURED, confidence high)

The three paper numbers are means over 10 iterations of these rows: LLC Bnd = bench lat_mem_rd_load, variant stride256_sz8.00000MB: kvmoff 11.2029, nvhe 11.2763, vhe 11.9612, pkvm 11.6002 ns, giving +3.546 % vs kvmoff, -3.018 % vs vhe, +2.872 % vs nvhe. Main Mem = lat_mem_rd_load stride256_sz64.00000MB: 10.3814 / 10.3020 / 10.7839 / 10.4110 ns, giving +0.285 %, -3.458 %, +1.058 %. Rand Mem = lat_mem_rd_rand stride16_sz64.00000MB: 182.2089 / 181.1044 / 181.2069 / 188.1345 ns, giving +3.252 %, +3.823 %, +3.882 %. With medians the same rows give +12.094 / -2.603 / +6.249 %, -0.121 / -4.049 / +1.011 % and +3.507 / +3.398 / +3.612 %.

Evidence: q1_reproduce.py on results/n90-day3-host/n90-{kvmoff,nvhe,vhe}-noLSM-full-cpu0.csv and n90-pkvm-noLSM-try2-cpu0.csv; output out_q1.txt part A; table A. A blind search over all 526 (lat_mem_rd variant x estimator) candidates finds exactly one that rounds to +3.55 % and one to +0.29 %; two round to +3.25 % (the other is load stride64 16 MB mean, +3.248 %), but only the random 64 MB row also reproduces the vhe and nvhe bars.

### host-stats#2 (DOCUMENTED, confidence high)

The metric definitions and the estimator used by the paper are the ones above: the figure pipeline names these three variants, and the paper states that it reports the average of 10 repetitions.

Evidence: kylin-lmbench/scripts/build-xlsx-mean.py:219-221 (variant names), :21 (STAT_MODE = 'mean'), :32 (pkvm column = try2 CSV); paper.txt:214-215 ("10次重复实验测试的平均值", "图中选择使用平均值"); scripts/lmbench:473 and :477 (sequential run with strides 16..1024, random run 'lat_mem_rd -t ... 16').

### host-stats#3 (MEASURED, confidence high)

The long-format CSVs agree value for value with the raw lmbench reports, and every configuration was measured in one single boot session per campaign (iterations are repeated measurements inside that session, about 10 minutes apart).

Evidence: q0_verify_csv_vs_raw.py: independent re-parse of the 50 raw *-iterN.txt files, 2660 values compared per configuration, 0 mismatches, iterations 1..10 complete (out_q0.txt). Uptime in the raw reports: 5-9 min at iteration 1 and 1:37-1:39 at iteration 10 for kvmoff, nvhe, vhe, pkvm and nvhe-noisy (line 38 of each report).

### host-stats#4 (MEASURED, confidence high)

The LLC-boundary metric is two-valued, not unimodal. CONFIG.host, 40 pooled values: 17 in 9.93-10.98 ns (mean 10.37, sd 0.32) and 23 in 11.47-12.63 ns (mean 12.35, sd 0.30), nothing between 10.98 and 11.47; standalone: 14 in 10.06-10.56 (mean 10.19) and 26 in 11.69-13.07 (mean 12.48), nothing between 10.57 and 11.69. High-value iterations per configuration: CONFIG.host kvmoff 4/10, nvhe 5/10, vhe 8/10, pkvm 6/10; standalone 6/10, 7/10, 7/10, 6/10; both campaigns 10/20, 12/20, 15/20, 12/20. Three CONFIG.host values are intermediate (vhe 11.474 and 11.727, pkvm 11.772) and are counted as high by the two-cluster split. The extra nvhe-noisy session has 10/10 on the low value.

Evidence: Tables B and C. Two clusters explain 91.2 % (CONFIG.host), 95.2 % (standalone), 93.0 % (both) of the variance; BIC of one normal vs two normals 122.8 vs 80.0, 129.8 vs 61.1, 247.4 vs 154.3; parametric-bootstrap likelihood-ratio test of 1 vs 2 normals: 0 of 2000 null simulations reach the observed statistic in each sample (p <= 0.0005); largest-spacing test against a uniform null p = 0.019, 1e-5, 1e-4 (q2_llc.py, q5_standalone.py, q7_tables.py; out_q2.txt, out_q5.txt part C, out_tables.txt T3).

### host-stats#5 (MEASURED, confidence high)

At the LLC boundary the pkvm-minus-kvmoff difference is not distinguishable from zero: d(mean) = +0.397 ns (+3.55 %), Welch t = 0.86, df 17.9, p = 0.402, Welch 95 % CI [-0.576, +1.370] ns; exact permutation test on means p = 0.3995; on medians (d = +1.308 ns) p = 0.490; exact Mann-Whitney p = 0.218; bootstrap 95 % CI of d(mean) [-0.485, +1.239] ns = [-4.2 %, +11.5 %] (BCa [-0.513, +1.216]); bootstrap CI of d(median) [-1.50, +2.09] ns; Fisher exact test on the high-value counts (6/10 vs 4/10) p = 0.656.

Evidence: Table D; q2_llc.py, out_q2.txt lines 1-45 (exact permutation over all C(20,10) = 184756 splits; bootstrap 20000 resamples). Statistics code validated by hs_selftest.py against numeric integration and brute force (out_selftest.txt: ALL OK).

### host-stats#6 (MEASURED, confidence high)

The pkvm-kvmoff difference at the LLC boundary is smaller than differences among the configurations that have no host stage-2: vhe - kvmoff = +0.758 ns (+6.77 %, Welch p = 0.082, permutation p on medians 0.031), vhe - nvhe = +0.685 ns (+6.07 %); pkvm is 3.02 % faster than vhe; ordering of means kvmoff 11.203 < nvhe 11.276 < pkvm 11.600 < vhe 11.961. Two 10-iteration means drawn from one and the same population of this metric differ by more than 3.55 % with probability 0.38-0.39; 95 % of such differences lie in [-7.6 %, +8.1 %]. With the observed within-configuration sd of 1.04 ns about 108 iterations per configuration would be needed to detect a true 3.55 % shift with 80 % power.

Evidence: Table D rows 4-6; q6_extra.py part A (out_q6.txt): resampling two groups of 10 from the 30 no-stage-2 CONFIG.host values gives [-7.57 %, +8.13 %], P(|diff| >= 3.55 %) = 0.379; from the 60 values of both campaigns [-7.76 %, +8.42 %], P = 0.393; n = 2 (1.96 + 0.84)^2 x 1.043^2 / 0.397^2 = 108.

### host-stats#7 (MEASURED, confidence high)

The +0.397 ns is a mixture effect, not a shift of the values: +0.387 ns comes from pkvm having 6 rather than 4 iterations on the high value, +0.010 ns from differences within the two values (low value: pkvm - kvmoff = -0.052 ns, high value: +0.073 ns). The estimator instability (mean +3.55 %, median +12.09 %) is a consequence of the same two-valued distribution.

Evidence: q2_llc.py decomposition line in out_q2.txt (mode-mixture part +0.387 ns, within-mode part +0.010 ns; low mode n = 4 vs 6, high mode n = 6 vs 4); table A rows 1-2.

### host-stats#8 (MEASURED, confidence high)

The neighbouring cells show no consistent pkvm effect either. At 8 MB the other strides are two-valued as well and pkvm - kvmoff is -5.00 % (stride 128, p = 0.20), +2.84 % (512, p = 0.53), -1.77 % (1024, p = 0.60); the average over strides 128/256/512/1024 is -0.10 %; high-value counts summed over these four strides are kvmoff 24/40, nvhe 22/40, vhe 28/40, pkvm 21/40 (Fisher pkvm vs pooled 74/120: p = 0.35). At stride 256: 4 MB -0.07 % (p = 0.21), 6 MB +1.03 % (p = 0.18), 12 MB +7.64 % (p = 0.063, produced by three pkvm iterations at 13.4-13.7 ns; vhe has two at 13.1-13.8 ns; pkvm - vhe +0.94 %), 16 MB +2.37 % (p = 0.058, while vhe - kvmoff is +4.39 %, p = 0.003), 64 MB +0.29 % (p = 0.77). For sizes 12-64 MB at stride 256 the vhe session is 3.9-6.6 % slower than kvmoff (p 0.0006-0.043) although it has no host stage-2.

Evidence: Table E and its per-iteration table; out_q2.txt (one section per cell with the full battery of tests); q6_extra.py part B (out_q6.txt).

### host-stats#9 (MEASURED, confidence high)

The standalone campaign and the session-level view confirm this. Standalone 8 MB: pkvm - kvmoff = +0.074 ns (+0.65 %), Welch p = 0.89, bootstrap CI [-0.92, +1.06] ns; pkvm - nvhe -2.81 %, pkvm - vhe -3.01 %; high-value counts 6/6/7/7 (Fisher pkvm vs pooled p = 0.72). Taking one median per boot session, the two pkvm sessions (12.123 and 12.348 ns) lie inside the range of the six no-stage-2 sessions (10.815 to 12.532 ns, sd 0.69): difference +0.29 ns = 0.4 between-session sd, t(6) = 0.56, p = 0.59; with session means the difference is -0.04 ns (-0.37 %), p = 0.87.

Evidence: Tables N, O and P; q5_standalone.py parts B, C and E (out_q5.txt).

### host-stats#10 (MEASURED, confidence high)

Which of the two values a measurement takes is decided per measurement, not by a slowly varying state of the session: the 8 MB stride-256 value is uncorrelated with the 6 MB and 12 MB points measured immediately before and after it in the same run (Spearman rho = -0.09 and +0.02, p = 0.60 and 0.92) and with the 8 MB points of the other strides in the same iteration (rho between -0.13 and 0.00, p >= 0.43); agreement of the high/low label between strides is 19-24 of 40 (Fisher p >= 0.29); exact runs tests on the eight high/low sequences give p >= 0.31.

Evidence: q8_adjacency.py (out_q8.txt); runs tests in out_tables.txt T3. Each reported number is the minimum over the repetitions of one forked child process that makes its own allocation: src/lat_mem_rd.c:143-148 (benchmp, save_minimum), src/lib_timing.c:231-245 and :628 (fork, one initialize per child), src/lib_mem.c:153 (malloc in base_initialize), src/bench.h:198 (TRIES 11).

### host-stats#11 (INFERRED, confidence low)

The host data alone do not identify the physical cause of the two values. It is an arithmetic fact that 8 MiB at stride 256 touches 32768 lines, which equals the capacity of the L3 sets those lines can use (2048 sets x 16 ways, with the L3 geometry given in the task), and the same equality holds at 8 MiB for strides 128, 512 and 1024, which are two-valued too; but this does not establish causation, and a worklog that appeared in the benchmark repository during this run reports on-device measurements on the N80 that contradict a page-colour explanation and point to physical page contiguity and possibly an interconnect frequency state.

Evidence: Arithmetic: 8388608 / 256 = 32768 = (8192 / 4) x 16. Counter-evidence is DOCUMENTED, not verified by me: kylin-lmbench/docs/memlat/memlat-investigation-worklog.zh-CN.md sections 6.4-6.5 (L3 refill counts unchanged, latency follows physical contiguity) and section 9 (unverified NoC devfreq hypothesis).

### host-stats#12 (MEASURED, confidence high)

Random access: the pkvm-minus-baseline difference becomes distinguishable at 3 MB (768 pages): d(median) = +0.709 ns (+1.94 %) vs kvmoff, bootstrap CI [+0.25, +1.08], exact permutation p on medians 0.0008 (Holm-adjusted over the 33 sizes 0.025), Mann-Whitney p = 4.3e-5; +0.678 ns vs nvhe and +0.749 ns vs vhe (both p = 0.0008); this is 10 times the largest median difference among the three no-stage-2 configurations at that size (0.071 ns). At 2 MB (512 pages) the difference is +0.13 to +0.21 ns (+0.6 to +1.0 %): nominal p = 0.043 vs kvmoff only, 0.20 vs nvhe, 0.14 vs vhe, not significant after Holm correction. Below 2 MB there is no consistent difference (largest nominal effects at 0.375-0.5 MB, +0.36 and +0.55 ns vs kvmoff, p = 0.05 and 0.12, and a negative one at 0.75 MB). From 4 MB (+1.73 ns, +3.6 %) to 16 MB every pkvm iteration is above every kvmoff iteration.

Evidence: Table G; q3_rand.py parts B-D (out_q3.txt), criteria A-G per size for each baseline.

### host-stats#13 (MEASURED, confidence high)

The random-access difference saturates. Difference of medians vs kvmoff for 8, 12, 16, 24, 32, 48, 64 MB: +7.05, +7.03, +7.74, +8.36, +8.05, +6.90, +6.50 ns (mean 7.37, sd 0.68); vs the pooled no-stage-2 values mean 7.20 (6.43 to 8.11); main-mode means +7.05, +6.97, +7.66, +8.41, +7.63, +6.16, +6.22 (mean 7.16). The slope against log2(size) for sizes >= 8 MB is -0.11 ns per doubling (p = 0.70). About 7.2 ns is 13.7 CPU cycles at the locked 1.9 GHz. The relative overhead therefore peaks at 6 MB (+8.1 %) and 8 MB (+6.3 %) and declines to +4.5 % at 12-32 MB and +3.5 % at 64 MB only because the baseline latency keeps rising.

Evidence: Tables G and I; q3_rand.py part D (out_q3.txt: 'saturation' block and slope test); clock 0.5263 ns per cycle from line 18 of the raw reports ('[MHZ: 1900 MHz, 0.5263 nanosec clock]').

### host-stats#14 (MEASURED, confidence high)

At 64 MB the effect is real but the paper's own estimator is imprecise. Mean: +5.93 ns (+3.25 %), bootstrap CI [-0.74, +11.75] ns = [-0.4 %, +6.6 %], Welch p = 0.098, permutation p = 0.093, because 3 kvmoff and 2 pkvm iterations are fast outliers. Median: +6.50 ns (+3.51 %), permutation p = 0.031, Mann-Whitney p = 0.0115, bootstrap CI lower bound at about zero (-0.09 to +0.08 depending on the bootstrap seed). Main mode (flagged iterations removed in both samples, 8 vs 7 kept): +6.22 ns [+5.46, +6.97] (+3.35 %), Welch p = 2.4e-10; vs nvhe +6.42 (+3.46 %), vs vhe +6.27 (+3.38 %). All 8 main-mode pkvm values (191.13 or more) exceed all 30 values of the three baselines (186.80 or less). The closeness of the mean-based +3.25 % to the robust value is partly fortuitous: the kvmoff mean is 1.63 % below its median and the pkvm mean 1.88 % below its median. At 12-48 MB the mean-based pkvm-kvmoff figures are +6.8, +10.9, +7.2, +9.0, +7.1 % against +4.5, +4.6, +4.7, +4.5, +3.8 % with medians.

Evidence: Tables H, G and I; q6_extra.py part E (out_q6.txt); per-iteration values at 64 MB: kvmoff 176.314 185.641 168.704 185.315 185.150 176.485 185.057 186.795 186.202 186.426; pkvm 192.634 193.091 191.564 191.895 191.131 166.436 191.336 192.266 192.199 178.793.

### host-stats#15 (MEASURED, confidence high)

The standalone campaign reproduces the random-access increment: differences of medians vs kvmoff / nvhe / vhe are +2.04 / +2.35 / +2.25 ns at 4 MB (+4.3 to +5.0 %, every pkvm run above every baseline run), +7.11 / +7.31 / +7.43 ns at 8 MB (+6.3 to +6.6 %), +6.92 / +6.80 / +7.00 at 16 MB (+4.0 to +4.1 %), +8.02 / +7.75 / +8.76 at 32 MB (+4.3 to +4.8 %), +7.09 / +6.37 / +6.86 at 64 MB (+3.4 to +3.8 %); main-mode differences vs kvmoff +2.02 [1.77, 2.28], +7.25 [6.82, 7.67], +6.93 [6.43, 7.44], +8.29 [7.82, 8.75], +6.88 [6.29, 7.47] ns.

Evidence: Tables N and O; q5_standalone.py parts B and D (out_q5.txt) on results/standalone-mem-bench/standalone-{kvmoff,nvhe,vhe,pkvm}.log (10 runs each, all parsed).

### host-stats#16 (MEASURED, confidence high)

With the boot session as the unit of replication the random-access increment stands far outside the between-session spread: at 64 MB the six no-stage-2 session medians are 185.05-186.05 ns (sd 0.34) and the two pkvm sessions 191.73 and 192.41 ns, difference +6.63 ns (+3.58 %) = 19 sd, t(6) = 21.9, p = 5.9e-7; at 4, 8, 16, 32 MB the differences are +1.98, +7.19, +7.13, +7.73 ns (16, 38, 11, 9.5 sd; p from 1e-8 to 2e-5); in each case both pkvm sessions lie outside the range of the six others (exact session permutation p = 1/28 = 0.036, the minimum attainable with 2 vs 6 sessions).

Evidence: Table P; q5_standalone.py part E (out_q5.txt).

### host-stats#17 (MEASURED, confidence high)

Per-iteration outliers occur in all four configurations and are almost all fast. CONFIG.host, sizes >= 12 MB (60 cells per configuration): kvmoff 16 fast cells (down to -21.5 %: 12 MB it2 121.4; 16 MB it2 132.4, it7 134.9, it8 142.8; 24 MB it6, it9; 32 MB it1 142.3, it2 143.0, it4, it9; 48 MB it1, it5, it9; 64 MB it1, it3, it6), nvhe 9 (32 MB it5, it6; 48 MB it2, it5, it10; 64 MB it3 164.5, it6, it7; 12 MB it5 -2.4 %), vhe 6 (16 MB it4 144.5; 24 MB it5 143.1; 48 MB it5; 64 MB it4, it8 159.9, it10), pkvm 5 (24 MB it6 169.5; 32 MB it6 151.5; 48 MB it8; 64 MB it6 166.4, it10 178.8). Slow outliers are rare: kvmoff 6 MB it5 +2.2 % and it10 +2.9 %, nvhe 6 MB it8 +7.7 %. They cluster by iteration (kvmoff iterations 1, 2 and 9 have three fast sizes each; pkvm iteration 6 has three). Standalone: kvmoff 32 MB run6 151.3 and 64 MB run9 169.5; nvhe 64 MB run4; vhe 16 MB run10 134.5, 32 MB run8 154.9, 64 MB runs 1, 9, 10; pkvm 8 MB run10 104.1, 16 MB run3 140.4, 32 MB runs 1, 2, 8, 64 MB runs 7, 8.

Evidence: Table J; q3_rand.py part E (out_q3.txt) and q6_extra.py part C (out_q6.txt); rule |x - median| > max(3.5 x 1.4826 x MAD, 1 % of median) per configuration and size.

### host-stats#18 (MEASURED, confidence high)

A discrete fast state of random access exists on hosts without stage-2. The extra nVHE session n90-nvhe-noisy-full is faster than the clean sessions in all 10 iterations at every size from 3 MB upward: 26.4 vs 36.6 ns at 3 MB (-28 %), 30.8 vs 47.6 at 4 MB (-35 %), 83.9 vs 112.5 at 8 MB (-25 %), 134.2 vs 168.6 at 16 MB (-20 %), 150.1 vs 185.2 at 64 MB (-19 %), with no difference at 2 MB and below; the gap is 33-35 ns for all sizes from 12 to 64 MB. The fastest single iterations of the clean sessions reach the same level (kvmoff 12 MB it2 121.44 vs 121.82; kvmoff 16 MB it2 132.41 vs 134.23; vhe 24 MB it5 143.13 vs 143.08; kvmoff 48 MB it9 148.49 vs 149.10). The same session is slower, not faster, in sequential access at 12-64 MB (+7 to +13 % at strides 64-1024) and sits on the low value in all 10 iterations at the LLC boundary.

Evidence: Table K and table B (nvhe-noisy row); table M rows 'nvhe-noisy - kvmoff'; q3_rand.py part E and q6_extra.py part D. The session is documented as collected with incomplete service masking (docs/n90-kvm-host/nvhe.md:11, docs/n90-kvm-host/SUMMARY.md:296) and its CSV env column is mislabelled (docs/derived-data-audit.zh-CN.md:41-44).

### host-stats#19 (INFERRED, confidence medium)

Because a state that is 18-35 % faster from 3 MB upward occurs on an nVHE host with no pVM, and sporadically in kvmoff, nvhe, vhe and pkvm hosts, a random-access advantage of 20-30 % from about 3 MB upward (the signature of the pVM series in Figure 8) cannot be attributed to pVM isolation on the strength of its size alone; it matches an uncontrolled platform state. The mechanism of that state is not identified by the host data.

Evidence: Table K (size signature: zero up to 2 MB, -28 % at 3 MB, -35 % at 4 MB, -19 % at 64 MB) compared with the Figure 8 description in the task; I did not analyse the guest data. A repository worklog written during this run proposes an interconnect (NoC) devfreq state and marks it unverified (docs/memlat/memlat-investigation-worklog.zh-CN.md section 9).

### host-stats#20 (INFERRED, confidence low)

The pkvm increment appears to persist inside the fast state: the pkvm runs that reach it sit at 140.37 ns (16 MB, standalone run 3) and 151.46 ns (32 MB, CONFIG.host iteration 6), against 132.41, 134.86, 134.48 ns (16 MB) and 142.32, 143.04 ns (32 MB) for the fastest no-stage-2 runs and 134.23 / 146.20 ns for the nvhe-noisy medians, i.e. about +4 to +8 ns; the documented medians of the discarded first pkvm run in its fast phase (140.42 at 16 MB, 150.23 at 32 MB, 154.40 at 64 MB) agree with these single runs.

Evidence: Single values MEASURED (q8_adjacency.py, out_q8.txt; tables J and N). try1 medians DOCUMENTED only (docs/n90-kvm-host/standalone-memory-bench-validation.md:376-384; the try1 files are not in results/n90-day3-host). Partially fast no-stage-2 runs (142.8, 144.5 ns at 16 MB; 151.3, 154.9 ns at 32 MB) overlap, so single runs cannot settle it.

### host-stats#21 (MEASURED, confidence high)

Sequential access at 64 MB: pkvm minus kvmoff by stride 16, 32, 64, 128, 256, 512, 1024 is -0.000, +0.003, +0.050, +0.175, +0.030, +0.262, +0.368 ns (-0.01, +0.12, +1.20, +1.95, +0.29, +2.73, +3.50 %); strides 64, 128, 512 and 1024 are individually significant (Welch p = 2e-5, 0.003, 0.030, 1e-6) and the difference grows with stride (Spearman rho = +0.89, exact p = 0.012; vs nvhe rho = +0.93, p = 0.007). At 32 MB and 16 MB the pattern is the same and larger: +0.643 ns (+5.98 %) and +0.650 ns (+5.74 %) at stride 1024, rho = +1.00 and +0.96. Against vhe the differences are negative at every stride from 32 upward at all three sizes (for example -0.203 ns at 64 MB stride 1024, -0.704 ns at 16 MB stride 1024; rho = -0.46 to -0.68, not significant).

Evidence: Tables L and M; q4_seq.py parts A and B (out_q4.txt). Page crossings per access = stride / 4096 follows from the chain construction in src/lib_mem.c:198-201.

### host-stats#22 (MEASURED, confidence high)

Taken at face value against kvmoff or nvhe, the implied extra cost per sequential page crossing is 1.1-1.9 ns at 64 MB, 2.1-3.5 ns at 32 MB and 1.2-4.4 ns at 16 MB depending on the weighting of the fit (at stride 1024 alone: 1.47, 2.57, 2.60 ns), i.e. roughly 15-45 % of the extra cost per access in random access at the same size (6.50, 8.05, 7.74 ns, where every access lands on a different page). Equality of the two is rejected: at 64 MB stride 1024 equality would predict +1.62 ns per access, the observed value is +0.368 ns with bootstrap CI [+0.273, +0.458] (vs nvhe +0.248 [+0.042, +0.423]).

Evidence: Table M (slopes with bootstrap CIs, random-access column) and table L (d/x column); q4_seq.py part C (out_q4.txt, 'prediction check').

### host-stats#23 (MEASURED, confidence high)

The sequential stride trend cannot be attributed to the host stage-2 with these data, because sessions without stage-2 show the same kind of trend at equal or larger size: vhe - kvmoff slopes of +1.7 to +2.8 ns per page crossing at 64 MB (+2.9 to +5.0 at 32 MB, rho = +0.86 to +0.96) and nvhe-noisy - kvmoff +5.1 to +7.0 ns per page crossing, while nvhe - kvmoff is about zero; pkvm lies between kvmoff/nvhe and vhe at every stride from 64 upward. In the standalone campaign (stride 256 only) the 64 MB difference is +0.117 ns (+1.11 %, p = 0.37) vs kvmoff, 0.000 ns in medians vs vhe, and +0.002 ns [-0.107, +0.111] on the main mode, which bounds the cost at that stride to [-1.7, +1.8] ns per page crossing.

Evidence: Table M rows 'vhe - kvmoff', 'nvhe - kvmoff', 'nvhe-noisy - kvmoff'; table L last column; table O rows 'seq s256 64 MB'; q5_standalone.py part D (main-mode line for seq s256 64 MB).

### host-stats#24 (MEASURED, confidence high)

The paper's Main Mem figure (+0.29 %) is the stride-256 point, where the difference is indistinguishable from zero (Welch p = 0.77, bootstrap CI [-0.15, +0.22] ns = [-1.5 %, +2.1 %]; median difference -0.12 %); the statement that sequential access shows no observable translation penalty holds for that point, while the larger strides show +2.7 to +3.5 % against kvmoff and -0.8 to -1.8 % against vhe, which is within session-to-session variation.

Evidence: Table L (64 MB rows), table E last row, table P row 'seq s256 64MB' (session-level difference -0.045 ns, p = 0.76).

### host-stats#25 (INFERRED, confidence high)

Verdict. Of the two highlighted numbers, the 64 MB random-access +3.25 % reflects a systematic effect of protected mode (robust size about +6.2 to +7.1 ns, +3.4 to +3.8 %, same against kvmoff, nvhe and vhe, present at every size from 3 MB, replicated in a second campaign, p < 1e-6 at the session level); the LLC-boundary +3.55 % does not (two-valued metric, difference explained by 6 vs 4 slow iterations, all tests p >= 0.22, CI spanning -4 % to +11 %, reversed sign against vhe, at other strides and in the replicate, and smaller than the vhe-kvmoff difference).

Evidence: Synthesis of the measured findings above: tables D, E, G, I, O, P.

### host-stats#26 (INFERRED, confidence medium)

The size profile of the random-access increment is what a fixed extra cost per page-table walk would produce: no difference while the pages of the chain stay within TLB reach (up to 1.5-2 MB, 384-512 pages), a growing difference from 3 MB to 8 MB, and a constant about 7 ns once every access touches a page that is no longer in the TLB; the random chain visits a different page on every access (src/lib_mem.c:254-262). A small walk-related increment of the size suggested by the sequential data (about 1.5-3 ns per page crossing, i.e. 0.1-0.2 ns or 1-2 % at stride 256) cannot be excluded at the 8 MB sequential point; the data have no power to detect it there.

Evidence: Table G (onset and plateau), table M; chain construction in src/lib_mem.c:254-262; tlb = 48 pages in every raw report. The per-access walk counts themselves were not measurable from the host CSVs; a repository worklog reports PMU walk counts on the N80 that rise from 0.05 per access at 2 MB to 0.97 at 8 MB (docs/memlat/memlat-investigation-worklog.zh-CN.md section 6.1, DOCUMENTED, not verified by me).

### host-stats#27 (MEASURED, confidence medium)

Side result for the two fault metrics named in the same paper sentence: minor page-fault latency is higher under pkvm in both campaigns (CONFIG.host +1.99 % vs kvmoff, +1.92 % vs nvhe, +1.03 % vs vhe by means; standalone +1.36 %, +1.06 %, +1.31 %, Welch p from 8e-9 to 2e-7, every pkvm run above every kvmoff run), whereas the protection-fault figure (-1.08 % by means, +0.22 % by medians) is not specific to pkvm: in the standalone campaign pkvm - kvmoff is -3.06 % (p = 0.002) but vhe - kvmoff is -3.57 % (p = 0.0003).

Evidence: q1_reproduce.py part C (out_q1.txt) and q5_standalone.py part B, metrics 'prot' and 'pagefault' (out_q5.txt).

### host-stats#28 (DOCUMENTED, confidence high)

Two statements in an older internal document are not supported by the raw data: it lists 'LLC 8MB seq' as +12.1 % for pkvm and summarises sequential access as '0 to +14 %, confirmed'; the +12.1 % is the difference of medians of the two-valued metric (10.815 vs 12.123 ns) and is not significant (permutation p = 0.49). The same document lists the try2 64 MB random value of iteration 10 as 191 ns, whereas the CSV and the raw report have 178.793 ns.

Evidence: kylin-lmbench/docs/n90-kvm-host/standalone-memory-bench-validation.md:383 and :409, and :366; compared with table D and with results/n90-day3-host/n90-pkvm-noLSM-try2-cpu0.csv (lat_mem_rd_rand stride16_sz64.00000MB, iteration 10).

## Caveats

- Each configuration was measured in one boot session per campaign, so the iteration-level p-values test 'this session against that session' and cannot by themselves separate the KVM mode from the session. The session-level analysis (table P) addresses this but has only two pkvm sessions; its permutation p cannot go below 1/28.
- The pkvm column is the second pkvm run (try2). The repository documents a first run (try1) that switched to a roughly 17-33 % faster random-access state from iteration 4 and was set aside (docs/n90-kvm-host/standalone-memory-bench-validation.md:361-369, scripts/build-xlsx-mean.py:32); its raw files are not in results/n90-day3-host, so I could not analyse it. The choice of try2 over try1 is a selection made before my analysis.
- The extra session n90-nvhe-noisy-full is documented as collected with incomplete service masking and is used here only as an auxiliary observation, never as a baseline. Its CSV carries the wrong env label (docs/derived-data-audit.zh-CN.md:41-44).
- The outlier rule behind the main-mode comparison (|x - median| > max(3.5 x 1.4826 x MAD, 1 % of median)) was chosen after looking at the data. For that reason mean, median, rank-based, main-mode and session-level results are all reported side by side; the verdict does not depend on the rule.
- With 10 values per group the bootstrap intervals are approximate and move by about 0.1 ns between bootstrap seeds (the lower bound of the 64 MB median-difference interval is -0.09 to +0.08 ns); the exact permutation test on medians has a floor of 0.0008 and the one on means a floor of 1.1e-5.
- 'Not distinguishable from zero' at the LLC boundary is not proof of a zero effect: the interval is [-4.2 %, +11.5 %], and a small walk-related increment of about 1-2 % would be invisible under the two-valued noise.
- lmbench reports, for each size and stride, the minimum over the repetitions of one forked child with one allocation (src/lat_mem_rd.c:148). A value can therefore reflect the best moment of a run rather than its typical behaviour, which matters if a platform state changes during a run.
- Cache and TLB parameters (L3 8 MiB, 16 ways, 8192 sets; 48-entry first-level data TLB) are taken from the task description and the raw reports; I did not verify them on a device. No device or remote host was contacted.
- Bimodality was assessed with cluster separation, BIC, a parametric-bootstrap likelihood-ratio test and a largest-spacing test; Hartigan's dip test was not implemented.
- The sequential slope per page crossing depends on the weighting of the least-squares fit (weighted fits are dominated by strides 16-64, unweighted ones by strides 512-1024) and the relation is not linear in stride/4096; table L gives the per-stride values.
- I analysed host data only. The statement about Figure 8 is an inference from the host data, not an analysis of the guest runs.
- While I was working, new material appeared in the benchmark repository (docs/memlat/, experiments/memlat-probe/, results/memlat-n80-20260930/, docs/n90-kvm-host/llc-boundary-8mb-analysis.md). I did not create or modify any of it. My computations were finished before I read it and do not use it; where I cite it, it is labelled DOCUMENTED and unverified. Its LLC-boundary conclusion agrees with mine; its NoC frequency-scaling explanation of the fast state is explicitly unverified.

## Open questions

- What physical state decides between the two values at the LLC boundary (about 10.3 vs 12.4 ns)? The host data show only that it is decided per measurement and occurs in every configuration. Recording physical page contiguity, L3 refill counts and the interconnect frequency for each run on the N90 would settle it.
- What is the fast random-access state (150 instead of 185 ns at 64 MB) that holds for a whole nVHE session and sporadically elsewhere? Candidates are a platform frequency state (documented, unverified NoC devfreq hypothesis) or a memory-backing difference. On the device one should record /sys/class/devfreq/*/cur_freq and governor, AnonHugePages of the lat_mem_rd process, and l2d_tlb_refill per access in fast and normal runs.
- Does the pkvm increment persist inside the fast state? Single fast pkvm runs (140.4 ns at 16 MB, 151.5 ns at 32 MB) and the documented try1 medians suggest +4 to +8 ns, but partially fast baseline runs overlap. It needs either the try1 raw files or a controlled run with the platform state pinned.
- Is the sequential stride trend (pkvm above kvmoff and nvhe by 1-3 ns per page crossing) a stage-2 cost or a session effect? The vhe session shows a larger trend without stage-2. At least three boot sessions per configuration, with physical contiguity and walk counts recorded, are needed to separate them.
- Why was the vhe CONFIG.host session 4-6 % slower than kvmoff and nvhe in sequential access at 12-64 MB (p down to 0.0006) while the vhe standalone session was not? This is the clearest sign of session-to-session variation unrelated to stage-2.
- The documents list n90-pkvm-noLSM-try1-* as stored in results/n90-day3-host, but the files are absent. Where are they?
- The onset of the random-access increment between 512 and 768 pages, and its growth up to 2048 pages, imply an effective second-level TLB reach of roughly 500 to 2000 entries for this access pattern; the actual FTC862 second-level TLB size is not documented in the repository.

## Tables

Configurations: kvmoff (kvm-arm.mode=none), nvhe, vhe, pkvm (= KylinX, try2). CONFIG.host = `results/n90-day3-host/`, standalone = `results/standalone-mem-bench/`. nvhe-noisy = extra nVHE session kept in the repository as a contaminated counter-example; it is shown for reference only. All values in ns unless stated. Generated by q9_compact.py (file out_tables_compact.txt); wider versions of every table are in out_tables.txt.

**A. Reproduction of the Figure 7 memory-latency numbers** (n = 10 iterations per configuration; values in ns)

| metric = bench / variant | estimator | kvmoff | nvhe | vhe | pkvm | pkvm vs kvmoff | pkvm vs vhe | pkvm vs nvhe |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| LLC Bnd = lat_mem_rd_load / stride256_sz8.00000MB | mean (paper) | 11.2029 | 11.2763 | 11.9612 | 11.6002 | +3.546 % | -3.018 % | +2.872 % |
| LLC Bnd = lat_mem_rd_load / stride256_sz8.00000MB | median | 10.8150 | 11.4100 | 12.4470 | 12.1230 | +12.094 % | -2.603 % | +6.249 % |
| Main Mem = lat_mem_rd_load / stride256_sz64.00000MB | mean (paper) | 10.3814 | 10.3020 | 10.7839 | 10.4110 | +0.285 % | -3.458 % | +1.058 % |
| Main Mem = lat_mem_rd_load / stride256_sz64.00000MB | median | 10.3570 | 10.2410 | 10.7810 | 10.3445 | -0.121 % | -4.049 % | +1.011 % |
| Rand Mem = lat_mem_rd_rand / stride16_sz64.00000MB | mean (paper) | 182.2089 | 181.1044 | 181.2069 | 188.1345 | +3.252 % | +3.823 % | +3.882 % |
| Rand Mem = lat_mem_rd_rand / stride16_sz64.00000MB | median | 185.2325 | 185.0450 | 185.4280 | 191.7295 | +3.507 % | +3.398 % | +3.612 % |

**B. LLC boundary (sequential, stride 256, 8 MB): per-iteration values in ns, in time order** (H = above the optimal two-cluster split of the pooled 40 values: 11.23 ns for CONFIG.host, 11.13 ns for standalone)

| campaign | config | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | mean | median | sd | pattern | high |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| CONFIG.host | kvmoff | 12.242 | 10.498 | 10.186 | 12.370 | 12.205 | 10.980 | 10.650 | 12.486 | 10.062 | 10.350 | 11.203 | 10.815 | 1.000 | HLLHHLLHLL | 4/10 |
| CONFIG.host | nvhe | 10.296 | 12.434 | 12.623 | 9.985 | 9.925 | 12.267 | 12.352 | 10.553 | 12.308 | 10.020 | 11.276 | 11.410 | 1.198 | LHHLLHHLHL | 5/10 |
| CONFIG.host | vhe | 11.474 | 12.622 | 11.727 | 12.473 | 12.446 | 12.575 | 10.919 | 12.448 | 10.297 | 12.631 | 11.961 | 12.447 | 0.826 | HHHHHHLHLH | 8/10 |
| CONFIG.host | pkvm | 10.704 | 11.772 | 12.570 | 12.561 | 12.521 | 10.557 | 10.252 | 12.496 | 10.095 | 12.474 | 11.600 | 12.123 | 1.069 | LHHHHLLHLH | 6/10 |
| CONFIG.host | nvhe-noisy | 10.812 | 10.343 | 10.342 | 10.311 | 10.270 | 10.255 | 10.327 | 10.282 | 10.098 | 10.330 | 10.337 | 10.319 | 0.182 | LLLLLLLLLL | 0/10 |
| standalone | kvmoff | 10.087 | 10.197 | 12.383 | 10.158 | 10.092 | 12.529 | 11.719 | 12.441 | 12.469 | 12.389 | 11.446 | 12.051 | 1.152 | LLHLLHHHHH | 6/10 |
| standalone | nvhe | 12.593 | 12.552 | 10.267 | 10.323 | 12.558 | 12.571 | 12.308 | 12.513 | 10.221 | 12.630 | 11.854 | 12.532 | 1.096 | HHLLHHHHLH | 7/10 |
| standalone | vhe | 10.121 | 12.975 | 10.565 | 13.074 | 10.138 | 11.691 | 12.378 | 12.435 | 12.910 | 12.490 | 11.878 | 12.407 | 1.179 | LHLHLHHHHH | 7/10 |
| standalone | pkvm | 12.257 | 12.472 | 10.058 | 12.497 | 12.438 | 12.561 | 10.105 | 10.140 | 12.511 | 10.165 | 11.520 | 12.348 | 1.211 | HHLHHHLLHL | 6/10 |

**C. LLC boundary: modality of the pooled samples**

| sample | n | low cluster: n, range, mean (sd) | high cluster: n, range, mean (sd) | empty gap between clusters | variance explained by 2 clusters | BIC 1 normal vs 2 normals | largest-spacing test vs uniform, p |
|---|---:|---|---|---|---:|---|---:|
| CONFIG.host (4 configs) | 40 | 17, 9.93-10.98, 10.372 (0.321) | 23, 11.47-12.63, 12.351 (0.304) | 10.980-11.474 (0.494 ns) | 91.2 % | 122.8 vs 80.0 | 0.0187 |
| standalone (4 configs) | 40 | 14, 10.06-10.56, 10.188 (0.131) | 26, 11.69-13.07, 12.475 (0.294) | 10.565-11.691 (1.126 ns) | 95.2 % | 129.8 vs 61.1 | 1.0e-05 |
| both campaigns | 80 | 31, 9.93-10.98, 10.289 (0.266) | 49, 11.47-13.07, 12.417 (0.302) | 10.980-11.474 (0.494 ns) | 93.0 % | 247.4 vs 154.3 | 0.0001 |

Likelihood-ratio test of one against two normal components, parametric bootstrap with 2000 simulations: 2 x delta logL = 53.8, 79.8, 106.2 for the three samples; none of the 2000 null simulations reached the observed value in any of them (p <= 0.0005).

**D. LLC boundary (CONFIG.host): pairwise tests**

| comparison | d(mean) ns | rel. | Welch t (df), p | exact permutation p (means) | bootstrap 95 % CI of d(mean), ns | same, relative | d(median) ns | exact permutation p (medians) | Mann-Whitney p | high-mode counts, Fisher p |
|---|---:|---:|---|---:|---|---|---:|---:|---:|---|
| pkvm - kvmoff | +0.397 | +3.55 % | +0.86 (17.9), 0.4021 | 0.3995 | [-0.485, +1.239] | [-4.18 %, +11.46 %] | +1.308 | 0.4902 | 0.2176 | 6/10 vs 4/10, 0.6563 |
| pkvm - nvhe | +0.324 | +2.87 % | +0.64 (17.8), 0.5316 | 0.4820 | [-0.625, +1.258] | [-5.30 %, +11.75 %] | +0.713 | 0.6707 | 0.2475 | 6/10 vs 5/10, 1.0000 |
| pkvm - vhe | -0.361 | -3.02 % | -0.85 (16.9), 0.4099 | 0.4026 | [-1.158, +0.436] | [-9.50 %, +3.73 %] | -0.324 | 0.9818 | 0.5288 | 6/10 vs 8/10, 0.6285 |
| nvhe - kvmoff | +0.073 | +0.66 % | +0.15 (17.4), 0.8835 | 0.9180 | [-0.863, +0.983] | [-7.46 %, +9.02 %] | +0.595 | 0.8444 | 0.9705 | 5/10 vs 4/10, 1.0000 |
| vhe - kvmoff | +0.758 | +6.77 % | +1.85 (17.4), 0.0817 | 0.0823 | [-0.040, +1.491] | [-0.35 %, +13.91 %] | +1.632 | 0.0309 | 0.0524 | 8/10 vs 4/10, 0.1698 |
| vhe - nvhe | +0.685 | +6.07 % | +1.49 (16.0), 0.1561 | 0.1510 | [-0.183, +1.531] | [-1.53 %, +14.36 %] | +1.037 | 0.2368 | 0.0753 | 8/10 vs 5/10, 0.3498 |

**E. Around the LLC boundary: other strides at 8 MB, other sizes at stride 256** (means in ns; "high" = iterations above the two-cluster split of that cell)

| stride | MB | mean kvmoff | mean nvhe | mean vhe | mean pkvm | high k/n/v/p | pkvm - kvmoff ns (rel.) | Welch p | perm p | bootstrap 95 % CI ns | pkvm - vhe rel. | pkvm - nvhe rel. | vhe - kvmoff rel. (Welch p) |
|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|---:|---:|---|
| 128 | 8 | 10.837 | 10.932 | 11.006 | 10.295 | 8/8/8/5 | -0.542 (-5.00 %) | 0.2016 | 0.2159 | [-1.282, +0.251] | -6.46 % | -5.83 % | +1.56 % (0.6502) |
| 256 | 8 | 11.203 | 11.276 | 11.961 | 11.600 | 4/5/8/6 | +0.397 (+3.55 %) | 0.4021 | 0.3995 | [-0.485, +1.239] | -3.02 % | +2.87 % | +6.77 % (0.0817) |
| 512 | 8 | 10.534 | 10.224 | 10.751 | 10.834 | 5/3/5/5 | +0.299 (+2.84 %) | 0.5305 | 0.5937 | [-0.538, +1.136] | +0.77 % | +5.96 % | +2.05 % (0.6322) |
| 1024 | 8 | 11.834 | 11.858 | 12.119 | 11.625 | 7/6/7/5 | -0.210 (-1.77 %) | 0.5985 | 0.6029 | [-0.917, +0.531] | -4.08 % | -1.97 % | +2.41 % (0.4277) |
| 256 | 4 | 5.487 | 5.484 | 5.483 | 5.484 | 6/2/4/3 | -0.004 (-0.07 %) | 0.2118 | 0.2151 | [-0.009, +0.002] | +0.01 % | -0.01 % | -0.08 % (0.0751) |
| 256 | 6 | 8.292 | 8.231 | 8.321 | 8.378 | 2/1/3/5 | +0.086 (+1.03 %) | 0.1783 | 0.1783 | [-0.031, +0.194] | +0.69 % | +1.79 % | +0.34 % (0.5990) |
| 256 | 12 | 10.984 | 10.861 | 11.713 | 11.823 | 0/0/2/3 | +0.839 (+7.64 %) | 0.0632 | 0.0642 | [+0.121, +1.624] | +0.94 % | +8.86 % | +6.64 % (0.0434) |
| 256 | 16 | 10.907 | 10.791 | 11.386 | 11.165 | 6/4/10/9 | +0.258 (+2.37 %) | 0.0585 | 0.0577 | [+0.028, +0.501] | -1.94 % | +3.46 % | +4.39 % (0.0034) |
| 256 | 24 | 10.808 | 10.914 | 11.419 | 11.033 | 1/3/5/1 | +0.225 (+2.08 %) | 0.0756 | 0.0763 | [-0.000, +0.445] | -3.38 % | +1.10 % | +5.65 % (0.0099) |
| 256 | 32 | 10.668 | 10.548 | 11.231 | 10.945 | 1/0/6/1 | +0.277 (+2.60 %) | 0.1481 | 0.1438 | [-0.037, +0.646] | -2.54 % | +3.76 % | +5.27 % (0.0023) |
| 256 | 48 | 10.431 | 10.649 | 10.982 | 10.524 | 3/4/9/3 | +0.093 (+0.89 %) | 0.4143 | 0.4102 | [-0.110, +0.304] | -4.18 % | -1.18 % | +5.29 % (0.0006) |
| 256 | 64 | 10.381 | 10.302 | 10.784 | 10.411 | 3/1/7/3 | +0.030 (+0.29 %) | 0.7697 | 0.7676 | [-0.154, +0.218] | -3.46 % | +1.06 % | +3.88 % (0.0127) |

Per-iteration values of those cells (ns):

| stride | MB | config | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 128 | 8 | kvmoff | 9.131 | 11.184 | 11.207 | 10.951 | 11.180 | 11.231 | 11.332 | 9.808 | 11.204 | 11.141 |
| 128 | 8 | nvhe | 11.439 | 11.426 | 11.341 | 11.281 | 9.366 | 11.334 | 11.411 | 11.232 | 11.394 | 9.095 |
| 128 | 8 | vhe | 11.496 | 11.499 | 11.192 | 11.476 | 11.423 | 11.413 | 9.397 | 11.445 | 11.468 | 9.254 |
| 128 | 8 | pkvm | 11.525 | 11.533 | 9.418 | 11.416 | 9.225 | 10.735 | 11.127 | 9.286 | 9.397 | 9.286 |
| 512 | 8 | kvmoff | 9.530 | 11.584 | 11.425 | 11.403 | 11.485 | 9.466 | 11.636 | 9.556 | 9.609 | 9.651 |
| 512 | 8 | nvhe | 9.680 | 11.695 | 11.620 | 9.518 | 9.570 | 9.524 | 9.464 | 11.528 | 9.625 | 10.018 |
| 512 | 8 | vhe | 9.965 | 11.931 | 11.865 | 11.729 | 11.774 | 9.819 | 9.904 | 9.891 | 10.707 | 9.924 |
| 512 | 8 | pkvm | 9.943 | 9.958 | 9.765 | 9.823 | 11.763 | 11.819 | 12.081 | 9.667 | 11.748 | 11.770 |
| 1024 | 8 | kvmoff | 12.295 | 12.277 | 11.087 | 12.232 | 12.330 | 11.890 | 12.596 | 10.683 | 12.354 | 10.599 |
| 1024 | 8 | nvhe | 11.457 | 11.779 | 10.625 | 12.336 | 12.362 | 12.500 | 12.316 | 11.548 | 12.800 | 10.859 |
| 1024 | 8 | vhe | 11.196 | 12.691 | 12.650 | 10.782 | 12.672 | 12.345 | 12.670 | 12.651 | 10.880 | 12.655 |
| 1024 | 8 | pkvm | 11.940 | 10.650 | 12.644 | 10.641 | 10.734 | 12.684 | 12.619 | 10.735 | 10.838 | 12.761 |
| 256 | 6 | kvmoff | 8.637 | 8.243 | 8.254 | 8.210 | 8.345 | 8.213 | 8.162 | 8.179 | 8.313 | 8.367 |
| 256 | 6 | nvhe | 8.255 | 8.199 | 8.372 | 8.186 | 8.183 | 8.121 | 8.172 | 8.298 | 8.250 | 8.271 |
| 256 | 6 | vhe | 8.288 | 8.287 | 8.422 | 8.453 | 8.342 | 8.435 | 8.177 | 8.290 | 8.303 | 8.210 |
| 256 | 6 | pkvm | 8.201 | 8.297 | 8.303 | 8.386 | 8.290 | 8.583 | 8.472 | 8.265 | 8.388 | 8.594 |
| 256 | 12 | kvmoff | 10.800 | 11.035 | 10.585 | 11.044 | 10.630 | 10.626 | 11.386 | 11.940 | 11.103 | 10.695 |
| 256 | 12 | nvhe | 11.171 | 10.729 | 10.981 | 10.620 | 10.592 | 10.579 | 10.674 | 11.094 | 11.088 | 11.079 |
| 256 | 12 | vhe | 13.777 | 13.069 | 11.251 | 11.271 | 11.303 | 11.120 | 11.285 | 11.139 | 11.773 | 11.147 |
| 256 | 12 | pkvm | 11.113 | 11.064 | 13.386 | 13.711 | 11.133 | 11.059 | 11.334 | 10.964 | 10.856 | 13.611 |
| 256 | 16 | kvmoff | 11.220 | 11.035 | 10.457 | 11.048 | 10.539 | 10.593 | 11.204 | 11.136 | 11.165 | 10.671 |
| 256 | 16 | nvhe | 11.100 | 10.789 | 11.003 | 10.525 | 10.540 | 10.516 | 10.596 | 11.221 | 10.527 | 11.098 |
| 256 | 16 | vhe | 12.104 | 11.171 | 11.240 | 11.423 | 11.442 | 11.187 | 11.422 | 11.751 | 11.056 | 11.064 |
| 256 | 16 | pkvm | 11.060 | 10.980 | 11.735 | 11.243 | 11.236 | 10.967 | 11.392 | 10.947 | 10.837 | 11.255 |

**F. Random access (lat_mem_rd_rand, stride 16): medians and means per configuration, ns**

| MB | pages | median kvmoff | median nvhe | median vhe | median pkvm | mean kvmoff | mean nvhe | mean vhe | mean pkvm |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00049-0.03125 (11 sizes) | 0-8 | 2.223-2.224 in all four | | | | 2.223-2.920 (isolated slow iterations) | | | |
| 0.04688 | 12 | 3.064 | 4.155 | 4.137 | 3.970 | 3.244 | 4.028 | 3.738 | 3.583 |
| 0.0625 | 16 | 3.833 | 4.588 | 4.109 | 4.663 | 4.023 | 4.420 | 4.449 | 4.594 |
| 0.09375 | 24 | 6.025 | 6.251 | 6.250 | 5.963 | 6.128 | 6.059 | 6.190 | 5.969 |
| 0.125 | 32 | 6.726 | 6.622 | 6.691 | 6.744 | 6.706 | 6.573 | 6.638 | 6.688 |
| 0.1875 | 48 | 6.739 | 6.786 | 6.797 | 6.774 | 6.765 | 6.788 | 6.742 | 6.776 |
| 0.25 | 64 | 7.938 | 7.964 | 7.937 | 7.923 | 7.948 | 7.962 | 7.933 | 7.935 |
| 0.375 | 96 | 8.261 | 8.329 | 8.255 | 8.624 | 8.315 | 8.428 | 8.282 | 8.558 |
| 0.5 | 128 | 10.697 | 10.612 | 10.249 | 11.246 | 10.519 | 10.718 | 10.399 | 11.149 |
| 0.75 | 192 | 16.735 | 16.676 | 16.922 | 16.614 | 16.807 | 16.696 | 16.950 | 16.585 |
| 1 | 256 | 19.409 | 19.480 | 19.479 | 19.429 | 19.462 | 19.480 | 19.485 | 19.465 |
| 1.5 | 384 | 20.186 | 20.176 | 20.125 | 20.241 | 20.164 | 20.177 | 20.140 | 20.231 |
| 2 | 512 | 20.677 | 20.752 | 20.733 | 20.883 | 20.691 | 20.735 | 20.721 | 20.926 |
| 3 | 768 | 36.602 | 36.633 | 36.562 | 37.311 | 36.609 | 36.660 | 36.580 | 37.316 |
| 4 | 1024 | 47.587 | 47.688 | 47.455 | 49.314 | 47.702 | 47.656 | 47.505 | 49.311 |
| 6 | 1536 | 67.137 | 67.350 | 67.374 | 72.589 | 67.521 | 68.018 | 67.389 | 72.839 |
| 8 | 2048 | 112.544 | 112.601 | 112.325 | 119.595 | 112.600 | 112.683 | 112.374 | 119.651 |
| 12 | 3072 | 154.651 | 154.810 | 154.647 | 161.678 | 151.347 | 154.484 | 154.709 | 161.637 |
| 16 | 4096 | 168.543 | 168.556 | 169.708 | 176.282 | 159.107 | 168.545 | 167.156 | 176.367 |
| 24 | 6144 | 177.229 | 177.470 | 180.272 | 185.589 | 171.606 | 177.397 | 176.668 | 184.006 |
| 32 | 8192 | 180.613 | 180.776 | 182.721 | 188.659 | 169.763 | 178.555 | 182.762 | 184.964 |
| 48 | 12288 | 182.662 | 182.444 | 183.849 | 189.558 | 176.269 | 178.766 | 182.582 | 188.797 |
| 64 | 16384 | 185.233 | 185.045 | 185.428 | 191.730 | 182.209 | 181.104 | 181.207 | 188.135 |

**G. Random access: pkvm minus baseline, difference of medians** (brackets: 95 % bootstrap CI; perm p: exact permutation test on medians, floor 0.0008; MWU: exact Mann-Whitney; sep.: all 10 pkvm iterations above all 10 kvmoff iterations; noise floor: largest median difference among kvmoff/nvhe/vhe)

| MB | pages | vs kvmoff ns [CI] | rel. | perm p | MWU p | sep. | vs nvhe ns (rel., perm p) | vs vhe ns (rel., perm p) | vs pooled no-stage-2 ns [CI] | noise floor ns |
|---:|---:|---|---:|---:|---:|---|---|---|---|---:|
| 0.00049-0.03125 (11 sizes) | 0-8 | within +/-0.001 | 0.00 % | 1.0000 | >= 0.21 | no | within +/-0.001 | within +/-0.001 | within +/-0.001 | <= 0.001 |
| 0.04688 | 12 | +0.906 [-0.883, +1.982] | +29.59 % | 0.3129 | 0.3110 | no | -0.186 (-4.46 %, 0.3235) | -0.167 (-4.05 %, 0.4171) | -0.092 [-1.838, +0.433] | 1.092 |
| 0.0625 | 16 | +0.831 [-0.160, +1.552] | +21.68 % | 0.0428 | 0.0892 | no | +0.076 (+1.66 %, 0.9846) | +0.554 (+13.49 %, 0.4994) | +0.555 [-0.343, +1.275] | 0.755 |
| 0.09375 | 24 | -0.062 [-0.425, +0.115] | -1.03 % | 0.5705 | 0.5413 | no | -0.288 (-4.60 %, 0.0611) | -0.287 (-4.59 %, 0.0234) | -0.240 [-0.323, +0.063] | 0.226 |
| 0.125 | 32 | +0.018 [-0.070, +0.069] | +0.26 % | 0.6427 | 0.8973 | no | +0.122 (+1.84 %, 0.0944) | +0.053 (+0.78 %, 0.2501) | +0.035 [-0.035, +0.104] | 0.104 |
| 0.1875 | 48 | +0.035 [-0.046, +0.070] | +0.52 % | 0.2348 | 0.4214 | no | -0.011 (-0.17 %, 0.5948) | -0.022 (-0.33 %, 0.6476) | -0.011 [-0.046, +0.054] | 0.058 |
| 0.25 | 64 | -0.014 [-0.059, +0.053] | -0.18 % | 0.5347 | 0.6166 | no | -0.041 (-0.51 %, 0.4190) | -0.014 (-0.17 %, 0.4410) | -0.014 [-0.052, +0.053] | 0.027 |
| 0.375 | 96 | +0.364 [-0.057, +0.651] | +4.41 % | 0.0511 | 0.0753 | no | +0.295 (+3.54 %, 0.1391) | +0.370 (+4.48 %, 0.0170) | +0.353 [+0.079, +0.454] | 0.075 |
| 0.5 | 128 | +0.550 [-0.170, +1.421] | +5.14 % | 0.1218 | 0.1230 | no | +0.634 (+5.97 %, 0.3009) | +0.997 (+9.72 %, 0.0036) | +0.722 [-0.108, +1.199] | 0.447 |
| 0.75 | 192 | -0.121 [-0.459, +0.008] | -0.72 % | 0.0172 | 0.0433 | no | -0.062 (-0.37 %, 0.2655) | -0.308 (-1.82 %, 0.0030) | -0.129 [-0.332, -0.053] | 0.246 |
| 1 | 256 | +0.020 [-0.269, +0.271] | +0.11 % | 0.8295 | 0.8369 | no | -0.051 (-0.26 %, 0.3495) | -0.050 (-0.25 %, 0.4612) | -0.040 [-0.173, +0.203] | 0.071 |
| 1.5 | 384 | +0.055 [+0.010, +0.124] | +0.27 % | 0.0948 | 0.0272 | no | +0.065 (+0.32 %, 0.1574) | +0.116 (+0.58 %, 0.1259) | +0.073 [+0.012, +0.135] | 0.061 |
| 2 | 512 | +0.206 [-0.027, +0.483] | +1.00 % | 0.0432 | 0.0630 | no | +0.131 (+0.63 %, 0.1979) | +0.151 (+0.73 %, 0.1449) | +0.170 [-0.029, +0.474] | 0.075 |
| 3 | 768 | +0.709 [+0.252, +1.084] | +1.94 % | 0.0008 | 4.3e-05 | no | +0.678 (+1.85 %, 0.0008) | +0.749 (+2.05 %, 0.0008) | +0.715 [+0.264, +1.082] | 0.071 |
| 4 | 1024 | +1.727 [+1.230, +2.031] | +3.63 % | 0.0008 | 1.1e-05 | yes | +1.627 (+3.41 %, 0.0008) | +1.859 (+3.92 %, 0.0008) | +1.682 [+1.404, +2.000] | 0.233 |
| 6 | 1536 | +5.452 [+4.407, +6.930] | +8.12 % | 0.0008 | 1.1e-05 | yes | +5.239 (+7.78 %, 0.0008) | +5.215 (+7.74 %, 0.0008) | +5.272 [+4.415, +6.805] | 0.237 |
| 8 | 2048 | +7.050 [+6.273, +7.721] | +6.26 % | 0.0008 | 1.1e-05 | yes | +6.994 (+6.21 %, 0.0011) | +7.270 (+6.47 %, 0.0008) | +7.074 [+6.612, +7.617] | 0.276 |
| 12 | 3072 | +7.026 [+6.584, +7.318] | +4.54 % | 0.0008 | 1.1e-05 | yes | +6.868 (+4.44 %, 0.0008) | +7.030 (+4.55 %, 0.0008) | +7.015 [+6.571, +7.272] | 0.163 |
| 16 | 4096 | +7.739 [+7.487, +33.584] | +4.59 % | 0.0008 | 1.1e-05 | yes | +7.725 (+4.58 %, 0.0008) | +6.574 (+3.87 %, 0.0008) | +7.648 [+7.086, +7.922] | 1.165 |
| 24 | 6144 | +8.360 [+7.816, +21.810] | +4.72 % | 0.0128 | 0.0007 | no | +8.119 (+4.57 %, 0.0032) | +5.317 (+2.95 %, 0.0032) | +8.106 [+7.093, +8.438] | 3.043 |
| 32 | 8192 | +8.047 [+7.331, +35.468] | +4.46 % | 0.0330 | 0.0007 | no | +7.883 (+4.36 %, 0.0063) | +5.938 (+3.25 %, 0.0107) | +7.449 [+6.694, +8.024] | 2.108 |
| 48 | 12288 | +6.896 [+5.561, +24.365] | +3.78 % | 0.0111 | 0.0005 | no | +7.115 (+3.90 %, 0.0108) | +5.709 (+3.11 %, 0.0066) | +6.647 [+5.516, +7.371] | 1.406 |
| 64 | 16384 | +6.497 [-0.085, +15.302] | +3.51 % | 0.0313 | 0.0115 | no | +6.684 (+3.61 %, 0.0445) | +6.302 (+3.40 %, 0.0326) | +6.428 [-0.144, +7.552] | 0.383 |

**H. Random access: pkvm minus baseline, difference of means (the paper estimator)**

| MB | vs kvmoff ns [bootstrap 95 % CI] | rel. [CI] | Welch p | vs nvhe ns (rel., Welch p) | vs vhe ns (rel., Welch p) |
|---:|---|---|---:|---|---|
| 1 | +0.003 [-0.152, +0.156] | +0.01 % [-0.78, +0.80] | 0.9736 | -0.015 (-0.08 %, 0.8354) | -0.020 (-0.10 %, 0.7999) |
| 1.5 | +0.067 [+0.003, +0.132] | +0.33 % [+0.02, +0.66] | 0.0683 | +0.054 (+0.27 %, 0.2031) | +0.091 (+0.45 %, 0.0286) |
| 2 | +0.236 [+0.038, +0.444] | +1.14 % [+0.18, +2.16] | 0.0494 | +0.192 (+0.93 %, 0.0942) | +0.206 (+0.99 %, 0.1222) |
| 3 | +0.708 [+0.440, +0.984] | +1.93 % [+1.20, +2.69] | 0.0008 | +0.656 (+1.79 %, 0.0014) | +0.736 (+2.01 %, 0.0005) |
| 4 | +1.609 [+1.331, +1.889] | +3.37 % [+2.79, +3.97] | 2.7e-08 | +1.655 (+3.47 %, 2.1e-08) | +1.806 (+3.80 %, 8.8e-09) |
| 6 | +5.318 [+4.544, +6.100] | +7.88 % [+6.70, +9.07] | 1.2e-09 | +4.821 (+7.09 %, 2.9e-06) | +5.449 (+8.09 %, 2.9e-09) |
| 8 | +7.051 [+6.618, +7.495] | +6.26 % [+5.87, +6.66] | 8.6e-16 | +6.969 (+6.18 %, 3.8e-14) | +7.277 (+6.48 %, 1.0e-12) |
| 12 | +10.290 [+6.793, +17.027] | +6.80 % [+4.39, +11.77] | 0.0128 | +7.152 (+4.63 %, 3.8e-09) | +6.927 (+4.48 %, 1.9e-19) |
| 16 | +17.260 [+7.911, +27.145] | +10.85 % [+4.69, +18.20] | 0.0069 | +7.822 (+4.64 %, 5.4e-18) | +9.211 (+5.51 %, 0.0053) |
| 24 | +12.400 [+5.313, +20.455] | +7.23 % [+3.00, +12.48] | 0.0102 | +6.609 (+3.73 %, 0.0028) | +7.338 (+4.15 %, 0.0956) |
| 32 | +15.202 [+3.803, +26.712] | +8.95 % [+2.15, +16.55] | 0.0279 | +6.409 (+3.59 %, 0.1437) | +2.202 (+1.21 %, 0.5692) |
| 48 | +12.529 [+5.846, +20.564] | +7.11 % [+3.20, +12.19] | 0.0113 | +10.031 (+5.61 %, 0.0020) | +6.215 (+3.40 %, 0.0012) |
| 64 | +5.926 [-0.741, +11.752] | +3.25 % [-0.40, +6.56] | 0.0979 | +7.030 (+3.88 %, 0.0721) | +6.928 (+3.82 %, 0.0891) |

**I. Random access, main mode only** (per configuration and size, iterations with |x - median| > max(3.5 x 1.4826 x MAD, 1 % of median) removed)

| MB | kept kvmoff/nvhe/vhe/pkvm | main-mode mean kvmoff | nvhe | vhe | pkvm | pkvm - kvmoff ns [Welch 95 % CI] | rel. | Welch p | pkvm - nvhe ns (rel.) | pkvm - vhe ns (rel.) |
|---:|---|---:|---:|---:|---:|---|---:|---:|---|---|
| 1 | 10/9/9/10 | 19.462 | 19.515 | 19.532 | 19.465 | +0.003 [-0.172, +0.178] | +0.01 % | 0.9736 | -0.050 (-0.25 %) | -0.066 (-0.34 %) |
| 1.5 | 10/10/10/10 | 20.164 | 20.177 | 20.140 | 20.231 | +0.067 [-0.006, +0.139] | +0.33 % | 0.0683 | +0.054 (+0.27 %) | +0.091 (+0.45 %) |
| 2 | 10/10/10/10 | 20.691 | 20.735 | 20.721 | 20.926 | +0.236 [+0.001, +0.470] | +1.14 % | 0.0494 | +0.192 (+0.93 %) | +0.206 (+0.99 %) |
| 3 | 10/10/10/10 | 36.609 | 36.660 | 36.580 | 37.316 | +0.708 [+0.377, +1.039] | +1.93 % | 0.0008 | +0.656 (+1.79 %) | +0.736 (+2.01 %) |
| 4 | 10/9/10/10 | 47.702 | 47.720 | 47.505 | 49.311 | +1.609 [+1.288, +1.930] | +3.37 % | 2.7e-08 | +1.591 (+3.33 %) | +1.806 (+3.80 %) |
| 6 | 8/9/10/10 | 67.191 | 67.514 | 67.389 | 72.839 | +5.648 [+4.844, +6.451] | +8.41 % | 1.8e-08 | +5.325 (+7.89 %) | +5.449 (+8.09 %) |
| 8 | 10/10/10/10 | 112.600 | 112.683 | 112.374 | 119.651 | +7.051 [+6.549, +7.554] | +6.26 % | 8.6e-16 | +6.969 (+6.18 %) | +7.277 (+6.48 %) |
| 12 | 9/9/10/10 | 154.670 | 154.867 | 154.709 | 161.637 | +6.967 [+6.691, +7.243] | +4.50 % | 6.1e-16 | +6.770 (+4.37 %) | +6.927 (+4.48 %) |
| 16 | 7/10/9/10 | 168.710 | 168.545 | 169.676 | 176.367 | +7.657 [+7.266, +8.047] | +4.54 % | 6.6e-17 | +7.822 (+4.64 %) | +6.690 (+3.94 %) |
| 24 | 8/10/9/9 | 177.213 | 177.397 | 180.394 | 185.623 | +8.409 [+7.786, +9.033] | +4.75 % | 2.6e-12 | +8.225 (+4.64 %) | +5.228 (+2.90 %) |
| 32 | 6/8/10/9 | 181.062 | 180.952 | 182.762 | 188.688 | +7.626 [+7.132, +8.119] | +4.21 % | 1.1e-11 | +7.736 (+4.27 %) | +5.926 (+3.24 %) |
| 48 | 7/7/9/9 | 183.453 | 183.357 | 183.890 | 189.617 | +6.164 [+4.908, +7.421] | +3.36 % | 5.7e-06 | +6.260 (+3.41 %) | +5.727 (+3.11 %) |
| 64 | 7/7/7/8 | 185.798 | 185.592 | 185.741 | 192.014 | +6.216 [+5.461, +6.972] | +3.35 % | 2.4e-10 | +6.422 (+3.46 %) | +6.274 (+3.38 %) |

**J. Random access: flagged iterations, sizes >= 3 MB, CONFIG.host** (same rule as in I; deviation relative to the configuration median)

| config | MB | median ns | flagged iterations |
|---|---:|---:|---|
| kvmoff | 6 | 67.137 | it5 68.588 (+2.2 %); it10 69.092 (+2.9 %) |
| kvmoff | 12 | 154.651 | it2 121.440 (-21.5 %) |
| kvmoff | 16 | 168.543 | it2 132.412 (-21.4 %); it7 134.863 (-20.0 %); it8 142.820 (-15.3 %) |
| kvmoff | 24 | 177.229 | it6 147.557 (-16.7 %); it9 150.796 (-14.9 %) |
| kvmoff | 32 | 180.613 | it1 142.316 (-21.2 %); it2 143.035 (-20.8 %); it4 162.606 (-10.0 %); it9 163.301 (-9.6 %) |
| kvmoff | 48 | 182.662 | it1 165.387 (-9.5 %); it5 164.641 (-9.9 %); it9 148.491 (-18.7 %) |
| kvmoff | 64 | 185.233 | it1 176.314 (-4.8 %); it3 168.704 (-8.9 %); it6 176.485 (-4.7 %) |
| nvhe | 4 | 47.688 | it5 47.081 (-1.3 %) |
| nvhe | 6 | 67.350 | it8 72.559 (+7.7 %) |
| nvhe | 12 | 154.810 | it5 151.043 (-2.4 %) |
| nvhe | 32 | 180.776 | it5 164.302 (-9.1 %); it6 173.633 (-4.0 %) |
| nvhe | 48 | 182.444 | it2 166.607 (-8.7 %); it5 167.984 (-7.9 %); it10 169.573 (-7.1 %) |
| nvhe | 64 | 185.045 | it3 164.520 (-11.1 %); it6 172.185 (-6.9 %); it7 175.195 (-5.3 %) |
| vhe | 16 | 169.708 | it4 144.468 (-14.9 %) |
| vhe | 24 | 180.272 | it5 143.129 (-20.6 %) |
| vhe | 48 | 183.849 | it5 170.811 (-7.1 %) |
| vhe | 64 | 185.428 | it4 175.439 (-5.4 %); it8 159.877 (-13.8 %); it10 176.568 (-4.8 %) |
| pkvm | 24 | 185.589 | it6 169.459 (-8.7 %) |
| pkvm | 32 | 188.659 | it6 151.455 (-19.7 %) |
| pkvm | 48 | 189.558 | it8 181.423 (-4.3 %) |
| pkvm | 64 | 191.730 | it6 166.436 (-13.2 %); it10 178.793 (-6.7 %) |

Standalone campaign, flagged runs (random access at 4/8/16/32/64 MB):

| config | MB | median ns | flagged runs |
|---|---:|---:|---|
| kvmoff | 16 | 169.798 | run3 167.891 (-1.1 %) |
| kvmoff | 32 | 181.552 | run6 151.342 (-16.6 %) |
| kvmoff | 64 | 185.320 | run9 169.476 (-8.5 %) |
| nvhe | 64 | 186.046 | run4 180.565 (-2.9 %) |
| vhe | 16 | 169.724 | run10 134.475 (-20.8 %) |
| vhe | 32 | 180.818 | run8 154.886 (-14.3 %) |
| vhe | 64 | 185.553 | run1 178.802 (-3.6 %); run9 176.844 (-4.7 %); run10 178.377 (-3.9 %) |
| pkvm | 8 | 120.005 | run10 104.114 (-13.2 %) |
| pkvm | 16 | 176.719 | run3 140.372 (-20.6 %) |
| pkvm | 32 | 189.575 | run1 180.844 (-4.6 %); run2 178.014 (-6.1 %); run8 174.861 (-7.8 %) |
| pkvm | 64 | 192.412 | run7 181.290 (-5.8 %); run8 178.197 (-7.4 %) |

**K. The fast state: the extra nVHE session "nvhe-noisy" (no host stage-2) against the clean sessions, random access medians in ns**

| MB | pages | kvmoff | nvhe | vhe | pkvm | nvhe-noisy | clean no-stage-2 minus nvhe-noisy | nvhe-noisy rel. to clean | pkvm minus clean no-stage-2 | fastest single iteration in the clean sessions |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 256 | 19.409 | 19.480 | 19.479 | 19.429 | 19.045 | +0.434 | -2.2 % | -0.050 | 19.068 (vhe) |
| 2 | 512 | 20.677 | 20.752 | 20.733 | 20.883 | 21.100 | -0.367 | +1.8 % | +0.151 | 20.341 (kvmoff) |
| 3 | 768 | 36.602 | 36.633 | 36.562 | 37.311 | 26.413 | +10.189 | -27.8 % | +0.709 | 36.295 (nvhe) |
| 4 | 1024 | 47.587 | 47.688 | 47.455 | 49.314 | 30.800 | +16.787 | -35.3 % | +1.727 | 47.081 (nvhe) |
| 6 | 1536 | 67.137 | 67.350 | 67.374 | 72.589 | 48.614 | +18.736 | -27.8 % | +5.239 | 66.540 (nvhe) |
| 8 | 2048 | 112.544 | 112.601 | 112.325 | 119.595 | 83.900 | +28.645 | -25.5 % | +7.050 | 112.041 (kvmoff) |
| 12 | 3072 | 154.651 | 154.810 | 154.647 | 161.678 | 121.820 | +32.832 | -21.2 % | +7.026 | 121.440 (kvmoff) |
| 16 | 4096 | 168.543 | 168.556 | 169.708 | 176.282 | 134.226 | +34.331 | -20.4 % | +7.725 | 132.412 (kvmoff) |
| 24 | 6144 | 177.229 | 177.470 | 180.272 | 185.589 | 143.077 | +34.393 | -19.4 % | +8.119 | 143.129 (vhe) |
| 32 | 8192 | 180.613 | 180.776 | 182.721 | 188.659 | 146.201 | +34.576 | -19.1 % | +7.883 | 142.316 (kvmoff) |
| 48 | 12288 | 182.662 | 182.444 | 183.849 | 189.558 | 149.101 | +33.561 | -18.4 % | +6.896 | 148.491 (kvmoff) |
| 64 | 16384 | 185.233 | 185.045 | 185.428 | 191.730 | 150.123 | +35.110 | -19.0 % | +6.497 | 159.877 (vhe) |

**L. Sequential access versus stride** (x = stride/4096 = page crossings per access; d = difference of means in ns; brackets: 95 % bootstrap CI; d/x = implied extra cost per page crossing)

| MB | stride | x | mean kvmoff | mean nvhe | mean vhe | mean pkvm | pkvm - kvmoff d [CI] | rel. | Welch p | d/x ns | pkvm - nvhe d (rel.) | pkvm - vhe d (rel.) | vhe - kvmoff d (rel.) |
|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---|
| 64 | 16 | 0.0039 | 2.318 | 2.320 | 2.312 | 2.317 | -0.000 [-0.004, +0.003] | -0.01 % | 0.8870 | -0.08 | -0.002 (-0.09 %) | +0.005 (+0.22 %) | -0.005 (-0.23 %) |
| 64 | 32 | 0.0078 | 2.674 | 2.678 | 2.702 | 2.677 | +0.003 [-0.003, +0.010] | +0.12 % | 0.4071 | +0.40 | -0.001 (-0.03 %) | -0.025 (-0.93 %) | +0.028 (+1.05 %) |
| 64 | 64 | 0.0156 | 4.216 | 4.224 | 4.523 | 4.267 | +0.050 [+0.034, +0.066] | +1.20 % | 2.2e-05 | +3.23 | +0.043 (+1.01 %) | -0.257 (-5.67 %) | +0.307 (+7.28 %) |
| 64 | 128 | 0.0312 | 8.999 | 9.022 | 9.449 | 9.175 | +0.175 [+0.081, +0.268] | +1.95 % | 0.0026 | +5.61 | +0.152 (+1.69 %) | -0.275 (-2.91 %) | +0.450 (+5.00 %) |
| 64 | 256 | 0.0625 | 10.381 | 10.302 | 10.784 | 10.411 | +0.030 [-0.151, +0.217] | +0.29 % | 0.7697 | +0.47 | +0.109 (+1.06 %) | -0.373 (-3.46 %) | +0.402 (+3.88 %) |
| 64 | 512 | 0.1250 | 9.604 | 9.526 | 9.946 | 9.865 | +0.262 [+0.106, +0.488] | +2.73 % | 0.0304 | +2.10 | +0.340 (+3.57 %) | -0.081 (-0.81 %) | +0.343 (+3.57 %) |
| 64 | 1024 | 0.2500 | 10.515 | 10.635 | 11.087 | 10.883 | +0.368 [+0.273, +0.458] | +3.50 % | 9.6e-07 | +1.47 | +0.248 (+2.33 %) | -0.203 (-1.83 %) | +0.571 (+5.43 %) |
| 32 | 16 | 0.0039 | 2.314 | 2.315 | 2.308 | 2.311 | -0.003 [-0.007, +0.002] | -0.13 % | 0.2356 | -0.74 | -0.004 (-0.16 %) | +0.003 (+0.13 %) | -0.006 (-0.25 %) |
| 32 | 32 | 0.0078 | 2.677 | 2.683 | 2.712 | 2.686 | +0.008 [+0.000, +0.016] | +0.31 % | 0.0681 | +1.08 | +0.003 (+0.12 %) | -0.027 (-0.98 %) | +0.035 (+1.31 %) |
| 32 | 64 | 0.0156 | 4.284 | 4.284 | 4.654 | 4.367 | +0.082 [+0.059, +0.106] | +1.92 % | 7.1e-06 | +5.27 | +0.083 (+1.93 %) | -0.287 (-6.17 %) | +0.370 (+8.63 %) |
| 32 | 128 | 0.0312 | 9.298 | 9.287 | 9.912 | 9.468 | +0.170 [+0.014, +0.325] | +1.83 % | 0.0594 | +5.45 | +0.181 (+1.95 %) | -0.444 (-4.48 %) | +0.614 (+6.61 %) |
| 32 | 256 | 0.0625 | 10.668 | 10.548 | 11.231 | 10.945 | +0.277 [-0.037, +0.639] | +2.60 % | 0.1481 | +4.43 | +0.397 (+3.76 %) | -0.285 (-2.54 %) | +0.562 (+5.27 %) |
| 32 | 512 | 0.1250 | 9.758 | 9.701 | 10.432 | 10.128 | +0.370 [+0.234, +0.529] | +3.79 % | 0.0004 | +2.96 | +0.427 (+4.40 %) | -0.304 (-2.91 %) | +0.674 (+6.91 %) |
| 32 | 1024 | 0.2500 | 10.762 | 10.773 | 11.698 | 11.405 | +0.643 [+0.454, +0.844] | +5.98 % | 3.1e-05 | +2.57 | +0.632 (+5.86 %) | -0.293 (-2.51 %) | +0.936 (+8.70 %) |
| 16 | 16 | 0.0039 | 2.308 | 2.310 | 2.310 | 2.307 | -0.001 [-0.003, +0.001] | -0.06 % | 0.2093 | -0.36 | -0.003 (-0.14 %) | -0.003 (-0.12 %) | +0.001 (+0.06 %) |
| 16 | 32 | 0.0078 | 2.671 | 2.673 | 2.724 | 2.689 | +0.018 [+0.012, +0.026] | +0.69 % | 0.0004 | +2.36 | +0.016 (+0.59 %) | -0.035 (-1.28 %) | +0.053 (+1.99 %) |
| 16 | 64 | 0.0156 | 4.316 | 4.323 | 4.722 | 4.456 | +0.140 [+0.111, +0.171] | +3.25 % | 8.4e-08 | +8.97 | +0.134 (+3.09 %) | -0.266 (-5.63 %) | +0.406 (+9.41 %) |
| 16 | 128 | 0.0312 | 9.501 | 9.782 | 10.180 | 9.800 | +0.298 [+0.153, +0.441] | +3.14 % | 0.0011 | +9.55 | +0.018 (+0.18 %) | -0.380 (-3.73 %) | +0.678 (+7.14 %) |
| 16 | 256 | 0.0625 | 10.907 | 10.791 | 11.386 | 11.165 | +0.258 [+0.030, +0.505] | +2.37 % | 0.0585 | +4.13 | +0.374 (+3.46 %) | -0.221 (-1.94 %) | +0.479 (+4.39 %) |
| 16 | 512 | 0.1250 | 10.108 | 10.034 | 10.824 | 10.613 | +0.505 [+0.296, +0.732] | +4.99 % | 0.0006 | +4.04 | +0.579 (+5.77 %) | -0.211 (-1.95 %) | +0.716 (+7.09 %) |
| 16 | 1024 | 0.2500 | 11.323 | 11.237 | 12.677 | 11.973 | +0.650 [+0.375, +0.918] | +5.74 % | 0.0003 | +2.60 | +0.735 (+6.54 %) | -0.704 (-5.56 %) | +1.354 (+11.96 %) |

**M. Sequential access: least-squares slope of the per-stride difference of means on x, in ns per page crossing [95 % bootstrap CI], next to the random-access difference of medians per access at the same size**

| MB | pair | slope, weighted (1/se^2), through origin | slope, unweighted, through origin | slope, unweighted, with intercept | Spearman rho of d vs stride (exact p) | random access: d(median) per access, ns |
|---:|---|---|---|---|---|---:|
| 64 | pkvm - kvmoff | +1.40 [+1.11, +1.71] | +1.59 [+1.19, +2.06] | +1.45 [+1.03, +1.88] | +0.89 (0.0123) | +6.50 |
| 64 | pkvm - nvhe | +1.08 [+0.64, +1.50] | +1.40 [+0.73, +2.03] | +1.11 [+0.33, +1.81] | +0.93 (0.0067) | +6.68 |
| 64 | pkvm - vhe | -0.46 [-0.85, -0.10] | -1.16 [-1.66, -0.62] | -0.24 [-0.84, +0.44] | -0.46 (0.3024) | +6.30 |
| 64 | nvhe - kvmoff | -0.01 [-0.33, +0.33] | +0.19 [-0.39, +0.83] | +0.34 [-0.34, +1.12] | +0.14 (0.7825) | -0.19 |
| 64 | vhe - kvmoff | +1.88 [+1.56, +2.22] | +2.76 [+2.32, +3.22] | +1.69 [+1.04, +2.32] | +0.86 (0.0238) | +0.20 |
| 64 | nvhe-noisy - kvmoff | +5.56 [+5.34, +5.77] | +6.55 [+6.26, +6.84] | +5.09 [+4.75, +5.40] | +0.96 (0.0028) | -35.11 |
| 32 | pkvm - kvmoff | +2.06 [+1.60, +2.53] | +2.77 [+2.13, +3.50] | +2.52 [+1.76, +3.27] | +1.00 (0.0004) | +8.05 |
| 32 | pkvm - nvhe | +2.08 [+1.64, +2.50] | +2.92 [+2.26, +3.63] | +2.52 [+1.79, +3.29] | +1.00 (0.0004) | +7.88 |
| 32 | pkvm - vhe | -0.79 [-1.39, -0.17] | -1.77 [-2.75, -0.88] | -0.66 [-1.85, +0.46] | -0.68 (0.1095) | +5.94 |
| 32 | nvhe - kvmoff | +0.00 [-0.32, +0.33] | -0.14 [-0.59, +0.29] | +0.00 [-0.50, +0.50] | -0.18 (0.7131) | +0.16 |
| 32 | vhe - kvmoff | +2.87 [+2.38, +3.36] | +4.54 [+3.82, +5.40] | +3.17 [+2.22, +4.23] | +0.96 (0.0028) | +2.11 |
| 32 | nvhe-noisy - kvmoff | +5.31 [+5.02, +5.61] | +6.39 [+6.00, +6.78] | +5.31 [+4.87, +5.75] | +0.96 (0.0028) | -34.41 |
| 16 | pkvm - kvmoff | +1.22 [+0.83, +1.62] | +3.04 [+2.14, +3.92] | +2.51 [+1.45, +3.55] | +0.96 (0.0028) | +7.74 |
| 16 | pkvm - nvhe | +1.61 [+1.18, +2.06] | +3.39 [+2.63, +4.20] | +3.14 [+2.23, +4.10] | +0.96 (0.0028) | +7.73 |
| 16 | pkvm - vhe | -0.85 [-1.23, -0.46] | -2.79 [-4.66, -1.11] | -2.15 [-4.60, -0.08] | -0.68 (0.1095) | +6.57 |
| 16 | nvhe - kvmoff | +0.14 [-0.28, +0.55] | -0.35 [-1.21, +0.50] | -0.62 [-1.67, +0.38] | -0.54 (0.2357) | +0.01 |
| 16 | vhe - kvmoff | +1.25 [+0.79, +1.70] | +5.83 [+4.10, +7.78] | +4.66 [+2.54, +7.08] | +0.96 (0.0028) | +1.16 |
| 16 | nvhe-noisy - kvmoff | +3.68 [+3.39, +3.96] | +5.41 [+4.69, +6.04] | +4.11 [+3.26, +4.87] | +0.96 (0.0028) | -34.32 |

**N. Standalone campaign: per-run values in ns** (`results/standalone-mem-bench/standalone-*.log`, run 1..10 in file order)

| metric | config | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | mean | median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| seq s256 8 MB | kvmoff | 10.087 | 10.197 | 12.383 | 10.158 | 10.092 | 12.529 | 11.719 | 12.441 | 12.469 | 12.389 | 11.446 | 12.051 |
| seq s256 8 MB | nvhe | 12.593 | 12.552 | 10.267 | 10.323 | 12.558 | 12.571 | 12.308 | 12.513 | 10.221 | 12.630 | 11.854 | 12.532 |
| seq s256 8 MB | vhe | 10.121 | 12.975 | 10.565 | 13.074 | 10.138 | 11.691 | 12.378 | 12.435 | 12.910 | 12.490 | 11.878 | 12.407 |
| seq s256 8 MB | pkvm | 12.257 | 12.472 | 10.058 | 12.497 | 12.438 | 12.561 | 10.105 | 10.140 | 12.511 | 10.165 | 11.520 | 12.348 |
| seq s256 64 MB | kvmoff | 10.305 | 10.399 | 10.396 | 10.504 | 10.461 | 10.379 | 10.724 | 10.543 | 10.356 | 10.641 | 10.471 | 10.430 |
| seq s256 64 MB | nvhe | 10.393 | 10.365 | 10.459 | 10.604 | 10.451 | 10.533 | 10.471 | 10.535 | 10.503 | 10.514 | 10.483 | 10.487 |
| seq s256 64 MB | vhe | 11.278 | 10.610 | 10.475 | 11.444 | 10.347 | 10.516 | 10.381 | 10.390 | 10.478 | 10.659 | 10.658 | 10.497 |
| seq s256 64 MB | pkvm | 10.346 | 10.381 | 10.385 | 10.529 | 10.500 | 11.619 | 10.624 | 10.495 | 10.524 | 10.470 | 10.587 | 10.497 |
| rand s16 4 MB | kvmoff | 47.580 | 47.520 | 47.881 | 47.735 | 47.666 | 47.364 | 47.929 | 47.779 | 47.261 | 48.226 | 47.694 | 47.700 |
| rand s16 4 MB | nvhe | 47.929 | 47.429 | 47.224 | 47.563 | 47.199 | 47.073 | 47.060 | 47.364 | 48.043 | 47.647 | 47.453 | 47.397 |
| rand s16 4 MB | vhe | 47.417 | 48.045 | 47.293 | 47.303 | 47.990 | 47.577 | 47.674 | 47.276 | 47.352 | 47.568 | 47.550 | 47.492 |
| rand s16 4 MB | pkvm | 49.826 | 49.535 | 49.654 | 49.214 | 49.906 | 49.878 | 49.662 | 49.521 | 50.094 | 49.884 | 49.717 | 49.744 |
| rand s16 8 MB | kvmoff | 112.912 | 113.956 | 113.165 | 113.200 | 112.577 | 112.545 | 112.178 | 112.884 | 113.129 | 112.604 | 112.915 | 112.898 |
| rand s16 8 MB | nvhe | 112.609 | 112.712 | 112.211 | 113.483 | 112.347 | 112.909 | 112.479 | 112.805 | 113.473 | 112.687 | 112.771 | 112.700 |
| rand s16 8 MB | vhe | 112.247 | 112.326 | 113.007 | 112.659 | 112.496 | 113.191 | 112.411 | 112.772 | 112.913 | 112.487 | 112.651 | 112.578 |
| rand s16 8 MB | pkvm | 120.207 | 120.493 | 119.794 | 120.484 | 119.804 | 119.750 | 120.669 | 120.487 | 119.748 | 104.114 | 118.555 | 120.005 |
| rand s16 16 MB | kvmoff | 169.493 | 169.868 | 167.891 | 169.728 | 169.491 | 169.693 | 169.897 | 170.352 | 170.124 | 170.090 | 169.663 | 169.798 |
| rand s16 16 MB | nvhe | 169.531 | 169.830 | 170.258 | 170.332 | 169.525 | 169.785 | 169.914 | 170.136 | 170.124 | 169.928 | 169.936 | 169.921 |
| rand s16 16 MB | vhe | 168.053 | 169.533 | 169.318 | 169.493 | 170.462 | 170.049 | 170.578 | 169.915 | 170.105 | 134.475 | 166.198 | 169.724 |
| rand s16 16 MB | pkvm | 175.726 | 176.306 | 140.372 | 177.754 | 176.938 | 176.990 | 177.353 | 177.199 | 176.376 | 176.500 | 173.151 | 176.719 |
| rand s16 32 MB | kvmoff | 181.298 | 181.805 | 181.902 | 182.135 | 180.634 | 151.342 | 181.823 | 181.148 | 181.808 | 180.580 | 178.447 | 181.552 |
| rand s16 32 MB | nvhe | 181.832 | 180.237 | 181.099 | 182.593 | 182.617 | 181.810 | 182.438 | 181.612 | 181.269 | 182.201 | 181.771 | 181.821 |
| rand s16 32 MB | vhe | 180.545 | 180.908 | 181.054 | 179.697 | 182.301 | 180.728 | 180.300 | 154.886 | 181.778 | 181.376 | 178.357 | 180.818 |
| rand s16 32 MB | pkvm | 180.844 | 178.014 | 190.006 | 189.893 | 189.681 | 190.033 | 189.468 | 174.861 | 189.408 | 189.720 | 186.193 | 189.575 |
| rand s16 64 MB | kvmoff | 185.755 | 186.475 | 186.157 | 185.989 | 184.781 | 184.807 | 185.648 | 184.992 | 169.476 | 184.721 | 183.880 | 185.320 |
| rand s16 64 MB | nvhe | 186.355 | 185.524 | 186.552 | 180.565 | 186.402 | 185.788 | 186.008 | 185.707 | 186.573 | 186.083 | 185.556 | 186.046 |
| rand s16 64 MB | vhe | 178.802 | 186.596 | 186.063 | 185.607 | 185.498 | 186.538 | 186.156 | 184.360 | 176.844 | 178.377 | 183.484 | 185.553 |
| rand s16 64 MB | pkvm | 191.975 | 192.599 | 192.577 | 192.581 | 192.318 | 192.899 | 181.290 | 178.197 | 192.506 | 191.446 | 189.839 | 192.412 |

**O. Standalone campaign: pkvm minus baseline** (d(mean) with Welch p; d(median) with 95 % bootstrap CI and exact permutation p)

| metric | baseline | d(mean) ns (rel.) | Welch p | d(median) ns (rel.) | bootstrap 95 % CI of d(median) | perm p (medians) | MWU p |
|---|---|---|---:|---|---|---:|---:|
| seq s256 8 MB | kvmoff | +0.074 (+0.65 %) | 0.8902 | +0.297 (+2.46 %) | [-2.249, +2.297] | 0.8515 | 0.6842 |
| seq s256 8 MB | nvhe | -0.333 (-2.81 %) | 0.5271 | -0.185 (-1.48 %) | [-2.412, +2.024] | 0.4779 | 0.0753 |
| seq s256 8 MB | vhe | -0.357 (-3.01 %) | 0.5122 | -0.059 (-0.48 %) | [-2.492, +1.783] | 0.9576 | 0.5288 |
| seq s256 64 MB | kvmoff | +0.117 (+1.11 %) | 0.3705 | +0.067 (+0.65 %) | [-0.098, +0.145] | 0.4418 | 0.6305 |
| seq s256 64 MB | nvhe | +0.104 (+1.00 %) | 0.4039 | +0.010 (+0.10 %) | [-0.104, +0.090] | 0.9318 | 1.0000 |
| seq s256 64 MB | vhe | -0.070 (-0.66 %) | 0.6821 | +0.000 (+0.00 %) | [-0.444, +0.116] | 0.9999 | 0.7552 |
| rand s16 4 MB | kvmoff | +2.023 (+4.24 %) | 2.3e-12 | +2.044 (+4.28 %) | [+1.772, +2.331] | 0.0008 | 1.1e-05 |
| rand s16 4 MB | nvhe | +2.264 (+4.77 %) | 7.2e-12 | +2.347 (+4.95 %) | [+1.972, +2.666] | 0.0008 | 1.1e-05 |
| rand s16 4 MB | vhe | +2.168 (+4.56 %) | 6.5e-13 | +2.252 (+4.74 %) | [+1.920, +2.538] | 0.0008 | 1.1e-05 |
| rand s16 8 MB | kvmoff | +5.640 (+4.99 %) | 0.0066 | +7.108 (+6.30 %) | [+6.630, +7.880] | 0.0045 | 0.0015 |
| rand s16 8 MB | nvhe | +5.784 (+5.13 %) | 0.0058 | +7.306 (+6.48 %) | [+6.885, +7.901] | 0.0040 | 0.0015 |
| rand s16 8 MB | vhe | +5.904 (+5.24 %) | 0.0051 | +7.428 (+6.60 %) | [+6.915, +8.001] | 0.0036 | 0.0015 |
| rand s16 16 MB | kvmoff | +3.489 (+2.06 %) | 0.3644 | +6.921 (+4.08 %) | [+6.269, +7.497] | 0.0036 | 0.0015 |
| rand s16 16 MB | nvhe | +3.215 (+1.89 %) | 0.4010 | +6.798 (+4.00 %) | [+6.144, +7.334] | 0.0030 | 0.0015 |
| rand s16 16 MB | vhe | +6.953 (+4.18 %) | 0.1877 | +6.995 (+4.12 %) | [+6.216, +7.890] | 0.0036 | 0.0011 |
| rand s16 32 MB | kvmoff | +7.745 (+4.34 %) | 0.0452 | +8.023 (+4.42 %) | [-0.963, +8.968] | 0.0362 | 0.0630 |
| rand s16 32 MB | nvhe | +4.422 (+2.43 %) | 0.0422 | +7.754 (+4.26 %) | [-1.291, +8.403] | 0.0275 | 0.1230 |
| rand s16 32 MB | vhe | +7.835 (+4.39 %) | 0.0266 | +8.757 (+4.84 %) | [-0.137, +9.469] | 0.0211 | 0.0433 |
| rand s16 64 MB | kvmoff | +5.959 (+3.24 %) | 0.0205 | +7.092 (+3.83 %) | [+1.561, +7.774] | 0.0170 | 0.0147 |
| rand s16 64 MB | nvhe | +4.283 (+2.31 %) | 0.0361 | +6.367 (+3.42 %) | [+0.661, +6.829] | 0.0090 | 0.0185 |
| rand s16 64 MB | vhe | +6.355 (+3.46 %) | 0.0078 | +6.859 (+3.70 %) | [+1.703, +13.651] | 0.0359 | 0.0089 |

Standalone, main mode only, pkvm - kvmoff (Welch 95 % CI): rand 4 MB +2.023 [+1.771, +2.276]; 8 MB +7.245 [+6.820, +7.670]; 16 MB +6.934 [+6.432, +7.436]; 32 MB +8.285 [+7.821, +8.749]; 64 MB +6.882 [+6.294, +7.471]; seq s256 64 MB +0.002 [-0.107, +0.111].

**P. Session-level analysis** (one median per boot session; no-stage-2 sessions = kvmoff, nvhe, vhe in CONFIG.host and in standalone = 6; pkvm sessions = 2; Student t with 6 df; the exact permutation test over the 28 ways of labelling 2 of 8 sessions cannot go below 0.0357)

| metric | no-stage-2 session medians (CONFIG.host k/n/v; standalone k/n/v) | sd between sessions | pkvm session medians (CONFIG.host; standalone) | pkvm minus no-stage-2, ns (rel.) | in sd units | t(6), p | session permutation p | both pkvm sessions outside the no-stage-2 range | same with session means: ns (rel.), p |
|---|---|---:|---|---|---:|---|---:|---|---|
| seq s256 8MB (LLC Bnd) | 10.815 / 11.410 / 12.447; 12.051 / 12.532 / 12.407 | 0.691 | 12.123; 12.348 | +0.292 (+2.44 %) | 0.4 | 0.56, 0.5935 | 0.7500 | no | -0.043 (-0.37 %), 0.8698 |
| seq s256 64MB (Main Mem) | 10.357 / 10.241 / 10.781; 10.430 / 10.487 / 10.497 | 0.181 | 10.345; 10.497 | -0.045 (-0.43 %) | 0.2 | -0.32, 0.7612 | 0.7857 | no | -0.014 (-0.13 %), 0.9234 |
| rand s16 4MB | 47.587 / 47.688 / 47.455; 47.700 / 47.397 / 47.492 | 0.126 | 49.314; 49.744 | +1.976 (+4.15 %) | 15.7 | 14.32, 7.2e-06 | 0.0357 | yes | +1.921 (+4.04 %), 4.5e-06 |
| rand s16 8MB | 112.544 / 112.601 / 112.325; 112.898 / 112.700 / 112.578 | 0.188 | 119.595; 120.005 | +7.193 (+6.39 %) | 38.2 | 42.17, 1.2e-08 | 0.0357 | yes | +6.437 (+5.71 %), 5.6e-07 |
| rand s16 16MB | 168.543 / 168.556 / 169.708; 169.798 / 169.921 / 169.724 | 0.644 | 176.282; 176.719 | +7.125 (+4.21 %) | 11.1 | 14.52, 6.7e-06 | 0.0357 | yes | +7.992 (+4.79 %), 0.0414 |
| rand s16 32MB | 180.613 / 180.776 / 182.721; 181.552 / 181.821 / 180.818 | 0.811 | 188.659; 189.575 | +7.734 (+4.26 %) | 9.5 | 12.05, 2.0e-05 | 0.0357 | yes | +7.303 (+4.10 %), 0.0771 |
| rand s16 64MB (Rand Mem) | 185.233 / 185.045 / 185.428; 185.320 / 186.046 / 185.553 | 0.344 | 191.730; 192.412 | +6.633 (+3.58 %) | 19.3 | 21.90, 5.9e-07 | 0.0357 | yes | +6.080 (+3.32 %), 0.0041 |
