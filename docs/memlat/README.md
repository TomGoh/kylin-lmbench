# 内存访问延迟根因调查

本目录存放 2026-09-30 针对"pKVM 宿主机内存访问延迟"的调查材料。起因是论文审稿意见：

> 图7和图8中，LLC 边界延迟上升了 3.55%，64MB 随机访问延迟上升了 3.25%。文章仅描述了现象，缺乏根本原因解释。

## 数据是在哪里跑的

读任何一份材料之前先看这张表。四类数据不能混用。

| 类别 | 在哪里跑 | 数据目录 | 对应论文 |
| --- | --- | --- | --- |
| 宿主机实验 | 直接在 N90 的宿主 Linux 上跑 lmbench，只切换 `kvm-arm.mode`，不启动虚拟机 | `results/n90-day3-host/`、`results/standalone-mem-bench/` | 5.2 节，图 7 |
| 虚拟机内实验 | 在 N90 上用 crosvm 启动 x-kernel 客户机，lmbench 跑在客户机里面 | `results/xkernel-n90-*` | 5.3 节，图 8–10 |
| 本次补充测量 | 2026-09-30 在 N80 的宿主 Linux 上，protected 方式启动。测量程序跑在宿主机上；后台有一个开机自启动的空闲保护虚拟机 | `results/memlat-n80-20260930/` | 解释图 7 的机制，检验平台状态和页布局两个假设 |
| 本次对照测量 | 2026-09-30 在一台同型号核的工作站（长城 D80F3）的宿主 Linux 上，不用 root。它的宿主机没有二级翻译 | `results/memlat-d80f3-20260930/` | 给 N80 的测量提供"没有二级翻译"的参照 |

审稿人引用的 3.55% 和 3.25% 都是宿主机实验的数字。

## 文件

| 文件 | 内容 |
| --- | --- |
| [memlat-rootcause.zh-CN.md](memlat-rootcause.zh-CN.md) | 结论：两个数字各自的成因、图 8 负开销的来由、证据等级和还没解决的问题 |
| [memlat-investigation-worklog.zh-CN.md](memlat-investigation-worklog.zh-CN.md) | 按时间顺序的过程记录，包括被推翻的假设 |
| [agents/](agents/README.md) | 多代理调查和核查的原始报告；[agents/verification-summary.md](agents/verification-summary.md) 是逐条核查结果 |
| [../../experiments/memlat-probe/](../../experiments/memlat-probe/README.zh-CN.md) | 测量工具、运行脚本、分析脚本 |
| [../../results/memlat-n80-20260930/](../../results/memlat-n80-20260930/README.md) | N80 上的原始日志、硬件信息、汇总表 |
| [../../results/memlat-d80f3-20260930/](../../results/memlat-d80f3-20260930/README.md) | 工作站上的原始日志和机器说明 |
| [../n90-kvm-host/llc-boundary-8mb-analysis.md](../n90-kvm-host/llc-boundary-8mb-analysis.md) | 更早的一份只凭数据做的分析；本次调查用代码和机器对它做了检验 |

## 与仓库里已有材料的关系

- `docs/n90-kvm-host/` 是 2026-06 的四模式宿主机实验报告，给出了"随机访问慢 3%–7%"的现象和架构层面的推测，
  当时没有硬件计数器数据。
- `docs/mmap/` 是 mmap 和 munmap 方向的调查，结论是小范围 munmap 逐页发 TLBI 的代价在二级翻译开启后变重。
  那里用过的 host stage-2 粒度直方图在本次调查中被引用；要注意它是 6 月在 N80 另一棵内核树上读到的，
  "99.5% 是 1 GiB 块"说的是整个 1 TiB 的 IPA 空间，不是内存。
- 本目录补上的是：页表遍历次数的实测；同一次开机里宿主机二级映射粒度不同造成的延迟差别；
  有、没有宿主机二级翻译时一次页表遍历各花多少个周期（N80 对一台同型号核的工作站）；
  用 lmbench 自己的程序做出来的"只换缓冲区物理页的排列顺序，8 MB 顺序访问就差 19%"，以及 lmbench 的子进程实际拿到什么样的页；
  图 8 负开销背后那个与启动方式无关的平台状态，以及它最主要的候选成因——片上互连按流量调频（在 N80 上复现）；
  以及对已有推测的逐条核查（其中几条被推翻，见结论文档第 7 节）。
- 2026-10-02 由用户执行了互连调频实验（实验 G5）：在驱动默认的按流量调频下，N80 复现了 N90 上 8 MB 的两个水平和"快""慢"两种状态（结论文档 1.4、4.3、5.3 节）。
- 还没有做成的：同一台机器上换启动方式的对照（要重启）；在 N90 上确认当时的互连调频策略、固定之后重测（要有那台机器）；
  在 N90 上直接记录 lmbench 缓冲区的物理页布局（不改设置）。
  脚本都已写好，见 `experiments/memlat-probe/README.zh-CN.md` 和结论文档第 9 节。
