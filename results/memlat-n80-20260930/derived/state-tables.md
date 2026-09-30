## Exp R: sequential stride 256, fresh process per point, 20 laps; interconnect pinned at 1800 MHz

rebuild 0 = chain built once; rebuild 1 = chain rewritten before every timed interval, as lmbench does.  ns = minimum of 11 intervals.  adjacency = fraction of virtually adjacent pages that are also physically adjacent, in either direction.

| size | rebuild | n | min | median | max | max / min | CV | largest gap between neighbouring values | median adjacency | L3 refills per access | page walks per access |
|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 4 MB | 0 | 20 | 4.43 | 4.45 | 4.65 | 1.049 | 1.0% | 3.4% (4.50 to 4.65) | 0.500 | 0.490 | 0.0000 |
| 4 MB | 1 | 20 | 4.43 | 4.45 | 4.64 | 1.048 | 1.1% | 2.3% (4.54 to 4.64) | 0.497 | 0.489 | 0.0000 |
| 6 MB | 0 | 20 | 6.85 | 6.97 | 7.10 | 1.036 | 1.0% | 0.7% (6.88 to 6.93) | 0.358 | 0.684 | 0.0470 |
| 6 MB | 1 | 20 | 6.83 | 6.99 | 7.15 | 1.047 | 1.2% | 1.0% (7.08 to 7.15) | 0.356 | 0.684 | 0.0432 |
| 8 MB | 0 | 20 | 9.22 | 9.37 | 9.43 | 1.022 | 0.4% | 1.2% (9.22 to 9.34) | 0.272 | 0.783 | 0.0528 |
| 8 MB | 1 | 20 | 9.22 | 9.35 | 9.42 | 1.022 | 0.5% | 0.9% (9.22 to 9.30) | 0.271 | 0.782 | 0.0485 |
| 12 MB | 0 | 20 | 9.41 | 9.88 | 10.16 | 1.080 | 2.1% | 1.3% (9.41 to 9.54) | 0.341 | 0.864 | 0.0578 |
| 12 MB | 1 | 20 | 9.45 | 9.89 | 10.21 | 1.079 | 2.1% | 1.1% (9.45 to 9.56) | 0.333 | 0.865 | 0.0563 |
| 16 MB | 0 | 20 | 9.32 | 9.67 | 10.09 | 1.082 | 2.5% | 2.4% (9.71 to 9.94) | 0.462 | 0.902 | 0.0600 |
| 16 MB | 1 | 20 | 9.44 | 9.65 | 10.09 | 1.070 | 2.1% | 2.6% (9.68 to 9.93) | 0.467 | 0.902 | 0.0596 |
| 64 MB | 0 | 20 | 8.53 | 8.64 | 8.92 | 1.046 | 1.4% | 0.6% (8.72 to 8.77) | 0.857 | 0.984 | 0.0625 |
| 64 MB | 1 | 20 | 8.90 | 9.09 | 9.29 | 1.044 | 1.1% | 0.9% (9.16 to 9.24) | 0.859 | 0.985 | 0.0625 |

Rank correlation of the latency with the physical layout (both rebuild settings pooled):

| size | n | rho(ns, adjacency) | rho(ns, distinct 2 MiB regions) | adjacency range | ns range |
|---:|---:|---:|---:|---|---|
| 4 MB | 40 | -0.22 | +0.24 | 0.14-0.57 | 4.43-4.65 |
| 6 MB | 40 | -0.49 | +0.27 | 0.28-0.41 | 6.83-7.15 |
| 8 MB | 40 | -0.61 | +0.36 | 0.24-0.36 | 9.22-9.43 |
| 12 MB | 40 | -0.94 | +0.94 | 0.16-0.52 | 9.41-10.21 |
| 16 MB | 40 | -0.92 | +0.90 | 0.28-0.62 | 9.32-10.09 |
| 64 MB | 40 | -0.37 | +0.42 | 0.79-0.90 | 8.53-9.29 |

Frame reuse: in 114 of 120 pairs of consecutive processes at the same size, the ascending adjacency of one equals the descending adjacency of the next within 0.02, i.e. the second process received the frames the first one had just freed, in reverse order.

## Exp BG: memory traffic from other cores; interconnect pinned at 1800 MHz

Background: none; r1 = one other core reading 256 MB in a loop; w1 = one other core writing; w2 = two other cores writing.  Median of the runs (ns per access, minimum of 11 intervals), change against none.

| test on cpu0 | none | r1 | w1 | w2 |
|---|---:|---:|---:|---:|
| sequential stride 256, 4 MB | 4.43 | 12.38 (+180%) | 16.28 (+268%) | 23.30 (+426%) |
| sequential stride 256, 8 MB | 9.57 | 14.20 (+48%) | 20.38 (+113%) | 26.92 (+181%) |
| sequential stride 256, 64 MB | 9.12 | 13.43 (+47%) | 20.56 (+125%) | 27.05 (+196%) |
| random, 8 MB | 96.35 | 180.66 (+88%) | 217.16 (+125%) | 310.20 (+222%) |
| random, 64 MB | 151.11 | 196.96 (+30%) | 246.77 (+63%) | 334.94 (+122%) |

## Exp H: lmbench's own lat_mem_rd on the N80, interconnect pinned at 1800 MHz

Interconnect frequency samples during these runs (value: count): 1800000: 17367

### Random access (lat_mem_rd -t -P 1 64 16), ns per access

| size | N80 off: median of 5 sweeps (range) | N80 system: median of 2 sweeps (range) | N90 host, fast state (non-quiesced nVHE) | N90 host, quiesced nVHE | N90 host, quiesced protected |
|---:|---:|---:|---:|---:|---:|
| 1 MB | 18.8 (18.4-19.5) | 15.3 (15.2-15.4) | 19.0 | 19.5 | 19.4 |
| 2 MB | 21.4 (20.3-21.5) | 17.6 (17.5-17.6) | 21.1 | 20.8 | 20.9 |
| 3 MB | 28.3 (27.4-29.6) | 23.0 (23.0-23.0) | 26.4 | 36.6 | 37.3 |
| 4 MB | 34.7 (34.1-35.5) | 27.5 (27.2-27.8) | 30.8 | 47.7 | 49.3 |
| 6 MB | 62.6 (60.0-63.5) | 49.7 (49.4-49.9) | 48.6 | 67.3 | 72.6 |
| 8 MB | 101.5 (100.0-102.1) | 81.9 (81.7-82.0) | 83.9 | 112.6 | 119.6 |
| 12 MB | 132.1 (131.6-133.5) | 112.6 (112.2-112.9) | 121.8 | 154.8 | 161.7 |
| 16 MB | 143.5 (142.1-143.9) | 122.0 (121.9-122.1) | 134.2 | 168.6 | 176.3 |
| 24 MB | 147.9 (147.7-150.8) | 129.1 (128.8-129.3) | 143.1 | 177.5 | 185.6 |
| 32 MB | 150.4 (148.8-152.1) | 131.3 (130.9-131.7) | 146.2 | 180.8 | 188.7 |
| 48 MB | 151.2 (149.9-152.9) | 133.8 (133.7-134.0) | 149.1 | 182.4 | 189.6 |
| 64 MB | 153.5 (152.4-154.2) | 134.8 (134.6-134.9) | 150.1 | 185.0 | 191.7 |

The N80 was in protected mode with its core at 1.9 GHz; the N90 core ran at 1.8 GHz. Core-bound parts differ by 5.6% for that reason alone.

### Sequential access, stride 256 (lat_mem_rd -P 1 64 256 and the stride-256 part of the full command), ns per access

'high' = more than 12% above the median of the lower half of the values of that row, the rule used for the N90 data.

| buffer pages | size | n | min | median | max | max / min | CV | largest gap between neighbouring values | high | N90 quiesced hosts: high of 40 | N90 quiesced hosts: min-max |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| off | 4 MB | 18 | 4.81 | 4.83 | 4.95 | 1.028 | 0.6% | 1.8% (4.86 to 4.95) | 0/18 | 0/40 | 5.47-5.50 |
| off | 6 MB | 18 | 7.02 | 7.68 | 7.89 | 1.124 | 3.0% | 4.5% (7.10 to 7.42) | 0/18 | 0/40 | 8.12-8.64 |
| off | 8 MB | 18 | 10.16 | 10.38 | 10.51 | 1.034 | 0.8% | 0.9% (10.16 to 10.25) | 0/18 | 22/40 | 9.93-12.63 |
| off | 12 MB | 18 | 10.90 | 11.22 | 11.43 | 1.049 | 1.2% | 1.0% (10.90 to 11.01) | 0/18 | 5/40 | 10.58-13.78 |
| off | 16 MB | 18 | 10.92 | 11.21 | 11.32 | 1.036 | 1.1% | 0.9% (10.98 to 11.08) | 0/18 | 0/40 | 10.46-12.10 |
| off | 24 MB | 18 | 10.75 | 11.04 | 11.27 | 1.049 | 1.1% | 1.0% (11.16 to 11.27) | 0/18 | 1/40 | 10.21-12.38 |
| off | 32 MB | 18 | 10.40 | 10.72 | 11.09 | 1.067 | 1.9% | 1.1% (10.94 to 11.06) | 0/18 | 2/40 | 10.21-12.15 |
| off | 48 MB | 18 | 10.31 | 10.46 | 10.54 | 1.022 | 0.7% | 0.5% (10.40 to 10.45) | 0/18 | 1/40 | 10.01-11.65 |
| off | 64 MB | 18 | 10.01 | 10.29 | 10.49 | 1.047 | 1.2% | 0.9% (10.01 to 10.11) | 0/18 | 1/40 | 9.98-11.48 |
| system | 4 MB | 3 | 4.66 | 4.70 | 4.74 | 1.018 | 0.7% | 1.0% (4.66 to 4.70) | 0/3 | 0/40 | 5.47-5.50 |
| system | 6 MB | 3 | 6.74 | 6.81 | 6.88 | 1.021 | 0.9% | 1.1% (6.81 to 6.88) | 0/3 | 0/40 | 8.12-8.64 |
| system | 8 MB | 3 | 8.86 | 8.95 | 9.16 | 1.033 | 1.4% | 2.3% (8.95 to 9.16) | 0/3 | 22/40 | 9.93-12.63 |
| system | 12 MB | 3 | 9.38 | 9.42 | 9.60 | 1.023 | 1.0% | 1.9% (9.42 to 9.60) | 0/3 | 5/40 | 10.58-13.78 |
| system | 16 MB | 3 | 9.49 | 9.51 | 9.68 | 1.020 | 0.9% | 1.8% (9.51 to 9.68) | 0/3 | 0/40 | 10.46-12.10 |
| system | 24 MB | 3 | 9.55 | 9.58 | 9.71 | 1.017 | 0.7% | 1.4% (9.58 to 9.71) | 0/3 | 1/40 | 10.21-12.38 |
| system | 32 MB | 3 | 9.54 | 9.60 | 9.60 | 1.006 | 0.3% | 0.6% (9.54 to 9.60) | 0/3 | 2/40 | 10.21-12.15 |
| system | 48 MB | 3 | 9.52 | 9.61 | 9.67 | 1.016 | 0.6% | 0.9% (9.52 to 9.61) | 0/3 | 1/40 | 10.01-11.65 |
| system | 64 MB | 3 | 9.56 | 9.57 | 9.71 | 1.016 | 0.7% | 1.4% (9.57 to 9.71) | 0/3 | 1/40 | 9.98-11.48 |

8 MB values in the order taken (off): 10.39 10.48 10.34 10.36 10.29 10.36 10.43 10.38 10.41 10.46 10.39 10.16 10.32 10.40 10.46 10.51 10.25 10.27

### Sequential access at 8 MB for every stride (full command), ns per access

| stride | sweep 1 | sweep 2 |
|---:|---:|---:|
| 16 | 2.18 | 2.18 |
| 32 | 2.56 | 2.55 |
| 64 | 4.31 | 4.24 |
| 128 | 9.21 | 9.50 |
| 256 | 10.25 | 10.27 |
| 512 | 9.70 | 9.72 |
| 1024 | 10.82 | 10.96 |

## Exp S: random chase on pages taken from one 1 GiB physical slot at a time; interconnect pinned at 1800 MHz

Each slot is measured twice per run: pass 2 uses the same data pages after moving them to a new virtual range (new page-table pages).  ns = median of 5 full cycles.  'RAM in slot' and 'kernel or reserved inside' come from /proc/iomem; a slot that is not entirely ordinary RAM cannot be one 1 GiB stage-2 block.

### 32 MB per slot, pages picked: spread evenly over the slot, 1 run(s)

| slot (physical base) | RAM in slot | kernel or reserved inside | runs x passes | ns: median (min-max) | cycles | page walks per access | L1 refills | L2 refills | L3 refills | adjacency | distinct 2 MiB regions |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0x80000000 | 94% | 0 MB | 2 | 151.8 (151.2-152.4) | 288.4 | 1.000 | 1.000 | 1.051 | 0.980 | 0.00 | 135 |
| 0xc0000000 | 87% | 348 MB | 2 | 151.9 (151.5-152.4) | 288.8 | 1.000 | 1.000 | 1.044 | 0.981 | 0.00 | 107 |
| 0x2080000000 | 50% | 1 MB | 2 | 154.1 (153.1-155.2) | 292.3 | 1.000 | 1.000 | 1.061 | 0.991 | 0.28 | 33 |
| 0x20c0000000 | 100% | 0 MB | 2 | 164.3 (164.3-164.4) | 311.7 | 1.000 | 1.000 | 1.674 | 1.000 | 0.00 | 194 |
| 0x2100000000 | 100% | 0 MB | 2 | 152.3 (151.4-153.2) | 288.4 | 1.000 | 1.000 | 1.045 | 0.980 | 0.00 | 229 |
| 0x2140000000 | 100% | 0 MB | 2 | 154.1 (153.5-154.7) | 291.2 | 1.000 | 1.000 | 1.067 | 0.989 | 0.00 | 302 |
| 0x2180000000 | 100% | 0 MB | 2 | 153.1 (151.6-154.6) | 290.7 | 1.000 | 1.000 | 1.072 | 0.986 | 0.00 | 270 |
| 0x21c0000000 | 100% | 0 MB | 2 | 152.6 (151.8-153.3) | 289.7 | 1.000 | 1.000 | 1.058 | 0.984 | 0.00 | 272 |
| 0x2200000000 | 100% | 0 MB | 2 | 152.2 (151.5-152.9) | 288.8 | 1.000 | 1.000 | 1.052 | 0.981 | 0.00 | 282 |
| 0x2240000000 | 100% | 0 MB | 2 | 152.1 (151.5-152.7) | 288.2 | 1.000 | 1.000 | 1.047 | 0.978 | 0.00 | 295 |
| 0x2280000000 | 100% | 0 MB | 2 | 151.3 (151.2-151.4) | 287.8 | 1.000 | 1.000 | 1.042 | 0.977 | 0.00 | 295 |
| 0x22c0000000 | 100% | 0 MB | 2 | 154.6 (153.0-156.2) | 292.6 | 1.000 | 1.000 | 1.043 | 0.981 | 0.00 | 287 |
| 0x2300000000 | 100% | 0 MB | 2 | 154.2 (153.7-154.8) | 292.5 | 1.000 | 1.000 | 1.051 | 0.982 | 0.00 | 272 |
| 0x2340000000 | 100% | 368 MB | 2 | 151.9 (151.7-152.1) | 288.5 | 1.000 | 1.000 | 1.041 | 0.982 | 0.00 | 160 |

Pass 2 minus pass 1 over all slots and runs: median -0.76 ns, range -3.26 to +1.74 ns (n = 14).

### 32 MB per slot, pages picked: lowest addresses of the slot, 3 run(s)

| slot (physical base) | RAM in slot | kernel or reserved inside | runs x passes | ns: median (min-max) | cycles | page walks per access | L1 refills | L2 refills | L3 refills | adjacency | distinct 2 MiB regions |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0x80000000 | 94% | 0 MB | 6 | 150.9 (149.6-159.7) | 286.1 | 0.907 | 1.000 | 1.044 | 0.979 | 1.00 | 17 |
| 0xc0000000 | 87% | 348 MB | 6 | 151.9 (150.6-158.1) | 287.7 | 0.996 | 1.000 | 1.042 | 0.978 | 0.96 | 26 |
| 0x2080000000 | 50% | 1 MB | 6 | 152.6 (151.5-154.4) | 290.0 | 0.995 | 1.000 | 1.053 | 0.980 | 0.97 | 23 |
| 0x20c0000000 | 100% | 0 MB | 6 | 153.3 (152.2-154.4) | 291.0 | 0.997 | 1.000 | 1.071 | 0.979 | 0.97 | 22 |
| 0x2100000000 | 100% | 0 MB | 6 | 151.8 (149.6-152.3) | 287.4 | 0.996 | 1.000 | 1.043 | 0.979 | 0.99 | 17 |
| 0x2140000000 | 100% | 0 MB | 6 | 151.0 (150.5-152.3) | 286.6 | 0.997 | 1.000 | 1.041 | 0.976 | 0.96 | 20 |
| 0x2180000000 | 100% | 0 MB | 6 | 151.3 (150.7-153.1) | 287.2 | 0.997 | 1.000 | 1.040 | 0.979 | 0.86 | 84 |
| 0x21c0000000 | 100% | 0 MB | 6 | 151.3 (150.6-151.5) | 287.0 | 0.998 | 1.000 | 1.041 | 0.977 | 0.93 | 88 |
| 0x2200000000 | 100% | 0 MB | 6 | 151.1 (150.3-151.8) | 287.0 | 0.997 | 1.000 | 1.040 | 0.978 | 0.89 | 59 |
| 0x2240000000 | 100% | 0 MB | 6 | 151.9 (150.6-152.4) | 288.3 | 0.997 | 1.000 | 1.049 | 0.979 | 0.89 | 119 |
| 0x2280000000 | 100% | 0 MB | 6 | 150.6 (148.8-151.2) | 285.9 | 0.905 | 1.000 | 1.037 | 0.977 | 1.00 | 17 |
| 0x22c0000000 | 100% | 0 MB | 6 | 153.4 (153.1-164.1) | 291.1 | 0.999 | 1.000 | 1.040 | 0.977 | 0.95 | 58 |
| 0x2300000000 | 100% | 0 MB | 6 | 154.1 (153.2-160.6) | 292.0 | 0.996 | 1.000 | 1.041 | 0.981 | 0.87 | 82 |
| 0x2340000000 | 100% | 368 MB | 6 | 151.6 (150.9-156.2) | 287.3 | 0.996 | 1.000 | 1.042 | 0.977 | 0.89 | 47 |

Pass 2 minus pass 1 over all slots and runs: median +0.04 ns, range -2.16 to +8.06 ns (n = 42).

### 64 MB per slot, pages picked: lowest addresses of the slot, 1 run(s)

| slot (physical base) | RAM in slot | kernel or reserved inside | runs x passes | ns: median (min-max) | cycles | page walks per access | L1 refills | L2 refills | L3 refills | adjacency | distinct 2 MiB regions |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0x80000000 | 94% | 0 MB | 2 | 155.5 (155.4-155.7) | 295.1 | 0.997 | 1.000 | 1.178 | 0.996 | 0.99 | 33 |
| 0xc0000000 | 87% | 348 MB | 2 | 155.7 (155.7-155.8) | 295.4 | 0.981 | 1.000 | 1.174 | 1.000 | 0.97 | 72 |
| 0x20c0000000 | 100% | 0 MB | 2 | 160.5 (160.3-160.6) | 304.4 | 0.998 | 1.000 | 1.340 | 1.000 | 0.93 | 49 |
| 0x2100000000 | 100% | 0 MB | 2 | 155.8 (155.5-156.2) | 295.5 | 0.992 | 1.000 | 1.197 | 0.998 | 0.98 | 33 |
| 0x2140000000 | 100% | 0 MB | 2 | 155.3 (155.0-155.7) | 294.7 | 0.998 | 1.000 | 1.151 | 0.997 | 0.94 | 37 |
| 0x2180000000 | 100% | 0 MB | 2 | 155.9 (155.9-156.0) | 295.6 | 0.998 | 1.000 | 1.163 | 1.000 | 0.86 | 117 |
| 0x21c0000000 | 100% | 0 MB | 2 | 155.1 (155.0-155.1) | 294.4 | 0.990 | 1.000 | 1.165 | 0.995 | 0.96 | 107 |
| 0x2200000000 | 100% | 0 MB | 2 | 155.9 (155.9-155.9) | 295.8 | 0.998 | 1.000 | 1.157 | 1.000 | 0.90 | 114 |
| 0x2240000000 | 100% | 0 MB | 2 | 155.9 (155.7-156.1) | 295.7 | 0.999 | 1.000 | 1.174 | 0.998 | 0.93 | 136 |
| 0x2280000000 | 100% | 0 MB | 2 | 155.8 (155.7-155.9) | 295.7 | 0.997 | 1.000 | 1.156 | 1.000 | 1.00 | 34 |
| 0x22c0000000 | 100% | 0 MB | 2 | 158.0 (157.7-158.3) | 299.5 | 0.998 | 1.000 | 1.151 | 1.000 | 0.96 | 94 |
| 0x2300000000 | 100% | 0 MB | 2 | 157.2 (157.1-157.3) | 298.4 | 0.998 | 1.000 | 1.181 | 0.993 | 0.88 | 138 |
| 0x2340000000 | 100% | 368 MB | 2 | 155.1 (154.9-155.4) | 294.3 | 0.998 | 1.000 | 1.173 | 0.994 | 0.85 | 120 |

Pass 2 minus pass 1 over all slots and runs: median -0.12 ns, range -0.73 to +0.73 ns (n = 13).

## Exp V: host pages that share a 2 MiB region with the memory of the running protected VM, against pages that do not

Where the VM's memory sits (vm-frames-n80.txt):

```
mapping ffff67800000-ffffa7800000 rw-s size_mb=1024 name='/memfd:crosvm_guest (deleted)' present_pages=65249 (254 MB)
  slot=0x82 phys=0x2080000000 pages=1369 (5 MB) distinct_2mb_regions=80 of 512
  slot=0x83 phys=0x20c0000000 pages=26743 (104 MB) distinct_2mb_regions=165 of 512
  slot=0x84 phys=0x2100000000 pages=36972 (144 MB) distinct_2mb_regions=96 of 512
  slot=0x85 phys=0x2140000000 pages=100 (0 MB) distinct_2mb_regions=9 of 512
  slot=0x86 phys=0x2180000000 pages=16 (0 MB) distinct_2mb_regions=9 of 512
  slot=0x87 phys=0x21c0000000 pages=8 (0 MB) distinct_2mb_regions=7 of 512
  slot=0x88 phys=0x2200000000 pages=5 (0 MB) distinct_2mb_regions=4 of 512
  slot=0x89 phys=0x2240000000 pages=33 (0 MB) distinct_2mb_regions=14 of 512
  slot=0x8a phys=0x2280000000 pages=3 (0 MB) distinct_2mb_regions=2 of 512
wrote 386 region numbers to guest-regions.txt
```

class shared = the page lies in a 2 MiB region that also holds VM pages (host stage-2 split to 4 KiB there); class clear = it does not.  Same process, same GiB slot, same way of picking pages.  ns = median of 5 full cycles; two passes per set.

### 16 MB per set, pages picked: spread evenly, 1 run(s)

| slot (physical base) | class | measurements | ns: median (min-max) | cycles | page walks per access | L1 refills | L2 refills | L3 refills | distinct 2 MiB regions | shared minus clear: ns | cycles | L2 refills |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0x2080000000 | clear | 2 | 143.3 (143.0-143.6) | 272.6 | 1.000 | 1.000 | 1.005 | 0.941 | 29 | | | |
| 0x20c0000000 | clear | 2 | 144.4 (143.7-145.0) | 274.8 | 1.000 | 1.000 | 1.005 | 0.951 | 52 | | | |
| 0x20c0000000 | shared | 2 | 155.9 (155.4-156.4) | 295.7 | 1.000 | 1.000 | 1.562 | 0.950 | 134 | +11.5 | +21.0 | +0.557 |
| 0x2100000000 | clear | 2 | 144.0 (143.0-144.9) | 273.9 | 1.000 | 1.000 | 1.006 | 0.946 | 227 | | | |
| 0x2140000000 | clear | 2 | 144.9 (144.0-145.8) | 277.1 | 1.000 | 1.000 | 1.007 | 0.954 | 293 | | | |
| 0x2180000000 | clear | 2 | 143.7 (143.7-143.7) | 273.7 | 1.000 | 1.000 | 1.009 | 0.943 | 262 | | | |
| 0x21c0000000 | clear | 2 | 145.1 (143.9-146.3) | 275.8 | 1.000 | 1.000 | 1.008 | 0.951 | 275 | | | |
| 0x2200000000 | clear | 2 | 144.1 (143.2-145.0) | 273.0 | 1.000 | 1.000 | 1.006 | 0.942 | 269 | | | |
| 0x2240000000 | clear | 2 | 143.0 (142.9-143.1) | 271.7 | 1.000 | 1.000 | 1.009 | 0.936 | 308 | | | |
| 0x2280000000 | clear | 2 | 144.1 (143.1-145.2) | 273.9 | 1.000 | 1.000 | 1.008 | 0.943 | 346 | | | |
| 0x22c0000000 | clear | 2 | 144.7 (144.6-144.9) | 275.3 | 1.000 | 1.000 | 1.007 | 0.937 | 292 | | | |
| 0x2300000000 | clear | 2 | 146.1 (145.4-146.7) | 277.8 | 1.000 | 1.000 | 1.006 | 0.945 | 281 | | | |
| 0x2340000000 | clear | 2 | 145.1 (143.4-146.8) | 277.1 | 1.000 | 1.000 | 1.006 | 0.955 | 158 | | | |

class clear over all slots: 142.9-146.8 ns, median 144.0 ns (n = 24).
shared minus clear, per slot: 0x20c0000000: +11.5 ns, +21.0 cycles, +0.557 L2 refills, -0.000 L1 refills.

### 32 MB per set, pages picked: spread evenly, 3 run(s)

| slot (physical base) | class | measurements | ns: median (min-max) | cycles | page walks per access | L1 refills | L2 refills | L3 refills | distinct 2 MiB regions | shared minus clear: ns | cycles | L2 refills |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0x2080000000 | clear | 6 | 151.6 (151.2-152.3) | 288.3 | 1.000 | 1.000 | 1.044 | 0.980 | 29 | | | |
| 0x20c0000000 | clear | 6 | 151.5 (150.9-154.4) | 287.8 | 1.000 | 1.000 | 1.040 | 0.979 | 56 | | | |
| 0x20c0000000 | shared | 6 | 168.3 (166.4-168.4) | 319.1 | 1.000 | 1.000 | 1.877 | 1.000 | 135 | +16.8 | +31.4 | +0.837 |
| 0x2100000000 | clear | 6 | 151.4 (150.9-152.4) | 287.5 | 1.000 | 1.000 | 1.040 | 0.978 | 229 | | | |
| 0x2140000000 | clear | 6 | 151.4 (151.1-152.5) | 287.5 | 1.000 | 1.000 | 1.049 | 0.976 | 304 | | | |
| 0x2180000000 | clear | 6 | 151.5 (151.1-154.7) | 288.4 | 1.000 | 1.000 | 1.046 | 0.980 | 273 | | | |
| 0x21c0000000 | clear | 6 | 151.3 (151.1-154.4) | 288.1 | 1.000 | 1.000 | 1.045 | 0.979 | 285 | | | |
| 0x2200000000 | clear | 6 | 151.9 (151.0-154.6) | 288.3 | 1.000 | 1.000 | 1.047 | 0.980 | 280 | | | |
| 0x2240000000 | clear | 6 | 151.8 (151.0-152.2) | 288.3 | 1.000 | 1.000 | 1.046 | 0.978 | 323 | | | |
| 0x2280000000 | clear | 6 | 151.4 (151.1-152.0) | 287.5 | 1.000 | 1.000 | 1.043 | 0.976 | 343 | | | |
| 0x22c0000000 | clear | 6 | 153.4 (153.0-154.2) | 291.8 | 1.000 | 1.000 | 1.044 | 0.979 | 297 | | | |
| 0x2300000000 | clear | 6 | 153.3 (153.0-154.4) | 291.5 | 1.000 | 1.000 | 1.038 | 0.978 | 286 | | | |
| 0x2340000000 | clear | 6 | 151.5 (150.9-151.9) | 287.7 | 1.000 | 1.000 | 1.039 | 0.978 | 158 | | | |

class clear over all slots: 150.9-154.7 ns, median 151.7 ns (n = 72).
shared minus clear, per slot: 0x20c0000000: +16.8 ns, +31.4 cycles, +0.837 L2 refills, -0.000 L1 refills.

### 32 MB per set, pages picked: lowest addresses, 1 run(s)

| slot (physical base) | class | measurements | ns: median (min-max) | cycles | page walks per access | L1 refills | L2 refills | L3 refills | distinct 2 MiB regions | shared minus clear: ns | cycles | L2 refills |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0x2080000000 | clear | 2 | 151.2 (151.1-151.3) | 287.1 | 0.997 | 1.000 | 1.047 | 0.975 | 19 | | | |
| 0x20c0000000 | clear | 2 | 151.4 (150.9-151.9) | 288.1 | 0.957 | 1.000 | 1.043 | 0.983 | 19 | | | |
| 0x20c0000000 | shared | 2 | 156.3 (156.1-156.5) | 297.1 | 0.948 | 1.000 | 1.144 | 0.978 | 18 | +4.9 | +9.0 | +0.101 |
| 0x2100000000 | clear | 2 | 151.9 (151.4-152.5) | 288.4 | 1.000 | 1.000 | 1.044 | 0.981 | 17 | | | |
| 0x2140000000 | clear | 2 | 151.7 (151.0-152.4) | 288.6 | 0.995 | 1.000 | 1.039 | 0.981 | 19 | | | |
| 0x2180000000 | clear | 2 | 152.5 (152.0-153.0) | 289.0 | 0.996 | 1.000 | 1.040 | 0.983 | 72 | | | |
| 0x21c0000000 | clear | 2 | 151.5 (151.3-151.7) | 287.4 | 0.993 | 1.000 | 1.045 | 0.977 | 95 | | | |
| 0x2200000000 | clear | 2 | 150.8 (150.7-150.9) | 286.1 | 0.992 | 1.000 | 1.033 | 0.973 | 42 | | | |
| 0x2240000000 | clear | 2 | 153.3 (151.9-154.7) | 290.9 | 0.997 | 1.000 | 1.050 | 0.989 | 115 | | | |
| 0x2280000000 | clear | 2 | 152.7 (150.9-154.4) | 289.1 | 0.993 | 1.000 | 1.043 | 0.984 | 17 | | | |
| 0x22c0000000 | clear | 2 | 153.3 (152.8-153.9) | 290.9 | 0.999 | 1.000 | 1.035 | 0.976 | 61 | | | |
| 0x2300000000 | clear | 2 | 153.6 (153.1-154.1) | 291.6 | 0.996 | 1.000 | 1.059 | 0.979 | 73 | | | |
| 0x2340000000 | clear | 2 | 151.6 (151.4-151.8) | 288.7 | 0.997 | 1.000 | 1.042 | 0.982 | 45 | | | |

class clear over all slots: 150.7-154.7 ns, median 151.8 ns (n = 24).
shared minus clear, per slot: 0x20c0000000: +4.9 ns, +9.0 cycles, +0.101 L2 refills, -0.000 L1 refills.

## Exp V2: shared against clear at working-set sizes from 2 MB to 64 MB

Per size: class clear over all slots (median and range of the per-set medians, two passes per set) and class shared over the slots that have enough shared pages.  extra = shared median minus clear median.  Below 6 MB the chase needs no page walks; there the spread of class clear across slots (different L3 placement) is the noise level.

| size | pages | page walks per access: clear / shared | clear: ns median (min-max), n | shared: ns median (min-max), n, slots | extra ns | extra cycles | extra cycles per walk | L2 refills: clear / shared | extra L2 refills |
|---:|---:|---|---|---|---:|---:|---:|---|---:|
| 2 MB | 512 | 0.000 / 0.000 | 21.0 (20.3-24.1), 24 | 20.9 (20.5-21.7), 6, 0x2080000000, 0x20c0000000, 0x2240000000 | -0.1 | -0.1 | no walks | 1.000 / 1.000 | +0.000 |
| 3 MB | 768 | 0.000 / 0.000 | 26.5 (26.2-26.9), 24 | 26.5 (26.1-27.0), 6, 0x2080000000, 0x20c0000000, 0x2240000000 | -0.0 | -0.0 | no walks | 1.000 / 1.000 | +0.000 |
| 4 MB | 1024 | 0.000 / 0.000 | 30.6 (30.2-39.4), 24 | 30.9 (30.4-32.4), 6, 0x2080000000, 0x20c0000000, 0x2240000000 | +0.3 | +0.5 | no walks | 1.000 / 1.000 | +0.000 |
| 6 MB | 1536 | 0.935 / 0.870 | 65.9 (63.5-76.5), 24 | 71.7 (71.3-72.1), 2, 0x20c0000000 | +5.8 | +9.9 | 11.4 | 0.999 / 1.078 | +0.080 |
| 8 MB | 2048 | 0.994 / 0.989 | 102.4 (100.6-106.6), 24 | 110.6 (109.7-111.6), 2, 0x20c0000000 | +8.2 | +15.2 | 15.4 | 1.000 / 1.170 | +0.171 |
| 12 MB | 3072 | 1.000 / 1.000 | 133.9 (132.6-145.5), 24 | 143.3 (143.2-143.4), 2, 0x20c0000000 | +9.4 | +18.2 | 18.2 | 1.002 / 1.368 | +0.366 |
| 16 MB | 4096 | 1.000 / 1.000 | 143.7 (141.4-148.1), 24 | 162.1 (161.9-162.3), 2, 0x20c0000000 | +18.4 | +34.5 | 34.5 | 1.007 / 1.570 | +0.563 |
| 24 MB | 6144 | 1.000 / 1.000 | 149.3 (148.6-151.7), 24 | 168.9 (168.7-169.1), 2, 0x20c0000000 | +19.6 | +35.8 | 35.8 | 1.019 / 1.937 | +0.918 |
| 32 MB | 8192 | 1.000 / 1.000 | 154.0 (150.7-156.0), 24 | 168.2 (168.2-168.2), 2, 0x20c0000000 | +14.2 | +28.1 | 28.1 | 1.043 / 1.878 | +0.834 |
| 48 MB | 12288 | 1.000 / 1.000 | 155.2 (153.7-157.4), 22 | 168.6 (168.5-168.7), 2, 0x20c0000000 | +13.4 | +25.6 | 25.6 | 1.108 / 1.930 | +0.822 |
| 64 MB | 16384 | 1.000 / 1.000 | 156.0 (154.9-158.3), 22 | 169.3 (169.3-169.4), 2, 0x20c0000000 | +13.4 | +25.5 | 25.5 | 1.161 / 1.970 | +0.809 |

## Exp V3: the shared-against-clear comparison repeated with other page sets

One page set of class shared per run (two passes); class clear from every slot of the same run.  extra = median of the shared set minus the median of class clear in the same run; 'same slot' uses only the clear set taken from the slot the shared set comes from.  Runs: V2 (seed 31) and V3 (seeds 41, 43, 47).

### Pages picked: spread evenly over the pool pages of the slot

| size | runs | extra ns per run | median (min-max) | relative | same slot: extra ns per run | extra cycles per run | page walks per access: clear / shared | extra L2 refills per run | distinct 2 MiB regions of the shared set |
|---:|---:|---|---|---:|---|---|---|---|---|
| 2 MB | 1 | -0.1 | -0.1 (-0.1 to -0.1) | -0.3% | +0.3 | -0.1 | 0.000 / 0.000 | +0.00 | 4 |
| 3 MB | 1 | -0.1 | -0.1 (-0.1 to -0.1) | -0.5% | -0.2 | +0.1 | 0.000 / 0.000 | -0.00 | 4 |
| 4 MB | 1 | -0.1 | -0.1 (-0.1 to -0.1) | -0.4% | -0.7 | -0.4 | 0.000 / 0.000 | +0.00 | 4 |
| 6 MB | 4 | +5.8, +5.2, +10.7, +7.2 | +6.5 (+5.2 to +10.7) | +9.9% | +6.6, +8.3, +5.7, +10.5 | +9.9, +10.7, +21.4, +11.9 | 0.939 / 0.881 | +0.08, +0.07, +0.07, +0.08 | 131, 133, 133, 133 |
| 8 MB | 4 | +8.2, +8.2, +8.5, +12.8 | +8.4 (+8.2 to +12.8) | +8.5% | +8.0, +8.0, +6.2, +12.6 | +15.2, +18.2, +16.0, +25.0 | 0.994 / 0.991 | +0.17, +0.18, +0.18, +0.17 | 132, 134, 133, 132 |
| 12 MB | 4 | +9.4, +11.1, +17.6, +10.7 | +10.9 (+9.4 to +17.6) | +8.3% | +6.5, +9.5, +15.3, +9.7 | +18.2, +19.8, +30.4, +20.5 | 1.000 / 1.000 | +0.37, +0.37, +0.35, +0.37 | 133, 134, 132, 134 |
| 16 MB | 4 | +18.4, +10.9, +18.7, +19.5 | +18.6 (+10.9 to +19.5) | +13.0% | +18.3, +12.4, +16.6, +20.2 | +34.5, +20.8, +33.9, +35.7 | 1.000 / 1.000 | +0.56, +0.56, +0.55, +0.55 | 134, 135, 134, 134 |
| 24 MB | 4 | +19.6, +17.9, +19.4, +19.5 | +19.5 (+17.9 to +19.6) | +13.1% | +20.0, +17.1, +19.2, +19.6 | +35.8, +34.1, +35.6, +37.0 | 1.000 / 1.000 | +0.92, +0.89, +0.87, +0.88 | 135, 135, 134, 134 |
| 32 MB | 4 | +14.2, +14.7, +14.1, +16.7 | +14.4 (+14.1 to +16.7) | +9.5% | +15.8, +14.9, +14.6, +16.6 | +28.1, +27.4, +27.6, +32.1 | 1.000 / 1.000 | +0.83, +0.84, +0.84, +0.83 | 135, 135, 136, 136 |
| 48 MB | 4 | +13.4, +14.7, +14.1, +13.8 | +14.0 (+13.4 to +14.7) | +9.0% | +13.6, +14.9, +14.5, +14.2 | +25.6, +27.5, +26.7, +26.2 | 1.000 / 1.000 | +0.82, +0.81, +0.78, +0.81 | 135, 136, 136, 136 |
| 64 MB | 4 | +13.4, +17.1, +13.4, +13.1 | +13.4 (+13.1 to +17.1) | +8.6% | +13.6, +17.4, +13.9, +13.3 | +25.5, +33.0, +25.2, +24.9 | 1.000 / 1.000 | +0.81, +0.82, +0.81, +0.79 | 135, 135, 137, 137 |

### Pages picked: lowest addresses (physically contiguous)

| size | runs | extra ns per run | median (min-max) | relative | same slot: extra ns per run | extra cycles per run | page walks per access: clear / shared | extra L2 refills per run | distinct 2 MiB regions of the shared set |
|---:|---:|---|---|---:|---|---|---|---|---|
| 16 MB | 1 | +2.3 | +2.3 (+2.3 to +2.3) | +1.6% | +1.3 | +3.2 | 0.992 / 0.809 | +0.03 | 10 |
| 32 MB | 1 | +6.5 | +6.5 (+6.5 to +6.5) | +4.3% | +7.0 | +12.7 | 0.996 / 0.982 | +0.11 | 18 |
| 64 MB | 1 | +7.7 | +7.7 (+7.7 to +7.7) | +4.9% | +7.9 | +14.6 | 0.998 / 0.993 | +0.28 | 34 |

## Exp W: sequential chase (stride 256) over the same kind of page set in sorted and in shuffled virtual order, by page class

sorted = virtual order follows ascending physical address; shuffled = the same selection rule, pages mapped in a random virtual order.  clear = stage-2 block mappings; shared = 4 KiB stage-2 leaves (2 MiB regions shared with the VM).  ns = median over sets (slots) and the two passes.

| size | pages picked | class | slots | sorted: ns (min-max) | shuffled: ns (min-max) | shuffled vs sorted | page walks per access: sorted / shuffled | L2 refills: sorted / shuffled | adjacency when sorted |
|---:|---|---|---:|---|---|---:|---|---|---:|
| 8 MB | lowest addresses | clear | 12 | 8.18 (7.96-8.42) | 9.69 (9.59-9.81) | +18.5% | 0.0509 / 0.0545 | 0.279 / 0.265 | 0.91 |
| 8 MB | lowest addresses | shared | 1 | 8.11 (8.11-8.11) | 9.73 (9.72-9.74) | +20.0% | 0.0374 / 0.0484 | 0.285 / 0.265 | 0.95 |
| 8 MB | spread evenly | clear | 12 | 9.64 (9.38-9.87) | 9.65 (9.59-9.68) | +0.1% | 0.0539 / 0.0551 | 0.260 / 0.261 | 0.00 |
| 8 MB | spread evenly | shared | 1 | 9.69 (9.66-9.71) | 9.69 (9.69-9.69) | +0.0% | 0.0420 / 0.0426 | 0.264 / 0.267 | 0.00 |
| 16 MB | lowest addresses | clear | 12 | 8.38 (8.05-8.69) | 10.49 (10.36-10.59) | +25.2% | 0.0571 / 0.0606 | 0.580 / 0.498 | 0.92 |
| 16 MB | lowest addresses | shared | 1 | 8.19 (8.19-8.19) | 10.40 (10.40-10.41) | +27.0% | 0.0500 / 0.0582 | 0.595 / 0.519 | 0.97 |
| 16 MB | spread evenly | clear | 12 | 10.54 (9.66-10.69) | 10.51 (10.49-10.54) | -0.2% | 0.0607 / 0.0614 | 0.480 / 0.493 | 0.00 |
| 16 MB | spread evenly | shared | 1 | 10.74 (10.74-10.74) | 10.68 (10.68-10.69) | -0.5% | 0.0566 / 0.0572 | 0.474 / 0.504 | 0.00 |
| 64 MB | lowest addresses | clear | 11 | 8.45 (8.14-8.70) | 10.61 (10.60-10.66) | +25.6% | 0.0592 / 0.0625 | 0.671 / 0.552 | 0.94 |
| 64 MB | lowest addresses | shared | 1 | 8.36 (8.35-8.36) | 10.62 (10.61-10.62) | +27.0% | 0.0576 / 0.0625 | 0.670 / 0.561 | 0.98 |
| 64 MB | spread evenly | clear | 11 | 10.13 (9.11-10.80) | 10.65 (10.61-10.82) | +5.1% | 0.0625 / 0.0625 | 0.522 / 0.549 | 0.00 |
| 64 MB | spread evenly | shared | 1 | 9.92 (9.92-9.93) | 10.74 (10.74-10.74) | +8.2% | 0.0625 / 0.0625 | 0.537 / 0.568 | 0.00 |

Same slot, both classes (slot 0x20c0000000 where available):

| size | pages picked | order | clear: ns | shared: ns | shared vs clear |
|---:|---|---|---:|---:|---:|
| 8 MB | lowest addresses | sorted | 8.03 | 8.11 | +0.9% |
| 8 MB | lowest addresses | shuffled | 9.69 | 9.73 | +0.4% |
| 8 MB | spread evenly | sorted | 9.68 | 9.69 | +0.1% |
| 8 MB | spread evenly | shuffled | 9.68 | 9.69 | +0.1% |
| 16 MB | lowest addresses | sorted | 8.16 | 8.19 | +0.4% |
| 16 MB | lowest addresses | shuffled | 10.45 | 10.40 | -0.4% |
| 16 MB | spread evenly | sorted | 10.39 | 10.74 | +3.3% |
| 16 MB | spread evenly | shuffled | 10.53 | 10.68 | +1.4% |
| 64 MB | lowest addresses | sorted | 8.24 | 8.36 | +1.4% |
| 64 MB | lowest addresses | shuffled | 10.60 | 10.62 | +0.1% |
| 64 MB | spread evenly | sorted | 9.14 | 9.92 | +8.6% |
| 64 MB | spread evenly | shuffled | 10.65 | 10.74 | +0.8% |

## Exp X: the form of the timed loop (one load instruction in a loop against lmbench's 100 loads in a row)

X1 = probe3, fresh process per point, chain rewritten before every interval; ns = minimum of 11 intervals, median over the processes.  X3 = lmbench's own lat_mem_rd in the same session (3 sweeps, 4 KiB pages).  adjacency = fraction of virtually adjacent pages that are physically adjacent, in either direction.

### Sequential, stride 256

| size | n | loop: ns (min-max) | unrolled: ns (min-max) | lmbench's own: ns (min-max) | unrolled / loop | unrolled / lmbench | loop / lmbench | cycles: loop / unrolled | median adjacency |
|---:|---:|---|---|---|---:|---:|---:|---|---:|
| 24 KiB | 8 + 8 | 2.107 (2.107-2.108) | 2.107 (2.107-2.107) | 2.107 (2.107-2.107) | 1.000 | 1.000 | 1.000 | 4.00 / 4.00 | 0.00 |
| 0.5 MB | 8 + 8 | 3.772 (3.697-3.816) | 3.848 (3.790-3.878) | 3.805 (3.765-3.835) | 1.020 | 1.011 | 0.991 | 7.18 / 7.34 | 0.00 |
| 1 MB | 8 + 8 | 4.127 (4.122-4.131) | 4.277 (4.261-4.289) | 4.257 (4.252-4.260) | 1.036 | 1.005 | 0.969 | 7.85 / 8.14 | 0.00 |
| 2 MB | 8 + 8 | 4.317 (4.309-4.322) | 4.522 (4.508-4.529) | 4.512 (4.506-4.517) | 1.048 | 1.002 | 0.957 | 8.20 / 8.60 | 0.00 |
| 4 MB | 8 + 8 | 4.506 (4.448-4.639) | 4.939 (4.887-4.990) | 4.857 (4.854-4.904) | 1.096 | 1.017 | 0.928 | 8.59 / 9.42 | 0.00 |
| 6 MB | 8 + 8 | 7.308 (7.130-7.416) | 7.793 (7.632-7.852) | 7.623 (7.546-7.794) | 1.066 | 1.022 | 0.959 | 13.96 / 14.85 | 0.00 |
| 8 MB | 8 + 8 | 9.532 (9.485-9.564) | 10.352 (10.333-10.448) | 10.445 (10.359-10.494) | 1.086 | 0.991 | 0.913 | 18.11 / 19.68 | 0.00 |
| 12 MB | 8 + 8 | 10.408 (10.394-10.442) | 11.414 (11.362-11.461) | 11.451 (11.434-11.516) | 1.097 | 0.997 | 0.909 | 19.77 / 21.66 | 0.00 |
| 16 MB | 8 + 8 | 10.546 (10.516-10.582) | 11.507 (11.485-11.595) | 11.591 (11.489-11.736) | 1.091 | 0.993 | 0.910 | 20.01 / 21.84 | 0.00 |
| 64 MB | 8 + 8 | 10.648 (10.612-10.672) | 11.585 (11.456-11.627) | 11.636 (11.556-11.695) | 1.088 | 0.996 | 0.915 | 20.21 / 21.98 | 0.00 |

### Random (lmbench -t pattern, stride 16)

| size | seeds | loop: ns (min-max) | unrolled: ns (min-max) | unrolled / loop |
|---:|---:|---|---|---:|
| 8 MB | 3 | 101.34 (100.62-102.82) | 99.23 (98.72-100.54) | 0.979 |
| 64 MB | 3 | 158.08 (157.75-158.10) | 158.10 (157.94-158.46) | 1.000 |

### lmbench's own lat_mem_rd, stride 256: Exp H (about 18:00) against Exp X3 (20:00), same platform state

Between the two the free memory of the machine became fragmented (hours of experiments that shuffle and free gigabytes of pages).  The adjacency column is what probe3, which allocates in the same way, recorded at about the same time (Exp R for the earlier, Exp X1 for the later session).

| size | Exp H: ns, median of the sweeps | adjacency then (Exp R) | Exp X3: ns, median of 3 | adjacency now (Exp X1) | change |
|---:|---:|---:|---:|---:|---:|
| 4 MB | 4.83 | 0.50 | 4.86 | 0.00 | +0.6% |
| 6 MB | 7.70 | 0.36 | 7.62 | 0.00 | -1.0% |
| 8 MB | 10.39 | 0.27 | 10.45 | 0.00 | +0.5% |
| 12 MB | 11.24 | 0.34 | 11.45 | 0.00 | +1.9% |
| 16 MB | 11.23 | 0.46 | 11.59 | 0.00 | +3.2% |
| 64 MB | 10.27 | 0.86 | 11.64 | 0.00 | +13.3% |

### X2: the same pages in sorted and in shuffled virtual order (as Exp W), sequential stride 256, by loop form

ns = median of 5 full cycles, median over slots and the two passes.  adjacent pages = lowest addresses of the slot; non-adjacent pages = spread evenly over the slot's pool pages.

| size | loop form | class | slots | adjacent pages, sorted: ns (min-max) | same pages, shuffled: ns (min-max) | shuffled vs sorted | non-adjacent pages, sorted / shuffled: ns | adjacency of the sorted adjacent set |
|---:|---|---|---:|---|---|---:|---|---:|
| 8 MB | loop | clear | 12 | 8.22 (8.00-8.49) | 9.66 (9.58-9.69) | +17.5% | 9.62 / 9.58 | 0.91 |
| 8 MB | loop | shared | 1 | 8.09 (8.08-8.10) | 9.68 (9.68-9.68) | +19.6% | 9.65 / 9.63 | 0.96 |
| 8 MB | unrolled | clear | 12 | 9.03 (8.81-9.32) | 10.56 (10.42-10.72) | +17.0% | 10.45 / 10.48 | 0.91 |
| 8 MB | unrolled | shared | 1 | 8.94 (8.93-8.95) | 10.59 (10.59-10.60) | +18.5% | 10.55 / 10.67 | 0.96 |
| 16 MB | unrolled | clear | 12 | 9.45 (9.09-9.72) | 11.32 (11.29-11.39) | +19.8% | 11.50 / 11.61 | 0.90 |
| 16 MB | unrolled | shared | 1 | 9.45 (9.26-9.64) | 11.31 (11.30-11.31) | +19.6% | 11.72 / 11.61 | 0.97 |
| 64 MB | unrolled | clear | 11 | 9.31 (9.12-9.71) | 11.60 (11.54-11.73) | +24.6% | 11.13 / 11.55 | 0.94 |
| 64 MB | unrolled | shared | 1 | 9.20 (9.20-9.21) | 11.69 (11.64-11.74) | +27.0% | 10.80 / 11.61 | 0.98 |

## Exp Y: the layout effect at 8 MB for every stride (frames2, lmbench's loop form, physically adjacent pages)

sorted = virtual order follows ascending physical address; shuffled = the same pages in a random virtual order.  ns = median of 5 full cycles, median over slots and the two passes.

| stride | accesses per page | slots | sorted: ns (min-max) | shuffled: ns (min-max) | shuffled - sorted (ns) | shuffled vs sorted | per page crossing (ns) | page walks per access: sorted / shuffled | L2 refills: sorted / shuffled | L3 refills: sorted / shuffled |
|---:|---:|---:|---|---|---:|---:|---:|---|---|---|
| 64 | 64 | 12 | 3.61 (3.54-3.74) | 4.33 (4.30-4.35) | +0.72 | +19.9% | +46.1 | 0.0120 / 0.0148 | 0.151 / 0.174 | 0.766 / 0.773 |
| 128 | 32 | 12 | 8.09 (7.98-8.29) | 9.65 (9.56-9.69) | +1.56 | +19.3% | +50.0 | 0.0248 / 0.0301 | 0.267 / 0.241 | 0.773 / 0.778 |
| 256 | 16 | 12 | 9.00 (8.84-9.24) | 10.59 (10.51-10.65) | +1.59 | +17.7% | +25.5 | 0.0489 / 0.0539 | 0.251 / 0.247 | 0.784 / 0.799 |
| 512 | 8 | 12 | 8.50 (8.29-8.70) | 10.04 (10.00-10.08) | +1.54 | +18.1% | +12.3 | 0.0866 / 0.0965 | 0.206 / 0.278 | 0.785 / 0.811 |
| 1024 | 4 | 12 | 9.33 (9.24-9.46) | 10.86 (10.82-11.09) | +1.53 | +16.4% | +6.1 | 0.1338 / 0.1380 | 0.152 / 0.312 | 0.795 / 0.819 |

