# mmap 相关实验与分析文档

本目录集中存放 pKVM host 侧 `mmap` 性能问题的分析、复测、拆解实验、应用级验证和优化方案文档。

> ## 📖 先读这篇：[pkvm-mmap-overview.zh-CN.md](pkvm-mmap-overview.zh-CN.md)
>
> **贯穿全程的总览**：从最早的 4-config Host 数据(症状) → mmap-split 拆分(定位到 munmap teardown)
> → gate(不在 EL2) → C0(backend 停顿) → C1(逐页 TLBI 根因) → 杠杆(FEAT_TLBIRANGE)，
> 每步带"背景→设计→代码→结果→与下一步的关系"，并如实保留两次机制修正。**想快速了解整件事的来龙去脉，看这一篇即可**；下面各篇是对应步骤的详细一手材料。

> ## 🔁 perf-only 复查（2026-06）：[perf-playbook/](perf-playbook/)
>
> 仅用 `perf`（不打补丁、不改 `common`）在 Kaitian 上从头复查同一问题的**可复用流程**，
> 用 perf 原生的 `:h`（EL2 周期）与 TLB-walk/stall 计数器替代原调查的两个自定义 hypercall。
> 含一份**可复现的 perf 编译手册**（[perf-playbook/build-perf-on-kaitian.md](perf-playbook/build-perf-on-kaitian.md)）。

## 建议阅读顺序

1. [lat-mmap-test-walkthrough.zh-CN.md](lat-mmap-test-walkthrough.zh-CN.md)

   从最基础的概念解释 lmbench `lat_mmap` 到底测什么，包括 `mmap`、触摸、page fault、`munmap` 和 lmbench 计时口径。

2. [pkvm-mmap-overhead-analysis.md](pkvm-mmap-overhead-analysis.md)

   早期 N90 受控实验与代码级机制分析，解释为什么 pKVM 下 `lat_mmap` 明显慢，而 `lat_mem_rd`、`bw_mem` 等稳定内存访问测试基本不受影响。

3. [n90-v10-mmap-host-report.md](n90-v10-mmap-host-report.md)

   N90 / Kylin V10 SP1 上 host 侧 mmap-only 四模式复测报告，包含 KVM-off、VHE、NVHE、pKVM，以及 C pKVM 内核复测结果。

4. [lmdb-pkvm-benchmark-plan.zh-CN.md](lmdb-pkvm-benchmark-plan.zh-CN.md)

   LMDB 应用级测试设计。该文档说明为什么 LMDB 虽然使用 mmap，但常规读写路径不等价于 lmbench `lat_mmap`。

5. [lmdb-kaitian-nvhe-pkvm-results.zh-CN.md](lmdb-kaitian-nvhe-pkvm-results.zh-CN.md)

   Kaitian 上 LMDB 在 NVHE 与 pKVM 下的实测结果。结论是长期打开后的 read/write 影响很小，频繁 open/close 更容易暴露 mmap 生命周期成本。

6. [mmap-split-kaitian-pkvm-comparison.zh-CN.md](mmap-split-kaitian-pkvm-comparison.zh-CN.md)

   当前最细的 `lat_mmap` 拆分实验。每个小测试用例都包含核心代码、测试内容、完整数据和结果分析。关键结论是 pKVM 的额外成本主要集中在写触摸后的 `munmap` teardown。

7. [pkvm-mmap-optimization-plan.zh-CN.md](pkvm-mmap-optimization-plan.zh-CN.md)

   针对 pKVM mmap 问题的优化入口和分阶段方案，包含拆分测试、hyp counter、TLBI/stage-2 teardown 插桩和回归验证思路。

8. [agile-popping-anchor.md](agile-popping-anchor.md) / [el2-gate-instrumentation.zh-CN.md](el2-gate-instrumentation.zh-CN.md)

   第二步（插桩与判别）的方案与使用说明：先用 EL2-only PMU 计数判别 munmap 退化是否进 EL2（gate），据结果决定走 host 侧分析（C1）还是 hyp 细粒度插桩（C2）。

9. [n80-gate-c0-results.zh-CN.md](n80-gate-c0-results.zh-CN.md)

   N80 上 gate + host 对照（C0）的完整实测报告：测试设计（结合脚本/代码/体系结构）、全部结果与分析。结论是退化不在 EL2、不在 TLBI 数量，而是 host stage-2 嵌套翻译使 teardown 访存的 backend 停顿放大（假设 a-2）→ 走 C1。

10. [c1-host-stage2-granularity.zh-CN.md](c1-host-stage2-granularity.zh-CN.md)

    C1 第一步：用新增的 xcore_stats op=3（只读自省，遍历 host stage-2 直方图）排除"碎片化"——host 内存 99.5% 是 1G block，benchmark 区域必在大块内。⚠️ **本篇当初据此把机制判成 a-2（嵌套 walk），已更正**：op=3 数据正确，但机制实为 a-1（逐页 TLBI），见第 11 篇。

11. [c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md)

    C1 机制判定（**最终结论**）：完整推理链——密集 munmap 对照证伪 a-2、源码定位 2MB 阈值、阈值扫描证实 a-1。退化 = **逐页 `TLBI` 的 stage-2 硬件税**（每条 host TLBI 在 pKVM 下多 ~0.27µs，gap∝TLBI 条数，在 2MB 整表-flush 阈值处断崖消失）。核心杠杆 = **FEAT_TLBIRANGE**（N80 没有）。

## 相关代码与数据

- `lat_mmap` 原始代码：[src/lat_mmap.c](../../src/lat_mmap.c)
- ns 精度复测代码：[src/lat_mmap_precise.c](../../src/lat_mmap_precise.c)
- mmap 拆分测试项目：[experiments/mmap-split](../../experiments/mmap-split)
- mmap 拆分批量脚本：[scripts/mmap-split-bench.sh](../../scripts/mmap-split-bench.sh)
- mmap 拆分分析脚本：[scripts/analyze-mmap-split.py](../../scripts/analyze-mmap-split.py)
- Kaitian mmap-split 原始数据：[results/mmap-split-kaitian](../../results/mmap-split-kaitian)
- LMDB 测试程序：[scripts/lmdb-pkvm-bench.c](../../scripts/lmdb-pkvm-bench.c)
- LMDB 批量脚本：[scripts/lmdb-pkvm-bench.sh](../../scripts/lmdb-pkvm-bench.sh)
- Kaitian LMDB 原始数据：[results/lmdb-bench-kaitian](../../results/lmdb-bench-kaitian)

## 当前结论

目前最有依据的判断是：

```text
pKVM 下 host 侧 lat_mmap 写路径变慢，主要不是 mmap 建立，也不是 first-touch 访问本身，
而是 touch 之后解除映射时的 munmap teardown 被显著放大。
```

下一步优化和插桩应优先围绕 `munmap_after_write_touch` 展开，重点观察 pKVM host stage-2 teardown、TLBI/shootdown、权限转换和连续 range 合并机会。

**第二步（N80 实测，2026-06-11，见 [n80-gate-c0-results.zh-CN.md](n80-gate-c0-results.zh-CN.md)）已判别**：

```text
退化不在 EL2（gate ΔEL2=0，计数器经 1.68 亿 cycle 阳性对照验证可用），
也不在 TLBI 数量（tlb_finish_mmu 占比极小、TLBI/walk 次数与 nvhe 相同）；
N80 上 protected 比 nvhe 慢 1.81×(+447µs/iter@64MB)，额外周期几乎全部是
backend(访存)停顿——即 host stage-2 嵌套翻译放大了 munmap teardown 的
页表 walk/页结构访存开销（假设 a-2）。
```

→ 路线定为 **C1（host 侧）**。

**C1 机制判定（N80 实测，2026-06-12，最终结论见 [c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md)）**：

```text
退化 = 逐页 TLBI 的 stage-2 硬件税（假设 a-1），不是嵌套 walk（a-2）。
证据链：op=3 自省排除碎片化(host RAM 99.5% 1G block) → 密集 munmap 对照 gap≈0
(页多反而无税)证伪 a-2 → 源码定位内核在范围≥2MB(MAX_DVM_OPS=512)时由"逐页TLBI"
切"单条整表flush" → 阈值扫描：gap 在 2MB 处断崖消失、<2MB 时 gap∝TLBI 条数，
每条 host TLBI 在 pKVM 下多 ~0.27µs。原 benchmark 稀疏 munmap gap +438µs 与之闭环。
```

→ 核心杠杆 = **FEAT_TLBIRANGE**（range TLBI 合并逐页 TLBI；N80 无此特性故退化明显，平台相关）；大 munmap 已自动 coalesce 成整表 flush、无税。
**注**：早先的 H2/"嵌套 walk 固有税"机制结论是误判，已在第 10、11 篇更正（op=3 数据正确，机制解释下早了）。
