# 仅用 perf 复查 pKVM mmap 问题

这是一套**无需内核补丁、仅依赖 perf** 的 pKVM `lat_mmap` 复查流程，可在任意已安装的
pKVM 板卡上执行。它用标准 `perf`（`:h` EL2 修饰符、TLB walk/stall 计数器）替代原始调查
中的两个自定义 hypercall。首个复查目标是 **Kaitian**（Phytium FTC862）。

## 目录

1. **[perf-only-mmap-investigation-playbook.zh-CN.md](perf-only-mmap-investigation-playbook.zh-CN.md)**
   设计与执行手册：目标、环境控制、Stage 0-6 的 perf 事件映射、决策树、降级路径和当前状态。**建议先读这篇。**

2. **[build-perf-on-kaitian.zh-CN.md](build-perf-on-kaitian.zh-CN.md)**
   在 Kaitian 上从 `common/tools/perf` 编译**与当前内核匹配、功能完整**的 `perf` 的可复现手册。
   文档记录了本次遇到的五个陷阱：旧版 `btf.h`、GNU Make 4.2.1 的 `#` 解析问题、
   缺失打包的 `libtraceevent`、安装路径问题，以及陈旧的 `FEATURE-DUMP` 缓存，并给出精确的软件包版本。

3. **[build-perf-on-kaitian.sh](build-perf-on-kaitian.sh)**
   将编译手册固化成幂等脚本。脚本会探测每个陷阱，因此在没有触发这些问题的板卡上也可直接使用。

4. **[../../../experiments/perf-reinvestigation/stage0/README.zh-CN.md](../../../experiments/perf-reinvestigation/stage0/README.zh-CN.md)**
   Stage 0 能力与平台探测结果：确认 FTC862 没有 FEAT_TLBIRANGE，验证 `cycles:h` 在 pKVM 下可用，
   并记录 FTC862 可用的 PMU 事件。

5. **[../../../experiments/perf-reinvestigation/results/README.zh-CN.md](../../../experiments/perf-reinvestigation/results/README.zh-CN.md)**
   Kaitian 上 protected 与 nvhe 的完整复查结果：2 MB 断崖、EL2 归因、cost layering、
   core-scaling 和 `mmap_split` 阶段拆解。

## 为什么需要这套流程

原始深入调查（[../pkvm-mmap-overview.zh-CN.md](../pkvm-mmap-overview.zh-CN.md)）在五个阶段中有两个阶段依赖修改过的
hypervisor。已安装的 stock pKVM 板卡无法随意打补丁，因此本手册的目标是：只用 `perf` 复现或证伪同一个根因。

这一点使它从一次性的调试记录变成可复用的方法：只要目标板卡可以运行匹配内核版本的 `perf`，就可以按同样的
Stage 0-6 流程验证 `lat_mmap` 退化是否存在、成本发生在哪一层，以及机制是否仍然是逐页 TLBI 的 stage-2 硬件税。

## 状态（2026-06-24）

- `perf` 已在 Kaitian 上完成编译和功能验证。
- Stage 0 已完成：FEAT_TLBIRANGE 缺失，`:h` EL2 计数可用。
- Stage 1-6 已执行：Kaitian 上用仅 perf 的方法复现了原始根因。
- 数据集和脚本已提交到 `experiments/perf-reinvestigation/`。
