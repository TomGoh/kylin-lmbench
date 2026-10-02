# 核查报告：audit:analysis-scripts

## Summary

Verdict: both scripts compute what they say, and the derived tables are numerically right. The problems are in what some columns are taken to mean, and four of them affect text that would go to the reviewer.

**Reproduction (from raw reports, own parser and statistics)**
- All 805 deterministic cells match my values: 508 in host-n90-tables.md, 297 in guest-n90-tables.md.
- The committed CSVs equal the raw reports: 10,520 host values and 4 x 2,630 guest values, 10 iterations per key, no duplicates, no orphan rows.
- Re-running copies of the two scripts reproduces both derived files byte for byte, except the five Monte-Carlo rows. I ran those at 20,000 shuffles, not 200,000, so they are checked only for consistency.
- Row selection matches the paper pipeline (scripts/build-xlsx-mean.py:218-221, scripts/build-vm-ratio-comparison.py:46-73, scripts/lmbench:470-477).
- No sign error, no dropped or double-counted iteration, no silent host/guest mixing. The guest script's host-next-to-guest table is labelled.
- welch(), exact_permutation_p() and bootstrap_ci() agree with my implementations on the data and on 30 random samples.

**Numbers confirmed**
- (a) By means: +3.55% / +0.29% / +3.25% vs kvmoff. By medians: +12.09% / -0.12% / +3.51%.
- (b) 8 MB stride 256: slow runs 4/5/8/6 with the 11.3 ns cut. Exact permutation p = 73808/184756 = 0.3995 (means), 0.4902 (medians).
- (c) Random increment: -0.05 ns at 1 MB, +0.71 at 3 MB, +1.73 at 4 MB, +5.24 at 6 MB, +7.05 at 8 MB, +6.5 to +8.1 from 12 to 64 MB. All 10 protected runs exceed all 30 baseline runs at 4, 8, 12 and 16 MB.
- (e) Non-quiesced nVHE: random access 18-35% faster from 3 MB, no two-valued behaviour at 8 MB.
- (f) Guest medians and ratios as tabulated.

**What must change before the tables are quoted**
1. **Sequential "implied ns per crossing" (host section 4) is an artefact.** The reference leaves out vhe. Against vhe, pkvm is faster at every stride from 64 up, and vhe minus kvmoff is larger than the claimed increment. The worklog's "1.6-2.0 ns per walk" is not supported.
2. **The "95% CI" next to the random increment is for pkvm minus kvmoff only, with 5000 draws.** At 64 MB the table prints [+0.01, +15.27]; the exact bootstrap interval is [-0.05, +15.24]. At 16-48 MB the upper bounds overstate the increment's uncertainty several-fold.
3. **The pooled permutation p-values treat 40 iterations of 4 boots as independent.** They show that these boots differ, not that the mode causes it. Two boots with the same translation regime (vhe, kvmoff) also differ "significantly" in sequential latency.
4. **The +3.25% itself (difference of means) has exact p = 0.093.** Only robust statistics make the 64 MB point significant (median permutation 0.031, Mann-Whitney 0.012).
5. **Slow-run counts depend on the cut.** They are 4/5/6/5 with a cut at 12.0 ns; five of 40 values lie between the clusters.
6. **The "more than 4% faster" counts change pattern with the cut.** The rise with size and the spread over all four modes hold only at 4%.
7. **The guest "pVM" label is unverifiable.** That data set's own tag says NP, and it shows the fingerprint of the fast platform state.

The benchmark repository received a concurrent commit (3a0fabf5) while I worked; the two scripts, the two derived tables, parse-lmbench.py and all raw data are unchanged by it.

## Defects

- **invalidates** | kylin-lmbench/experiments/memlat-probe/analyze-host-memlat.py:200 (column header :195, division :203); derived host-n90-tables.md:95-103: Section 4 measures the sequential increment against (median kvmoff + median nvhe)/2 and drops vhe, although vhe is one of the three no-stage-2 baselines used in section 3 (line 163). The baselines are not interchangeable here. pkvm minus vhe is -0.054, -0.081, -0.437, -0.137, -0.167 ns at strides 64 to 1024. vhe minus kvmoff is +0.111, +0.227, +0.424, +0.353, +0.593 ns (exact permutation p <= 0.011 each), larger than the tabulated pkvm increment (+0.050, +0.157, +0.046, +0.244, +0.404 ns) at every one of these strides. No uncertainty is printed for 'implied ns per crossing'. Effect: Scope: this invalidates only the column 'implied ns per crossing' and sentences built on it. The column (+0.7 to +5.0 ns) depends on the reference: against vhe it is -3.5, -2.6, -7.0, -1.1, -0.7 ns; against the median of all three baselines it is +2.8, +4.7, -0.2, +1.7, +1.5 ns. The worklog sentence (section 6.2) that the N90 sequential data imply about 1.6 to 2.0 ns per page walk is not supported. The data support only that pkvm lies inside the spread of the no-stage-2 boots for sequential access. The paper's +0.29% statement is not affected.
- **weakens** | analyze-host-memlat.py:165 (header :155, bootstrap_ci :89-97); derived host-n90-tables.md:58-74: The interval printed next to 'pkvm - baseline' is not an interval for that quantity. It is a percentile bootstrap of median(pkvm) - median(kvmoff) only, with 5000 draws. (i) At 16-48 MB its upper bounds (+33.58, +21.78, +35.43, +24.37 ns) come from kvmoff's fast outlier runs; the exact percentile-bootstrap interval of the tabulated increment (all four groups resampled) is [+7.47,+8.00], [+7.63,+8.54], [+7.29,+8.43], [+5.54,+7.98]. (ii) 5000 draws are too few at a knife-edge. At 64 MB the table prints [+0.01, +15.27]; the exact bootstrap distribution gives [-0.05, +15.24] with P*(difference <= 0) = 0.0260 > 0.025 (three 20000-draw checks: 0.0258, 0.0265, 0.0260). For the tabulated increment the exact interval is [-0.09, +11.23]. Effect: Quoting this column as the confidence interval of the increment misstates the uncertainty in both directions. 'The 95% interval at 64 MB excludes zero' is false for this method, and 64 MB is the point the paper and the reviewer cite. The increments at 3-48 MB are unaffected: their intervals exclude zero under every method. The rank-based exact interval at 64 MB is +5.49 to +7.69 ns.
- **weakens** | analyze-host-memlat.py:173-192; derived host-n90-tables.md:83-91: The Monte-Carlo test pools 30 runs from three boots and permutes 40 individual iterations. The 10 iterations of a mode are repeated measurements inside one boot, and the data set holds one protected boot, so the permutation unit is wrong for a statement about boot mode. Iteration-level tests pick up boot effects in the same files: vhe vs kvmoff differ with exact p = 0.011 (seq stride 256, 64 MB, +3.88%), p < 0.001 (strides 512 and 1024) and p = 0.005 for a 0.005 ns difference at stride 16. These two boots have the same translation regime: 'vhe' is not an accepted kvm-arm.mode value at tag 6.6.0-73.76 (arch/arm64/kvm/arm.c:3373-3408), and arch/arm64/kernel/pi/idreg-override.c:241-242 turns VHE off only for nvhe and protected. Effect: The p-values 0.000005 to 0.015 say that these four boots differ, not that protected mode causes it. With sessions as the unit the evidence is 1 protected boot against 3 (p = 0.25), or 2 against 6 if the standalone sessions are counted (p = 1/28 = 0.036 one-sided). The supportable argument is the size of the separation: both protected session medians exceed all six others by at least 5.7 ns at 8-64 MB, against a 0.3-2.1 ns range among the six.
- **weakens** | analyze-host-memlat.py:103-112 and :124-130 (a test on means exists only for the 8 MB point); derived host-n90-tables.md:9-10, 74, 91: The two numbers the reviewer cites are tested with different statistics. For LLC Bnd the script tests the paper's estimator (difference of 10-run means vs kvmoff, exact permutation). For Rand Mem no test on means is computed; only median-based quantities are shown (pooled permutation p = 0.0148, bootstrap interval). Effect: On the paper's estimator the 64 MB random number is not significant at 5%: +5.93 ns (+3.25%), exact permutation p = 0.093 vs kvmoff (0.087 vs vhe, 0.073 vs nvhe), Welch p = 0.098. Each mode has 2-3 fast outlier runs. With robust statistics it is significant: exact permutation on medians p = 0.031, exact Mann-Whitney p = 0.012, 8 of 10 protected runs above all 30 baseline runs. The reply should not present +3.25% as the established effect; the stable quantity is the median shift of about +6.5 ns (+3.5%) at 64 MB and +7 to +8 ns at 8-48 MB.
- **weakens** | analyze-host-memlat.py:41 (MODE_SPLIT_NS = 11.3), used at :120-123; derived host-n90-tables.md:14-19: The 'slow-mode runs' column depends on the cut. Five of the 40 values lie between the clusters (vhe 10.92, 11.47, 11.73; pkvm 11.77; kvmoff 10.98). The clusters proper are 9.93-10.70 ns (15 values) and 12.21-12.63 ns (20 values). With the cut at 11.3 the counts are 4/5/8/6; with any cut between 11.8 and 12.2 they are 4/5/6/5. The 'slow-mode mean' of vhe (12.30) and pkvm (12.40) includes intermediate values. Effect: 'The +3.55% is 4 slow runs against 6' (worklog section 3) and '8/10 for vhe' should read 5-6 and 6-8. The conclusion that the difference is indistinguishable from zero does not depend on the cut: the tests use raw values (exact permutation p = 0.3995; Fisher on the counts p = 0.66 or 1.00).
- **weakens** | analyze-host-memlat.py:236-246 (threshold 0.96 at :245); derived host-n90-tables.md:127-140: 'More than 4% faster than the median' is an arbitrary cut, far from the fast state it is meant to detect (the non-quiesced run is 18-35% faster). The pattern changes with the cut. Totals for 12/16/24/32/48/64 MB are 1/4/4/6/8/11 at 4%, 1/4/4/6/4/4 at 8% and 1/3/2/3/1/0 at 15%. At 15% the runs are 8 kvmoff, 0 nvhe, 1 vhe, 1 pkvm. At 64 MB all 11 counted runs are only 4.7-13.8% below their median. Effect: 'Occurs in all four modes' and 'the larger the working set the more often' (worklog 9.1, used as support for the interconnect-frequency hypothesis) hold only for the 4% cut. Runs that reach the fast level occur at 12-48 MB, mostly in the kvmoff boot, and not at 64 MB. lmbench reports the minimum of 11 timed intervals, and an interval lasts about 0.78 s at 64 MB against about 0.18 s at 16 MB, so a short transient would also produce a rising count of partly fast values with size.
- **weakens** | kylin-lmbench/experiments/memlat-probe/analyze-guest-memlat.py:30-35; derived guest-n90-tables.md:5-21: Configuration labels come from directory names only and are printed without caveat. The data set labelled 'pVM on pKVM host' (xkernel-n90-pkvm-pvm-20260605-163040) carries ENV_TAG=xkernel-pkvm-np in autorun.marker and started.txt, and its report files are named xkernel-pkvm-np-cpu0-iterN.txt, the same tag as the NP set. environment.txt and CONFIG.xkernel.used are byte-identical in all four guest directories. Nothing in the raw reports records host boot mode, VM type, vCPU pinning or crosvm options. Effect: Every statement about the protected VM (20-32% faster random access, Figure 8's negative overhead) rests on an unverifiable label. Independently of the label, this data set shows the fast platform state seen in the non-quiesced host run: no two-valued behaviour at 8 MB sequential at any stride (max/min 1.03-1.05 against 1.23-1.26 in the other three guests), and random 64 MB at 152.9 ns against 150.1 ns on the non-quiesced host. The difference cannot be attributed to protection.
- **weakens** | analyze-guest-memlat.py:98-106; derived guest-n90-tables.md:49-55: Section 3 prints 'pVM vs nVHE VM' as a ratio of medians at 8 MB, where three guest sets are two-valued (about 10.0 and 12.4 ns at stride 256) and the pVM set is not. The ratio then reflects only which side of 5/10 the slow runs fall on: -19.20% (stride 256), -8.60% (1024), -3.04% (512), -0.95% (128), although the pVM values sit at the same fast level at every stride. No per-iteration values or warning are printed. Effect: This is the same estimator instability as the host LLC-boundary point (+3.55% by mean, +12.09% by median). By means the stride-256 figure is -15.6% vs the nVHE-host VM and -11.0% vs the VHE-host VM. Quoting -19.2%, or the paper's 'LLC boundary latency lower by more than 10%' for the pVM, as a property of protected VMs would be quoting a state difference.
- **cosmetic** | analyze-host-memlat.py:192 (shuffles at :185): The Monte-Carlo p is reported as max(hits,1)/shuffles with six decimals; the valid estimator is (hits+1)/(shuffles+1). '(upper bound)' is printed only for hits = 0, so the 8 MB and 16 MB rows (one hit each) read as point estimates of 0.000005. Effect: None. For the sizes with complete separation (4, 8, 16 MB) the exact p of this statistic is 3060/847,660,528 = 3.6e-6, so the printed values sit at the resolution limit of 200,000 shuffles.
- **cosmetic** | analyze-host-memlat.py:136-137; derived host-n90-tables.md:28: The table asserts an untested mechanism: '(modes are decided per allocation, so strides within one iteration do not agree)'. The second half holds (phi between the slow indicators of two strides in one iteration is -0.08 to +0.19). The first half is not established. Every point is both a new allocation and a different moment. The 8 MB value correlates with the next points of the same sweep (Spearman rho +0.35 to +0.46 with 12 MB, +0.32 to +0.44 with 16 MB) and hardly with the preceding 4 and 6 MB points (-0.23 to +0.30). All five 12 MB stride-256 values above 13 ns follow a slow 8 MB point (5 of 23 vs 0 of 17). Effect: Wording only, but the sentence should not be quoted. The data cannot separate 'decided by the pages the child received' from 'decided by a platform state that outlives one child'.
- **cosmetic** | analyze-host-memlat.py:222-223 (docstring :14-17); derived host-n90-tables.md:107: Provenance and interpretation of the non-quiesced run are hard-coded print statements, not derived from data: 'taken with desktop and background services running', and in the docstring a second state 'independent of the KVM mode'. Effect: Partly checkable. Both summary files show the same kernel image and kvm-arm.mode=nvhe. A gvfsd-fuse mount appears in iterations 2-10 of the non-quiesced run and in none of the 40 quiesced reports. Iteration 1, without that mount, is just as fast (random 64 MB 150.7 ns, 8 MB sequential 10.81 ns), so the desktop marker does not explain the state. 'Independent of the KVM mode' cannot follow from a comparison made in one mode.
- **cosmetic** | analyze-guest-memlat.py:11-12 (docstring), :66-67, :85-88; derived guest-n90-tables.md:5-21: The docstring says the table gives 'the ratios used in Figure 8'. The script uses medians; Figure 8 is built from 10-run means (docs/vm-ratio-comparison.csv columns *_mean, which my mean-based recomputation reproduces to the last digit). Effect: The numbers differ from the figure by up to 3.5 percentage points (24 MB: pVM/nVHE -20.2% vs -16.67%, NP/nVHE +0.7% vs +3.62%; 8 MB pVM/VHE -21.7% vs -19.67%). The qualitative picture is unchanged, and the table header does say 'medians'.
- **cosmetic** | analyze-host-memlat.py:44-59; analyze-guest-memlat.py:48, :55-58, :66-67: Missing or duplicated data would pass silently. Neither script checks that every key has 10 iterations (headers hard-code 'iter 1..10' and 'total of 40'). Duplicate (bench, variant, iter) rows overwrite each other. The guest loader skips rows whose variant does not match ('if m:') and discards the parser's stderr (530 UNPARSED lines per guest data set). Effect: None today. I verified 263 keys x 10 iterations in all nine data sets, no duplicates, no unmatched variants, and that the discarded parser messages concern only non-lmbench lines. It is a latent hazard: the non-quiesced CSV carries the same env value (n90-nvhe-noLSM-full) as the quiesced one.
- **cosmetic** | analyze-guest-memlat.py:36-39, :108-115; derived guest-n90-tables.md:58-71: The host-next-to-guest table is labelled correctly (host vs guest), but shows only the two slow-state host sets (kvmoff, pkvm try2). It omits the non-quiesced host set, which is the host curve the 'pVM' guest follows (64 MB 152.9 vs 150.1 ns; 16 MB 141.2 vs 134.2; 32 MB 150.2 vs 146.2). Effect: The table invites the reading 'a protected guest is faster than the bare host' (152.9 vs 185.2 ns), which is a comparison across platform states.

## Discrepancies

- Deterministic cells: none. All 805 cells (508 in host-n90-tables.md, 297 in guest-n90-tables.md) regenerated from the raw reports with my own parser and statistics are identical as printed.
- Host section 3, column '95% CI vs kvmoff', 64 MB: derived [+0.01, +15.27]; the exact percentile-bootstrap interval is [-0.05, +15.24], with P*(difference <= 0) = 0.0260. The lower bound changes sign; the derived value is a 5000-draw Monte-Carlo accident.
- Host section 3, same column, other rows: 48 MB lower bound +5.75 derived vs +5.56 exact; 1.5 MB lower bound -0.02 derived vs +0.00 exact (P* = 0.0248); 0.5, 0.75, 1, 2, 3, 4, 16 and 24 MB differ by at most 0.02 ns; 6, 8, 12 and 32 MB are identical.
- Host section 3: the CI column is not the interval of the tabulated increment. Exact intervals for pkvm median minus median of the three baseline medians: 16 MB [+7.47,+8.00] (table [+7.47,+33.58]); 24 MB [+7.63,+8.54] (table [+7.82,+21.78]); 32 MB [+7.29,+8.43] (table [+7.32,+35.43]); 48 MB [+5.54,+7.98] (table [+5.75,+24.37]); 64 MB [-0.09,+11.23] (table [+0.01,+15.27]); 4 MB [+1.40,+2.02] (table [+1.23,+2.04]); 8 MB [+6.56,+7.66] (table [+6.27,+7.73]).
- Host section 3 Monte-Carlo permutation p: derived 0.000005 (upper bound) at 4 MB and 0.000005 at 8 and 16 MB; exact value 3060/847,660,528 = 3.61e-6 for each. 32 MB: derived 0.002010; mine 0.00195, 0.00235, 0.00275 in three 20,000-shuffle runs. 64 MB: derived 0.014780; mine 0.0136, 0.0139, 0.0153. These are consistent. I did not re-run 200,000 shuffles, so these five cells are not reproduced bit for bit.
- Host section 2, bootstrap 95% CI of the mean difference: derived [-0.48, +1.25]; mine [-0.48, +1.24] and [-0.46, +1.24] with two other seeds. This is Monte-Carlo noise only.
- Host section 2, slow-mode counts: identical (4/5/8/6) with the script's 11.3 ns cut; 4/5/6/5 with a cut at 12.0 ns.
- Host section 4, sequential increments at 64 MB: identical with the script's reference (-0.001, +0.000, +0.050, +0.157, +0.046, +0.244, +0.404 ns). Against the median of all three baselines: -0.001, -0.002, +0.044, +0.147, -0.012, +0.216, +0.381. Against vhe alone: +0.004, -0.006, -0.054, -0.081, -0.437, -0.137, -0.167.
- Guest tables: no discrepancy with my medians. Against the figure they claim to describe, the median-based ratios differ from Figure 8's mean-based values by up to 3.5 percentage points (24 MB pVM/nVHE -20.2% vs -16.67%; 12 MB -21.5% vs -19.96%; 16 MB -20.1% vs -18.70%; 8 MB pVM/VHE -21.7% vs -19.67%).

## Threats to validity

- Mode is confounded with boot and time of day. The suite has one boot per mode: vhe Jun 3 22:20-00:03, kvmoff Jun 4 00:11-01:54, nvhe 02:02-03:44, pkvm try2 12:05-13:47 CST, the only daytime run. The 10 iterations are repeated measures inside one boot, so no analysis of these files can separate a mode effect from a boot, thermal or time-of-day effect. Boot effects of the relevant size exist: vhe and kvmoff, with the same translation regime, differ by 3.9% at seq 64 MB (exact p = 0.011) and by 6.8% at the LLC-boundary point.
- At session level the random-access evidence is 2 protected sessions against 6 others, and the standalone logs (results/standalone-mem-bench/*.log) carry no timestamp, kernel command line or boot id. Whether they were separate boots, and in which mode, is documented only in prose.
- The N90 data contain no mechanism evidence: no PMU counters, no record of stage-2 mapping granularity, no dmesg. The per-run summary files hold only kernel, cmdline and cpu max frequency; they do not confirm that protected mode initialised, which EL2 implementation ran, or the THP and ASLR state. The data can show that protected boots are about 7 ns slower per load when every load changes page above 8 MB, and not below 2 MB. They cannot show that the time is spent in stage-2 walks rather than in another property of those boots (physical placement after the hyp reservation, walk-cache behaviour, memory-system state).
- A second platform state exists and is not controlled or recorded (interconnect or memory frequency, power source, thermal state). In one non-quiesced nVHE boot, random access is 18-35% faster in all 10 iterations with no overlap. The data cannot say what selects the state or whether the protected increment is the same in both states. Only one host data set is in the fast state, in one mode, and the raw try1 protected run is not in the repository. Its exclusion in favour of try2 cannot be audited.
- Each reported value is lmbench's minimum over 11 timed intervals in one child on one allocation (src/lat_mem_rd.c:148, TRIES = 11 in src/bench.h:198). Slow transients are removed and fast ones kept, so per-iteration values are not draws from one stationary distribution. Means are estimator-sensitive (LLC Bnd +3.55% by mean, +12.09% by median; Rand Mem p = 0.093 on means, 0.012-0.031 with robust tests).
- Power at the LLC boundary is low. With 10 runs per mode and a two-cluster distribution (SD about 1.0 ns), the 95% interval of pkvm minus kvmoff is about -0.5 to +1.2 ns (-4% to +11%). The data neither confirm nor exclude an overhead of the paper's 3.55%, or the roughly 0.4 ns that a 7 ns cost per page crossing would give at stride 256. Non-significance is not evidence of absence.
- Guest data: one VM session per configuration, on two days (pVM set Jun 5 05:31-08:28 UTC, VHE-host VM Jun 5 09:16-12:17, nVHE-host VM Jun 6 02:30-05:30, NP Jun 6 05:47-08:45). Host state is unrecorded, and the pVM and NP sets come from different protected boots a day apart. The guest data cannot show a property of protected VMs; all guests run under stage 2, so NP equal to the regular VMs also says nothing about stage-2 cost.
- Cross-context comparisons. Host vs guest differ in kernel (Linux vs x-kernel), allocator and vCPU placement. N90 vs N80 differ in machine (32 GB vs 16 GB, other DIMMs), kernel, and effective core clock: the L1-resident latency is 2.223 ns in all five N90 host sets and 2.225-2.228 ns in the guests (4 cycles at about 1.80 GHz, although lmbench prints 1900 MHz), so the clock is equal across N90 sets but unverified against N80. Dividing N90 time increments by N80 walk counts is a cross-machine inference.
- Scope: only cpu0, only 4 KiB pages, only two lmbench access patterns, no VM running on the host. Nothing here generalises to the faster cores, to THP-backed workloads or to a host with guests running.

## Recomputed tables

All values in ns, recomputed from the raw per-iteration reports with an independent parser and my own statistics. N = 10 iterations per data set everywhere. "p < 0.001" means fewer than 185 of 184,756 splits.

**(a) Figure 7 memory numbers (host, N90)**

| metric | estimator | kvmoff | nvhe | vhe | pkvm | vs kvmoff | vs vhe | vs nvhe | exact permutation p, pkvm vs kvmoff / vhe / nvhe |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| LLC Bnd = seq stride 256, 8 MB | mean | 11.203 | 11.276 | 11.961 | 11.600 | +3.55% | -3.02% | +2.87% | 0.399 / 0.403 / 0.482 |
| LLC Bnd = seq stride 256, 8 MB | median | 10.815 | 11.410 | 12.447 | 12.123 | +12.09% | -2.60% | +6.25% | 0.490 / 0.982 / 0.671 |
| Main Mem = seq stride 256, 64 MB | mean | 10.381 | 10.302 | 10.784 | 10.411 | +0.29% | -3.46% | +1.06% | 0.768 / 0.013 / 0.257 |
| Main Mem = seq stride 256, 64 MB | median | 10.357 | 10.241 | 10.781 | 10.345 | -0.12% | -4.05% | +1.01% | 0.995 / 0.006 / 0.515 |
| Rand Mem = rand (-t) stride 16, 64 MB | mean | 182.209 | 181.104 | 181.207 | 188.135 | +3.25% | +3.82% | +3.88% | 0.093 / 0.087 / 0.073 |
| Rand Mem = rand (-t) stride 16, 64 MB | median | 185.233 | 185.045 | 185.428 | 191.730 | +3.51% | +3.40% | +3.61% | 0.031 / 0.033 / 0.045 |

The p-values test the difference of the estimator named in the row (means in mean rows, medians in median rows), over all C(20,10) splits.

Null comparison, vhe vs kvmoff on means (two boots with the same translation regime): LLC Bnd +6.77% (exact p 0.082), Main Mem +3.88% (exact p 0.011), Rand Mem -0.55% (exact p 0.757).

**(b) lat_mem_rd_load stride 256 at 8 MB, per iteration (host, N90)**

| mode | iterations 1..10 | runs >= 11.3 ns (analyst's cut) | runs >= 12.0 ns | runs in 10.9-11.9 ns | mean | SD | median |
|---|---|:---:|:---:|---|---:|---:|---:|
| kvmoff | 12.24 10.50 10.19 12.37 12.21 10.98 10.65 12.49 10.06 10.35 | 4/10 | 4/10 | 10.98 | 11.203 | 1.00 | 10.815 |
| nvhe | 10.30 12.43 12.62 9.98 9.93 12.27 12.35 10.55 12.31 10.02 | 5/10 | 5/10 | none | 11.276 | 1.20 | 11.410 |
| vhe | 11.47 12.62 11.73 12.47 12.45 12.57 10.92 12.45 10.30 12.63 | 8/10 | 6/10 | 11.47, 11.73, 10.92 | 11.961 | 0.83 | 12.447 |
| pkvm | 10.70 11.77 12.57 12.56 12.52 10.56 10.25 12.50 10.10 12.47 | 6/10 | 5/10 | 11.77 | 11.600 | 1.07 | 12.123 |

- pkvm vs kvmoff: mean difference +0.397 ns (+3.55%).
- Exact two-sided permutation test over all C(20,10) = 184,756 splits: p = 73808/184756 = 0.3995 (difference of means); 90562/184756 = 0.4902 (difference of medians).
- Welch t = 0.86, df = 17.9, p = 0.402. Exact Mann-Whitney p = 0.218.
- Fisher exact on slow counts: 6/10 vs 4/10 p = 0.656; 5/10 vs 4/10 p = 1.000.
- Bootstrap 95% interval of the mean difference (20,000 draws): [-0.48, +1.24] ns.

**(c) Random access (lat_mem_rd -t, stride 16), host N90: pkvm median minus the median of the three baseline medians**

| size | kvmoff | nvhe | vhe | pkvm | increment | exact bootstrap 95% interval of this increment | spread of 3 baseline medians | pkvm runs above all 30 baseline runs | Hodges-Lehmann shift vs 30 pooled [exact 95% CI] | derived table's '95% CI vs kvmoff' | exact interval for pkvm - kvmoff |
|---:|---:|---:|---:|---:|---:|---|---:|:---:|---|---|---|
| 1 MB | 19.41 | 19.48 | 19.48 | 19.43 | -0.05 | [-0.19, +0.20] | 0.07 | 0/10 | -0.03 [-0.15, +0.13] | [-0.27, +0.26] | [-0.27, +0.27] |
| 1.5 MB | 20.19 | 20.18 | 20.12 | 20.24 | +0.06 | [+0.01, +0.14] | 0.06 | 0/10 | +0.07 [+0.01, +0.14] | [-0.02, +0.12] | [+0.00, +0.12] |
| 2 MB | 20.68 | 20.75 | 20.73 | 20.88 | +0.15 | [-0.04, +0.47] | 0.08 | 1/10 | +0.18 [+0.02, +0.40] | [-0.04, +0.48] | [-0.03, +0.49] |
| 3 MB | 36.60 | 36.63 | 36.56 | 37.31 | +0.71 | [+0.26, +1.09] | 0.07 | 7/10 | +0.70 [+0.38, +1.00] | [+0.25, +1.09] | [+0.26, +1.08] |
| 4 MB | 47.59 | 47.69 | 47.45 | 49.31 | +1.73 | [+1.40, +2.02] | 0.23 | 10/10 | +1.68 [+1.42, +1.93] | [+1.23, +2.04] | [+1.23, +2.03] |
| 6 MB | 67.14 | 67.35 | 67.37 | 72.59 | +5.24 | [+4.38, +6.79] | 0.24 | 6/10 | +5.19 [+4.55, +5.88] | [+4.41, +6.93] | [+4.41, +6.93] |
| 8 MB | 112.54 | 112.60 | 112.32 | 119.59 | +7.05 | [+6.56, +7.66] | 0.28 | 10/10 | +7.02 [+6.69, +7.50] | [+6.27, +7.73] | [+6.27, +7.73] |
| 12 MB | 154.65 | 154.81 | 154.65 | 161.68 | +7.03 | [+6.57, +7.28] | 0.16 | 10/10 | +6.92 [+6.65, +7.24] | [+6.58, +7.32] | [+6.58, +7.32] |
| 16 MB | 168.54 | 168.56 | 169.71 | 176.28 | +7.73 | [+7.47, +8.00] | 1.16 | 10/10 | +7.63 [+7.05, +7.98] | [+7.47, +33.58] | [+7.49, +33.58] |
| 24 MB | 177.23 | 177.47 | 180.27 | 185.59 | +8.12 | [+7.63, +8.54] | 3.04 | 9/10 | +7.83 [+5.65, +8.52] | [+7.82, +21.78] | [+7.81, +21.77] |
| 32 MB | 180.61 | 180.78 | 182.72 | 188.66 | +7.88 | [+7.29, +8.43] | 2.11 | 9/10 | +7.33 [+6.16, +8.07] | [+7.32, +35.43] | [+7.32, +35.43] |
| 48 MB | 182.66 | 182.44 | 183.85 | 189.56 | +6.90 | [+5.54, +7.98] | 1.41 | 9/10 | +6.40 [+5.45, +7.55] | [+5.75, +24.37] | [+5.56, +24.38] |
| 64 MB | 185.23 | 185.05 | 185.43 | 191.73 | +6.50 | [-0.09, +11.23] | 0.38 | 8/10 | +6.43 [+5.49, +7.69] | [+0.01, +15.27] | [-0.05, +15.24] |

"Exact bootstrap" means the exact distribution of the median of a 10-value resample, convolved across groups, with no Monte-Carlo error. At 64 MB, P*(pkvm - kvmoff <= 0) = 0.0260.

Pooled permutation test on the difference of medians (10 pkvm vs 30 pooled):
- 4, 8, 16 MB: exact p = 3060/847,660,528 = 3.6e-6.
- 32 MB: about 0.002 by Monte-Carlo (three runs of 20,000 shuffles: 0.00195, 0.00235, 0.00275).
- 64 MB: about 0.014 (0.0136, 0.0139, 0.0153).

Session-level view, random access (median of 10 runs per session):

| size | suite kvmoff | suite nvhe | suite vhe | standalone kvmoff | standalone nvhe | standalone vhe | range of the 6 | suite pkvm (try2) | standalone pkvm | smallest pkvm minus largest baseline |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 MB | 47.59 | 47.69 | 47.45 | 47.70 | 47.40 | 47.49 | 0.30 | 49.31 | 49.74 | +1.61 |
| 8 MB | 112.54 | 112.60 | 112.32 | 112.90 | 112.70 | 112.58 | 0.57 | 119.59 | 120.01 | +6.70 |
| 16 MB | 168.54 | 168.56 | 169.71 | 169.80 | 169.92 | 169.72 | 1.38 | 176.28 | 176.72 | +6.36 |
| 32 MB | 180.61 | 180.78 | 182.72 | 181.55 | 181.82 | 180.82 | 2.11 | 188.66 | 189.57 | +5.94 |
| 64 MB | 185.23 | 185.05 | 185.43 | 185.32 | 186.05 | 185.55 | 1.00 | 191.73 | 192.41 | +5.68 |

Standalone replication of the Figure 7 points (means): seq 256 at 8 MB pkvm vs kvmoff +0.65% (exact p 0.82); seq 256 at 64 MB +1.11% (p 0.49); rand 64 MB +3.24% (p 0.011). Standalone slow runs at 8 MB (>= 11.3 / >= 12.0): kvmoff 6/5, nvhe 7/7, vhe 7/6, pkvm 6/6.

**(d) Sequential access at 64 MB by stride, host N90 (medians)**

| stride | kvmoff | nvhe | vhe | pkvm | pkvm - mean(kvmoff, nvhe) [analyst's reference] | pkvm - median of all 3 baselines | pkvm - vhe | vhe - kvmoff | exact perm p (means): pkvm vs kvmoff | pkvm vs vhe | vhe vs kvmoff |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 2.317 | 2.318 | 2.312 | 2.317 | -0.001 | -0.001 | +0.004 | -0.005 | 0.925 | 0.011 | 0.005 |
| 32 | 2.675 | 2.678 | 2.682 | 2.676 | +0.000 | -0.002 | -0.006 | +0.007 | 0.423 | 0.198 | 0.019 |
| 64 | 4.217 | 4.230 | 4.328 | 4.274 | +0.050 | +0.044 | -0.054 | +0.111 | <0.001 | <0.001 | <0.001 |
| 128 | 9.034 | 9.014 | 9.261 | 9.180 | +0.157 | +0.147 | -0.081 | +0.227 | 0.003 | 0.140 | <0.001 |
| 256 | 10.357 | 10.241 | 10.781 | 10.345 | +0.046 | -0.012 | -0.437 | +0.424 | 0.768 | 0.013 | 0.011 |
| 512 | 9.573 | 9.517 | 9.926 | 9.789 | +0.244 | +0.216 | -0.137 | +0.353 | 0.001 | 0.542 | <0.001 |
| 1024 | 10.473 | 10.518 | 11.066 | 10.899 | +0.404 | +0.381 | -0.167 | +0.593 | <0.001 | 0.002 | <0.001 |

By 10-run means, pkvm - kvmoff is +0.262 ns (+2.73%) at stride 512 and +0.368 ns (+3.50%) at stride 1024; vhe - kvmoff is +0.343 and +0.571 ns.

**(e) Non-quiesced nVHE host run versus the quiesced runs (medians)**

| size | rand: quiesced nvhe | rand: non-quiesced nvhe | change | rand: quiesced kvmoff / vhe / pkvm | seq stride 256: quiesced nvhe | seq stride 256: non-quiesced nvhe | change |
|---:|---:|---:|---:|---|---:|---:|---:|
| 1 MB | 19.48 | 19.05 | -2.2% | 19.41 / 19.48 / 19.43 | 4.44 | 4.47 | +0.7% |
| 2 MB | 20.75 | 21.10 | +1.7% | 20.68 / 20.73 / 20.88 | 4.70 | 4.74 | +0.9% |
| 3 MB | 36.63 | 26.41 | -27.9% | 36.60 / 36.56 / 37.31 | 5.31 | 4.92 | -7.5% |
| 4 MB | 47.69 | 30.80 | -35.4% | 47.59 / 47.45 / 49.31 | 5.48 | 5.07 | -7.5% |
| 6 MB | 67.35 | 48.61 | -27.8% | 67.14 / 67.37 / 72.59 | 8.22 | 7.46 | -9.2% |
| 8 MB | 112.60 | 83.90 | -25.5% | 112.54 / 112.32 / 119.59 | 11.41 | 10.32 | -9.6% |
| 12 MB | 154.81 | 121.82 | -21.3% | 154.65 / 154.65 / 161.68 | 10.86 | 11.34 | +4.4% |
| 16 MB | 168.56 | 134.23 | -20.4% | 168.54 / 169.71 / 176.28 | 10.69 | 11.47 | +7.2% |
| 24 MB | 177.47 | 143.08 | -19.4% | 177.23 / 180.27 / 185.59 | 10.87 | 11.27 | +3.6% |
| 32 MB | 180.78 | 146.20 | -19.1% | 180.61 / 182.72 / 188.66 | 10.50 | 11.17 | +6.4% |
| 48 MB | 182.44 | 149.10 | -18.3% | 182.66 / 183.85 / 189.56 | 10.54 | 11.04 | +4.7% |
| 64 MB | 185.05 | 150.12 | -18.9% | 185.23 / 185.43 / 191.73 | 10.24 | 11.11 | +8.5% |

- Seq stride 256 at 8 MB per iteration, quiesced nvhe: 10.30 12.43 12.62 9.98 9.93 12.27 12.35 10.55 12.31 10.02.
- Same, non-quiesced nvhe: 10.81 10.34 10.34 10.31 10.27 10.26 10.33 10.28 10.10 10.33.
- Random 8 MB per-iteration ranges: quiesced [112.2, 113.2], non-quiesced [83.2, 84.8]. At 64 MB: quiesced [164.5, 186.6], non-quiesced [149.9, 151.9].
- 8 MB sequential max/min over 10 iterations at strides 128/256/512/1024: quiesced 1.26/1.27/1.24/1.21, non-quiesced 1.01/1.07/1.03/1.03.

Quiesced runs below (1 - t) x their own median, random access, totals of 40 (kvmoff/nvhe/vhe/pkvm):

| size | t = 4% (the script's cut) | t = 8% | t = 15% |
|---:|---|---|---|
| 12 MB | 1 (1/0/0/0) | 1 (1/0/0/0) | 1 (1/0/0/0) |
| 16 MB | 4 (3/0/1/0) | 4 (3/0/1/0) | 3 (3/0/0/0) |
| 24 MB | 4 (2/0/1/1) | 4 (2/0/1/1) | 2 (1/0/1/0) |
| 32 MB | 6 (4/1/0/1) | 6 (4/1/0/1) | 3 (2/0/0/1) |
| 48 MB | 8 (3/3/1/1) | 4 (3/1/0/0) | 1 (1/0/0/0) |
| 64 MB | 11 (3/3/3/2) | 4 (1/1/1/1) | 0 |

**(f) Guest random access (measured inside the x-kernel guest; lat_mem_rd -t, stride 16)**

| size | VM on VHE host | VM on nVHE host | NP VM on pKVM host | 'pVM' on pKVM host | pVM vs nVHE VM (medians) | pVM vs VHE VM | NP vs nVHE VM | same three ratios from 10-run means (Figure 8's estimator) | pVM runs below all 30 other-guest runs |
|---:|---:|---:|---:|---:|---:|---:|---:|---|:---:|
| 3 MB | 39.39 | 39.44 | 39.44 | 29.00 | -26.5% | -26.4% | -0.0% | -26.43%, -25.73%, -0.04% | 10/10 |
| 4 MB | 51.84 | 52.30 | 52.62 | 35.97 | -31.2% | -30.6% | +0.6% | -31.22%, -30.86%, +0.81% | 10/10 |
| 6 MB | 78.88 | 81.13 | 80.68 | 55.34 | -31.8% | -29.8% | -0.6% | -31.67%, -29.80%, -0.60% | 10/10 |
| 8 MB | 124.97 | 126.83 | 126.53 | 97.85 | -22.8% | -21.7% | -0.2% | -22.49%, -19.67%, -0.58% | 4/10 |
| 12 MB | 164.41 | 165.03 | 164.76 | 129.49 | -21.5% | -21.2% | -0.2% | -19.96%, -19.54%, +1.64% | 9/10 |
| 16 MB | 176.90 | 176.73 | 177.05 | 141.20 | -20.1% | -20.2% | +0.2% | -18.70%, -18.78%, +1.48% | 10/10 |
| 24 MB | 185.11 | 184.54 | 185.92 | 147.25 | -20.2% | -20.5% | +0.7% | -16.67%, -20.42%, +3.62% | 10/10 |
| 32 MB | 187.93 | 189.92 | 189.23 | 150.18 | -20.9% | -20.1% | -0.4% | -20.65%, -19.24%, -1.03% | 10/10 |
| 48 MB | 192.80 | 191.46 | 191.47 | 151.07 | -21.1% | -21.6% | +0.0% | -19.63%, -21.44%, +0.03% | 10/10 |
| 64 MB | 192.94 | 192.00 | 192.35 | 152.91 | -20.4% | -20.8% | +0.2% | -20.16%, -20.25%, -1.25% | 10/10 |

- The 4/10 at 8 MB is caused by one VHE-host VM run (iteration 1, 97.8 ns).
- Guest seq stride 256 at 8 MB per iteration:
  - VHE-host VM: 11.06 9.90 12.37 12.41 12.37 11.89 9.96 12.35 10.00 9.94
  - nVHE-host VM: 12.26 12.36 11.08 10.10 10.31 12.58 12.45 12.38 12.46 12.43
  - NP VM: 12.24 12.42 10.04 12.46 10.06 12.55 10.03 10.12 11.45 10.38
  - 'pVM': 9.87 10.00 9.99 9.89 9.93 10.04 10.15 10.10 9.94 10.02
- Means of those: 11.226, 11.842, 11.175, 9.993. pVM vs nVHE-host VM is -15.6% by mean, -19.2% by median.
- Host non-quiesced nVHE random medians for comparison with the 'pVM' column: 3 MB 26.41, 4 MB 30.80, 6 MB 48.61, 8 MB 83.90, 12 MB 121.82, 16 MB 134.23, 32 MB 146.20, 64 MB 150.12.
