# 核查报告：audit:night-code

## Summary

I audited the code and run scripts used for the night's experiments. Files checked: probe3.c, frames2.c (including a diff against 166d6ec2), thplayout.c, layoutshim.c, lmb-frames.py, bgload.c, nothp.c, run14 to run32, the lmbench sources (lib_mem.c, lat_mem_rd.c, lib_timing.c), and mm/mremap.c, mm/huge_memory.c, arch/arm64 contpte and mm/page_alloc.c at tags 6.6.0-79.93 and 6.6.0-73.76. I found no defect that invalidates a claim in night2.json, night3.json or worklog 11.18-11.32. Several defects weaken parts of them.

**What the code does correctly**
- **probe3 tlb chain.** The chain is a single cycle of npages x L lines and never takes two hops in a row on the same page. I checked this by simulation (chain_sim.py) for all six configurations.
- **l2over index.** It computes the set as ((pfn<<6)+line)&1023, which is the right index (PA bits 15:6) for a 512 KiB, 8-way, 64 B-line L2 without set hashing.
- **frames2 refactor.** The non-mix path (run_set) does the same thing as the code at 166d6ec2.
- **mremap keeps the frames.** Moving a 4 KiB page out of a PMD-mapped THP splits the PMD into PTEs that point at the same frames (mremap.c:669-690, huge_memory.c:2729-2764 at 6.6.0-79.93). No page is copied.
- **The one-page offset prevents contpte folding.** The fold test (pgtable.h:1454-1475) needs the address and the pfn both to end a 16-page block. With the offset that is never true at once, and contpte.c:118 also requires one large folio.
- **Re-collapse is prevented by MADV_NOHUGEPAGE, not by the offset.** That flag is set only after the moves, so for a short window the moved VMAs still carry VM_HUGEPAGE from the pool. The data give no sign that khugepaged used that window.
- **The shim replaces exactly lmbench's timed buffer.** It catches the one malloc of 64 MB + 8 KiB that each forked child makes in base_initialize. It returns a page-aligned pointer at 2 MiB + 4 KiB, so lmbench's base equals that pointer. The 8 MB working set is therefore exactly the first 8 MB chunk (checked with shimtest.c on this workstation).
- **What else differs between sorted, head8 and shuffled8:**
  - VMA count: 1, about 2,000 and about 16,900 (shimtest2.c). This is software-only; there are no faults in the timed loop.
  - Page-table pages: same number and the same virtual coverage.
  - Frames: within an 8 MB chunk the same set of frames, so the same cache-colour distribution.
  - Host stage-2 class: THP frames can never lie in VM-shared 2 MiB regions, but the "natural" buffers can.
- **lmb-frames.py reads the right child at the right time.** All 33 children of every sweep were captured. Its page counts include lmbench's malloc header page (8 MB gives 2049 pages).

**Defects that weaken claims**
- **2048 x 2 is not translation-only.** It has 0.06-0.08 L2 refills per hop in both touch orders, because 4,096 lines in 1,024 sets overflow some sets even with random frames.
- **The chain-order versus ascending comparison (N4) is confounded.** The run order is fixed, and the two orders got different frames (1024 x 2: 90 against 269 distinct 2 MiB regions). probe3 also records no frame adjacency in tlb mode.
- **The N2 slot share moves with repetition order.** r(rep, share) = -0.82, so time and amount held back cannot be separated from share.
- **H6 sorted against shuffled cannot show an order effect.** lmbench -t builds its random page permutation over the whole 64 MB before the malloc, so both layouts are visited in random order anyway.
- **Every workstation measurement ran on a loaded machine.** Load average was 5.1-7.5 on 8 cores, with the ondemand governor.
- **Worklog 11.23, line 1213, states the stride order wrongly.** It says stride 64 runs first. In the June N90 raw reports the order is 16, 32, 64, so two full sweeps with 64 MB children come before stride 64's 8 MB point.

I reproduced these numbers: the medians of nn#1 and nn#4, the N3 slope and its region counts, the H8 ratios in nh#1, and the H7 frame reuse (2033-2034 of 2049).

## Defects

- **weakens** | experiments/memlat-probe/probe3.c:219-233 (tlb chain: line (37k+17j) mod 64, first touch in chain order) and run18/run21 configs: Even with random frames, configurations with 4096 data lines (2048 x 2, 4096 x 1, 1024 x 4) overflow some of the 1024 eight-way L2 sets (Poisson mean 4 per set). My simulation (chain_sim.py) gives an l2over of 0.037-0.050 for random frames, against 0.000 for 2048 x 1. Measured on the N80: Exp N 2048 x 2 has 0.056-0.073 L2 refills per hop and 4096 x 1 has 0.075-0.153 (expN-n80.log). N4 with ascending first touch still has 0.059-0.083 (2048 x 2) and 0.066-0.100 (4096 x 1) refills, and 1024 x 4 has 0.008-0.039. Only 2048 x 1 is clean (0.001-0.011). Effect: The N80-minus-workstation differences for 2048 x 2 (+14.7 in nn#1, +13.41 in nn#4) and 4096 x 1 (+14.6, +14.18) include L2-miss cycles on the N80, which cost a different number of cycles on the workstation (2.5 against 1.9 GHz). nn#1 does not say that 2048 x 2 has refills. The 2048 x 1 numbers that nn#6 relies on are unaffected.
- **weakens** | run21-prefault.sh:42-48 (pf=0 always before pf=1 in each repetition); probe3.c:375 (contig_frac computed only when !rnd && !tlbm): The chain-order versus ascending-first-touch comparison is confounded with a fixed run order and with the frames each run got. In expN4-n80.log the median number of distinct 2 MiB regions is 90 against 269 (1024 x 2), 343 against 375 (2048 x 1) and 384 against 421 (2048 x 2). In tlb mode probe3 does not record whether virtually adjacent pages are physically adjacent, so hardware coalescing of contiguous translations cannot be checked. Effect: nn#4(b) (2048 x 1 lower by 1.6 cycles, walks 0.956 against 0.916 after ascending touch) cannot be attributed to the touch order. Alternatives that cannot be excluded: different frame sources caused by the fixed order, and TLB coalescing of pages that are adjacent both virtually and physically after ascending touch. The analyst's 'cause unknown' stands, and the comparison should not be read as an effect of touch order.
- **cosmetic** | run19-slot-mix.sh:13-24 (Exp N2): Hold size, seed and repetition number move together, and residency is not checked (sleep 2, then SIGSTOP). In expN2.log at 2048 x 1, r(rep, share) = -0.82, r(rep, cycles) = -0.79 and r(share, regions) = +0.84. The share is high only in repetitions 1-4. Effect: The share-to-cycles correlation of +0.98 in nn#2 is also an order/time correlation. nn#2 and the later sections already treat it as non-causal and rely on N3, which is controlled. No conclusion changes.
- **weakens** | run29-lmbench-layout-random.sh with layoutshim.c; src/lib_mem.c:146,152,254-270: lat_mem_rd -t takes its page list as a random permutation over all maxlen pages, computed before the malloc, and moves to another page on every load. Sorted and shuffled shim buffers are therefore both visited in random physical order; the comparison is in effect a change of random seed. Effect: In nn#15, 'the physical order of the pages does not move lmbench's random-access figures' is true by construction and is not evidence from H6. What H6 measures is huge-page-pool frames against normally allocated frames: 0-4 percent, and 13 percent at 6 MB. The worklog's correction table (line 46) already says this, but night2.json nn#15 still uses the old wording. nh#4's statement that frame order cannot cause the random-access fast state holds by the access pattern, not by H6. Conclusion unchanged; the wording should change.
- **cosmetic** | layoutshim.c:126-193 (THP pool) against natural runs under nothp (run27, run29): The shim's frames are whole free 2 MiB blocks, so they can never lie in 2 MiB regions shared with the protected VM (host stage-2 with 4 KiB leaves). Natural lmbench buffers can lie there. Shim against natural therefore differs in host stage-2 class mix as well as in layout. Effect: There is only a small effect on the stride-256 sequential comparisons (one walk per 16 accesses), so the statement that natural runs sit at the shuffled level is not affected. The 'natural / sorted' readings in random access (H6: 1.134 at 6 MB), where every access walks, may partly reflect this. Comparisons between shim layouts (sorted, head8, shuffled8) are unaffected.
- **cosmetic** | layoutshim.c:178-185 (one VMA per moved page unless pgoffs are consecutive): Besides frame order, the layouts differ in VMA count: sorted 1, head8 about 2,047 and shuffled8 about 16,889 VMAs over the buffer. I confirmed this with shimtest2.c on the workstation (kernel 7.0); the mremap/copy_vma merge rule is the same at 6.6. lmb-frames.py also cannot find a shuffled shim buffer, because no single mapping is at least 60 MB (not used there). Effect: There are no page faults or VMA lookups in lmbench's timed loop: the pages are present and writable, and the chain is rewritten on present pages. The page-table pages (same count and coverage) and the per-8 MB frame sets are equal. No effect on nn#13, nn#14 or nh#1 is expected.
- **weakens** | results/memlat-d80f3-20260930/*.log (all workstation runs): Every workstation run started and ended with a load average of 5.10-7.47 on 8 cores, with governor=ondemand (for example expH4-d80f3.log '## start ... loadavg=5.79'; expN-d80f3.log 5.31-6.83). The workstation is shared, its 8 MiB L3 and DRAM are shared, and cpu0 is not isolated. Effect: Workstation latencies near the L3 boundary (4-12 MB) and their run-to-run scatter are contaminated by other jobs. This weakens the quantitative workstation statements: nn#7 (8 MB scatter of 10-20 percent), nn#8 ('about a third' and '8 MB unstable'), nn#13 (workstation ratios), nn#14 ('a different pattern' at 8 MB) and nn#17(c) as a size comparison. That a layout effect exists without a host stage-2 at 16 MB survives, because the ranges do not overlap. The tlb-mode results (nn#1, nn#4, nn#6) are less affected: the data sit in private L1/L2, ns_min is used, and cyc_est in the no-walk configurations matches the N80's counted cycles (13.96-14.58 against 13.99-14.60).
- **weakens** | docs/memlat/memlat-investigation-worklog.zh-CN.md:1213 (section 11.23): The worklog says that in one lmbench run stride 64 comes first, so that no child with a buffer over 8 MB has run before its 8 MB point. The June N90 raw reports run strides 16, 32, 64, ... (n90-kvmoff-noLSM-full-cpu0-iter1.txt: 'stride=16' line 552, 'stride=32' line 587, 'stride=64' line 622). Two full sweeps with 64 MB children therefore come before stride 64's 8 MB point. This is not in the worklog's correction table. Effect: The argument in 11.23 that removed 'stride 64 rarely shows the high level' as a point against E2 fails. That point against E2 is restored, which is consistent with nn#17's and nh#4's later listing of the stride dependence as unexplained by layout. nn#17 and nh#4 do not rely on the false sentence.
- **weakens** | frames2 slot classes 0x8b/0x8c ('can still be 1 GiB blocks') used in run20/run22, nn#3, nn#5, nn#6: The host stage-2 granularity of the slots was never read; it is inferred from where no VM pages lie. guest-regions-n3/z/n5.txt hold VM regions in 0x82-0x8a and none in 0x8b or 0x8c. The measured direction (candidate slots cost 3.6 cycles more per hop than 2 MiB-block slots) is not what one would naively expect of 1 GiB blocks, and no code reads stage-2 descriptors. Effect: The slot difference in N3 is measured and linear: I reproduced the slope, and region count does not drive it (mb2 86→156→175→110 across 0-100 percent, while cycles rise monotonically). The labels '1 GiB block' and '2 MiB block' in nn#3, nn#5 and nn#6 are inferences and should be worded as 'slots without VM pages' and 'slots with VM pages'.
- **cosmetic** | lmb-frames.py:68-86 (longest present stretch): The stretch starts with glibc's malloc chunk-header page, one page below lmbench's base. Page counts are therefore n+1 (8 MB gives 2049) and the first frame is not part of the timed buffer. Effect: One adjacency pair in about 2,048, negligible. It explains the '2049 frames' in nn#11 and nh#3. H7 frame reuse is reproduced either way (12 MB child holds 2033-2034 of the 8 MB child's frames in 4 of 4 sweeps; the header frame is the same).
- **cosmetic** | thplayout.c:16-22, layoutshim.c:11-15, 185/259 (madvise after the moves): The header comment still says contpte exists only from 6.9 on. Re-collapse is prevented by MADV_NOHUGEPAGE alone, which is applied only after the move loop, while the moved VMAs inherit VM_HUGEPAGE from the pool. The pool's own range is transiently contpte-folded when its PMD is split (set_pte_at in __split_huge_pmd_locked) and unfolded when each PTE is moved. Effect: Frames are kept and the destination is never folded. Sorted shows 0.0625 walks per access (one per page) at 32 and 64 MB in expL2-n80.log; aligned shows 0. No collapse is visible. nn#9(b) holds; only the code comment is wrong.
- **cosmetic** | run25/26/27/28/29/31/32 (stamp() helper; traps): The output-timestamping loop (one fork of date per line), the awk/cat state reads and the watcher's /proc polling are not pinned away from the benchmark CPU (the watcher is pinned to cpu6). The traps kill only the watcher, not a stopped bgload, if a script is interrupted. Effect: meta.log and the per-log '## start'/'## done' lines show every run completing, and the N80 load average stayed at about 1. H2 (no watcher) and H3 (watcher) give the same 8 MB values (10.04-10.46 against 10.14-10.44). No effect.
- **weakens** | wf1-results/night3.json nh#3 (transfer of H7 to the N90): Frame hand-back from the 8 MB child to the 12 MB child is measured only on the N80. That machine ran in protected mode with a VM running, system THP 'always', and a per-CPU high of about 1,600. The N90 runs were under THP 'never'. Also, H8's head8 models the remaining 4 MB as sorted, whereas under E2 they would come from the same scattered source. Effect: head8 is a lower bound for the 12 MB reading under E2, which makes nh#3's expectation (about 1.16-1.19 or more) conservative. The open alternative is the one nh#3 itself names: the N90 allocator may not have handed the frames back. The inference is supported on the N80 but not shown for the N90.

## Discrepancies

- nn#13: 'adjacency of the first 2048 pages ... at most 0.001 for both shuffled layouts'. In expH4-shim.log each direction is at most 0.0010, but 33 shuffled8 buffers have adj2048=0.0010/0.0010, so ascending plus descending is 0.0020 (cosmetic).
- nn#13 still says shuffled8's 'first 8 MB use the same frames as sorted'. Each lat_mem_rd child builds its own pool, so sorted and shuffled8 runs use the same method of picking frames (the first four 2 MiB pages of the process's pool), not the same frames. The worklog correction table line 52 says this; night2.json does not.
- nn#1 lists 2048 x 2 (+14.7) among the translation-dominated configurations without saying that expN-n80.log shows 0.056-0.073 L2 refills per hop there. It mentions refills only for 4096 x 1 and 2048 x 1.
- nn#15: 'the physical order of the pages does not move lmbench's random-access figures'. lmbench -t randomises page order over the whole 64 MB before the malloc, so H6 could not have shown an order effect. The worklog corrected this (line 46); night2.json nn#15 was not updated.
- Worklog 11.23 line 1213: 'lmbench 一次运行里步长 64 排在最前面' is contradicted by the June N90 raw reports (stride order 16, 32, 64, 128, 256, 512, 1024).
- The thplayout.c header comment ('contiguous-PTE support (6.9 and later)') contradicts the N80 kernel (CONFIG_ARM64_CONTPTE=y, contpte.c present at both 6.6 tags). nn#9 acknowledges this, but the source comment was not corrected.

## Threats to validity

- Host stage-2 granularity on the N80 was never read out. Every class label (1 GiB candidate, 2 MiB block, 4 KiB in VM-shared regions) is inferred from VM page locations; only the per-slot cycle differences are measured.
- The L2 set index assumes PA[15:6] with no hashing. The 0.999 correlation of l2over with L2 refills in N4 supports it, but the L2 replacement policy and the space taken by page-table and code lines are not modelled, hence refills exceed l2over by 0.03-0.05.
- In tlb mode probe3 records no frame adjacency, so hardware TLB coalescing of runs that are contiguous both virtually and physically cannot be excluded for the chain-order versus ascending difference.
- cyc_est assumes a 4-cycle L1 load-to-use latency and a core clock that stays constant between the main measurement and the L1 reference. This is verified against counted cycles only on the N80; the workstation used the ondemand governor under a load average of about 6.
- All workstation runs shared the machine with other jobs (load average 5.1-7.5), so L3-boundary results there are noisy and may be biased.
- Repetition order is fixed in every script (chain before ascending; sorted, then shuffled8, then shuffled, then natural; sorted, then head8, then shuffled8). This matters only for small differences such as the 1.6-cycle effect in N4.
- Shim layouts use one fixed permutation per repetition (SHIM_SEED=rep), so all children of a sweep share the same virtual order; only 2-4 permutations were tested per experiment.
- binaries-n80.txt predates thplayout.c and layoutshim.c, so no checksum ties the device binaries to the repository sources; the log formats match the sources.
- The N80 ran a desktop session and an idle protected VM throughout. lmb-frames.py polled /proc from cpu6 during H3 and H7, and the stamp helper was unpinned (H2 against H3 shows no visible effect).

## Recomputed tables

Exp N medians (expN-n80.log, 5 processes; expN-d80f3.log, 20 processes). "N80 est" is cyc_est; "N80 counted" is ev11; "WS est" is the workstation's cyc_est.

| pages x lines | N80 est | N80 counted | WS est | N80 est - WS | N80 walks/hop | N80 L2 refills/hop |
|---|---|---|---|---|---|---|
| 256 x 16 | 14.37 | 14.38 | 14.53 | -0.2 | 0.000 | 0.010-0.016 |
| 512 x 8 | 14.47 | 14.58 | 14.49 | 0.0 | 0.000 | 0.006-0.030 |
| 1024 x 4 | 14.54 | 14.57 | 14.58 | 0.0 | 0.000 | 0.011-0.029 |
| 2048 x 1 | 39.39 | 39.68 | 24.96 | +14.4 | 0.959 | 0.002-0.004 |
| 2048 x 2 | 40.52 | 40.75 | 25.86 | +14.7 | 0.944 | **0.056-0.073** |
| 4096 x 1 | 42.55 | 42.61 | 27.99 | +14.6 | 1.001 | 0.075-0.153 |

N4 on the N80 (expN4-n80.log, 8 repetitions; pf = TLB_PREFAULT; mb2 = distinct 2 MiB regions):

| config, pf | l2over | L2 refills/hop | cycles (median) | walks/hop (median) | mb2 (median) |
|---|---|---|---|---|---|
| 1024x2, 0 / 1 | 0-0.076 / 0-0.005 | 0-0.044 / 0-0.003 | 13.99 / 13.96 | 0 / 0 | 90.5 / 269 |
| 2048x1, 0 / 1 | 0-0.009 / 0 | 0.001-0.011 / 0.001-0.006 | 39.85 / 38.25 | 0.956 / 0.916 | 343 / 374.5 |
| 2048x2, 0 / 1 | 0.028-0.066 / 0.036-0.058 | 0.051-0.079 / 0.059-0.083 | 40.63 / 39.65 | 0.934 / 0.906 | 383.5 / 421 |
| 4096x1, 0 / 1 | 0.072-0.460 / 0.022-0.056 | 0.117-0.502 / 0.066-0.100 | 50.23 / 42.41 | 0.998 / 0.993 | 517 / 525 |

N3 tlb1 at 8 MB (expN3.log; mean over 3 seeds x 2 passes):

| mix, %A | cycles | mb2 regions |
|---|---|---|
| 8b:88, 0 | 36.91 | 86-97 |
| 8b:88, 12 | 37.32 | 156-160 |
| 8b:88, 25 | 37.87 | 168-173 |
| 8b:88, 50 | 38.82 | 175-176 |
| 8b:88, 75 | 39.73 | 175-176 |
| 8b:88, 100 | 40.46 | 109-111 |
| 8b:8c, 50 | 40.46 | 187-192 |
| 88:89, 50 | 37.09 | 157-159 |

Region count rises and falls across the mix while cycles rise steadily, so region count does not drive the slope.

N2 at 2048 x 1 (expN2.log): r(rep, share) = -0.82, r(rep, cycles) = -0.79, r(share, cycles) = +0.98, r(mb2, share) = +0.84.

H8 (expH8.log, medians of 3; the noc reading is 1800000 at all 18 start and end points):

| stride, size | sorted ns | head8 ns | shuffled8 ns | head8/sorted | shuffled8/sorted | linear prediction |
|---|---|---|---|---|---|---|
| 128, 8 MB | 8.014 | 9.693 | 9.697 | 1.210 | 1.210 | 1.210 |
| 128, 12 MB | 8.143 | 9.423 | 10.059 | 1.157 | 1.235 | 1.157 |
| 128, 24 MB | 8.095 | 8.741 | 10.052 | 1.080 | 1.242 | 1.081 |
| 256, 8 MB | 8.837 | 10.632 | 10.587 | 1.203 | 1.198 | 1.198 |
| 256, 12 MB | 8.954 | 10.634 | 11.477 | 1.188 | 1.282 | 1.188 |
| 256, 24 MB | 8.676 | 9.732 | 11.610 | 1.122 | 1.338 | 1.113 |
| 256, 64 MB | 8.498 | 9.078 | 11.505 | 1.068 | 1.354 | 1.044 |

Shim logs: thp_kb=67584 in all buffers of H4, H5, H6 and H8 (H5 has 394 per layout because stride 1024 skips 512 B). head8 adjacency (ascending + descending) is 0.0005-0.0010 over the first 2048 pages, 0.499-0.500 over 4096 and 0.877 over all.

H7 (expH7-pfns.log): the 12 MB child holds 2034, 2033, 2034 and 2033 of the 8 MB child's 2049 frames (2049 includes the malloc header page).
