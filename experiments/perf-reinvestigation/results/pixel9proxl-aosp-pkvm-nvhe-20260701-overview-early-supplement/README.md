# Pixel 9 Pro XL overview-early supplement

Date: 2026-07-01

This directory contains the supplemental Pixel overview-early run used to extend
the lifecycle split and steady-access controls from 3 runs to 5 runs per mode.

- Device: Pixel 9 Pro XL (`komodo`), AOSP userdebug.
- Modes: protected and NVHE, switched with the Pixel komodo safe
  `vendor_kernel_boot_b` DTB bootargs flow.
- Purpose: supplement
  `experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260629-overview-early`.
- Command shape:
  `LAT_RUNS=0 SPLIT_RUNS=2 STEADY_RUNS=2 CPU=4 WAIT_THERMAL_MAX_MC=39000 bash experiments/perf-reinvestigation/pixel-run-overview-early.sh`.
- Temperature gate: wait for the maximum thermal zone to be below 39000 mC
  before each randomized task.

Raw row counts:

| Mode | `mmap_split_full.csv` | `thermal_gate.tsv` | `lat_mem_rd.txt` | `bw_mem.txt` | `bw_mmap_rd.txt` |
|---|---:|---:|---:|---:|---:|
| protected | 168 data rows | 180 task rows | 80 lines | 36 lines | 24 lines |
| NVHE | 168 data rows | 180 task rows | 80 lines | 36 lines | 24 lines |

All recorded task return codes are zero. After the NVHE supplement, the device
was restored to protected mode and verified against the original
`vendor_kernel_boot_b` backup:

`da27174be409b06dc61376cb6f1a444f1b4bcea257640e22c5f12836eaab6d3f`

The merged 5-run analysis directory is:

`experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260701-overview-early-5run`
