# 核查报告：audit:final-reply

## Summary

I audited the reply draft Documents/KylinX-审稿回复-内存延迟根因-草稿.md (311 lines) against docs/memlat/memlat-rootcause.zh-CN.md and the primary data. I recomputed the numbers myself; the scripts are in <scratch>/wf7/audit-final-reply/ (host.py for the N90 host CSVs and standalone-mem-bench, g5.py for expG5*.log, plus inline checks of the guest Fig. 8 data, expN4 on the N80 and the workstation, and the paper .docx). Kernel facts were checked with read-only git against tags 6.6.0-73.76, 6.6.0-76.8x and 6.6.0-79.93.

Almost every number reproduces:
- 64 MB random: 182.21 against 188.13 by mean (+3.25%, p=0.093); 185.23 against 191.73 by median (+3.51%, p=0.031).
- 8 MB stride 256: +3.55% by mean (p=0.399), +12.09% by median, -3.02% against VHE, VHE +6.77% over kvm-off, +0.65% in the standalone repeat.
- Every row of table 3.2.
- Per-boot medians: six baseline boots at 185.05-186.05 ns, the two protected boots at 191.73 and 192.41 ns, so 5.7-7.4 ns apart.
- PageFault +2.0%; the noisy nVHE boot is +2.1% over the clean one. ProtFault median +0.25%; standalone VHE -3.57%.
- Memread +0.55% by mean and -1.58% by median; the kvm-off outlier is 14826 MB/s at 67.11 MB.
- G5 levels: low 10.30-10.71 ns, high 12.00-12.64 ns, ratio 1.208. Random 64 MB is 150.9 ns at 1800 MHz and 190.6/190.9 ns under simple_ondemand.
- Translation-only chase: 13.96 cycles on both machines when no walk is needed. With walks (2048 x 1) it is 25.15 on the workstation and 38.10 on the N80.
- Guest pVM set: -20% to -32% by median against the other guest sets, 7.6-32.3 ns below kvm-off.
- CONFIG_X1_RMS: first enabled in 6.6.0-76.85 (commit b1b2979f, authored 2026-06-29, committed 2026-07-07). KVM_PGTABLE_MIN_BLOCK_LEVEL is 1 for 4K pages. phytium_noc defaults to simple_ondemand with 100 ms polling and is built as a module (=m).

The problems are wording, scope and consistency, not arithmetic.

Parts 二 and 三 (read by the reviewer) state as fact several things that were only reproduced on the N80 or inferred:
- the N90 interconnect scaled with load;
- the pVM guest data were taken with the interconnect at high frequency;
- the 8 MB level corresponds one-to-one with the interconnect frequency (it is 11 of 12-13 points);
- the workstation has the same processor model (it is a D3000; the N80 is a D3000M; only the FTC862 core and L1/L2 match);
- 2 MiB huge pages for the pVM would avoid the extra host cost (never measured).

Leftovers from earlier judgements:
- the proposed paper text (三 3.1, lines 215-216) explains the 8 MB point only through page layout and omits the interconnect evidence;
- the Kessler-Hill reference supports page-colour conflicts, a mechanism the conclusion document rules out;
- part 一 item 6 says the random-access ratios match the N90 point by point; the conclusion records a mismatch at 4-6 MB;
- part 一 item 2 points to letter items 4 and 5, but only the bracketed text after item 5 changes once the experiment is done.

The to-do table has three gaps:
- run27 on the N90 needs THP set to madvise or always, which contradicts 不改任何系统设置 if the N90 is kept at THP never;
- it does not say which machine run5 runs on, or that the interconnect governor should be fixed to performance first;
- it omits checking the Arm ARM section number, deciding mean against median for the whole paper, running run27/run24 on a non-protected N80 boot, and checking the governor with and without the desktop masked.

No sentence mixes host and guest numbers without a label. Two sentences do compare N80 host values with N90 guest values in a way that needs explicit labels and the 12 MB and up restriction.

## Defects

- **weakens** | Draft line 181 (二, 双值波动来源): States as fact that the paper's test platform (N90) has an interconnect scaled with load and that the 8 MB point's traffic sits at the threshold. The N90 governor was never recorded, and the driver is a module (CONFIG_ARM_PHYTIUM_NOC_DEVFREQ=m in 6.6.0-73.76 kylinos_generic_defconfig:1855), so it is not even recorded whether it was loaded. The conclusion (1.4, 4.3) grades the attribution to the N90 as an inference. Corrected wording: 该平台的片上互连驱动默认按内存总线负载动态调频（simple_ondemand，每 100ms 调整一次）；原测试时互连处于何种策略没有记录。我们推测该测量点产生的内存流量恰好处于调频阈值附近。 Effect: The reviewer would read an unmeasured property of the N90 as established fact.
- **weakens** | Draft line 183 (二): 取值与测量期间互连是否升至最高频率一一对应 is wrong. My recount (g5.py) gives 13 simple_ondemand stride-256 8 MB points. 11 follow the rule. 12.00 ns has one 1800 MHz sample. 10.71 ns has none (its buffer is about 0.65-0.71 contiguous). The conclusion says 11 of 12 judgeable. G5 is also a single run with the governors in fixed order. Corrected wording: 13 次测量中有 11 次的取值与测量期间互连是否升至最高频率相符（例外的一次缓冲区物理上大半连续）；将互连固定在最高或最低频率后（各 4 次），分别只出现较低或较高的一个水平。 Effect: Overstates the strength of the reproduction to the reviewer.
- **weakens** | Draft lines 193-194 (三, 图 8): 进一步分析表明，该组数据采集时平台的片上互连处于较高的工作频率 is stated as fact. The guest data have no host-side record (no kernel, boot mode, governor or crosvm command line). The conclusion (1.5, section 6) says 最可能 and 无法证实到底. The sentence also says 在同系列平台上将互连固定在最高频率可复现同样的延迟水平, which compares N80 host values with N90 guest values. That holds only at 12 MB and up: N80 at 1800 MHz gives 130.2/140.8/150.9 ns at 12/16/64 MB against the pVM guest's 129.5/141.2/152.9. It fails at 4-8 MB: 33.8/60.4/100.9 against 36.0/55.3/97.9. Corrected wording: 进一步分析表明，该组数据最可能是在另一种平台状态下采集的：其曲线与一次后台未屏蔽干净、未启用 KylinX 的宿主机测试相同；在同系列平台的宿主机上将片上互连固定在最高频率时，12MB 以上的随机访问延迟与该组数据相近。由于当时没有记录宿主机一侧的状态，这一点无法完全证实。 Effect: An inference is presented to the reviewer as a finding, and N80 host data are mixed with N90 guest data without a label.
- **weakens** | Draft line 196 (三, 若未重测 bracket): 其内存访问开销与 NP VM 一致 is not measured. Only the code path is shared, and the only pVM data set is the one being retracted. Corrected wording: 修改稿删去了这一表述，并在 5.3 节说明 pVM 与 NP VM 的二阶段映射由同一路径建立，按实现预期二者的内存访问开销相同，有待在固定平台状态的条件下重测确认。 Effect: Would replace one unsupported claim with another.
- **weakens** | Draft lines 159 and 163 (二 (一) item 5): 一台同型号处理器…的机器 and 两台机器处理器型号及一、二级缓存相同 are wrong. The workstation is a D3000 (results/memlat-d80f3-20260930/README.md line 13, host name D3000; different L3/L4 structure). The N80 is a D3000M (hw-survey-n80.txt line 28). Only the FTC862 core (same MIDR) and the L1/L2 caches are the same. The parenthesis also omits other differences: host kernel at EL1 against EL2, IPA 40 against 48 bits, a loaded workstation with no counters (walks per hop assumed equal), and the reviewer-acknowledged up-to-3-cycle uncertainty. Corrected wording: 一台处理器核相同（飞腾 FTC862，一、二级缓存相同）、未开启 KylinX（宿主机只有一阶段翻译）的台式机 ……（两台机器处理器核及一、二级缓存相同，但芯片型号、整机、内核版本和宿主内核所在特权级不同；该访问方式的数据驻留在一、二级缓存内。工作站无法读取硬件计数器，比较时假定两台机器每次访存的页表遍历次数相同。） Effect: A factual error in a reviewer-facing comparison; the comparison remains a magnitude check only.
- **weakens** | Draft line 162 (二 (一) item 5): 与图 7 中随机访问的增量（约 12–15 个周期）相符 omits the known tension. The cleanest N90 points (8, 12, 64 MB: 11.3-13.1 cycles) match the N80 2 MiB-block class, not the 1 GiB class that the N90 should mostly be in (conclusion 3.7, 3.8). Part 一 item 8 states this tension; the letter does not. Corrected wording: 二者之差为 12–15 个周期，与图 7 中随机访问的增量（约 12–15 个周期）在数量级上一致；由于是两台机器之间的比较，这只是数量级上的印证，不是对二阶段翻译代价的直接测量。 Effect: Presents a cross-machine magnitude match as a quantitative agreement.
- **weakens** | Draft lines 142-143 (二 (一) item 1): 它出现和饱和的位置，与该访问模式开始需要页表遍历、直至每次访存都需要遍历的位置一致 rests on N80 counter data (another machine, protected only). The fit by walk count overestimates 3-4 MB by about a factor of two, and L3 refills fit almost as well (R2 0.96 against 0.88; correlation 0.98 against 0.95; conclusion 3.2, 3.6). Corrected wording: 它出现和饱和的位置，与在同型号处理器上用硬件计数器测得的该访问模式页表遍历次数曲线大体同步（3–4MB 处增量小于按遍历次数的预期）。 Effect: Overstates the uniqueness of the walk-count fit to the reviewer.
- **weakens** | Draft lines 215-216 (三 3.1, proposed paper text): This is a leftover from the 页布局最可能 judgement. The only explanation offered for the 8 MB point is page layout (19%), and it is not said that this was measured on another machine (N80, protected). It omits the interconnect evidence, which is now the leading candidate (conclusion 1.4, 4.3 判断). Part 一 line 57 itself says the N90 high values do not look like layout. Corrected wording: 该测量点位于缓存容量边界，对内存通路状态最为敏感：在同系列平台上，片上互连按负载调频时该点在约10.4ns与12.6ns两个水平之间切换，将互连频率固定后只出现一个水平；此外它对测试缓冲区的物理页布局也敏感（同一平台状态下仅改变物理页的排列顺序，延迟相差约19%）。 Effect: The paper text would advance the superseded explanation and cite N80 data as if from the test platform.
- **cosmetic** | Draft line 185 (二): 这两个因素都与 KylinX 无关. This is supported for the two levels: they appear with the same size on the native N90 boot. For the layout effect it holds only as 不是 KylinX 引入的: the effect also exists on the workstation without stage 2, but there it is 2-3 times smaller at strides 64-256. The N80 was measured only under protected mode, so the conclusion leaves open whether stage 2 changes its size (section 9, 布局效应为什么在 N80 上比工作站大两三倍). Corrected wording: 双值波动在未开启虚拟化的原生环境中以相同的幅度出现，因此它不是 KylinX 引入的；物理页布局效应在没有二阶段翻译的同型号核机器上同样存在。 Effect: A slight overreach about the layout effect.
- **weakens** | Draft line 80 (一 item 6): 两者之比随工作集的变化与 N90 逐点相符 contradicts the conclusion (1.4, line 102). The ratios match only at 8-64 MB. At 4 MB it is 1.63 against 1.55 and at 6 MB 1.60 against 1.38. Corrected wording: 两者之比在 8–64MB 与 N90 相符（相差 0.03 以内），4–6MB 不符。 Effect: An internal overclaim to the authors; it could be copied into the reply.
- **weakens** | Draft line 58 (一 item 3, suggested reply wording): 在同系列平台上复现表明它来自片上互连按负载调频 states the N90 cause as proven, which contradicts lines 49 and 58 (仍然是推断的一环). Corrected wording: 该点在原生环境下同样双值波动，与 KylinX 无关；在同系列平台上，片上互连按负载调频可以复现同样的两个水平，这是最可能的来源（原测试平台当时的调频策略没有记录）。 Effect: Inconsistent guidance to the authors.
- **cosmetic** | Draft line 65 (一 item 4): 按实验 G5，就是互连处在高频 is too strong, because no host-side record exists for the guest data. Corrected wording: 按实验 G5，最可能就是互连处在高频. Effect: Wording only.
- **cosmetic** | Draft line 39 (一 item 2): 做了之后回复信（一）里第 4、5 点就可以写成同机实测 is wrong. Item 4 is already a same-boot comparison. Only item 5 (the cross-machine comparison) and the 【补测后填写】 bracket after it change. Corrected wording: 做了之后可以填入回复信（一）第 5 点后面【】里的内容，第 5 点的跨机器对照降为辅助证据。 Effect: Internal inconsistency.
- **cosmetic** | Draft line 37 against line 303: The run5 duration is given as 每种启动方式约 15 分钟 on line 37 and 每次约 20 分钟 on line 303. The script header (run5-mode-compare.sh line 9) says about 15 minutes. Corrected wording for line 303: 重启 4 次，每种启动方式测量约 15 分钟. Effect: Internal inconsistency.
- **weakens** | Draft line 304 (四, run30/run27 row): 不改任何系统设置 is wrong for run27. Its shim needs transparent_hugepage/enabled set to madvise or always (run30-n90-two-levels.sh lines 24-26; layoutshim.c lines 35 and 142, MADV_HUGEPAGE). The June environment and run30's own instructions use THP never. Corrected wording: run30 不改任何系统设置；run27 需要 THP 为 madvise 或 always（若 N90 处于 THP never 的测试环境，需临时改动并在结束后恢复）. Effect: The to-do table understates what the N90 experiment requires.
- **weakens** | Draft line 303 (四, run5 row): The row does not say which machine run5 should run on. It also does not say to fix the interconnect: run5 records the governor but does not set it. G5 shows the NoC state moves 64 MB random latency by about 26%, so rand.log across boot modes is confounded unless the NoC is fixed (tlb.log is not affected). Corrected wording: 在 N90（论文平台）上运行；每次运行前把 /sys/class/devfreq/nocfreq/governor 固定为 performance 并记录，或至少确认四种启动方式下互连状态相同. Effect: The planned decisive experiment could be confounded.
- **weakens** | Draft lines 248-250 (三 3.3, proposed paper text): 以2MB大页为 pVM 分配内存可以避免通用域内存与 pVM 页面落入同一2MB区间 is a prediction from the source code, not measured. Metadata pages taken by the monitor would still split some regions (conclusion 3.7). The text also does not say the measurement is from the N80 with the Rust-monitor kernel, and that the 4 KiB classification is inferred from source, not read from EL2. Corrected wording: 按实现，以2MB大页为 pVM 分配内存预期可以使通用域内存基本不与 pVM 页面落入同一2MB区间（监视器自身的元数据页仍会拆分少数区间），我们将其作为后续优化并验证. In the first sentence, add: 在与测试平台同型号处理器的另一台机器上 and 按内核实现推断被拆分为4KB表项. Effect: An unmeasured optimisation is stated as fact in the paper.
- **weakens** | Draft line 205 and line 210 (三 3.1): 其成因是两阶段地址翻译 and 上述增量来自硬件地址翻译路径 are inferences until the same-machine comparison is done. Line 220 acknowledges this only for the first phrase. Corrected wording: 我们将其归因于两阶段地址翻译 …… 正常访存不陷入监视器，上述增量不来自监视器的软件路径. Effect: The default paper text overclaims; only the note softens it.
- **cosmetic** | Draft line 174 (二): 各配置 10 轮测量中落在较高水平上的次数分别为 4、5、6–8、5–6 次 does not name the order of the configurations. Recomputed with a 12.0 ns threshold: kvm-off 4, nVHE 5, VHE 6, protected 5; at 11.3 ns: 4/5/8/6. Corrected wording: 原生 4 次、nVHE 5 次、VHE 6–8 次、KylinX 5–6 次（按划分线不同有一两次出入）. Effect: Ambiguity only.
- **cosmetic** | Draft line 174 (二), 两个水平各自的数值在各配置之间没有差别: The high-level means are 12.33/12.40/12.53/12.52 and the low-level means 10.35/10.16/10.30/10.40. They are not identical, but nothing in them is specific to protected mode. Corrected wording: 两个水平各自的数值在各配置之间没有 KylinX 特有的偏移. Effect: Wording only.
- **weakens** | Draft line 146 (二 (一) item 2): The text does not disclose that the six baseline boots and two protected boots are those in the same platform state. Two fast-state boots were excluded. One of the two protected boots is the Figure 7 boot itself, not part of 另一批. The standalone logs carry no timestamps or boot parameters. Corrected wording: 把处于同一平台状态的每次启动作为一个样本（共 8 次，排除了 2 次处于另一种平台状态的启动），两次开启 KylinX 的启动（图 7 的一次与另一批测试中的一次），64MB 处的中位数都高于六次对照启动 5.7–7.4ns，而六次对照启动彼此只相差 1.0ns. Effect: A reviewer could see the selection as hidden.
- **cosmetic** | Draft line 168 (二) and line 211 (三): 其代价又可与相邻的访存重叠 is stated as fact. The conclusion (3.5) says it is consistent with the data but not directly evidenced. Corrected wording: 其代价可能与相邻访存重叠. Effect: Wording only.
- **cosmetic** | Draft line 214 (三 3.1): Rounds the reviewer-cited 3.55% to +3.6%, and attaches p=0.40 (which is against native only) to all three baselines. Corrected wording: 相对原生、nVHE、VHE 分别为+3.55%、+2.9%、−3.0%，相对原生的差别不具统计显著性（置换检验 p=0.40）. Effect: Wording only.
- **cosmetic** | Draft lines 227-238 (三 3.2 table) against line 240: The note on line 240 refers to 1–12MB, but the table has no 12 MB row. Recomputed 12 MB row: 154.65 | 161.68 | +7.03 | +4.5%. Effect: Completeness only.
- **cosmetic** | Draft line 289 (三 3.7 references): The optional Kessler-Hill reference (page-placement cache conflicts) supports page-colour L3 set conflicts. The conclusion (4.3 先排除的) rules that mechanism out for this data, so the reference is a leftover. The lmbench doc/memhier.ms passage (lines 1119-1124 and 952-954, which I checked) suffices. Corrected wording: delete it, or add (仅作背景；本文数据不支持页颜色冲突这一机制). Effect: Could steer the reviewer toward an excluded mechanism.
- **cosmetic** | Draft line 51 (一 item 3): scripts/apply-masks.sh and verify-clean-env.sh were committed at 2026-06-04 20:41 (commit 08268522), after the June 3-4 runs; the protected try2 started 2026-06-04 12:05. Only prepare-host.sh predates them (27a3ffc1, 05-31). The statement that they 没有动它 rests on the procedure, not on a record. Corrected wording: 仓库里的准备脚本（其中 apply-masks.sh、verify-clean-env.sh 在采集之后才提交）只锁了 CPU 频率、屏蔽了服务，没有涉及互连调频. Effect: A minor provenance caveat.
- **cosmetic** | Draft line 56 (一 item 3): 比 12–64 MB 的读数还高约 20%: the N90 clean 12-64 MB stride-256 medians are 10.24-11.33 ns, so the high level of 12.4 is 10%-21% above them. Corrected wording: 比 12–64MB 的读数还高约 10%–20%. Effect: Wording only.
- **cosmetic** | Draft line 302 (四, first row): 决定图 7、图 8 的数据是不是 Rust 监视器测的: the June config file settles Figure 7 only. The host kernel of the Figure 8 guest runs was never recorded. Corrected wording: 决定图 7 的数据是不是 Rust 监视器测的（图 8 的宿主机内核没有记录，只能推测相同）. Effect: Scope of a check.
- **weakens** | Draft lines 298-308 (四, missing items): The table omits work that the draft itself depends on: (1) check the Arm ARM section number before citing it (line 285); (2) decide whether the whole paper switches to medians (lines 219, 276); (3) run run27/run24 on an N80 booted non-protected, to back the layout-unrelated-to-KylinX statement; (4) on the N90, read the governor with and without the desktop masked (conclusion section 9), not only fix it; (5) if the paper text 3.3 is kept, repeat run11/run12/run16 on the N90, which line 253 mentions but the table does not. Effect: The to-do list is incomplete for the claims as drafted.

## Discrepancies

- Line 183 says 一一对应; the primary data give 11 of 13 points (11 of 12 judgeable) in expG5.log against expG5-noc-samples.log.
- Line 163 says the processor models are the same; the workstation is a D3000 and the N80 a D3000M (hw-survey-n80.txt:28, memlat-d80f3-20260930/README.md:13).
- Line 80 says the random-access ratios match point by point; the conclusion line 102 records a mismatch at 4-6 MB (1.63 against 1.55, 1.60 against 1.38).
- Lines 215-216 offer only page layout as the paper-text explanation; part 一 line 49 and conclusion 4.3 make the interconnect the leading candidate.
- Line 304 says run27 changes no system setting; the script requires THP madvise or always.
- Line 37 gives 15 minutes per boot mode and line 303 gives 20; the run5 script says 15.
- Line 39 says letter items 4 and 5 become same-machine measurements; only item 5 and its bracket change.
- Line 193 states the interconnect state of the guest pVM run as fact; the conclusion 1.5 says 最可能 and 无法证实到底.
- Line 162 says 相符; part 一 lines 105-106 and conclusion 3.8 note a 3-4 cycle tension (N90 matches the 2 MiB class, not the expected 1 GiB class) that the letter omits.

## Threats to validity

- G5 is a single run on the N80 (protected boot, background pVM, desktop session) with the governors in fixed order. The N90 governor, and whether the phytium_noc module was even loaded, were never recorded. Every reviewer-facing sentence about the N90 interconnect is therefore an inference.
- The interconnect state moves 64 MB random latency by about 26% on the N80 (150.9 against 190.7 ns), roughly eight times the +3.25% under discussion. The letter's stage-2 explanation silently assumes all four N90 boots were in the same interconnect state. The data support that only indirectly: the three baselines agree within 0.3 ns at 0.75-12 MB, and under simple_ondemand random access sits at the 600 MHz floor. The letter should say so.
- The guest pVM data set has a directory name that disagrees with its own tag (xkernel-pkvm-np) and no host-side record. Any statement about it is inference.
- The translation-only comparison spans two machines with different chips, kernels, host EL and IPA size. The workstation was loaded and had no counters.
- The 4 KiB classification of pages that share a 2 MiB region with the pVM, and the 1 GiB-block classification, are inferred from source code, never read from EL2.
- The June preparation scripts in the repository were partly committed after the collection, so the June procedure is known only from the documents.
- The paper's section numbers (3.1, 5.1-5.3) were checked only through the docx text order; the headings carry no numbers in the extracted text.

## Recomputed tables

Host N90, lat_mem_rd -t stride 16, medians (ns), recomputed with host.py:

| size | kvm-off | protected | diff | rel | spread of 3 baselines | rel by mean |
|---:|---:|---:|---:|---:|---:|---:|
| 1MB | 19.41 | 19.43 | +0.02 | +0.1% | 0.07 | 0.0% |
| 2MB | 20.68 | 20.88 | +0.21 | +1.0% | 0.08 | +1.1% |
| 3MB | 36.60 | 37.31 | +0.71 | +1.9% | 0.07 | +1.9% |
| 4MB | 47.59 | 49.31 | +1.73 | +3.6% | 0.23 | +3.4% |
| 6MB | 67.14 | 72.59 | +5.45 | +8.1% | 0.24 | +7.9% |
| 8MB | 112.54 | 119.59 | +7.05 | +6.3% | 0.28 | +6.3% |
| 12MB | 154.65 | 161.68 | +7.03 | +4.5% | 0.16 | +6.8% |
| 16MB | 168.54 | 176.28 | +7.74 | +4.6% | 1.16 | +10.8% |
| 32MB | 180.61 | 188.66 | +8.05 | +4.5% | 2.11 | +9.0% |
| 64MB | 185.23 | 191.73 | +6.50 | +3.5% | 0.38 | +3.3% |

Other recomputed values:
- 64 MB random: means 182.21 / 181.10 / 181.21 / 188.13 (kvm-off / nVHE / VHE / protected); mean ratio +3.25%, exact permutation p=0.093; median ratio +3.51%, p=0.031.
- 8 MB stride 256: +3.55% by mean (p=0.399), +12.09% by median; against nVHE +2.87%, against VHE -3.02%; VHE against kvm-off +6.77%. Standalone repeat: +0.65%, against nVHE -2.81%, against VHE -3.01%.
- Per-boot 64 MB medians: baselines 185.05, 185.23, 185.32, 185.43, 185.55, 186.05; protected 191.73 and 192.41.
- PageFault: protected 0.2599 against kvm-off 0.2548 (+2.0%); noisy nVHE 0.2604 against clean nVHE 0.2550 (+2.1%).
- ProtFault: by mean -1.1%, by median +0.25%; standalone VHE against kvm-off -3.57% by mean.
- Memread at 67.11 MB: +0.55% by mean, -1.58% by median; kvm-off iteration 9 is 14826.32 MB/s.
- Sequential 64 MB stride 256: +0.29% by mean, -0.12% by median; against VHE -3.46%.

G5, N80, 8 MB stride 256 under simple_ondemand (13 points), recomputed with g5.py:

| level | values (ns) | 1800 MHz samples during the child |
|---|---|---|
| low (6) | 10.30, 10.42, 10.43, 10.47, 10.54, 10.71 | 3, 3, 1, 1, 2, 0 (10.71: contiguity about 0.65) |
| high (7) | 12.00, 12.51, 12.62, 12.62, 12.63, 12.63, 12.64 | 1 for 12.00, 0 for the rest |

- Ratio of the level medians: 1.208. Strict agreement with the rule: 11 of 13.
- performance: 9.08-10.09 ns. powersave: 12.66-12.74 ns.
- Random 64 MB: performance 150.9 ns; ondemand 190.6 and 190.9 ns; powersave 192.4 ns. Random 4 MB: 33.8 against 55.2 (ratio 1.63).

Guest N90, random access, medians (ns), recomputed inline:
- pVM against nVHE guest: 3 MB -26.5%, 4 MB -31.2%, 6 MB -31.8%, 8 MB -22.8%, 12-64 MB -20.1% to -21.5%. By mean the smallest gap is -16.7% (24 MB).
- pVM minus host kvm-off: -7.6 ns (3 MB) to -32.3 ns (64 MB).
- N80 at 1800 MHz against the pVM guest: 12 MB 130.2 against 129.5; 16 MB 140.8 against 141.2; 64 MB 150.9 against 152.9; 4 MB 33.8 against 36.0; 6 MB 60.4 against 55.3; 8 MB 100.9 against 97.9.

Translation-only chase (cyc_est medians, prefault=1; source expN4-d80f3.log and expN4-n80.log):

| configuration | workstation | N80 |
|---|---:|---:|
| 1024 x 2 | 13.96 | 13.96 |
| 1024 x 4 | 14.54 | 14.53 |
| 2048 x 1 | 25.15 | 38.10 |
| 2048 x 2 | 26.06 | 39.47 |
| 4096 x 1 | 28.16 | 42.34 |

Extra cycles when walks are needed (2048 x 1 minus 1024 x 2): 11.2 on the workstation, 24.1 on the N80.
