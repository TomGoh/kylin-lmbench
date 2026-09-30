All numbers in sections 1-3 were measured inside the guest.

## 0. What identifies each guest data set

| label used below (from the directory name) | directory | ENV_TAG in started.txt | report file prefix | first line of started.txt | reports | lines the parser did not recognise |
|---|---|---|---|---|---:|---:|
| VM on VHE host | xkernel-n90-kvm-vhe-20260605-201819 | xkernel-kvm | xkernel-kvm-cpu0 | Fri Jun  5 09:16:53 UTC 2026 | 10 | 530 |
| VM on nVHE host | xkernel-n90-kvm-nvhe-20260606-133103 | xkernel-kvm-nvhe | xkernel-kvm-nvhe-cpu0 | Sat Jun  6 02:30:07 UTC 2026 | 10 | 530 |
| NP VM on pKVM host | xkernel-n90-pkvm-np-clean-20260606-164648 | xkernel-pkvm-np | xkernel-pkvm-np-cpu0 | Sat Jun  6 05:47:06 UTC 2026 | 10 | 530 |
| set labelled pVM | xkernel-n90-pkvm-pvm-20260605-163040 | xkernel-pkvm-np | xkernel-pkvm-np-cpu0 | Fri Jun  5 05:31:53 UTC 2026 | 10 | 530 |

No file of these directories records the host boot mode, the host kernel, the VM type or the crosvm command line.  The set labelled pVM has the same ENV_TAG as the non-protected set.

## 1. Guest random access (lmbench -t, stride 16), ns

Ratios are given as median-based / mean-based; Figure 8 uses 10-run means.

| size | VM on VHE host (median) | VM on nVHE host (median) | NP VM on pKVM host (median) | set labelled pVM (median) | pVM vs nVHE VM | pVM vs VHE VM | NP vs nVHE VM | pVM - nVHE VM (ns, medians) | pVM runs below all 30 other runs |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 0.5 MB | 12.67 | 11.76 | 12.29 | 11.91 | +1.3% / -0.6% | -6.0% / -7.2% | +4.5% / +2.2% | +0.1 | 0/10 |
| 0.75 MB | 16.77 | 17.00 | 17.07 | 17.26 | +1.5% / +0.9% | +2.9% / +2.0% | +0.4% / -0.5% | +0.3 | 0/10 |
| 1 MB | 19.59 | 19.70 | 19.58 | 19.73 | +0.1% / +0.5% | +0.7% / +0.6% | -0.6% / -0.4% | +0.0 | 0/10 |
| 1.5 MB | 21.26 | 20.83 | 20.87 | 20.84 | +0.0% / -0.5% | -2.0% / -1.1% | +0.2% / +0.6% | +0.0 | 1/10 |
| 2 MB | 23.69 | 23.96 | 23.76 | 22.38 | -6.6% / -5.5% | -5.5% / -6.3% | -0.8% / -1.2% | -1.6 | 3/10 |
| 3 MB | 39.39 | 39.44 | 39.44 | 29.00 | -26.5% / -26.4% | -26.4% / -25.7% | -0.0% / -0.0% | -10.4 | 10/10 |
| 4 MB | 51.84 | 52.30 | 52.62 | 35.97 | -31.2% / -31.2% | -30.6% / -30.9% | +0.6% / +0.8% | -16.3 | 10/10 |
| 6 MB | 78.88 | 81.13 | 80.68 | 55.34 | -31.8% / -31.7% | -29.8% / -29.8% | -0.6% / -0.6% | -25.8 | 10/10 |
| 8 MB | 124.97 | 126.83 | 126.53 | 97.85 | -22.8% / -22.5% | -21.7% / -19.7% | -0.2% / -0.6% | -29.0 | 4/10 |
| 12 MB | 164.41 | 165.03 | 164.76 | 129.49 | -21.5% / -20.0% | -21.2% / -19.5% | -0.2% / +1.6% | -35.5 | 9/10 |
| 16 MB | 176.90 | 176.73 | 177.05 | 141.20 | -20.1% / -18.7% | -20.2% / -18.8% | +0.2% / +1.5% | -35.5 | 10/10 |
| 24 MB | 185.11 | 184.54 | 185.92 | 147.25 | -20.2% / -16.7% | -20.5% / -20.4% | +0.7% / +3.6% | -37.3 | 10/10 |
| 32 MB | 187.93 | 189.92 | 189.23 | 150.18 | -20.9% / -20.6% | -20.1% / -19.2% | -0.4% / -1.0% | -39.7 | 10/10 |
| 48 MB | 192.80 | 191.46 | 191.47 | 151.07 | -21.1% / -19.6% | -21.6% / -21.4% | +0.0% / +0.0% | -40.4 | 10/10 |
| 64 MB | 192.94 | 192.00 | 192.35 | 152.91 | -20.4% / -20.2% | -20.8% / -20.2% | +0.2% / -1.2% | -39.1 | 10/10 |

## 2. Guest random access per iteration (ns)

8 MB:

- VM on VHE host: 97.8 126.2 124.6 123.6 125.8 126.6 125.9 124.9 125.1 124.7
- VM on nVHE host: 128.2 126.3 126.0 125.3 130.4 127.0 127.1 126.9 125.8 126.7
- NP VM on pKVM host: 125.1 127.1 126.6 126.2 126.6 124.9 126.7 126.6 126.2 126.5
- set labelled pVM: 97.4 101.6 99.0 97.1 97.4 98.4 97.8 95.8 97.9 101.9

64 MB:

- VM on VHE host: 192.8 192.7 189.7 193.2 193.2 193.7 193.4 192.8 193.0 186.7
- VM on nVHE host: 191.3 191.3 191.5 192.0 191.9 192.0 192.0 192.4 192.4 192.5
- NP VM on pKVM host: 186.6 180.4 192.2 192.4 180.4 192.8 192.3 192.4 193.1 192.8
- set labelled pVM: 152.2 155.5 152.6 152.5 153.1 152.6 152.9 153.2 152.9 154.9

## 3. Guest sequential access, ns

Stride 256 at 8 MB, per iteration.  Three of the sets take two values, as the quiesced hosts do; a ratio of medians or of means at this point mostly reflects how many iterations fell on the high value.

- VM on VHE host: 11.06 9.90 12.37 12.41 12.37 11.89 9.96 12.35 10.00 9.94  (mean 11.226, median 11.475, max/min 1.25)
- VM on nVHE host: 12.26 12.36 11.08 10.10 10.31 12.58 12.45 12.38 12.46 12.43  (mean 11.842, median 12.370, max/min 1.24)
- NP VM on pKVM host: 12.24 12.42 10.04 12.46 10.06 12.55 10.03 10.12 11.45 10.38  (mean 11.175, median 10.916, max/min 1.25)
- set labelled pVM: 9.87 10.00 9.99 9.89 9.93 10.04 10.15 10.10 9.94 10.02  (mean 9.993, median 9.995, max/min 1.03)

| stride | size | VM on VHE host (median) | VM on nVHE host (median) | NP VM on pKVM host (median) | set labelled pVM (median) | pVM vs nVHE VM (medians / means) | max/min over iterations: VM on VHE host / VM on nVHE host / NP VM on pKVM host / set labelled pVM |
|---:|---:|---:|---:|---:|---:|---:|---|
| 16 | 8 MB | 2.345 | 2.349 | 2.349 | 2.348 | -0.06% / -0.14% | 1.00 / 1.01 / 1.01 / 1.01 |
| 16 | 64 MB | 2.353 | 2.358 | 2.359 | 2.369 | +0.45% / +0.40% | 1.01 / 1.01 / 1.01 / 1.01 |
| 32 | 8 MB | 2.713 | 2.712 | 2.710 | 2.721 | +0.35% / +0.51% | 1.01 / 1.01 / 1.06 / 1.02 |
| 32 | 64 MB | 2.737 | 2.732 | 2.733 | 2.744 | +0.44% / +0.40% | 1.01 / 1.01 / 1.01 / 1.02 |
| 64 | 8 MB | 4.156 | 4.133 | 4.183 | 4.135 | +0.04% / -0.22% | 1.21 / 1.06 / 1.04 / 1.03 |
| 64 | 64 MB | 4.368 | 4.266 | 4.346 | 4.316 | +1.18% / +1.16% | 1.02 / 1.01 / 1.01 / 1.03 |
| 128 | 8 MB | 9.130 | 9.095 | 10.771 | 9.008 | -0.95% / -8.76% | 1.25 / 1.25 / 1.25 / 1.03 |
| 128 | 64 MB | 9.015 | 8.862 | 8.968 | 8.923 | +0.69% / +0.77% | 1.01 / 1.03 / 1.02 / 1.02 |
| 256 | 8 MB | 11.475 | 12.370 | 10.916 | 9.995 | -19.20% / -15.61% | 1.25 / 1.24 / 1.25 / 1.03 |
| 256 | 64 MB | 10.369 | 10.178 | 10.439 | 10.282 | +1.02% / +0.83% | 1.01 / 1.01 / 1.09 / 1.02 |
| 512 | 8 MB | 9.313 | 9.508 | 11.117 | 9.218 | -3.04% / -8.08% | 1.24 / 1.26 / 1.23 / 1.04 |
| 512 | 64 MB | 9.841 | 9.620 | 9.724 | 9.720 | +1.04% / +0.82% | 1.06 / 1.03 / 1.05 / 1.01 |
| 1024 | 8 MB | 12.224 | 11.249 | 11.947 | 10.282 | -8.60% / -8.02% | 1.23 / 1.24 / 1.24 / 1.05 |
| 1024 | 64 MB | 11.477 | 11.238 | 11.354 | 11.304 | +0.59% / -0.60% | 1.02 / 1.09 / 1.10 / 1.02 |

## 4. Guest next to host, random access medians in ns

Host columns were measured on the host Linux, outside any VM.  The first two host sets were taken with the background services masked; the third was taken before they were masked and is the host set whose curve the set labelled pVM follows.  Comparing a guest column with a host column of the other kind compares two states of the machine, not guest with host.

| size | host kvmoff, quiesced | host pkvm (try2), quiesced | host nvhe, not quiesced | VM on VHE host | VM on nVHE host | NP VM on pKVM host | set labelled pVM | set labelled pVM minus host nvhe, not quiesced |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 MB | 20.68 | 20.88 | 21.10 | 23.69 | 23.96 | 23.76 | 22.38 | +1.28 |
| 3 MB | 36.60 | 37.31 | 26.41 | 39.39 | 39.44 | 39.44 | 29.00 | +2.59 |
| 4 MB | 47.59 | 49.31 | 30.80 | 51.84 | 52.30 | 52.62 | 35.97 | +5.17 |
| 6 MB | 67.14 | 72.59 | 48.61 | 78.88 | 81.13 | 80.68 | 55.34 | +6.72 |
| 8 MB | 112.54 | 119.59 | 83.90 | 124.97 | 126.83 | 126.53 | 97.85 | +13.95 |
| 12 MB | 154.65 | 161.68 | 121.82 | 164.41 | 165.03 | 164.76 | 129.49 | +7.67 |
| 16 MB | 168.54 | 176.28 | 134.23 | 176.90 | 176.73 | 177.05 | 141.20 | +6.97 |
| 24 MB | 177.23 | 185.59 | 143.08 | 185.11 | 184.54 | 185.92 | 147.25 | +4.17 |
| 32 MB | 180.61 | 188.66 | 146.20 | 187.93 | 189.92 | 189.23 | 150.18 | +3.98 |
| 48 MB | 182.66 | 189.56 | 149.10 | 192.80 | 191.46 | 191.47 | 151.07 | +1.97 |
| 64 MB | 185.23 | 191.73 | 150.12 | 192.94 | 192.00 | 192.35 | 152.91 | +2.78 |
