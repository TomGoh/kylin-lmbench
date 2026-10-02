# 核查报告：audit:fast-state

## Summary

VERDICT ON H-i: UNDETERMINED as a root cause. Its descriptive core is supported, with one correction; the NoC mechanism itself has never been measured.

SUPPORTED (re-derived from raw reports; my own parser matches the CSVs in 13150/13150 memory-latency cells): the N90 has a two-level memory-path state that does not depend on the KVM mode.
- Pinned-fast data sets: the nVHE "noisy" host, every day-1/day-2 host run (protected, default, nVHE), the pVM guest, and try1 (documented only).
- Noisy versus clean nVHE, random access: no shift up to 2 MB (-2.3 to +7%); -10.2 / -16.9 / -18.7 / -28.7 ns at 3 / 4 / 6 / 8 MB; -34.4 +/- 0.8 ns from 16 to 64 MB (150.1 vs 185.0 ns). Ranges are disjoint at every size from 3 MB (exact permutation p = 1.1e-5).
- The pVM-minus-NP guest shift is the same: -10.4 / -16.7 / -28.7 ns at 3 / 4 / 8 MB.
- L1 latency, lat_ops, null syscall and the tlb line (48 in 90/90 iterations) do not change.

CORRECTION: the quiesced state is not "slow", it is traffic-following.
- Random access and cache-resident 2-8 MB workloads are always slow (0/160 random cells at 3-8 MB; bw_mem wr 4.19 MB 0/40).
- Sustained DRAM streaming is mostly fast. The slow level (x1.19-1.26) appears in 55.6% of cells at 8 MB, 11.9% at 12 MB and 1.9-6.9% at 16-64 MB; bw_mem_rd 16.78 MB is low in 18/40 (level ratio 1.233).

STRONGEST EVIDENCE FOR THE NoC MECHANISM
1. The N80 with nocfreq at performance/1800 MHz and 4 KiB pages reproduces the fast curve: lmbench random 64 MB 152.4-154.2 ns, within 2.6 ns of the N90 pVM guest from 12 to 64 MB; sequential 8 MB is unimodal, 10.16-10.51 ns in 16/16 sweeps.
2. The penalty starts where data leave a roughly 2 MB core-side cache, not where DRAM starts (at 3 MB at most 4% of hops can be DRAM, yet the shift is +10.2 ns per hop). Only DRAM-bound traffic triggers the fast level, and the time constants are multiples of 100 ms.
3. Source code: default governor simple_ondemand, 100 ms polling, load metric from DDR-port counters, ACPI id PHYT0047. No June script reads or sets devfreq.

STRONGEST EVIDENCE AGAINST, OR MISSING
- No latency was ever measured at a NoC frequency other than 1800 MHz, and the N90's devfreq state was never recorded.
- try1 went persistently fast in a fully masked run (documented only).
- Slow episodes survive the heaviest streaming (VHE iteration 3: three consecutive stride sweeps).
- The agent that pins the governor is unidentified: the recorded policy table lists only simple_ondemand and powersave, and the noisy run shows no desktop session.

ALTERNATIVES
- (a) THP: contradicted. N80 THP gives -17 to -23% at 0.5-2 MB; the N90 fast state shows none. Only the N80 8 MB THP value (81.9 ns) coincides with N90 fast (83.9 ns).
- (b) Frame contiguity: contradicted for the fast state (N80 placement effects are at most 2-4% and of opposite sign), but supported as a separate second effect: the noisy run is 3.5-13.8% slower in sequential access from 12 MB.
- (c) CPU frequency: contradicted (L1 2.223 vs 2.224 ns; all cores capped at 1.9 GHz).
- (d) Protected VM or protected mode: contradicted as the cause (fast on an nVHE host with no VM; slow on protected hosts and in the NP guest). No pVM control run exists.
- (e) Minimum of 11: not a cause; it shapes the two-valued appearance and the sporadic fast cells.
- (f) A DDR-only power state is contradicted by the 3-4 MB arithmetic; thermal by the absence of drift; contention by sign (N80 background load makes cpu0 30-180% slower; noisy load average 1.00-1.08).

Surviving candidates: H-i, or an unidentified interconnect power state with the same dynamics.

## Defects

- **invalidates** | H-i premise for the N90 (worklog section 9; results/n90-day3-host/*-summary.txt; prepare-host.sh, quiet-host.sh, scripts/apply-masks.sh, scripts/verify-clean-env.sh): Nothing about the N90's interconnect was ever recorded: not whether ACPI device PHYT0047 exists, whether phytium_noc was loaded, which governor was active, or cur_freq. The summaries hold only env, kernel, cmdline and cpu_max_freqs, and grep finds no devfreq reference in any June script or document. Effect: The statement that quiesced runs had the governor on simple_ondemand and non-quiesced runs had it pinned is an inference for every N90 data set. It cannot be given to a reviewer as a fact.
- **invalidates** | Central physical claim (results/memlat-n80-20260930/*.log, meta.log, expH-noc-samples.log): No latency measurement exists at any NoC frequency other than 1800 MHz on any machine. All 10366+ frequency samples and every log header read governor=performance, 1800000. The governor experiments (run4, run7, run8) were not executed. Effect: That a lower interconnect clock adds about 35 ns per DRAM access and about 25 ns per cache transfer beyond 2 MB is untested. H-i can only be offered as a hypothesis with the experiment that would test it.
- **weakens** | docs/n90-kvm-host/standalone-memory-bench-validation.md:29-40 and 345-372 (try1; raw files not in the repository): A fully masked, verified-clean protected-mode run switched at iteration 4 from 194 to 154 ns (64 MB random) and stayed fast for the remaining seven iterations. Its documented medians (26.87 / 31.89 / 91.01 / 154.4 ns at 3 / 4 / 8 / 64 MB; sequential 64 MB 10.11 ns) are the pinned-fast fingerprint. Effect: The rule that quiesced means not pinned has a documented exception. H-i needs an unrecorded event that changed or froze the governor, and the raw data to examine it are gone.
- **weakens** | Agent that pins the governor (results/memlat-n80-20260930/devfreq-survey-n80.txt:69-127, vm-frames-n80.txt; raw headers of n90-nvhe-noisy-full-cpu0-iter*.txt): The recorded power-manager policy table lists only simple_ondemand (default scene) and powersave (idle, meeting, office, video), never performance. On the N80 the freeze of trans_stat (16.5 s for nocfreq, 27.8 s for the GPU device) coincides with the start of the power daemon (16:22:10 per the worklog) and equally with crosvm/pvm-manage (16:21:55). In the noisy N90 run the mount table has no desktop portal mount (present in the day-1/day-2 desktop runs), only gvfs from iteration 2; load average is 1.00-1.08. Effect: The claim that a desktop power-management daemon pins the interconnect high is not supported by the daemon's own table, which would select ondemand or the minimum frequency. A desktop session is not evidenced for the only same-kernel fast host run. The link from 'non-quiesced' to 'pinned' is unidentified.
- **weakens** | Clean host runs, sequential and bw_mem rows (results/n90-day3-host/*.csv; my out_t14_seqstate.txt, out_t19_vhe_episode.txt, out_t23_stats2.txt): A load-following governor does not explain slow episodes that persist through the heaviest DRAM streaming. VHE iteration 3 is slow through the whole 8-64 MB range of three consecutive stride sweeps (stride 32 x1.08-1.11, stride 64 x1.25-1.28, stride 128 x1.16-1.28); VHE iteration 8 through the whole stride-64 sweep. bw_mem_rd is low at 16.78, 33.55 and 67.11 MB together in kvmoff iteration 9, nVHE iteration 5 and VHE iteration 10 (3/3 coupling, Fisher p = 1.0e-4). Effect: The simple story that traffic raises the frequency needs a further mechanism that can hold the state low for seconds to minutes. One code fact may be relevant but is unverified as a cause: at tag 6.6.0-73.76 the driver updates its cached rate even when the ACPI call fails (phytium_noc.c:144-151).
- **weakens** | Load metric (klinux drivers/devfreq/phytium_noc.c at tag 6.6.0-73.76, lines 24, 46-65, 277-300): The register is named WR_NOLAST_HANDSHARK_NUM and the comment says 'dmu read/write commands'. Whether reads count, and how many counts one cache line produces, cannot be determined from source. The thresholds (above 8.45e6 counts per 100 ms at 600 MHz jumps to maximum; at least 1.93e7 to stay at 1800 MHz) were never compared with a measured count. Effect: The account of the 8 MB two-valued point as traffic near the up-threshold is qualitative. Read-only bw_mem_rd is fast in 37/40 cells at 33-67 MB, which requires read traffic to be counted; that contradicts a literal reading of the register name.
- **weakens** | Size at which the shift starts (random 3-6 MB; sequential 3-6 MB; bw_mem 4.19 MB; lat_ctx): The shift is present well inside the 8 MiB L3. At 3 MB and 4 MB the fast values (26.4 and 30.8 ns) allow at most 4.1% and 7.5% of hops to be DRAM accesses, yet the slow state adds 10.2 and 16.9 ns per hop. bw_mem wr at 4.19 MB differs by 19.5%. The worklog frames the penalty as slower main-memory access. Effect: H-i works only if cache traffic beyond about 2 MB crosses the scaled interconnect. N80 counters are consistent with this (l3d_cache_refill starts above 2 MB and costs about 16-21 ns, not a DRAM access), but it is an undocumented hardware assumption. The same arithmetic excludes a DDR-only explanation.
- **weakens** | N80 calibration (expA.log, expC.log, expF.log, expH-rand.log, expH-seq256.log, expS.log, expV.log, vm-frames-n80.txt): The N80 is not uniformly fast-like. At 6 and 8 MB its 4 KiB values (62.6 and 101.5 ns) lie between the N90 fast (48.6 / 83.9) and slow (67.4 / 112.6) values, and its 8 MB huge-page value (81.7-84.2 ns) coincides with N90 fast. The machine differs in DIMMs, in effective CPU clock (1.9 vs 1.8 GHz), and ran a desktop plus an idle protected VM that fragments host stage-2 (pages sharing 2 MiB regions with it: 167 vs 151 ns at 32 MB). Effect: The calibration supports 'fast equals interconnect at maximum' at 4 MB and below and from 12 MB (within about 5 ns). It is ambiguous at the L3 boundary and cannot by itself exclude other causes.
- **weakens** | Figure 8 inference (results/xkernel-n90-*; started.txt, environment.txt): No host-side record exists for any guest run, and there is no control (a pVM run in the traffic-following state, or an NP run in the pinned state). The pVM directory carries the NP ENV_TAG. Effect: That the pVM guest is fast because of the platform state rests on fingerprint identity with the noisy host (shift, par_mem -22 to -28%, bw_mem +20 to +24% at 4-8 MB, lat_ctx, 8 MB low 10/10) and on the guest beating bare metal by 7.6-32 ns. That is strong, but still an inference.
- **cosmetic** | Noisy run, large sequential and streaming rows: The noisy run is slower, not faster, in sequential access from 12 MB (+3.5 to +13.8%), bzero (-13%), bcopy (-6 to -7%) and stride 1024 at 1-4 MB (+5 to +15%), with a tight spread (max/min 1.006-1.013). H-i does not explain this. Effect: A second, separate effect (scattered page frames in the non-quiesced environment) must be stated whenever the noisy run is used as the example of the fast state. It does not contradict H-i.
- **cosmetic** | Wording 'changes memory latency by about 20%': About 20% holds only for DRAM-bound random access (-17 to -21% from 12 MB). At 3-6 MB the shift is -28 to -35%, at 8 MB -25%; sequential 3-8 MB -7.5 to -17%; bandwidth levels differ by x1.10-1.23. Effect: Quote the absolute shift per access (about 35 ns beyond 16 MB, 10-29 ns at 3-8 MB) rather than one percentage.
- **cosmetic** | Day-1/day-2 support (results/n90-day1, n90-day2 raw headers and summaries): Those runs used a different, untagged kernel build (6.6.0-52-generic #43pkvm10, Apr 13 2026) and a 2.1 GHz lock. The first run had the big cores at 3.1 GHz and is faster still (64 MB random 133.9 ns; 1-2 MB 13.1 / 15.1 ns against 16.1-18.5 ns in later 2.1 GHz runs), a third level tied to core or cluster frequency. Effect: The association of fast with not-yet-masked is confounded with kernel build and frequency settings. Only the noisy run is a same-kernel comparison.
- **cosmetic** | Statement 'CPU frequency locked at 1.9 GHz' (N90): The effective N90 core clock was 1.80 GHz: L1 load 2.223 ns is 4 cycles, float add 1.11 ns is 2 cycles. The N80 at a true 1.9 GHz gives 2.107 ns, and the N90 at the 2.1 GHz lock gives 1.906 ns. The MHZ header line is a constant from configs/CONFIG.host. Effect: No effect on comparisons within the N90. Cross-machine comparisons of core-bound latencies need a factor of 1.056.

## Discrepancies

- H-i as stated ('in quiesced runs DRAM-bound random access is slow and the 8 MB point flips') is incomplete. In the clean runs DRAM-bound streaming runs at the fast level in 93-98% of cells at 16-64 MB. The slow level is not confined to 8 MB: strides 128-1024 give 55.6% slow at 8 MB, 11.9% at 12 MB, 6.2 / 6.9 / 3.1 / 3.1 / 1.9% at 16 / 24 / 32 / 48 / 64 MB. bw_mem_rd 16.78 MB is low in 18/40 plus 4 intermediate; bw_mem_wr 16.78 MB low in 18/40.
- Worklog 9.3 says 64 MB sequential access differs little between the two environments. I get noisy slower by 4.4-8.5% at 12-64 MB for stride 256, 9.5-11.3% for stride 512, 7.5-13.8% for stride 1024, and bzero 67 MB -13.0%.
- Worklog 11.2 expected contention to explain that slowdown. The N80 BG log shows one reader on another core raises cpu0's 64 MB sequential latency from 8.85-9.42 to 13.3-13.5 ns (+47%) and 64 MB random from 148-154 to 197 ns. That is the wrong magnitude, and the noisy load average was only 1.00-1.08.
- host-stats#10 says the two-valued state is decided per measurement and is uncorrelated with the 12 MB point. Pooled over strides 64-1024 in the four clean hosts, 12 MB is slow in 19/93 cases when 8 MB was slow and in 3/107 when it was not (Fisher p = 6.5e-5). The state carries over between consecutive measurements.
- guest-fig8#12 says the sporadic fast cells may be per-process rather than time-window events. Host fast cells are complete at short laps (12-32 MB: 9 complete, 6 partial) and only partial at long laps (48 MB: 1 complete, 6 partial; 64 MB: 0 complete, 10 partial at 25-72%). That implies fast windows of roughly 0.1-0.5 s.
- concl#7 says random access is within 2.5% up to 2 MB and 19-36% lower from 3 to 64 MB. Median differences at 0.375, 0.5 and 0.0625 MB are +6.8, +6.8 and +12.9% (noisy slower); the 'within 2.5%' holds only at 0.03 MB and below and at 0.75-2 MB. At 48 and 64 MB the reduction is 18.3 and 18.9%. The 150.1 vs 185.0 ns figures are confirmed.
- concl#8 and the worklog 9.1 table of fast single runs are confirmed exactly: 0 at each size up to 8 MB, then 1, 4, 4, 6, 8, 11 of 40 at 12, 16, 24, 32, 48, 64 MB.
- The task statement describes non-quiesced runs as 'desktop and services running'. For the noisy run the raw headers show no xdg portal mount (present in day-1/day-2 desktop runs), only a gvfs mount from iteration 2, a tracefs debug mount, and 11906 wlan packets at start against 362 in the clean run. The documents mention pvm-manage and Kylin AI services, not a desktop session.
- The statement that a desktop power-management daemon pins the interconnect high is not what the recorded policy table implies. It lists simple_ondemand for the default scene and powersave for idle, meeting, office and video scenes. The 'performance' governor observed on the N80 appears nowhere in the table.
- prior-docs#35 reads the v1 load metric as apparently write-channel traffic, while worklog 9.3 says large read traffic raises the interconnect frequency by itself. Both cannot hold. The data need read traffic to count: read-only bw_mem_rd at 33-67 MB is at the fast level in 37/40 clean cells.
- prior-docs#29 says the day-1/day-2 runs used kernel 6.6.0-52. The raw headers show the build '#43pkvm10-KYLINOS, Apr 13 2026', which is not the tagged 6.6.0-52.51 (2025-11-01). Its devfreq code cannot be verified from the klinux tags.
- The README and task statement say the N80 ran no VM. The analyst's later entry (worklog 11.3) and vm-frames-n80.txt show an idle protected VM (crosvm started 16:21:55, 254 MB resident) during all N80 measurements.
- Worklog 9.5(1) says the four-mode comparison stays valid because all four clean runs are in the same slow state. That holds for medians of random access. It does not hold for points in the flip region (8 MB sequential, bw_mem 16.78 MB) or for means that include partially fast cells (64 MB random: kvmoff 3, nVHE 3, VHE 3, pkvm 2 of 10).
- prior-docs#34 gives a level ratio of about 1.25 for bandwidth. I get 1.233 for bw_mem_rd 16.78 MB, but 1.116 for wr, 1.096 for rdwr and 1.116 for cp 8.39 MB.

## Threats to validity

- The decisive measurement has not been made. On the N90 (or the N80), in one boot with 4 KiB pages and cpu0 fixed, set /sys/class/devfreq/nocfreq to the minimum (powersave, or userspace at 600 MHz) and to the maximum (performance), and run lat_mem_rd -t 64 16 and lat_mem_rd 64 256 at least 10 times each while sampling cur_freq every 100 ms. H-i predicts about 185 vs 150 ns at 64 MB random on the N90, +10 and +17 ns at 3 and 4 MB, no change up to 2 MB, and the 8 MB sequential point single-valued high and low respectively. If latency does not follow the NoC frequency, H-i is refuted and the cause is an unidentified platform state.
- A third pass under simple_ondemand with the same sampling would test the traffic-following part: cur_freq should sit at 600 MHz during random laps, jump during sequential access from 12 MB, and flip at 8 MB.
- The premise on the N90 cannot be checked from existing data. Read governor, cur_freq and trans_stat once after apply-masks plus reboot and once with the desktop stack running; identify which process writes the governor.
- try1 cannot be re-examined: its raw files were never committed. Every try1 number is quoted from documents.
- lmbench prints only the minimum of 11 intervals (100 ms each for lat_mem_rd, 10 ms for bw_mem). On the N90 there are no per-interval values, so the time course inside a measurement is inferred from how results depend on lap length.
- Each condition is one boot. The noisy run is the only fast host run on the day-3 kernel; the day-1/day-2 runs differ in kernel build and CPU frequency settings.
- The N80 is not the N90: 2 x 8 GB modules, a true 1.9 GHz core clock against 1.80 GHz effective on the N90, a desktop session, an idle protected VM, and system THP=always with per-process disabling. Absolute values near the L3 boundary (6-8 MB) are not transferable.
- My slow/fast classification of sequential cells uses a threshold of 1.12 times the pooled low level. The VHE run carries a 3-8% offset of its own, so its intermediate cells are partly a layout effect.
- The cache picture I use (a roughly 2 MB core-side level, with the rest of the 8 MiB L3 and DRAM behind the interconnect) is inferred from N80 counters and timing, not from documentation.
- The guest x-kernel build is assumed to be commit 9bab5da3, where anonymous private mmap uses 4 KiB pages unless a huge flag is given (posix/mm/src/mmap.rs). The commit actually run is unrecorded.
- The second effect in the noisy run (slower large sequential access) is attributed to scattered page frames by inference (stride 1024 at 1-4 MB, N80 huge-page contrast of -8 to -15%). No page-frame data exist for the N90.

## Recomputed tables

### T0. Prediction versus observation
Symbols: + predicted, − contradicted, 0 silent, ? fits only with an extra unverified assumption. (f1) = DDR power state, (f2) = thermal, (f3) = contention from other cores.

| # | Observable (recomputed) | H-i | (a) THP | (b) frames | (c) CPU freq | (d) pVM / protected | (e) min of 11 | (f1) | (f2) | (f3) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Random 0.25-2 MB unchanged (−2.3 to +7%) | + | − | 0 | − | 0 | 0 | + | 0 | 0 |
| 2 | Shift starts at 3 MB (−10.2 ns), −16.9 ns at 4 MB, inside the 8 MiB L3 | ? | − | − | − | − | − | − | − | − |
| 3 | Constant −34.4 ± 0.8 ns at 16-64 MB (−19 to −20%) | + | − | − | − | − | − | + | 0 | − |
| 4 | Sequential 3-6 MB, strides 128/256: −7.5 to −10.8% (no TLB misses there) | + | − | − | − | − | − | − | − | − |
| 5 | 8 MB sequential: low 10/10 (noisy), 10/10 (pVM), 16/16 (N80 at fixed NoC); clean 55.6% slow, stride 64 only 10% | + | − | − | − | − | 0 | ? | − | − |
| 6 | Sequential from 12 MB: noisy +3.5 to +13.8% slower; pVM guest within −0.5 to −1.8% of NP | 0 | − | + | − | − | 0 | 0 | 0 | ? |
| 7 | Stride 1024 at 1-4 MB: noisy +5 to +15%, wider spread | 0 | − | + | 0 | 0 | 0 | 0 | 0 | 0 |
| 8 | tlb line = 48 in 90/90 iterations | + | − | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 9 | bw_mem: cache-resident sizes always slow in clean runs; from 16.78 MB two levels in clean, one in noisy | + | − | − | − | − | 0 | − | − | − |
| 10 | par_mem −17 to −27% at 4-33 MB, none up to 2 MB | + | 0 | − | − | − | 0 | 0 | 0 | − |
| 11 | lat_ctx −5 to −12% for footprints of 1.5-6 MB; +2 to +5% when small | + | 0 | 0 | − | − | 0 | − | 0 | − |
| 12 | lat_ops, null syscall, L1 identical | + | + | + | − | + | + | + | 0 | + |
| 13 | Day-1/day-2 hosts fast in protected, default and nVHE modes | + | − | 0 | − | − | − | 0 | 0 | 0 |
| 14 | try1: masked, slow in iterations 1-3, fast in 4-10 (documented) | ? | − | ? | 0 | − | − | ? | 0 | − |
| 15 | pVM guest fast 10/10, same shift, 7.6-32 ns faster than bare metal; other three guests slow | + | − | − | − | − | − | − | 0 | − |
| 16 | Sporadic fast cells: complete at 12-32 MB laps, partial at 48-64 MB, none at 3-8 MB | + | − | − | 0 | − | + | 0 | − | − |
| 17 | State persists (12 MB slow given 8 MB slow: 19/93 vs 3/107) and depends on line rate | + | − | ? | 0 | − | − | 0 | 0 | 0 |
| 18 | Slow episodes through the heaviest streaming (VHE iteration 3 and 8; bw_mem three times) | ? | − | − | 0 | − | − | − | 0 | 0 |
| 19 | N80 at NoC 1800 MHz, 4 KiB pages: matches N90 fast plus protected increment up to 4 MB and from 12 MB; in between at 6-8 MB | + | − | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

### T1. Random access (stride 16), medians in ns
N80 columns: lmbench binary, NoC fixed at 1800 MHz, protected mode, cpu0 at 1.9 GHz (expH-rand.log; 4 KiB n = 5, huge pages n = 2). Refill rates per hop from expA.log.

| MB | N90 clean nVHE | N90 noisy nVHE | diff | ratio | guest NP | guest pVM | diff | N80 4 KiB | N80 huge | N80 L3 refill | N80 TLB refill | shift per L3 refill | shift per walk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 10.61 | 11.33 | +0.72 | 1.068 | 12.29 | 11.91 | −0.38 | 11.48 | 8.82 | 0.000 | 0.000 | | |
| 1 | 19.48 | 19.05 | −0.43 | 0.978 | 19.58 | 19.73 | +0.15 | 18.82 | 15.28 | 0.001 | 0.006 | | |
| 2 | 20.75 | 21.10 | +0.35 | 1.017 | 23.76 | 22.38 | −1.38 | 21.41 | 17.56 | 0.060 | 0.046 | | |
| 3 | 36.63 | 26.41 | −10.22 | 0.721 | 39.44 | 29.00 | −10.44 | 28.28 | 23.02 | 0.407 | 0.190 | 25.1 | 53.8 |
| 4 | 47.69 | 30.80 | −16.89 | 0.646 | 52.62 | 35.97 | −16.65 | 34.67 | 27.48 | 0.624 | 0.447 | 27.1 | 37.8 |
| 6 | 67.35 | 48.61 | −18.74 | 0.722 | 80.68 | 55.34 | −25.34 | 62.62 | 49.66 | 0.789 | 0.838 | 23.7 | 22.3 |
| 8 | 112.60 | 83.90 | −28.70 | 0.745 | 126.53 | 97.85 | −28.67 | 101.48 | 81.86 | 0.878 | 0.967 | 32.7 | 29.7 |
| 12 | 154.81 | 121.82 | −32.99 | 0.787 | 164.76 | 129.49 | −35.27 | 132.05 | 112.57 | 0.929 | 0.998 | 35.5 | 33.0 |
| 16 | 168.56 | 134.23 | −34.33 | 0.796 | 177.05 | 141.20 | −35.85 | 143.46 | 121.99 | 0.974 | 1.000 | 35.3 | 34.3 |
| 24 | 177.47 | 143.08 | −34.39 | 0.806 | 185.92 | 147.25 | −38.68 | 147.92 | 129.08 | 0.980 | 1.000 | 35.1 | 34.4 |
| 32 | 180.78 | 146.20 | −34.58 | 0.809 | 189.23 | 150.18 | −39.04 | 150.39 | 131.29 | 0.979 | 1.000 | 35.3 | 34.6 |
| 48 | 182.44 | 149.10 | −33.34 | 0.817 | 191.47 | 151.07 | −40.41 | 151.17 | 133.84 | 0.994 | 1.000 | 33.5 | 33.3 |
| 64 | 185.05 | 150.12 | −34.92 | 0.811 | 192.35 | 152.91 | −39.44 | 153.45 | 134.75 | 0.997 | 1.000 | 35.0 | 34.9 |

- Noisy and clean ranges are disjoint at every size from 3 to 64 MB (exact permutation p = 1.08e-5); the same holds for pVM vs NP.
- Other clean medians at 64 MB: kvmoff 185.23, VHE 185.43, pkvm try2 191.73.
- DRAM share bound: at 3 MB at most (26.41 − 21.10) / (150.12 − 21.10) = 4.1% of hops; at 4 MB at most 7.5%.
- N80 huge pages versus 4 KiB: −23 / −19 / −17 / −18% at 0.5 / 1 / 1.5 / 2 MB; −5.3 / −7.2 / −19.6 / −18.7 ns at 3 / 4 / 8 / 64 MB.

### T2. N80 calibration values requested (ns per access)

| Source | Pages | 8 MB | 64 MB | Which N90 state it resembles |
|---|---|---|---|---|
| expA.log (probe, 3 seeds x 2) | 4 KiB | 102.1-104.4 min; 104.8-110.9 median | 153.2-156.6 min | 64 MB: fast plus protected increment (150.1 + 4.3 to 6.5 = 154.4-156.6). 8 MB: between fast (83.9 + 7.1 = 91.0) and slow (119.6) |
| expC.log (huge pages requested) | 2 MiB | 82.5-84.2 min (TLB refills below 2e-5) | 137.5-138.1 (TLB refills 0.087-0.124, partial) | 8 MB: equals N90 fast (83.9). 64 MB: 12-13 ns below N90 fast; resembles neither |
| expF.log (frame placement) | 4 KiB | not measured | 154.2-160.9 over 7 policies (compact 154.7-155.6; scattered 160.2-160.5) | fast plus protected increment; placement spread 4.3% |
| expH-rand.log (lmbench binary) | 4 KiB / huge | 100.0-102.1 / 81.7-82.0 | 152.4-154.2 / 134.6-134.9 | as above |

The N90 protected-mode increment is +7.05 / +6.5 ns at 8 / 64 MB in the slow state (try2) and +7.1 / +4.3 ns in the fast state (documented try1 minus noisy).

### T3. Sequential access, stride 256, medians in ns

| MB | N90 clean nVHE | N90 noisy | noisy vs clean | guest NP | guest pVM | pVM vs NP | N80 4 KiB (n = 16, min..max) | N80 huge (n = 3) |
|---|---|---|---|---|---|---|---|---|
| 2 | 4.699 | 4.744 | +0.9% | 4.979 | 4.875 | −2.1% | 4.46 (4.45..4.52) | 4.43 |
| 3 | 5.315 | 4.919 | −7.5% | 5.559 | 5.037 | −9.4% | 4.67 (4.66..4.71) | 4.60 |
| 4 | 5.483 | 5.072 | −7.5% | 5.860 | 5.121 | −12.6% | 4.83 (4.81..4.95) | 4.70 |
| 6 | 8.224 | 7.465 | −9.2% | 9.261 | 7.569 | −18.3% | 7.70 (7.42..7.89) | 6.81 |
| 8 | 11.410 | 10.319 | −9.6% | 10.916 | 9.995 | −8.4% | 10.39 (10.16..10.51) | 8.95 |
| 12 | 10.855 | 11.338 | +4.4% | 10.682 | 10.608 | −0.7% | 11.24 (10.90..11.43) | 9.42 |
| 16 | 10.692 | 11.466 | +7.2% | 10.692 | 10.605 | −0.8% | 11.23 (10.94..11.32) | 9.51 |
| 64 | 10.241 | 11.113 | +8.5% | 10.439 | 10.282 | −1.5% | 10.27 (10.01..10.49) | 9.57 |

Other strides, noisy versus clean nVHE:
- Stride 64: −0.3 / −0.8 / −10.8% at 3 / 4 / 6 MB; +5.9 to +7.8% from 12 MB.
- Stride 128: −7.5 / −9.3 / −10.8 / −16.9% at 3 / 4 / 6 / 8 MB; +3.5 to +9.7% from 12 MB.
- Stride 512: −1.0 / −1.7 / −4.8% at 3 / 4 / 6 MB; +9.5 to +11.3% from 12 MB.
- Stride 1024: +5.0 / +12.1 / +14.9 / +13.8% at 1 / 2 / 3 / 4 MB; −8.9% at 8 MB; +7.5 to +13.8% from 12 MB.
- Strides 16 and 32: within 1.4%.

8 MB stride 256 per iteration: clean 23/40 above 11.3 ns (kvmoff 4, nVHE 5, VHE 8, pkvm 6); noisy 0/10 (10.10-10.81); Fisher p = 0.0009. Guests: 17/30 against pVM 0/10 (p = 0.002).

### T4. The slow level in clean runs

| Quantity | Host (4 clean sets) | Guests (VHE, nVHE, NP) |
|---|---|---|
| Slow cells, strides 128-1024, at 8 / 12 / 16 / 24 / 32 / 48 / 64 MB | 55.6 / 11.9 / 6.2 / 6.9 / 3.1 / 3.1 / 1.9% of 160 | 50.8 / 5.8 / 0.8 / 3.3 / 0.8 / 0 / 0% of 120 |
| Stride 64 at 8 MB | 4/40 (vs 28, 22, 17, 22 of 40 for strides 128, 256, 512, 1024; p at most 1.9e-3) | 1/30 (vs 13-17 of 30) |
| 12 MB slow given 8 MB slow / not slow | 19/93 vs 3/107 (p = 6.5e-5) | 6/62 vs 2/88 (p = 0.066) |
| Slow-to-fast level ratio, sequential | 1.19 (stride 256, 8 MB: 12.35 vs 10.37 ns), 1.22-1.26 elsewhere | same |
| Random cells complete / partial fast, of 40 (host) or 30 (guest), at 12 / 16 / 24 / 32 / 48 / 64 MB | 1/0, 2/2, 3/1, 3/3, 1/6, 0/10; none at 3-8 MB | 2/0, 1/1, 1/3, 0/1, 0/3, 0/2; one at 8 MB |

bw_mem in clean runs (levels in MB/s):
- rd 16.78 MB: 19 low (mean 15073) and 21 high (18591), ratio 1.233; noisy 17698.
- wr 16.78 MB: 18 low (7173) and 22 high (8002), ratio 1.116.
- cp 8.39 MB: 16 low and 24 high, ratio 1.116.
- rd 33.55 and 67.11 MB: low in the same three iterations only.
- Cache-resident sizes are never fast in clean runs: wr 4.19 MB clean 17486-17722 against noisy 21071-21127; rd 8.39 MB clean at most 16710 against noisy at least 18600.

Timing facts from lmbench source:
- lat_mem_rd uses 100 ms timing intervals and 11 repetitions, about 1.2 s per point (lat_mem_rd.c:143, lib_timing.c:173). The chain is rewritten before every interval (lib_mem.c:186-273).
- bw_mem uses 10 ms intervals, about 0.13 s per point (bw_mem.c:109-133).
- N80 trans_stat under simple_ondemand, first 16.5 s after driver load: 21 jumps to 1800 MHz, mean dwell there 130 ms, 57% of the time at 600 MHz.

### T5. Other rows, noisy versus clean nVHE, and pVM versus NP guest

| Row | Host | Guest |
|---|---|---|
| L1 load | 2.224 vs 2.223 ns | 2.228 vs 2.226 ns |
| lat_ops (18 rows), null syscall | identical to the printed digit; 0.1028 vs 0.1029 us | identical within 0.9% |
| tlb | 48 vs 48 | 48 vs 48 |
| bw_mem rd at 4.19 / 8.39 / 16.78 / 67.11 MB | +5.7 / +15.9 / −5.9 / −7.1% | +6.4 / +23.9 / +1.0 / +1.0% |
| bw_mem wr at 4.19 / 8.39 / 16.78 MB | +19.5 / +16.7 / −1.6% | +19.9 / +21.0 / +0.5% |
| libc bcopy at 4-33 MB; bzero at 8-67 MB | −4 to −7%; −9 to −13% | +0.3 to +1.2%; 0% |
| par_mem at 4.2 / 8.4 / 16.8 / 33.6 MB | −23.2 / −26.7 / −23.9 / −16.7% (none up to 2 MB) | −22.6 / −27.7 / −23.0 / −21.4% |
| lat_ctx 64k x 96, 64k x 64, 32k x 96 | −11.8 / −11.6 / −10.2% | −18.0 / −17.2 / −15.5% |
| lat_tcp, lat_udp | +25% (noise services) | not applicable |

### T6. Runs and recorded metadata

| Data set | Date, uptime at start | Kernel, mode | Masking | Session evidence in mount table | Load average | State |
|---|---|---|---|---|---|---|
| day-1 host | 06-01 15:55, 39 min | 6.6.0-52 #43pkvm10, protected; big cores 3.1 GHz | none | portal + gvfs | 0.10 | fast (64 MB 133.9 ns) |
| day-1 quiet, N5 | 06-01 19:09 and 19:16, 2-25 min | same, 2.1 GHz | quiet-host.sh stop | none, then gvfs | 0.2-1.1 | fast |
| day-2 default and nVHE | 06-01 21:03; 06-02 09:08, 09:38 | same, default / nVHE | none | portal + gvfs | about 1.0-1.1 | fast (nVHE: sequential stride 128 at 3 / 4 MB 4.625 / 4.699, identical to noisy) |
| noisy nVHE | 06-03 16:17, 9 min | 6.6.0-73 #76, nVHE, 1.9 GHz cap | incomplete (pvm-manage and AI services running, per documents) | gvfs from iteration 2, no portal | 1.00-1.08 | fast 10/10 |
| VHE, kvmoff, nVHE, pkvm try2 | 06-03 22:20 to 06-04 12:05, 5-7 min | same kernel, four modes | full; verify reported ALL CLEAN | none | 1.00-1.05 | traffic-following |
| pkvm try1 | 06-04 (documented) | protected | full | unknown | unknown | slow in iterations 1-3, fast in 4-10 |
| guest pVM | 06-05 13:31-16:28 CST | host state unrecorded | unknown | — | — | fast 10/10 |
| guests VHE, nVHE, NP | 06-05 17:16 to 06-06 16:45 CST | unrecorded | unknown (NP directory named 'clean') | — | — | traffic-following |
| N80 | 09-30, up about 1 h | 6.6.0-79 #93, protected; idle pVM in background | none (desktop) | — | 0.3-2.7 | nocfreq performance, 1800 MHz |

Masking scripts: apply-masks.sh lists 90 system and 12 user services, among them upower (line 57) and lightdm (line 49), and sets multi-user.target (line 151). quiet-host.sh stops 38 services including upower, lightdm and OptiDaemon. No script reads or writes any devfreq node.

### T7. Driver facts (klinux drivers/devfreq/phytium_noc.c)

| Item | Tag 6.6.0-73.76 (443 lines; N90 June kernel) | HEAD, identical at 6.6.0-79.93 (649 lines; N80 kernel) |
|---|---|---|
| Default governor | DEVFREQ_GOV_SIMPLE_ONDEMAND (line 307) | same (line 476) |
| Polling; thresholds | polling_ms = 100 (344); upthreshold 80, downdifferential 10 (351-352) | same (528; 537-541) |
| Load metric | busy = maximum of four counters at offset 0x44 (WR_NOLAST_HANDSHARK_NUM) in blocks 0x400 apart, snapshotted and cleared every poll (46-65, 277-300); total = 320000 x rate x 100 / initial_freq. Comment: 'peak number of dmu read/write commands on the axi bus' | v1 identical (82-102, 381-396); new v2 device uses a 5-bit busy code with ramp-up and hysteresis (43-56, 225-253) |
| Frequency table | not in the driver; read from ACPI method PGCL, set by PSCF, read back by PGCF (85-236). N80 lists 1800, 1450, 1300, 1200, 1000, 950, 900, 650, 600 MHz | same |
| ACPI match | 'PHYT0047' only (422-425) | 'PHYT0047' (v1) and 'PHYT3010' (v2) (623-627) |
| Error path | cached rate is updated even when the ACPI set call fails (144-151) | same (258-264) |
| Build | CONFIG_ARM_PHYTIUM_NOC_DEVFREQ=m (kylinos_generic_defconfig:1855) | =m; module loaded on the N80 |

- Governor arithmetic at the tag (governor_simpleondemand.c): jump to maximum when busy exceeds 80% of total; keep above 70%; otherwise the target in kHz is busy x 0.075. So more than 8.45e6 counts per 100 ms at 600 MHz jumps to 1800 MHz, and at least 1.93e7 are needed to stay there.
- phytium_noc.c is unchanged between tags 6.6.0-52.51 and 6.6.0-73.76. The three later commits first appear in 6.6.0-75.80.
- No other kernel code references the device, so the governor can only be changed from user space.
