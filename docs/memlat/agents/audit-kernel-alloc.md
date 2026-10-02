# 核查报告：audit:kernel-alloc

## Summary

I audited the klinux kernel source at both release tags. In mm/page_alloc.c, 17 functions that decide how pages are handed out and taken back are byte-identical at 6.6.0-73.76 and 6.6.0-79.93. These include the per-CPU free-list functions (free_pcppages_bulk, rmqueue_bulk, nr_pcp_alloc, nr_pcp_high, nr_pcp_free, decay_pcp_high, zone_highsize), the buddy-allocator functions (__rmqueue_smallest, expand, __free_one_page) and the watermark setup. The other changes between the tags in that file are a lock-helper refactor, page->private=0 at free, and the removal of a redundant free_count=0. I then re-derived the claimed behaviour from those functions and tested it on the raw N80 frame dumps (expH7-pfns.log).

1. Allocation for a user page fault.
- With THP never, PR_SET_THP_DISABLE or MADV_NOHUGEPAGE, every page is order 0. thp_vma_allowable_orders returns 0 (huge_memory.c:125, huge_mm.h:315-325). This also switches off multi-size THP.
- The call path is folio_prealloc (memory.c:1055) → rmqueue_pcplist → __rmqueue_pcplist. That function takes pages from the HEAD of the movable order-0 per-CPU list (page_alloc.c:3023).
- When the list is empty, nr_pcp_alloc (2949-2997) sets the refill size. It is 63<<alloc_factor (at most 2016) and is limited to high-count-63. Each refill also raises pcp->high by that batch, up to high_max.
- rmqueue_bulk (2309-2338) then calls __rmqueue_smallest once per page (1595). That takes the smallest order first and the head of each list. expand() returns the lowest page of a split block and puts the upper halves at the heads of the lower-order lists.
- So a split block is delivered in ascending physical order and appended with list_add_tail (2333). Fresh pages therefore come in ascending physical order, and the smallest free blocks are used up first.

2. Freeing on exit.
- exit_mmap (mmap.c:3372) unmaps the VMAs in ascending virtual address (VA) order. mmu_gather batches the pages (up to about 10000; mmu_gather.c:164-203) and frees them in that order: free_pages_and_swap_cache → folios_put_refs → free_unref_folios.
- Each page is pushed onto the HEAD of the list (free_unref_page_commit, 2620). The next child therefore gets the previous child's frames in reverse VA order. In H7 this holds in all 32 hand-overs (the descending fraction is 0.83-1.00).
- Neither tag calls lru_add_drain in exit_mmap. Up to 30 just-faulted folios are therefore freed later, which matches the 15-30 top pages of each buffer that never reach the next buffer.
- When count reaches the per-CPU limit (high), clamp(free_count, 63, high-63) pages are drained from the TAIL, i.e. the oldest pages (1224). free_count counts consecutive frees: +1 per free, capped at 2016, halved on every allocation.
- In the buddy allocator, a drained page joins its free buddy (pfn^1, and so on upward) or goes to the HEAD of its order-0 list. It goes to the tail only if buddy_merge_likely holds (796-882).
- Consequence: a drained page with no buddy in the drained set (I call it unpaired) is handed out again by the next refill. A drained pair merges and is handed out only after the smaller blocks are used up.
- H7 confirms this. Of all 32 hand-overs, frames went missing in quantity in only four: 6→8 MB in sweeps 2-4 and 12→16 MB in sweep 4. There, 1082/1082, 1112/1112, 522/1066 and 514/738 of the paired frames were lost, against only 59/415, 82/385, 16/431 and 0/2295 of the unpaired ones.
- This is the missing step in the analyst's account of the 6→8 MB break. It also explains sweep 1 without needing the assumption that no drain occurred: there, all of the 6 MB child's frames were unpaired.

3. Per-CPU limit and watermarks.
- The floor of the per-CPU limit (high_min) is the zone's low watermark divided by 8 CPUs. The ceiling (high_max) is managed pages / 8 / 8.
- The decay (vmstat, about every 1 s) does high = max3(count-2016, high*7/8, high_min) and drains the excess from the tail.
- My recomputation reproduces the N80 exactly: Normal zone min/low/high 9818/12738/15658, floor 1592, ceiling 45631. min_free_kbytes is 45056 kB, i.e. 11264 pages, set by khugepaged's set_recommended_min_free_kbytes.
- Writing never to the THP setting calls start_stop_khugepaged, which recomputes int_sqrt(nr_free_buffer_pages*4*16) and the per-CPU limits.
- Estimate for a 32 GB / 8-CPU N90 with 28.3-28.5 GB visible: the floor is 1410-1525 pages (5.5-5.95 MiB) with THP never and 2105-2210 pages (8.2-8.6 MiB) with THP on. This agrees with nn#12's ~1500/~2200.
- On the N80, 1655 and 1781 are 1592 plus one or two refill increments (63, 63+126), not other floors. The limit grows on allocation refills; frees alone raise it at most to free_count+63 (2079 or less).

4. N80 evidence and the N90 inference (nh#3).
- Small children up to about 4-6 MB take the contiguous high-VA tail of the previous sweep's 64 MB child from the head of the per-CPU list; that is where the long runs come from.
- The decay empties a list of about 17,000 pages to near its floor of 1592 within about 17 ticks. The 8 MB child starts about 32 s into the sweep, so it then takes its new frames from the buddy allocator, smallest blocks first: unpaired single pages and order-1/2 blocks, i.e. runs of 2-8 pages.
- The 48-64 MB children reach large blocks, hence the longer runs.
- This undermines 11.29's refutation of 11.25. It also undermines the statement in 11.30 and section 4.3 that the scattered frames "persist on cpu0's per-CPU list" at the time of the 8 MB child. They do sit there between sweeps; the holder process cannot take them because it allocated before the sweep started and was then stopped.
- The source says that hand-back of the 8 MB child's frames to the 12 MB child is not a code invariant: it depends on the per-CPU state, and the N80 itself shows failures (6→8 MB in 3 of 4 sweeps, 12→16 MB in 1 of 4).
- However, scattered unpaired frames come back either from the per-CPU list or from the head of the buddy order-0 list. On the N80, the 8 MB child's buffers were 0.1-27% paired.
- So under E2 a scattered 8 MB buffer would be inherited by the 12 MB child. Failure in four of five N90 sweeps would require paired-but-shuffled frames, heavy competing allocation, or different tunables, none of which were recorded.
- nh#3's premise therefore holds, but for this reason, not 'same code at both tags'.

5. Contiguous-PTE folding never applies to order-0 pages. __contpte_try_fold requires the folio to cover the whole 64 KiB range (contpte.c:113-114), and contpte_try_fold also requires the VA and PFN to be aligned to the same 16-entry boundary (pgtable.h:1454-1473). The shim's pages belong to order-9 folios; the one-page offset prevents folding of the sorted layout, and the PFN check prevents it for the shuffled one. nn#9 is confirmed.

6. No kernel mechanism makes the physical order of order-0 4 KiB pages change TLB refills. Only the set of frames matters, through the host stage-2 block size in protected mode, and that set is identical for sorted and shuffled8 within each 8 MB chunk.

Two Kylin-specific mechanisms were never recorded on either machine: the kymm page pool (CONFIG_KYLIN_MM_PAGEPOOL, default y, disabled at runtime by default, not on the exit path) and the pcp_batch_override sysctl.

## Defects

- **weakens** | worklog 11.30 (first bullet of the observed facts) and conclusion doc section 4.4 (first bullet) / 4.3 part 3: The claim that 'from 2049 to 16385 pages every child contains ALL frames of the previous child, in all four runs; only 6 MB → 8 MB breaks' is refuted. In sweep 4 (expH7-pfns.log, the 4th block of 33 lines) the 16 MB child holds only 2555 of the 12 MB child's 3073 frames. Its share from the previous child is 0.62 against the size ratio 0.75, and the analyst's own table in derived/state-tables.md (sweep 4, row 4097) shows 0.62. The 514 lost frames are exactly paired frames: 514 of 738 paired frames lost, 0 of 2295 unpaired. The 'all' also needs the qualification 'except the top 15-30 pages' (permutation array and lru_add batch). Effect: Hand-over failures are not unique to 6→8 MB; they occur wherever a drain meets paired frames. This weakens the 'only 6→8 breaks' narrative. It does not undermine nh#3, because the lost frames are paired, not scattered.
- **weakens** | worklog 11.30 (correction of 11.25, last bullet) and section 4.4 ('6 MB 的子进程退出时释放的 1600 来页正好顶到收缩后的上限，内核一次把链表清掉大半，8 MB 的子进程于是要重新取页'): The mechanism is incomplete and, as stated, would not produce the break. Drained pages go to the buddy allocator. A page with no free buddy goes to the HEAD of the order-0 list (page_alloc.c:870-877, 678-693), and __rmqueue_smallest (1595) hands those back first at the next refill. Only drained pairs coalesce and are handed out later. H7 shows exactly this (my script h7f.py). At 6→8 MB, paired frames lost were 1082/1082, 1112/1112 and 522/1066, against unpaired 59/415, 82/385 and 16/431. In sweeps 2-3 every C6 frame the 8 MB child got back was unpaired (pairing fraction 0.00), while the lost ones were 93-95% paired. The break therefore needs (a) a tail drain (nr_pcp_free = clamp(free_count, 63, high-63) from list_last_entry, page_alloc.c:1224, 2531-2554), (b) buddy coalescing of drained pairs, and (c) smallest-first refill. Effect: The corrected mechanism predicts that scattered, unpaired frames survive a drain. This strengthens the premise of nh#3 (a scattered 8 MB child's frames return to the 12 MB child). It also explains sweep 1 without assuming 'no flush'.
- **weakens** | worklog 11.29 (refutation of 11.25), 11.30 ('它们留存的地方是 cpu0 的每 CPU 链表…别的核上的进程拿不走'), conclusion 4.3 part 3 last bullet: 11.29 refutes 11.25 with a pagetypeinfo snapshot taken at the START of the sweep. decay_pcp_high (page_alloc.c:2344-2372, run from vmstat_update about every second, vmstat.c:837, 1948-1959) cuts high by max(1/8, count-2016) per tick. Starting from the observed 17146/17279 (expH7.log:44), the list reaches its floor (~1592-1781) after about 17 ticks; the 8 MB child starts about 32-33 s after the sweep start (expH7.log timestamps 537.746 → 570.863). At that point the per-CPU list holds at most about 1.8 thousand pages, so most of the 1052-1707 'new' single pages must come from the buddy order-0 lists, which the decay refilled from cpu0's list. They are on cpu0's list only between sweeps, after the 64 MB child exits. The holder does not take them because it allocated before the sweep and was then stopped. This is an inference from source and timestamps; there are no intermediate per-CPU readings. Effect: 11.25's 'buddy gives the smallest free blocks first' is closer to right for the 8 MB child than the 11.29/11.30 correction. The paper conclusion is unaffected.
- **cosmetic** | worklog 11.30 ('空闲时逐步收缩到下限（N80 上读到过 1592、1655、1781），连续分配、释放时放大'), section 4.4, results README line 24: The floor is the single value high_min = low watermark / 8 = 12738/8 = 1592 (zone_highsize, page_alloc.c:5630-5677). 1655 and 1781 are 1592 plus 63 and 63+126, i.e. refill increments added in nr_pcp_alloc (2972-2973). The limit grows on allocation refills, by 63<<alloc_factor per refill (at most 2016) up to high_max = managed/64 = 45631. Frees can raise it only to free_count+63, at most 2079 (nr_pcp_high, 2593-2599). Effect: Wording only.
- **weakens** | wf1-results/night3.json nh#3 ('the same code at both kernel tags'): The code is indeed identical: 17 relevant functions are byte-identical (my comparison script), and the page_alloc.c diff between the tags is the lock helper, page->private=0 at free, and a removed redundant init. But identical code does not make the hand-back an invariant. Whether the 12 MB child gets the 8 MB child's frames depends on pcp->high when the 8 MB child exits (the floor, the refill size of that child, decay ticks), free_count, buddy pairing and competing allocations. The N80 itself shows failures (6→8 MB 3 of 4, 12→16 MB 1 of 4). The valid source argument is that unpaired, scattered frames return either from the per-CPU head or from the buddy order-0 head. Effect: nh#3's premise survives, on a different footing. Safe wording: 'By the allocator code (identical at both tags), frames of a scattered (unpaired) 8 MB buffer return to the next child either from the per-CPU list or from the head of the buddy order-0 list; on the N80 this held in 4 of 4 sweeps (2033-2034 of 2049). A failure in four of five N90 sweeps would need paired-but-shuffled frames, competing allocations on that CPU, or different allocator tunables, none of which were recorded on the N90.'
- **cosmetic** | nn#11 / worklog 11.25 inference 'a child whose buffer fits gets back, in reverse order, the frames the previous child freed': Holds (reverse order: descending-index fraction 0.83-1.00 in all 32 H7 hand-overs). 'Fits' should be 'stays below pcp->high during the exit', and pcp->high is dynamic. Even when the limit is exceeded, unpaired frames still come back via the buddy order-0 head. Effect: None beyond defect 2.
- **weakens** | all allocator explanations (11.25-11.32, 4.4, nn#11, nn#12): Several Kylin-specific mechanisms in the tree are never mentioned and their state was never recorded on either machine. (1) The kymm page pool: CONFIG_KYLIN_MM_PAGEPOOL, default y (mm/kymm/Kconfig); /proc/kymm_pool/enabled, default off; hooks free_unref_page (page_alloc.c:2679) and __free_pages_ok (1287), but not free_unref_folios, which is the exit path; allocation only in the slow path (4394). (2) The pcp_batch_override sysctl (page_alloc.c:66, 5582, 6450), which changes batch and therefore the floor, refill and drain sizes. (3) percpu_pagelist_high_fraction: 0 on the N80; if non-zero it disables auto-tuning. (4) A user-set vm.min_free_kbytes. None was recorded on the N90. Effect: Leaves the N90 per-CPU floor and the hand-back behaviour open. They are probably at defaults, but this is unverified.

## Discrepancies

- nh#3 (inference): partly-correct. The verified fact is 2033-2034 of 2049 frames of the 8 MB child in the 12 MB child in 4/4 H7 sweeps (my h7.py). The code is the same at both tags (byte-identical function bodies). But the hand-back is state-dependent, not guaranteed by the code; the N80 shows breaks at 6→8 (3/4) and 12→16 (1/4). The source supports the premise only for unpaired, scattered frames (see defect 5 for safe wording).
- Worklog 11.30 / conclusion 4.4: 'every child from 2049 to 16385 pages contains all frames of its predecessor' is refuted by sweep 4, 12→16 MB (2555/3073), which the analyst's own derived table shows (0.62 against 0.75).
- Worklog 11.30 mechanism ('drain clears most of the list, so the 8 MB child must take new pages'): partly-correct. A tail drain does occur and is consistent with nr_pcp_free. But the frames lost are the drained frames that coalesced in the buddy allocator (pairing analysis); drained unpaired frames came back.
- Worklog 11.29/11.30 'scattered frames persist on cpu0's per-CPU list at the time of the 8 MB child': not established, and contradicted by the decay arithmetic plus the expH7.log timestamps. They persist there only between sweeps.
- nn#12 / 4.4 N90 floor estimate (~1500 with THP never, ~2200 with THP on): confirmed by recomputation (1410-1525 / 2105-2210 for 28.3-28.5 GB, GB or GiB, DMA zone managed 430k-500k pages). The N80 recomputation is exact (9818/12738/15658, 1592, 45631). Unrecorded N90 tunables could change it.
- nn#9 contiguous-PTE folding: confirmed (order-0 never folded; one-page offset prevents folding for the sorted layout; PR_SET_THP_DISABLE / MADV_NOHUGEPAGE disable PMD THP and multi-size THP in the fault path).
- Disagreement with the earlier verifier verify-nn-alloc-primary: it attributes the unbroken 6→8 MB step of H7 sweep 1 to 'no flush'. All of that 6 MB child's frames were unpaired (2 paired of 1497), so a flush would also leave no trace; the data cannot distinguish the two. Its allocator model ignores buddy coalescing, which my 2x2 analysis shows decides which frames are lost.

## Threats to validity

- There are no intermediate per-CPU (count, high) readings during the N80 sweeps. The decay timeline (17k pages down to the ~1.6-1.8k floor in about 17 ticks, before the 6 MB child at about 32 s) is computed from the source and timestamps, not observed.
- The coalescing evidence uses pfn^1 membership in the previous child's buffer as a proxy for 'the buddy was also drained/free'. It does not check pageblock migratetype or buddies that were free from elsewhere. buddy_merge_likely tail placement and migratetype separation (pages in non-movable pageblocks go to other per-CPU lists) are further unmeasured routes.
- The N80 kernel's PCP_BATCH_SCALE_MAX (default 5) and the values of pcp_batch_override, kymm_pool/enabled, watermark_scale_factor, min_free_kbytes and percpu_pagelist_high_fraction on the N90 were never read. The N90 estimate assumes defaults and a DMA zone like the N80's (430-500k managed pages).
- The source shows what the allocator does on one CPU. Competing allocations on cpu0 (desktop on the N80; kworkers or interrupts on the N90) and drain_all_pages callers (compaction, reclaim, isolation) can break hand-backs and are not recorded.
- Everything about the N90 allocator state is inference. No frame numbers, per-CPU state or tunables were recorded there, so whether N90 8 MB buffers were scattered (E2) remains unmeasured.
- I ran no programs. All results come from read-only git show/diff and Python analysis of the logs; nothing was measured on this workstation.

## Recomputed tables

### 1. H7 hand-overs where frames were lost (expH7-pfns.log; previous child's buffer minus its top 40 pages; paired = pfn^1 also in that buffer)

| sweep | hand-over | paired taken | paired lost | unpaired taken | unpaired lost |
|---|---|---:|---:|---:|---:|
| 1 | 6→8 MB | 2 | 0 | 1495 | 0 |
| 2 | 6→8 MB | 0 | 1082 | 356 | 59 |
| 3 | 6→8 MB | 0 | 1112 | 303 | 82 |
| 4 | 6→8 MB | 544 | 522 | 415 | 16 |
| 4 | 12→16 MB | 224 | 514 | 2295 | 0 |
| 1-4 | 8→12 MB | 2 / 30 / 24 / 552 | 0 / 0 / 0 / 0 | 2007 / 1979 / 1985 / 1457 | 0 / 0 / 0 / 0 |

In the other 27 hand-overs at most 63 frames were lost (28 paired and 63 unpaired at most). In every hand-over the previous child's frames appear in reverse VA order (descending-index fraction 0.83-1.00).

### 2. Watermarks and per-CPU limits (zone Normal, 8 CPUs; my reimplementation of calculate_min_free_kbytes, set_recommended_min_free_kbytes, __setup_per_zone_wmarks and zone_highsize)

| machine / case | min_free_kbytes | min / low / high (pages) | per-CPU floor high_min | per-CPU ceiling high_max |
|---|---:|---|---:|---:|
| N80, THP always (check against pagealloc-n80.txt) | 45056 | 9818 / 12738 / 15658 (exact) | 1592 (exact) | 45631 |
| N90 28.3-28.5 GB, THP never | 21000-21836 | ~4870-5145 / 11280-12185 / 17690-19225 | 1410-1525 (5.5-5.95 MiB) | ~100k-110k |
| N90 28.3-28.5 GB, THP on | 45056 | ~10450-10615 / 16860-17655 / 23270-24700 | 2105-2210 (8.2-8.6 MiB) | ~100k-110k |

The 8 MB lmbench child faults about 2049 + 33 + a few pages, i.e. about 2085.

### 3. Decay arithmetic (decay_pcp_high, one tick about every 1 s)
Starting at count = high = 17146: 15130, 13239, 11584, 10136, 8869, 7760, 6790, 5941, 5199, 4549, 3980, 3483, 3047, 2666, 2333, 2041, 1786, and then the floor. That is about 17 ticks, against about 32 s from the sweep start to the 6 MB child (expH7.log).
