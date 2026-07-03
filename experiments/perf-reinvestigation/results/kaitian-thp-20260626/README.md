# Kaitian THP-mitigation A/B (2026-06-26)

Does THP shrink the pKVM munmap/teardown regression on a platform **without FEAT_TLBIRANGE**?
Full **protected × nvhe** A/B on Kaitian (Phytium / Kylin V10 SP1, `6.6.30-pkvm-clean`).
Analysis & write-up: [`docs/mmap/pkvm-thp-mitigation.zh-CN.md`](../../../../docs/mmap/pkvm-thp-mitigation.zh-CN.md).
Plan: [`docs/mmap/kaitian-thp-mmap-experiment-plan.zh-CN.md`](../../../../docs/mmap/kaitian-thp-mmap-experiment-plan.zh-CN.md).

## Environment (both legs, see `{protected,nvhe}/metadata.txt`)
THP=always, ASLR=0, governor=performance @1.9 GHz, `taskset -c 0`, quiet-host; only `kvm-arm.mode` differs.

## Headline — protected−nvhe gap = the pKVM tax (median µs)

| workload (64 MB) | metric | protected | nvhe | **gap** |
|---|---|---:|---:|---:|
| ext4 file | lat_mmap THP=always | 631.7 | 423.3 | **+208** |
| ext4 file | lat_mmap THP=never | 634.4 | 422.1 | **+212** |
| ext4 file | op_sweep teardown (always/never) | 293 | 89 | **+204** |
| tmpfs/shmem (huge) | lat_mmap | 13.9 | 13.5 | **+0.4** |
| tmpfs/shmem (huge) | op_sweep teardown | 3.4 | 3.4 | **0** |
| anon 8 MB sparse | base / huge | 47.8 / 5.0 | 21.6 / 5.0 | **+26 → 0** |
| anon 16 MB sparse | base / huge | 89.5 / 5.1 | 39.4 / 5.1 | **+50 → 0** |
| anon 64 MB sparse | base / huge | 120 / 20 | 120 / 20 | −0 / +0.3 |

Global THP=always does nothing for ext4 (tax unchanged); the same shared workload on THP-capable shmem
collapses +208→+0.4 µs; anon loses the tax in the sub-2 MB regime. ext4 +204 µs ≈ 1630 slot × 0.125 µs/slot.

## Files per leg
`metadata.txt` · `e1-anon-sweep.txt` / `e1-anon-dense.txt` / `e1-huge-check.txt` (E1) ·
`e2-file-thp.txt` (E2) · `e3-tmpfs.txt` / `e3-huge-check.txt` (E3).

## Reproduce
`bash experiments/munmap-tlbi/thp-leg.sh <protected|nvhe>` then
`python3 experiments/munmap-tlbi/analyze-thp.py <leg-dir>`.
