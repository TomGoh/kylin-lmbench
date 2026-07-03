# Pixel 9 Pro XL overview-early 5-run combined result

Date: 2026-07-01

This directory combines the original Pixel overview-early run with the 2026-07-01
supplemental split/steady run:

- Original source: `experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260629-overview-early`
- Supplemental source: `experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260701-overview-early-supplement`

Combination policy:

- `lat_mmap_precise` is copied from the original source unchanged; it already had
  5 runs per size and mode.
- `mmap_split_full.csv`, `lat_mem_rd.txt`, `bw_mem.txt`, and `bw_mmap_rd.txt`
  combine the original 3 runs with the supplemental 2 runs.
- Supplemental run labels are renumbered from run 1/2 to run 4/5 in this combined
  directory only. The source directories are not modified.
- Temperature gate logs are combined with the same run-label renumbering.

Use `experiments/perf-reinvestigation/pixel-analyze-overview-early.py --result-dir experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260701-overview-early-5run`
to regenerate `summary/overview-early-*.csv`.
