# Pixel 9 Pro XL overview-early pKVM/nVHE run

Date: 2026-06-29
Device: Pixel 9 Pro XL / komodo / AOSP userdebug
Modes: `protected` vs `nvhe`, switched by same-length `vendor_kernel_boot_b` DTB bootargs override.

This run ports the early experiments from `docs/mmap/pkvm-mmap-overview.zh-CN.md`:

- Stage 1: multi-size `lat_mmap_precise`
- Stage 1 controls: `lat_mem_rd`, `bw_mem`, `bw_mmap_rd`
- Stage 2: full 12-way `mmap_split_bench` lifecycle matrix

Pixel repeat counts are reduced from the original N90/Kaitian overview runs to keep the phone inside the thermal gate:

- `LAT_RUNS=5`
- `SPLIT_RUNS=3`
- `STEADY_RUNS=3`
- thermal gate: wait before each subtest until max thermal zone is below `39000` mC

The phone was restored to byte-perfect protected state after the run:

- final live mode: `kvm-arm.mode=protected`
- final `vendor_kernel_boot_b` sha256: `da27174be409b06dc61376cb6f1a444f1b4bcea257640e22c5f12836eaab6d3f`

## Files

- `raw/protected/`, `raw/nvhe/`: raw command output and thermal/frequency gate logs
- `metadata/`: mode/hash verification and binary hashes
- `summary/overview-early-measurements.csv`: parsed per-run measurements
- `summary/overview-early-summary.csv`: per-mode medians
- `summary/overview-early-diff.csv`: protected minus nvhe medians

## Key Results

`lat_mmap_precise`, median us/iteration:

| size MB | protected | nvhe | protected - nvhe | ratio |
|---:|---:|---:|---:|---:|
| 0.5 | 11.744 | 11.493 | +0.251 | 1.022 |
| 1 | 15.515 | 16.721 | -1.206 | 0.928 |
| 2 | 23.135 | 24.969 | -1.835 | 0.927 |
| 4 | 52.428 | 40.904 | +11.524 | 1.282 |
| 8 | 90.666 | 88.049 | +2.617 | 1.030 |
| 16 | 168.236 | 165.236 | +3.000 | 1.018 |
| 64 | 630.541 | 631.601 | -1.060 | 0.998 |

64 MB lifecycle split, median us/iteration:

| subtest | protected | nvhe | protected - nvhe | ratio |
|---|---:|---:|---:|---:|
| `mmap_unmap` | 8.308 | 10.051 | -1.743 | 0.827 |
| `write_touch_cold` | 594.990 | 572.529 | +22.461 | 1.039 |
| `munmap_after_no_touch` | 1.726 | 1.665 | +0.061 | 1.037 |
| `munmap_after_write_touch` | 45.084 | 44.744 | +0.341 | 1.008 |
| `mmap_write_touch_unmap` | 644.211 | 534.487 | +109.724 | 1.205 |
| `mmap_read_touch_unmap` | 398.596 | 388.784 | +9.812 | 1.025 |

`munmap_after_write_touch` size sweep, median us/iteration:

| size MB | protected | nvhe | protected - nvhe | ratio |
|---:|---:|---:|---:|---:|
| 0.5 | 5.182 | 2.952 | +2.230 | 1.756 |
| 1 | 5.574 | 5.440 | +0.134 | 1.025 |
| 2 | 7.446 | 7.705 | -0.259 | 0.966 |
| 4 | 9.955 | 11.559 | -1.604 | 0.861 |
| 8 | 14.218 | 15.495 | -1.277 | 0.918 |
| 16 | 15.709 | 18.342 | -2.633 | 0.856 |
| 64 | 45.084 | 44.744 | +0.341 | 1.008 |

Steady controls:

| test | protected | nvhe | protected - nvhe | ratio |
|---|---:|---:|---:|---:|
| `lat_mem_rd` 64 MB stride 128, ns/load | 3.518 | 3.477 | +0.041 | 1.012 |
| `bw_mem rd`, MB/s | 26410.41 | 26609.38 | -198.97 | 0.993 |
| `bw_mem wr`, MB/s | 16318.26 | 17563.17 | -1244.91 | 0.929 |
| `bw_mem rdwr`, MB/s | 16434.15 | 15561.48 | +872.67 | 1.056 |
| `bw_mmap_rd mmap_only`, MB/s | 24231.40 | 24122.52 | +108.88 | 1.005 |
| `bw_mmap_rd open2close`, MB/s | 8968.18 | 9585.61 | -617.43 | 0.936 |

## Interpretation

The Pixel does not reproduce the overview's Phytium/N90/Kaitian early signal.

The decisive Stage 2 signature on Phytium was that `munmap_after_write_touch` dominated the full `lat_mmap` delta. On this Pixel run, `munmap_after_write_touch` is essentially equal at 64 MB (`+0.341 us`, ratio `1.008`) and does not show a monotonic protected penalty across sizes.

The 64 MB `mmap_write_touch_unmap` split point is slower in protected, but the multi-size `lat_mmap_precise` 64 MB point is flat (`-1.060 us`, ratio `0.998`), and the isolated `munmap_after_write_touch` path is flat. Treat the full-path split delta as a secondary observation, not as evidence that the Phytium mechanism reproduced.

The steady controls are also broadly flat at the scale relevant to the original overview: `lat_mem_rd` differs by about `+0.041 ns/load`, and `bw_mmap_rd mmap_only` differs by about `+0.45%`.

Combined with the Pixel MADV per-entry and ported threshold/op-spectrum runs in the sibling result directory, the current behavioral picture is:

- Pixel protected has a measurable cost in forced single-page teardown probes.
- Real multi-page teardown paths on Pixel do not show the Phytium-style `munmap_after_write_touch` or 2 MB cliff signature.
- This is consistent with Tensor G4 using range/batched TLB maintenance paths that hide the per-entry cost in normal mmap lifecycle workloads.
