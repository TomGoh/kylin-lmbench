# 核查报告：audit:s2-design-review

## Summary

**Scope.** Everything below was re-derived from expS.log, expV.log, expV2.log, expW.log, vm-frames-n80.txt, iomem-n80.txt, the frames2.c versions in git, and the kernel at tag 6.6.0-79.93. A further raw log, expV3.log (20:30–20:54: three more page sets per size, same slot), appeared while I worked. It is outside this round; I report it separately and only as supporting evidence.

Terms: "slot" is a 1 GiB physical range; "shared" pages lie in a 2 MiB region that also holds pages present in the VMM's guest-memory mapping; "clear" pages do not.

**Verdicts**

1. **Shared pages cost more per random access: stands, with narrower wording.** Safe wording: "On the N80, in one boot, lmbench's random chase over shared host pages was 7% to 13% slower than over clear pages when the pages were spread out (6 to 64 MB), and 2% to 5% slower when they were physically contiguous. At 2 to 4 MB, where the chase needs no page walks, there was no difference. All shared sets came from one population of about 49.7 thousand pages in about 135 regions of the slot at 0x20c0000000. The kernel source says these pages have 4 KiB host stage-2 leaves; this was not read from EL2. In the sequential chase the same sets were 0% to 3% slower."
   - The 13% end is not stable: 16 MB gave +11.9 ns (8%) in Exp V and +18.4 ns (13%) in Exp V2.
   - At 6 and 12 MB the shared times lie inside the spread of the clear passes; only the L2-refill counts separate the classes there.

2. **Same-boot evidence that a host TLB miss reads host stage-2 descriptors: stands, but it is indirect, not direct.**
   - The extra L2-cache refills (+0.08 to +0.92 per access) follow what one extra 8-byte descriptor per page frame, eight per cache line, predicts at every size and for both ways of picking pages.
   - They change from +0.10 to +0.84 between contiguous and spread picks with an identical virtual layout, so the structure being read is indexed by physical address. Stage-1 descriptors are excluded by this and by pass 2 (new page-table pages, same result).
   - The source check supports the leaf-size inference: a split block is refilled at once one level down (stage2_map_prefault_block, pgtable.c:1027–1064, enabled by KVM_HOST_S2_FLAGS in consts.rs:155–157), and donation is one 4 KiB page at a time for 4 KiB-backed guest memory.
   - A second signature is in the logs and was not used by the analyst: at 6 MB the L2-TLB refill rate of clear sets rises with the number of 2 MiB regions the set spans (0.855 at 29 regions to 0.963 at 308; Spearman +1.00 over 10 slots in V2).
   - Neither signature measures what a block-mapped stage 2 costs against none.

3. **"2 MiB blocks are not measurably slower than 1 GiB blocks": falls as argued.**
   - The analyst compared incomplete slots with complete ones. By the analyst's own source reading, every complete slot that held a guest page at 19:24 (0x20c0000000 to 0x2280000000) was 2 MiB-mapped too. Only 0x22c0000000 and 0x2300000000 can still have been 1 GiB blocks.
   - Those two differ from all others in two reproducible ways, both only where page walks occur. They take +1.6 to +2.0 ns per access at 12 MB and above (positive in 25 of 26 passes per slot in S, V and V2 at ≥24 MB; −0.1 to −0.2 ns at 3 and 4 MB, where there are DRAM misses but no walks). They show fewer L2-TLB refills near TLB capacity (0.85 against 0.94–0.96 at 6 MB).
   - Safe wording: "Pages under 2 MiB blocks were not slower than pages in the two slots that may be 1 GiB-mapped; those two were 1.6–2.0 ns slower per access and used fewer TLB refills near capacity. Block size may matter in both directions; no slot's block size was read."

4. **Virtual-order effect unrelated to stage 2: stands, narrower.** It is equally large for clear and shared pages (+18.5%/+20.0% at 8 MB, +25.2%/+27.0% at 16 MB, +25.6%/+27.0% at 64 MB), so it is not caused by 4 KiB stage-2 leaves. Whether it needs stage 2 at all was not tested (protected mode only). It also appears for pages that are near but not adjacent (+3.8% to +7.4% at 64 MB with adjacency 0.0000).

**Alternatives tested against the logs**
- **Spread, region count, pick density:** excluded. Clear sets span 29–344 regions and one page in 1.5–15.7, with no relation to time or L2 refills (Spearman +0.13 and +0.20); the shared set (135 regions, one in 6.1) lies inside that range.
- **Measurement order:** excluded. Each shared set is bracketed within seconds by clear sets at 150.9–152.3 ns before and 151.0–151.6 ns after.
- **VM activity or preemption:** no sign. Wall time times 1.8976 cycles/ns equals the EL0-only cycle count (median ratio 0.999 clear, 1.000 shared). The VM grew by 12 pages and 5 regions between 19:24 and the next archived listing (written to the results directory at 20:09), none in the slot at 0x20c0000000.
- **Page migration:** no sign before timing (in all 152 sorted rows of expW.log, va_region_changes equals mb2_regions − 1); not checked during timing.
- **Page colour:** not recorded by frames2. It cannot add L2 refills, because data lines miss L2 anyway, but it does move times by up to 8 ns at 8 MB and below.
- **One physical population:** cannot be excluded.

**Arithmetic**
- A spread 32 MB set needs about 6,400–7,700 descriptor lines (400–480 KiB), not 8,192; the 135 regions hold only 8,640 lines in total.
- What governs the misses is reuse distance, not "fits in L2": 56% of walks refill L2 at 16 MB, where the lines need 256 KiB.
- A plain LRU model of the 512 KiB L2 gives extra refills of 0.01, 0.06, 0.30, 0.63, 0.96, 0.84–0.99, 0.80–0.92, 0.82–0.92 for 6 to 64 MB; measured 0.08, 0.17, 0.37, 0.56, 0.92, 0.83, 0.82, 0.81. For the mixed set of Exp S it gives +0.66; measured +0.63.
- Extra cycles fit a·(walks − extra L2 refills) + b·(extra L2 refills) + c·(extra L3 refills) with a = 8.7, b = 29.2, c = 231 cycles (rms 1.0 cycle over 26 passes). Reference latencies on the same machine: 4.0 (L1), 15.3 (L2), 38 (L3) cycles. So 29 cycles per L2-refilling walk is plausible for an L3 hit.
- The raw ratio of extra time to extra L2 refills is not constant (124, 89, 50, 61 or 39, 39, 34, 31, 32 cycles from 6 to 64 MB; 86 for the contiguous pick), so it only makes sense with the base term and the L3 term.

**Not predicted by the stage-2 explanation**
- The bump at 16–24 MB is the shared class losing its residual L3 hits (+0.06 and +0.035 L3 refills), and at 16 MB this happens in some runs only.
- The clear median moved from 151.7 to 154.0 ns between V and V2 because 11 of 24 clear passes lost their L3 hits in that V2 run.
- In the sequential chase the shared class pays at most 6 cycles per page crossing, against 26–36 per walk in the random chase, even for spread and shuffled sets where the analyst's "adjacent descriptors" reason does not apply.
- The shared class shows fewer L2-TLB refills than clear at 8–16 MB in the sequential chase.
- The offset of the two candidate 1 GiB slots (verdict 3).

**Measurements that need no settings change and no reboot**
1. A chase that touches one cache line per page, so every access misses the TLB but data come from L2/L3. This isolates the per-walk cost from DRAM and L3 effects for shared, clear and the two offset slots.
2. Access-count events 0x16, 0x04, 0x2b, 0x19, 0x2f in the existing design, to count descriptor reads rather than refills.
3. Shared sets outside the one population: the roughly 1.5 thousand shared pool pages of the slot at 0x2080000000 at 5–5.8 MB; shared pages pooled across slots; mixtures with a chosen shared fraction.
4. At fixed size, vary pages per group of eight frames (1, 2, 4, 8) and the number of regions a set spans (1 to 256 within one slot, at 5–8 MB).
5. Log the selected frames, colour histograms and a post-timing frame re-read; alternate and interleave the order; at least five sets per size.
6. Read /sys/kernel/debug/kvm/*/protected_hyp_mem and protected_shared_mem, /proc/kpageflags for the regions, /proc/vmstat and the vCPU threads' stat around each pass; archive every VM page list.
7. Keep a measured clear set mapped, make the guest touch new memory, and re-measure the same frames.

**Measurements that need a settings change or a reboot**
- Stop the VM and re-measure the same regions; the source's coalescing path predicts the penalty disappears.
- Back guest memory with 2 MiB pages, or start a second protected VM.
- Boot protected without the VM, repeat Exp S and the 6 MB walk-rate test.
- Boot nvhe or kvm-off.
- Boot a kernel that can dump the host stage 2: the snapshot hypercall is commented out at hyp_main.rs:1912 and there is no ptdump.
- Repeat on the N90.

## Defects

- **invalidates** | memlat-rootcause.zh-CN.md section 3.7 (last result bullet), worklog 11.3, claim ev#9, derived/state-tables.md Exp S tables (columns 'RAM in slot'): Incomplete GiB slots are compared with 'complete' ones as if the complete ones were 1 GiB stage-2 blocks. By the same source reading the analyst uses elsewhere, any slot holding a guest page is split to 2 MiB blocks. vm-frames-n80.txt (19:24) shows guest pages in every complete slot from 0x20c0000000 to 0x2280000000, so only 0x22c0000000 and 0x2300000000 can have been 1 GiB blocks. Those two are lumped with the rest although they are 1.6-2.0 ns slower at 12 MB and above (25 of 26 passes positive per slot at >=24 MB in S, V, V2) and have fewer L2-TLB refills at 6 and 8 MB (0.849/0.851 against 0.935-0.963; 0.980/0.978 against 0.993-0.999). Effect: Conclusion 3 does not follow from the comparison made. The data contain a reproducible difference between the only candidate 1 GiB slots and the 2 MiB-mapped ones, tied to page walks (absent at 3-4 MB where DRAM misses occur without walks).
- **weakens** | Design of Exp V and V2 (run11-vm-shared.sh, run12-vm-shared-sizes.sh; expV.log, expV2.log): From 6 MB upward every shared set comes from one slot and in fact from one recurring population: frames_in_class is 49405-49735 and the set spans 130-135 regions in every run. The three runs of Exp V and the two passes per size of V2 are re-draws from the same frames; passes reuse the same frames and the same page order. Other slots had too few shared pool pages (1499 and about 1100) and were measured only at 2-4 MB, where there are no walks. Effect: Conclusions 1 and 2 rest on one physical population of about 135 regions on one machine in one boot. A property of these regions other than stage-2 leaf size is made unlikely by the counter signature but is not excluded by independent regions. The later V3 log repeats with the same population.
- **weakens** | memlat-rootcause.zh-CN.md 3.7 (size table and 'the extra is the cost per walk'), worklog 11.8, claim ev#11: The 'cycles per walk' column (11 to 36) and the 7%-13% range mix two things: the extra descriptor read, and at 12-32 MB the loss of the residual L3 hits of the data lines (extra L3 refills +0.062 at 16 MB and +0.035 at 24 MB in V2, worth about 14 and 8 cycles). The second part is not reproducible at 16 MB: Exp V gives +11.9 ns with L3 refills 0.946-0.954, V2 gives +18.4 ns with 0.9993-0.9995, with identical extra L2 refills (0.555 and 0.563). Both numbers are in the analyst's tables but the contradiction is not discussed; the size table shows only +18.4. Effect: The upper end of the range (13%) and the non-monotonic shape come from a cache-occupancy side effect that appears in some runs only. The descriptor-read part alone rises monotonically to about 13-14.5 ns (8.5%-9.5%) at 24-64 MB.
- **weakens** | expV2.log rows at 6, 8 and 12 MB; section 3.7 size table: At 6 and 12 MB the two shared passes lie inside the spread of the 24 clear passes (6 MB: shared 71.3/72.1 ns, clear up to 76.5; 12 MB: shared 143.2/143.4, clear up to 145.5). Set-specific effects of the same size exist without any walk: at 4 MB the clear set of slot 0x20c0000000 is 38.8/39.4 ns against 30.6 elsewhere, and slot 0x2200000000 is +3.1 ns at 2 MB and +4.9 ns at 4 MB. Effect: The time penalty quoted for 6-12 MB (7%-9%) is weakly supported by times alone. What separates the classes cleanly at those sizes is the L2-refill count (shared 1.075-1.376, clear 0.998-1.008).
- **weakens** | memlat-rootcause.zh-CN.md 3.7 ('the two classes have the same number of walks'), claim ev#12(b): Equal walk counts are a ceiling effect at 12 MB and above (1.000 in every set). Where the count is below its ceiling it depends on the number of 2 MiB regions of the set (6 MB: 0.855 at 29 regions to 0.963 at 308) and is lower in the two candidate 1 GiB slots. In the sequential chase the shared class has fewer L2-TLB refills than clear (8 MB: 0.037-0.049 against a clear median of 0.051-0.055). Effect: The statement is true only in the saturated regime. The region dependence is an unremarked second stage-2 signature that supports conclusion 2 and contradicts conclusion 3.
- **weakens** | Worklog 11.8 and claim ev#14 (interpretation of Exp W); sections 1.7 and 3.7 headline: In the sequential chase the shared class pays at most 6 cycles per page crossing (-6.6 to +5.8 over the 12 conditions) against 26-36 cycles per walk in the random chase. The reason given ('descriptors of adjacent pages are adjacent') covers only sorted contiguous sets; the penalty is equally absent for spread and shuffled sets (16 MB +5.0, 64 MB +3.0 cycles per crossing), where each walk needs its own descriptor line and that line cannot still be in L2. The headline '7%-13% slower' carries no restriction to the random chase or to spread pages. Effect: Conclusion 1 must be restricted to a dependent random chase over spread pages. The stage-2 explanation needs an untested extra assumption (walk latency hidden or done ahead in the sequential chase) to cover Exp W.
- **weakens** | Section 3.7 background paragraph; frames2.c header comment; vm-frames.py; run12-vm-shared-sizes.sh: The stage-2 leaf size of no page was observed. The region list contains pages present in the VMM's guest-memory mapping, which is a superset of donated pages, and it misses pages the host gave to the hypervisor for the VM (memcache pages refilled on every guest fault, hyp_main.rs:1067) and pages shared with it. The list used for V2 and W (written to vm-frames-n80-run12.txt and guest-regions.txt at 19:29) is not archived. Effect: 'Are mapped with 4 KiB leaves' should read 'are expected from the kernel source to be'. Class clear may contain 4 KiB-mapped regions; that would dilute the effect, not create it, and the clear sets show no sign of it (L2 refills 1.03-1.08 at 32 MB).
- **weakens** | experiments/memlat-probe/frames2.c (all versions used): The program prints only the lowest and highest frame of a set: no frame list, no count of distinct descriptor lines, no colour statistics. It re-reads frame numbers before timing but not after. The order is fixed (slots ascending, clear before shared), and each value is the median of 5 timed intervals while the counters are sums over the same 5. Effect: Colour distribution of the sets and migration during timing cannot be checked from the logs; the descriptor-line arithmetic has to be modelled instead of counted. Order effects are excluded only by the bracketing clear measurements.
- **weakens** | Worklog 11.8 and claim ev#14 ('only when virtually adjacent pages are physically adjacent'); conclusion 4 wording: The order effect also appears for sets with adjacency 0.0000 whose pages are merely near: 64 MB spread sets show +3.8% to +7.4% (clear) and +8.2% (shared), and the 16 MB clear set of slot 0x2080000000 shows +9.1%. 'Unrelated to stage-2' is broader than what was tested, which is 4 KiB leaves against blocks in protected mode, one run per condition. Effect: Conclusion 4 stands only as 'not caused by 4 KiB host stage-2 leaves'.
- **cosmetic** | memlat-rootcause.zh-CN.md 3.7 (bullet on cache lines), claim ev#12(c): 'A 32 MB set needs 8192 lines, 512 KiB, exactly the L2 size, so nearly every walk misses' is an upper bound presented as the mechanism. The 135 regions hold 8640 descriptor lines in total and a modelled spread set uses about 6400-7700. The miss rate is set by reuse distance: 56% of walks already refill L2 at 16 MB (256 KiB of lines) and 92% at 24 MB (384 KiB). Effect: None on the verdicts; the explanation of the size dependence should be restated.
- **cosmetic** | memlat-rootcause.zh-CN.md 3.7 ('what it shows and does not show', second bullet): The N80 figure of 11-18 cycles per walk (4 KiB leaves against blocks, 1.9 GHz) is set beside the N90 figure of 12-15 cycles per access (block-mapped stage 2 against none, 1.8 GHz) as order-of-magnitude corroboration. They are different quantities from different data sets. Effect: None if the sentence is read as the caveat it carries; it should not be cited as support for the Figure 7 mechanism.
- **cosmetic** | results/memlat-n80-20260930/README.md field list; task description of the round: README says ns_min/ns_med/ns_max are over 11 repetitions; frames2 uses 5 (REPS at frames2.c line 54 in commit 7ef1be47, and in every earlier version). The logs of S, V and V2 were produced by three earlier frames2 versions (formats of commits 58c45b76, 3a0fabf5, 8ec9fe31), not by the 7ef1be47 version: expS.log has frames_in_slot and no class field, expV.log and expV2.log have no mode/stride/order fields. Effect: None on the measurements in random mode; provenance only.

## Discrepancies

- Same nominal condition, two results: 16 MB spread shared set is +11.9 ns over clear in expV.log (lines 119-120: 156.4/155.4 ns, L3 refills 0.954/0.946) and +18.4 ns in expV2.log (lines 187-188: 162.3/161.9 ns, L3 refills 0.9995/0.9993). The conclusion document's size table shows only +18.4; worklog 11.6 gives +11.5 without comment. The later V3 log reproduces both values (+10.9, +18.7, +19.5).
- Conclusion document 3.7 states that 2 MiB and 1 GiB blocks show no resolvable difference (at most 1-2 ns), while its own background paragraph says guest pages split the GiB blocks. With vm-frames-n80.txt lines 3-11, the 'complete' slots compared are themselves 2 MiB-mapped, and the two that are not (0x22c0000000, 0x2300000000) are consistently 1.6-2.0 ns slower at 12 MB and above.
- Claim ek#4 ('nothing merges the host stage-2 back into blocks') is contradicted by the source at tag 6.6.0-79.93: stage2_coalesce_walk_table_post (arch/arm64/kvm/hyp/pgtable.c:1127-1176) replaces a table by a block when no counted entry is left, and it runs on every kvm_pgtable_stage2_map (lines 1204-1239, TABLE_POST), which is the path taken when a page is returned to the host (host.rs:766-770 via host_stage2_idmap_locked; __pkvm_host_reclaim_page at host.rs:1949). This claim belongs to another verifier; I note it because it changes what stopping the VM should do.
- Claim ev#12(c) and section 3.7: '32 MB needs about 8192 lines (512 KiB)'. Recomputed: at most 8640 lines exist for 135 regions; a modelled spread set uses about 6400-7700 lines (400-480 KiB).
- Claim ev#12(b) and section 3.7: 'walks per access are the same in both classes'. Recomputed at 6 MB in expV2.log: walks range from 0.848 to 0.964 across clear sets and track the number of regions (Spearman +1.00 over 10 slots); shared is 0.889/0.851.
- Worklog 11.8 and claim ev#14: the order effect appears 'only' with physical adjacency. Recomputed from expW.log, 64 MB spread sets with adjacency 0.0000: +3.9% (0x2140000000), +3.8% (0x21c0000000), +5.0%, +4.3%, +6.8% (0x22c0000000), +7.4% (0x2300000000), shared +8.2%.
- The size table's 2-4 MB rows (-0.1, 0.0, +0.3 ns) pool shared sets from three slots. For the slot that carries all larger sizes (0x20c0000000) the 2 MB difference is +0.7 ns with more L3 refills (0.10 against 0.05), and at 4 MB its clear set is 7.6 ns slower than its shared set. These are page-set effects, not walk effects, and they are not mentioned.
- Worklog 11.3 says the VM's two vCPU threads used 50 seconds of CPU in three hours. vm-process-n80.txt records no CPU time, so this cannot be checked from the archived sources.
- The task description says the evening logs were produced by the frames2 version in commit 7ef1be47. By log format, expS.log, expV.log and expV2.log come from earlier versions; only expW.log matches. The V2 version adds a calibration to at least 100 ms per timed interval that the V version lacks.
- README.md describes ns_min/ns_med/ns_max as taken over 11 repetitions; for the frames2 logs it is 5.
- My recomputation otherwise agrees with the analyst's numbers: Exp V 32 MB shared 168.25 ns (166.45-168.41), clear 151.67 ns (150.86-154.70, n=72), +0.834 L2 refills; V2 extras +5.8, +8.2, +9.4, +18.4, +19.6, +14.2, +13.4, +13.4 ns; contiguous pick +4.5 ns against all clear (+4.9 against the clear set of the same slot); Exp W order effects +18.5/+20.0, +25.2/+27.0, +25.6/+27.0 percent.

## Threats to validity

- One machine, one boot, one idle VM with one memory layout, and one population of shared frames (about 49.7 thousand pages in about 135 regions of one GiB). Every statement about shared pages generalises from that.
- The stage-2 shape is inferred from kernel source for every page. The two counter signatures (L2-cache refills following frame-indexed descriptor lines; L2-TLB refills following the number of 2 MiB regions) are my reading of counters on a core whose TLB and walk caches are undocumented.
- PMU semantics are implementation defined: 0x2d is taken as page walks (the PMU advertises no walk event), and whether walker reads and prefetch-initiated fills are counted in 0x17 and 0x2a is assumed from the data. All events exclude EL1 and EL2.
- Identifying 0x22c0000000 and 0x2300000000 as the 1 GiB-mapped slots rests on the VM page list of 19:24 (no list exists from the time of Exp S), on the source, and on the absence of hypervisor-owned or shared pages in those slots, which was not checked. With only two such slots the offset could have another cause tied to those addresses, although its absence at 3-4 MB argues against a DRAM-latency cause.
- Background is uncontrolled: desktop session, the idle VM, system THP 'always'. The clear class flips between two L3 states about 3.3 ns apart (L3 refills about 0.975 or about 1.000 per access at 32 MB) for unknown reasons, and Exp S shows transients up to +13 ns lasting seconds.
- The hypothesis about shared regions was formed after Exp S's written prediction had failed, from the anomaly of the slot at 0x20c0000000, and was then tested on that same slot. The test used an independent criterion (the VM page list) and a prediction committed 12 seconds before the run, but it is a refinement within the slot, not an independent replication.
- The region list is incomplete (hypervisor-owned and shared kernel pages) and was 0 to 11 minutes old when used; the list used for V2 and W is not archived. Observed VM growth was 12 pages and 5 regions between the 19:24 listing and the next archived one (on disk at 20:09).
- Page migration during timing was not checked. Before timing the frame numbers are consistent in every row I could test.
- Page colour of the sets is unknown. It cannot explain the L2-refill signature but can shift times at 8 MB and below and may contribute to the L3-state differences at 12-24 MB.
- My LRU model of the L2 cache is a simplification (no L1 in front, no prefetcher, ideal LRU, modelled placement of pool pages). It reproduces the shape and level of the extra refills; it is a plausibility check, not a measurement. It under-predicts at 6-8 MB (0.01 and 0.06 against 0.08 and 0.17).
- expV3.log postdates the claims and was produced by a later frames2 build (chase=loop, same timed loop). I used it only to see whether the V2 values recur; the verdicts are stated from S, V, V2 and W.
- The random dependent chase with one walk per access is a worst case. The 7%-13% figure says nothing about ordinary host workloads, and the sequential result (0%-3%) shows the penalty can almost vanish.

## Recomputed tables

All values recomputed from the raw logs. "Extra" is the shared set of slot 0x20c0000000 minus the median of all clear passes of the same run. V3 columns come from the later log and are outside this round.

### Table 1. Exp V, 32 MB, pages spread evenly (expV.log, 3 runs x 2 passes)

| set | n | ns median (min-max) | EL0 cycles | walks per access | L2 refills | L3 refills |
|---|---:|---|---:|---:|---:|---:|
| shared, slot 0x20c0000000 | 6 | 168.25 (166.45-168.41) | 319.1 | 1.000 | 1.877 | 1.000 |
| clear, same slot | 6 | 151.50 (150.89-154.38) | 287.8 | 1.000 | 1.040 | 0.979 |
| clear, all 12 slots | 72 | 151.67 (150.86-154.70) | 288.2 | 1.000 | 1.043 | 0.978 |
| shared minus clear (all) | | +16.6 | +30.9 | 0 | +0.834 | +0.021 |

Clear measured just before each shared set: 151.05, 152.32, 150.89 ns; just after: 151.59, 151.03, 151.21 ns.

### Table 2. Size dependence and descriptor-line arithmetic

Fit: extra cycles = 8.7 x (walks - extra L2 refills) + 29.2 x (extra L2 refills) + 231 x (extra L3 refills), from V and V2 (26 passes, rms 1.0 cycle).

| size, pick | extra ns in V2 (percent) | other runs, extra ns | extra L2 refills (all runs) | extra L3 refills (all runs) | descriptor lines needed (KiB; share of 512 KiB L2) | LRU model, extra L2 refills | extra cycles: fit / measured |
|---|---|---|---|---|---|---|---|
| 6 MB, spread | +5.8 (8.8%) | V3: +5.2, +10.7, +7.2 | 0.072-0.080 | 0.004-0.026 | 1536 (96; 19%) | 0.01 | 11.0 / 9.9 |
| 8 MB, spread | +8.2 (8.0%) | V3: +8.2, +8.5, +12.8 | 0.169-0.183 | 0.006-0.032 | 2048 (128; 25%) | 0.05-0.07 | 13.4 / 15.2 |
| 12 MB, spread | +9.4 (7.0%) | V3: +11.1, +17.6, +10.7 | 0.353-0.370 | 0.002-0.069 | 3072 (192; 38%) | 0.29-0.32 | 16.7 / 18.2 |
| 16 MB, spread | +18.4 (12.8%) | V: +11.9 (8.3%); V3: +10.9, +18.7, +19.5 | 0.552-0.563 | 0.002-0.067 | 4096 (256; 50%) | 0.63 | V2 34.5 / 34.5; V 21.6 / 21.5 |
| 24 MB, spread | +19.6 (13.1%) | V3: +17.9, +19.4, +19.5 | 0.875-0.918 | 0.030-0.043 | 6144 (384; 75%) | 0.96 | 35.6 / 35.8 |
| 32 MB, spread | +14.2 (9.2%) | V: +16.5, +16.7, +15.6; V3: +14.7, +14.1, +16.7 | 0.830-0.841 | 0.010-0.027 | 6400-7700 (403-480; 79-94%) | 0.84-0.99 | V2 28.7 / 28.1; V 30.6 / 30.8 |
| 48 MB, spread | +13.4 (8.6%) | V3: +14.7, +14.1, +13.8 | 0.777-0.822 | 0.001-0.009 | 6700-8500 (417-533) | 0.80-0.92 | 25.8 / 25.6 |
| 64 MB, spread | +13.4 (8.6%) | V3: +17.1 (one pass at 176.8 ns with 1.05 L3 refills), +13.4, +13.1 | 0.792-0.817 | -0.001-0.026 | 6700-8600 (421-538) | 0.82-0.92 | 25.5 / 25.5 |
| 16 MB, contiguous | not run | V3: +2.3 (1.6%) | 0.030 | 0.002 | about 580 (36) | 0.001 | |
| 32 MB, contiguous | not run | V: +4.5 (3.0%); V3: +6.5 (4.3%) | 0.104-0.112 | 0.000-0.010 | about 1150 (71) | 0.06-0.11 | V 10.4 / 8.9 |
| 64 MB, contiguous | not run | V3: +7.7 (4.9%) | 0.281 | 0.000 | about 2300 (145) | 0.28-0.30 | |

At 2, 3 and 4 MB (no walks) the shared set of this slot differs from the clear median by +0.7, 0.0 and +0.9 ns; at 4 MB the clear set of the same slot is 38.8/39.4 ns against a clear median of 30.6.

Extra cycles per extra L2 refill, raw: 124, 89, 50, 61 (V2) or 39 (V), 39, 34-37, 31, 32 from 6 to 64 MB; 86 for the contiguous 32 MB set. After removing 231 cycles per extra L3 refill: 101, 81, 48, 36, 30, 30-31, 31, 31. Reference latencies on this machine: L1-hit chase 4.0 cycles (expX1.log, 23 KiB), L2-hit 15.3 (expA.log, 0.5 MB), L3-hit 38 (expA.log, 1.5 MB).

Separation per run: the smallest shared L2-refill value exceeds the largest clear value in all 5 runs of V and all 8 runs of V2 at 6 MB and above. For times this holds at 8 MB and from 16 MB upward; at 6 MB 2 of 24 clear passes and at 12 MB 1 of 24 are slower than the shared ones.

### Table 3. Slots: expected stage-2 shape, walk rate at 6 MB, offset at 32 MB

| slot base | guest pages at 19:24 (regions) | host stage-2 leaf expected from the source | walks per access at 6 MB in V2 [regions of the set] | ns offset from the run's clear median, Exp V 32 MB |
|---|---|---|---|---:|
| 0x2080000000 (half RAM) | 1369 (80) | 2 MiB | 0.855 [29] | -0.3 |
| 0x20c0000000, clear | 26743 (165) | 2 MiB | 0.876 [54] | -0.2 |
| 0x20c0000000, shared | same | 4 KiB | 0.870 [131] | +16.6 |
| 0x2100000000 | 36972 (96) | 2 MiB | 0.935 [227] | -0.3 |
| 0x2140000000 | 100 (9) | 2 MiB | 0.948 [259] | -0.2 |
| 0x2180000000 | 16 (9) | 2 MiB | 0.936 [240] | 0.0 |
| 0x21c0000000 | 8 (7) | 2 MiB | 0.945 [247] | -0.5 |
| 0x2200000000 | 5 (4) | 2 MiB | 0.940 [245] | -0.1 |
| 0x2240000000 | 33 (14) | 2 MiB | 0.949 [265] | +0.1 |
| 0x2280000000 | 3 (2) | 2 MiB | 0.963 [308] | -0.3 |
| 0x22c0000000 | 0 | 1 GiB possible | 0.849 [273] | +1.7 |
| 0x2300000000 | 0 | 1 GiB possible | 0.851 [258] | +1.6 |
| 0x2340000000 (holds the 86 MiB hypervisor pool) | 0 | 2 MiB | 0.917 [153] | -0.2 |

Spearman correlation of walks with regions over the 10 clear slots other than the two candidates: +1.00 at 6 MB and +0.92 at 8 MB in V2; +0.90 to +0.97 in each of the six V3 runs at 6 and 8 MB. At 8 MB in V2 the two candidate slots have 0.980 and 0.978 walks against 0.993-0.999 for other slots with more than 200 regions.

Offset of the two candidate slots against the median of the other clear slots, by size (S, V, V2; mean of all passes): 3 MB -0.13, 4 MB -0.17, 8 MB +0.65, 16 MB +1.8, 24 MB +1.7, 48 MB +2.1, 64 MB +2.0 ns (median +1.8 at 32 MB, n=36). The low slots 0x80000000 and 0xc0000000 (Exp S only) are at -0.5 and +0.1 ns.

Physical spread inside class clear (Exp V, 32 MB, n=72): sets span 29-344 regions and take one page in 1.5-15.7; Spearman with ns +0.13, with L2 refills +0.20. The shared set spans 135 regions and takes one page in 6.1.

### Table 4. Exp W, sequential chase with stride 256: shared minus clear

Per page crossing = 16 x per-access difference. The random chase at the same sizes gives 26-36 cycles per walk.

| size, pick, order | shared ns | clear median ns | difference | cycles per page crossing | extra L2 refills per crossing | L2-TLB refills per access, shared / clear median |
|---|---:|---:|---:|---:|---:|---|
| 8 MB, contiguous, sorted | 8.11 | 8.18 | -0.8% | -2.0 | +0.09 | 0.037 / 0.051 |
| 8 MB, contiguous, shuffled | 9.73 | 9.69 | +0.5% | +1.2 | 0.00 | 0.048 / 0.055 |
| 8 MB, spread, sorted | 9.69 | 9.64 | +0.5% | +0.9 | +0.06 | 0.042 / 0.054 |
| 8 MB, spread, shuffled | 9.69 | 9.65 | +0.4% | +1.4 | +0.09 | 0.043 / 0.055 |
| 16 MB, contiguous, sorted | 8.19 | 8.38 | -2.3% | -5.8 | +0.25 | 0.050 / 0.057 |
| 16 MB, contiguous, shuffled | 10.40 | 10.49 | -0.8% | -2.7 | +0.34 | 0.058 / 0.061 |
| 16 MB, spread, sorted | 10.74 | 10.54 | +1.9% | +5.8 | -0.09 | 0.057 / 0.061 |
| 16 MB, spread, shuffled | 10.68 | 10.51 | +1.6% | +5.0 | +0.17 | 0.057 / 0.061 |
| 64 MB, contiguous, sorted | 8.36 | 8.45 | -1.1% | -1.5 | -0.02 | 0.058 / 0.059 |
| 64 MB, contiguous, shuffled | 10.62 | 10.61 | 0.0% | +0.1 | +0.14 | 0.0625 / 0.0625 |
| 64 MB, spread, sorted | 9.92 | 10.13 | -2.1% (clear sets differ in adjacency) | -6.6 | +0.24 | 0.0625 / 0.0625 |
| 64 MB, spread, shuffled | 10.74 | 10.65 | +0.8% | +3.0 | +0.31 | 0.0625 / 0.0625 |

Against the clear set of the same slot the largest difference is +3.3% (16 MB, spread, sorted).

Order effect (shuffled over sorted), contiguous pick, clear median / shared: 8 MB +18.5% / +20.0%; 16 MB +25.2% / +27.0%; 64 MB +25.6% / +27.0%. Per slot it ranges from +15% to +30% and follows the adjacency of the sorted set (0.77-0.998).

### Table 5. Other checks

| check | result |
|---|---|
| Pass 2 minus pass 1 (new page-table pages), Exp V | clear: median -0.22 ns (n=60); shared: median -0.43 ns (n=5), L2 refills -0.0001 |
| Wall time x 1.8976 over EL0 cycle count | clear median 0.999 (0.981-1.006); shared median 1.000 (0.998-1.002) in Exp V |
| Frame numbers before timing, sorted rows of expW.log | va_region_changes = mb2_regions - 1 in 152 of 152 rows (690 of 690 in V3) |
| Shared set region count, 32 MB | 135 in all three runs of V and in V2 |
| Clear class at 32 MB, two L3 states | L3 refills below 0.985: 151.5 ns (n=172); 0.995 or more: 154.8 ns (n=21). Passes in the second state: 0-2 of 24 per run in V, 11 of 24 in the 32 MB run of V2 |
| Mixed set of Exp S (slot 0x20c0000000, 65% shared) | measured 164.3 ns and 1.675 L2 refills (about +0.63); LRU model +0.66; linear mixture of the V class values +0.55 |
| VM page list, 19:24 against the listing archived at 20:09 | 65249 to 65261 present pages, 386 to 391 regions; slot 0x20c0000000 unchanged (26743 pages, 165 regions) |
