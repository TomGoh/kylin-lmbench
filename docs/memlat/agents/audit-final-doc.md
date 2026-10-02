# 核查报告：audit:final-doc

## Summary

Final audit of docs/memlat/memlat-rootcause.zh-CN.md (branch pkvm-memlat-rootcause, HEAD f44422c8), sections 1–6 and 9, checked against primary sources.

Checks done:
- I regenerated derived/state-tables.md and host-n90-tables.md with copies of analyze-state-experiments.py and analyze-host-memlat.py. Both are byte-identical to the committed files.
- With my own parsers I recomputed the N90 host CSVs, the standalone batch, Exp G5 (child windows matched to 100 ms NoC samples and to the frame records), H4, H5, H8 and H7 (frame hand-back), and the guest Fig. 8 directories.
- I checked the lmbench timing code and the klinux tags 6.6.0-73.76 and 6.6.0-79.93 (phytium_noc.c, X1_RMS, KVM_PGTABLE_MIN_BLOCK_LEVEL, mm/kymm/Kconfig).

Numbers that reproduce:
- Every N90 number in sections 1.1, 1.3, 3.1–3.5, 4.1, 4.2, 5.1, 5.3, 5.5 and 6, including the exact permutation p-values, Mann-Whitney, Fisher, the bootstrap intervals, the per-size increments and the dip counts.
- The H4/H5 and H8 ratios, and the G5 values in sections 1.4, 4.3 part 6 and 5.3.
- The 1.6 kernel facts, and the NoC driver defaults at both kernel tags.

The core verdicts hold:
- +3.55% is a count difference between levels (Fisher p = 0.66).
- +3.25% is a mean. The robust increment is +6.3 to 6.7 ns, or +3.4 to 3.6% by medians.

Problems found:
1. **Wording stronger than the evidence, against critic-g and the worklog's own 11.34 correction.**
   - Section 5.3 (line 869) states as fact that the N90 slow state is the NoC at low frequency and the fast state the NoC at high frequency.
   - The 1.4 heading, the 4.3 judgement (line 717) and 1.5 still say 'most likely'.
   - The 1.4 heading also attributes the fast state to traffic-following, although the document's own account is that the NoC was held high.
2. **The 1.4 summary '11 of 12 judgeable points' is selective.** The one-sample 12.00 ns high point was dropped as not judgeable, while the two one-sample low points were kept. The honest count is 11 of 13 consistent, with two exceptions, from one run, Fisher p of about 0.03.
3. **Section 4.3 part 6 says ENOUGH=10000 could shorten each lmbench timing to about 10 ms. The lmbench source refutes this.** lat_mem_rd passes 100000 us, and get_enough() returns max(ENOUGH, e).
4. **1.4 and the 4.3 judgement present '4–6 MB constantly slower' as a reproduced N90 feature.** They ignore critic-g ng#3(4): within the N90 the quiesced/fast ratio there is only 1.08/1.11, against 1.16/1.25 for the N80.
5. **Section 3 does not answer critic-g's point that G5 makes the NoC state an alternative explanation for the +3.25%.**
6. **Factual slips.**
   - 4.4 says the 8 MB child got back 15–47% of the 6 MB child's pages. In fact it got back 21–63% of them; 15–47% is the share of the 8 MB child's own buffer.
   - 4.4 says 514 frames were lost; the count is 518.
   - 4.4 says CONFIG_KYLIN_MM_PAGEPOOL is off by default. It is default y; only the runtime switch is off.
   - The 4.3 E1/E2 table says stride 32 has 1/40 high values, which contradicts 0/40 in the 4.3 part 1 table.
   - '12–64 MB 1.5–3.5% slower' is false at 48 MB (−0.4%).
   - The 8 MB random ratio differs by 0.034, not 'within 0.03'.
   - The 4.3 part 5 table's high-8 MB row sums to 92 of 93.
   - '96%–100%' hand-back is 91% at 1 MB.
   - Section 2's '32768 cache lines' is the access count; 8 MB is 131072 lines.
   - The null-syscall range omits a 0.1040 value.
7. **Stale after G5.**
   - Header line 3 still says all measurements were on 2026-09-30.
   - The data-kind table still gives the N80 date and 'performance, fixed 1800 MHz'.
   - The E1 cell 'not measured' in the 4.3 comparison table.
   - The section 9 row 'two to three times larger', which the 4.3 text and the worklog have already narrowed to strides 64–256.
   - The section 9 row that says 'no setting change', although it includes run27, which needs THP.
   - Section 7 says 'changed twice' while 1.4 says 'three times'.
   - The worklog corrections table has no G5-round entries.

None of these invalidates the two main conclusions about Figure 7. Items 1, 2, 4 and 5 weaken how strongly the NoC attribution and the stage-2 attribution may be stated.

## Defects

- **weakens** | Section 5.3, line 869 ('所以 N90 干净环境的随机访问就是"互连在低频"，"快"状态就是"互连在高频"'): Stated as an established fact about the N90. G5 is a reproduction on another machine (N80, protected mode, 1.9 GHz, idle pVM in the background), and the N90 NoC governor, its frequency, and even whether the driver was loaded were never recorded. This contradicts 1.4 of the same document ('还没有在 N90 上确认') and critic-g ng#3 ('They do not show what NoC frequency the N90 ran at'). The preceding line also presents 4–8 MB as matching (1.37–1.63 against 1.34–1.55), although 1.4 itself says 4–6 MB do not match (1.63 vs 1.55, 1.60 vs 1.38). Effect: Overstates the NoC attribution in the one place a reader of section 5 will quote. Correct wording: '在 N80 上，随机访问在按流量调频时始终停在 600 MHz 的水平，它与 1800 MHz 之比在 8–64 MB 与 N90"干净环境 ÷ 快状态"相差 0.02–0.035，4–6 MB 不符（1.63 对 1.55，1.60 对 1.38）。这与"N90 干净环境的随机访问对应互连低频、快状态对应互连高频"相符，但 N90 当时的互连状态没有记录，没有在 N90 上确认。'
- **weakens** | 1.4 heading (line 90), 1.5 (line 111), 4.3 judgement (line 717), 4.4 (line 725): Uses '最可能' / '主要是'. critic-g ng#4 explicitly rejected 'most likely' as going beyond the evidence and gave the safe wording 'sufficient and leading candidate, not shown to be the cause on the N90'; the bold sentence of 1.4 (line 101) and the worklog 11.34 correction adopt that wording, so the document now uses two strengths at once. The 1.4 heading also says both the slow AND the fast state come from '按流量调频'. In the document's own account (1.4 line 104, 5.4) the fast state means the NoC was held high, by an unidentified agent or by background traffic, not traffic-following as such. Effect: Wording inconsistency on the central new judgement. Correct heading: '1.4 两个水平和 N90 的"快""慢"两种状态：片上互连的调频状态是充分且最主要的候选成因（没有在 N90 上确认）；这个点同时对缓冲区的物理页布局敏感。' In 4.3 line 717 and 1.5 replace '最可能来自/最可能是' with '最主要的候选是'.
- **weakens** | 1.4, line 96 ('12 个可以判断的点里 11 个对得上，例外的那一个缓冲区物理上大半连续'): There are 13 points, not 12. 'Judgeable' is defined nowhere. Three points had exactly one 1800 MHz sample: sw6 (12.00 ns, high), sw10 (10.47, low) and the stride-256 part of the full command (10.43, low). Only the contradicting one (sw6) was excluded as not judgeable; the two agreeing ones were kept. Section 4.3 part 6 (line 686) lists all 13 correctly. The adjacency explanation of 10.71 ns is post hoc (critic-g ng#2). Effect: Makes the per-child association look cleaner than it is. Correct wording (my g5check.py, expG5.log against expG5-noc-samples.log): '13 个点里 11 个符合"子进程运行期间有一次 1800 MHz 采样就是低值"；例外是 12.00 ns（有一次 1800 MHz 采样却是高值）和 10.71 ns（没有 1800 MHz 采样却是低值，它的缓冲区连续度 0.71，这是事后的解释）。只有一次运行，Fisher 检验 p ≈ 0.03。'
- **weakens** | 1.4 third bullet (line 99) and 4.3 judgement (line 716: '同时出现的还有 N90 的其余特征（…4–6 MB 固定偏慢…）'): Ignores critic-g ng#3(4). The comparison switches to a cross-machine baseline: N90 quiesced is 13%/18% slower than N80 at 1800 MHz. Within the N90 the quiesced/fast ratio at 4/6 MB is only 1.081/1.107, against N80 ondemand/performance 1.159/1.252. The N90 quiesced level (5.48/8.26 ns) lies between N80 1800 MHz (4.85/6.99) and N80 600 MHz (5.62/8.75), not at the 600 MHz level. Also, 4.4 says the NoC is 'not pushed up' at 4–6 MB. Effect: One of the three 'reproduced N90 features' cited for the NoC attribution does not reproduce within the N90. Correct wording: '4、6 MB 顺序访问在 N80 上按流量调频时固定地慢 16%、25%（只有一个水平）。N90 干净环境在这两处也只有一个水平，但它相对 N90"快"状态只慢 8%、11%，绝对值落在 N80 的 1800 MHz 和 600 MHz 两个水平之间；这一项只是方向一致。'
- **weakens** | Section 3 (3.1–3.6) and 1.1/1.2, after G5: critic-g ('Missing for root cause', 64 MB (a)) points out that G5 shows the NoC state moves 64 MB random latency by about 26% (150.9 against 190.7 ns), eight times the cited +3.25%. The +3.25% therefore cannot be attributed to stage-2 unless the NoC state is shown to be equal across the four boots. Section 3.6 lists the remaining alternatives (L3 refills, one boot per mode) but not the NoC state. The data do contain arguments against a NoC explanation, and the document does not make them:
- by 1.4/5.3 the quiesced random runs already sit at the low NoC level (N80 ondemand 190.7 ≈ powersave 192.4), so a NoC difference could not make pkvm slower still;
- the pkvm increment is zero up to 2 MB and peaks at 6 MB (+8.1%), whereas a NoC-state mixture would be relatively largest at 4 MB (state ratio 1.55);
- the three baselines agree within 0.3 ns at 0.75–12 MB. Effect: The stage-2 explanation of +3.25% is left open to an alternative the investigation itself introduced. Add to 3.6: '另外的解释还有互连状态：G5 里互连状态让 64 MB 随机访问相差约 26%。现有数据不利于它：按 5.3，干净环境的随机访问本来就处在互连低频的水平，互连状态不会让 protected 比它更慢；protected 的增量在 2 MB 以内为零、在 6 MB 处最大，而两种互连状态之比在 4 MB 处最大（1.55）。各次开机的互连状态没有记录，所以这一点只是不利，不是排除。'
- **cosmetic** | 4.3 part 6, line 696 (parenthesis about 'ENOUGH: 10000'): Refuted by the lmbench source. lat_mem_rd.c:143 calls benchmp(..., 100000, ...). lib_timing.c:173 does 'enough = get_enough(enough)', and get_enough (lib_timing.c:1407-1410) returns max(long_enough, e), where long_enough comes from the ENOUGH variable (1540-1541). With ENOUGH=10000 the interval stays 100000 us, so every timing on the N90 was also at least about 0.1 s. Section 5.1 line 797 (0.8 s at 64 MB, 0.2 s at 16 MB) agrees with count = len/stride (lat_mem_rd.c:128). Effect: Adds a spurious caveat to the G5-to-N90 transfer, and contradicts section 2 and 5.1. Correct wording: 'N90 结果头里的 ENOUGH: 10000 不会缩短 lat_mem_rd 的计时：它调用 benchmp 时传入 100000 µs，get_enough() 取两者中较大的一个，所以 N90 上每次计时同样至少约 0.1 秒。'
- **cosmetic** | 4.4 second bullet (line 737: '8 MB 的子进程只拿回 6 MB 子进程 15%–47% 的页'): Wrong denominator. From expH7-pfns.log, the 6 MB child (1537 pages) shares 367, 315 and 970 frames with the 8 MB child in sweeps 2, 3 and 4. That is 24%, 20% and 63% of the 6 MB child's pages, or 18%, 15% and 47% of the 8 MB child's 2049 pages. critic-f also quotes 24%, 21% and 63% returned. The figure '1052–1707 new pages' reproduces. Effect: Correct wording: '8 MB 的子进程只拿回 6 MB 子进程 1537 页中的 315–970 页（20%–63%，占自己缓冲区的 15%–47%）'.
- **cosmetic** | 4.4 first bullet (line 736: '丢的 514 页全是成对的页'): 3073 − 2555 = 518. My recount of expH7-pfns.log (sweep 4, 3073→4097) gives 518 lost frames, all 518 with their buddy (pfn^1) in the 12 MB child. The 514 comes from the kernel-alloc audit's different pairing count. Effect: Correct wording: '丢的 518 页全是成对的页'.
- **cosmetic** | 4.4 third bullet (line 743: '麒麟自己的页池（CONFIG_KYLIN_MM_PAGEPOOL，默认关闭）'): mm/kymm/Kconfig at both 6.6.0-73.76 and 6.6.0-79.93 declares 'config KYLIN_MM_PAGEPOOL ... default y', and it is sourced unconditionally from mm/Kconfig:1378. Only the runtime switch is off by default (kymm_pool.c: 'bool kymm_pool_enabled;', zero-initialised). audit-kernel-alloc says the same. Effect: Correct wording: '麒麟自己的页池（CONFIG_KYLIN_MM_PAGEPOOL 默认编进内核，运行时开关 /proc/kymm_pool/enabled 默认关闭）'.
- **cosmetic** | 4.3 E1/E2 table, row 3 (line 708: '步长 32 是 1/40'): Contradicts the table in 4.3 part 1 (line 590: stride 32 high count 0, '只有一个值高 8%') and the 12% criterion used everywhere else. My recount: stride 32 max/base = 1.081, so 0/40 high. Stride 64 is 4/40 and strides 128–1024 are 28/22/17/22. Effect: Correct wording: '步长 32 是 0/40（只有一个值高 8%），64 是 4/40，128–1024 是 17–28/40'.
- **cosmetic** | 4.3 part 6, line 690 ('12–64 MB 在 simple_ondemand 下只比 performance 慢 1.5%–3.5%'): At 48 MB the ondemand median (10.039, n=12) is below the performance median (10.078), i.e. −0.4%. The derived table that produced 1.5–3.5% omits 48 MB. Other sizes: 12 MB +3.2% (12 sweeps) or +3.5% (13 points); 16, 24, 32 and 64 MB +1.5% to +2.2%. Effect: Correct wording: '12–64 MB 在 simple_ondemand 下与 performance 相差 −0.4% 到 +3.5%'.
- **cosmetic** | 1.4 line 102 ('随机访问的比值只在 8–64 MB 与 N90 相符（相差 0.03 以内）'): At 8 MB the ratios are 1.374 (N80) and 1.341 (N90), a difference of 0.034. At 64 MB it is 0.030. Effect: Correct wording: '相差 0.02–0.035'.
- **cosmetic** | 4.3 part 5 table (lines 662-665): The 'high' row (57+16+19) sums to 92, not 93. One 12 MB value is below 0.97 (0.962); critic-f and the worklog corrections table record this, but the table does not show it. Effect: Add a column '低于 0.97: 1 / 0', or a footnote.
- **cosmetic** | 4.3 part 3, line 642 ('子进程的缓冲区基本都包含上一个子进程的页（96%–100%…）'), and 4.4 line 735 ('…全部物理页'): From expH7-pfns.log the share of the previous child's frames found in the next child is 0.93 (0.5→0.75 MB) and 0.91 (1→1.5 MB) in all four sweeps, 0.95–1.00 from 1.5 MB on, and 0.83 once at 12→16 MB. Effect: Correct wording: '91%–100%（1.5 MB 以上 95%–100%）'; drop '全部'.
- **cosmetic** | Header line 3; data-kind table lines 30 and 44: Line 3 says all measurements were on 2026-09-30 and the document was finalised on 2026-10-01. In fact H7 and H8 ran on 2026-10-01 and G5 on 2026-10-02 (meta.log lines 54-58), and the document was last changed on 10-02 (commit a9837f37). Line 30 gives the N80 date as 2026-09-30 only. Line 44 says the N80 interconnect was 'performance，固定 1800 MHz', which was no longer true during G5. Effect: Fix:
- line 3: '测量在 2026-09-30 至 10-02'
- line 30: '2026-09-30 至 10-02'
- line 44: 'performance，固定 1800 MHz（实验 G5 除外：临时改为 simple_ondemand 和 powersave）'
- **cosmetic** | Section 9, row 'Why is the layout effect two to three times larger on the N80 than on the workstation' (line 1021): Contradicts 4.3 part 2 (line 620) and the worklog correction to 11.23: the workstation effect is smaller only at strides 64–256. At strides 512 and 1024 it is as large (8 MB: 1.13 and 1.22 against 1.21 and 1.17). Effect: Correct wording: '布局效应为什么在步长 64–256 上 N80 比没有二级翻译的工作站大两三倍（步长 512、1024 上两台一样大）'.
- **cosmetic** | Section 9, row 3 (line 1018: '需要什么: N90，root，不改系统设置'): The row also proposes run27-lmbench-layout-shim.sh. Per run30's own header (lines 23-26), run27's pool needs transparent_hugepage/enabled set to madvise or always, which is a setting change against the June THP=never environment. Effect: Correct wording: 'run30 不改系统设置；run27 要临时把 THP 设为 madvise'.
- **cosmetic** | 4.3 E1/E2 table, row 2, E1 column ('没有量过…'): Stale after G5. The 600 MHz vs 1800 MHz level ratio was measured at stride 256 (1.21 between the ondemand levels; powersave/performance 12.70/9.92 = 1.28). Only the other strides remain unmeasured. Effect: Correct wording: '只在步长 256 上量过（G5：按流量调频的两个水平之比 1.21）；其余步长没有量过'.
- **cosmetic** | 5.2, row '物理页布局不同' (line 811): Cites H6 'sorted vs shuffled within 1.4%' as evidence. The worklog correction to 11.28 and section 4.3 line 615 already note that this comparison cannot show an order effect by construction, because lmbench -t randomises page order. What H6 measured is huge-page-derived vs ordinary frames: 0–4%, 13% at 6 MB. Effect: Correct wording: 'N80 上 lmbench 自己的随机访问测试，缓冲区取自大页还是普通分配，读数相差 0–4%（6 MB 处 13%，实验 H6）…解释不了 18%–35%'.
- **cosmetic** | 1.3, line 88 ('对一个与 pKVM 无关…的因素'): The layout factor exists without stage-2, but its size at stride 256 was measured only in protected mode (19%). On the stage-2-free workstation it is 8% at 8 MB, and 4.3 part 2 says the cause of the difference is not known. Effect: Correct wording: '对一个并非 pKVM 引入、测试时既没有控制也没有记录的因素（没有二级翻译的同型号核机器上也有，步长 256、8 MB 处是 8%）敏感到这种程度'.
- **cosmetic** | Section 2, line 136 ('8 MB 共 2048 页、32768 条缓存行'): The cache line is 64 B (hw-survey-n80.txt line 50: coherency size 64), so 8 MB is 131072 lines. 32768 is the number of accesses at stride 256, one line out of every four. Effect: Correct wording: '8 MB 共 2048 页，访问 32768 次（每 4 条缓存行取 1 条）'.
- **cosmetic** | 3.3, line 244 ('空系统调用在四种启动方式下都是 0.1028–0.1029 微秒'): The nVHE and protected boots each have one iteration at 0.1040 (CSV lat_syscall,null). Effect: Correct wording: '中位数都是 0.1028–0.1029 微秒（nVHE、protected 各有一轮 0.1040）'.
- **cosmetic** | 1.4 line 108 vs section 7 line 981; worklog corrections table: 1.4 says the judgement on the two levels changed three times; section 7 says twice (E1→E2→E1), with G5 listed separately. The worklog's top corrections table has no rows for the corrections made in the G5 round. Those corrections appear only inline in 11.34: predictions 1 and 2 scored 'held', 'most likely', the 1.39 ratio, the wrong script name, and 11.02 against 11.05. Effect: Use one count: '改过两次判断（E1 → E2 → E1），G5 之后有了直接复现'. Add the G5-round rows to the worklog corrections table.
- **cosmetic** | 1.4 line 93 and 5.4 line 887 (the June preparation scripts did not touch devfreq): Correct as far as the committed scripts go: grep finds no devfreq or nocfreq in prepare-host.sh, apply-masks.sh or verify-clean-env.sh. But these scripts were first committed on 2026-06-04 20:41 (commit 08268522), after the pkvm try2 run that started at 12:05 the same day. Section 3.7 says this; 1.4 and 5.4 do not. Effect: Add '（这几个脚本是数据采集之后才提交的，按文档就是当时用的）'.
- **cosmetic** | Section 8 (outside the 1–6/9 scope, internal consistency): The row on 'LLC 边界 +3.55%' and the row '实验环境' were not updated after G5. They mention only page-layout sensitivity and the CPU clock, not the interconnect governor, which 1.4 now calls the leading candidate and which was not recorded. Effect: Add '并且随片上互连的调频状态在两个水平之间切换（N80 上复现，N90 没有记录）' and '互连调频策略没有记录'.

## Discrepancies

- 1.4 line 96: '12 judgeable points, 11 match' against 13 points with 2 exceptions (sw6 12.00 ns with one 1800 MHz sample; sw12 10.71 ns with none).
- 4.3 line 696: ENOUGH=10000 would shorten each timing to about 10 ms. Source: get_enough() returns max(ENOUGH, 100000), so it stays at 0.1 s.
- 4.3 line 708: stride 32 '1/40' high, against line 590 and my recount: 0/40 (max/base 1.081).
- 4.4 line 737: '15%–47% of the 6 MB child's pages'. Recount: 20%–63% of the 6 MB child; 15%–47% is the share of the 8 MB child's own buffer.
- 4.4 line 736: '514 lost frames' against 3073 − 2555 = 518 lost, all paired.
- 4.4 line 743: CONFIG_KYLIN_MM_PAGEPOOL 'default off' against Kconfig 'default y'; only the runtime switch is off.
- 4.3 line 690: '12–64 MB 1.5%–3.5% slower under ondemand' against −0.4% at 48 MB.
- 1.4 line 102: 'within 0.03 at 8–64 MB' against 0.034 at 8 MB (1.374 vs 1.341).
- 4.3 part 5 table: the high-8 MB row sums to 92 of 93.
- 4.3 line 642: hand-back '96%–100%' against 0.91–0.93 at 0.5–1.5 MB.
- Section 2 line 136: '32768 cache lines' in 8 MB against 131072 lines of 64 B (32768 accesses).
- 3.3 line 244: null syscall 'always 0.1028–0.1029' against one 0.1040 in nVHE and in pkvm.
- 1.5 '8–32 ns' against section 6 '7.6–32 ns' (rounding).
- Header line 3 and the data table (lines 30, 44): dates and the NoC row predate H7, H8 and G5.
- Section 7 'changed twice' against 1.4 'changed three times'.
- Section 9 'layout effect two to three times larger on the N80' against 4.3 and the worklog correction (only strides 64–256).
- 5.3 line 869 states the N90 states ARE the NoC frequencies, against 1.4 'not confirmed on the N90' and critic-g.
- 1.4 and 4.3 headline wording 'most likely' against critic-g's required wording 'sufficient and leading candidate'.
- All other checked numbers reproduce exactly:
- 1.1: +3.25%; medians +3.51/+3.40/+3.61%; p 0.093/0.087/0.073, 0.031/0.033/0.045; Mann-Whitney 0.011/0.009/0.009; bootstrap interval −0.4 to +6.6%.
- 3.2: increments and the 'pkvm above all 30 baseline values' counts.
- 3.4: standalone increments.
- 3.5: stride table.
- 4.1: perm 0.40/0.49, Mann-Whitney 0.22, Fisher 0.66/1.00, interval −0.47 to +1.23 ns, the two group means, the neighbouring-row counts.
- 4.3: H4/H5 table and N90 level medians and counts; H8 ratios.
- G5: every value and NoC-sample count.
- 5.1: table and dip counts.
- 5.3: both tables.
- 5.5: Memread.
- 6: guest ranges and medians.
- 1.6: X1_RMS history, commit b1b2979f0c0bf 2026-06-29/2026-07-07, first tag 6.6.0-76.85.

## Threats to validity

- G5 is one run on the N80, with the governor states in fixed order (performance, then ondemand, then powersave) and no return to performance. All N80 data are protected mode with an idle pVM, THP always and a desktop session. Nothing about the N90's NoC governor, its frequency, or whether the =m module was loaded was ever recorded.
- drivers/devfreq/phytium_noc.c differs between 6.6.0-73.76 (the June N90 kernel) and 6.6.0-79.93 (the N80 kernel used for G5). At 79.93 the file has v1/v2 paths and suspend handling. For the PHYT0047 (v1) device both tags register simple_ondemand with polling 100 ms, upthreshold 80 and downdifferential 10, and read the same WR_NOLAST_HANDSHARK_NUM registers. So the behaviour is the same by source, but it was not run on the N90.
- The N80 ondemand 'low' 8 MB level (10.3–10.7 ns) is a mixed state, about 4–5% above the 1800 MHz level (9.9–10.1 ns). The match of absolute values with the N90 (10.3/12.4 ns) is a cross-machine comparison: 1.9 GHz against 1.8 GHz core, different DRAM, protected only.
- The +3.25% stage-2 attribution still rests on a single protected boot (try2, chosen after seeing try1), with no same-machine mode comparison. The NoC state of each June boot is unknown, and G5 shows NoC state moves 64 MB random latency by about 26%.
- Several N80 numbers in 3.7 and 3.8 rely on the analyst's derived tables. I regenerated those tables identically from the raw logs with the analyst's scripts, but recomputed independently only Exp N/N4 differences, H4, H5, H7, H8 and G5.
- The June prep scripts (prepare-host.sh, apply-masks.sh, verify-clean-env.sh) were committed after the data were taken (2026-06-04 20:41), so the claim that 'the scripts did not touch devfreq' depends on the committed version being what was run.
- Stage-2 block sizes (the '1 GiB-candidate' slots) were never read from EL2. The workstation baseline differs in IPA limit (48 bits against 40; I confirmed 48 in this machine's kernel log), in kernel version, and in load.

## Recomputed tables

| Check | Doc | My recomputation (source) |
|---|---|---|
| 64 MB rand, pkvm vs kvmoff/vhe/nvhe, mean | +3.25/+3.82/+3.88% | +3.25/+3.82/+3.88% (CSV) |
| 64 MB rand, medians, diff | +6.50/+6.30/+6.68 ns | same; standalone batch +7.09/+6.86/+6.37 ns |
| 64 MB perm p (mean / median), Mann-Whitney | 0.093/0.087/0.073; 0.031/0.033/0.045; 0.011/0.009/0.009 | identical (exact enumeration) |
| 8 MB seq256 pkvm − kvmoff | +0.397 ns, +3.55%; p 0.40/0.49; Mann-Whitney 0.22; Fisher 0.66/1.00; CI −4% to +11% | +0.397, +3.55%; 0.399/0.49; 0.218; 0.656/1.00; −0.47 to +1.23 ns (−4.2% to +11.0%) |
| G5 ondemand 8 MB (13 points) | 6 low (10.29–10.71), 7 high (12.00–12.64) | same; n1800 low: 3,2,3,1,1,0; high: 0,0,1,0,0,0,0 |
| G5 random ondemand/perf, 4/6/8/12/16/64 MB | 1.63/1.60/1.37/1.29/1.27/1.26 | 1.632/1.596/1.374/1.290/1.274/1.264 |
| N90 quiesced/fast random | 1.55/1.38/1.34/1.27/1.26/1.23 | 1.546/1.385/1.341/1.270/1.256/1.234 |
| G5 seq256 12–64 MB ondemand/perf | +1.5% to +3.5% | +3.2% (12, 12 sweeps), +2.2, +2.0, +2.2, **−0.4 (48)**, +1.5 |
| N90 8 MB high counts, strides 16/32/64/128/256/512/1024 | 0/0/4/28/22/17/22 (table); '32: 1/40' (row) | 0/0/4/28/22/17/22 |
| H4 stride 256, 8 MB sorted/shuffled8 | 8.90/10.62 (1.19) | 8.90/10.62 (1.193) |
| H8 head8/sorted, 12 MB, s128/s256 | 1.157/1.188 | 1.157/1.188 |
| H7 6→8 MB frames returned (sweeps 2–4) | '15%–47% of the 6 MB child' | 367/315/970 of 1537 = 24/20/63% (= 18/15/47% of the 8 MB child) |
| H7 sweep 4, 12→16 MB lost | 514 | 518 (all paired) |
| lmbench timing with ENOUGH=10000 | 'about 10 ms' | ≥ 100 ms (get_enough = max) |
| KYLIN_MM_PAGEPOOL default | off | Kconfig default y; runtime off |
