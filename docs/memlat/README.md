# 内存访问延迟根因调查

本目录存放 2026-09-30 针对"pKVM 宿主机内存访问延迟"的调查材料。起因是论文审稿意见：

> 图7和图8中，LLC 边界延迟上升了 3.55%，64MB 随机访问延迟上升了 3.25%。文章仅描述了现象，缺乏根本原因解释。

## 数据是在哪里跑的

读任何一份材料之前先看这张表。三类数据不能混用。

| 类别 | 在哪里跑 | 数据目录 | 对应论文 |
| --- | --- | --- | --- |
| 宿主机实验 | 直接在 N90 的宿主 Linux 上跑 lmbench，只切换 `kvm-arm.mode`，不启动虚拟机 | `results/n90-day3-host/`、`results/standalone-mem-bench/` | 5.2 节，图 7 |
| 虚拟机内实验 | 在 N90 上用 crosvm 启动 x-kernel 客户机，lmbench 跑在客户机里面 | `results/xkernel-n90-*` | 5.3 节，图 8–10 |
| 本次补充测量 | 在 N80 的宿主 Linux 上，protected 方式启动，没有虚拟机 | `results/memlat-n80-20260930/` | 解释图 7 的机制 |

审稿人引用的 3.55% 和 3.25% 都是宿主机实验的数字。

## 文件

| 文件 | 内容 |
| --- | --- |
| [memlat-rootcause.zh-CN.md](memlat-rootcause.zh-CN.md) | 结论：两个数字各自的成因、证据和还没解决的问题。**核查完成后写入** |
| [memlat-investigation-worklog.zh-CN.md](memlat-investigation-worklog.zh-CN.md) | 按时间顺序的过程记录，包括被推翻的假设 |
| [agents/](agents/) | 多代理调查和核查的原始报告 |
| [../../experiments/memlat-probe/](../../experiments/memlat-probe/README.zh-CN.md) | 测量工具、运行脚本、分析脚本 |
| [../../results/memlat-n80-20260930/](../../results/memlat-n80-20260930/README.md) | N80 上的原始日志、硬件信息、汇总表 |
| [../n90-kvm-host/llc-boundary-8mb-analysis.md](../n90-kvm-host/llc-boundary-8mb-analysis.md) | 更早的一份只凭数据做的分析；本次调查用代码和机器对它做了检验 |

## 与仓库里已有材料的关系

- `docs/n90-kvm-host/` 是 2026-06 的四模式宿主机实验报告，给出了"随机访问慢 3%–7%"的现象和架构层面的推测，
  当时没有硬件计数器数据。
- `docs/mmap/` 是 mmap 和 munmap 方向的调查，结论是小范围 munmap 逐页发 TLBI 的代价在二级翻译开启后变重。
  那里用过的 host stage-2 粒度直方图（N80 上 99.5% 是 1 GiB 块）在本次调查中被引用。
- 本目录补上的是：页表遍历次数的实测、8 MB 顺序访问点双峰的物理成因，以及对已有推测的逐条核查。
