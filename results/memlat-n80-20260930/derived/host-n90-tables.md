## 1. Figure 7 memory-latency numbers (pkvm try2 against each baseline)

p = exact two-sided permutation test on the estimator of the row, over all 184756 ways to split the 20 iterations of two boots.

| metric | estimator | kvmoff | nvhe | vhe | pkvm | vs kvmoff (p) | vs vhe (p) | vs nvhe (p) | vhe vs kvmoff (p) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LLC Bnd (seq stride 256, 8 MB) | mean | 11.203 | 11.276 | 11.961 | 11.600 | +3.55% (0.399) | -3.02% (0.403) | +2.87% (0.482) | +6.77% (0.082) |
| LLC Bnd (seq stride 256, 8 MB) | median | 10.815 | 11.410 | 12.447 | 12.123 | +12.09% (0.490) | -2.60% (0.982) | +6.25% (0.671) | +15.09% (0.031) |
| Main Mem (seq stride 256, 64 MB) | mean | 10.381 | 10.302 | 10.784 | 10.411 | +0.29% (0.768) | -3.46% (0.013) | +1.06% (0.257) | +3.88% (0.011) |
| Main Mem (seq stride 256, 64 MB) | median | 10.357 | 10.241 | 10.781 | 10.345 | -0.12% (0.995) | -4.05% (0.006) | +1.01% (0.515) | +4.09% (0.010) |
| Rand Mem (rand stride 16, 64 MB) | mean | 182.209 | 181.104 | 181.207 | 188.135 | +3.25% (0.093) | +3.82% (0.087) | +3.88% (0.073) | -0.55% (0.757) |
| Rand Mem (rand stride 16, 64 MB) | median | 185.233 | 185.045 | 185.428 | 191.730 | +3.51% (0.031) | +3.40% (0.033) | +3.61% (0.045) | +0.11% (0.844) |

Rand Mem, pkvm against kvmoff / vhe / nvhe, exact Mann-Whitney p: 0.011 / 0.009 / 0.009.
The last column compares two boots that have the same translation regime (the kernel runs at EL2 with VHE in both); it shows how large a difference between boots can be without any stage-2.

## 2. LLC-boundary point (sequential, stride 256, 8 MB): per-iteration values (ns)

| config | iter 1..10 | runs >= 11.3 ns | runs >= 12.0 ns | mean | SD | median |
|---|---|:---:|:---:|---:|---:|---:|
| kvmoff | 12.24 10.50 10.19 12.37 12.21 10.98 10.65 12.49 10.06 10.35 | 4/10 | 4/10 | 11.203 | 1.00 | 10.815 |
| nvhe | 10.30 12.43 12.62 9.98 9.93 12.27 12.35 10.55 12.31 10.02 | 5/10 | 5/10 | 11.276 | 1.20 | 11.410 |
| vhe | 11.47 12.62 11.73 12.47 12.45 12.57 10.92 12.45 10.30 12.63 | 8/10 | 6/10 | 11.961 | 0.83 | 12.447 |
| pkvm | 10.70 11.77 12.57 12.56 12.52 10.56 10.25 12.50 10.10 12.47 | 6/10 | 5/10 | 11.600 | 1.07 | 12.123 |

The 40 values form two groups, 9.93-10.70 ns (15 values) and 12.21-12.63 ns (20 values); in between: vhe 10.92, kvmoff 10.98, vhe 11.47, vhe 11.73, pkvm 11.77. The count of 'slow' runs therefore depends on where the line is drawn.

Mean of the runs at or above 12.2 ns / at or below 10.75 ns, per config: kvmoff 12.33 / 10.35; nvhe 12.40 / 10.16; vhe 12.53 / 10.30; pkvm 12.52 / 10.40.

pkvm - kvmoff: mean difference +0.397 ns (+3.55%); Welch t = 0.86 (df = 17.9); exact permutation p = 0.3995 (means), 0.4902 (medians); exact Mann-Whitney p = 0.218; bootstrap 95% interval of the mean difference [-0.47, +1.23] ns (-4.2% to +11.0%).
Fisher exact test on the counts at the 11.3 ns cut (6/10 against 4/10): p = 0.66.
Fisher exact test on the counts at the 12.0 ns cut (5/10 against 4/10): p = 1.00.

Same working set at the other strides, per iteration (ns):

| stride | config | iter 1..10 | mean | pkvm vs kvmoff (means) |
|---:|---|---|---:|---:|
| 64 | kvmoff | 4.24 4.20 4.09 4.14 4.15 4.17 4.10 5.05 4.15 4.09 | 4.240 |  |
| 64 | nvhe | 4.24 4.21 4.26 4.20 4.15 4.15 4.04 4.19 4.18 4.17 | 4.181 |  |
| 64 | vhe | 4.29 4.24 5.21 4.32 4.23 4.36 4.29 5.19 4.26 4.34 | 4.473 |  |
| 64 | pkvm | 4.32 4.33 4.30 4.55 4.26 5.15 4.25 4.25 4.25 4.20 | 4.387 | +3.5% |
| 128 | kvmoff | 9.13 11.18 11.21 10.95 11.18 11.23 11.33 9.81 11.20 11.14 | 10.837 |  |
| 128 | nvhe | 11.44 11.43 11.34 11.28 9.37 11.33 11.41 11.23 11.39 9.10 | 10.932 |  |
| 128 | vhe | 11.50 11.50 11.19 11.48 11.42 11.41 9.40 11.45 11.47 9.25 | 11.006 |  |
| 128 | pkvm | 11.53 11.53 9.42 11.42 9.22 10.73 11.13 9.29 9.40 9.29 | 10.295 | -5.0% |
| 512 | kvmoff | 9.53 11.58 11.43 11.40 11.48 9.47 11.64 9.56 9.61 9.65 | 10.534 |  |
| 512 | nvhe | 9.68 11.70 11.62 9.52 9.57 9.52 9.46 11.53 9.62 10.02 | 10.224 |  |
| 512 | vhe | 9.96 11.93 11.87 11.73 11.77 9.82 9.90 9.89 10.71 9.92 | 10.751 |  |
| 512 | pkvm | 9.94 9.96 9.77 9.82 11.76 11.82 12.08 9.67 11.75 11.77 | 10.834 | +2.8% |
| 1024 | kvmoff | 12.29 12.28 11.09 12.23 12.33 11.89 12.60 10.68 12.35 10.60 | 11.834 |  |
| 1024 | nvhe | 11.46 11.78 10.62 12.34 12.36 12.50 12.32 11.55 12.80 10.86 | 11.858 |  |
| 1024 | vhe | 11.20 12.69 12.65 10.78 12.67 12.35 12.67 12.65 10.88 12.65 | 12.119 |  |
| 1024 | pkvm | 11.94 10.65 12.64 10.64 10.73 12.68 12.62 10.73 10.84 12.76 | 11.625 | -1.8% |

Neighbouring sizes at stride 256 (mean and coefficient of variation per config):

| size | kvmoff | nvhe | vhe | pkvm | pkvm vs kvmoff | pkvm vs vhe | vhe vs kvmoff |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 MB | 5.49 ns, CV 0.1% | 5.48 ns, CV 0.1% | 5.48 ns, CV 0.1% | 5.48 ns, CV 0.2% | -0.1% | +0.0% | -0.1% |
| 6 MB | 8.29 ns, CV 1.7% | 8.23 ns, CV 0.9% | 8.32 ns, CV 1.1% | 8.38 ns, CV 1.6% | +1.0% | +0.7% | +0.3% |
| 8 MB | 11.20 ns, CV 8.9% | 11.28 ns, CV 10.6% | 11.96 ns, CV 6.9% | 11.60 ns, CV 9.2% | +3.5% | -3.0% | +6.8% |
| 12 MB | 10.98 ns, CV 3.9% | 10.86 ns, CV 2.2% | 11.71 ns, CV 8.0% | 11.82 ns, CV 10.3% | +7.6% | +0.9% | +6.6% |
| 16 MB | 10.91 ns, CV 2.8% | 10.79 ns, CV 2.7% | 11.39 ns, CV 2.9% | 11.17 ns, CV 2.4% | +2.4% | -1.9% | +4.4% |
| 24 MB | 10.81 ns, CV 2.7% | 10.91 ns, CV 5.2% | 11.42 ns, CV 5.0% | 11.03 ns, CV 2.1% | +2.1% | -3.4% | +5.7% |
| 32 MB | 10.67 ns, CV 3.1% | 10.55 ns, CV 2.2% | 11.23 ns, CV 3.3% | 10.95 ns, CV 4.3% | +2.6% | -2.5% | +5.3% |
| 48 MB | 10.43 ns, CV 2.7% | 10.65 ns, CV 3.8% | 10.98 ns, CV 2.9% | 10.52 ns, CV 2.0% | +0.9% | -4.2% | +5.3% |
| 64 MB | 10.38 ns, CV 2.3% | 10.30 ns, CV 2.1% | 10.78 ns, CV 3.5% | 10.41 ns, CV 2.0% | +0.3% | -3.5% | +3.9% |

## 3. Random access (lmbench -t, stride 16): medians and the protected-mode increment

increment = median(pkvm) - median of the three baseline medians.  The interval is a 95% percentile bootstrap of that quantity with all four groups resampled (20000 draws); it treats iterations as independent, see the note at the top of the script.

| size | pages | kvmoff | nvhe | vhe | pkvm | increment (ns) | 95% interval (ns) | relative to kvmoff | spread of the 3 baseline medians (ns) | pkvm runs above all 30 baseline runs |
|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|:---:|
| 0.25 MB | 64 | 7.94 | 7.96 | 7.94 | 7.92 | -0.01 | [-0.05, +0.05] | -0.18% | 0.03 | 0/10 |
| 0.375 MB | 96 | 8.26 | 8.33 | 8.25 | 8.62 | +0.36 | [+0.05, +0.48] | +4.41% | 0.07 | 0/10 |
| 0.5 MB | 128 | 10.70 | 10.61 | 10.25 | 11.25 | +0.63 | [-0.12, +1.23] | +5.14% | 0.45 | 1/10 |
| 0.75 MB | 192 | 16.73 | 16.68 | 16.92 | 16.61 | -0.12 | [-0.40, -0.02] | -0.72% | 0.25 | 0/10 |
| 1 MB | 256 | 19.41 | 19.48 | 19.48 | 19.43 | -0.05 | [-0.19, +0.20] | +0.11% | 0.07 | 0/10 |
| 1.5 MB | 384 | 20.19 | 20.18 | 20.12 | 20.24 | +0.06 | [+0.02, +0.14] | +0.27% | 0.06 | 0/10 |
| 2 MB | 512 | 20.68 | 20.75 | 20.73 | 20.88 | +0.15 | [-0.04, +0.47] | +1.00% | 0.08 | 1/10 |
| 3 MB | 768 | 36.60 | 36.63 | 36.56 | 37.31 | +0.71 | [+0.26, +1.08] | +1.94% | 0.07 | 7/10 |
| 4 MB | 1024 | 47.59 | 47.69 | 47.45 | 49.31 | +1.73 | [+1.40, +2.03] | +3.63% | 0.23 | 10/10 |
| 6 MB | 1536 | 67.14 | 67.35 | 67.37 | 72.59 | +5.24 | [+4.41, +6.78] | +8.12% | 0.24 | 6/10 |
| 8 MB | 2048 | 112.54 | 112.60 | 112.32 | 119.59 | +7.05 | [+6.56, +7.66] | +6.26% | 0.28 | 10/10 |
| 12 MB | 3072 | 154.65 | 154.81 | 154.65 | 161.68 | +7.03 | [+6.57, +7.27] | +4.54% | 0.16 | 10/10 |
| 16 MB | 4096 | 168.54 | 168.56 | 169.71 | 176.28 | +7.73 | [+7.47, +8.00] | +4.59% | 1.16 | 10/10 |
| 24 MB | 6144 | 177.23 | 177.47 | 180.27 | 185.59 | +8.12 | [+7.63, +8.53] | +4.72% | 3.04 | 9/10 |
| 32 MB | 8192 | 180.61 | 180.78 | 182.72 | 188.66 | +7.88 | [+7.28, +8.44] | +4.46% | 2.11 | 9/10 |
| 48 MB | 12288 | 182.66 | 182.44 | 183.85 | 189.56 | +6.90 | [+5.53, +7.98] | +3.78% | 1.41 | 9/10 |
| 64 MB | 16384 | 185.23 | 185.05 | 185.43 | 191.73 | +6.50 | [-0.09, +11.23] | +3.51% | 0.38 | 8/10 |

Per-iteration values at 64 MB (every mode has two or three faster iterations):

- kvmoff: 176.3 185.6 168.7 185.3 185.2 176.5 185.1 186.8 186.2 186.4
- nvhe: 186.2 185.9 164.5 186.6 185.6 172.2 175.2 185.9 184.5 184.5
- vhe: 186.6 185.6 185.6 175.4 185.1 186.0 185.3 159.9 186.0 176.6
- pkvm: 192.6 193.1 191.6 191.9 191.1 166.4 191.3 192.3 192.2 178.8

pkvm (10 runs) against the 30 pooled runs of the three baselines, Monte-Carlo permutation test on the difference of medians (200000 shuffles).  This says that the pkvm boot differs from the other three boots; it does not by itself attribute the difference to the boot mode.

| size | median pooled baselines | median pkvm | difference (ns) | two-sided p |
|---:|---:|---:|---:|---:|
| 4 MB | 47.63 | 49.31 | +1.68 | 0.000005 |
| 8 MB | 112.52 | 119.59 | +7.07 | 0.000010 |
| 16 MB | 168.63 | 176.28 | +7.65 | 0.000010 |
| 32 MB | 181.21 | 188.66 | +7.45 | 0.002015 |
| 64 MB | 185.30 | 191.73 | +6.43 | 0.014785 |

## 4. One boot session as the unit: the suite runs and the stand-alone runs

results/standalone-mem-bench holds a second set of sessions (10 runs each of a short memory-only test).  The logs carry no date, kernel or boot identification; that they were taken on the N90 in the four modes on other boots is stated only in docs/n90-kvm-host/standalone-memory-bench-validation.md.

Random access, median of the 10 runs of each session (ns):

| size | suite kvmoff | suite nvhe | suite vhe | alone kvmoff | alone nvhe | alone vhe | range of the 6 | suite pkvm | alone pkvm | smallest pkvm minus largest baseline |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 MB | 47.59 | 47.69 | 47.45 | 47.70 | 47.40 | 47.49 | 0.30 | 49.31 | 49.74 | +1.61 |
| 8 MB | 112.54 | 112.60 | 112.32 | 112.90 | 112.70 | 112.58 | 0.57 | 119.59 | 120.01 | +6.70 |
| 16 MB | 168.54 | 168.56 | 169.71 | 169.80 | 169.92 | 169.72 | 1.38 | 176.28 | 176.72 | +6.36 |
| 32 MB | 180.61 | 180.78 | 182.72 | 181.55 | 181.82 | 180.82 | 2.11 | 188.66 | 189.57 | +5.94 |
| 64 MB | 185.23 | 185.05 | 185.43 | 185.32 | 186.05 | 185.55 | 1.00 | 191.73 | 192.41 | +5.68 |

With sessions as the unit there are 2 protected sessions against 6 others; both protected medians lie above all six.  The probability of that ordering if the mode made no difference is 1/28 = 0.036.

Stand-alone sessions, the three Figure 7 points (10-run means; exact permutation p on means):

| point | kvmoff | nvhe | vhe | pkvm | pkvm vs kvmoff (p) | pkvm vs nvhe | pkvm vs vhe |
|---|---:|---:|---:|---:|---:|---:|---:|
| seq stride 256, 8 MB | 11.446 | 11.854 | 11.878 | 11.520 | +0.65% (0.820) | -2.81% | -3.01% |
| seq stride 256, 64 MB | 10.471 | 10.483 | 10.658 | 10.587 | +1.11% (0.486) | +1.00% | -0.66% |
| rand, 64 MB | 183.880 | 185.556 | 183.484 | 189.839 | +3.24% (0.011) | +2.31% | +3.46% |

Stand-alone sessions, seq stride 256 at 8 MB, per run (ns):

- kvmoff: 10.09 10.20 12.38 10.16 10.09 12.53 11.72 12.44 12.47 12.39  (>= 11.3: 6, >= 12.0: 5)
- nvhe: 12.59 12.55 10.27 10.32 12.56 12.57 12.31 12.51 10.22 12.63  (>= 11.3: 7, >= 12.0: 7)
- vhe: 10.12 12.97 10.56 13.07 10.14 11.69 12.38 12.44 12.91 12.49  (>= 11.3: 7, >= 12.0: 6)
- pkvm: 12.26 12.47 10.06 12.50 12.44 12.56 10.11 10.14 12.51 10.16  (>= 11.3: 6, >= 12.0: 6)

## 5. Sequential access at 64 MB by stride (one page crossing every 4096/stride accesses), medians (ns)

The last column is what 7 ns per page crossing would add, 7 ns being the random-access increment.  No cost per page crossing can be derived from these rows: pkvm lies above kvmoff and nvhe at some strides, but the vhe boot, which has no host stage-2 either, lies above pkvm.

| stride | crossings per access | kvmoff | nvhe | vhe | pkvm | pkvm - kvmoff | pkvm - nvhe | pkvm - vhe | vhe - kvmoff | 7 ns x crossings |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 0.0039 | 2.317 | 2.318 | 2.312 | 2.317 | -0.001 | -0.001 | +0.004 | -0.005 | 0.027 |
| 32 | 0.0078 | 2.675 | 2.678 | 2.682 | 2.676 | +0.002 | -0.002 | -0.006 | +0.007 | 0.055 |
| 64 | 0.0156 | 4.217 | 4.230 | 4.328 | 4.274 | +0.057 | +0.044 | -0.054 | +0.111 | 0.109 |
| 128 | 0.0312 | 9.034 | 9.014 | 9.261 | 9.180 | +0.147 | +0.167 | -0.081 | +0.227 | 0.219 |
| 256 | 0.0625 | 10.357 | 10.241 | 10.781 | 10.345 | -0.012 | +0.104 | -0.437 | +0.424 | 0.438 |
| 512 | 0.1250 | 9.573 | 9.517 | 9.926 | 9.789 | +0.216 | +0.272 | -0.137 | +0.353 | 0.875 |
| 1024 | 0.2500 | 10.473 | 10.518 | 11.066 | 10.899 | +0.427 | +0.381 | -0.167 | +0.593 | 1.750 |

## 6. Quiesced nVHE host against the non-quiesced nVHE host (neither has a host stage-2)

results/n90-day3-host/n90-nvhe-noisy-full-* was taken on the same machine, kernel and KVM mode before the background services were masked (according to the June documents; the result files record only the kernel and its command line).  Medians of 10 iterations.

| size | random: quiesced | random: non-quiesced | change | seq stride 256: quiesced | seq stride 256: non-quiesced | change |
|---:|---:|---:|---:|---:|---:|---:|
| 1 MB | 19.48 | 19.05 | -2.2% (-0.4 ns) | 4.44 | 4.47 | +0.7% |
| 2 MB | 20.75 | 21.10 | +1.7% (+0.3 ns) | 4.70 | 4.74 | +0.9% |
| 3 MB | 36.63 | 26.41 | -27.9% (-10.2 ns) | 5.31 | 4.92 | -7.5% |
| 4 MB | 47.69 | 30.80 | -35.4% (-16.9 ns) | 5.48 | 5.07 | -7.5% |
| 6 MB | 67.35 | 48.61 | -27.8% (-18.7 ns) | 8.22 | 7.46 | -9.2% |
| 8 MB | 112.60 | 83.90 | -25.5% (-28.7 ns) | 11.41 | 10.32 | -9.6% |
| 12 MB | 154.81 | 121.82 | -21.3% (-33.0 ns) | 10.86 | 11.34 | +4.4% |
| 16 MB | 168.56 | 134.23 | -20.4% (-34.3 ns) | 10.69 | 11.47 | +7.2% |
| 24 MB | 177.47 | 143.08 | -19.4% (-34.4 ns) | 10.87 | 11.27 | +3.6% |
| 32 MB | 180.78 | 146.20 | -19.1% (-34.6 ns) | 10.50 | 11.17 | +6.4% |
| 48 MB | 182.44 | 149.10 | -18.3% (-33.3 ns) | 10.54 | 11.04 | +4.7% |
| 64 MB | 185.05 | 150.12 | -18.9% (-34.9 ns) | 10.24 | 11.11 | +8.5% |

Sequential stride 256 at 8 MB, per iteration (ns):

- quiesced nvhe: 10.30 12.43 12.62 9.98 9.93 12.27 12.35 10.55 12.31 10.02
- non-quiesced nvhe: 10.81 10.34 10.34 10.31 10.27 10.26 10.33 10.28 10.10 10.33

Non-quiesced run, strides 128 to 1024 at 8 MB: 0 of 40 values at or above 11.3 ns.

## 7. Single runs of the quiesced data sets that are faster than the median of their config (random access)

Counts of runs more than 4%, 8% and 15% below the median, as kvmoff/nvhe/vhe/pkvm.  The non-quiesced run is 18% to 35% below the quiesced one, so only the last column counts runs that reach that level completely; lmbench reports the fastest of 11 timed intervals, and a run that is a few percent low can be one in which some of the laps of that interval were fast.

| size | > 4% below | > 8% below | > 15% below |
|---:|---|---|---|
| 3 MB | 0 (0/0/0/0) | 0 (0/0/0/0) | 0 (0/0/0/0) |
| 4 MB | 0 (0/0/0/0) | 0 (0/0/0/0) | 0 (0/0/0/0) |
| 6 MB | 0 (0/0/0/0) | 0 (0/0/0/0) | 0 (0/0/0/0) |
| 8 MB | 0 (0/0/0/0) | 0 (0/0/0/0) | 0 (0/0/0/0) |
| 12 MB | 1 (1/0/0/0) | 1 (1/0/0/0) | 1 (1/0/0/0) |
| 16 MB | 4 (3/0/1/0) | 4 (3/0/1/0) | 3 (3/0/0/0) |
| 24 MB | 4 (2/0/1/1) | 4 (2/0/1/1) | 2 (1/0/1/0) |
| 32 MB | 6 (4/1/0/1) | 6 (4/1/0/1) | 3 (2/0/0/1) |
| 48 MB | 8 (3/3/1/1) | 4 (3/1/0/0) | 1 (1/0/0/0) |
| 64 MB | 11 (3/3/3/2) | 4 (1/1/1/1) | 0 (0/0/0/0) |
| all sizes | 34 (16/7/6/5) | 23 (14/3/3/3) | 10 (8/0/1/1) |

## 8. Does the high level of the sequential test carry over to the next size measured?

lmbench measures the sizes of one stride in ascending order, each in a fresh child process about one second after the previous one.  high = more than 12% above the median of the lower half of the 40 values of that stride and size.  Expected = the count if the two sizes were unrelated within each (config, stride); p from 20000 random re-pairings of the iterations within each (config, stride).

| first measurement | second measurement | high at the first | high at the second | high at both | expected | one-sided p |
|---|---|---:|---:|---:|---:|---:|
| 6 MB, strides 64-1024 | 8 MB, same stride and iteration | 0 | 93 | 0 | 0.0 | 1.0000 |
| 8 MB, strides 64-1024 | 12 MB, same stride and iteration | 93 | 22 | 19 | 12.5 | 0.0005 |
| 12 MB, strides 64-1024 | 16 MB, same stride and iteration | 22 | 12 | 6 | 2.7 | 0.0170 |
| 16 MB, strides 64-1024 | 24 MB, same stride and iteration | 12 | 13 | 8 | 3.2 | 0.0001 |
| 8 MB, strides 128, 256, 512 | 8 MB at the next stride (about a minute later), same iteration | 67 | 61 | 35 | 33.8 | 0.3911 |
| 8 MB, strides 128-1024 | 8 MB, same stride, next iteration (about ten minutes later) | 83 | 84 | 49 | 52.0 | 0.8980 |

## 9. What the next sizes read right after a high 8 MB point

Same sweeps as section 8 (strides 64-1024, four quiesced boots, ten iterations each: 200 sweeps).  Every value is divided by the median of the lower half of the 40 values of its stride and size.  The sweeps are split by whether their 8 MB point was high (more than 1.12).  If a high 8 MB point came from the frames of that child's buffer and the next child took the same frames back (as every 12 MB child did on the N80, Exp H7), two thirds of the 12 MB buffer and half of the 16 MB buffer would be those frames.

| size | 8 MB point of the sweep | sweeps | quartiles of value / low level | within 0.97-1.04 | 1.04-1.12 | above 1.12 | above 1.20 |
|---:|---|---:|---|---:|---:|---:|---:|
| 12 MB | high | 93 | 1.004 / 1.028 / 1.068 | 57 | 16 | 19 | 16 |
| 12 MB | low | 107 | 0.999 / 1.016 / 1.036 | 83 | 21 | 3 | 3 |
| 16 MB | high | 93 | 1.001 / 1.033 / 1.062 | 54 | 26 | 12 | 6 |
| 16 MB | low | 107 | 0.999 / 1.022 / 1.045 | 76 | 30 | 0 | 0 |
| 24 MB | high | 93 | 1.000 / 1.020 / 1.061 | 56 | 23 | 9 | 5 |
| 24 MB | low | 107 | 1.000 / 1.022 / 1.050 | 70 | 31 | 4 | 0 |
| 32 MB | high | 93 | 1.004 / 1.025 / 1.064 | 59 | 26 | 7 | 3 |
| 32 MB | low | 107 | 0.998 / 1.016 / 1.035 | 83 | 23 | 0 | 0 |

12 MB value / low level in the sweeps whose 8 MB point was high, by stride (count: median, number above 1.12):

- stride 64: 4: 1.248, 3
- stride 128: 28: 1.018, 6
- stride 256: 22: 1.028, 4
- stride 512: 17: 1.028, 1
- stride 1024: 22: 1.051, 5

Histogram of the 12 MB value / low level after a high 8 MB point (bins of 0.04):

```
0.94-0.98 ##### 5
0.98-1.02 ################################# 33
1.02-1.06 ############################## 30
1.06-1.10 ### 3
1.10-1.14 ### 3
1.14-1.18 ## 2
1.18-1.22 ## 2
1.22-1.26 ######### 9
1.26-1.30 ###### 6
```
