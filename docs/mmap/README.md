# mmap 相关实验与分析文档

本目录集中存放 pKVM host 侧 `mmap` 性能问题的分析、复测、拆解实验、应用级验证和优化方案文档。

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
