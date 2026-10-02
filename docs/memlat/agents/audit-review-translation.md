# 核查报告：audit:review-translation

## Summary

Verdict: the inference stands only in a narrower form. Two parts of it hold up on primary data. The cross-machine arithmetic is not wrong, but it carries more uncertainty than the stated "12 to 15 cycles" suggests.

What I re-derived myself (scripts in <scratch>/wf5/audit-review-translation/: nn1.py, nn4.py, n3.py, z.py, nn5.py, n90.py, p64.py):

(1) Within one N80 protected boot, the cost of a walk depends on the physical class of the data page. Exp Z, 2048x1, counted cycles minus 13.97, divided by walks: 24.0 to 24.2 cycles per walk in all ten "2 MiB" slots, 28.0 in both slots 0x8b and 0x8c, 34.1 in VM-shared regions (one slot, with 0.05 L2 refills per hop). N3 mixes the classes linearly from 36.91 to 40.46 cycles per hop. The no-walk configurations are flat at 14.3 to 14.5. Data stay in L2 (L2 refills at most 0.005), and Exp Z pass 2, which uses new page-table pages, gives the same result. So the only physical-address-dependent step left in the walk is the host stage-2. This is the strongest N80-side evidence that the stage-2 is consulted during walks and costs time. It needs no class labels.

(2) On the N90 itself, with the same machine and four boots, the increment exists only in protected mode. Median pkvm minus the median of the pooled other three boots:
- below 0.2 ns up to 2 MB
- 0.72, 1.68 and 5.27 ns at 3, 4 and 6 MB
- 6.4 to 8.1 ns at 8 to 64 MB, which is 11.6 to 14.6 cycles at 1.8 GHz

nVHE minus kvm-off stays within 0.24 ns at every size, so the host exception level alone does not matter. This shape follows TLB reach.

(3) The cross-machine numbers reproduce. Using probe3 on both machines with ascending first touch, N80 minus workstation is +12.95 cycles (2048x1), +13.41 (2048x2) and +14.18 (4096x1). With chain-order touch it is +14.26 (2048x1). The no-walk configurations differ by 0.00 to 0.04. With the class values (frames2 23.0 and 26.4 extra per hop, workstation 11.2) the difference is 11.8 to 15.2 per hop.

What is weaker than claimed:
- The workstation is not "the N80 without a stage-2". Its KVM log reports a 48-bit IPA limit against 40 on the N80, so the physical address size the core reports differs even though the core ID (MIDR) is the same. Walker or firmware differences cannot be bounded from the data. The no-walk agreement validates L1/L2 and TLB reach, not the walker.
- The comparison mixes estimators and programs: N80 counted cycles averaged over the timed intervals (frames2) against the workstation's minimum-interval estimate (probe3). That moves the difference by 0.2 to 0.4 cycles.
- The workstation's walks per hop are unknown.
- The "1 GiB" label for 0x8b and 0x8c rests on source plus the memory map only. Hidden hypervisor metadata pages could split any slot, and nothing reads the EL2 tables. A larger block being slower has no architectural reason; it needs an undocumented TLB or walk-cache property.
- Under the source-based expectation (N90 with no VM, so mostly 1 GiB blocks), the N80 classes predict at least about 15 to 16 cycles per walk. The N90 shows 11.6 to 14.6.
- The N90 per-walk quotient at 2 to 4 MB is only 3.3 to 3.9 ns (6 to 7 cycles). That regime is the closest to the cache-resident chase, so a fixed per-walk cost does not fit the whole curve. This is weak evidence because the walk rates come from another machine and change steeply there, but it is unresolved.
- The N90 pkvm column is a single boot (try2).
- The paper's +3.25% is mean pkvm against mean kvm-off at 64 MB, inflated or deflated by fast-state iterations. Against nVHE or VHE the means give +3.88 and +3.82; the medians give +3.40 to +3.61%. The walk explanation addresses the median increment of about 6.4 ns, not the 3.25 figure as such.

Safe wording: "In protected mode the host's page walks consult the host stage-2 and cost more. On the N80 this is shown within one boot by a walk cost that depends on the stage-2 class of the data page. On the N90 the protected boot alone has a random-access increment of 6.4 to 8.1 ns (12 to 15 cycles) per access at 8 to 64 MB, starting where TLB misses start. A translation-only chase on a second FTC862 machine without a host stage-2 shows 12 to 15 fewer cycles per walking hop than the N80. The two sizes agree, which supports attributing the increment to the stage-2 part of the walk. A same-machine comparison of boot modes, which alone would establish it, has not been done."

Measurements that would settle it:
- With a reboot: run5-mode-compare.sh on the N80 and on the N90, at least two interleaved boots per mode, PMU on. Include probe3 tlb (1024x2, 2048x1, ascending touch), frames2 tlb1 per slot and lmbench -t. Prediction: in non-protected boots 2048x1 minus 1024x2 is about 11 cycles, there is no slot dependence, and the lmbench increment disappears. Also a 2x2 of protected/non-protected against 4 KiB/2 MiB pages, and optionally a kernel that caps host stage-2 blocks at 2 MiB or dumps the leaf level.
- Without a reboot: on the N80, change the stage-2 state of the same frames (start or stop a VM so that slots 0x8b/0x8c split or others coalesce) and remeasure. Predicted 28 to 24 or 24 to 28 cycles per walk. This is a device-state change, so stage it for the user.
- Without a reboot: enable user PMU on the workstation (paranoid at most 2, user's decision) to get walks per hop and counted cycles.
- Without a reboot: run probe3 or frames2 tlb with PMU on the N90 in its current boot to get its own per-walk cost and class.

## Defects

- **cosmetic** | nn#6 (and memlat-rootcause.zh-CN.md 3.7 class table, worklog 11.21/11.23), VM-shared class from Exp Z: The VM-shared class is quoted as 33.6 cycles per walk with 0.967 walks per hop. Recomputed from results/memlat-n80-20260930/expZ.log (six class=shared lines, slot 0x83, tlb stride 1, size 8): ev11 mean 46.57, ev2d mean 0.956, (46.57-13.97)/0.956 = 34.1. 0.967 is the value of a single line. Effect: None on the inference; the class value is 34.1, not 33.6. The doc's own table in 3.7 already says 34.1.
- **cosmetic** | nn#6 cross-machine arithmetic (23.0/26.4 minus 11.2): The N80 class values are counted cycles averaged over the timed intervals of frames2 (N3: 36.91 and 40.46). The workstation value is probe3's estimate from the minimum interval (cyc_est). The 2048x1 chase drifts downward over its intervals on both machines. On the N80 the counted value exceeds the minimum-based one by 0.15 to 0.4 cycles: from ns_min, N3 gives 36.71 to 36.77 and 40.18 to 40.27. Using the same program on both machines (probe3, N4 ascending) gives +12.95 to +14.18; chain order gives +14.26. Effect: The range shrinks to about 11.6 to 15.0 per hop with matched estimators. The size is unchanged, but the comparison is not like for like.
- **weakens** | nn#6 'adds 11.8 to 15.2 cycles per hop with a walk' versus the inference's framing 'to a page walk': The difference is per hop. The N80 walks 0.92 to 0.96 times per hop and the workstation's walk rate is unknown. Per walk, assuming equal walk rates, it is 24.1-11.2/0.953 = 12.3 (2 MiB class) to 28.0-11.8 = 16.2 (1 GiB-candidate class). If the workstation walk rate is anywhere in 0.85 to 1.0, the 2 MiB per-walk figure lies between 10.9 and 12.9. Effect: The per-walk stage-2 cost for the class the N90 should be in is about 16, not 15, which widens the gap to the N90's 11.6 to 14.6 cycles.
- **weakens** | nn#6 / memlat-rootcause 3.8: the workstation as 'no stage-2 baseline': Apart from the stage-2, the two machines differ in the following. SoC integration and firmware: same MIDR, but KVM reports a 40-bit IPA limit on the N80 (hw-survey-n80.txt line 163) and 48 bits on the workstation (journalctl here), so the reported PARange differs. Kernel 6.6 against 7.0, HZ 250 against 1000. KPTI may be forced by KASLR on 6.6 unless E0PD is present (6.6.0-79.93 cpufeature.c around 1799-1803, mmu.h:84); its state is unknown on both. Load 0.2-1 against 5-7. The no-walk configurations agree within 0.0 to 0.04 cycles, which clears L1/L2 latency, clock conversion and TLB reach, but not the walker or walk caches. The N90's own nVHE minus kvm-off (at most 0.24 ns, about 0.4 cycle) clears the host exception level and translation regime. Effect: Quantifiable residuals: walk-count uncertainty about 0.6 cycle per hop; estimator and program mixing 0.2 to 0.4; load and ticks under 0.5, and they would shrink, not inflate, the difference; regime under 0.5. The firmware or SoC walker configuration is not bounded by any data and could in principle account for several cycles. So '12 to 15 cycles' is an order-of-magnitude match, not a measurement of the stage-2 cost.
- **weakens** | Class labels '1 GiB-candidate' (slots 0x8b, 0x8c) used for the 15.2 endpoint and for the N90 transfer: The labels come only from source plus the memory map plus the VM frame list. In both trees the host stage-2 is prepopulated with the largest blocks: nvhe/mem_protect.c:155-196, xhypervisor host.rs:375-410 and 546, KVM_PGTABLE_MIN_BLOCK_LEVEL 1. Tables are coalesced back when no counted entry remains (pgtable.c:1127-1170). Hypervisor metadata pages donated for the VM are invisible from the host and could split any slot, and the EL2 tables were never read. The data show only that these two slots differ in translation: they are the two slowest of twelve slots, by 3.6 to 4.0 cycles per hop, consistently across seeds. That a 1 GiB block would be slower than a 2 MiB block has no architectural basis; it requires an undocumented property of the FTC862 TLB or walk cache. Effect: The existence of a stage-2-dependent walk cost on the N80 does not depend on the labels. The upper endpoint (15.2) and the prediction for the N90 (mostly 1 GiB, so at least about 15 to 16 cycles) do. That prediction is 1 to 4 cycles above the N90's observed 11.6 to 14.6.
- **weakens** | Step from the N80/workstation figure to the N90 Figure 7 increment: nn#6 presents the agreement in size as 'this is what Figure 7 shows'. Three things weaken that. (a) The N90 increment divided by the N80 Exp A walk rates is 3.3 to 3.9 ns (6 to 7 cycles) per walk at 2 to 4 MB and 6.3 to 8.1 ns at 6 MB and above (derived/device-tables.md; my N90 medians: 0.72, 1.68, 5.27 ns at 3, 4, 6 MB). The 2 to 4 MB regime is the closest to the cache-resident chase and gives about half the cost. (b) The N90 walk rates were never measured. (c) The pkvm column is one boot (try2). In a dependent chase the walk and the data miss cannot overlap, and at 64 MB the leaf-PTE lines are reused about every 2048 data lines, so they mostly stay in L2; this supports additivity at 8 to 64 MB but does not explain the small-size shortfall. Effect: The identification of the N90 increment with 'the stage-2 cost of a cache-resident walk' remains an inference. It is consistent at 8 to 64 MB and inconsistent, though weakly so, at 2 to 4 MB.
- **cosmetic** | nn#6 'that is the +3.25% of Figure 7': +3.25% is mean pkvm over mean kvm-off at 64 MB. Against nVHE and VHE the means give +3.88% and +3.82%; the medians give +3.51%, +3.61% and +3.40%. The mean values include fast-state iterations: pkvm 166.4 and 178.8 ns, kvm-off 168.7 to 176.5 ns. The quantity the walk explanation addresses is the median increment of about 6.4 ns (+3.5%). Effect: The paper's specific number is a noisy reading of the increment. The explanation applies to the increment, not to the 3.25 figure as such.
- **cosmetic** | nn#6 'there the protected host is slower ... by 6.5 to 8.1 ns': The range depends on the baseline. Against the median of the pooled three other boots I get 6.43 to 8.11 ns at 8 to 64 MB. Against the single boots it is 5.32 (VHE at 24 MB) to 8.36 ns, which is 9.6 to 15.0 cycles. Effect: The comparison band on the N90 side is wider than stated.

## Discrepancies

- nn#6: the VM-shared class is quoted as 33.6 cycles per walk (46.5, 0.967 walks). expZ.log gives a mean of 46.57 cycles per hop at 0.956 walks, i.e. 34.1 per walk; memlat-rootcause 3.7 itself prints 34.1 with 0.952.
- nn#6 mixes estimators: N80 class values are counted cycles averaged over the timed intervals (frames2, N3), the workstation value is cyc_est from the minimum interval (probe3). On the N80 the counted value exceeds the minimum-based one by 0.15 to 0.4 (Exp N medians: 39.68 against 39.39 at 2048x1).
- nn#6 states the stage-2 addition per hop (11.8 to 15.2), while the inference under review says per page walk. Per walk with equal walk rates it is 12.3 to 16.2.
- N90 increment: 6.5 to 8.1 ns holds only against the median of the pooled baselines (my value 6.43 to 8.11). Against the individual boots it is 5.32 to 8.36 ns.
- +3.25% (Figure 7) reproduces only as mean pkvm over mean kvm-off at 64 MB. Mean against nVHE or VHE is +3.88 or +3.82%; medians are +3.40 to +3.61%.
- Everything else checked in nn#1 to nn#5 reproduced. Exp N medians: 14.37/14.53, 14.47/14.49, 14.54/14.58, 39.39/24.96, 40.52/25.86, 42.55/27.99, 54.27/38.18, 66.56/50.31. N4 ascending differences: +12.95, +13.41, +14.18, and 0.00/-0.01 for the no-walk configurations. Pooled regression over N2+N4+N5 (50 clean processes): 24.19 + 4.87 (s.e. 1.28) x candidate share + 0.281 (s.e. 0.082) per 100 regions, R^2 0.67; per-experiment candidate coefficients 6.99, -2.30, 3.38.

## Threats to validity

- Unbounded hardware or firmware confound: the N80 and the D80F3 share the core ID (MIDR) but report different physical address sizes (KVM IPA limit 40 against 48), so the core integration differs. Walker or walk-cache configuration (implementation-defined registers set by firmware) cannot be shown equal. The agreement of the no-walk configurations does not test the walker.
- The workstation's walks per hop are unknown (no PMU access). The N80's own walk rate moves from 0.956 to 0.916 with the order of first touch, for an unknown reason, and only on the N80; on the workstation the touch order changes nothing (25.22 against 25.15).
- Possible mechanism split: in protected mode, stage-2 entries may compete for TLB capacity (more walks) rather than making each walk dearer. At 2048 pages the N80 is near saturation (0.95 walks per hop), so this can account for at most about 1 cycle there, but it is not separable from the data.
- Class labels for the N80 slots are inferred from source. Hypervisor metadata donations are invisible from the host. The 'larger block slower' result has no tested mechanism.
- The N80 ran with an idle protected VM in the background, which fragments the host stage-2. The class mix of the N90's lmbench buffers in June is unknown. The N90 kernel was 6.6.0-73.76 with, by defconfig, the C hypervisor; the N80 ran 79.93 with the Rust one. pgtable.c and mem_protect.c are the same at both tags per source, but the hypervisor's allocation behaviour may differ.
- The N90 protected column is one boot, re-run after a first try; each other mode is one boot. Fast-state iterations contaminate means.
- The N90 increment's correlation with L3 refills (0.95) is close to its correlation with walks (0.98). From the N90 timing data alone a DRAM or LLC-side component cannot be excluded; the 2x2 hugepage test was never run.
- The 2 to 4 MB per-walk quotient on the N90 (about 6 to 7 cycles) uses N80 walk rates on the steep part of the TLB-reach curve, so it is unreliable. It neither confirms nor refutes a fixed per-walk cost.
- The workstation prediction in worklog 11.18 was written after a pilot run on the workstation (disclosed), so only the stability and the other configurations count as a test.

## Recomputed tables

| quantity | N80 (protected) | D80F3 (no host stage-2) | difference | source / script |
|---|---:|---:|---:|---|
| 1024x2 no-walk, cyc_est median (N4 ascending) | 13.96 | 13.96 | -0.00 | nn4.py |
| 1024x4 no-walk (N4 ascending) | 14.53 | 14.54 | -0.01 | nn4.py |
| 2048x1 (N4 ascending), cyc_est median | 38.10 (walks 0.916) | 25.15 | +12.95 | nn4.py |
| 2048x1 (N4 chain order) | 39.48 (walks 0.956) | 25.22 | +14.26 | nn4.py |
| 2048x2 (N4 ascending) | 39.47 | 26.06 | +13.41 | nn4.py |
| 4096x1 (N4 ascending; N80 has 0.066-0.100 L2 refills per hop) | 42.34 | 28.16 | +14.18 | nn4.py |
| 2048x1 extra over 1024x2, per hop | 24.1 (asc) / 25.5 (chain) | 11.2 | 12.9 / 14.2 | nn4.py |
| frames2 2048x1 '2 MiB' class (N3 0%), counted / from ns_min | 36.91 / 36.71-36.77 | - | - | n3.py |
| frames2 2048x1 '1 GiB-candidate' (N3 100%), counted / from ns_min | 40.46 / 40.18-40.27 | - | - | n3.py |
| Exp Z per walk, ten '2 MiB' slots / 0x8b, 0x8c / VM-shared (0x83) | 24.0-24.2 / 28.0, 28.0 / 34.1 | - | - | z.py |

| N90 lat_mem_rd -t, medians (ns) | 3 MB | 4 MB | 6 MB | 8 MB | 12 MB | 16 MB | 24 MB | 32 MB | 48 MB | 64 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pkvm minus median of pooled other boots | 0.72 | 1.68 | 5.27 | 7.07 | 7.02 | 7.65 | 8.11 | 7.45 | 6.65 | 6.43 |
| same in cycles at 1.8 GHz | 1.3 | 3.0 | 9.5 | 12.7 | 12.6 | 13.8 | 14.6 | 13.4 | 12.0 | 11.6 |
| nVHE minus kvm-off | 0.03 | 0.10 | 0.21 | 0.06 | 0.16 | 0.01 | 0.24 | 0.16 | -0.22 | -0.19 |
| N80 Exp A walks per access (derived/device-tables.md) | 0.19 | 0.45 | 0.84 | 0.97 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

64 MB: mean pkvm over mean kvm-off is +3.25% (the paper's figure); over nVHE +3.88%, over VHE +3.82%; median ratios +3.40% to +3.61%.
