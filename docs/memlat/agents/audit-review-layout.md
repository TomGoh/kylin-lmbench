# 核查报告：audit:review-layout

## Summary

DESIGN REVIEW of the analyst's current position (nh#1-nh#4: on the N90 the two levels of the 8 MB point come more likely from a platform state, E1, than from buffer layout, E2). I re-derived everything below from the raw CSVs and logs with my own scripts.

WHAT I REPRODUCED
- nh#1 (Exp H8): reproduced exactly from expH8.log and expH8-shim.log.
- nh#2: reproduced exactly with pooled normalization: 93 sweeps with a high 8 MB point; at 12 MB 57 normal, 16 between, 19 high; 16/24/32 MB high 12/9/7.
- nh#3 premise: in all four sweeps of expH7-pfns.log the 12 MB child holds 2033-2034 of the 8 MB child's 2049 frames, in exactly reversed virtual order. The allocator functions are the same at both kernel tags. The zap path in mm/memory.c was refactored between them; I did not trace it.
- nh#4 random-access figures: 35 values at 12-64 MB in 22 iterations, 0.785-0.96 of the boot median. The lowest equal the non-quiesced level (0.97-1.005 of it).
- nn#14 level ratios and counts: 1.221/1.219/1.207/1.212/1.162 with 4/28/22/17/22 high values.

(1) CAN A LAYOUT MECHANISM PRODUCE THE N90 PATTERN? Mostly no, but the pattern is a mixture, which the analyst does not say.
- 72 of the 93 high 8 MB points are isolated: the 12 MB point is not high.
  - Isolated highs depend strongly on the stride: 1/40 at stride 64 against 16-22/40 at each of strides 128-1024 (Fisher p about 3e-8).
  - After an isolated high, the 12 MB value is the same as after a low 8 MB point (mean difference -0.005 to +0.015, all p > 0.1). There is no partial carry-over.
  - Exp H8 plus the H7 hand-over predicts 1.16-1.19 at 12 MB. That band holds only 4-6 of 93 values, across thresholds 1.08-1.15 and three normalizations.
  - Reversed hand-over order does not rescue E2. A random set stays random when reversed. A 'descending is costly' mechanism would predict a high 16 MB point after a low 12 MB point: 0 of 73. On the N80, reversed order costs only 3.0% at 8 MB and 6.8% at 16-64 MB (expL2-n80.log).
  - An L3 page-colour mechanism, left open by an earlier verifier, is excluded by size. The high 8 MB level (12.46 ns at stride 256) is 15-22% above the normal 12-64 MB levels (10.2-10.8 ns). A cache-miss-fraction effect cannot exceed the level where everything misses.
  - Source reading, not traced: a hand-over failure would not give the 12 MB child contiguous frames by itself. Frames drained from the per-CPU list to the buddy allocator go back on the order-0 lists, which __rmqueue_smallest serves first.
- The other 21 highs carry over 2-7 sizes, and in some sweeps across strides. This includes all strides from 32 to 128 in VHE iteration 3, with stride 32 at 1.08-1.11.
  - These carried runs are roughly the same at every stride (stride 64: 3, 128: 6, 256: 5, 512: 1, 1024: 5).
  - They are concentrated in the VHE boot: probability that the next size is high after a high one is 18/29 there, against 0/3, 1/7 and 0/7 in the other three boots.
  - They fit a persistent scattered-frame pool as well as a long-lived platform state.

(2) CAN E1 PRODUCE THE REST?
- The per-stride ratio agreement with the N80 is weakly discriminating. It amounts to 'about 1.2 at every stride from 64 up, a dip at 1024'. Bootstrap 95% intervals of the N90 ratios are 0.03-0.07 wide, and a memory-path slowdown of about 20% would give the same.
  - The N80 ratios were measured under protected mode, yet the N90 ratio is the same in all four boots (kvmoff 1.15-1.22, pkvm 1.18-1.23).
  - The only same-core machine without a host stage-2 (the workstation) has smaller, differently shaped ratios at strides 64-256 (1.11, 1.06, 1.08).
  - So 'no free parameter' assumes the N80 magnitude carries over to non-stage-2 boots.
  - In the one N90 sweep where the high state reached stride 32, its size (1.08-1.11) is about twice the N80 layout ratio there (1.05).
- No effect at stride 16: both explanations predict this, because the per-hop time there is L1-bound.
- Bandwidth tests: bw_mem_rd at 16.78 MB has two levels (about 0.79 against 1.00, ratio about 1.26) in 4-8 of 10 iterations per boot. At 33/67 MB it is low only in kvmoff iteration 9, nvhe iteration 5 and vhe iteration 10, in the same iterations as their 16.78 MB lows. bw_mem buffers are also recycled between processes, so this does not separate E1 from E2.
- Non-quiesced run: E1 alone cannot make it 6-14% slower at 12-64 MB, with bzero bandwidth 12% lower. However, the quiesced VHE boot itself sits 3-11% above kvmoff/nvhe at 12-64 MB, with 3-5% lower bandwidth. A per-boot factor of that size therefore exists without any noise. nn#16's two-factor fit is post hoc.
- Is 'a state that changes from one child to the next' testable in the existing data? Essentially no.
  - Within a sweep, neighbours in time are also neighbours in allocation.
  - Across benchmarks within an iteration I tested association between counts, with permutations inside each boot. High 8 MB count against fast random count: r = +0.21 (wrong sign), p = 0.20. High 8 MB count against low bw16: p = 1.0. Fast random against low bw16: p = 0.11. So there is no evidence of a minutes-long shared state, and none against child-scale switching.
  - Cross-stride independence also holds (72 same against 78.8 expected). This is equally what E2 predicts if each stride's 64 MB child resets the pool. The N80's 'persisted over 32 sweeps' is a degenerate always-scattered state, so it is not an informative contrast.

(3) DO THE QUIESCED RANDOM-ACCESS 'FAST' VALUES SHOW THE SAME STATE?
- They are a continuum, not two states: 8 of 35 values reach the non-quiesced level, 16 of 35 are only 4-10% below the median, and 11 are at 64 MB, mostly partial.
- That fits partial overlap of the best repetition with a fast window. At 64 MB a random repetition lasts about 0.8 s; every timing lasts at least 100 ms, because benchmp is called with enough = 100000.
- Exp H6 excludes page order, but the N80's 'natural' buffer read 1.134 times 'sorted' at 6 MB in the same experiment, so physical placement is not zero.
- That a platform state exists on the quiesced N90 is plausible. That it is the same state as the sequential 8 MB levels is untested.

(4) HAND-OVER ARGUMENT (nh#3)
- Robust to the threshold (1.08-1.15), to the normalization, and at strides 128-1024 in three boots.
- Not at stride 64 (3 of 4 highs carried over) and weaker in the VHE boot (10/28).
- Its premise rests on 4 sweeps at one stride on another machine. The Clopper-Pearson 95% lower bound for the N80 hand-over rate is 0.40.
- The same sweeps show an untraced hand-over break at 6 to 8 MB in 3 of 4 cases.
- On the N90, THP 'never' lowers the floor of the per-CPU list limit. That THP was 'never' rests only on the script default; nothing in the June results records it.

JUDGEMENT THE EVIDENCE SUPPORTS: "On the N90 most high 8 MB values (about three quarters) are isolated. The 12 MB point of the same sweep is at the normal level with no partial elevation, and their frequency depends strongly on the stride (1/40 at stride 64 against about half at 128-1024). No layout mechanism tested on the N80 produces this if the N80's frame hand-over also holds on the N90. A platform state switching per child (for example interconnect frequency) is consistent with it but has not been measured on any machine. About a quarter of the highs carry over several sizes or strides, mainly in one boot; layout and a longer-lived platform state explain these equally. Both levels occur at similar rates in all four boot modes (22-28 of 50), so the +3.55% is a difference in counts, not a protected-mode overhead."

WHAT A CAREFUL REVIEWER WOULD STILL OBJECT TO
- No mechanism was measured on the paper's machine.
- The N80 used for mechanism claims differs in mode (protected only), load (desktop, background pVM), THP and memory size.
- The grouping of the N90 data was chosen after the fact.
- The non-quiesced run's settings (THP, governor) are unrecorded.
- The 8 MB point is bistable from an uncontrolled factor, so the paper should report its distribution or median across iterations, not a mean difference.

MEASUREMENTS THAT WOULD SETTLE IT ON THE N90
Without a settings change:
- (a) Read the devfreq governors and limits read-only in the June environment. If there is no nocfreq or the governor is 'performance', the interconnect-frequency form of E1 is out.
- (b) Run run30 (paper's command, frames per child, interconnect sampled every 100 ms), alternating instrumented and uninstrumented sweeps. The python watcher's own traffic could suppress an E1 state driven by traffic.
- (c) A private copy of lat_mem_rd that prints all 11 repetition times per child. E1 predicts children with mixed fast and slow repetitions; E2 predicts a constant level within each child.
- (d) A fixed-buffer test: one 8 MB buffer timed in 100 ms windows for minutes, interleaved with lmbench's other sizes. A level that switches within one buffer means a platform state; a constant level per buffer that varies between fresh buffers means layout (with root, add pagemap).
- (e) Alternate 8 MB sequential and 64 MB random windows in one process and check whether the fast windows coincide in time.
With a settings change:
- (f) Pin the interconnect governor (performance, powersave, simple_ondemand) while recording frames, as G5 does on the N80.
- (g) Enable THP (madvise) to run layoutshim sorted/shuffled8 on the N90 itself in kvmoff and pkvm boots. Two levels with sorted buffers means E1. This also measures the N90's own layout ratio per stride and its dependence on stage-2.

## Defects

- **weakens** | nh#4 (judgement) and worklog 11.32 / memlat-rootcause 4.3: Treats all high 8 MB values as one phenomenon. They split into isolated highs (72/93: 1/40 at stride 64 against 16-22/40 at strides 128-1024, Fisher p about 3e-8) and carried runs (21/93: 3/6/5/1/5 per stride, roughly the same at every stride; 3 of the 4 highs at stride 64 are carried; whole-sweep runs at strides 32, 64 and 128 in VHE iteration 3 and at stride 64 in VHE iteration 8; in the VHE boot the next size is high after a high one in 18/29 cases, against 0/3, 1/7 and 0/7 in the other boots). Effect: 'E1 more likely' is supported for the isolated highs only. The carried runs fit a persistent scattered-frame pool (E2) as well as a long-lived state. The judgement should be worded per kind of high, not globally.
- **weakens** | nh#4: 'the level at one stride is independent of the level at the previous stride, whereas on the N80 a scattered state persisted over all 32 sweeps': Cross-stride independence (I get 72 same against 78.8 expected over strides 64-1024) is also what E2 predicts if each stride's 64 MB child (16385 pages) flushes the per-CPU pool. The N80 contrast is a degenerate state: always scattered, under a desktop session. Effect: This point does not discriminate between E1 and E2 and should be dropped from the list of support for E1.
- **weakens** | nh#4: random-access 'fast' values 'with a ratio of the two states (1.23-1.27) like that of the two sequential levels': The 35 values form a continuum: 0.785-0.96 of the boot median, only 8 at or below 0.81, 16 at 0.90-0.96, and 11 of 35 at 64 MB, mostly partial. They are not two states. No iteration-level association exists with the high 8 MB counts (r = +0.21, the wrong sign for a shared state; p = 0.20 by permutation within boot). Exp H6 excludes page order, but the N80 'natural' buffer read 1.134 times 'sorted' at 6 MB in the same experiment. Effect: That some platform state exists on the quiesced N90 is plausible. That it is 'the same state' as the sequential levels is unsupported, and the 1.23-1.27 ratio describes only the extreme values.
- **weakens** | nh#3 (hand-over inference): The premise comes from 4 sweeps at one stride on the N80 (Clopper-Pearson 95% lower bound 0.40 for the hand-over rate), whose own 6 to 8 MB step broke in 3 of 4 sweeps for an untraced reason. Transfer to the N90 (32 GB, THP 'never', a lower floor for the per-CPU list limit) is assumed. The argument also fails at stride 64 (3 of 4 highs carried) and is weaker in the VHE boot (10/28). Effect: For strides 128-1024 in three boots the argument is robust to the threshold (1.08-1.15) and to the normalization: no diluted carry-over, mean 12 MB difference -0.005 to +0.015, p > 0.1. As a statement about all strides and boots it is too strong. Source reading supports its direction: drained order-0 frames would be served first again.
- **weakens** | nn#14 / nn#17(b) ratio agreement, still cited in rootcause 4.3 as E2's demonstrated sensitivity: The N80 layout ratios were measured with a host stage-2 (protected mode). The N90 level ratio is the same in boots with and without a stage-2 (kvmoff 1.15-1.22, pkvm 1.18-1.23). The only same-core machine without a stage-2 shows smaller ratios at strides 64-256 (1.11, 1.06, 1.08). The agreement is about 1.2 at every stride with a dip at 1024, and the N90 bootstrap intervals are 0.03-0.07 wide. In the only N90 sweep where the state reached stride 32, its size (1.08-1.11) is about twice the N80 layout ratio (1.05). Effect: The agreement is not E2-specific; a memory-path slowdown of about 20% fits it equally. Its weight as E2 support was overstated, which is consistent with the current lean but should be said explicitly.
- **cosmetic** | nh#2 wording: Two wording issues. The group ranges are 0.962-1.105 and 1.15-1.284, not '0.94-1.10 and 1.22-1.30'; four values (1.15, 1.177, 1.199, 1.207) lie in the band E2 would predict. The pooled normalization mixes boots whose 12-64 MB baselines differ by 3-11% (VHE, pkvm), so the '1.04-1.12' category is largely a boot offset. Effect: Minor. The main counts reproduce, and the conclusion survives per-boot normalization.
- **weakens** | nn#16 / rootcause 5.1 (non-quiesced run needs a second factor): A per-boot slowdown of the same size (3-11% at 12-64 MB, bandwidth 3-5% lower) exists in the quiesced VHE boot without any background noise, so the non-quiesced run's offset is not unique evidence for scattered buffers. The bandwidth of the non-quiesced run at 16 MB and above is 6-12% lower, which contradicts 'faster platform' alone. Effect: Both candidates need an unexplained per-boot factor. The two-factor reading (layout times platform) is a post hoc fit, not evidence.

## Discrepancies

- nh#2: lower group after a high 8 MB point spans 0.962-1.105 (claim 0.94-1.10); upper group spans 1.15-1.284 (claim 1.22-1.30). Values in 1.10-1.22: 6 strictly inside, 7 counting 1.10 itself.
- nh#2 counts reproduce exactly with pooled normalization (93; 57/16/19; 83/21/3; 16/24/32 MB high 12/9/7). Normalized per boot by the minimum, they are 96; 62/13/21 at 12 MB.
- Cross-stride independence: over strides 64-1024 with per-boot minimum normalization I get 72 same against 78.8 expected, a slight anti-correlation; the worklog cites 61 against 60.3. Both mean independence.
- Random-access 'fast' values: count and range reproduce (35 values in 22 iterations, 0.785-0.96), but the distribution is continuous, not two states.
- H7: overlap 2033-2034 of 2049 confirmed, and the frames sit in exactly reversed positions. In 3 of 4 sweeps the 6 to 8 MB step kept only 0.205-0.631 of the frames.
- H8: all ratios reproduce to 0.001. At 32-64 MB, stride 256, head8 sits 1.5-2.3% above the linear-share line (1.100/1.079/1.068 against 1.084/1.057/1.044).
- nn#14 levels reproduce exactly. The workstation's stride-256 ratio at 8 MB is 1.076 (H4); the stride-128 ratio from H5 is 1.055.

## Threats to validity

- Nothing about frames or the interconnect was recorded on the N90; every E2 mechanism (hand-over, linear share) is carried over from the N80, which was in protected mode with a desktop session, a background pVM and THP 'always' (lmbench ran under nothp).
- The grouping of the N90 data was chosen after looking at it (the analyst says so); my isolated-versus-carried split is also post hoc.
- Small counts: 4 highs at stride 64, 1 sweep with the state at stride 32, and the carried runs concentrated in one boot (VHE).
- The N80 hand-over was observed in 4 sweeps at a single stride; the 6 to 8 MB break is unexplained.
- THP 'never' and the interconnect governor on the N90 in June are unrecorded (THP rests only on the prepare-host.sh default); the non-quiesced run's settings are unknown.
- The workstation layout data (H5, D80F3) were taken at loadavg 6.09 on a shared machine.
- Normalization choices (pooled lower-half median, per-boot minimum, per-boot second smallest) move the counts by a few sweeps; the conclusions above held under all three.
- E1 has not been measured at any interconnect frequency other than 1800 MHz on any machine.

## Recomputed tables

**A. 12 MB point after a high or low 8 MB point** (strides 64-1024, 200 sweeps)

| normalization | threshold | 8 MB high: n | 12 MB <1.04 | 12 MB 1.04-thr | 12 MB >thr | 8 MB low: <1.04 / mid / >thr |
|---|---|---|---|---|---|---|
| pooled lower-half median | 1.08 | 100 | 62 | 13 | 25 | 79 / 19 / 2 |
| pooled lower-half median | 1.12 | 93 | 58 | 16 | 19 | 83 / 21 / 3 |
| pooled lower-half median | 1.15 | 81 | 49 | 16 | 16 | 92 / 22 / 5 |
| per-boot minimum | 1.12 | 96 | 62 | 13 | 21 | 91 / 10 / 3 |

**B. Isolated versus carried highs at 8 MB**, per stride (40 sweeps each; normalized by the per-boot second-smallest value, threshold 1.12)

| stride | 32 | 64 | 128 | 256 | 512 | 1024 |
|---|---|---|---|---|---|---|
| isolated (8 MB high, 12 MB not) | 0 | 1 | 22 | 16 | 16 | 18 |
| carried (8 MB and 12 MB high) | 0 | 3 | 6 | 5 | 1 | 5 |

- Mean 12 MB value after a high against after a low 8 MB point, excluding full highs: difference -0.005 to +0.015, all p > 0.1. The H8 prediction is 1.157 (stride 128) and 1.188 (stride 256).
- Alternation (16 MB high after 8 MB high and 12 MB low): 0 of 73.

**C. Per boot** (strides 64-1024)

| boot | 8 MB high | P(12 MB high given 8 MB high) | P(next size high given high, 12-48 MB) |
|---|---|---|---|
| kvmoff | 25/50 | 3/25 | 0/3 |
| nvhe | 21/50 | 3/21 | 1/7 |
| vhe | 28/50 | 10/28 | 18/29 |
| pkvm | 22/50 | 5/22 | 0/7 |

**D. N90 level ratio at 8 MB** (pooled; 95% bootstrap interval) against the N80 shuffled8/sorted ratio and the workstation ratio

| stride | 64 | 128 | 256 | 512 | 1024 |
|---|---|---|---|---|---|
| N90 | 1.221 (1.195-1.238) | 1.219 (1.199-1.233) | 1.207 (1.173-1.226) | 1.212 (1.181-1.224) | 1.162 (1.107-1.178) |
| N80 | 1.230 | 1.202 | 1.193 | 1.207 | 1.169 |
| workstation | 1.112 | 1.055 | 1.076 | 1.134 | 1.216 |

**E. Exp H8** (N80, medians of three repetitions), ratio to sorted

| size | head8, stride 128 | shuffled8, stride 128 | head8, stride 256 | shuffled8, stride 256 |
|---|---|---|---|---|
| 8 MB | 1.210 | 1.210 | 1.203 | 1.198 |
| 12 MB | 1.157 | 1.235 | 1.188 | 1.282 |
| 16 MB | 1.117 | 1.242 | 1.159 | 1.314 |
| 24 MB | 1.080 | 1.242 | 1.122 | 1.338 |
| 64 MB | 1.037 | 1.242 | 1.068 | 1.354 |

**F. Association between iterations** (40 iterations; permutation within boot, two-sided p)

| pair | p |
|---|---|
| high 8 MB count vs fast random count | 0.20 (r = +0.21) |
| high 8 MB count vs low bw_mem_rd at 16.78 MB | 1.0 |
| fast random count vs low bw_mem_rd at 16.78 MB | 0.11 |
| high 8 MB count vs high 12-64 MB count | 0.005 (driven by VHE iteration 3) |

**G. Per-boot baseline at 12-64 MB** (boot median / kvmoff+nvhe low level)

| boot | ratio |
|---|---|
| vhe | 1.03-1.11 |
| pkvm | 1.02-1.08 |
| non-quiesced nVHE | 1.06-1.14 |
