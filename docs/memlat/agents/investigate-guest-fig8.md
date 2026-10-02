# 调查代理报告：guest-fig8

> 这是多代理调查阶段的原始报告，英文原文照录。它的结论在使用前还要经过独立核查，
> 核查结果见同目录下的 verify-*.md。

## Headline

Figure 8's three N90 series are 10-iteration MEAN ratios built from the four results/xkernel-n90-* directories (pVM/nVHE, pVM/VHE, NP/nVHE); my independent re-parse of the raw reports reproduces docs/vm-ratio-comparison.csv to 5e-7 percentage points. In random access the dataset labelled pVM is 26-32% faster at 3-6 MB, 22% at 8 MB and 17-21% at 12-64 MB than both regular-VM baselines in every one of its 10 iterations (100/100 measurements, no state switching), while the NP VM is within -1.3..+3.6% (means) / -0.6..+0.8% (medians) of baseline. That pVM guest is also 8-32 ns FASTER than the bare-metal kvmoff host, and its complete fingerprint (same shift of the random curve, bw_mem at 4-8 MB, par_mem, LLC-boundary sequential latency, lat_ctx) is reproduced by a HOST-only run in nVHE mode with no pKVM and no guest (n90-nvhe-noisy-full) and shows up sporadically in every other dataset including kvmoff, so the 'negative overhead' is a machine/run state and not evidence of a property of protected VMs. No host-side record (kvm-arm.mode, crosvm command, pvmfw, pinning, THP, memory backing, host kernel) exists for any guest run; the pVM run was on a different day and boot, is the only one showing host interference on one vCPU, and carries the ENV_TAG of the NP run.

## Findings

### guest-fig8#1 (MEASURED, confidence high)

Figure 8 N90 series = ratio of 10-iteration MEANS: 'pVM/nVHE' = results/xkernel-n90-pkvm-pvm-20260605-163040 over results/xkernel-n90-kvm-nvhe-20260606-133103; 'pVM/VHE' = same numerator over results/xkernel-n90-kvm-vhe-20260605-201819; 'NP VM/nVHE' = results/xkernel-n90-pkvm-np-clean-20260606-164648 over the nVHE set; overhead = 100*(mean_num-mean_den)/mean_den; both panels use stride 16 ('Memory load latency' and 'Random load latency' blocks of the lmbench report). NP VM/VHE is not plotted.

Evidence: scripts/build-vm-ratio-comparison.py:46-74 (datasets), 106-122 (RATIOS), 288-289 (mean), 301-304 (pct); docs/vm-lmbench-methodology.zh-CN.md:99; paper P159 (10 repetitions averaged). wf1/guest-fig8/verify_csv.py: for the 66 stride-16 rows, docs/vm-ratio-comparison.csv delta_pct equals my recomputation from raw iter files (independent parser load.py, cross-checked identical to parse-lmbench.py on 263 keys x 8 datasets) with max abs difference 5e-7 pp; median-based ratios differ by up to 29.7 pp. Visible figure points match mean values only (virtCCA sequential peak +7.31% at 16 MB and +2.29% at 1 MB, random +222.2% at 64 MB; pVM/nVHE +21.5% at 0.047 MB, pVM/VHE +14.5% at 0.031 MB). No plotting script found in the repo or ~/Documents.

### guest-fig8#2 (MEASURED, confidence high)

Random access, stride 16: the pVM dataset is faster than both baselines at every size from 3 MB up. Mean-based (as plotted) pVM/nVHE: -26.4% (3 MB), -31.2% (4), -31.7% (6), -22.5% (8), -20.0% (12), -18.7% (16), -16.7% (24), -20.7% (32), -19.6% (48), -20.2% (64). pVM/VHE: -25.7, -30.9, -29.8, -19.7, -19.5, -18.8, -20.4, -19.2, -21.4, -20.3. Median-based values at 12-64 MB are -20.1..-21.5% (nVHE) and -20.1..-21.7% (VHE). The visual reading is therefore refined to: 26-32% faster at 3-6 MB, about 22% at 8 MB, 17-21% at 12-64 MB; the effect starts at 3 MB (2 MB is -5.5%), not at 10 MB, and the paper's '10%-20% above 10 MB' understates it.

Evidence: wf1/guest-fig8/curves.py, final_tables.py (table 2). Absolute 64 MB means: pVM 153.24, nVHE 191.94, VHE 192.14, NP 189.54 ns. stats.py: at every size 3-64 MB the pVM and nVHE/NP value ranges do not overlap; exact two-sided permutation p = 1.08e-5 (2/C(20,10)); bootstrap 95% CI of the mean ratio at 64 MB pVM/nVHE [-20.48,-19.79]%, at 4 MB [-32.06,-30.29]%.

### guest-fig8#3 (MEASURED, confidence high)

NP VM is equal to the regular-VM baselines in random access: NP/nVHE at 3-64 MB is -1.25..+3.62% on means and -0.56..+0.75% on medians; NP/VHE is -2.22..+3.05% (means), -0.69..+2.28% (medians). The larger mean excursions (+3.6% at 24 MB, +3.1% NP/VHE at 8 MB) come from single fast outliers in the baseline sets, not from NP. The paper sentence that 'KylinX各模式' show the negative overhead is wrong for NP.

Evidence: final_tables.py table 2; stats.py: NP vs nVHE permutation p = 0.94 (3 MB), 0.17 (8 MB), 0.68 (16 MB), 0.21 (64 MB). Outliers: nVHE 24 MB iterations 2/6/9 = 158.4/162.5/153.3 ns vs 184-186 otherwise; VHE 8 MB iteration 1 = 97.8 vs 123.6-126.6.

### guest-fig8#4 (MEASURED, confidence high)

Sequential access, stride 16: every N90 series stays within +-1%. pVM/nVHE ranges from -0.98% (4 MB) to +0.99% (48 MB); pVM/VHE -0.95..+0.84%; NP/nVHE -0.15..+0.21%; NP/VHE -0.02..+0.32%. The pVM curve dips at 4 and 6 MB (-1.0%, -0.7%) and shows a +0.3..0.5% saw-tooth on alternate sizes below 2 MB.

Evidence: final_tables.py table 3 (all 33 sizes, means and medians). Values are 2.225-2.379 ns throughout because stride 16 is fully prefetched.

### guest-fig8#5 (MEASURED, confidence high)

Per-iteration stability: the pVM random values do not switch state. All 100 measurements (10 sizes 3-64 MB x 10 iterations) sit on the fast curve, CV 0.65-2.06% per size. The three other guest sets sit on the normal curve with sporadic single excursions to the fast or an intermediate level, only at 8 MB and above: VHE 3/100 (8 MB i1 = 97.8, 12 MB i2 = 130.0, 16 MB i5 = 151.4), nVHE 6/100, NP 6/100.

Evidence: wf1/guest-fig8/periter.py, states.py (tables 4 and 5). Classification s = (normal - v)/(normal - fast), FAST if s >= 0.75, MID 0.25-0.75: pVM F=100; VHE F=2 M=1; nVHE F=3 M=3; NP M=6.

### guest-fig8#6 (MEASURED, confidence high)

The +-10..20% spikes of all N90 series at 0.03-0.06 MB in the random panel are not overheads: at the L1D boundary each dataset's per-iteration values are bimodal (about 2.23 ns vs 4.3-5.5 ns) and the mean estimator turns different mode counts into large ratios.

Evidence: periter.out: size 0.03125 MB: nVHE 8 iterations at 2.226 and 2 at 5.44; NP 9 at 2.227 and 1 at 5.47; pVM 9 at ~2.23 and 1 at 5.54. Size 0.04688 MB: VHE 6 of 10 at 4.4-5.3, nVHE 3, NP 5, pVM 5. Median-based ratios at 0.03125 MB are +0.2% or less.

### guest-fig8#7 (MEASURED, confidence high)

Absolute random latency: the three regular guests are slower than the host, the pVM guest is faster than the host. Medians at 4/8/16/64 MB (ns): host kvmoff 47.59/112.54/168.54/185.23; host vhe 47.45/112.32/169.71/185.43; host nvhe 47.69/112.60/168.56/185.05; host pkvm(try2) 49.31/119.59/176.28/191.73; guest VHE 51.84/124.97/176.90/192.94; guest nVHE 52.30/126.83/176.73/192.00; guest NP 52.62/126.53/177.05/192.35; guest pVM 35.97/97.85/141.20/152.91. Guest minus same-mode host: VHE +4.4/+12.6/+7.2/+7.5; nVHE +4.6/+14.2/+8.2/+7.0; NP minus host pkvm +3.3/+6.9/+0.8/+0.6 (NP minus kvmoff +5.0/+14.0/+8.5/+7.1); pVM minus host pkvm -13.3/-21.7/-35.1/-38.8; pVM minus kvmoff -11.6/-14.7/-27.3/-32.3.

Evidence: wf1/guest-fig8/host_vs_guest.py and final_tables.py (table 6), from results/n90-day3-host/*.csv (verified identical to the raw iter files) and the guest raw reports.

### guest-fig8#8 (INFERRED, confidence high)

A guest that is 7.6 ns (3 MB) to 32 ns (64 MB) faster than the same machine with KVM off cannot be explained by a cheaper stage-2 path: a perfect stage 2 can at best equal native. The pVM advantage is therefore not a virtualization-efficiency effect.

Evidence: Table 6: G pVM - H kvmoff = -7.60, -11.62, -11.80, -14.69, -25.17, -27.34, -29.98, -30.43, -31.59, -32.33 ns at 3..64 MB (medians). L1 latency is identical (guest 2.226 ns, host 2.223 ns), so clock or frequency differences are excluded.

### guest-fig8#9 (MEASURED, confidence high)

The same fast curve exists in a host-only dataset with kvm-arm.mode=nvhe (no pKVM, benchmark pinned to cpu0): results/n90-day3-host/n90-nvhe-noisy-full-* is on it in all 10 iterations: 26.4/30.8/48.6/83.9/121.8/134.2/143.1/146.2/149.1/150.1 ns at 3..64 MB versus 36.6/47.7/67.4/112.6/154.8/168.6/177.5/180.8/182.4/185.0 for the clean nVHE host. The normal-minus-fast shift is the same in host and guest: host +10.2/+16.9/+18.7/+28.7/+33.0/+34.3/+34.4/+34.6/+33.3/+34.9 ns, guest (NP minus pVM) +10.4/+16.7/+25.3/+28.7/+35.3/+35.9/+38.7/+39.0/+40.4/+39.4 ns. Predicting the pVM curve as 'NP curve minus the host shift' has mean absolute error 3.1 ns (3.0%), against 31.5% for 'pVM = NP'. Below 3 MB neither pair differs.

Evidence: wf1/guest-fig8/survey.py, states.py (host table: nvhe-noisy F=100/100), final_tables.py (table 7). Kernel cmdline of the noisy run: results/n90-day3-host/n90-nvhe-noisy-full-20260603-161758-summary.txt (kvm-arm.mode=nvhe, cores=0, cpu_max_freqs 1900000 x8).

### guest-fig8#10 (MEASURED, confidence high)

The fingerprint matches across unrelated benchmarks. Host noisy-vs-clean nVHE next to guest pVM-vs-NP (medians): bw_mem_wr 4 MB +19.5% / +19.9%; bw_mem_wr 8 MB +16.7% / +21.0%; bw_mem_rd 8 MB +15.9% / +23.9%; bw_mem_cp 4 MB +12.1% / +17.0%; par_mem 4 MB -23.2% / -22.6%, 8 MB -26.7% / -27.7%, 16 MB -23.9% / -23.0%; sequential stride 128 at 3/4/6 MB -7.5/-9.3/-10.8% / -9.2/-11.2/-18.5%; lat_ctx 64K x 96 procs -11.8% / -18.0%; bw_mem_wr 256 KB -21.5% / -16.1%. Pearson r between the two delta vectors over the 33 random sizes is 0.84. Differences: the noisy host additionally shows contention effects the pVM guest lacks (sequential >=12 MB +6..13% slower, lat_tcp/udp +25%).

Evidence: wf1/guest-fig8/signature.py, fingerprint.py, fp_periter.py (table 8). In the pVM set every one of these fingerprint metrics is in the fast mode in all 10 iterations (e.g. bw_mem_wr 4 MB 20995-21052 MB/s vs 17492-17610 in the other three guests).

### guest-fig8#11 (DOCUMENTED, confidence medium)

The internal docs describe the conditions of two host fast-state episodes. The 'noisy' nVHE run was taken with incomplete service masking, with pvm-manage and Kylin AI services running. A first pKVM host run ('try1') switched at iteration 4 from about 194 ns to 154 ns at 64 MB and stayed there for the remaining iterations; an identical re-run (try2) and standalone runs did not reproduce it. The try1 curve quoted in the docs (26.87/31.89/49.87/91.01/128.1/140.4/147.4/150.2/151.2/154.4 ns at 3..64 MB) is within 1-7 ns of the pVM guest curve at every size.

Evidence: docs/n90-kvm-host/SUMMARY.md:296-297; docs/n90-kvm-host/nvhe.md:9-12; docs/n90-kvm-host/standalone-memory-bench-validation.md:29-40 and 361-372; docs/n90-kvm-host/pkvm-memory-access-speedup.md:42-56 (that doc is marked retracted). The try1 raw files are not in the repo or its git history, so these numbers could not be recomputed.

### guest-fig8#12 (MEASURED, confidence high)

The fast level is not confined to those runs: it appears sporadically in every clean dataset, including the host with KVM off. Host 12-64 MB cells that are fast or intermediate: kvmoff 15/60, vhe 5/60, nvhe 7/60, pkvm(try2) 4/60; at 3-8 MB 0/160. The separate standalone host logs show the same (kvmoff 32 MB run 6 = 151.3 ns vs 181; vhe 16 MB run 10 = 134.5 vs 170; pkvm 16 MB run 3 = 140.4 vs 177). In addition the LLC-boundary sequential latency (8 MB) is bimodal per measurement in every clean host and guest dataset (stride 128: about 9.0-9.4 vs 11.0-11.5 ns; stride 256: about 9.9-10.7 vs 12.2-12.6 ns) while the pVM guest and the noisy host are in the low mode 10/10.

Evidence: wf1/guest-fig8/states.py, standalone.py, and the 8 MB per-iteration listing (tables 5 and 9). Adjacent-size clustering of the sporadic cells within an iteration is not significant (8 adjacent pairs observed vs 5.0 expected, permutation p = 0.10, clustering.py), so they may be per-process rather than time-window events.

### guest-fig8#13 (MEASURED, confidence high)

The pVM run is the only guest run with host-side interference on the benchmark CPU. Pure-core metrics have CV 0.7-1.6% in the pVM set (integer_add 1.13%, integer_div 1.08%, double_add 1.33%, null syscall 1.59%, L1 load latency 0.68%) and 0.00% in the other three guest sets; 26.1% of L1-range lat_mem_rd points are more than 0.15% above the minimum in pVM versus 0.0% elsewhere (max 2.294 vs 2.226 ns). The perturbed points alternate strictly with measurement order: in 64 of 70 (iteration x stride) blocks they lie on one parity only (6 of 364 perturbed points on the other parity) and the parity flips in 60 of 60 transitions between 33-size blocks. This is the signature of benchmark children alternating between two vCPUs of which one is disturbed.

Evidence: wf1/guest-fig8/noise_probe.py, alternation.py (table 10). Mechanism of alternation is DOCUMENTED: x-kernel assigns new tasks round-robin over CPU_NUM=2 run queues (x-kernel 9bab5da3 task/ktask/src/run_queue.rs:110-122; platforms/aarch64-crosvm-virt/defconfig:16; docs/vm-lmbench-methodology.zh-CN.md:268-303). The fast memory state itself is present on both vCPUs.

### guest-fig8#14 (DOCUMENTED, confidence high)

What the result directories record about the four runs: identical lmbench config (CONFIG.xkernel.used md5 40b058db... in all four), identical environment.txt (md5 191468761a...: MemTotal 1999956 kB, MemFree 1802388 kB, Cached 524 kB, same /dev list incl. dice and firmware-dtb, same mounts), identical report header (uname 'Linux kylin-x 10.0.0', BusyBox 1.37.0), CORES=0 ITERS=10 DMA_SIZE_M=128. Recorded differences are only the ENV_TAG and the guest-clock times: pVM 06-05 05:31:53-08:28:53 UTC (first run), VHE 06-05 09:16:53-12:17:46, nVHE 06-06 02:30:07-05:30:23, NP 06-06 05:47:06-08:46:00. The pVM directory's ENV_TAG and file prefix are 'xkernel-pkvm-np', the same as the NP run. Not recorded anywhere: host kvm-arm.mode (only implied by directory names), host kernel version, crosvm command line, whether pvmfw was used, vCPU pinning, host THP settings, guest memory backing, x-kernel commit.

Evidence: results/xkernel-n90-*/{started.txt,completed.txt,autorun.marker,environment.txt,CONFIG.xkernel.used} (md5sum comparison run by me); docs/vm-lmbench-methodology.zh-CN.md:26-35, 56-62, 107-119, 264-266, 305-328. Since kvm-arm.mode is a boot parameter, the pVM and NP runs were necessarily in different boots with two other boots in between (INFERRED).

### guest-fig8#15 (INFERRED, confidence medium)

The host CPU-frequency lock of prepare-host.sh was in effect during all four guest runs, so the same script's top-level THP=never setting was probably applied too.

Evidence: Guest L1 load latency is 2.225-2.226 ns in all four sets, equal to the host value under the 1.9 GHz lock (2.223 ns); day-1 host data at the 2.1 GHz lock gives 1.906 ns (results/n90-day1/n90-host-cpu0-iter1.txt). prepare-host.sh:21-33 sets the frequency and :41-42 writes 'never' to /sys/kernel/mm/transparent_hugepage/enabled in the same run. The THP state itself was not recorded.

### guest-fig8#16 (DOCUMENTED, confidence medium)

The only launch script for an x-kernel protected VM that exists locally starts it through pvm-manage without any CPU pinning: pvm-manage run --protected-vm-with-pvmfw -- --cpus 2 --mem size=2048 --block disk.img --vsock 3 kernel.bin, which pvm-manage turns into crosvm --log-level debug run --disable-sandbox --protected-vm-with-firmware ./custom_pvmfw plus an extra instance block device and a device-tree overlay. No script for the NP, nVHE or VHE x-kernel runs exists in any local repo; the old launch script for Linux guests (deleted) used taskset -c 0,1 on the whole crosvm process, --no-balloon and no hugepage option.

Evidence: kylin100-xkernel-boots/scripts/start_xkernel_pvm.sh (last line); kylin100-xkernel-boots/pvm-manage/src/main.rs:200-230; kylin-lmbench git show 9e3f55de^:guest/launch-guest.sh; docs/vm-lmbench-methodology.zh-CN.md:116-118 and 322 (run-crosvm-n80.sh not found). Whether the June pVM run used this path is not recorded.

### guest-fig8#17 (DOCUMENTED, confidence high)

Kernel code gives protected and non-protected guests the same stage-2 mapping granularity. With pKVM enabled every non-permission stage-2 fault of either VM type goes through pkvm_mem_abort, which maps a 2 MB block only when the VMM's own mapping of the guest memory is a PMD-level huge page; EL2 then calls donate (pVM) or share (NP) with the same nr_pages, and neither EL2 implementation forces page granularity for guests. Without pKVM, user_mem_abort applies the same THP test. So block mappings depend on how crosvm's memory is backed on the host, not on protection.

Evidence: klinux at the 6.6.0-73 commit 1e6773d13b560 (the host kernel version in the host summaries): arch/arm64/kvm/mmu.c:2279-2283 (dispatch), 1697-1766 (pkvm_mem_abort, FOLL_LONGTERM for all guests at :1705, transparent_hugepage_adjust at :1766); HEAD mmu.c:1495-1545, 1779-1791, 2073-2079, 2303-2307. C EL2: arch/arm64/kvm/hyp/nvhe/hyp-main.c:1089-1092, mem_protect.c:199-203, 1674-1705, 1852-1882. Rust EL2: xhypervisor/src/hyp_main.rs:1075-1081, mem_protect/guest.rs:487-489, 1111-1119, 1165-1217, mem_protect/host.rs:1579-1626, permissions.rs:659-709. Host kernel of the guest runs is unrecorded.

### guest-fig8#18 (INFERRED, confidence medium)

Larger TLB entries are not the reason the pVM guest is fast. x-kernel maps anonymous private mmap memory with 4 KiB pages, one page per fault, and lmbench's tlb test reports 48 pages in all 40 guest iterations including the 10 pVM ones, so the effective translation granule in the pVM guest is 4 KiB regardless of stage-2 block size.

Evidence: DOCUMENTED part: x-kernel 9bab5da3 (mainline at test time; actual commit unrecorded) posix/mm/src/mmap.rs:166-172 and 197-203, mm/memspace-file/src/cow.rs:93-111 and 301-307, mm/memspace/src/aspace.rs:467-484; CONTIGUOUS bit defined but unused (mm/page_table/src/arch/aarch64.rs:36). MEASURED part: 'tlb: 48 pages' in 10/10 iterations of each guest set and 50/50 host iterations. Identical MemTotal/MemFree in the four environment.txt files suggests the same guest image.

### guest-fig8#19 (DOCUMENTED, confidence medium)

The host preparation and verification scripts control only the top-level THP switch, while the kernel tree has per-size anonymous and shmem THP controls that the top-level 'never' does not override when a size is set to 'always'. The recorded 'THP=never' therefore does not by itself prove the absence of large folios; by default (no thp_anon= on the recorded host command lines) only the PMD size inherits the top-level setting and shmem THP is off.

Evidence: kylin-lmbench prepare-host.sh:41-42, scripts/verify-clean-env.sh:50-53; klinux include/linux/huge_mm.h:283-296 (mask starts from huge_anon_orders_always unconditionally), mm/huge_memory.c:753-754 and 945-1028 (defaults, thp_anon=), mm/shmem.c:545 (shmem_huge default never), include/linux/huge_mm.h:67 (per-size shmem_enabled). The same code is present at commit 1e6773d13b560. The sysfs state on the N90 was not read.

### guest-fig8#20 (INFERRED, confidence low)

The size dependence of the normal-minus-fast shift is described by about 35 ns x (1 - 512 pages / working-set pages): zero up to 2 MB, then rising and saturating at 33-35 ns (host) or 39-40 ns (guest). This fits a per-access cost that applies once the working set exceeds 512 pages (2 MB), such as a second-level TLB miss, but equally a fixed adder for accesses that leave a 2 MB region; the data do not separate the two. Because the guest-minus-host offset is about the same in both states (+2.6..+14 ns), translation misses are probably still occurring in the fast state.

Evidence: Table 7 (model column vs measured shifts: 11.7/17.5/23.3/26.2/29.2/30.6/32.1/32.8/33.5/33.9 predicted vs host 10.2/16.9/18.7/28.7/33.0/34.3/34.4/34.6/33.3/34.9). lat_mem_rd -t visits a different page on every load and its traversal order equals first-touch order (src/lib_mem.c:129-175, 206-273), and each size runs in a fresh child that mallocs the full 64 MB. The FTC862 second-level TLB size is undocumented.

### guest-fig8#21 (INFERRED, confidence medium)

Evidence-ranked explanations for pVM versus regular VM in random access: (1) a run-level 'fast memory state' of the machine unrelated to protection, which the pVM run was in for its whole 3 hours: strongly supported. Its physical nature is open; sub-candidates are (1a) large-folio backing that survives the top-level THP=never, (1b) physically contiguous versus scattered page allocation on the host (and hence host-contiguous guest memory), (1c) an SoC or memory power/clock state that depends on other activity. (2) pVM-specific stage-2 block mapping: contradicted by code symmetry, by the 4 KiB guest stage 1 and by the guest being faster than bare metal; at most a co-factor worth a few ns. (3) a different guest kernel build for the pVM: contradicted by identical environment.txt and header. (4) mislabelled dataset: cannot be excluded for the label, but the run is not a copy of NP (I/O bandwidth 12-18% lower, page-fault low mode 64 vs 79-81 us) and mislabelling would not explain the speed-up. (5) clock or frequency artefact: excluded.

Evidence: Findings above; table 12 lists for each candidate the supporting and opposing evidence and the measurement that would decide it.

### guest-fig8#22 (MEASURED, confidence high)

Related host numbers of Figure 7 are reproduced exactly by mean ratios and are affected by the same bimodality. 'LLC Bnd +3.55/-3.0/+2.9' = sequential stride 256 at 8 MB, pkvm vs kvmoff/vhe/nvhe = +3.55%/-3.02%/+2.87%; this metric is bimodal per iteration in every mode (about 10.0-10.7 vs 12.2-12.6 ns), the low-mode count is 6/10 kvmoff, 4/10 pkvm, 2/10 vhe, 5/10 nvhe, and the pkvm-kvmoff difference of +0.40 ns has exact permutation p = 0.40. 'Rand Mem +3.25/+3.8/+3.9' = random 64 MB means (+3.25%/+3.82%/+3.88%); the medians give +3.51%/+3.40%/+3.61% (+6.3..6.7 ns) and the mean-based p-values are only 0.07-0.09 because sporadic fast cells inflate the variance, although the normal-state values are cleanly separated (pkvm 191.1-193.1 vs kvmoff 184.7-186.8 ns).

Evidence: Computation on results/n90-day3-host/*.csv in this session: means stride256 8 MB kvmoff 11.203, nvhe 11.276, vhe 11.961, pkvm 11.600 ns; random 64 MB means 182.209/181.104/181.207/188.135, medians 185.233/185.045/185.428/191.730. Standalone logs confirm the 8 MB bimodality in all four modes (results/standalone-mem-bench/*.log, standalone.py).

### guest-fig8#23 (DOCUMENTED, confidence high)

The internal documentation never endorsed the pVM speed-up: the overall summary compares only VHE, nVHE and the NP run and reports random 64 MB as +0.17% for pKVM(NP) vs nVHE; the methodology document lists the pVM 64 MB random ratio 0.798 as unexplained and warns that the dataset label must be confirmed before use. The same fast-state fingerprint also underlies other pVM 'gains' quoted in the paper for Figures 9 and 10 (context switch at 96 processes -10..-20%, LLC boundary -10%).

Evidence: docs/lmbench-overall-summary.zh-CN.md:100-136; docs/vm-lmbench-methodology.zh-CN.md:187, 195, 264-266; paper.txt P164 and P167. MEASURED support: lat_ctx 64K/96p medians VHE 15.25, nVHE 15.36, NP 15.28, pVM 12.53 us, against host nVHE clean 11.75 vs noisy 10.37 us.

## Caveats

- No device was contacted; everything rests on files in the repos. The live sysfs state of the N90 (THP knobs, idle states, crosvm options) was therefore not read.
- There is no host-side record for any of the four guest runs. kvm-arm.mode, host kernel, crosvm command line, pvmfw use, vCPU pinning, THP settings and memory backing are known only from directory names, a config comment, and staff recollection quoted in docs/vm-lmbench-methodology.zh-CN.md. Whether the dataset labelled pVM was really a protected VM cannot be verified from the repo.
- The physical mechanism of the fast state is not established. The three sub-candidates (large folios, physical page placement, power or clock state) are inferences; none explains every observation, and the 35 ns x (1 - 512/pages) description is a fit, not a demonstrated TLB effect.
- Host pKVM 'try1' numbers are quoted from internal docs; the raw files are absent from the repo and its git history. One of those docs (pkvm-memory-access-speedup.md) is explicitly retracted.
- x-kernel source was read at commit 9bab5da3 (mainline at test time according to the methodology doc); the commit actually run is unrecorded. The kernel source for the host was read at the commit tagged 6.6.0-73.76, the version recorded in the host-test summaries two days before the guest runs; the kernel booted for the guest runs is unrecorded.
- crosvm behaviour (memfd backing, effect of --protected-vm on memory population) was not checked against source; only option names in the prebuilt binary and the pvm-manage wrapper were inspected, and that binary is from a later repo snapshot.
- Each dataset is a single 3-hour run of 10 iterations in one boot. Iterations within a run are not independent replicates of the run-level condition, so the permutation p-values quantify separation between two runs, not between VM types.
- Mean-based ratios (the paper's estimator) are sensitive to the sporadic fast cells and to bimodal metrics; medians are given alongside. lmbench reports the minimum over repetitions for each size, which makes a measurement look fast if any one repetition was fast.
- The adjacent-size clustering test for sporadic fast cells is not significant (p = 0.10), so whether they are time-window events or per-process events is unresolved.
- The noisy nVHE host run also contains genuine contention effects (large sequential sizes and TCP/UDP slower) that the pVM guest does not show; the match concerns the fast-state fingerprint only.

## Open questions

- What is the fast state physically? Needs PMU counters (l2d_tlb_refill, l3d_cache_refill, stall_backend per load) and a pagemap PFN dump of the lat_mem_rd buffer in a fast and a normal run on the same boot.
- What was different on the host during the pVM run (06-05 13:31-16:28 local): launched through pvm-manage with --log-level debug and no pinning? service masks not applied? first VM after boot? The interference on one vCPU says something was, but nothing is recorded.
- Do per-size THP knobs (hugepages-*/enabled, shmem_enabled) on the N90 differ from the defaults, and does any Kylin service or pvm-manage change them after prepare-host.sh has run?
- Does a pVM still beat an NP VM when both are started alternately in the same boot under an identical, recorded host state? If not, the Figure 8 random-panel claim (and the related pVM gains in Figures 9 and 10) should be withdrawn or restated as NP-equal.
- Is the dataset in xkernel-n90-pkvm-pvm-20260605-163040 really a protected VM with pvmfw, given its ENV_TAG is xkernel-pkvm-np?
- Why is random access at 3-6 MB (within the 8 MiB L3) 10-18 ns slower in the normal state; is the knee at 2 MB the second-level TLB reach (512 x 4 KiB) or an L3 property of the FTC862?
- Why does the fast state never appear at 3-8 MB random in clean runs (0/280) while the LLC-boundary sequential latency is in its low mode 20-70% of the time?

## Tables

All numbers computed in this session from raw per-iteration lmbench reports (scripts under wf1/guest-fig8). Guest sets: VHE = xkernel-n90-kvm-vhe-20260605-201819, nVHE = xkernel-n90-kvm-nvhe-20260606-133103, NP = xkernel-n90-pkvm-np-clean-20260606-164648, pVM = xkernel-n90-pkvm-pvm-20260605-163040. Host sets: results/n90-day3-host (kvmoff, vhe, nvhe, pkvm = try2, and nvhe-noisy).

### Table 1. What Figure 8 plots (verification)

| Figure series | numerator | denominator | estimator | check |
|---|---|---|---|---|
| N90 KylinX pVM/nVHE | pkvm-pvm | kvm-nvhe | 100 x (mean10 / mean10 - 1) | equals vm-ratio-comparison.csv to 5e-7 pp (66 rows) |
| N90 KylinX pVM/VHE | pkvm-pvm | kvm-vhe | same | same |
| N90 KylinX NP VM/nVHE | pkvm-np-clean | kvm-nvhe | same | same |
| (not plotted) NP VM/VHE | pkvm-np-clean | kvm-vhe | same | computed here |
| median-based alternative | | | | differs from the CSV by up to 29.7 pp (0.047 MB) |

### Table 2. Random load latency, stride 16: mean and median of 10 iterations (ns) and overhead (%). Mean-based columns are what Figure 8 plots.

| size MB | VHE mean | nVHE mean | NP mean | pVM mean | VHE med | nVHE med | NP med | pVM med | pVM/nVHE mean% | pVM/VHE mean% | NP/nVHE mean% | NP/VHE mean% | pVM/nVHE med% | pVM/VHE med% | NP/nVHE med% | NP/VHE med% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00049 | 2.225 | 2.226 | 2.226 | 2.234 | 2.225 | 2.226 | 2.226 | 2.228 | +0.40 | +0.42 | +0.02 | +0.04 | +0.11 | +0.13 | +0.02 | +0.04 |
| 0.00098 | 2.225 | 2.226 | 2.226 | 2.226 | 2.225 | 2.226 | 2.226 | 2.226 | +0.02 | +0.05 | +0.01 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.00195 | 2.225 | 2.226 | 2.226 | 2.234 | 2.225 | 2.226 | 2.226 | 2.230 | +0.38 | +0.40 | +0.02 | +0.04 | +0.18 | +0.22 | +0.00 | +0.04 |
| 0.00293 | 2.225 | 2.226 | 2.226 | 2.227 | 2.225 | 2.226 | 2.226 | 2.226 | +0.03 | +0.07 | +0.01 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.00391 | 2.225 | 2.226 | 2.226 | 2.232 | 2.225 | 2.226 | 2.226 | 2.229 | +0.28 | +0.31 | +0.02 | +0.04 | +0.16 | +0.20 | +0.00 | +0.04 |
| 0.00586 | 2.225 | 2.226 | 2.226 | 2.226 | 2.225 | 2.226 | 2.226 | 2.226 | +0.01 | +0.05 | +0.00 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.00781 | 2.225 | 2.226 | 2.226 | 2.232 | 2.225 | 2.226 | 2.226 | 2.229 | +0.30 | +0.33 | +0.01 | +0.04 | +0.16 | +0.20 | +0.00 | +0.04 |
| 0.01172 | 2.225 | 2.226 | 2.226 | 2.226 | 2.225 | 2.226 | 2.226 | 2.226 | +0.00 | +0.05 | +0.00 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.01562 | 2.225 | 2.226 | 2.226 | 2.235 | 2.225 | 2.226 | 2.226 | 2.228 | +0.40 | +0.44 | +0.00 | +0.04 | +0.09 | +0.13 | +0.00 | +0.04 |
| 0.02344 | 2.256 | 2.226 | 2.226 | 2.227 | 2.226 | 2.226 | 2.226 | 2.226 | +0.02 | -1.33 | +0.00 | -1.34 | +0.00 | +0.00 | +0.00 | +0.00 |
| 0.03125 | 2.249 | 2.881 | 2.551 | 2.576 | 2.226 | 2.226 | 2.227 | 2.231 | -10.58 | +14.54 | -11.45 | +13.42 | +0.22 | +0.22 | +0.04 | +0.04 |
| 0.04688 | 3.713 | 2.981 | 3.484 | 3.621 | 4.379 | 2.228 | 3.266 | 3.267 | +21.46 | -2.48 | +16.88 | -6.15 | +46.63 | -25.39 | +46.61 | -25.40 |
| 0.0625 | 4.860 | 5.369 | 5.235 | 4.936 | 4.883 | 5.610 | 5.689 | 4.679 | -8.06 | +1.57 | -2.48 | +7.73 | -16.59 | -4.17 | +1.41 | +16.51 |
| 0.09375 | 6.878 | 7.071 | 7.178 | 6.933 | 6.958 | 7.117 | 7.077 | 6.904 | -1.95 | +0.80 | +1.51 | +4.36 | -3.01 | -0.78 | -0.57 | +1.71 |
| 0.125 | 7.475 | 7.711 | 7.668 | 7.658 | 7.689 | 7.725 | 7.726 | 7.732 | -0.70 | +2.44 | -0.56 | +2.58 | +0.08 | +0.55 | +0.02 | +0.49 |
| 0.1875 | 7.764 | 7.760 | 7.892 | 7.768 | 7.753 | 7.767 | 7.779 | 7.760 | +0.10 | +0.06 | +1.69 | +1.65 | -0.10 | +0.08 | +0.15 | +0.34 |
| 0.25 | 7.979 | 7.934 | 8.135 | 8.261 | 7.851 | 7.851 | 7.986 | 8.043 | +4.12 | +3.54 | +2.54 | +1.96 | +2.44 | +2.43 | +1.72 | +1.71 |
| 0.375 | 9.292 | 8.936 | 9.764 | 9.024 | 9.296 | 8.805 | 9.943 | 8.980 | +0.99 | -2.88 | +9.27 | +5.08 | +1.99 | -3.40 | +12.92 | +6.95 |
| 0.5 | 12.732 | 11.889 | 12.146 | 11.820 | 12.674 | 11.759 | 12.293 | 11.909 | -0.58 | -7.16 | +2.16 | -4.60 | +1.28 | -6.04 | +4.55 | -3.00 |
| 0.75 | 16.849 | 17.044 | 16.955 | 17.190 | 16.770 | 17.001 | 17.075 | 17.258 | +0.86 | +2.02 | -0.52 | +0.63 | +1.52 | +2.91 | +0.44 | +1.82 |
| 1 | 19.633 | 19.662 | 19.583 | 19.753 | 19.594 | 19.701 | 19.577 | 19.730 | +0.46 | +0.61 | -0.40 | -0.25 | +0.14 | +0.69 | -0.63 | -0.09 |
| 1.5 | 21.066 | 20.930 | 21.058 | 20.824 | 21.261 | 20.832 | 20.870 | 20.837 | -0.50 | -1.15 | +0.61 | -0.04 | +0.02 | -2.00 | +0.18 | -1.84 |
| 2 | 24.069 | 23.872 | 23.593 | 22.549 | 23.694 | 23.956 | 23.761 | 22.385 | -5.54 | -6.31 | -1.17 | -1.98 | -6.56 | -5.52 | -0.81 | +0.28 |
| 3 | 39.231 | 39.601 | 39.586 | 29.135 | 39.391 | 39.441 | 39.439 | 28.999 | -26.43 | -25.73 | -0.04 | +0.91 | -26.47 | -26.38 | -0.00 | +0.12 |
| 4 | 51.911 | 52.180 | 52.602 | 35.891 | 51.840 | 52.303 | 52.625 | 35.972 | -31.22 | -30.86 | +0.81 | +1.33 | -31.22 | -30.61 | +0.61 | +1.52 |
| 6 | 79.106 | 81.267 | 80.783 | 55.529 | 78.875 | 81.126 | 80.675 | 55.337 | -31.67 | -29.80 | -0.60 | +2.12 | -31.79 | -29.84 | -0.56 | +2.28 |
| 8 | 122.511 | 126.980 | 126.248 | 98.419 | 124.971 | 126.829 | 126.526 | 97.855 | -22.49 | -19.67 | -0.58 | +3.05 | -22.85 | -21.70 | -0.24 | +1.24 |
| 12 | 160.949 | 161.786 | 164.439 | 129.499 | 164.413 | 165.026 | 164.757 | 129.486 | -19.96 | -19.54 | +1.64 | +2.17 | -21.54 | -21.24 | -0.16 | +0.21 |
| 16 | 174.476 | 174.286 | 176.866 | 141.702 | 176.897 | 176.730 | 177.049 | 141.199 | -18.70 | -18.78 | +1.48 | +1.37 | -20.10 | -20.18 | +0.18 | +0.09 |
| 24 | 185.166 | 176.828 | 183.228 | 147.355 | 185.112 | 184.537 | 185.921 | 147.245 | -16.67 | -20.42 | +3.62 | -1.05 | -20.21 | -20.46 | +0.75 | +0.44 |
| 32 | 186.555 | 189.866 | 187.903 | 150.663 | 187.933 | 189.918 | 189.226 | 150.184 | -20.65 | -19.24 | -1.03 | +0.72 | -20.92 | -20.09 | -0.36 | +0.69 |
| 48 | 192.804 | 188.471 | 188.527 | 151.470 | 192.802 | 191.464 | 191.475 | 151.069 | -19.63 | -21.44 | +0.03 | -2.22 | -21.10 | -21.65 | +0.01 | -0.69 |
| 64 | 192.137 | 191.937 | 189.544 | 153.236 | 192.945 | 192.001 | 192.351 | 152.907 | -20.16 | -20.25 | -1.25 | -1.35 | -20.36 | -20.75 | +0.18 | -0.31 |

### Table 3. Sequential load latency, stride 16: mean and median (ns) and overhead (%)

| size MB | VHE mean | nVHE mean | NP mean | pVM mean | VHE med | nVHE med | NP med | pVM med | pVM/nVHE mean% | pVM/VHE mean% | NP/nVHE mean% | NP/VHE mean% | pVM/nVHE med% | pVM/VHE med% | NP/nVHE med% | NP/VHE med% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00049 | 2.225 | 2.226 | 2.226 | 2.226 | 2.225 | 2.226 | 2.226 | 2.226 | +0.02 | +0.06 | +0.01 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.00098 | 2.225 | 2.225 | 2.226 | 2.233 | 2.225 | 2.225 | 2.226 | 2.228 | +0.36 | +0.38 | +0.03 | +0.04 | +0.11 | +0.11 | +0.04 | +0.04 |
| 0.00195 | 2.225 | 2.226 | 2.226 | 2.226 | 2.225 | 2.226 | 2.226 | 2.226 | +0.01 | +0.05 | +0.00 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.00293 | 2.225 | 2.226 | 2.226 | 2.238 | 2.225 | 2.226 | 2.226 | 2.229 | +0.54 | +0.58 | +0.01 | +0.04 | +0.13 | +0.18 | +0.00 | +0.04 |
| 0.00391 | 2.225 | 2.226 | 2.226 | 2.229 | 2.225 | 2.226 | 2.226 | 2.226 | +0.14 | +0.18 | +0.00 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.00586 | 2.225 | 2.226 | 2.226 | 2.232 | 2.225 | 2.226 | 2.226 | 2.228 | +0.30 | +0.34 | +0.00 | +0.04 | +0.09 | +0.13 | +0.00 | +0.04 |
| 0.00781 | 2.225 | 2.226 | 2.226 | 2.226 | 2.225 | 2.226 | 2.226 | 2.226 | +0.02 | +0.06 | +0.00 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.01172 | 2.225 | 2.226 | 2.226 | 2.232 | 2.225 | 2.226 | 2.226 | 2.229 | +0.26 | +0.31 | +0.00 | +0.04 | +0.13 | +0.18 | +0.00 | +0.04 |
| 0.01562 | 2.225 | 2.226 | 2.226 | 2.227 | 2.225 | 2.226 | 2.226 | 2.226 | +0.02 | +0.07 | +0.00 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.02344 | 2.225 | 2.226 | 2.226 | 2.235 | 2.225 | 2.226 | 2.226 | 2.229 | +0.41 | +0.46 | +0.00 | +0.04 | +0.16 | +0.20 | +0.00 | +0.04 |
| 0.03125 | 2.225 | 2.226 | 2.226 | 2.226 | 2.225 | 2.226 | 2.226 | 2.226 | +0.02 | +0.06 | +0.00 | +0.04 | +0.00 | +0.04 | +0.00 | +0.04 |
| 0.04688 | 2.226 | 2.226 | 2.226 | 2.236 | 2.226 | 2.226 | 2.226 | 2.229 | +0.47 | +0.48 | +0.00 | +0.01 | +0.13 | +0.13 | +0.00 | +0.00 |
| 0.0625 | 2.226 | 2.226 | 2.226 | 2.226 | 2.226 | 2.226 | 2.226 | 2.226 | +0.02 | +0.02 | +0.01 | +0.01 | +0.00 | +0.00 | +0.00 | +0.00 |
| 0.09375 | 2.321 | 2.322 | 2.322 | 2.332 | 2.318 | 2.318 | 2.318 | 2.330 | +0.44 | +0.49 | +0.03 | +0.08 | +0.54 | +0.54 | +0.00 | +0.00 |
| 0.125 | 2.321 | 2.325 | 2.321 | 2.323 | 2.317 | 2.321 | 2.321 | 2.321 | -0.06 | +0.08 | -0.15 | -0.02 | +0.00 | +0.17 | +0.00 | +0.17 |
| 0.1875 | 2.321 | 2.322 | 2.323 | 2.334 | 2.319 | 2.322 | 2.322 | 2.327 | +0.50 | +0.57 | +0.01 | +0.09 | +0.19 | +0.32 | -0.02 | +0.11 |
| 0.25 | 2.321 | 2.325 | 2.329 | 2.326 | 2.319 | 2.325 | 2.326 | 2.322 | +0.04 | +0.22 | +0.13 | +0.32 | -0.09 | +0.15 | +0.06 | +0.30 |
| 0.375 | 2.330 | 2.334 | 2.335 | 2.342 | 2.329 | 2.333 | 2.334 | 2.338 | +0.34 | +0.50 | +0.06 | +0.22 | +0.19 | +0.39 | +0.04 | +0.24 |
| 0.5 | 2.329 | 2.329 | 2.329 | 2.329 | 2.327 | 2.327 | 2.327 | 2.329 | -0.02 | +0.02 | -0.01 | +0.03 | +0.06 | +0.04 | +0.00 | -0.02 |
| 0.75 | 2.329 | 2.330 | 2.330 | 2.339 | 2.328 | 2.330 | 2.330 | 2.335 | +0.38 | +0.43 | -0.01 | +0.04 | +0.19 | +0.32 | +0.00 | +0.13 |
| 1 | 2.331 | 2.330 | 2.332 | 2.334 | 2.330 | 2.330 | 2.333 | 2.332 | +0.15 | +0.14 | +0.07 | +0.06 | +0.06 | +0.06 | +0.09 | +0.09 |
| 1.5 | 2.333 | 2.331 | 2.333 | 2.341 | 2.333 | 2.330 | 2.333 | 2.337 | +0.45 | +0.36 | +0.08 | -0.01 | +0.28 | +0.15 | +0.11 | -0.02 |
| 2 | 2.335 | 2.333 | 2.336 | 2.333 | 2.335 | 2.333 | 2.337 | 2.333 | +0.02 | -0.06 | +0.13 | +0.05 | +0.02 | -0.06 | +0.15 | +0.06 |
| 3 | 2.344 | 2.344 | 2.345 | 2.343 | 2.343 | 2.345 | 2.345 | 2.336 | -0.03 | -0.04 | +0.06 | +0.06 | -0.36 | -0.32 | +0.02 | +0.06 |
| 4 | 2.355 | 2.355 | 2.357 | 2.332 | 2.354 | 2.356 | 2.356 | 2.332 | -0.98 | -0.95 | +0.05 | +0.08 | -1.02 | -0.96 | +0.02 | +0.08 |
| 6 | 2.363 | 2.365 | 2.364 | 2.348 | 2.362 | 2.364 | 2.365 | 2.341 | -0.73 | -0.65 | -0.05 | +0.03 | -0.93 | -0.87 | +0.06 | +0.13 |
| 8 | 2.346 | 2.352 | 2.352 | 2.349 | 2.345 | 2.349 | 2.349 | 2.348 | -0.14 | +0.12 | -0.01 | +0.26 | -0.06 | +0.15 | +0.00 | +0.21 |
| 12 | 2.348 | 2.348 | 2.353 | 2.368 | 2.348 | 2.348 | 2.353 | 2.360 | +0.86 | +0.84 | +0.20 | +0.18 | +0.53 | +0.51 | +0.23 | +0.21 |
| 16 | 2.348 | 2.352 | 2.354 | 2.357 | 2.349 | 2.349 | 2.354 | 2.356 | +0.24 | +0.39 | +0.08 | +0.23 | +0.30 | +0.28 | +0.19 | +0.17 |
| 24 | 2.358 | 2.364 | 2.361 | 2.376 | 2.357 | 2.362 | 2.363 | 2.369 | +0.48 | +0.73 | -0.13 | +0.13 | +0.28 | +0.51 | +0.02 | +0.25 |
| 32 | 2.353 | 2.356 | 2.358 | 2.362 | 2.353 | 2.356 | 2.359 | 2.362 | +0.26 | +0.41 | +0.09 | +0.24 | +0.25 | +0.38 | +0.11 | +0.23 |
| 48 | 2.361 | 2.356 | 2.361 | 2.379 | 2.360 | 2.356 | 2.361 | 2.373 | +0.99 | +0.77 | +0.21 | -0.00 | +0.72 | +0.55 | +0.21 | +0.04 |
| 64 | 2.353 | 2.360 | 2.357 | 2.369 | 2.353 | 2.358 | 2.359 | 2.369 | +0.40 | +0.72 | -0.11 | +0.21 | +0.45 | +0.68 | +0.02 | +0.26 |

### Table 4. Random stride 16, per-iteration values (ns), sizes 3-64 MB

| size MB | set | i1 | i2 | i3 | i4 | i5 | i6 | i7 | i8 | i9 | i10 | mean | median | CV% |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | VHE | 39.7 | 38.2 | 39.1 | 39.5 | 39.4 | 39.7 | 39.1 | 39.8 | 38.5 | 39.4 | 39.23 | 39.39 | 1.36 |
| 3 | nVHE | 39.9 | 39.3 | 39.4 | 39.7 | 39.3 | 39.4 | 39.2 | 39.5 | 40.8 | 39.6 | 39.60 | 39.44 | 1.14 |
| 3 | NP | 39.3 | 39.4 | 40.7 | 39.6 | 39.8 | 39.4 | 39.3 | 39.9 | 39.1 | 39.2 | 39.59 | 39.44 | 1.16 |
| 3 | pVM | 30.1 | 29.1 | 28.2 | 28.9 | 28.9 | 28.8 | 29.6 | 29.6 | 29.4 | 28.8 | 29.14 | 29.00 | 1.90 |
| 4 | VHE | 51.7 | 51.4 | 52.8 | 51.7 | 52.2 | 51.7 | 52.1 | 52.1 | 51.9 | 51.5 | 51.91 | 51.84 | 0.79 |
| 4 | nVHE | 52.5 | 52.1 | 51.7 | 52.5 | 52.8 | 52.7 | 51.6 | 52.5 | 51.9 | 51.6 | 52.18 | 52.30 | 0.89 |
| 4 | NP | 52.1 | 52.4 | 53.1 | 52.8 | 52.7 | 51.8 | 53.1 | 52.8 | 52.6 | 52.4 | 52.60 | 52.62 | 0.78 |
| 4 | pVM | 35.9 | 37.4 | 36.2 | 36.0 | 35.2 | 35.6 | 36.0 | 35.0 | 35.2 | 36.4 | 35.89 | 35.97 | 2.00 |
| 6 | VHE | 78.5 | 78.9 | 77.5 | 78.5 | 79.2 | 82.2 | 78.8 | 79.8 | 79.4 | 78.2 | 79.11 | 78.88 | 1.57 |
| 6 | nVHE | 81.3 | 80.1 | 81.9 | 84.0 | 80.9 | 79.2 | 80.6 | 82.5 | 79.1 | 83.0 | 81.27 | 81.13 | 1.96 |
| 6 | NP | 77.9 | 80.8 | 85.3 | 82.1 | 80.8 | 79.0 | 79.7 | 80.6 | 80.1 | 81.5 | 80.78 | 80.68 | 2.49 |
| 6 | pVM | 53.8 | 54.9 | 55.8 | 54.7 | 54.8 | 54.7 | 56.1 | 57.5 | 57.0 | 56.0 | 55.53 | 55.34 | 2.06 |
| 8 | VHE | 97.8 | 126.2 | 124.6 | 123.6 | 125.8 | 126.6 | 125.9 | 124.9 | 125.1 | 124.7 | 122.51 | 124.97 | 7.14 |
| 8 | nVHE | 128.2 | 126.3 | 126.0 | 125.3 | 130.4 | 127.0 | 127.1 | 126.9 | 125.8 | 126.7 | 126.98 | 126.83 | 1.12 |
| 8 | NP | 125.1 | 127.1 | 126.6 | 126.2 | 126.6 | 124.9 | 126.7 | 126.6 | 126.2 | 126.5 | 126.25 | 126.53 | 0.56 |
| 8 | pVM | 97.4 | 101.6 | 99.0 | 97.1 | 97.4 | 98.4 | 97.8 | 95.8 | 97.9 | 101.9 | 98.42 | 97.85 | 1.96 |
| 12 | VHE | 165.3 | 130.0 | 164.4 | 164.5 | 164.1 | 164.5 | 163.5 | 163.8 | 164.8 | 164.6 | 160.95 | 164.41 | 6.76 |
| 12 | nVHE | 165.2 | 163.5 | 163.7 | 164.1 | 165.5 | 164.9 | 165.6 | 165.4 | 134.9 | 165.2 | 161.79 | 165.03 | 5.86 |
| 12 | NP | 163.6 | 163.6 | 164.8 | 164.9 | 165.4 | 165.1 | 164.7 | 163.3 | 165.3 | 163.6 | 164.44 | 164.76 | 0.48 |
| 12 | pVM | 127.5 | 128.9 | 129.2 | 129.9 | 129.2 | 130.0 | 129.8 | 131.6 | 129.9 | 129.0 | 129.50 | 129.49 | 0.81 |
| 16 | VHE | 178.6 | 177.2 | 177.1 | 176.8 | 151.4 | 176.4 | 177.5 | 176.6 | 177.0 | 176.3 | 174.48 | 176.90 | 4.67 |
| 16 | nVHE | 175.7 | 176.5 | 175.8 | 176.6 | 178.3 | 176.8 | 178.1 | 177.8 | 177.6 | 149.6 | 174.29 | 176.73 | 5.00 |
| 16 | NP | 176.3 | 177.0 | 175.8 | 177.1 | 177.0 | 177.5 | 177.1 | 177.1 | 177.3 | 176.4 | 176.87 | 177.05 | 0.29 |
| 16 | pVM | 140.0 | 148.4 | 142.1 | 140.5 | 141.1 | 141.3 | 142.1 | 139.1 | 141.5 | 140.8 | 141.70 | 141.20 | 1.78 |
| 24 | VHE | 185.8 | 185.3 | 184.7 | 185.0 | 184.2 | 185.0 | 185.0 | 185.7 | 185.6 | 185.6 | 185.17 | 185.11 | 0.27 |
| 24 | nVHE | 184.1 | 158.4 | 184.1 | 185.3 | 185.0 | 162.5 | 185.0 | 185.0 | 153.3 | 185.7 | 176.83 | 184.54 | 7.44 |
| 24 | NP | 159.0 | 185.6 | 185.4 | 186.1 | 186.7 | 186.2 | 186.0 | 186.3 | 185.1 | 185.8 | 183.23 | 185.92 | 4.65 |
| 24 | pVM | 145.8 | 150.1 | 147.2 | 146.7 | 146.8 | 147.1 | 147.3 | 148.0 | 147.3 | 147.3 | 147.36 | 147.25 | 0.77 |
| 32 | VHE | 189.0 | 188.4 | 188.0 | 187.6 | 187.9 | 187.8 | 188.0 | 181.2 | 179.5 | 188.1 | 186.55 | 187.93 | 1.77 |
| 32 | nVHE | 189.4 | 188.5 | 190.4 | 191.3 | 190.3 | 189.8 | 190.0 | 190.8 | 189.4 | 188.8 | 189.87 | 189.92 | 0.46 |
| 32 | NP | 191.4 | 189.2 | 189.4 | 189.1 | 189.6 | 189.2 | 188.9 | 189.3 | 173.7 | 189.1 | 187.90 | 189.23 | 2.67 |
| 32 | pVM | 148.5 | 155.7 | 150.4 | 151.8 | 149.9 | 150.1 | 150.3 | 149.3 | 149.8 | 150.7 | 150.66 | 150.18 | 1.32 |
| 48 | VHE | 192.6 | 192.5 | 193.2 | 193.0 | 193.1 | 193.3 | 192.4 | 193.4 | 192.4 | 192.1 | 192.80 | 192.80 | 0.25 |
| 48 | nVHE | 190.6 | 191.4 | 191.1 | 191.6 | 192.3 | 167.2 | 192.5 | 192.1 | 192.2 | 183.7 | 188.47 | 191.46 | 4.19 |
| 48 | NP | 174.8 | 174.6 | 191.1 | 191.5 | 195.0 | 191.5 | 191.5 | 192.0 | 191.9 | 191.4 | 188.53 | 191.47 | 3.91 |
| 48 | pVM | 150.4 | 150.8 | 152.6 | 151.0 | 151.1 | 150.8 | 153.3 | 152.5 | 151.4 | 150.8 | 151.47 | 151.07 | 0.65 |
| 64 | VHE | 192.8 | 192.7 | 189.7 | 193.2 | 193.2 | 193.7 | 193.4 | 192.8 | 193.0 | 186.7 | 192.14 | 192.94 | 1.16 |
| 64 | nVHE | 191.3 | 191.3 | 191.5 | 192.0 | 191.9 | 192.0 | 192.0 | 192.4 | 192.4 | 192.5 | 191.94 | 192.00 | 0.23 |
| 64 | NP | 186.6 | 180.4 | 192.2 | 192.4 | 180.4 | 192.8 | 192.3 | 192.4 | 193.1 | 192.8 | 189.54 | 192.35 | 2.73 |
| 64 | pVM | 152.2 | 155.5 | 152.6 | 152.5 | 153.1 | 152.6 | 152.9 | 153.2 | 152.9 | 154.9 | 153.24 | 152.91 | 0.71 |

### Table 5. State of each measurement (F = fast, M = intermediate, N = normal; iteration order i1..i10)

Guests (fast reference = pVM median, normal reference = median of the three regular guests):

| size MB | fast ref | normal ref | VHE | nVHE | NP | pVM |
|---:|---:|---:|---|---|---|---|
| 3 | 29.0 | 39.4 | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 4 | 36.0 | 52.3 | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 6 | 55.3 | 80.7 | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 8 | 97.9 | 126.5 | FNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 12 | 129.5 | 164.8 | NFNNNNNNNN | NNNNNNNNFN | NNNNNNNNNN | FFFFFFFFFF |
| 16 | 141.2 | 176.9 | NNNNMNNNNN | NNNNNNNNNF | NNNNNNNNNN | FFFFFFFFFF |
| 24 | 147.2 | 185.1 | NNNNNNNNNN | NMNNNMNNFN | MNNNNNNNNN | FFFFFFFFFF |
| 32 | 150.2 | 189.2 | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNMN | FFFFFFFFFF |
| 48 | 151.1 | 191.5 | NNNNNNNNNN | NNNNNMNNNN | MMNNNNNNNN | FFFFFFFFFF |
| 64 | 152.9 | 192.4 | NNNNNNNNNN | NNNNNNNNNN | NMNNMNNNNN | FFFFFFFFFF |
| totals of 100 | | | F2 M1 N97 | F3 M3 N94 | F0 M6 N94 | F100 |

Hosts (fast reference = noisy nVHE median, normal reference = clean nVHE median; pkvm uses its own median as normal):

| size MB | fast ref | normal ref | kvmoff | vhe | nvhe | pkvm (try2) | nvhe-noisy |
|---:|---:|---:|---|---|---|---|---|
| 3 | 26.4 | 36.6 | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 4 | 30.8 | 47.7 | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 6 | 48.6 | 67.3 | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 8 | 83.9 | 112.6 | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 12 | 121.8 | 154.8 | NFNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 16 | 134.2 | 168.6 | NFNNNNFMNN | NNNMNNNNNN | NNNNNNNNNN | NNNNNNNNNN | FFFFFFFFFF |
| 24 | 143.1 | 177.5 | NNNNNFNNFN | NNNNFNNNNN | NNNNNNNNNN | NNNNNMNNNN | FFFFFFFFFF |
| 32 | 146.2 | 180.8 | FFNMNNNNMN | NNNNNNNNNN | NNNNMNNNNN | NNNNNFNNNN | FFFFFFFFFF |
| 48 | 149.1 | 182.4 | MNNNMNNNFN | NNNNMNNNNN | NMNNMNNNNM | NNNNNNNNNN | FFFFFFFFFF |
| 64 | 150.1 | 185.0 | MNMNNNNNNN | NNNMNNNMNN | NNMNNMMNNN | NNNNNMNNNM | FFFFFFFFFF |
| non-normal, 3-8 MB | | | 0/40 | 0/40 | 0/40 | 0/40 | 40/40 |
| non-normal, 12-64 MB | | | 15/60 | 5/60 | 7/60 | 4/60 | 60/60 |

### Table 6. Absolute random latency (stride 16), medians of 10 iterations (ns): guests vs host

| size MB | H kvmoff | H vhe | H nvhe | H pkvm(try2) | H nvhe-noisy | G VHE | G nVHE | G NP | G pVM | G VHE - H vhe | G nVHE - H nvhe | G NP - H pkvm | G pVM - H pkvm | G pVM - H kvmoff | G NP - H kvmoff | G pVM - H nvhe-noisy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 20.68 | 20.73 | 20.75 | 20.88 | 21.10 | 23.69 | 23.96 | 23.76 | 22.38 | +2.96 | +3.20 | +2.88 | +1.50 | +1.71 | +3.08 | +1.28 |
| 3 | 36.60 | 36.56 | 36.63 | 37.31 | 26.41 | 39.39 | 39.44 | 39.44 | 29.00 | +2.83 | +2.81 | +2.13 | -8.31 | -7.60 | +2.84 | +2.59 |
| 4 | 47.59 | 47.45 | 47.69 | 49.31 | 30.80 | 51.84 | 52.30 | 52.62 | 35.97 | +4.38 | +4.62 | +3.31 | -13.34 | -11.62 | +5.04 | +5.17 |
| 6 | 67.14 | 67.37 | 67.35 | 72.59 | 48.61 | 78.88 | 81.13 | 80.68 | 55.34 | +11.50 | +13.78 | +8.09 | -17.25 | -11.80 | +13.54 | +6.72 |
| 8 | 112.54 | 112.32 | 112.60 | 119.59 | 83.90 | 124.97 | 126.83 | 126.53 | 97.85 | +12.65 | +14.23 | +6.93 | -21.74 | -14.69 | +13.98 | +13.95 |
| 12 | 154.65 | 154.65 | 154.81 | 161.68 | 121.82 | 164.41 | 165.03 | 164.76 | 129.49 | +9.77 | +10.22 | +3.08 | -32.19 | -25.17 | +10.11 | +7.67 |
| 16 | 168.54 | 169.71 | 168.56 | 176.28 | 134.23 | 176.90 | 176.73 | 177.05 | 141.20 | +7.19 | +8.17 | +0.77 | -35.08 | -27.34 | +8.51 | +6.97 |
| 24 | 177.23 | 180.27 | 177.47 | 185.59 | 143.08 | 185.11 | 184.54 | 185.92 | 147.25 | +4.84 | +7.07 | +0.33 | -38.34 | -29.98 | +8.69 | +4.17 |
| 32 | 180.61 | 182.72 | 180.78 | 188.66 | 146.20 | 187.93 | 189.92 | 189.23 | 150.18 | +5.21 | +9.14 | +0.57 | -38.48 | -30.43 | +8.61 | +3.98 |
| 48 | 182.66 | 183.85 | 182.44 | 189.56 | 149.10 | 192.80 | 191.46 | 191.47 | 151.07 | +8.95 | +9.02 | +1.92 | -38.49 | -31.59 | +8.81 | +1.97 |
| 64 | 185.23 | 185.43 | 185.05 | 191.73 | 150.12 | 192.94 | 192.00 | 192.35 | 152.91 | +7.52 | +6.96 | +0.62 | -38.82 | -32.33 | +7.12 | +2.78 |

Means at the four requested sizes (ns; host means are pulled down by sporadic fast cells):

| size MB | H kvmoff | H vhe | H nvhe | H pkvm(try2) | G VHE | G nVHE | G NP | G pVM | G VHE - H vhe | G nVHE - H nvhe | G NP - H pkvm | G pVM - H pkvm | G pVM - H kvmoff |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 47.70 | 47.51 | 47.66 | 49.31 | 51.91 | 52.18 | 52.60 | 35.89 | +4.41 | +4.52 | +3.29 | -13.42 | -11.81 |
| 8 | 112.60 | 112.37 | 112.68 | 119.65 | 122.51 | 126.98 | 126.25 | 98.42 | +10.14 | +14.30 | +6.60 | -21.23 | -14.18 |
| 16 | 159.11 | 167.16 | 168.54 | 176.37 | 174.48 | 174.29 | 176.87 | 141.70 | +7.32 | +5.74 | +0.50 | -34.67 | -17.40 |
| 64 | 182.21 | 181.21 | 181.10 | 188.13 | 192.14 | 191.94 | 189.54 | 153.24 | +10.93 | +10.83 | +1.41 | -34.90 | -28.97 |

### Table 7. Normal-minus-fast shift of the random curve (medians, ns): host versus guest, and prediction of the pVM curve

| size MB | pages | host clean nVHE | host noisy nVHE | host shift | guest NP | guest pVM | guest shift | 35 ns x (1 - 512/pages) | predicted pVM = NP - host shift | error ns | error % |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 256 | 19.48 | 19.05 | +0.43 | 19.58 | 19.73 | -0.15 | 0.0 | | | |
| 1.5 | 384 | 20.18 | 20.10 | +0.07 | 20.87 | 20.84 | +0.03 | 0.0 | | | |
| 2 | 512 | 20.75 | 21.10 | -0.35 | 23.76 | 22.38 | +1.38 | 0.0 | | | |
| 3 | 768 | 36.63 | 26.41 | +10.22 | 39.44 | 29.00 | +10.44 | 11.7 | 29.22 | -0.22 | -0.8 |
| 4 | 1024 | 47.69 | 30.80 | +16.89 | 52.62 | 35.97 | +16.65 | 17.5 | 35.74 | +0.23 | +0.7 |
| 6 | 1536 | 67.35 | 48.61 | +18.74 | 80.68 | 55.34 | +25.34 | 23.3 | 61.94 | -6.60 | -11.9 |
| 8 | 2048 | 112.60 | 83.90 | +28.70 | 126.53 | 97.85 | +28.67 | 26.2 | 97.82 | +0.03 | +0.0 |
| 12 | 3072 | 154.81 | 121.82 | +32.99 | 164.76 | 129.49 | +35.27 | 29.2 | 131.77 | -2.28 | -1.8 |
| 16 | 4096 | 168.56 | 134.23 | +34.33 | 177.05 | 141.20 | +35.85 | 30.6 | 142.72 | -1.52 | -1.1 |
| 24 | 6144 | 177.47 | 143.08 | +34.39 | 185.92 | 147.25 | +38.68 | 32.1 | 151.53 | -4.28 | -2.9 |
| 32 | 8192 | 180.78 | 146.20 | +34.58 | 189.23 | 150.18 | +39.04 | 32.8 | 154.65 | -4.47 | -3.0 |
| 48 | 12288 | 182.44 | 149.10 | +33.34 | 191.47 | 151.07 | +40.41 | 33.5 | 158.13 | -7.06 | -4.7 |
| 64 | 16384 | 185.05 | 150.12 | +34.92 | 192.35 | 152.91 | +39.44 | 33.9 | 157.43 | -4.52 | -3.0 |

Prediction error: mean absolute 3.12 ns, RMS 4.00 ns, mean absolute 2.97%; the naive prediction pVM = NP is off by 31.5% on average.

### Table 8. Fingerprint of the fast state in other benchmarks (medians of 10 iterations)

| metric | H nvhe clean | H nvhe noisy | host change % | G NP | G pVM | guest change % (pVM vs NP) | G pVM vs G nVHE % |
|---|---:|---:|---:|---:|---:|---:|---:|
| lat_mem_rd_rand 3 MB (ns) | 36.63 | 26.41 | -27.9 | 39.44 | 29.00 | -26.5 | -26.5 |
| lat_mem_rd_rand 4 MB | 47.69 | 30.80 | -35.4 | 52.62 | 35.97 | -31.6 | -31.2 |
| lat_mem_rd_rand 8 MB | 112.60 | 83.90 | -25.5 | 126.53 | 97.86 | -22.7 | -22.8 |
| lat_mem_rd_rand 16 MB | 168.56 | 134.23 | -20.4 | 177.05 | 141.20 | -20.2 | -20.1 |
| lat_mem_rd_rand 64 MB | 185.05 | 150.12 | -18.9 | 192.35 | 152.91 | -20.5 | -20.4 |
| seq stride 128, 3 MB (ns) | 5.000 | 4.625 | -7.5 | 5.137 | 4.665 | -9.2 | -8.9 |
| seq stride 128, 4 MB | 5.181 | 4.699 | -9.3 | 5.365 | 4.763 | -11.2 | -11.0 |
| seq stride 128, 6 MB | 7.649 | 6.826 | -10.8 | 8.463 | 6.894 | -18.5 | -17.0 |
| seq stride 256, 6 MB | 8.225 | 7.465 | -9.2 | 9.261 | 7.569 | -18.3 | -17.3 |
| bw_mem_rd 4.19 MB (MB/s) | 26187 | 27688 | +5.7 | 25889 | 27557 | +6.4 | +6.6 |
| bw_mem_rd 8.39 MB | 16423 | 19037 | +15.9 | 15755 | 19523 | +23.9 | +22.9 |
| bw_mem_wr 0.262 MB | 52081 | 40869 | -21.5 | 41944 | 35180 | -16.1 | -21.3 |
| bw_mem_wr 4.19 MB | 17662 | 21104 | +19.5 | 17529 | 21026 | +19.9 | +19.7 |
| bw_mem_wr 8.39 MB | 9274 | 10825 | +16.7 | 9160 | 11086 | +21.0 | +20.7 |
| bw_mem_cp 4.19 MB | 8338 | 9347 | +12.1 | 8204 | 9600 | +17.0 | +16.9 |
| bw_mem_rdwr 8.39 MB | 12971 | 14244 | +9.8 | 11285 | 12840 | +13.8 | +13.7 |
| par_mem 4 MB | 8.51 | 6.54 | -23.2 | 8.89 | 6.88 | -22.6 | -21.0 |
| par_mem 8 MB | 10.20 | 7.47 | -26.7 | 10.95 | 7.92 | -27.7 | -20.2 |
| par_mem 16 MB | 12.36 | 9.40 | -23.9 | 12.41 | 9.56 | -23.0 | -19.1 |
| par_mem 33 MB | 11.92 | 9.93 | -16.7 | 12.16 | 9.56 | -21.4 | -18.0 |
| lat_ctx 64K x 96 procs (us) | 11.75 | 10.37 | -11.8 | 15.28 | 12.53 | -18.0 | -18.4 |
| lat_ctx 64K x 64 procs | 9.21 | 8.14 | -11.6 | 11.81 | 9.78 | -17.2 | -18.3 |
| lmbench tlb (pages) | 48 | 48 | 0 | 48 | 48 | 0 | 0 |
| not shared: seq stride 128, 64 MB (ns) | 9.01 | 9.88 | +9.7 | 8.97 | 8.92 | -0.5 | +0.7 |
| not shared: lat_tcp localhost (us) | 22.70 | 28.36 | +24.9 | 110.63 | 109.90 | -0.7 | -1.3 |

Pearson r between host change and guest change: 0.84 over the 33 random sizes, 0.84 over 48 lat_ctx variants, 0.74 over 176 bw_mem variants.

### Table 9. LLC boundary (sequential, 8 MB) is bimodal per measurement in clean datasets (ns, i1..i10)

| dataset | stride 128 | low-mode count | stride 256 | low-mode count |
|---|---|---:|---|---:|
| guest VHE | 9.05 11.17 11.19 9.02 9.21 11.21 9.06 8.97 9.02 9.20 | 7 | 11.06 9.90 12.37 12.41 12.37 11.89 9.96 12.35 10.00 9.94 | 4 |
| guest nVHE | 8.96 11.04 11.13 8.97 11.11 9.11 11.24 9.08 9.04 9.05 | 6 | 12.26 12.36 11.08 10.10 10.31 12.58 12.45 12.38 12.46 12.43 | 2 |
| guest NP | 10.43 8.98 11.12 9.02 11.26 9.05 11.21 11.24 9.04 11.22 | 4 | 12.24 12.42 10.04 12.46 10.06 12.55 10.03 10.12 11.45 10.38 | 5 |
| guest pVM | 8.86 8.95 9.10 8.99 9.04 9.04 9.00 8.96 9.01 9.12 | 10 | 9.87 10.00 9.99 9.89 9.93 10.04 10.15 10.10 9.94 10.02 | 10 |
| host kvmoff | 9.13 11.18 11.21 10.95 11.18 11.23 11.33 9.81 11.20 11.14 | 2 | 12.24 10.50 10.19 12.37 12.21 10.98 10.65 12.49 10.06 10.35 | 6 |
| host nvhe | 11.44 11.43 11.34 11.28 9.37 11.33 11.41 11.23 11.39 9.10 | 2 | 10.30 12.43 12.62 9.98 9.93 12.27 12.35 10.55 12.31 10.02 | 5 |
| host vhe | 11.50 11.50 11.19 11.48 11.42 11.41 9.40 11.45 11.47 9.25 | 2 | 11.47 12.62 11.73 12.47 12.45 12.57 10.92 12.45 10.30 12.63 | 2 |
| host pkvm (try2) | 11.53 11.53 9.42 11.42 9.22 10.73 11.13 9.29 9.40 9.29 | 5 | 10.70 11.77 12.57 12.56 12.52 10.56 10.25 12.50 10.10 12.47 | 4 |
| host nvhe-noisy | 9.42 9.35 9.44 9.46 9.42 9.35 9.40 9.36 9.43 9.48 | 10 | 10.81 10.34 10.34 10.31 10.27 10.26 10.33 10.28 10.10 10.33 | 10 |

Low mode counted as below 10.0 ns (stride 128) and below 11.2 ns (stride 256). Standalone host logs (fresh process per run, stride 256, 8 MB): kvmoff 10.09 10.20 12.38 10.16 10.09 12.53 11.72 12.44 12.47 12.39; nvhe 12.59 12.55 10.27 10.32 12.56 12.57 12.31 12.51 10.22 12.63; vhe 10.12 12.97 10.56 13.07 10.14 11.69 12.38 12.44 12.91 12.49; pkvm 12.26 12.47 10.06 12.50 12.44 12.56 10.11 10.14 12.51 10.16.

Figure 7 tie-in (host, stride 256, 8 MB, means): kvmoff 11.203, nvhe 11.276, vhe 11.961, pkvm 11.600 ns; pkvm vs kvmoff +3.55% (exact permutation p = 0.40), vs vhe -3.02% (p = 0.40), vs nvhe +2.87% (p = 0.48). Random 64 MB means 182.209 / 181.104 / 181.207 / 188.135: pkvm vs kvmoff +3.25% (p = 0.093), medians +3.51%.

### Table 10. Interference on pure-core metrics (10 iterations)

| metric | G VHE | G nVHE | G NP | G pVM | H nvhe clean | H nvhe noisy |
|---|---|---|---|---|---|---|
| integer_add ns (min-max, CV) | 0.28-0.28, 0.00% | 0.28-0.28, 0.00% | 0.28-0.28, 0.00% | 0.28-0.29, 1.13% | 0.28-0.28, 0.00% | 0.28-0.28, 0.00% |
| integer_div ns | 4.45-4.45, 0.00% | 4.45-4.45, 0.00% | 4.45-4.45, 0.00% | 4.45-4.61, 1.08% | 4.45-4.45, 0.00% | 4.45-4.45, 0.00% |
| double_add ns | 1.11-1.11, 0.00% | 1.11-1.11, 0.00% | 1.11-1.11, 0.00% | 1.11-1.16, 1.33% | 1.11-1.11, 0.00% | 1.11-1.11, 0.00% |
| double_div ns | 6.68-6.68, 0.00% | 6.68-6.68, 0.00% | 6.68-6.68, 0.00% | 6.68-6.82, 0.75% | 6.67-6.67, 0.00% | 6.67-6.67, 0.00% |
| L1 load latency, random 0.00049 MB | 2.225-2.225, 0.00% | 2.225-2.226, 0.02% | 2.226-2.226, 0.00% | 2.226-2.273, 0.68% | 2.223-2.223, 0.00% | 2.223-2.224, 0.02% |
| null syscall us | 1.672-1.679, 0.11% | 1.674-1.677, 0.08% | 1.673-1.677, 0.09% | 1.674-1.762, 1.59% | 0.1028-0.1040, 0.47% | 0.1028-0.1051, 0.69% |
| L1-range lat_mem_rd points more than 0.15% above minimum (of 760) | 0.0% | 0.0% | 0.0% | 26.1% (max 2.294) | 0.0% | 0.0% |

pVM alternation: 364 of 900 L1-range points (all strides, sizes up to 0.0625 MB) exceed 2.2275 ns; in 64 of 70 (iteration x stride) blocks they are confined to one position parity (6 points on the other parity); the parity flips in 60 of 60 transitions between consecutive 33-size stride blocks.

### Table 11. Setup of the four guest runs: what is recorded and what is not

| item | VHE run | nVHE run | NP run | pVM run | source / status |
|---|---|---|---|---|---|
| directory | xkernel-n90-kvm-vhe-20260605-201819 | xkernel-n90-kvm-nvhe-20260606-133103 | xkernel-n90-pkvm-np-clean-20260606-164648 | xkernel-n90-pkvm-pvm-20260605-163040 | results/ |
| ENV_TAG (started.txt, autorun.marker, file prefix) | xkernel-kvm | xkernel-kvm-nvhe | xkernel-pkvm-np | xkernel-pkvm-np (does not match directory) | recorded |
| start, guest clock UTC | 06-05 09:16:53 | 06-06 02:30:07 | 06-06 05:47:06 | 06-05 05:31:53 | started.txt |
| end, guest clock UTC | 06-05 12:17:46 | 06-06 05:30:23 | 06-06 08:46:00 | 06-05 08:28:53 | completed.txt |
| order, day | 2nd, day 1 | 3rd, day 2 | 4th, day 2 | 1st, day 1 | derived |
| host boot | separate boot per mode; pVM and NP runs separated by two other boots and about 21 h | | | | inferred (mode is a boot parameter) |
| host kvm-arm.mode | vhe (name only) | nvhe (name only) | protected (name only) | protected (name only) | not recorded in any result file |
| host kernel version | ? | ? | ? | ? | not recorded (host tests two days earlier: 6.6.0-73-generic) |
| guest kernel | x-kernel 'Linux kylin-x 10.0.0' | same | same | same | report header; commit not recorded |
| guest memory | MemTotal 1999956 kB, MemFree 1802388 kB | identical | identical | identical | environment.txt (md5 identical x4) |
| guest vCPUs | 2 (CPU_NUM=2; alternation and fork bimodality) | 2 | 2 | 2 | config label + data |
| lmbench config | CONFIG.xkernel, md5 40b058db... | identical | identical | identical | CONFIG.xkernel.used |
| VMM | crosvm | crosvm | crosvm | crosvm | config comment only; options not recorded |
| pvmfw | ? | ? | ? | ? (local script uses --protected-vm-with-pvmfw) | not recorded; /dev/dice and /dev/firmware-dtb exist in all four guests |
| vCPU pinning | ? | ? | ? | ? (local pVM script has no taskset) | not recorded; 'taskset' only by recollection (methodology 118, 202) |
| host CPU frequency | locked 1.9 GHz | locked | locked | locked | inferred from L1 latency 2.225-2.226 ns |
| host THP (top-level, per-size, shmem) | ? | ? | ? | ? | not recorded |
| guest memory backing (memfd/hugepages, lock, prealloc) | ? | ? | ? | ? | not recorded |
| interference on a vCPU | none | none | none | yes, one of two vCPUs | measured (table 10) |
| memory state | normal (3/100 excursions) | normal (6/100) | normal (6/100) | fast (100/100) | measured (table 5) |
| virtio-blk read bandwidth 1 MB (MB/s, median) | 48.8 | 48.7 | 66.7 | 55.4 | measured |
| file page-fault latency, low/high mode (us) | 76 / 110 | 77 / 114 | 79-82 / 115-121 | 64-65 / 97-103 | measured |

Differences that could change stage-2 granularity or guest physical layout, none of which is recorded: host THP state including per-size anonymous and shmem knobs and defrag; crosvm --hugepages or a hugetlbfs-backed memory file; host memory fragmentation at VM start (boot age, what ran before, first run of the day versus later); long-term pinning and donation of guest pages (at the 6.6.0-73 commit both NP and pVM guests were pinned with FOLL_LONGTERM under pKVM, regular KVM guests were not pinned); pvmfw and swiotlb (extra reserved regions and a different first-touch order of guest memory); vCPU placement; order and timing in which the guest first touches its memory.

### Table 12. Candidate explanations for pVM versus regular VM in random access, ranked by evidence

| rank | candidate | supporting evidence | opposing evidence or gap | measurement that decides |
|---:|---|---|---|---|
| 1 | Run-level fast memory state of the machine, unrelated to protection; the pVM run was in it throughout | same shift and fingerprint in a host-only nVHE run; pVM guest faster than kvmoff host; fast cells in every dataset; pVM = NP - host shift within 3.1 ns; different day and boot; interference on one vCPU; documented try1 switch on a pKVM host | physical nature of the state unknown | pVM and NP launched alternately from one script in one boot with recorded host state; the gap should vanish or follow the state |
| 1a | large folios that survive top-level THP=never (per-size anonymous or shmem knobs) | code allows it; shift proportional to (1 - 2 MB/size) | guest stage 1 is 4 KiB and tlb = 48, so guest TLB entries cannot grow; guest-host offset equal in both states; clean runs are mostly normal | read hugepages-*/enabled, shmem_enabled, defrag, AnonHugePages, ShmemPmdMapped, thp_fault_alloc and per-size stats before and after a run; smaps of lat_mem_rd and of crosvm |
| 1b | physically contiguous versus scattered page placement (host allocator regime; host-contiguous guest memory) | LLC-boundary latency bimodal per measurement in all clean sets and always low in pVM and noisy host; DRAM-size fast cells in long measurements; traversal order of the random test equals first-touch order | why random 3-6 MB gains 10-18 ns is not demonstrated | dump PFNs of the 64 MB buffer through /proc/pid/pagemap in fast and normal runs; repeat after compact_memory and drop_caches |
| 1c | SoC, L3 or DRAM power or clock state that depends on other activity | noisy run had pvm-manage and AI services (documented); pVM run had interference | load average of the noisy run was about 1.0; L1, L2 and 1-2 MB latencies identical in both states | lat_mem_rd -t pinned to cpu0 with and without a spinner and with a memory-active task on another core |
| 2 | pVM-only stage-2 block mapping | pVM pages are donated and pinned | same fault path and block-capable EL2 code for NP and pVM; needs THP-mapped VMM memory; cannot beat bare metal; guest stage 1 is 4 KiB | stage-2 page-table dump or ShmemPmdMapped of crosvm for both VM types |
| 3 | different guest kernel build for the pVM | none | identical environment.txt, header and config | record x-kernel commit and image hash per run |
| 4 | mislabelled dataset | ENV_TAG and file prefix say pkvm-np | values differ from NP everywhere; would not explain the speed-up | record crosvm command line and VM type from the host |
| 5 | timer or frequency artefact | none | L1, L2 and 1-2 MB latencies agree within 0.1-1% | none needed |

For every variant of candidate 1 the decisive probe is the PMU: perf stat -e l1d_tlb_refill,l2d_tlb_refill,l2d_cache_refill,l3d_cache_refill,mem_access,stall_backend around lat_mem_rd -t -P 1 64 16 on cpu0 in a fast and in a normal run. l2d_tlb_refill per load dropping from about 1 to about 0 means translation reach (1a); unchanged TLB refills with fewer l3d_cache_refill at 3-6 MB and lower stall_backend per load at 64 MB means placement or memory-path latency (1b or 1c).

### Table 13. Significance of the guest differences in random access (exact permutation on means, all 184756 splits)

| size MB | pair | mean A | mean B | mean ratio % | bootstrap 95% CI | exact p | ranges overlap |
|---:|---|---:|---:|---:|---|---:|---|
| 4 | pVM/nVHE | 35.89 | 52.18 | -31.22 | [-32.06, -30.29] | 1.08e-05 | no |
| 4 | pVM/VHE | 35.89 | 51.91 | -30.86 | [-31.70, -29.96] | 1.08e-05 | no |
| 4 | pVM/NP | 35.89 | 52.60 | -31.77 | [-32.59, -30.86] | 1.08e-05 | no |
| 4 | NP/nVHE | 52.60 | 52.18 | +0.81 | [+0.11, +1.50] | 4.6e-02 | yes |
| 8 | pVM/nVHE | 98.42 | 126.98 | -22.49 | [-23.48, -21.45] | 1.08e-05 | no |
| 8 | pVM/VHE | 98.42 | 122.51 | -19.67 | [-22.14, -15.46] | 7.58e-05 | yes (VHE i1 = 97.8) |
| 8 | pVM/NP | 98.42 | 126.25 | -22.04 | [-22.92, -21.05] | 1.08e-05 | no |
| 8 | NP/nVHE | 126.25 | 126.98 | -0.58 | [-1.36, +0.10] | 0.17 | yes |
| 16 | pVM/nVHE | 141.70 | 174.29 | -18.70 | [-20.55, -15.68] | 1.08e-05 | no |
| 16 | pVM/VHE | 141.70 | 174.48 | -18.78 | [-20.54, -15.92] | 1.08e-05 | no |
| 16 | pVM/NP | 141.70 | 176.87 | -19.88 | [-20.57, -18.91] | 1.08e-05 | no |
| 16 | NP/nVHE | 176.87 | 174.29 | +1.48 | [-0.35, +4.91] | 0.68 | yes |
| 64 | pVM/nVHE | 153.24 | 191.94 | -20.16 | [-20.48, -19.79] | 1.08e-05 | no |
| 64 | pVM/VHE | 153.24 | 192.14 | -20.25 | [-20.81, -19.55] | 1.08e-05 | no |
| 64 | pVM/NP | 153.24 | 189.54 | -19.16 | [-20.35, -17.63] | 1.08e-05 | no |
| 64 | NP/nVHE | 189.54 | 191.94 | -1.25 | [-2.92, +0.25] | 0.21 | yes |
| 64 | NP/VHE | 189.54 | 192.14 | -1.35 | [-3.20, +0.24] | 0.19 | yes |
| 64 | nVHE/VHE | 191.94 | 192.14 | -0.10 | [-0.68, +0.69] | 0.82 | yes |
