## Exp R: sequential stride 256, fresh process per point, 20 laps; interconnect pinned at 1800 MHz

rebuild 0 = chain built once; rebuild 1 = chain rewritten before every timed interval, as lmbench does.  ns = minimum of 11 intervals.  adjacency = fraction of virtually adjacent pages that are also physically adjacent, in either direction.  In every lap the rebuild 1 process ran right after the rebuild 0 process and received its frames in reverse order, so at 64 MB (and 16 MB) rebuild 1 always has a descending and rebuild 0 an ascending layout: the rebuild setting is aliased with the direction of the layout and with run order.

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

Rank correlation of the latency with the physical layout (both rebuild settings pooled).  lap = position of the process in the run (1 to 20); the partial correlation removes the lap trend from both variables:

| size | n | rho(ns, adjacency) | rho(ns, distinct 2 MiB regions) | rho(adjacency, lap) | rho(ns, lap) | partial rho(ns, adjacency) given lap | adjacency range | ns range |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 4 MB | 40 | -0.22 | +0.24 | -0.15 | +0.50 | -0.17 | 0.14-0.57 | 4.43-4.65 |
| 6 MB | 40 | -0.49 | +0.27 | +0.31 | -0.27 | -0.45 | 0.28-0.41 | 6.83-7.15 |
| 8 MB | 40 | -0.61 | +0.36 | -0.05 | +0.07 | -0.61 | 0.24-0.36 | 9.22-9.43 |
| 12 MB | 40 | -0.94 | +0.94 | -0.99 | +0.94 | -0.24 | 0.16-0.52 | 9.41-10.21 |
| 16 MB | 40 | -0.92 | +0.90 | -0.98 | +0.90 | -0.47 | 0.28-0.62 | 9.32-10.09 |
| 64 MB | 40 | -0.37 | +0.42 | -0.98 | +0.40 | +0.08 | 0.79-0.90 | 8.53-9.29 |

Frame reuse: in 118 of 120 pairs of consecutive processes at the same size, the ascending adjacency of the first equals the descending adjacency of the second within 0.02 (in 114 of them the reverse relation holds as well), which indicates that the second process received the frames the first one had just freed, in reverse order.  Frame numbers were not logged by probe3.

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

Each slot is measured twice per run: pass 2 uses the same data pages after moving them to a new virtual range (new page-table pages).  ns = median of 5 full cycles.  'RAM in slot' and 'kernel or reserved inside' come from /proc/iomem; a slot that is not entirely ordinary RAM cannot be one 1 GiB stage-2 block.  This table is NOT a comparison of 1 GiB with 2 MiB blocks: a protected VM was running and had pages in eight further slots (vm-frames-n80.txt), and one donated page turns a slot's 1 GiB block into 2 MiB blocks.  Only the slots at 0x22c0000000 and 0x2300000000 can still have been 1 GiB blocks; see the slot table further down.

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

From 6 MB upward one page set of class shared per run (two passes), all from slot 0x20c0000000 and all drawn from the same population of about 50 thousand pool pages; below 6 MB several slots have a shared set.  Class clear from every slot of the same run.  extra = median of the shared sets minus the median of class clear in the same run; 'same slot' compares each shared set with the clear set of its own slot (median over the slots).  Runs: V2 and V3; the seed changes the order of the chase, not which pages are selected.

### Pages picked: spread evenly over the pool pages of the slot

| size | runs | slots with a shared set | extra ns per run | median (min-max) | relative | same slot: extra ns per run | extra cycles per run | page walks per access: clear / shared | extra L2 refills per run | distinct 2 MiB regions of the shared set |
|---:|---:|---|---|---|---:|---|---|---|---|---|
| 2 MB | 1 | 3 | -0.1 | -0.1 (-0.1 to -0.1) | -0.3% | +0.3 | -0.1 | 0.000 / 0.000 | +0.00 | 4 |
| 3 MB | 1 | 3 | -0.0 | -0.0 (-0.0 to -0.0) | -0.1% | +0.1 | -0.0 | 0.000 / 0.000 | +0.00 | 4 |
| 4 MB | 1 | 3 | +0.3 | +0.3 (+0.3 to +0.3) | +0.9% | -0.7 | +0.5 | 0.000 / 0.000 | +0.00 | 4 |
| 6 MB | 4 | 1, 1, 1, 1 | +5.8, +5.2, +10.7, +7.2 | +6.5 (+5.2 to +10.7) | +9.9% | +6.6, +8.3, +5.7, +10.5 | +9.9, +10.7, +21.4, +11.9 | 0.939 / 0.881 | +0.08, +0.07, +0.07, +0.08 | 131, 133, 133, 133 |
| 8 MB | 4 | 1, 1, 1, 1 | +8.2, +8.2, +8.5, +12.8 | +8.4 (+8.2 to +12.8) | +8.5% | +8.0, +8.0, +6.2, +12.6 | +15.2, +18.2, +16.0, +25.0 | 0.994 / 0.991 | +0.17, +0.18, +0.18, +0.17 | 132, 134, 133, 132 |
| 12 MB | 4 | 1, 1, 1, 1 | +9.4, +11.1, +17.6, +10.7 | +10.9 (+9.4 to +17.6) | +8.3% | +6.5, +9.5, +15.3, +9.7 | +18.2, +19.8, +30.4, +20.5 | 1.000 / 1.000 | +0.37, +0.37, +0.35, +0.37 | 133, 134, 132, 134 |
| 16 MB | 4 | 1, 1, 1, 1 | +18.4, +10.9, +18.7, +19.5 | +18.6 (+10.9 to +19.5) | +13.0% | +18.3, +12.4, +16.6, +20.2 | +34.5, +20.8, +33.9, +35.7 | 1.000 / 1.000 | +0.56, +0.56, +0.55, +0.55 | 134, 135, 134, 134 |
| 24 MB | 4 | 1, 1, 1, 1 | +19.6, +17.9, +19.4, +19.5 | +19.5 (+17.9 to +19.6) | +13.1% | +20.0, +17.1, +19.2, +19.6 | +35.8, +34.1, +35.6, +37.0 | 1.000 / 1.000 | +0.92, +0.89, +0.87, +0.88 | 135, 135, 134, 134 |
| 32 MB | 4 | 1, 1, 1, 1 | +14.2, +14.7, +14.1, +16.7 | +14.4 (+14.1 to +16.7) | +9.5% | +15.8, +14.9, +14.6, +16.6 | +28.1, +27.4, +27.6, +32.1 | 1.000 / 1.000 | +0.83, +0.84, +0.84, +0.83 | 135, 135, 136, 136 |
| 48 MB | 4 | 1, 1, 1, 1 | +13.4, +14.7, +14.1, +13.8 | +14.0 (+13.4 to +14.7) | +9.0% | +13.6, +14.9, +14.5, +14.2 | +25.6, +27.5, +26.7, +26.2 | 1.000 / 1.000 | +0.82, +0.81, +0.78, +0.81 | 135, 136, 136, 136 |
| 64 MB | 4 | 1, 1, 1, 1 | +13.4, +17.1, +13.4, +13.1 | +13.4 (+13.1 to +17.1) | +8.6% | +13.6, +17.4, +13.9, +13.3 | +25.5, +33.0, +25.2, +24.9 | 1.000 / 1.000 | +0.81, +0.82, +0.81, +0.79 | 135, 135, 137, 137 |

### Pages picked: lowest addresses (physically contiguous)

| size | runs | slots with a shared set | extra ns per run | median (min-max) | relative | same slot: extra ns per run | extra cycles per run | page walks per access: clear / shared | extra L2 refills per run | distinct 2 MiB regions of the shared set |
|---:|---:|---|---|---|---:|---|---|---|---|---|
| 16 MB | 1 | 1 | +2.3 | +2.3 (+2.3 to +2.3) | +1.6% | +1.3 | +3.2 | 0.992 / 0.809 | +0.03 | 10 |
| 32 MB | 1 | 1 | +6.5 | +6.5 (+6.5 to +6.5) | +4.3% | +7.0 | +12.7 | 0.996 / 0.982 | +0.11 | 18 |
| 64 MB | 1 | 1 | +7.7 | +7.7 (+7.7 to +7.7) | +4.9% | +7.9 | +14.6 | 0.998 / 0.993 | +0.28 | 34 |

## Slot effect in the random chase: the two GiB slots that can still be 1 GiB stage-2 blocks against the others

Slots 0x22c0000000 and 0x2300000000 hold no VM page, no memory-region boundary and no hypervisor pool; every other slot is mapped by 2 MiB blocks at most (kernel source plus vm-frames-n80.txt; the stage-2 table itself was not read).  Per run: median over these two slots minus median over the other slots, class clear (or all).  Logs: expS, expV, expV2, expV3.

| size | pages picked | runs | difference per run (ns) | median ns | median cycles | median L2 refills | page walks per access |
|---:|---|---:|---|---:|---:|---:|---:|
| 2 MB | spread evenly | 1 | +1.1 | +1.06 | +2.11 | -0.000 | 0.000 |
| 3 MB | spread evenly | 1 | -0.1 | -0.11 | -0.43 | +0.000 | 0.000 |
| 4 MB | spread evenly | 1 | -0.2 | -0.22 | -0.55 | -0.000 | 0.000 |
| 6 MB | spread evenly | 4 | +2.7 +1.2 -0.3 -1.3 | +0.45 | +2.40 | +0.000 | 0.943 |
| 8 MB | spread evenly | 4 | +0.7 +1.0 -1.9 +0.7 | +0.70 | +0.62 | -0.000 | 0.995 |
| 12 MB | spread evenly | 4 | +2.7 +1.9 +2.4 +2.3 | +2.35 | +4.80 | -0.001 | 1.000 |
| 16 MB | spread evenly | 5 | +1.4 +1.9 +2.8 +1.7 +2.9 | +1.95 | +3.91 | -0.001 | 1.000 |
| 24 MB | spread evenly | 4 | +1.7 +3.3 +2.5 +0.7 | +2.11 | +3.98 | -0.004 | 1.000 |
| 32 MB | spread evenly | 8 | +1.9 +1.7 +2.0 +2.3 +0.1 +2.7 +1.8 +1.6 | +1.82 | +3.47 | -0.002 | 1.000 |
| 48 MB | spread evenly | 4 | +2.2 +1.7 +1.3 +2.1 | +1.89 | +3.21 | +0.006 | 1.000 |
| 64 MB | spread evenly | 4 | +2.0 +1.4 +2.0 +2.2 | +2.03 | +3.85 | +0.007 | 1.000 |
| 16 MB | lowest addresses | 1 | +1.4 | +1.37 | +1.39 | +0.005 | 0.992 |
| 32 MB | lowest addresses | 5 | +9.0 +1.5 +2.2 +1.9 +1.7 | +1.94 | +3.66 | -0.004 | 0.996 |
| 64 MB | lowest addresses | 2 | +1.8 +2.0 | +1.90 | +3.76 | +0.007 | 0.998 |

## Exp W: sequential chase (stride 256) over the same kind of page set in sorted and in shuffled virtual order, by page class

sorted = virtual order follows ascending physical address; shuffled = the same selection rule, pages mapped in a random virtual order.  clear = stage-2 block mappings; shared = 4 KiB stage-2 leaves (2 MiB regions shared with the VM).  ns = median over sets (slots) and the two passes.

selection step = pool pages of the class in the slot per selected page (1 for the lowest-address sets): with evenly spread pages every step-th pool page in ascending frame order is taken.  It is not a physical distance; frame numbers per page were not logged.

| size | pages picked | class | slots | sorted: ns (min-max) | shuffled: ns (min-max) | shuffled vs sorted | page walks per access: sorted / shuffled | L2 refills: sorted / shuffled | adjacency when sorted | selection step (min-max) |
|---:|---|---|---:|---|---|---:|---|---|---:|---|
| 8 MB | lowest addresses | clear | 12 | 8.18 (7.96-8.42) | 9.69 (9.59-9.81) | +18.5% | 0.0509 / 0.0545 | 0.279 / 0.265 | 0.91 | 1 |
| 8 MB | lowest addresses | shared | 1 | 8.11 (8.11-8.11) | 9.73 (9.72-9.74) | +20.0% | 0.0374 / 0.0484 | 0.285 / 0.265 | 0.95 | 1 |
| 8 MB | spread evenly | clear | 12 | 9.64 (9.38-9.87) | 9.65 (9.59-9.68) | +0.1% | 0.0539 / 0.0551 | 0.260 / 0.261 | 0.00 | 5.5-64.6 |
| 8 MB | spread evenly | shared | 1 | 9.69 (9.66-9.71) | 9.69 (9.69-9.69) | +0.0% | 0.0420 / 0.0426 | 0.264 / 0.267 | 0.00 | 24.3-24.3 |
| 16 MB | lowest addresses | clear | 12 | 8.38 (8.05-8.69) | 10.49 (10.36-10.59) | +25.2% | 0.0571 / 0.0606 | 0.580 / 0.498 | 0.92 | 1 |
| 16 MB | lowest addresses | shared | 1 | 8.19 (8.19-8.19) | 10.40 (10.40-10.41) | +27.0% | 0.0500 / 0.0582 | 0.595 / 0.519 | 0.97 | 1 |
| 16 MB | spread evenly | clear | 12 | 10.54 (9.66-10.69) | 10.51 (10.49-10.54) | -0.2% | 0.0607 / 0.0614 | 0.480 / 0.493 | 0.00 | 2.8-32.1 |
| 16 MB | spread evenly | shared | 1 | 10.74 (10.74-10.74) | 10.68 (10.68-10.69) | -0.5% | 0.0566 / 0.0572 | 0.474 / 0.504 | 0.00 | 12.1-12.1 |
| 64 MB | lowest addresses | clear | 11 | 8.45 (8.14-8.70) | 10.61 (10.60-10.66) | +25.6% | 0.0592 / 0.0625 | 0.671 / 0.552 | 0.94 | 1 |
| 64 MB | lowest addresses | shared | 1 | 8.36 (8.35-8.36) | 10.62 (10.61-10.62) | +27.0% | 0.0576 / 0.0625 | 0.670 / 0.561 | 0.98 | 1 |
| 64 MB | spread evenly | clear | 11 | 10.13 (9.11-10.80) | 10.65 (10.61-10.82) | +5.1% | 0.0625 / 0.0625 | 0.522 / 0.549 | 0.00 | 1.4-8.0 |
| 64 MB | spread evenly | shared | 1 | 9.92 (9.92-9.93) | 10.74 (10.74-10.74) | +8.2% | 0.0625 / 0.0625 | 0.537 / 0.568 | 0.00 | 3.0-3.0 |

Same slot, both classes (slot 0x20c0000000 where available).  With evenly spread pages the two classes of one slot have different selection steps, so this comparison is not at equal spacing:

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

### lmbench's own lat_mem_rd, stride 256: Exp H (18:45 to 19:13) against Exp X3 (19:56 to 20:07), same platform state

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

## Exp Z: a chase dominated by address translation (frames2 tlb<L>: another page on every hop, L cache lines per page)

cycles = user-mode CPU cycles per hop (median of the per-set medians, two passes per set).  '2 MiB slots' are all slots except 0x22c0000000 and 0x2300000000, the two that can still be 1 GiB stage-2 blocks.  shared = pages in 2 MiB regions that also hold pages of the running VM (4 KiB stage-2 leaves).

| pages x lines per page | lines | class clear, 2 MiB slots: cycles (ns) | page walks | L2 refills | 1 GiB-candidate slots minus 2 MiB slots, per run: cycles | median | class shared minus clear, per run: cycles | median | extra L2 refills of class shared |
|---|---:|---|---:|---:|---|---:|---|---:|---:|
| 2048 x 1 | 2048 | 37.01 (19.48) | 0.960 | 0.001 | +3.59 +3.50 +3.61 | +3.59 | +9.9 +9.3 +9.5 | +9.5 | +0.052 |
| 1024 x 4 | 4096 | 14.48 (7.63) | 0.000 | 0.019 | -0.10 -0.03 +0.01 | -0.03 | +0.0 -0.1 -0.1 | -0.1 | -0.004 |
| 2048 x 2 | 4096 | 37.75 (19.87) | 0.940 | 0.051 | +3.42 +3.46 +3.56 | +3.46 | +12.7 +13.0 +13.3 | +13.0 | +0.217 |
| 4096 x 1 | 4096 | 39.08 (20.58) | 0.998 | 0.061 | +3.92 +3.95 +3.88 | +3.92 | +24.4 +24.3 +24.8 | +24.4 | +0.743 |
| 8192 x 1 | 8192 | 49.18 (25.88) | 1.013 | 0.525 | +3.98 +4.04 +3.92 | +3.98 | +37.2 +36.5 +36.8 | +36.8 | +1.295 |
| 16384 x 1 | 16384 | 61.68 (32.49) | 1.015 | 1.110 | +3.98 +3.93 +3.94 | +3.94 | +28.4 +28.0 +28.0 | +28.0 | +0.871 |

Cost of one page walk with a block-mapped stage-2 (class clear, 2 MiB slots): cycles per hop minus the no-walk reference (1024 pages x 4 lines, 14.48 cycles), for configurations with the same 4096 lines of data:

- 2048 pages x 2 lines: +23.3 cycles per hop
- 4096 pages x 1 lines: +24.6 cycles per hop

## Exp N: the translation-only chase as an unprivileged program, with and without a host stage-2

Same source (probe3 tlb) on the N80 (kvm-arm.mode=protected, kernel 6.6.0-79) and on a D80F3 workstation with the same cores (KVM in VHE mode, no host stage-2, kernel 7.0.0-34).  cycles = 4 x ns / (ns per hop of a chase inside the L1 cache, taken in the same process); the PMU columns exist for the N80 only.  Median over the processes (min-max).  Pages are first touched in chain order here; see Exp N4 for what that does to the 4096 x 1 row.

| pages x lines per page | data lines | N80: cycles | N80 PMU: cycles | page walks per hop | L2 refills per hop (min-max) | D80F3: cycles | per CPU | N80 - D80F3 |
|---|---:|---|---:|---:|---|---|---|---:|
| 2048 x 1 | 2048 | 39.39 (38.98-39.87), 5 | 39.68 | 0.959 | 0.003 (0.002-0.004) | 24.96 (24.49-25.15), 20 | 24.90 24.95 24.98 25.00 | +14.43 |
| 256 x 16 | 4096 | 14.37 (14.29-14.40), 5 | 14.38 | 0.000 | 0.014 (0.010-0.016) | 14.53 (14.25-14.90), 20 | 14.52 14.38 14.71 14.70 | -0.16 |
| 512 x 8 | 4096 | 14.47 (14.19-14.68), 5 | 14.58 | 0.000 | 0.022 (0.006-0.030) | 14.49 (14.24-15.13), 20 | 14.49 14.45 14.49 14.60 | -0.02 |
| 1024 x 4 | 4096 | 14.54 (14.33-14.70), 5 | 14.57 | 0.000 | 0.023 (0.011-0.029) | 14.58 (14.35-14.77), 20 | 14.57 14.54 14.63 14.46 | -0.03 |
| 2048 x 2 | 4096 | 40.52 (39.40-40.93), 5 | 40.75 | 0.944 | 0.065 (0.056-0.073) | 25.86 (25.43-26.26), 20 | 25.91 25.84 25.99 25.70 | +14.67 |
| 4096 x 1 | 4096 | 42.55 (42.31-43.94), 5 | 42.61 | 1.001 | 0.091 (0.075-0.153) | 27.99 (27.82-28.33), 20 | 28.20 27.92 28.00 28.02 | +14.55 |
| 8192 x 1 | 8192 | 54.27 (53.87-56.84), 5 | 54.30 | 1.010 | 0.621 (0.604-0.741) | 38.18 (37.93-39.62), 20 | 38.14 38.29 38.15 38.16 | +16.10 |
| 16384 x 1 | 16384 | 66.56 (66.27-68.36), 5 | 66.92 | 1.018 | 1.123 (1.100-1.153) | 50.31 (49.41-51.02), 20 | 49.97 50.53 50.23 50.32 | +16.25 |

## Exp N2: the same chase as root, with other frames in every repetition

Before each repetition a stopped process holds back (repetition - 1) x 192 MB, so the probe gets other frames.  share = share of the pages of the working set in the two 1 GiB-candidate slots (0x22c0000000, 0x2300000000); regions = distinct 2 MiB regions of the working set.  One process per cell.

| rep | held back | 4096 x 1: share | regions | cycles | walks | L2 refills | 1024 x 4: share | regions | cycles | walks | L2 refills | 2048 x 1: share | regions | cycles | walks | L2 refills |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 MB | 0.350 | 484 | 48.60 | 0.999 | 0.402 | 0.329 | 346 | 14.60 | 0.000 | 0.024 | 0.335 | 423 | 38.66 | 0.944 | 0.002 |
| 2 | 192 MB | 0.382 | 476 | 69.12 | 0.996 | 0.616 | 0.377 | 251 | 14.28 | 0.000 | 0.009 | 0.385 | 369 | 39.03 | 0.924 | 0.002 |
| 3 | 384 MB | 0.412 | 296 | 80.27 | 0.989 | 0.769 | 0.429 | 148 | 14.68 | 0.000 | 0.027 | 0.425 | 201 | 39.40 | 0.943 | 0.002 |
| 4 | 576 MB | 0.143 | 184 | 76.24 | 0.991 | 0.728 | 0.140 | 109 | 14.62 | 0.000 | 0.025 | 0.140 | 142 | 37.52 | 0.942 | 0.003 |
| 5 | 768 MB | 0.051 | 140 | 72.07 | 0.988 | 0.682 | 0.043 | 80 | 14.66 | 0.000 | 0.026 | 0.047 | 116 | 36.41 | 0.914 | 0.001 |
| 6 | 960 MB | 0.021 | 117 | 66.99 | 0.992 | 0.630 | 0.021 | 72 | 14.70 | 0.000 | 0.029 | 0.025 | 114 | 36.74 | 0.937 | 0.001 |
| 7 | 1152 MB | 0.005 | 79 | 75.09 | 0.983 | 0.821 | 0.012 | 59 | 14.76 | 0.000 | 0.031 | 0.007 | 71 | 36.39 | 0.928 | 0.002 |
| 8 | 1344 MB | 0.005 | 86 | 61.78 | 0.992 | 0.603 | 0.010 | 63 | 14.36 | 0.000 | 0.013 | 0.004 | 71 | 36.54 | 0.937 | 0.003 |
| 9 | 1536 MB | 0.003 | 81 | 72.87 | 0.986 | 0.715 | 0.004 | 47 | 14.42 | 0.000 | 0.017 | 0.004 | 64 | 36.14 | 0.923 | 0.002 |
| 10 | 1728 MB | 0.002 | 67 | 68.17 | 0.984 | 0.647 | 0.003 | 48 | 14.43 | 0.000 | 0.016 | 0.003 | 59 | 36.10 | 0.920 | 0.000 |
| 11 | 1920 MB | 0.003 | 79 | 61.75 | 0.988 | 0.567 | 0.005 | 51 | 14.51 | 0.000 | 0.020 | 0.004 | 65 | 36.10 | 0.922 | 0.001 |
| 12 | 2112 MB | 0.018 | 239 | 73.85 | 0.987 | 0.708 | 0.020 | 109 | 14.66 | 0.000 | 0.027 | 0.015 | 150 | 36.88 | 0.944 | 0.000 |

Per configuration, over the 12 repetitions:

| pages x lines | cycles (min-max) | r(cycles, share) | r(cycles, regions) | r(share, regions) | r(cycles, L2 refills) | cycles = a + b x share + c x regions/100: a | b (s.e.) | c (s.e.) | R^2 |
|---|---|---:|---:|---:|---:|---:|---|---|---:|
| 4096 x 1 | 48.60-80.27 | -0.07 | -0.28 | +0.89 | +0.95 | 75.17 | +44.21 (32.46) | -5.88 (3.54) | 0.24 |
| 1024 x 4 | 14.28-14.76 | -0.06 | -0.08 | +0.81 | +1.00 | 14.57 | +0.01 (0.53) | -0.02 (0.09) | 0.01 |
| 2048 x 1 | 36.10-39.40 | +0.98 | +0.84 | +0.84 | +0.43 | 36.29 | +6.89 (0.85) | +0.04 (0.12) | 0.96 |

## Exp N3: page sets that mix two GiB slots in a fixed proportion (frames2, 2048 pages x 1 line, class clear)

A = a slot that can still be a 1 GiB stage-2 block, B = a slot mapped with 2 MiB blocks.  cycles = median over the three repetitions of the mean of the two passes (min-max of the repetitions).  'minus 0%' is taken within each repetition.

| A : B | share of A | cycles (min-max) | minus 0%, per repetition | median | linear between the 0% and 100% medians | page walks per hop | L2 refills per hop | 2 MiB regions |
|---|---:|---|---|---:|---:|---:|---:|---:|
| 0x8b:0x88 | 0% | 36.88 (36.60-37.26) | +0.00 +0.00 +0.00 | +0.00 | +0.00 | 0.952 | 0.0012 | 92 |
| 0x8b:0x88 | 12% | 37.29 (37.01-37.67) | +0.41 +0.41 +0.41 | +0.41 | +0.42 | 0.950 | 0.0003 | 159 |
| 0x8b:0x88 | 25% | 37.95 (37.45-38.21) | +0.95 +1.07 +0.85 | +0.95 | +0.88 | 0.956 | 0.0004 | 172 |
| 0x8b:0x88 | 50% | 38.70 (38.50-39.26) | +2.00 +1.82 +1.90 | +1.90 | +1.75 | 0.949 | 0.0015 | 176 |
| 0x8b:0x88 | 75% | 39.78 (39.31-40.10) | +2.84 +2.89 +2.71 | +2.84 | +2.63 | 0.953 | 0.0002 | 175 |
| 0x8b:0x88 | 100% | 40.39 (40.08-40.90) | +3.64 +3.51 +3.48 | +3.51 | +3.51 | 0.942 | 0.0007 | 109 |
| 0x8c:0x89 | 0% | 36.99 (36.48-37.38) | +0.00 +0.00 +0.00 | +0.00 | +0.00 | 0.955 | 0.0004 | 90 |
| 0x8c:0x89 | 12% | 37.47 (37.09-37.85) | +0.47 +0.48 +0.61 | +0.48 | +0.40 | 0.956 | 0.0010 | 154 |
| 0x8c:0x89 | 25% | 37.88 (37.60-38.22) | +0.84 +0.89 +1.12 | +0.89 | +0.83 | 0.954 | 0.0009 | 166 |
| 0x8c:0x89 | 50% | 38.94 (38.45-39.27) | +1.89 +1.95 +1.97 | +1.95 | +1.67 | 0.957 | 0.0007 | 172 |
| 0x8c:0x89 | 75% | 39.77 (39.37-40.29) | +2.91 +2.79 +2.89 | +2.89 | +2.50 | 0.953 | 0.0004 | 177 |
| 0x8c:0x89 | 100% | 40.32 (40.14-40.97) | +3.59 +3.33 +3.66 | +3.59 | +3.33 | 0.939 | 0.0007 | 104 |

Straight line through the 36 points of the two pairs: cycles = 36.98 + 3.59 (s.e. 0.16) x share.  With a quadratic term added: +4.24 (s.e. 0.61) x share -0.65 (s.e. 0.59) x share^2.

Controls and the no-walk configuration:

| set | configuration | cycles per repetition | median | page walks per hop |
|---|---|---|---:|---:|
| two 1 GiB-candidate slots, half each | 2048 x 1 | 40.83 40.40 40.16 | 40.40 | 0.945 |
| two 2 MiB slots, half each | 2048 x 1 | 37.49 37.09 36.70 | 37.09 | 0.960 |
| 0x8b:0x88, 0% of A | 1024 x 4 (no walks) | 14.45 14.36 14.61 | 14.45 | 0.000 |
| 0x8b:0x88, 50% of A | 1024 x 4 (no walks) | 14.40 14.28 14.27 | 14.28 | 0.000 |
| 0x8b:0x88, 100% of A | 1024 x 4 (no walks) | 14.39 14.33 14.51 | 14.39 | 0.000 |

## Exp N4: pages first touched in chain order (as in Exp N and N2) or in ascending virtual order (TLB_PREFAULT=1)

N80 as root with memory held back as in N2, 8 repetitions, one process per cell.  l2over = share of the data lines that lie in an L2 set holding more than 8 of them, computed from the frame numbers before the timed part.

### N80: 4096 x 1, per repetition

| rep | held back | chain order: l2over | L2 refills per hop | cycles | ascending order: l2over | L2 refills per hop | cycles |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 MB | 0.072 | 0.117 | 43.86 | 0.056 | 0.100 | 43.52 |
| 2 | 256 MB | 0.460 | 0.502 | 57.89 | 0.043 | 0.092 | 42.11 |
| 3 | 512 MB | 0.298 | 0.347 | 48.77 | 0.040 | 0.095 | 43.33 |
| 4 | 768 MB | 0.120 | 0.152 | 44.66 | 0.043 | 0.097 | 43.38 |
| 5 | 1024 MB | 0.362 | 0.403 | 50.03 | 0.032 | 0.088 | 42.71 |
| 6 | 1280 MB | 0.424 | 0.462 | 51.05 | 0.022 | 0.069 | 41.77 |
| 7 | 1536 MB | 0.395 | 0.431 | 50.42 | 0.038 | 0.085 | 41.34 |
| 8 | 1792 MB | 0.414 | 0.448 | 50.75 | 0.043 | 0.066 | 40.11 |

Chain order, 4096 x 1: r(L2 refills, l2over) = +0.999, r(cycles, L2 refills) = +0.895 over 8 repetitions.

### N80: all configurations

| pages x lines | data lines | chain order: cycles (min-max) | page walks per hop | L2 refills per hop | ascending order: cycles (min-max) | page walks per hop | L2 refills per hop | difference of the medians: cycles | walks |
|---|---:|---|---:|---:|---|---:|---:|---:|---:|
| 1024 x 2 | 2048 | 13.99 (13.88-14.99) | 0.000 | 0.000 | 13.96 (13.94-14.00) | 0.000 | 0.000 | -0.03 | +0.000 |
| 1024 x 4 | 4096 | 14.60 (14.52-14.89) | 0.000 | 0.023 | 14.54 (14.27-14.91) | 0.000 | 0.021 | -0.06 | +0.000 |
| 2048 x 1 | 2048 | 39.85 (37.63-40.65) | 0.956 | 0.004 | 38.25 (36.36-39.86) | 0.916 | 0.004 | -1.60 | -0.040 |
| 2048 x 2 | 4096 | 40.63 (39.12-42.19) | 0.934 | 0.072 | 39.65 (38.08-41.67) | 0.906 | 0.069 | -0.97 | -0.029 |
| 4096 x 1 | 4096 | 50.23 (43.86-57.89) | 0.998 | 0.417 | 42.41 (40.11-43.52) | 0.993 | 0.090 | -7.82 | -0.005 |

### N80: 2048 x 1, cycles per page walk = (cycles - cycles of 1024 x 2) / page walks per hop

| rep | chain order: share in the two candidate slots | regions | cycles | walks | cycles per walk | ascending order: share | regions | cycles | walks | cycles per walk |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.296 | 649 | 40.65 | 0.964 | 27.64 | 0.289 | 608 | 39.86 | 0.938 | 27.63 |
| 2 | 0.303 | 480 | 40.24 | 0.968 | 27.12 | 0.171 | 434 | 38.04 | 0.921 | 26.16 |
| 3 | 0.138 | 391 | 38.82 | 0.963 | 25.77 | 0.127 | 405 | 39.70 | 0.930 | 27.69 |
| 4 | 0.054 | 200 | 40.02 | 0.953 | 27.31 | 0.147 | 431 | 39.83 | 0.937 | 27.63 |
| 5 | 0.108 | 364 | 40.20 | 0.942 | 27.84 | 0.214 | 344 | 38.46 | 0.905 | 27.08 |
| 6 | 0.217 | 322 | 39.69 | 0.960 | 26.77 | 0.160 | 259 | 37.68 | 0.912 | 26.01 |
| 7 | 0.132 | 146 | 37.96 | 0.925 | 25.91 | 0.098 | 245 | 37.12 | 0.899 | 25.77 |
| 8 | 0.084 | 146 | 37.63 | 0.946 | 25.00 | 0.065 | 178 | 36.36 | 0.902 | 24.85 |

Cycles per walk against the share of pages in the two candidate slots, both orders (16 processes): 25.68 + 5.85 (s.e. 2.93) x share; r = +0.47.

### D80F3 (no host stage-2, unprivileged, no PMU): cycles from the L1 reference

| pages x lines | chain order: cycles (min-max), n | ascending order: cycles (min-max), n | difference of the medians | N80 ascending order - D80F3 ascending order |
|---|---|---|---:|---:|
| 1024 x 2 | 13.97 (13.89-14.04), 16 | 13.96 (13.89-14.01), 16 | -0.01 | -0.00 |
| 1024 x 4 | 14.54 (14.42-14.87), 16 | 14.54 (14.42-14.85), 16 | +0.00 | -0.01 |
| 2048 x 1 | 25.22 (24.88-25.39), 16 | 25.15 (24.66-25.50), 16 | -0.07 | +12.95 |
| 2048 x 2 | 26.20 (25.73-26.85), 16 | 26.06 (25.70-26.29), 16 | -0.15 | +13.41 |
| 4096 x 1 | 28.12 (27.90-28.85), 16 | 28.16 (27.87-28.55), 16 | +0.04 | +14.18 |

## Exp N5: which stage-2 class the pages of probe3's own buffer are in, and what a page walk costs it

N80 as root, memory held back as in N2, one process per cell.  candidate share = pages in the two 1 GiB-candidate slots; shared share = pages in 2 MiB regions that hold pages of the running VM (region list taken at the start; the list taken at the end is identical).  cycles per walk = (cycles - median cycles of 1024 x 2 at the same touch order) / page walks per hop.  model = 24.1 + 4.0 x candidate share + 9.5 x shared share, the three class values measured with frames2 (written down before the run).

| rep | held back | touch order | candidate share | shared share | 2 MiB regions | cycles | page walks per hop | L2 refills per hop | cycles per walk | model | measured - model |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 MB | chain | 0.288 | 0.053 | 530 | 39.59 | 0.965 | 0.003 | 26.54 | 25.75 | +0.78 |
| 1 | 0 MB | ascending | 0.304 | 0.050 | 606 | 39.19 | 0.935 | 0.001 | 26.99 | 25.79 | +1.19 |
| 2 | 192 MB | chain | 0.298 | 0.058 | 603 | 40.01 | 0.966 | 0.000 | 26.93 | 25.84 | +1.09 |
| 2 | 192 MB | ascending | 0.304 | 0.058 | 611 | 39.51 | 0.942 | 0.003 | 27.12 | 25.87 | +1.25 |
| 3 | 384 MB | chain | 0.311 | 0.061 | 624 | 40.80 | 0.979 | 0.007 | 27.38 | 25.92 | +1.46 |
| 3 | 384 MB | ascending | 0.313 | 0.061 | 626 | 39.91 | 0.949 | 0.001 | 27.33 | 25.94 | +1.39 |
| 4 | 576 MB | chain | 0.042 | 0.007 | 215 | 48.04 | 0.947 | 0.517 | (L2 refills: not a translation measurement) | | |
| 4 | 576 MB | ascending | 0.084 | 0.022 | 327 | 36.95 | 0.918 | 0.001 | 25.04 | 24.65 | +0.39 |
| 5 | 768 MB | chain | 0.100 | 0.024 | 347 | 37.40 | 0.926 | 0.004 | 25.29 | 24.73 | +0.56 |
| 5 | 768 MB | ascending | 0.107 | 0.025 | 352 | 36.55 | 0.887 | 0.003 | 25.47 | 24.77 | +0.70 |
| 6 | 960 MB | chain | 0.102 | 0.026 | 349 | 38.25 | 0.962 | 0.001 | 25.21 | 24.75 | +0.45 |
| 6 | 960 MB | ascending | 0.113 | 0.027 | 367 | 37.52 | 0.925 | 0.001 | 25.46 | 24.81 | +0.65 |
| 7 | 1152 MB | chain | 0.111 | 0.027 | 364 | 38.14 | 0.953 | 0.001 | 25.34 | 24.80 | +0.54 |
| 7 | 1152 MB | ascending | 0.120 | 0.027 | 383 | 36.18 | 0.860 | 0.000 | 25.85 | 24.84 | +1.01 |
| 8 | 1344 MB | chain | 0.120 | 0.028 | 383 | 38.31 | 0.958 | 0.002 | 25.39 | 24.84 | +0.55 |
| 8 | 1344 MB | ascending | 0.129 | 0.029 | 402 | 37.69 | 0.923 | 0.002 | 25.69 | 24.89 | +0.80 |
| 9 | 1536 MB | chain | 0.129 | 0.029 | 405 | 38.20 | 0.949 | 0.002 | 25.50 | 24.90 | +0.61 |
| 9 | 1536 MB | ascending | 0.120 | 0.027 | 390 | 37.29 | 0.913 | 0.006 | 25.56 | 24.84 | +0.72 |
| 10 | 1728 MB | chain | 0.119 | 0.026 | 391 | 38.35 | 0.953 | 0.002 | 25.57 | 24.83 | +0.74 |
| 10 | 1728 MB | ascending | 0.148 | 0.039 | 434 | 38.02 | 0.928 | 0.002 | 25.92 | 25.07 | +0.86 |
| 11 | 1920 MB | chain | 0.150 | 0.042 | 438 | 38.86 | 0.965 | 0.001 | 25.78 | 25.09 | +0.68 |
| 11 | 1920 MB | ascending | 0.149 | 0.042 | 437 | 37.90 | 0.921 | 0.005 | 26.00 | 25.09 | +0.91 |
| 12 | 2112 MB | chain | 0.015 | 0.004 | 108 | 47.16 | 0.926 | 0.512 | (L2 refills: not a translation measurement) | | |
| 12 | 2112 MB | ascending | 0.022 | 0.005 | 134 | 35.65 | 0.892 | 0.001 | 24.32 | 24.24 | +0.08 |

Within 1.0 cycle of the model: 16 of 22 processes (2 further processes had 0.5 L2 refills per hop and are left out).  Shared share: 0.004 to 0.062.

### All clean probe3 runs of 2048 x 1 (Exp N2, N4, N5): cycles per walk against candidate share and number of 2 MiB regions

cycles per walk = (cycles - 13.97) / page walks per hop; 13.97 is the median of 1024 x 2 in N4 and N5.

| runs | n | cycles per walk (min-max) | a | b: per unit candidate share (s.e.) | c: per 100 regions (s.e.) | R^2 | r(share, regions) |
|---|---:|---|---:|---|---|---:|---:|
| N2 + N4 + N5 | 50 | 23.99-27.86 | 24.19 | +4.87 (1.28) | +0.281 (0.082) | 0.67 | +0.73 |
| N2 | 12 | 23.99-27.13 | 24.06 | +6.99 (0.59) | +0.010 (0.080) | 0.98 | +0.84 |
| N4 | 16 | 24.83-27.86 | 25.13 | -2.30 (4.25) | +0.537 (0.225) | 0.46 | +0.80 |
| N5 | 22 | 24.31-27.40 | 23.56 | +3.38 (1.28) | +0.413 (0.094) | 0.98 | +0.97 |

## Exp T2: first-touch order on the workstation (no host stage-2, unprivileged, frame numbers not readable)

probe2, sequential chase, stride 256; a stopped process holds back memory so that the buffer comes from larger free blocks.  ns = median of three processes (min-max).

| size | held back | ascending first touch | random | descending | random vs ascending | descending vs ascending |
|---:|---:|---|---|---|---:|---:|
| 8 MB | 0 MB | 4.39 (4.14-5.36) | 4.53 (4.51-4.58) | 4.75 (4.62-4.94) | +3.2% | +8.2% |
| 8 MB | 1024 MB | 4.43 (4.09-4.70) | 4.10 (4.01-4.29) | 4.34 (4.27-4.87) | -7.3% | -2.0% |
| 8 MB | 2048 MB | 4.56 (4.34-5.28) | 4.56 (4.20-4.65) | 4.41 (4.37-4.61) | -0.0% | -3.3% |
| 16 MB | 0 MB | 7.53 (7.50-7.55) | 7.56 (7.48-7.57) | 7.53 (7.45-7.57) | +0.5% | +0.0% |
| 16 MB | 1024 MB | 7.53 (7.48-7.58) | 7.52 (7.51-7.64) | 7.58 (7.54-7.59) | -0.1% | +0.7% |
| 16 MB | 2048 MB | 7.54 (7.52-7.55) | 7.54 (7.51-7.55) | 7.54 (7.52-7.55) | +0.1% | +0.1% |
| 64 MB | 0 MB | 7.47 (7.33-7.51) | 7.56 (7.52-7.57) | 7.50 (7.46-7.52) | +1.2% | +0.4% |
| 64 MB | 1024 MB | 7.42 (7.37-7.55) | 7.49 (7.46-7.52) | 7.54 (7.52-7.58) | +1.0% | +1.6% |
| 64 MB | 2048 MB | 7.49 (7.28-7.56) | 7.52 (7.47-7.59) | 7.49 (7.46-7.54) | +0.4% | -0.1% |

## Exp L2: the same frames in sorted, reversed and shuffled virtual order, pages taken from transparent huge pages

thplayout: the pool is faulted in as 2 MiB huge pages, then every 4 KiB page is moved into a new range that starts one page after a 2 MiB boundary (4 KiB page-table entries, no contiguous-PTE folding).  sorted = the order of the pool, i.e. ascending physical address inside every 2 MiB block; aligned = sorted without the one-page offset.  Sequential chase, chain written once; ns = median of the processes (min-max), cycles = 4 x ns / L1 reference.

### N80 (kvm-arm.mode=protected, kernel 6.6.0-79, root)

114 lines; lines whose pool was not fully backed by huge pages: 0.

| loop form | stride | size | sorted: ns | cycles | shuffled: ns | cycles | shuffled vs sorted | extra cycles per page crossing | reversed vs sorted | aligned vs sorted | adjacency: sorted / reversed (descending) / shuffled | page walks per access: sorted / shuffled / aligned | L2 refills: sorted / shuffled |
|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---|---|---|
| loop | 256 | 4 MB | 4.40 (4.39-4.41), 6 | 8.35 | 4.41 (4.41-4.42), 6 | 8.38 | +0.4% | +0 | -0.0% | -4.2% | 0.999 / 0.999 / 0.001 | 0.0000 / 0.0000 / 0.0000 | 0.006 / 0.007 |
| loop | 256 | 8 MB | 7.96 (7.92-7.98), 6 | 15.11 | 9.70 (9.69-9.71), 6 | 18.42 | +21.9% | +53 | +3.0% | -2.3% | 0.999 / 0.999 / 0.000 | 0.0553 / 0.0529 / 0.0000 | 0.282 / 0.259 |
| loop | 256 | 16 MB | 8.10 (8.06-8.12), 6 | 15.39 | 10.52 (10.50-10.58), 6 | 19.97 | +29.8% | +73 | +6.8% | -1.4% | 0.998 / 0.998 / 0.000 | 0.0602 / 0.0602 / 0.0000 | 0.591 / 0.481 |
| loop | 256 | 32 MB | 8.18 (8.14-8.23), 6 | 15.54 | 10.65 (10.57-10.71), 6 | 20.22 | +30.2% | +75 | +6.8% | -2.0% | 0.998 / 0.998 / 0.000 | 0.0625 / 0.0625 / 0.0000 | 0.653 / 0.519 |
| loop | 256 | 64 MB | 8.24 (8.17-8.24), 6 | 15.64 | 10.65 (10.64-10.68), 6 | 20.22 | +29.3% | +73 | +6.8% | -3.0% | 0.998 / 0.998 / 0.000 | 0.0625 / 0.0625 / 0.0002 | 0.674 / 0.538 |
| unrolled | 64 | 16 MB | 3.72 (3.71-3.73), 6 | 7.06 | 4.55 (4.54-4.56), 6 | 8.64 | +22.3% | +101 |  |  | 0.998 / - / 0.000 | 0.0147 / 0.0148 / - | 0.269 / 0.314 |
| unrolled | 256 | 16 MB | 8.89 (8.84-8.96), 6 | 16.88 | 11.37 (11.34-11.46), 6 | 21.58 | +27.9% | +75 |  |  | 0.998 / - / 0.000 | 0.0600 / 0.0601 / - | 0.499 / 0.428 |

### D80F3 workstation (no host stage-2, kernel 7.0.0-34, unprivileged)

114 lines; lines whose pool was not fully backed by huge pages: 0.

| loop form | stride | size | sorted: ns | cycles | shuffled: ns | cycles | shuffled vs sorted | extra cycles per page crossing | reversed vs sorted | aligned vs sorted |
|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|
| loop | 256 | 4 MB | 3.35 (3.34-3.37), 6 | 8.33 | 3.36 (3.34-3.38), 6 | 8.36 | +0.3% | +0 | +0.0% | -4.1% |
| loop | 256 | 8 MB | 4.23 (3.97-4.51), 6 | 10.55 | 4.12 (3.97-4.67), 6 | 10.26 | -2.7% | -5 | -1.7% | -8.5% |
| loop | 256 | 16 MB | 6.86 (6.85-6.98), 6 | 17.08 | 7.55 (7.50-7.62), 6 | 18.79 | +10.1% | +27 | -0.2% | -2.3% |
| loop | 256 | 32 MB | 6.91 (6.88-6.93), 6 | 17.20 | 7.49 (7.43-7.55), 6 | 18.66 | +8.5% | +23 | +1.4% | -2.0% |
| loop | 256 | 64 MB | 6.97 (6.93-7.06), 6 | 17.37 | 7.51 (7.50-7.53), 6 | 18.70 | +7.7% | +21 | +1.1% | -2.5% |
| unrolled | 64 | 16 MB | 3.15 (3.10-3.20), 6 | 7.85 | 3.42 (3.37-3.44), 6 | 8.50 | +8.3% | +42 |  |  |
| unrolled | 256 | 16 MB | 7.67 (7.64-7.71), 6 | 19.09 | 8.14 (8.11-8.17), 6 | 20.25 | +6.2% | +19 |  |  |

## Exp H2: lmbench's own lat_mem_rd (stride 256) with memory held back, probe3 before and after every sweep

A stopped process holds back the given amount before the sweep.  probe3 (sequential, stride 256, 8 MB, lmbench's loop form, chain rewritten before every interval) runs right before and right after the sweep and reports the adjacency of its own buffer (ascending / descending).  lmbench: lat_mem_rd -P 1 64 256 under nothp.  Interconnect: performance 1800000 at the start of every sweep.

| rep | held back | probe3 before: adjacency asc / desc | ns | lmbench 4 MB | 6 MB | 8 MB | 12 MB | 16 MB | 32 MB | 64 MB | probe3 after: adjacency asc / desc | ns |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | 0 MB | 0.00 / 0.00 | 10.39 | 4.91 | 7.69 | 10.46 | 11.47 | 11.55 | 11.25 | 11.00 | 0.01 / 0.72 | 9.55 |
| 1 | 1024 MB | 0.71 / 0.01 | 9.56 | 4.91 | 7.16 | 10.30 | 11.30 | 11.45 | 11.20 | 10.62 | 0.02 / 0.95 | 9.25 |
| 1 | 2048 MB | 0.95 / 0.01 | 8.90 | 4.82 | 6.96 | 10.28 | 11.41 | 11.56 | 11.40 | 10.61 | 0.01 / 0.98 | 9.26 |
| 1 | 2560 MB | 0.96 / 0.01 | 8.87 | 4.80 | 6.78 | 10.30 | 11.46 | 11.59 | 11.36 | 10.30 | 0.01 / 0.97 | 9.14 |
| 2 | 0 MB | 0.97 / 0.01 | 8.84 | 4.81 | 6.92 | 10.26 | 11.32 | 11.38 | 11.28 | 11.09 | 0.00 / 0.73 | 9.61 |
| 2 | 1024 MB | 0.73 / 0.00 | 9.55 | 4.88 | 7.19 | 10.22 | 11.29 | 11.39 | 11.34 | 10.45 | 0.01 / 0.97 | 9.14 |
| 2 | 2048 MB | 0.96 / 0.01 | 8.82 | 4.83 | 6.98 | 10.06 | 11.24 | 11.42 | 11.20 | 10.44 | 0.00 / 0.98 | 9.28 |
| 2 | 2560 MB | 0.97 / 0.00 | 8.84 | 4.81 | 6.89 | 10.04 | 11.23 | 11.44 | 11.16 | 10.32 | 0.01 / 0.96 | 9.23 |
| 3 | 0 MB | 0.96 / 0.01 | 8.84 | 4.81 | 7.03 | 10.38 | 11.44 | 11.56 | 11.55 | 11.11 | 0.00 / 0.73 | 9.48 |
| 3 | 1024 MB | 0.72 / 0.01 | 9.36 | 4.87 | 7.27 | 10.23 | 11.13 | 11.26 | 11.21 | 10.76 | 0.00 / 0.97 | 9.15 |
| 3 | 2048 MB | 0.97 / 0.00 | 8.85 | 4.82 | 6.84 | 10.17 | 11.35 | 11.47 | 10.92 | 10.22 | 0.00 / 0.97 | 9.24 |
| 3 | 2560 MB | 0.97 / 0.00 | 8.87 | 4.82 | 6.99 | 10.31 | 11.09 | 11.33 | 10.34 | 9.91 | 0.01 / 0.97 | 9.19 |
| 4 | 0 MB | 0.96 / 0.01 | 8.86 | 4.82 | 6.96 | 10.20 | 11.14 | 11.29 | 11.30 | 10.85 | 0.01 / 0.72 | 9.46 |
| 4 | 1024 MB | 0.72 / 0.01 | 9.38 | 4.95 | 7.27 | 10.37 | 11.27 | 11.19 | 10.97 | 10.45 | 0.01 / 0.97 | 9.22 |
| 4 | 2048 MB | 0.96 / 0.01 | 8.92 | 4.81 | 7.12 | 10.37 | 11.34 | 11.26 | 10.46 | 9.79 | 0.01 / 0.97 | 9.16 |
| 4 | 2560 MB | 0.96 / 0.01 | 8.80 | 4.82 | 6.98 | 10.35 | 11.20 | 11.27 | 10.86 | 10.10 | 0.01 / 0.97 | 9.26 |

probe3, 8 MB: 23 runs with total adjacency of at least 0.8: median 9.14 ns (8.80-9.28); 1 runs with at most 0.3: median 10.39 ns (10.39-10.39); ratio 0.880.  Spearman rho(ns, total adjacency) over the 32 probe3 runs: -0.48.

lmbench's own values by the amount held back (median, min-max over the sweeps):

| held back | sweeps | 4 MB | 6 MB | 8 MB | 12 MB | 16 MB | 24 MB | 32 MB | 48 MB | 64 MB |
|---:|---:|---|---|---|---|---|---|---|---|---|
| 0 MB | 4 | 4.81 (4.81-4.91) | 7.00 (6.92-7.69) | 10.32 (10.20-10.46) | 11.38 (11.14-11.47) | 11.47 (11.29-11.56) | 11.25 (10.99-11.44) | 11.29 (11.25-11.55) | 11.00 (10.93-11.30) | 11.05 (10.85-11.11) |
| 1024 MB | 4 | 4.89 (4.87-4.95) | 7.23 (7.16-7.27) | 10.27 (10.22-10.37) | 11.28 (11.13-11.30) | 11.32 (11.19-11.45) | 11.14 (10.91-11.45) | 11.20 (10.97-11.34) | 10.83 (10.78-11.11) | 10.54 (10.45-10.76) |
| 2048 MB | 4 | 4.82 (4.81-4.83) | 6.97 (6.84-7.12) | 10.23 (10.06-10.37) | 11.34 (11.24-11.41) | 11.44 (11.26-11.56) | 11.51 (10.89-11.62) | 11.06 (10.46-11.40) | 10.52 (10.05-11.00) | 10.33 (9.79-10.61) |
| 2560 MB | 4 | 4.81 (4.80-4.82) | 6.93 (6.78-6.99) | 10.31 (10.04-10.35) | 11.22 (11.09-11.46) | 11.38 (11.27-11.59) | 11.07 (10.89-11.39) | 11.01 (10.34-11.36) | 10.31 (10.28-10.47) | 10.20 (9.91-10.32) |

## Exp H3: lmbench's own lat_mem_rd (stride 256), with the physical layout of its own buffers

As H2, and a watcher reads /proc/<pid>/pagemap of every lat_mem_rd child a quarter of a second after it appeared.  adjacency = fraction of virtually adjacent pages of the child's buffer that are physically adjacent (ascending / descending); runs = maximal runs of physically adjacent pages.  A child is matched to the lmbench output line of the same size that was printed after the child was sampled.

### The 8 MB point, every sweep

| rep | held back | lmbench ns | adjacency of its buffer: asc / desc | runs of adjacent pages | longest run (pages) | 2 MiB regions |
|---:|---:|---:|---|---:|---:|---:|
| 1 | 0 MB | 10.28 | 0.001 / 0.001 | 2046 | 2 | 649 |
| 1 | 1024 MB | 10.38 | 0.001 / 0.006 | 2035 | 4 | 669 |
| 1 | 2048 MB | 10.17 | 0.195 / 0.002 | 1647 | 293 | 615 |
| 1 | 2560 MB | 10.19 | 0.106 / 0.013 | 1805 | 210 | 624 |
| 2 | 0 MB | 10.17 | 0.156 / 0.011 | 1708 | 270 | 621 |
| 2 | 1024 MB | 10.44 | 0.001 / 0.001 | 2046 | 2 | 621 |
| 2 | 2048 MB | 10.27 | 0.011 / 0.001 | 2024 | 21 | 628 |
| 2 | 2560 MB | 10.34 | 0.002 / 0.001 | 2042 | 5 | 626 |
| 3 | 0 MB | 10.32 | 0.123 / 0.002 | 1794 | 251 | 630 |
| 3 | 1024 MB | 10.25 | 0.084 / 0.008 | 1861 | 4 | 620 |
| 3 | 2048 MB | 10.14 | 0.162 / 0.003 | 1711 | 268 | 610 |
| 3 | 2560 MB | 10.21 | 0.095 / 0.000 | 1855 | 192 | 628 |

### The 16 MB point, every sweep

| rep | held back | lmbench ns | adjacency of its buffer: asc / desc | runs of adjacent pages | longest run (pages) | 2 MiB regions |
|---:|---:|---:|---|---:|---:|---:|
| 1 | 0 MB | 11.36 | 0.125 / 0.007 | 3557 | 4 | 752 |
| 1 | 1024 MB | 11.49 | 0.127 / 0.006 | 3554 | 4 | 764 |
| 1 | 2048 MB | 11.36 | 0.144 / 0.001 | 3506 | 252 | 760 |
| 1 | 2560 MB | 11.48 | 0.035 / 0.007 | 3926 | 77 | 838 |
| 2 | 0 MB | 11.40 | 0.086 / 0.001 | 3740 | 205 | 799 |
| 2 | 1024 MB | 11.51 | 0.001 / 0.005 | 4076 | 4 | 836 |
| 2 | 2048 MB | 11.55 | 0.051 / 0.003 | 3876 | 21 | 822 |
| 2 | 2560 MB | 11.51 | 0.003 / 0.002 | 4079 | 5 | 827 |
| 3 | 0 MB | 11.49 | 0.027 / 0.001 | 3980 | 108 | 834 |
| 3 | 1024 MB | 11.49 | 0.107 / 0.004 | 3639 | 4 | 787 |
| 3 | 2048 MB | 11.30 | 0.087 / 0.001 | 3736 | 193 | 816 |
| 3 | 2560 MB | 11.34 | 0.069 / 0.003 | 3802 | 192 | 836 |

### The 64 MB point, every sweep

| rep | held back | lmbench ns | adjacency of its buffer: asc / desc | runs of adjacent pages | longest run (pages) | 2 MiB regions |
|---:|---:|---:|---|---:|---:|---:|
| 1 | 0 MB | 11.04 | 0.281 / 0.205 | 8429 | 8 | 877 |
| 1 | 1024 MB | 10.86 | 0.340 / 0.252 | 6682 | 512 | 878 |
| 1 | 2048 MB | 10.06 | 0.387 / 0.311 | 4963 | 1024 | 826 |
| 1 | 2560 MB | 10.46 | 0.339 / 0.297 | 5969 | 1024 | 901 |
| 2 | 0 MB | 11.05 | 0.268 / 0.187 | 8923 | 205 | 936 |
| 2 | 1024 MB | 10.58 | 0.292 / 0.225 | 7907 | 512 | 980 |
| 2 | 2048 MB | 10.43 | 0.282 / 0.262 | 7466 | 512 | 983 |
| 2 | 2560 MB | 10.25 | 0.318 / 0.303 | 6208 | 1024 | 901 |
| 3 | 0 MB | 11.04 | 0.237 / 0.183 | 9516 | 108 | 983 |
| 3 | 1024 MB | 10.49 | 0.333 / 0.285 | 6261 | 512 | 905 |
| 3 | 2048 MB | 10.38 | 0.334 / 0.297 | 6054 | 1024 | 886 |
| 3 | 2560 MB | 10.09 | 0.361 / 0.317 | 5282 | 1024 | 898 |

### By size: latency against the adjacency of lmbench's own buffer

| size | sweeps matched | total adjacency (min-max) | ns (min-max) | Spearman rho(ns, total adjacency) | sweeps with adjacency >= 0.8: n, median ns | sweeps with adjacency <= 0.3: n, median ns | ratio |
|---:|---:|---|---|---:|---|---|---:|
| 2 MB | 12 | 0.00-0.88 | 4.45-4.57 | -0.60 | 8, 4.46 | 1, 4.54 | 0.983 |
| 3 MB | 12 | 0.00-0.92 | 4.67-4.73 | -0.68 | 8, 4.68 | 1, 4.73 | 0.990 |
| 4 MB | 12 | 0.00-0.93 | 4.83-4.92 | -0.89 | 8, 4.84 | 1, 4.92 | 0.984 |
| 6 MB | 12 | 0.00-0.85 | 6.90-7.82 | -0.99 | 3, 6.91 | 1, 7.82 | 0.883 |
| 8 MB | 12 | 0.00-0.20 | 10.14-10.44 | -0.81 | 0 | 12, 10.26 |  |
| 12 MB | 12 | 0.00-0.14 | 11.22-11.42 | -0.75 | 0 | 12, 11.35 |  |
| 16 MB | 12 | 0.00-0.14 | 11.30-11.55 | -0.58 | 0 | 12, 11.48 |  |
| 24 MB | 12 | 0.15-0.26 | 11.15-11.58 | -0.57 | 0 | 12, 11.37 |  |
| 32 MB | 12 | 0.20-0.41 | 10.78-11.41 | -0.57 | 0 | 6, 11.26 |  |
| 48 MB | 12 | 0.34-0.60 | 10.39-11.32 | -0.96 | 0 | 0 |  |
| 64 MB | 12 | 0.42-0.70 | 10.06-11.05 | -0.89 | 0 | 0 |  |

## Exp H4: lmbench's own lat_mem_rd (stride 256) on a buffer whose physical layout is set

The unmodified lat_mem_rd binary with layoutshim.so preloaded: its 64 MB buffer consists of 4 KiB pages taken from 2 MiB huge pages, in physical order (sorted), in random order within every 8 MB (shuffled8: the first 8 MB use the same frames as sorted), or in random order over the whole buffer (shuffled).  natural = without the library, under nothp, as in Exp H.  ns = lmbench's own figure; median over the repetitions (min-max).

### N80 (kvm-arm.mode=protected, kernel 6.6.0-79, root)

Interconnect at the start of every sweep: performance 1800000.

Buffers built by the library: 396; fully backed by huge pages before being taken apart: 396.
Adjacency of the first 2048 pages, sorted: ascending 0.9985-0.9985, descending 0.0000-0.0000 (132 buffers).
Adjacency of the first 2048 pages, shuffled8: ascending 0.0000-0.0010, descending 0.0000-0.0010 (132 buffers).
Adjacency of the first 2048 pages, shuffled: ascending 0.0000-0.0005, descending 0.0000-0.0000 (132 buffers).

| size | sorted | shuffled8 | shuffled | natural | shuffled8 / sorted | shuffled / sorted | natural / sorted |
|---:|---|---|---|---|---:|---:|---:|
| 2 MB | 4.45 (4.45-4.46) | 4.52 (4.50-4.53) | 4.52 (4.51-4.52) | 4.53 (4.52-4.55) | 1.014 | 1.015 | 1.017 |
| 4 MB | 4.82 (4.82-4.84) | 4.85 (4.83-4.87) | 4.87 (4.85-4.98) | 4.89 (4.87-5.01) | 1.007 | 1.010 | 1.015 |
| 6 MB | 6.82 (6.82-6.83) | 7.28 (7.20-7.30) | 7.53 (7.48-7.56) | 7.68 (7.63-7.72) | 1.066 | 1.103 | 1.125 |
| 8 MB | 8.90 (8.87-8.93) | 10.62 (10.54-10.63) | 10.52 (10.48-10.54) | 10.36 (10.22-10.43) | 1.193 | 1.181 | 1.164 |
| 12 MB | 9.10 (9.06-9.13) | 11.44 (11.39-11.51) | 11.52 (11.35-11.54) | 11.38 (11.20-11.42) | 1.256 | 1.266 | 1.249 |
| 16 MB | 9.02 (8.93-9.05) | 11.54 (11.47-11.65) | 11.59 (11.38-11.65) | 11.48 (11.18-11.54) | 1.280 | 1.286 | 1.273 |
| 24 MB | 8.91 (8.63-8.96) | 11.56 (11.52-11.68) | 11.63 (11.40-11.69) | 11.46 (11.43-11.51) | 1.298 | 1.306 | 1.287 |
| 32 MB | 8.74 (8.55-8.93) | 11.59 (11.51-11.71) | 11.65 (11.40-11.71) | 11.27 (11.04-11.32) | 1.326 | 1.333 | 1.290 |
| 48 MB | 8.78 (8.58-8.86) | 11.50 (11.47-11.69) | 11.65 (11.39-11.72) | 11.21 (10.78-11.35) | 1.310 | 1.327 | 1.277 |
| 64 MB | 8.83 (8.57-9.93) | 11.53 (11.47-11.70) | 11.64 (11.41-11.70) | 10.97 (10.76-11.28) | 1.305 | 1.318 | 1.242 |

The 8 MB point in every repetition (ns): rep 1: sorted 8.87, shuffled8 10.63, shuffled 10.53, natural 10.43; rep 2: sorted 8.91, shuffled8 10.61, shuffled 10.54, natural 10.38; rep 3: sorted 8.93, shuffled8 10.63, shuffled 10.48, natural 10.35; rep 4: sorted 8.89, shuffled8 10.54, shuffled 10.51, natural 10.22.

### D80F3 workstation (no host stage-2, kernel 7.0.0-34, unprivileged)

Buffers built by the library: 396; fully backed by huge pages before being taken apart: 396.

| size | sorted | shuffled8 | shuffled | natural | shuffled8 / sorted | shuffled / sorted | natural / sorted |
|---:|---|---|---|---|---:|---:|---:|
| 2 MB | 3.42 (3.41-3.43) | 3.43 (3.43-3.44) | 3.43 (3.43-3.43) | 3.44 (3.43-3.45) | 1.006 | 1.005 | 1.006 |
| 4 MB | 3.49 (3.48-3.50) | 3.57 (3.56-3.61) | 3.60 (3.57-3.62) | 3.62 (3.60-3.65) | 1.024 | 1.031 | 1.037 |
| 6 MB | 3.89 (3.81-4.05) | 4.01 (3.98-4.06) | 3.98 (3.94-4.08) | 4.12 (4.03-4.18) | 1.031 | 1.021 | 1.058 |
| 8 MB | 4.30 (4.12-4.40) | 4.63 (4.57-4.75) | 4.70 (4.46-4.91) | 4.77 (4.61-5.28) | 1.076 | 1.092 | 1.110 |
| 12 MB | 6.65 (6.52-6.85) | 7.53 (7.34-7.58) | 7.56 (7.54-7.60) | 7.63 (7.45-7.80) | 1.133 | 1.138 | 1.148 |
| 16 MB | 7.72 (7.66-7.73) | 8.19 (8.17-8.21) | 8.17 (8.11-8.24) | 8.21 (8.18-8.25) | 1.061 | 1.057 | 1.064 |
| 24 MB | 7.74 (7.66-7.80) | 8.10 (8.02-8.13) | 8.07 (7.96-8.10) | 8.08 (8.00-8.16) | 1.047 | 1.042 | 1.044 |
| 32 MB | 7.72 (7.62-7.79) | 7.99 (7.91-8.06) | 7.96 (7.93-8.06) | 7.97 (7.83-8.02) | 1.035 | 1.031 | 1.033 |
| 48 MB | 7.63 (7.55-7.69) | 7.93 (7.83-7.94) | 7.93 (7.87-7.98) | 7.94 (7.91-7.97) | 1.039 | 1.040 | 1.041 |
| 64 MB | 7.65 (7.55-7.72) | 7.94 (7.92-7.95) | 7.87 (7.80-7.97) | 7.91 (7.84-8.02) | 1.038 | 1.029 | 1.034 |

The 8 MB point in every repetition (ns): rep 1: sorted 4.24, shuffled8 4.62, shuffled 4.91, natural 4.85; rep 2: sorted 4.12, shuffled8 4.75, shuffled 4.77, natural 4.61; rep 3: sorted 4.40, shuffled8 4.57, shuffled 4.63, natural 4.69; rep 4: sorted 4.36, shuffled8 4.64, shuffled 4.46, natural 5.28.

## Exp H5: lmbench's own lat_mem_rd on sorted and on shuffled pages, every stride of the paper's command

As H4 (layoutshim.so; shuffled = random order within every 8 MB, the same frames as sorted).  Strides 16, 32, 64, 128, 512, 1024 from run28 (two repetitions per layout), stride 256 from H4 (four).  ns = lmbench's own figure, median of the repetitions.  The N90 columns are the two levels of the four quiesced host boots of June 2026 at the same point (40 values; high = more than 12% above the median of the lower half).

### N80 (kvm-arm.mode=protected, kernel 6.6.0-79, root)

8 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 2.179 (2.179-2.180), 2 | 2.183 (2.183-2.184), 2 | +0.004 | 1.002 | 2.304, 40 | none, 0 | |
| 32 | 2.439 (2.438-2.441), 2 | 2.572 (2.568-2.576), 2 | +0.133 | 1.054 | 2.648, 40 | none, 0 | |
| 64 | 3.543 (3.514-3.572), 2 | 4.357 (4.344-4.369), 2 | +0.814 | 1.230 | 4.234, 36 | 5.168, 4 | 1.221 |
| 128 | 8.026 (8.025-8.027), 2 | 9.648 (9.642-9.653), 2 | +1.622 | 1.202 | 9.326, 12 | 11.367, 28 | 1.219 |
| 256 | 8.903 (8.872-8.927), 4 | 10.619 (10.545-10.629), 4 | +1.716 | 1.193 | 10.323, 18 | 12.460, 22 | 1.207 |
| 512 | 8.322 (8.307-8.336), 2 | 10.043 (10.037-10.049), 2 | +1.721 | 1.207 | 9.680, 23 | 11.729, 17 | 1.212 |
| 1024 | 9.272 (9.265-9.279), 2 | 10.844 (10.826-10.861), 2 | +1.572 | 1.169 | 10.848, 18 | 12.607, 22 | 1.162 |

12 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 2.187 (2.185-2.188), 2 | 2.189 (2.189-2.190), 2 | +0.003 | 1.001 | 2.306, 40 | none, 0 | |
| 32 | 2.470 (2.465-2.474), 2 | 2.603 (2.595-2.611), 2 | +0.134 | 1.054 | 2.682, 40 | none, 0 | |
| 64 | 3.651 (3.618-3.683), 2 | 4.524 (4.519-4.528), 2 | +0.873 | 1.239 | 4.372, 37 | 5.445, 3 | 1.245 |
| 128 | 8.155 (8.147-8.164), 2 | 10.018 (9.983-10.053), 2 | +1.863 | 1.228 | 9.791, 34 | 12.178, 6 | 1.244 |
| 256 | 9.104 (9.056-9.133), 4 | 11.436 (11.389-11.505), 4 | +2.332 | 1.256 | 11.079, 35 | 13.611, 5 | 1.229 |
| 512 | 8.653 (8.637-8.669), 2 | 10.903 (10.830-10.976), 2 | +2.250 | 1.260 | 10.219, 37 | 12.770, 3 | 1.250 |
| 1024 | 9.662 (9.612-9.713), 2 | 12.168 (12.025-12.311), 2 | +2.505 | 1.259 | 11.473, 35 | 13.449, 5 | 1.172 |

6 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 2.173 (2.173-2.173), 2 | 2.178 (2.178-2.178), 2 | +0.005 | 1.002 | 2.312, 40 | none, 0 | |
| 32 | 2.390 (2.389-2.391), 2 | 2.443 (2.442-2.444), 2 | +0.053 | 1.022 | 2.603, 40 | none, 0 | |
| 64 | 3.299 (3.261-3.337), 2 | 3.647 (3.636-3.659), 2 | +0.348 | 1.106 | 4.011, 40 | none, 0 | |
| 128 | 6.497 (6.488-6.506), 2 | 6.950 (6.935-6.965), 2 | +0.453 | 1.070 | 7.662, 40 | none, 0 | |
| 256 | 6.824 (6.816-6.835), 4 | 7.277 (7.202-7.305), 4 | +0.453 | 1.066 | 8.289, 40 | none, 0 | |
| 512 | 6.658 (6.627-6.689), 2 | 7.588 (7.531-7.645), 2 | +0.930 | 1.140 | 8.020, 40 | none, 0 | |
| 1024 | 6.951 (6.943-6.959), 2 | 8.431 (8.402-8.460), 2 | +1.480 | 1.213 | 8.618, 40 | none, 0 | |

4 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 2.172 (2.172-2.172), 2 | 2.175 (2.175-2.176), 2 | +0.003 | 1.002 | 2.307, 40 | none, 0 | |
| 32 | 2.354 (2.354-2.354), 2 | 2.357 (2.357-2.358), 2 | +0.003 | 1.001 | 2.543, 40 | none, 0 | |
| 64 | 2.585 (2.582-2.588), 2 | 2.596 (2.591-2.601), 2 | +0.011 | 1.004 | 2.776, 40 | none, 0 | |
| 128 | 4.462 (4.462-4.462), 2 | 4.482 (4.475-4.488), 2 | +0.020 | 1.004 | 5.181, 40 | none, 0 | |
| 256 | 4.820 (4.818-4.845), 4 | 4.854 (4.827-4.873), 4 | +0.034 | 1.007 | 5.484, 40 | none, 0 | |
| 512 | 5.056 (5.053-5.059), 2 | 5.476 (5.467-5.485), 2 | +0.420 | 1.083 | 5.495, 40 | none, 0 | |
| 1024 | 5.256 (5.256-5.257), 2 | 6.450 (6.430-6.469), 2 | +1.193 | 1.227 | 5.729, 40 | none, 0 | |

64 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 2.199 (2.198-2.199), 2 | 2.194 (2.193-2.194), 2 | -0.005 | 0.998 | 2.316, 40 | none, 0 | |
| 32 | 2.503 (2.500-2.506), 2 | 2.627 (2.627-2.627), 2 | +0.124 | 1.050 | 2.678, 40 | none, 0 | |
| 64 | 3.774 (3.737-3.811), 2 | 4.615 (4.606-4.624), 2 | +0.841 | 1.223 | 4.246, 38 | 5.353, 2 | 1.261 |
| 128 | 8.111 (8.107-8.114), 2 | 9.991 (9.986-9.996), 2 | +1.880 | 1.232 | 9.118, 39 | 11.447, 1 | 1.255 |
| 256 | 8.835 (8.574-9.927), 4 | 11.527 (11.467-11.703), 4 | +2.693 | 1.305 | 10.442, 39 | 11.480, 1 | 1.099 |
| 512 | 8.909 (8.895-8.923), 2 | 11.123 (11.103-11.144), 2 | +2.215 | 1.249 | 9.690, 39 | 10.729, 1 | 1.107 |
| 1024 | 10.250 (10.244-10.256), 2 | 12.736 (12.729-12.742), 2 | +2.486 | 1.242 | 10.809, 40 | none, 0 | |

### D80F3 workstation (no host stage-2, kernel 7.0.0-34, unprivileged)

8 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 1.664 (1.664-1.665), 2 | 1.666 (1.666-1.666), 2 | +0.002 | 1.001 | 2.304, 40 | none, 0 | |
| 32 | 1.906 (1.882-1.930), 2 | 1.923 (1.913-1.934), 2 | +0.018 | 1.009 | 2.648, 40 | none, 0 | |
| 64 | 2.494 (2.388-2.600), 2 | 2.773 (2.687-2.859), 2 | +0.279 | 1.112 | 4.234, 36 | 5.168, 4 | 1.221 |
| 128 | 4.627 (4.592-4.663), 2 | 4.883 (4.462-5.303), 2 | +0.255 | 1.055 | 9.326, 12 | 11.367, 28 | 1.219 |
| 256 | 4.302 (4.123-4.398), 4 | 4.627 (4.568-4.753), 4 | +0.326 | 1.076 | 10.323, 18 | 12.460, 22 | 1.207 |
| 512 | 4.323 (4.278-4.369), 2 | 4.902 (4.760-5.043), 2 | +0.578 | 1.134 | 9.680, 23 | 11.729, 17 | 1.212 |
| 1024 | 4.326 (4.314-4.338), 2 | 5.261 (5.249-5.274), 2 | +0.935 | 1.216 | 10.848, 18 | 12.607, 22 | 1.162 |

12 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 1.669 (1.668-1.670), 2 | 1.672 (1.671-1.674), 2 | +0.003 | 1.002 | 2.306, 40 | none, 0 | |
| 32 | 1.993 (1.975-2.011), 2 | 2.014 (2.000-2.027), 2 | +0.020 | 1.010 | 2.682, 40 | none, 0 | |
| 64 | 2.984 (2.971-2.997), 2 | 3.344 (3.337-3.351), 2 | +0.360 | 1.121 | 4.372, 37 | 5.445, 3 | 1.245 |
| 128 | 6.496 (6.491-6.501), 2 | 7.109 (6.968-7.250), 2 | +0.613 | 1.094 | 9.791, 34 | 12.178, 6 | 1.244 |
| 256 | 6.646 (6.522-6.852), 4 | 7.530 (7.344-7.577), 4 | +0.884 | 1.133 | 11.079, 35 | 13.611, 5 | 1.229 |
| 512 | 6.226 (6.114-6.337), 2 | 7.402 (7.396-7.408), 2 | +1.176 | 1.189 | 10.219, 37 | 12.770, 3 | 1.250 |
| 1024 | 6.474 (6.454-6.495), 2 | 7.981 (7.805-8.156), 2 | +1.506 | 1.233 | 11.473, 35 | 13.449, 5 | 1.172 |

6 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 1.661 (1.661-1.662), 2 | 1.664 (1.664-1.664), 2 | +0.002 | 1.002 | 2.312, 40 | none, 0 | |
| 32 | 1.857 (1.849-1.864), 2 | 1.861 (1.852-1.869), 2 | +0.004 | 1.002 | 2.603, 40 | none, 0 | |
| 64 | 2.266 (2.215-2.317), 2 | 2.231 (2.179-2.283), 2 | -0.035 | 0.985 | 4.011, 40 | none, 0 | |
| 128 | 3.869 (3.797-3.940), 2 | 3.858 (3.845-3.871), 2 | -0.010 | 0.997 | 7.662, 40 | none, 0 | |
| 256 | 3.893 (3.806-4.047), 4 | 4.014 (3.983-4.060), 4 | +0.120 | 1.031 | 8.289, 40 | none, 0 | |
| 512 | 4.037 (4.029-4.044), 2 | 4.511 (4.450-4.572), 2 | +0.474 | 1.118 | 8.020, 40 | none, 0 | |
| 1024 | 4.146 (4.140-4.153), 2 | 5.105 (5.058-5.152), 2 | +0.959 | 1.231 | 8.618, 40 | none, 0 | |

4 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 1.660 (1.660-1.661), 2 | 1.661 (1.660-1.662), 2 | +0.001 | 1.000 | 2.307, 40 | none, 0 | |
| 32 | 1.792 (1.785-1.798), 2 | 1.798 (1.793-1.803), 2 | +0.006 | 1.004 | 2.543, 40 | none, 0 | |
| 64 | 1.990 (1.989-1.992), 2 | 2.024 (2.016-2.032), 2 | +0.034 | 1.017 | 2.776, 40 | none, 0 | |
| 128 | 3.352 (3.341-3.363), 2 | 3.400 (3.394-3.406), 2 | +0.048 | 1.014 | 5.181, 40 | none, 0 | |
| 256 | 3.487 (3.476-3.504), 4 | 3.570 (3.558-3.606), 4 | +0.083 | 1.024 | 5.484, 40 | none, 0 | |
| 512 | 3.874 (3.872-3.877), 2 | 4.201 (4.193-4.210), 2 | +0.327 | 1.084 | 5.495, 40 | none, 0 | |
| 1024 | 3.995 (3.994-3.997), 2 | 4.954 (4.930-4.979), 2 | +0.959 | 1.240 | 5.729, 40 | none, 0 | |

64 MB:

| stride | sorted: ns (min-max), n | shuffled: ns (min-max), n | shuffled - sorted | shuffled / sorted | N90: low level, n | N90: high level, n | N90: high / low |
|---:|---|---|---:|---:|---|---|---:|
| 16 | 1.696 (1.693-1.698), 2 | 1.688 (1.687-1.688), 2 | -0.008 | 0.995 | 2.316, 40 | none, 0 | |
| 32 | 2.130 (2.128-2.131), 2 | 2.135 (2.131-2.139), 2 | +0.005 | 1.003 | 2.678, 40 | none, 0 | |
| 64 | 3.434 (3.431-3.438), 2 | 3.572 (3.535-3.608), 2 | +0.137 | 1.040 | 4.246, 38 | 5.353, 2 | 1.261 |
| 128 | 7.157 (7.150-7.163), 2 | 7.347 (7.333-7.360), 2 | +0.190 | 1.027 | 9.118, 39 | 11.447, 1 | 1.255 |
| 256 | 7.651 (7.548-7.724), 4 | 7.938 (7.924-7.951), 4 | +0.287 | 1.038 | 10.442, 39 | 11.480, 1 | 1.099 |
| 512 | 7.248 (7.232-7.264), 2 | 8.624 (8.605-8.643), 2 | +1.376 | 1.190 | 9.690, 39 | 10.729, 1 | 1.107 |
| 1024 | 8.282 (8.282-8.283), 2 | 9.757 (9.744-9.770), 2 | +1.475 | 1.178 | 10.809, 40 | none, 0 | |

## Exp H6: lmbench's own random-access test (lat_mem_rd -t -P 1 64 16) on a buffer whose physical layout is set

N80, protected mode, interconnect at 1800 MHz.  sorted and shuffled (over the whole buffer) use layoutshim.so; natural = without the library, under nothp.  ns = lmbench's own figure, median of the repetitions (min-max).  The last two columns are the N90 host medians of June 2026 in its two platform states (nVHE, quiesced and non-quiesced).

| size | sorted | shuffled | natural | shuffled / sorted | natural / sorted | N90 quiesced | N90 fast state | fast / quiesced |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 1 MB | 18.45 (18.39-18.50) | 19.11 (19.06-19.15) | 18.87 (18.55-19.19) | 1.036 | 1.023 | 19.48 | 19.05 | 0.978 |
| 2 MB | 21.35 (21.33-21.36) | 21.65 (21.59-21.71) | 21.21 (20.95-21.47) | 1.014 | 0.994 | 20.75 | 21.10 | 1.017 |
| 3 MB | 27.81 (27.65-27.97) | 27.48 (27.29-27.68) | 28.25 (27.86-28.64) | 0.988 | 1.016 | 36.63 | 26.41 | 0.721 |
| 4 MB | 33.37 (33.14-33.60) | 33.12 (32.74-33.50) | 34.61 (34.52-34.69) | 0.992 | 1.037 | 47.69 | 30.80 | 0.646 |
| 6 MB | 55.22 (54.30-56.13) | 54.53 (53.23-55.83) | 62.61 (61.47-63.76) | 0.988 | 1.134 | 67.35 | 48.61 | 0.722 |
| 8 MB | 93.76 (92.41-95.11) | 94.83 (94.14-95.53) | 97.59 (97.31-97.86) | 1.011 | 1.041 | 112.60 | 83.90 | 0.745 |
| 12 MB | 127.81 (126.85-128.76) | 128.57 (128.38-128.75) | 130.17 (129.94-130.40) | 1.006 | 1.018 | 154.81 | 121.82 | 0.787 |
| 16 MB | 139.40 (139.28-139.53) | 140.50 (140.46-140.54) | 142.00 (141.58-142.41) | 1.008 | 1.019 | 168.56 | 134.23 | 0.796 |
| 24 MB | 147.76 (147.41-148.10) | 148.08 (147.97-148.19) | 149.97 (149.88-150.06) | 1.002 | 1.015 | 177.47 | 143.08 | 0.806 |
| 32 MB | 151.01 (150.78-151.23) | 151.10 (151.04-151.16) | 152.75 (152.43-153.07) | 1.001 | 1.012 | 180.78 | 146.20 | 0.809 |
| 48 MB | 153.46 (153.01-153.92) | 153.50 (153.40-153.60) | 154.28 (154.15-154.40) | 1.000 | 1.005 | 182.44 | 149.10 | 0.817 |
| 64 MB | 154.84 (154.35-155.32) | 154.59 (154.45-154.72) | 154.35 (154.30-154.41) | 0.998 | 0.997 | 185.05 | 150.12 | 0.811 |

## Exp H7: which frames the successive children of lmbench's lat_mem_rd get (stride 256)

lmb-frames.py stored the frame numbers of every child's buffer.  Per sweep and child: runs = maximal runs of physically adjacent pages; 'from the previous child' = share of this child's frames that were in the buffer of the child before it (if a child gets back all frames of its predecessor this equals the ratio of the two sizes, 0.60 to 0.75); new = frames not used by any earlier child of the sweep; per-CPU list = count and high of cpu0 in zone Normal at the start of the sweep (/proc/zoneinfo).

### sweep 1: 0 MB held back; per-CPU list at the start: 637 pages, high 1781

| pages of the buffer | runs | distinct 2 MiB regions | from the previous child | size ratio | new frames | runs among the new frames | lmbench ns |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1025 | 1023 | 419 | 0.74 | 0.75 | 258 | 257 | 5.01 |
| 1537 | 1535 | 517 | 0.64 | 0.67 | 527 | 527 | 7.65 |
| 2049 | 2047 | 588 | 0.74 | 0.75 | 513 | 513 | 10.36 |
| 3073 | 2929 | 662 | 0.66 | 0.67 | 1019 | 878 | 11.33 |
| 4097 | 3441 | 673 | 0.75 | 0.75 | 1026 | 514 | 11.30 |
| 6145 | 4477 | 715 | 0.66 | 0.67 | 2064 | 1033 | 10.86 |
| 8193 | 5503 | 744 | 0.75 | 0.75 | 2048 | 1025 | 11.21 |
| 12289 | 7170 | 781 | 0.67 | 0.67 | 4076 | 1657 | 10.67 |
| 16385 | 8154 | 805 | 0.75 | 0.75 | 4096 | 972 | 10.87 |

### sweep 2: 2560 MB held back; per-CPU list at the start: 17146 pages, high 17279

| pages of the buffer | runs | distinct 2 MiB regions | from the previous child | size ratio | new frames | runs among the new frames | lmbench ns |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1025 | 263 | 148 | 0.74 | 0.75 | 256 | 65 | 4.89 |
| 1537 | 712 | 344 | 0.65 | 0.67 | 513 | 439 | 7.46 |
| 2049 | 2033 | 590 | 0.18 | 0.75 | 1655 | 1655 | 10.29 |
| | | | | | | frames in common with the 8 MB child of the previous sweep: 0.60 | |
| 3073 | 2891 | 661 | 0.66 | 0.67 | 945 | 793 | 11.29 |
| 4097 | 3405 | 692 | 0.75 | 0.75 | 1024 | 513 | 11.29 |
| 6145 | 4438 | 728 | 0.66 | 0.67 | 2048 | 1022 | 11.04 |
| 8193 | 5432 | 759 | 0.74 | 0.75 | 2113 | 1057 | 11.18 |
| 12289 | 7006 | 800 | 0.67 | 0.67 | 3437 | 1409 | 10.91 |
| 16385 | 8233 | 847 | 0.75 | 0.75 | 3686 | 1159 | 10.79 |

### sweep 3: 0 MB held back; per-CPU list at the start: 17336 pages, high 18028

| pages of the buffer | runs | distinct 2 MiB regions | from the previous child | size ratio | new frames | runs among the new frames | lmbench ns |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1025 | 190 | 77 | 0.74 | 0.75 | 258 | 55 | 4.87 |
| 1537 | 622 | 292 | 0.65 | 0.67 | 512 | 429 | 7.26 |
| 2049 | 2028 | 593 | 0.15 | 0.75 | 1707 | 1701 | 10.44 |
| | | | | | | frames in common with the 8 MB child of the previous sweep: 0.55 | |
| 3073 | 2879 | 659 | 0.66 | 0.67 | 988 | 827 | 11.33 |
| 4097 | 3393 | 687 | 0.75 | 0.75 | 1024 | 513 | 11.34 |
| 6145 | 4426 | 732 | 0.66 | 0.67 | 2076 | 1039 | 11.21 |
| 8193 | 5448 | 757 | 0.75 | 0.75 | 2048 | 1022 | 11.23 |
| 12289 | 7162 | 791 | 0.67 | 0.67 | 3922 | 1669 | 11.23 |
| 16385 | 8579 | 850 | 0.75 | 0.75 | 3826 | 1355 | 11.10 |

### sweep 4: 2560 MB held back; per-CPU list at the start: 13382 pages, high 13444

| pages of the buffer | runs | distinct 2 MiB regions | from the previous child | size ratio | new frames | runs among the new frames | lmbench ns |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1025 | 300 | 165 | 0.74 | 0.75 | 256 | 65 | 4.89 |
| 1537 | 772 | 389 | 0.65 | 0.67 | 513 | 464 | 7.47 |
| 2049 | 1634 | 558 | 0.47 | 0.75 | 1052 | 1052 | 10.26 |
| | | | | | | frames in common with the 8 MB child of the previous sweep: 0.63 | |
| 3073 | 2551 | 633 | 0.66 | 0.67 | 986 | 896 | 11.12 |
| 4097 | 3232 | 654 | 0.62 | 0.75 | 1538 | 801 | 11.06 |
| 6145 | 4266 | 702 | 0.66 | 0.67 | 2048 | 1024 | 11.09 |
| 8193 | 5291 | 741 | 0.75 | 0.75 | 2054 | 1028 | 10.99 |
| 12289 | 6422 | 809 | 0.67 | 0.67 | 3330 | 939 | 10.91 |
| 16385 | 6515 | 820 | 0.75 | 0.75 | 4096 | 73 | 10.71 |

## Exp H8: lmbench's own lat_mem_rd on a buffer of which only the first 8 MB are scattered

layoutshim.so; sorted = physical order; head8 = the pages of the first 8 MB in random order, the rest in physical order (SHUFFLE_HEAD_MB=8); shuffled8 = random order within every 8 MB.  Command lat_mem_rd -P 1 64 128 256, three repetitions per layout.  ns = lmbench's own figure, median (min-max).  'linear' = 1 + (scattered share) x (shuffled8 / sorted - 1), the scattered share being min(1, 8 MB / size).

- sorted: 198 buffers, 198 fully backed by huge pages; ascending adjacency over the first 2048 / 4096 / all pages 0.999-0.999 / 0.998-0.998 / 0.998-0.998
- head8: 198 buffers, 198 fully backed by huge pages; ascending adjacency over the first 2048 / 4096 / all pages 0.000-0.001 / 0.499-0.500 / 0.877-0.877
- shuffled8: 198 buffers, 198 fully backed by huge pages; ascending adjacency over the first 2048 / 4096 / all pages 0.000-0.001 / 0.001-0.001 / 0.000-0.001

stride 128:

| size | sorted | head8 | shuffled8 | head8 / sorted | shuffled8 / sorted | linear |
|---:|---|---|---|---:|---:|---:|
| 4 MB | 4.46 (4.46-4.46) | 4.49 (4.49-4.52) | 4.50 (4.48-4.54) | 1.007 | 1.009 | 1.009 |
| 6 MB | 6.45 (6.41-6.48) | 7.08 (7.01-7.09) | 7.02 (6.96-7.08) | 1.096 | 1.088 | 1.088 |
| 8 MB | 8.01 (8.00-8.02) | 9.69 (9.67-9.72) | 9.70 (9.68-9.70) | 1.210 | 1.210 | 1.210 |
| 12 MB | 8.14 (8.11-8.16) | 9.42 (9.42-9.46) | 10.06 (10.06-10.08) | 1.157 | 1.235 | 1.157 |
| 16 MB | 8.12 (8.07-8.15) | 9.07 (9.06-9.12) | 10.08 (10.05-10.15) | 1.117 | 1.242 | 1.121 |
| 24 MB | 8.10 (8.06-8.15) | 8.74 (8.68-8.81) | 10.05 (10.04-10.13) | 1.080 | 1.242 | 1.081 |
| 32 MB | 8.05 (7.92-8.09) | 8.53 (8.48-8.63) | 10.05 (10.03-10.12) | 1.059 | 1.247 | 1.062 |
| 48 MB | 8.05 (7.92-8.11) | 8.45 (8.34-8.47) | 10.02 (9.98-10.13) | 1.049 | 1.244 | 1.041 |
| 64 MB | 8.05 (7.91-8.11) | 8.36 (8.27-8.37) | 10.01 (9.96-10.08) | 1.037 | 1.242 | 1.030 |

stride 256:

| size | sorted | head8 | shuffled8 | head8 / sorted | shuffled8 / sorted | linear |
|---:|---|---|---|---:|---:|---:|
| 4 MB | 4.83 (4.83-4.83) | 4.86 (4.85-4.87) | 4.84 (4.84-4.90) | 1.006 | 1.003 | 1.003 |
| 6 MB | 6.80 (6.79-6.81) | 7.27 (7.26-7.33) | 7.26 (7.25-7.36) | 1.069 | 1.068 | 1.068 |
| 8 MB | 8.84 (8.83-8.87) | 10.63 (10.62-10.64) | 10.59 (10.58-10.67) | 1.203 | 1.198 | 1.198 |
| 12 MB | 8.95 (8.94-9.04) | 10.63 (10.63-10.66) | 11.48 (11.41-11.53) | 1.188 | 1.282 | 1.188 |
| 16 MB | 8.81 (8.79-8.93) | 10.21 (10.18-10.27) | 11.58 (11.50-11.65) | 1.159 | 1.314 | 1.157 |
| 24 MB | 8.68 (8.64-8.81) | 9.73 (9.71-9.78) | 11.61 (11.46-11.69) | 1.122 | 1.338 | 1.113 |
| 32 MB | 8.61 (8.58-8.76) | 9.47 (9.44-9.54) | 11.50 (11.49-11.69) | 1.100 | 1.336 | 1.084 |
| 48 MB | 8.57 (8.53-8.74) | 9.24 (9.19-9.29) | 11.51 (11.50-11.76) | 1.079 | 1.343 | 1.057 |
| 64 MB | 8.50 (8.48-8.71) | 9.08 (9.07-9.19) | 11.51 (11.49-11.76) | 1.068 | 1.354 | 1.044 |

## Exp G5: lmbench's own lat_mem_rd under three interconnect governors, with NoC samples and buffer layouts

run33-noc-lmbench-frames.sh, N80, protected, run by the user (the governor change needs the user).  max = performance (1800 MHz), ondemand = simple_ondemand, min = powersave.  For every data point: the NoC samples (every 100 ms) between the previous output line and this one, i.e. while that child ran; adj = ascending + descending adjacency of the child's buffer (lmb-frames.py).

- max: samples 1800 MHz: 2203
- ondemand: samples 1800 MHz: 552, 1450 MHz: 21, 1300 MHz: 11, 1200 MHz: 69, 1000 MHz: 38, 950 MHz: 39, 900 MHz: 573, 650 MHz: 47, 600 MHz: 7693
- min: samples 600 MHz: 2274

### Sequential, stride 256: ns per access, median (min-max) [n]

| size | max | ondemand | min | ondemand / max | min / max |
|---:|---|---|---|---:|---:|
| 2 MB | 4.47 (4.46-4.52) [4] | 4.47 (4.45-4.74) [13] | 4.47 (4.47-4.65) [4] | 1.000 | 0.999 |
| 4 MB | 4.85 (4.84-4.90) [4] | 5.62 (5.58-5.65) [13] | 5.61 (5.60-5.63) [4] | 1.159 | 1.157 |
| 6 MB | 6.99 (6.89-7.60) [4] | 8.75 (8.69-9.20) [13] | 8.82 (8.67-9.37) [4] | 1.253 | 1.262 |
| 8 MB | 9.92 (9.08-10.09) [4] | 12.00 (10.29-12.64) [13] | 12.70 (12.66-12.74) [4] | 1.210 | 1.280 |
| 12 MB | 10.68 (9.57-11.07) [4] | 11.05 (10.21-13.42) [13] | 13.43 (13.38-13.55) [4] | 1.035 | 1.258 |
| 16 MB | 10.62 (9.60-11.27) [4] | 10.80 (10.09-12.05) [13] | 13.65 (13.56-13.74) [4] | 1.017 | 1.286 |
| 24 MB | 10.34 (9.48-10.90) [4] | 10.52 (10.14-11.33) [13] | 13.22 (12.91-13.37) [4] | 1.018 | 1.279 |
| 32 MB | 10.17 (9.15-10.61) [4] | 10.38 (9.92-11.51) [13] | 13.06 (12.93-13.18) [4] | 1.021 | 1.284 |
| 64 MB | 9.88 (9.15-10.20) [4] | 10.03 (9.82-10.24) [13] | 12.33 (12.25-12.68) [4] | 1.015 | 1.248 |

### Random (-t): ns per access, median (min-max) [n]

| size | max | ondemand | min | ondemand / max | min / max |
|---:|---|---|---|---:|---:|
| 2 MB | 20.70 (20.70-20.70) [1] | 23.08 (21.64-24.51) [2] | 20.57 (20.57-20.57) [1] | 1.115 | 0.994 |
| 4 MB | 33.83 (33.83-33.83) [1] | 55.22 (53.62-56.81) [2] | 54.63 (54.63-54.63) [1] | 1.632 | 1.615 |
| 6 MB | 60.40 (60.40-60.40) [1] | 96.39 (95.35-97.44) [2] | 95.21 (95.21-95.21) [1] | 1.596 | 1.576 |
| 8 MB | 100.93 (100.93-100.93) [1] | 138.69 (137.81-139.56) [2] | 139.06 (139.06-139.06) [1] | 1.374 | 1.378 |
| 12 MB | 130.22 (130.22-130.22) [1] | 167.95 (167.70-168.20) [2] | 170.05 (170.05-170.05) [1] | 1.290 | 1.306 |
| 16 MB | 140.75 (140.75-140.75) [1] | 179.30 (178.61-180.00) [2] | 180.08 (180.08-180.08) [1] | 1.274 | 1.279 |
| 24 MB | 146.96 (146.96-146.96) [1] | 184.57 (184.00-185.15) [2] | 185.74 (185.74-185.74) [1] | 1.256 | 1.264 |
| 32 MB | 148.86 (148.86-148.86) [1] | 190.30 (189.73-190.88) [2] | 190.52 (190.52-190.52) [1] | 1.278 | 1.280 |
| 64 MB | 150.86 (150.86-150.86) [1] | 190.71 (190.56-190.86) [2] | 192.40 (192.40-192.40) [1] | 1.264 | 1.275 |

### Every 8 MB stride-256 point: value, NoC during the child, buffer adjacency

| state | sweep | ns | NoC samples during the child (MHz) | share at 1800 MHz | adjacency |
|---|---:|---:|---|---:|---:|
| max | 1 | 10.09 | 1800x12 | 1.00 | 0.3023 |
| max | 2 | 9.95 | 1800x12 | 1.00 | 0.2959 |
| max | 3 | 9.08 | 1800x13 | 1.00 | 0.9179999999999999 |
| max | 4 | 9.90 | 1800x13 | 1.00 | 0.4165 |
| ondemand | 1 | 10.29 | 1800x3, 600x10 | 0.23 | 0.1543 |
| ondemand | 2 | 10.54 | 1800x2, 600x11 | 0.15 | 0.19970000000000002 |
| ondemand | 3 | 10.42 | 1800x3, 600x8 | 0.27 | 0.1289 |
| ondemand | 4 | 12.64 | 600x12 | 0.00 | 0.1299 |
| ondemand | 5 | 12.51 | 600x11 | 0.00 | 0.25830000000000003 |
| ondemand | 6 | 12.00 | 1800x1, 600x11 | 0.08 | 0.3262 |
| ondemand | 7 | 12.62 | 600x13 | 0.00 | 0.2315 |
| ondemand | 8 | 12.62 | 600x12 | 0.00 | 0.1597 |
| ondemand | 9 | 12.63 | 600x11 | 0.00 | 0.1978 |
| ondemand | 10 | 10.47 | 1800x1, 600x12 | 0.08 | 0.209 |
| ondemand | 11 | 12.62 | 600x12 | 0.00 | 0.209 |
| ondemand | 12 | 10.71 | 600x12 | 0.00 | 0.7095 |
| ondemand | full command | 10.43 | 1800x1, 600x12 | 0.08 | 0.4155 |
| min | 1 | 12.71 | 600x11 | 0.00 | 0.0801 |
| min | 2 | 12.74 | 600x11 | 0.00 | 0.0845 |
| min | 3 | 12.69 | 600x11 | 0.00 | 0.0742 |
| min | 4 | 12.66 | 600x12 | 0.00 | 0.147 |

### The paper's full command under ondemand (one run): 8 MB point per stride and the NoC samples while that child ran

| stride | 4 MB | 6 MB | 8 MB | 12 MB | 8 MB: NoC samples (H = 1800 MHz, m = 650-1450 MHz, . = 600 MHz) |
|---:|---:|---:|---:|---:|---|
| 16 | 2.18 | 2.18 | 2.19 | 2.20 | `.HHmmHH.....` |
| 32 | 2.38 | 2.57 | 2.55 | 2.59 | `...HHmmHmmmm` |
| 64 | 2.77 | 4.23 | 3.97 | 4.05 | `.HmmmHHHHmHH` |
| 128 | 5.22 | 8.42 | 10.37 | 9.78 | `.......H....` |
| 256 | 5.62 | 8.90 | 10.43 | 11.43 | `....H........` |
| 512 | 5.33 | 8.24 | 10.06 | 9.52 | `.....H.......` |
| 1024 | 5.58 | 9.21 | 11.29 | 11.05 | `.........H..` |

### Side by side with the N90 host data of June (medians; N90 quiesced = kvmoff, nvhe, vhe pooled; N90 non-quiesced = the nVHE 'fast state' boot)

| test | size | N80 max | N80 ondemand | N80 min | N90 non-quiesced | N90 quiesced | N80 ondemand / max | N90 quiesced / non-quiesced |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| sequential 256 | 4 MB | 4.85 | 5.62 | 5.61 | 5.07 | 5.48 | 1.159 | 1.081 |
| sequential 256 | 6 MB | 6.99 | 8.75 | 8.82 | 7.46 | 8.26 | 1.252 | 1.107 |
| sequential 256 | 8 MB | 9.92 | 12.26 | 12.70 | 10.32 | 11.97 | 1.235 | 1.160 |
| sequential 256 | 12 MB | 10.68 | 11.02 | 13.43 | 11.34 | 11.09 | 1.032 | 0.978 |
| sequential 256 | 16 MB | 10.62 | 10.85 | 13.65 | 11.47 | 11.08 | 1.022 | 0.966 |
| sequential 256 | 64 MB | 9.88 | 10.03 | 12.33 | 11.11 | 10.46 | 1.015 | 0.941 |
| random | 4 MB | 33.83 | 55.22 | 54.63 | 30.80 | 47.63 | 1.632 | 1.546 |
| random | 6 MB | 60.40 | 96.39 | 95.21 | 48.61 | 67.32 | 1.596 | 1.385 |
| random | 8 MB | 100.93 | 138.69 | 139.06 | 83.90 | 112.52 | 1.374 | 1.341 |
| random | 12 MB | 130.22 | 167.95 | 170.05 | 121.82 | 154.66 | 1.290 | 1.270 |
| random | 16 MB | 140.75 | 179.30 | 180.08 | 134.23 | 168.63 | 1.274 | 1.256 |
| random | 64 MB | 150.86 | 190.71 | 192.40 | 150.12 | 185.30 | 1.264 | 1.234 |

For the sequential 8 MB point the quiesced N90 median mixes its two levels (about 10.3 and 12.4 ns); the N80 ondemand values are listed above.

### ondemand, stride 256: value relative to the max-state median of the same size, against the share of NoC samples at 1800 MHz

| size | points | Spearman (value, share at 1800) | median ratio when share >= 0.9 | when share < 0.5 |
|---:|---:|---:|---:|---:|
| 4 MB | 13 | nan |  | 1.159 (13) |
| 6 MB | 13 | nan |  | 1.253 (13) |
| 8 MB | 13 | -0.83 |  | 1.210 (13) |
| 12 MB | 13 | -0.51 |  | 1.035 (13) |
| 16 MB | 13 | -0.56 |  | 1.017 (12) |
| 24 MB | 13 | -0.18 |  | 1.017 (12) |
| 32 MB | 13 | -0.47 |  | 1.022 (12) |
| 64 MB | 13 | -0.25 |  | 1.015 (9) |

## Two-factor check: is the N90 non-quiesced run 'scattered pages on a faster platform'?

Per stride and size: low = median of the low level of the four quiesced N90 host boots (40 values, values more than 12% above the median of the lower half left out); fast-state = median of the ten iterations of the non-quiesced nVHE boot; layout ratio = shuffled / sorted with lmbench's own program on the N80 (H4, H5).  If the buffers of the non-quiesced run were physically scattered and those of the low level physically contiguous, then (fast-state / low) / (layout ratio) is what the platform state alone does.

### N90: fast-state / low

| stride | 3 MB | 4 MB | 6 MB | 8 MB | 12 MB | 16 MB | 24 MB | 32 MB | 48 MB | 64 MB |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 64 | 0.997 | 0.992 | 0.890 | 1.023 | 1.050 | 1.068 | 1.072 | 1.063 | 1.068 | 1.068 |
| 128 | 0.925 | 0.907 | 0.891 | 1.010 | 1.030 | 1.047 | 1.048 | 1.048 | 1.073 | 1.084 |
| 256 | 0.925 | 0.925 | 0.901 | 1.000 | 1.023 | 1.035 | 1.027 | 1.035 | 1.040 | 1.064 |
| 512 | 0.991 | 0.983 | 0.949 | 1.030 | 1.073 | 1.070 | 1.093 | 1.080 | 1.089 | 1.093 |
| 1024 | 1.155 | 1.140 | 1.020 | 1.011 | 1.053 | 1.061 | 1.096 | 1.094 | 1.105 | 1.103 |

### N80: layout ratio (shuffled / sorted)

| stride | 3 MB | 4 MB | 6 MB | 8 MB | 12 MB | 16 MB | 24 MB | 32 MB | 48 MB | 64 MB |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 64 | 1.001 | 1.004 | 1.106 | 1.230 | 1.239 | 1.240 | 1.238 | 1.236 | 1.225 | 1.223 |
| 128 | 1.004 | 1.004 | 1.070 | 1.202 | 1.228 | 1.230 | 1.232 | 1.232 | 1.228 | 1.232 |
| 256 | 1.007 | 1.007 | 1.066 | 1.193 | 1.256 | 1.280 | 1.298 | 1.326 | 1.310 | 1.305 |
| 512 | 1.081 | 1.083 | 1.140 | 1.207 | 1.260 | 1.264 | 1.257 | 1.255 | 1.249 | 1.249 |
| 1024 | 1.202 | 1.227 | 1.213 | 1.169 | 1.259 | 1.265 | 1.255 | 1.257 | 1.252 | 1.242 |

### quotient of the two

| stride | 3 MB | 4 MB | 6 MB | 8 MB | 12 MB | 16 MB | 24 MB | 32 MB | 48 MB | 64 MB |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 64 | 0.995 | 0.988 | 0.805 | 0.832 | 0.847 | 0.862 | 0.866 | 0.860 | 0.872 | 0.874 |
| 128 | 0.920 | 0.903 | 0.833 | 0.840 | 0.838 | 0.851 | 0.850 | 0.851 | 0.874 | 0.880 |
| 256 | 0.919 | 0.918 | 0.845 | 0.838 | 0.815 | 0.808 | 0.791 | 0.780 | 0.793 | 0.816 |
| 512 | 0.916 | 0.907 | 0.833 | 0.853 | 0.852 | 0.846 | 0.870 | 0.861 | 0.872 | 0.875 |
| 1024 | 0.960 | 0.929 | 0.841 | 0.865 | 0.836 | 0.839 | 0.874 | 0.870 | 0.883 | 0.887 |

From 6 MB upward (40 cells): fast-state / low ranges over 0.890-1.105 (median 1.051, coefficient of variation 5.1%); the quotient ranges over 0.780-0.887 (median 0.850, coefficient of variation 3.1%).

