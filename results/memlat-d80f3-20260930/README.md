# Workstation measurements (Great Wall D80F3), 2026-09-30

Reference measurements on a machine with the same cores as the N80 and N90
laptops whose host does **not** run under a stage-2 translation.  Everything
here was run as an ordinary user: no root, no hardware counters, no change of
any system setting.  The programs are in `experiments/memlat-probe/`; the
matching N80 logs are in `results/memlat-n80-20260930/`.

## The machine

| | |
|---|---|
| Model | Great Wall 世恒 D80F3 (board GWMDDB1EL1T), host name D3000 |
| CPU | 8 x FTC862, `MIDR_EL1` 0x700f8620 (implementer 0x70, part 0x862), the same value as on the N80 |
| Clock | cpufreq driver `cppc_cpufreq`, governor `ondemand`, maximum 2500 MHz; the L1 reference chase gives 1.606 ns per hop = 4 cycles, i.e. 2.49 GHz during the measurements |
| Caches (sysfs) | L1d 64 KiB 4-way, L2 512 KiB 8-way per core (both as on the N80); level 3: 16 ways x 8192 sets shared by 4 cores (reported size 4096K); level 4: 8192K, 16 ways x 8192 sets, shared by all 8 cores |
| Memory | 31578828 kB |
| Kernel | Ubuntu 7.0.0-34-generic, 4 KiB pages, 48-bit virtual addresses, 4 page-table levels, `CONFIG_ARM64_CONTPTE=y` |
| Virtualisation | kernel log: `CPU: All CPU(s) started at EL2`, `kvm [1]: VHE mode initialized successfully`, `kvm [1]: IPA Size Limit: 48 bits`; no `kvm-arm.mode=` on the command line.  The host kernel runs at EL2 and user programs are translated by one stage only |
| Huge pages | `transparent_hugepage/enabled` = madvise, `defrag` = madvise; the sizes below 2 MiB are all `never` |
| PMU | `perf_event_paranoid` = 4, so an ordinary user cannot open counters; all `evXX=` fields read `na` |
| Load | the machine was in use (load average 5 to 7); every value is the minimum of 11 intervals of about 0.1 s |

Because the clock differs from the N80 (1.90 GHz) and no counters are
available, results are compared in cycles obtained from a reference in the
same process: `cyc_est = 4 x ns / l1_ns`, where `l1_ns` is the time per hop
of a pointer chase inside the L1 cache (4 cycles on this core).  On the N80
the medians of this estimate agree with the counted cycles within 0.4 per configuration.

## Files

| File | Experiment | Script | When |
|---|---|---|---|
| `expN-d80f3.log` | N: translation-only chase (`probe3 tlb`), CPUs 0, 4, 5, 7, 5 seeds each | `run18-translation-noroot.sh` | 21:40-21:44 |
| `expN4-d80f3.log` | N4: the same with the pages first touched in chain order or in ascending virtual order, CPUs 0 and 4, 8 repetitions each | `run21-prefault.sh` | 22:05-22:09 |
| `expT2.log` | T2: sequential chase after ascending, random or descending first touch, with 0, 1024 or 2048 MB held back by a stopped process | `run23-touch-order-noroot.sh` | 22:19-22:21 |
| `expH4-d80f3.log` `expH4-d80f3-shim.log` | H4: lmbench's own `lat_mem_rd -P 1 64 256` on buffers from `layoutshim.so` (sorted, shuffled within 8 MB, shuffled) and natural under `nothp`; the shim log has `adj=na` (no root) | `run27-lmbench-layout-shim.sh` | 23:06-23:18 |
| `expH5-d80f3.log` `expH5-d80f3-shim.log` | H5: the same for the other strides of the paper's command | `run28-lmbench-layout-strides.sh` | 23:21-23:40 |
| `expL2-d80f3.log` | L2: the same frames in sorted, reversed and shuffled virtual order, pages taken from transparent huge pages (`thplayout`) | `run24-thp-layout-noroot.sh` | 22:25-22:28 |

Tables: `results/memlat-n80-20260930/derived/state-tables.md`, sections
"Exp N", "Exp N4", "Exp T2", "Exp L2", "Exp H4" and "Exp H5" (written by
`experiments/memlat-probe/analyze-state-experiments.py`).

## What these data can and cannot show

- They are from another machine than the N80 and the N90: another board,
  another memory subsystem and cache hierarchy above L2, another kernel.  Only
  quantities that stay inside the core and its L1/L2 caches (the
  translation-only chase with at most 4096 cache lines of data) are compared
  across machines as numbers.
- The layout experiment (L2) is used for one qualitative statement: the effect
  of the virtual order of physically contiguous pages on the sequential chase
  exists on this core without a host stage-2.  Its size here (8% to 10%) is
  not a prediction for the laptops.
- Frame numbers cannot be read without root.  In L2 physical adjacency is
  known by construction (the pool consists of 2 MiB huge pages, confirmed by
  `thp_kb=`); in T2 it is unknown, which is why T2 has no conclusion.
