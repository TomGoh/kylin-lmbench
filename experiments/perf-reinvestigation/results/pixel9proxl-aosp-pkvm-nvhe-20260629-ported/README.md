# Pixel 9 Pro XL ported N80/N90/Kaitian userland suite

Date: 2026-06-29
Device: Pixel 9 Pro XL / komodo / AOSP userdebug
Modes: `protected` vs `nvhe`

This directory contains the Pixel port of the userland portions of the N80/N90/Kaitian mmap teardown work:

- `lat_mmap_precise` 64 MB sparse point
- `mmap_split_bench` 64 MB selected lifecycle points
- `munmap_only` dense threshold scan plus sparse reference
- `op_sweep` for `munmap`, `MADV_DONTNEED`, and `mprotect`
- backing comparisons: file / `anon_base` / `anon_huge`
- `munmap_bench`
- `huge_check` for anon/tmpfs huge-page engagement

The following were not portable to Pixel AOSP userland and are intentionally not run here:

- `tlbi_ab.ko` direct TLBI kernel module
- `/proc/xcore_stats` EL2 PMU gate and host stage-2 introspection
- core hotplug / frequency-locking sweeps from the Kylin boards

The run used the same pre-test thermal gate as the MADV and overview-early runs: wait until max thermal zone is below `39000` mC before each subtest.

## Files

- `raw/protected/`, `raw/nvhe/`: raw command output and thermal/frequency gate logs
- `metadata/`: mode/hash verification and binary hashes
- `summary/ported-suite-measurements.csv`: parsed measurements
- `summary/ported-suite-diff.csv`: protected minus nvhe diff for comparable numeric rows

## Key Directional Points

This suite was run once per point, so treat the numbers as directional coverage, not final statistics.

64 MB sparse `lat_mmap_precise`:

| protected us | nvhe us | protected - nvhe | ratio |
|---:|---:|---:|---:|
| 678.845 | 674.096 | +4.749 | 1.007 |

`munmap_only` dense threshold scan selected points:

| point | protected us | nvhe us | protected - nvhe | ratio |
|---|---:|---:|---:|---:|
| 1.9 MB dense | 59.6 | 59.6 | +0.0 | 1.000 |
| 2.0 MB dense | 49.6 | 50.5 | -0.9 | 0.982 |
| 6.4 MB sparse | 54.3 | 49.3 | +5.0 | 1.101 |
| 64 MB dense | 1095.7 | 1066.3 | +29.4 | 1.028 |

`op_sweep munmap` selected points:

| point | protected us | nvhe us | protected - nvhe | ratio |
|---|---:|---:|---:|---:|
| 1.9 MB dense | 58.4 | 52.0 | +6.4 | 1.123 |
| 2.0 MB dense | 57.6 | 58.8 | -1.2 | 0.980 |
| 6.4 MB sparse | 42.9 | 45.4 | -2.5 | 0.945 |
| 64 MB dense | 1089.2 | 1058.7 | +30.5 | 1.029 |

`mprotect` is essentially flat at 64 MB (`+1.5 us`, ratio `1.006`). `MADV_DONTNEED` and `munmap` show small mixed deltas, not the large monotonic Phytium-style protected penalty.

`huge_check` reported `AnonHugePages=0`, `ShmemPmdMapped=0`, and `FilePmdMapped=0` for the tested anon/tmpfs geometries on this Pixel run, so `anon_huge`/tmpfs entries cannot be interpreted as successful huge-page mitigation tests.

## Interpretation

The portable userland suite does not reproduce the N80/Kaitian 2 MB cliff as a large protected-vs-nvhe teardown penalty on Pixel. The small 64 MB dense deltas are far below the Phytium-style effect and are not accompanied by a decisive sparse `lat_mmap` or isolated `munmap_after_write_touch` signal.

The non-portable pieces remain important caveats: this run cannot directly measure bare TLBI instruction cost, EL2-only cycles, or host stage-2 page-table granularity on Pixel without kernel support.
