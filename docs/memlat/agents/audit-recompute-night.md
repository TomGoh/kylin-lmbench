# 核查报告：audit:recompute-night

## Summary

I rebuilt every table in scope from the raw logs with my own parsers (Python 3 standard library only; no analyst analyze-*.py read beforehand). Scripts are in <scratch>/wf5/audit-recompute-night/ (lib.py, hlib.py, a_expN.py to k4_misc.py) and their outputs are in out/*.txt.

**What reproduces to the printed digit:**
- Exp N, N2, N3, N4, N5, L2, H2, H3, H4, H5, H6, H8 in derived/state-tables.md.
- The H7 tables.
- The N90 level, count, non-quiesced, two-factor and "after a high 8 MB point" tables in host-n90-tables.md (sections 6, 8, 9).
- The night2/night3 claim numbers nn#1 to nn#16 and nh#1 to nh#3.
- I also checked all 13,150 lat_mem_rd rows of the five N90 CSVs against the raw iter reports: 0 mismatches.

**Discrepancies larger than rounding.** All are in prose; none is in a derived table.
1. Worklog 11.19 says the cycle estimate agrees with the counted cycles "within 0.3". The largest difference of medians is 0.36 (16384 x 1) and per process it reaches 1.13.
2. Worklog 11.24 says the 12/16/24 MB values are "11.1-11.6 ns". In H2 the 24 MB values reach down to 10.89 and the 12 MB values to 11.09.
3. Worklog 11.30 and rootcause 4.3 (third part) and 4.4 say every child holds all of the previous child's frames, except at 6 to 8 MB, in all four sweeps. This is false.
   - In sweep 4 the 16 MB child got only 2555 of the 3073 frames of the 12 MB child (83%).
   - Elsewhere the share is 96-100%, not 100%.
   - Worklog 11.31 says half of the 16 MB buffer is the 8 MB child's frames. That holds in 3 of 4 sweeps; in sweep 4 it is 37% (1519 frames).
   - The claim that matters most (8 MB to 12 MB: 2033-2034 of 2049 frames in 4 of 4 sweeps) is confirmed.
4. Rootcause 4.3 (fifth part) and worklog 11.32 say the 8 MB points of adjacent strides took the same level "61 of 120, expected 60.3". I get 62 (35 both high + 27 both low), with 59.6 expected within each configuration or 60.2 pooled. The conclusion (no dependence) is unchanged.
5. nh#4 gives the ratio of the two random-access states as 1.23-1.27. It is 1.22-1.27; 48 MB gives 1.224.
6. The caption of the N5 table says the reference is "the median of 1024 x 2 at the same touch order". The script (analyze-state-experiments.py line 1261) also drops processes with ev17 >= 0.05: chain-order 1024 x 2 had two crowded processes at 26.0 and 28.9 cycles. The effect is about 0.02 cycles per walk.
7. N3 (nn#3) says L2 refills stay below 0.002 and walks at 0.94-0.96 per hop. That holds for cell medians only; per pass, walks span 0.930-0.983 and refills reach 0.0054.

**Interpretive findings from the recomputation:**
- **N2 to N5 regression (nn#5, rootcause 3.8):** nn#5 blames the spread of the per-experiment coefficients on collinearity alone.
  - Adding the share of pages in slot 0x83 (the GiB slot holding most of the VM's 2 MiB regions) lifts the pooled R² from 0.67 to 0.86 (coefficient +6.1, s.e. 0.8).
  - In N4 alone R² goes from 0.46 to 0.99 (+8.7, s.e. 0.4).
  - In N2 the same regressor is -0.24 (s.e. 0.56): reps 8-9 had 25-34% of their pages in 0x83 and the lowest cost (24.0-24.1 cycles per walk).
  - So an unrecorded factor differs between experiments. Neither the regions term nor the 0x83 share is a stable explanation. An earlier verifier found the 0x83 term; the contradiction in N2 is new here.
- **Two-factor check (nn#16):** the drop of the coefficient of variation (5.1% to 3.1%) comes entirely from the 6 MB column.
  - At 8 MB and above (35 cells) the fast-state/low ratio already has a CV of 2.7%, the quotient 3.2%, and the correlation with the layout ratio is r = 0.22.
  - The real support is the 3-4 MB cells (r = 0.92, n = 10). The rootcause doc says this; the nn#16 claim does not.
- **N2 time order:** in the clean 2048 x 1 N2 fit (r = +0.98) the candidate share is confounded with time and amount held back. Reps 1-3 (share 0.33-0.43) all come before reps 4-12 (share 0.14 or less), so the 12 points form two clusters.
- **N3 run order:** within each seed the six shares ran in fixed ascending order, about 3 s apart. All six interior points lie 0.07-0.39 cycles above the straight line between the endpoints: a mild concave bend, not significant (quadratic term -0.65 ± 0.59). The 0x8b:0x8c against 0x88:0x89 controls (40.40 against 37.09) back a real slot effect.
- **nn#11:** its mechanism ("the per-CPU list holds about 1600 pages") is contradicted by H7. The list held 13-17 thousand pages, with a high of 13-18 thousand, at the start of sweeps 2-4. The analyst corrected this in worklog 11.30, but night2.json still carries the old wording.

**Not covered:** X1/X2/X3, Y, Z, V3 and T2 were outside the recompute list (a)-(k) and were not recomputed.

## Defects

- **weakens** | docs/memlat/memlat-investigation-worklog.zh-CN.md 11.30 (lines 1499-1500); docs/memlat/memlat-rootcause.zh-CN.md 4.3 part 3 (line 638-639) and 4.4 (line 706): These lines say every child buffer holds ALL frames of the previous child, except at 6 to 8 MB, in all four H7 sweeps. Recomputed from expH7-pfns.log, the step 12 MB to 16 MB in sweep 4 hands back only 2555 of 3073 frames (0.831). Other steps hand back 0.96-1.00, not exactly all: for example 4 MB to 6 MB gives 984-999 of 1025, and 8 MB to 12 MB gives 2033-2034 of 2049. Worklog 11.31 says half of the 16 MB buffer is the 8 MB child's frames; this holds in sweeps 1-3 (0.496) but not in sweep 4 (0.371, 1519 frames). Effect: The nh#3 argument uses only the 8 MB to 12 MB step, which holds in 4 of 4 sweeps, so its core stands. The wording 'all, every time' overstates how reliable the hand-back is. On the N80 itself the hand-back failed at two different steps within four sweeps (6 to 8 MB in 3 of 4, 12 to 16 MB in 1 of 4). That weakens the claim that a failed hand-back on the N90 would be implausible.
- **weakens** | night2.json nn#5 and worklog 11.23 (pooled N2+N4+N5 regression); rootcause 3.8 limitations: nn#5 attributes the different per-experiment coefficients to collinearity of share and regions. A third regressor was left out: the share of pages in slot 0x83 (the VM's main GiB slot). Pooled fit: R² 0.67 to 0.86, coefficient +6.08 (s.e. 0.77). N4 alone: R² 0.46 to 0.99, +8.70 (s.e. 0.40). N2 alone: -0.24 (s.e. 0.56); in N2 reps 8-9 had s83 = 0.25-0.34 at the lowest cost per walk (24.09 and 24.02 cycles). Effect: probe3 costs more than frames2 because of 'candidate share plus more 2 MiB regions': this is not established. An unrecorded factor differs between N2, N4 and N5, and it is not simply 'pages in slot 0x83' either. The rootcause already says probe3 numbers are only directional and frames2 is authoritative, so the class values (24.1 and 28.0 cycles per walk) are unaffected.
- **weakens** | night2.json nn#16; derived/state-tables.md 'Two-factor check' summary line: The claim gives the CV of fast-state/low as 5.1% and of the quotient as 3.1% over 40 cells (6 MB and above), as support. Recomputed, the whole reduction comes from the 6 MB column. For the 35 cells at 8 MB and above: FL CV 2.7% (sample), quotient CV 3.2%, Pearson(FL, layout ratio) 0.22. Over all 40 cells r = 0.79 only because of the 6 MB column. The supporting signal is in the 3-4 MB cells (r = 0.92, n = 10). Effect: The 'scattered pages on a faster platform' reading of the non-quiesced run rests on 10-15 small-size cells, not on 40. The rootcause doc (4.3 part 4) already carries this caveat; the claim text does not.
- **weakens** | night2.json nn#11 (INFERENCE about the cause): The claim says the per-CPU list of cpu0 holds about 1600 pages and that the 8 MB child is the first that must go to the buddy allocator. expH7.log shows Normal-zone pcp count/high of 17146/17279, 17336/18028 and 13382/13444 at the start of sweeps 2-4, and 18766/19747 at the end of sweep 1. The 8 MB child was still scattered in every sweep (runs 1634-2047 of 2049). Effect: The inference is refuted by H7. The analyst corrected it in worklog 11.30 and rootcause 4.4, but night2.json still states it.
- **cosmetic** | docs/memlat/memlat-investigation-worklog.zh-CN.md 11.24 line 1251: '12、16、24 MB 也不变（11.1–11.6 ns）': in expH2.log the 24 MB values span 10.89-11.62 (rep 4 at holds 2048/2560: 10.89, rep 3 at hold 1024: 10.91, rep 3 at hold 2560: 10.92, rep 4 at hold 0: 10.99) and 12 MB reaches down to 11.09. Effect: None for the conclusion: the medians by hold show no trend (24 MB: 11.25, 11.14, 11.51, 11.07). Only the quoted range is wrong.
- **cosmetic** | docs/memlat/memlat-investigation-worklog.zh-CN.md 11.19 line 909: The line says the cycle estimate agrees with the hardware counter within 0.3. The medians differ by up to 0.36 (16384 x 1: 66.92 against 66.56; 2048 x 1: 0.29); single processes differ by up to 1.13 (16384 x 1, seed 4). night2 nn#1 and rootcause 3.8 say 0.4, which is correct. Effect: None.
- **cosmetic** | rootcause 4.3 part 5 item 2 (line 664) and worklog 11.32 line 1582: '120 次里相同的 61 次，独立时预期 60.3': recomputed from the four quiesced N90 CSVs with the 12% rule, the stride pairs 128/256, 256/512 and 512/1024 agree in 62 of 120 (35 both high, 27 both low). The expected value is 59.6 within configurations, 60.2 pooled. The '61' equals the count of high values at the second stride (61) in host-n90-tables section 8. Effect: None; independence still holds.
- **cosmetic** | night3.json nh#4: The ratio of the two random-access states (quiesced nVHE / non-quiesced) at 12-64 MB is 1.271, 1.256, 1.240, 1.237, 1.224, 1.233, i.e. 1.22-1.27, not 1.23-1.27. Effect: None.
- **cosmetic** | derived/state-tables.md Exp N5 caption; experiments/memlat-probe/analyze-state-experiments.py line 1261: The caption says 'median cycles of 1024 x 2 at the same touch order'. The code also drops 1024 x 2 processes with ev17 >= 0.05: chain order had two at 26.02 and 28.85 cycles. The true median is 14.008 with them and 13.989 without. As a result the cycles per walk differ from the caption's method by about 0.02 (rep 1 chain 26.54 against 26.52; residual maximum +1.46 against +1.44). Effect: None; 16 of 22 within 1.0 and all residuals positive either way.
- **cosmetic** | night2.json nn#3: 'L2-cache refills are below 0.002 per hop and page walks 0.94 to 0.96 per hop in all walk configurations' holds for cell medians only. Per pass, walks span 0.930-0.983 and L2 refills reach 0.0054. Effect: None.

## Discrepancies

- Worklog 11.19: the estimate and the counter agree 'within 0.3'. Recomputed: up to 0.36 on medians (16384x1) and 1.13 for single processes. Claim nn#1 and rootcause 3.8 say 0.4, which is correct.
- Worklog 11.24: '12/16/24 MB unchanged (11.1-11.6 ns)'. Recomputed: 24 MB spans 10.89-11.62 and 12 MB 11.09-11.47 (expH2.log).
- Worklog 11.30, rootcause 4.3 part 3 and 4.4: 'every child contains all frames of the previous child (except 6 to 8 MB), in all four runs'. Recomputed: sweep 4, 12 MB to 16 MB: 2555/3073 = 0.831. Other steps 0.96-1.00. 8 MB to 12 MB confirmed at 2033-2034 of 2049 in 4/4.
- Worklog 11.31: '16 MB child is half 8 MB frames'. Recomputed: 0.496 in sweeps 1-3, 0.371 in sweep 4.
- Rootcause 4.3 part 5 and worklog 11.32: adjacent-stride 8 MB levels 'same 61 of 120, expected 60.3'. Recomputed: same 62 of 120, expected 59.6 (within configuration) or 60.2 (pooled).
- nh#4: state ratio '1.23-1.27'. Recomputed: 1.22-1.27 (48 MB 1.224).
- N5 table caption against code: the reference also excludes 1024x2 processes with ev17 >= 0.05 (not stated). Effect on cycles per walk about 0.02.
- nn#3: walks 'from 0.94 to 0.96' and L2 '< 0.002' hold only for cell medians. Per pass: 0.930-0.983 and up to 0.0054.
- nn#16 states the CV reduction 5.1% to 3.1% as support. At 8 MB and above (35 cells) the quotient is more dispersed than the raw ratio (3.2% against 2.7%); r(FL, LR) = 0.22 there. The rootcause doc notes this; the claim does not.
- nn#5 'coefficients differ because the two regressors correlate' is incomplete: the slot-0x83 share explains N4 (R² 0.46 to 0.99) but has the opposite sign or none in N2 (-0.24 ± 0.56).
- nn#11 inference ('per-CPU list about 1600 pages, 8 MB child first to hit the buddy allocator') is contradicted by expH7.log pcp counts of 13-17 thousand pages at sweep starts. The analyst corrected it in worklog 11.30, but night2.json still carries it.
- Matched to rounding (no discrepancy): every number in state-tables.md for N, N2, N3, N4, N5, L2 (both machines), H2, H3 (8/16/64 MB tables and by-size Spearman), H4 and H5 (both machines), H6, H7 (all four sweep tables), H8, the two-factor tables; host-n90-tables sections 6, 8, 9 (quartiles differ by 0.001 at two cells from the interpolation method); worklog 11.19-11.32 tables; rootcause 3.8 table (N80 ascending cyc_est), 4.3 tables, subset level ratios (no stage-2 1.23/1.22/1.21/1.21/1.13, protected 1.21/1.23/1.20/1.20/1.18), 16-64 MB high/low 1.087-1.129, 3-4 MB r = 0.92, the 35 random-access values in 22 iterations 3-21% low.

## Threats to validity

- One process per cell in N2, N4 and N5. Each of the 12 or 8 repetitions is a single process at a different amount held back, so repetition, hold amount and wall-clock time are perfectly confounded. In N2 the clean 2048x1 share is bimodal: reps 1-3 at 0.33-0.43 and reps 4-12 at 0.14 or less. The r = +0.98 is essentially a two-cluster contrast.
- N3: within each seed the shares ran in fixed ascending order about 3 s apart (all of seed 61, then 67, then 71), so share is confounded with a 15 s time ramp. The cross-pair controls (40.40 against 37.09) are the evidence that is not ordered.
- Estimator mixing across machines: N80 'cycles' are counted ev11 (N2, N3, N4, N5) or the estimate cyc_est (N, rootcause 3.8). The workstation has the estimate only, and its walks per hop are unknown (assumed 0.95). nn#6 also mixes programs: frames2 class values on the N80 against probe3 on the workstation.
- Workstation runs were made on a shared, loaded machine (loadavg 5.3-6.8, governor ondemand) and spread over 4 (N) or 2 (N4) CPUs. cyc_est relies on the L1 reference in the same process being taken at the same frequency.
- Workstation layoutshim and thplayout adjacency is 'na' (unprivileged), so 'sorted' there is physically ordered within each 2 MiB huge page but its order across huge pages is unverified.
- L2, H4, H5, H6 and H8 cells are small: n = 2-4 sweeps per layout (H5: 2 for six strides). L2's n = 6 comes from 3 processes with 2 lines each, so the lines are not independent. Order within each rep was fixed (sorted first).
- Interconnect frequency was read only at the start and end of each sweep (H5 sweeps last about 4.4 min). 'Fixed at 1800 MHz' during a sweep is assumed, not sampled.
- H3 matches each pagemap sample (taken about 0.25 s after the child appeared, 0.69-0.93 s before its output line) to the next output line. All 396 matched by page count at MB sizes. Pages that are not yet faulted or that are migrated later would not be seen.
- H2 has no frame data: 'scattered in all 32 N80 sweeps' (nh#4) rests on frame data for 16 sweeps (H3 12 + H7 4). For the 16 H2 sweeps it is inferred from the latency value.
- N90 two-level rule: 'high = more than 12% above the median of the lower half of 40 values' is arbitrary. At stride 128, 8 MB, the 'low' group (n = 12) contains values up to 10.735 ns, 15% above its own median, so intermediate values are absorbed into 'low'. Counts of high values move with the cut.
- N90 low and high levels pool 30 non-stage-2 values with 10 protected values. Ratios compared with the N80 come from protected mode only.
- The two-factor check divides N90 ratios by N80 layout ratios from another machine and kernel. Its support comes from the 3-6 MB cells only (see the defects).
- nh#3 and the H8 linear-share argument assume the N90 low level corresponds to contiguous buffers. With H7 showing hand-back failures at 6 to 8 MB (3/4) and 12 to 16 MB (1/4) on the N80, the probability of a hand-back failure on the N90 is not well bounded by 4 sweeps.
- All N80 night data carry the running protected VM in the background and THP 'always'. N5 measured the shared share only for its own buffers (0.004-0.0625), not for N2 or N4.
- Not recomputed in this audit: X1/X2/X3, Y, Z, V3, T2 (outside list (a)-(k)). Values quoted from Exp Z (for example 33.6 cycles per walk for the shared class) were not re-derived here.

## Recomputed tables

### (a) Exp N: cycles per hop, median (min-max), n; N80 PMU median, walks, L2 (min-max); D80F3 cyc_est; per-CPU medians (cpu 0/4/5/7)
| pages x lines | N80 cyc_est | N80 ev11 | walks | L2 refills | D80F3 cyc_est, n | per CPU | N80-D80 |
|---|---|---:|---:|---|---|---|---:|
| 2048x1 | 39.39 (38.98-39.87), 5 | 39.68 | 0.959 | 0.003 (0.002-0.004) | 24.96 (24.49-25.15), 20 | 24.90 24.95 24.98 25.00 | +14.43 |
| 256x16 | 14.37 (14.29-14.40) | 14.38 | 0.000 | 0.014 (0.010-0.016) | 14.53 (14.25-14.90) | 14.52 14.38 14.71 14.70 | -0.16 |
| 512x8 | 14.47 (14.19-14.68) | 14.58 | 0.000 | 0.022 (0.006-0.030) | 14.49 (14.24-15.13) | | -0.02 |
| 1024x4 | 14.54 (14.33-14.70) | 14.57 | 0.000 | 0.023 (0.011-0.029) | 14.58 (14.35-14.77) | | -0.03 |
| 2048x2 | 40.52 (39.40-40.93) | 40.75 | 0.944 | 0.065 (0.056-0.073) | 25.86 (25.43-26.26) | | +14.67 |
| 4096x1 | 42.55 (42.31-43.94) | 42.61 | 1.001 | 0.091 (0.075-0.153) | 27.99 (27.82-28.33) | 28.20 27.92 28.00 28.02 | +14.55 |
| 8192x1 | 54.27 (53.87-56.84) | 54.30 | 1.010 | 0.621 (0.604-0.741) | 38.18 (37.93-39.62) | | +16.10 |
| 16384x1 | 66.56 (66.27-68.36) | 66.92 | 1.018 | 1.123 (1.100-1.153) | 50.31 (49.41-51.02) | | +16.25 |
|ev11 minus cyc_est, medians: at most 0.36; single processes: at most 1.13|

### (b) Exp N2 (cycles = ev11; one process per cell)
| config | cycles range | r(c,share) | r(c,reg) | r(share,reg) | r(c,L2) | fit a; b (se); c per 100 reg (se); R² |
|---|---|---:|---:|---:|---:|---|
| 4096x1 | 48.60-80.27 | -0.07 | -0.28 | +0.89 | +0.95 | 75.17; +44.21 (32.46); -5.88 (3.54); 0.24 |
| 1024x4 | 14.28-14.76 | -0.06 | -0.08 | +0.81 | +1.00 | 14.57; +0.01 (0.53); -0.02 (0.09); 0.01 |
| 2048x1 | 36.10-39.40 | +0.98 | +0.84 | +0.84 | +0.43 | 36.29; +6.89 (0.85); +0.04 (0.12); 0.96 |
The per-rep share, regions, cycles, walks and L2 values are identical to state-tables.md lines 466-477. With cyc_est instead of ev11, 2048x1 gives a slope of +6.36 (1.05).

### (c) Exp N3 (ev11, mean of 2 passes; 3 seeds)
| pair | 0% | 12% | 25% | 50% | 75% | 100% |
|---|---|---|---|---|---|---|
| 0x8b:0x88 | 36.88 | 37.29 (+0.41) | 37.95 (+0.95) | 38.70 (+1.90) | 39.78 (+2.84) | 40.39 (+3.51) |
| 0x8c:0x89 | 36.99 | 37.47 (+0.48) | 37.88 (+0.89) | 38.94 (+1.95) | 39.77 (+2.89) | 40.32 (+3.59) |
Linear fit over 36 points: 36.98 + 3.59 (0.16) x share, R² 0.935. Quadratic: b = 4.24 (0.61), c = -0.65 (0.59). Controls: two 1 GiB-candidate slots 40.83/40.40/40.16, median 40.40; two 2 MiB slots 37.49/37.09/36.70, median 37.09. 1024x4 at 0/50/100%: 14.45/14.28/14.39. All six interior points lie above the endpoint line by +0.07 to +0.39.

### (d) Exp N4 (N80 ev11 medians, n = 8; D80F3 cyc_est, n = 16 from cpu0 and cpu4)
| config | N80 chain | N80 asc | Δ | walks chain/asc | D80 chain | D80 asc | N80 asc (cyc_est) - D80 asc |
|---|---|---|---:|---|---|---|---:|
| 1024x2 | 13.99 (13.88-14.99) | 13.96 (13.94-14.00) | -0.03 | 0/0 | 13.97 | 13.96 | -0.00 |
| 1024x4 | 14.60 | 14.54 | -0.06 | 0/0 | 14.54 | 14.54 | -0.01 |
| 2048x1 | 39.85 (37.63-40.65) | 38.25 (36.36-39.86) | -1.60 | 0.956/0.916 | 25.22 | 25.15 | +12.95 |
| 2048x2 | 40.63 | 39.65 | -0.97 | 0.934/0.906 | 26.20 | 26.06 | +13.41 |
| 4096x1 | 50.23 (43.86-57.89) | 42.41 (40.11-43.52) | -7.82 | 0.998/0.993 | 28.12 | 28.16 | +14.18 |
4096x1 chain order: r(L2, l2over) = 0.999; r(cycles, L2) = 0.895; L2 minus l2over = 0.032-0.048. 2048x1 cycles per walk 24.85-27.84; fit 25.68 + 5.85 (2.93) x share, r = 0.47.

### (e) Exp N5 and pooled fit (cycles per walk = (ev11 - 13.97)/walks, 50 clean 2048x1 processes)
N5: 22 clean processes. 16 within 1.0 of the model; residuals +0.08 to +1.44 (+1.46 with a reference of 13.98), all positive. shared_frac 0.0039-0.0625.
| data | n | a | b share (se) | c /100 reg (se) | R² | with slot 0x83 share: d (se), R² |
|---|---:|---:|---|---|---:|---|
| N2+N4+N5 | 50 | 24.19 | +4.87 (1.28) | +0.281 (0.082) | 0.67 | +6.08 (0.77), 0.86 |
| N2 | 12 | 24.06 | +6.99 (0.59) | +0.010 (0.080) | 0.98 | -0.24 (0.56), 0.98 |
| N4 | 16 | 25.13 | -2.30 (4.25) | +0.537 (0.225) | 0.46 | +8.70 (0.40), 0.99 |
| N5 | 22 | 23.56 | +3.38 (1.28) | +0.413 (0.094) | 0.98 | -2.29 (3.33), 0.98 |

### (f) Exp L2 (ns_min median (min-max), n = 6 from 3 processes)
N80 loop/256 shuffled vs sorted: 4 MB +0.4%, 8 MB +21.9% (+53 cycles per page crossing), 16 MB +29.8% (+73), 32 MB +30.2% (+75), 64 MB +29.3% (+73). Unrolled form: 256/16 MB +27.9% (+75); 64/16 MB +22.3% (+101). Reversed: -0.0, +3.0, +6.8, +6.8, +6.8%. Aligned: -4.2 to -1.4%. Walks sorted = shuffled (0.0625 at 32 and 64 MB). D80F3: +0.3, -2.7, +10.1, +8.5, +7.7%; unrolled +6.2% and +8.3%. Every cell equals state-tables.md.

### (g) Exp H2
lmbench 8 MB over 16 sweeps: 10.04-10.46. Medians by hold 0/1024/2048/2560 MB: 8 MB 10.32/10.27/10.23/10.31; 64 MB 11.05/10.54/10.33/10.20. probe3 (ns_min): adjacency >= 0.8 n = 23, median 9.14 (8.80-9.28); 0.72-0.73 n = 8, 9.36-9.61; adjacency 0.00 n = 1, 10.39. Spearman -0.48. Interconnect 1800000 at all 64 readings.

### (h) Exp H3 (396 children matched by time; page counts agree at every MB size)
| size | adjacency | ns | Spearman |
|---|---|---|---:|
| 2 | 0.00-0.88 | 4.45-4.57 | -0.60 |
| 3 | 0.00-0.92 | 4.67-4.73 | -0.68 |
| 4 | 0.00-0.93 | 4.83-4.92 | -0.89 |
| 6 | 0.00-0.85 | 6.90-7.82 | -0.99 |
| 8 | 0.00-0.20 | 10.14-10.44 | -0.81 |
| 12 | 0.00-0.14 | 11.22-11.42 | -0.75 |
| 16 | 0.00-0.14 | 11.30-11.55 | -0.58 |
| 24 | 0.15-0.26 | 11.15-11.58 | -0.57 |
| 32 | 0.20-0.41 | 10.78-11.41 | -0.57 |
| 48 | 0.34-0.60 | 10.39-11.32 | -0.96 |
| 64 | 0.42-0.70 | 10.06-11.05 | -0.89 |

### (i) H4, H5, H6, H8 (lmbench's own ns, median of reps)
- **H4, N80, stride 256, shuffled8/sorted:** 2 MB 1.014, 4 MB 1.007, 6 MB 1.066, 8 MB 1.193 (8.90 against 10.62), 12 MB 1.256, 16 MB 1.280, 24 MB 1.298, 32 MB 1.326, 48 MB 1.310, 64 MB 1.305.
- **H4, N80, 8 MB per rep:** +19.8, +19.0, +19.1, +18.6%.
- **H4, D80F3, shuffled8/sorted:** 1.006, 1.024, 1.031, 1.076, 1.133, 1.061, 1.047, 1.035, 1.039, 1.038.
- **H5, 8 MB, N80 shuffled8/sorted for strides 16-1024:** 1.002, 1.054, 1.230, 1.202, 1.193, 1.207, 1.169.
- **H5, 8 MB, D80F3:** 1.001, 1.009, 1.112, 1.055, 1.076, 1.134, 1.216.
- **H5, 12 MB, N80:** 1.001, 1.054, 1.239, 1.228, 1.256, 1.260, 1.259.
- **H6:** shuffled/sorted 1.036 (1 MB), then 0.988-1.014 from 2 to 64 MB. natural/sorted 0.994-1.041, except 1.134 at 6 MB.
- **H8, head8/sorted (stride 128 / 256):** 8 MB 1.210/1.203, 12 MB 1.157/1.188, 16 MB 1.117/1.159, 24 MB 1.080/1.122, 64 MB 1.037/1.068.
- **H8, head8 minus the linear prediction:** within ±0.009 from 8 to 24 MB; +0.016 to +0.024 at 32-64 MB, stride 256.
- **Shim logs:** all buffers fully backed by huge pages (H4 396, H5 788, H6 132, H8 594).

### (j) Exp H7: share of a child's frames found in the NEXT child (sweeps 1/2/3/4)
| from to | s1 | s2 | s3 | s4 |
|---|---|---|---|---|
| 2 to 3 MB | 1.000 | 0.998 | 1.000 | 0.998 |
| 3 to 4 | 0.988 | 0.987 | 0.988 | 0.987 |
| 4 to 6 | 0.960 | 0.974 | 0.975 | 0.974 |
| 6 to 8 | 0.982 | 0.239 | 0.205 | 0.631 |
| 8 to 12 | 0.9927 (2034) | 0.9922 (2033) | 0.9927 (2034) | 0.9922 (2033) |
| 12 to 16 | 0.998 | 0.999 | 0.999 | **0.831** |
| 16 to 24 | 0.991 | 0.994 | 0.988 | 0.994 |
| 24 to 32 | 0.998 | 0.987 | 0.998 | 0.997 |
| 32 to 48 | 1.000 | 1.000 | 1.000 | 1.000 |
| 48 to 64 | 0.998 | 0.998 | 0.998 | 0.998 |
- **8 MB child's frames as a share of later children:** sweeps 1-3: 0.662 of the 12 MB child, 0.496 of 16 MB, 0.33 of 24 MB. Sweep 4: 0.662, 0.371, 0.248.
- **pcp count/high at the start of each sweep:** 637/1781, 17146/17279, 17336/18028, 13382/13444.
- **New frames in the 8 MB child:** 513, 1655, 1707, 1052, spread over 266, 528, 546 and 431 regions of 2 MiB.

### (k) N90 quiesced host (40 values per stride and size; rule 12% above the lower-half median)
| stride (8 MB) | low, n | high, n | hi/lo | non-quiesced median |
|---|---|---|---:|---:|
| 16 | 2.304, 40 | none | | 2.303 |
| 32 | 2.648, 40 (one value at 2.853) | none | | 2.656 |
| 64 | 4.234, 36 | 5.168, 4 | 1.221 | 4.332 |
| 128 | 9.326, 12 | 11.367, 28 | 1.219 | 9.419 |
| 256 | 10.323, 18 | 12.460, 22 | 1.207 | 10.319 |
| 512 | 9.680, 23 | 11.729, 17 | 1.212 | 9.971 |
| 1024 | 10.848, 18 | 12.607, 22 | 1.162 | 10.971 |
- **12 MB hi/lo for strides 64-1024:** 1.245 (3), 1.244 (6), 1.229 (5), 1.250 (3), 1.172 (5).
- **High 8 MB values per configuration (kvmoff/nvhe/vhe/pkvm):** stride 64 1/0/2/1; 128 8/8/8/4; 256 4/5/7/6; 512 5/3/4/5; 1024 6/5/7/4.
- **Non-quiesced against quiesced nVHE, random access:** 0.978, 1.017, 0.721, 0.646, 0.722, 0.745, 0.787, 0.796, 0.806, 0.809, 0.817, 0.811 (1-64 MB).
- **Non-quiesced against quiesced nVHE, sequential stride 256:** -7.5% at 3-4 MB, -9.2% at 6 MB, -9.6% at 8 MB, +3.6 to +8.5% at 12-64 MB.
- **Two-factor check:** FL (non-quiesced / low) and the quotient FL / layout ratio are identical to state-tables.md lines 1068-1094. Over the 40 cells at 6 MB and above: FL 0.890-1.105 (median 1.051, CV 5.1%); quotient 0.780-0.887 (median 0.850, CV 3.1%). Over the 35 cells at 8 MB and above: FL CV 2.7%, quotient CV 3.2%, r(FL, LR) = 0.22. At 3-4 MB r = 0.92.

After a high or low 8 MB point (strides 64-1024, 200 sweeps; value divided by the lower-half median):
| size | 8 MB | n | quartiles | 0.97-1.04 | 1.04-1.12 | >1.12 | >1.20 |
|---|---|---:|---|---:|---:|---:|---:|
| 12 | high | 93 | 1.004/1.028/1.068 | 57 | 16 | 19 | 16 |
| 12 | low | 107 | 0.999/1.016/1.036 | 83 | 21 | 3 | 3 |
| 16 | high | 93 | 1.001/1.033/1.062 | 54 | 26 | 12 | 6 |
| 16 | low | 107 | 1.000/1.022/1.044 | 76 | 30 | 0 | 0 |
| 24 | high | 93 | 1.000/1.020/1.061 | 56 | 23 | 9 | 5 |
| 24 | low | 107 | 1.000/1.022/1.049 | 70 | 31 | 4 | 0 |
| 32 | high | 93 | 1.004/1.025/1.064 | 59 | 26 | 7 | 3 |
| 32 | low | 107 | 0.999/1.016/1.035 | 83 | 23 | 0 | 0 |
Values of 12 MB after a high 8 MB point between 1.10 and 1.22: 7. Adjacent strides 128/256/512/1024: the same level in 62 of 120 pairs; expected 59.6-60.2.
