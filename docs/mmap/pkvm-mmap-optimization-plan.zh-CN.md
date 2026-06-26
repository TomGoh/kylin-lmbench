# pKVM mmap/teardown 路径优化：阶段性结论与后续工作

**初版**：2026-06-10
**更新**：2026-06-16
**适用范围**：N80 / N90 / Kaitian 上 pKVM 宿主机侧 mmap 生命周期与 teardown 路径
**相关结果**：
- [lat-mmap-test-walkthrough.zh-CN.md](lat-mmap-test-walkthrough.zh-CN.md)
- [pkvm-mmap-overhead-analysis.md](pkvm-mmap-overhead-analysis.md)
- [lmdb-kaitian-nvhe-pkvm-results.zh-CN.md](lmdb-kaitian-nvhe-pkvm-results.zh-CN.md)
- [pkvm-mmap-overview.zh-CN.md](pkvm-mmap-overview.zh-CN.md)
- [pkvm-teardown-op-generality.en.md](pkvm-teardown-op-generality.en.md)

## 1. 阶段性调查结论

当前结论已经从“mmap 生命周期哪里慢”收敛到“哪类 TLB teardown 会慢”。核心判断如下：

| 测试 | 现象 | 初步含义 |
|---|---|---|
| lmbench `lat_mmap` | pKVM 明显慢，64 MB 精测约 +42% | 问题存在于 `mmap + touch + munmap` 生命周期，而非稳态访存 |
| `mmap_split` | 额外时间主要落在写触摸后的 `munmap` | first-touch 建表不是主因 |
| EL2 gate / hyp counter | `munmap` 窗口内 ΔEL2 = 0 | 额外时间不是 hypervisor 执行时间 |
| perf / C0 | 指令、缺页、walk 数量基本不变，后端停顿增加 | 候选机制收敛到 TLB 失效成本 |
| host stage-2 粒度自省 | 宿主机内存 99.5% 为 1G block | “stage-2 碎片化 / walk 变深”不是主因 |
| TLBI 阈值扫描 | `<2 MB` 逐页路径有 gap，`2 MB` 处塌缩 | 退化由逐页 TLBI slot 数决定 |
| 核数复查 / TLBI 直接计时 | protected 约 289 ns/slot，nvhe 约 23 ns/slot | `+0.27 us/slot` 是本地合成 TLB 条目失效成本，不是跨核广播 |
| teardown 通用性测试 | `munmap`、`MADV_DONTNEED`、`mprotect` 在 `<2 MB` 下 gap 重合 | 代价不是 syscall 私有，而是逐页 flush 路径的通用属性 |

阶段性根因：

> pKVM protected 模式为宿主机启用 host stage-2 后，宿主机 EL1/EL0 的 TLB 条目变成带 VMID 标记的 stage-1 x stage-2 合成条目。在当前 N80 / N90 / Kaitian 这类不支持 FEAT_TLBIRANGE 的平台上，arm64 对 `<2 MB` flush range 会逐 4K slot 发 TLBI；每个 slot 在 protected 下比 nvhe 多约 `+0.27 us`。因此，所有落入这条逐页 flush 路径的 teardown 操作都会付费。

当前受影响边界：

- `munmap`：写触摸后 zap 脏页，且常按 PMD 分批 flush；稀疏写触摸即使总跨度大，也可能每批都低于 2 MB，从而吃满逐页 TLBI 罚时。
- `madvise(MADV_DONTNEED)`：与 `munmap` 行为基本一致，是第二个明确受影响对象；allocator decommit 路径需要纳入后续验证。
- `mprotect`：连续改动区间 `<2 MB` 时同样受影响；稀疏大跨度不 zap 脏页，通常可累计成一次超过 2 MB 的 flush，因此额外 gap 接近 0。
- 长期复用映射、稳态读写、`lat_mem_rd` / `bw_mem` 这类路径不是主影响面。

当前不再作为主线的假设：

| 旧假设 | 当前状态 | 原因 |
|---|---|---|
| first-touch 触发 host stage-2 建表导致慢 | 已证伪 | 拆分测试显示 first-touch 不是主要额外时间来源 |
| host stage-2 页表 walk / 分配导致慢 | 已证伪为主因 | 粒度自省与密集触摸对照均不支持 |
| `+0.27 us/slot` 来自跨核广播等待 | 已更正 | TLBI 直接计时、均值统计、perf 进程计数均显示与在线核数无关 |
| 优化 host stage-2 映射粒度可解决问题 | 非主线 | 宿主机 host stage-2 已以大块映射为主，瓶颈在 TLBI 条目类别 |

## 2. 后续工作的核心原则

后续不再按“哪里可能慢”发散排查，而应围绕“减少逐页 TLBI 次数，或避免落入逐页路径”推进。原则如下：

1. 优先验证能直接减少 TLBI slot 数的方案，而不是继续优化 stage-2 walk、page-table allocation 或 EL2 map/unmap。
2. 所有结果使用 mean / median 与 perf 进程计数交叉验证，不再用 `min` 作为主要判据。
3. 每个优化候选必须同时解释收益来源、适用边界和安全影响。
4. 验证不能只看 `lat_mmap`，还要覆盖 `MADV_DONTNEED`、allocator decommit、LMDB openclose/read/write 与完整 lmbench 回归。
5. pKVM 隔离语义和 ARM TLBI ordering 是硬边界；任何延迟 invalidation、扩大可见范围或改变 ownership model 的方案都必须先证明安全性。

本阶段的核心问题已经变为：

```text
能否通过硬件 range TLBI、内核阈值调整或运行时规避，
减少 `<2 MB` teardown 中的逐页 TLBI 次数，
并且不把成本转移成更大的 TLB refill 或安全风险？
```

## 3. 已完成步骤一：拆分 `lat_mmap`

状态：该步骤已经完成，并证明主要额外时间位于写触摸后的 `munmap` teardown。以下保留测试设计，作为后续回归和复测的基线。

原版 `lat_mmap` 每轮执行：

```text
mmap
按 16 KB 步长写触摸前 size/10 区域
munmap
```

这个结果只能说明整条路径慢，不能说明慢在具体哪一段。建议新增一个 `lat_mmap_split` 或等价脚本，将测试拆成三类。

当前仓库已经新增独立测试项目：

```text
experiments/mmap-split/
```

配套脚本：

```text
scripts/mmap-split-bench.sh
scripts/analyze-mmap-split.py
```

它不依赖 lmbench harness，而是直接用 `clock_gettime(CLOCK_MONOTONIC)` 对每个拆分阶段计时。这样做的好处是每个 mode 的计时边界明确，便于和 pKVM hyp counter 对齐。

### 3.1 mmap-only

测试内容：

```text
for each iteration:
    mmap(file, size)
    munmap(size)
```

不做 touch。

作用：

```text
判断仅创建/拆除 VMA 和 file mapping 是否已经出现 pKVM 额外开销。
```

早期判据：如果 `mmap-only` 已经明显慢，说明 pKVM 成本不只来自 first-touch page fault，还可能来自环境打开、VMA 建立、stage-2 权限检查或 teardown。当前结果未把 `mmap-only` 作为主线。

### 3.2 touch-only

测试内容：

```text
mmap 一次
在计时区内触摸页面
可区分首次触摸和重复触摸
最后 munmap
```

建议分两种：

```text
touch-cold：每次触摸尚未建立页表项的新页面
touch-hot：重复触摸已经建立好映射的页面
```

作用：

```text
区分 first-touch 缺页建表成本和稳定映射后的普通访问成本。
```

早期判据：如果 `touch-cold` 慢而 `touch-hot` 不慢，基本可以确认额外开销集中在首次访问和建表路径。当前拆分结果已排除 first-touch 建表为主因。

### 3.3 munmap-only

测试内容：

```text
预先 mmap + touch 完成
计时区只测 munmap
```

作用：

```text
判断拆映射、页表回收和 TLB invalidation 是否是主因。
```

当前结果：`munmap-only` 在写触摸后明显变慢，这一判据已经触发。后续优化应转向 TLBI 数量、batch/range TLBI 和阈值策略；延迟回收与当前根因不匹配，暂不作为主线。

### 3.4 与 LMDB 的对应关系

拆分后的 microbenchmark 可以映射到 LMDB 子测试：

| 拆分项 | 对应 LMDB 行为 |
|---|---|
| `mmap-only` | `mdb_env_open` 中的环境映射建立 |
| `touch-cold` | 初次访问数据库页、扩大工作集、page cache 页面首次映射 |
| `touch-hot` | 长期打开环境后的常规读事务 |
| `munmap-only` | `mdb_env_close` 时释放环境 |

当前 LMDB 数据显示 `openclose` 明显慢，而 read/write 基本持平。结合后续定位，LMDB 后续应作为 mmap close/decommit 形态的应用级回归重点；长期打开后的 read/write 主要用于确认稳态访问没有回退。

## 4. 已完成步骤二：EL2 gate 与 pKVM hyp 侧计数器

状态：后续 gate 实验证明 `munmap` 计时窗口内 ΔEL2 = 0，主退化不发生在 hyp 执行时间内。以下插桩设计仍可作为复查或新平台验证模板。

Linux 侧 perf 可以看到 syscall、minor fault、TLB miss 等 host 事件，但不一定能完整解释 EL2 hyp 内部开销。因此需要在 pKVM hyp 侧增加轻量计数器。

### 4.1 建议计数项

建议先加最小集合：

```text
host_mem_abort_count
host_stage2_map_count
host_stage2_unmap_count
host_stage2_tlbi_count
host_stage2_map_ns_total
host_stage2_unmap_ns_total
host_stage2_tlbi_ns_total
host_stage2_alloc_count
host_stage2_alloc_ns_total
```

如果计时成本太高，可以先只加 count，不加 ns；确认事件数量后再对重点路径加时间统计。

### 4.2 建议插桩位置

重点关注：

```text
handle_host_mem_abort
host_stage2_idmap_locked
host stage-2 page-table insert/map path
host stage-2 unmap/protect path
stage-2 TLBI path
hyp page-table page allocation path
host memory permission fault path
```

如果代码分为 Rust pKVM 实现和 C glue，需要在二者边界处明确计数归属，避免重复计数。

### 4.3 导出方式

可选方案：

1. debugfs/sysfs 节点导出。
2. hyp trace buffer 周期性导出。
3. 临时 printk 输出。
4. per-cpu counter，通过 host 调用读取。

建议优先选择低扰动方式。不要在每次 fault 里 printk，否则会严重改变性能结果。

### 4.4 当时需要回答的问题与当前答案

计数器要能回答：

```text
lat_mmap 64 MB 每轮触摸约 410 个点，host_mem_abort 是否也接近这个量级？
mmap-only 是否触发 host stage-2 map/unmap？
munmap-only 是否触发大量 unmap 或 TLBI？
LMDB openclose 的慢是否伴随 host_stage2_tlbi_count 增加？
```

当前答案：

```text
lat_mmap 的主要额外时间不来自 host_mem_abort
mmap-only 不是主退化段
munmap-only 的额外时间不来自 EL2 host_stage2_unmap/TLBI，而来自 host EL1 直接执行的 TLBI
LMDB openclose 仍是应用级回归重点，但后续应重点看 mmap close/decommit 形态，而不是 hyp counter 增量
```

这些答案已经将优化方向收敛到 host 侧 TLBI 硬件成本，而不是 EL2 map/unmap 或 host stage-2 建表。

## 5. 已完成步骤三：Linux 侧辅助观测

在 host Linux 侧同步收集：

```bash
perf stat -e cycles,instructions,page-faults,minor-faults,dTLB-load-misses,dTLB-store-misses \
  ./lat_mmap_split ...
```

也可以使用 ftrace/tracefs 观察：

```text
sys_enter_mmap / sys_exit_mmap
sys_enter_munmap / sys_exit_munmap
handle_mm_fault
filemap fault
mm page fault tracepoints
TLB flush tracepoints
```

Linux 侧数据主要用于辅助判断：

```text
是否 minor fault 数量一致？
是否 pKVM 的 CPU cycles 增加但 Linux 侧 fault 数量不变？
是否 munmap 引起更多 TLB flush？
```

如果 Linux 侧事件数量相同，但 pKVM 总耗时更高，需要先区分两类可能：一类是 EL2 或 stage-2 维护路径，另一类是 host 侧 TLBI 在 stage-2 开启后的硬件执行成本。当前数据已经指向后一类。

## 6. 当前可行的优化方向

当前优化目标不是降低所有 mmap 成本，而是降低或绕开 `<2 MB` teardown 的逐页 TLBI 成本。

### 6.1 首选方向：硬件支持 FEAT_TLBIRANGE

这是最干净的解决路径。支持 FEAT_TLBIRANGE 的平台可以让 `__flush_tlb_range_op` 使用 range TLBI，把 N 个 4K slot 压缩为少数几条范围失效指令，直接消除 `N * 0.27 us` 这个乘数。

适用场景：

```text
新平台选型
同一 SoC 不同 revision 的能力确认
对比验证当前结论是否随 range TLBI 消失
```

验证方式：

```text
读取 ID_AA64ISAR0_EL1.TLB 字段
确认内核 system_supports_tlb_range() 走 range 分支
复跑 op_sweep / munmap_only / lat_mmap_split
重点观察 <2 MB 下 protected - nvhe gap 是否明显缩小
```

当前 N80 / N90 / Kaitian 均不支持该特性，因此这条更适合作为平台结论和后续硬件验证项。

### 6.2 当前唯一明确的软件杠杆：评估 `MAX_DVM_OPS`

arm64 当前以 `MAX_DVM_OPS = 512` 作为逐页 TLBI 与整 ASID flush 的分界，4K 页下阈值为 2 MB。降低该阈值可以让更多 teardown 提前进入整 ASID flush，减少昂贵的逐页合成条目失效。

预期收益：

```text
munmap / MADV_DONTNEED 的中小范围 teardown 可能显著变快
lat_mmap 稀疏写触摸场景的 protected - nvhe gap 下降
allocator decommit 中的 MADV_DONTNEED 罚时下降
```

主要代价：

```text
整 ASID flush 会失效该地址空间内更多 TLB 条目
后续访问可能产生更多 TLB refill
大工作集、长期复用映射、频繁上下文切换负载可能回退
```

建议实验矩阵：

| 阈值方案 | 目的 |
|---|---|
| baseline 512 | 当前 2 MB 行为 |
| 256 | 观察 1 MB 以上是否提前塌缩 |
| 128 | 观察 512 KB 以上是否收益明显 |
| 64 | 探索更激进阈值的 refill 代价 |

每个阈值至少跑 `op_sweep`、`munmap_only`、`lat_mmap_split`、原版 `lat_mmap`、LMDB openclose/read/write、`lat_mem_rd`、`bw_mem`。判断时不能只看 teardown 变快，还要看整轮 workload 是否因 refill 增多而抵消收益。

### 6.3 应用和运行时规避

对现有硬件，如果不改内核，实际可控点在于减少 dirty teardown 的频率，或改变每次 flush 的几何形态。

可评估方向：

```text
复用 mmap，避免频繁 mmap/munmap 同一类对象
把小块 decommit 合并为更少次数的批量操作
在语义允许时评估 MADV_FREE，而不是立即 zap 的 MADV_DONTNEED
调整 allocator decay / decommit 策略，降低 MADV_DONTNEED 频率
对 JIT / guard page 等 mprotect 场景，尽量避免高频 <2 MB 连续权限切换
```

注意边界：

```text
合并范围不必然绕开罚时，munmap / MADV_DONTNEED 对脏页可能按 PMD force_flush
如果每个 PMD 内实际 flush range 仍低于 2 MB，仍会走逐页路径
规避策略必须用 op_sweep 或真实 workload 验证，不能只按总跨度判断
```

### 6.4 暂不作为主线的方向

以下方向可以保留为历史假设或新平台异常时的复查项，但不应作为当前优化入口：

| 方向 | 当前判断 |
|---|---|
| 批量建立 host stage-2 映射 | first-touch 不是主因，且 host stage-2 映射一经建立长期有效 |
| 优化 host stage-2 walk / 分配 | 粒度自省和密集对照不支持，收益预期低 |
| 提高 host stage-2 映射粒度 | 当前已主要为 1G block，瓶颈不在页表层数 |
| 延迟 stage-2 表项回收 | 与当前根因不匹配，且安全风险高 |
| 减少跨核广播范围 | 核数复查已证明主要开销不是广播等待 |

## 7. 验证矩阵

后续每个优化 patch 或规避方案至少需要覆盖以下测试：

| 测试 | 目的 |
|---|---|
| `op_sweep` | 同时观察 `munmap` / `MADV_DONTNEED` / `mprotect` 的逐页 gap |
| `munmap_only` threshold sweep | 验证 2 MB gate 或新阈值是否按预期移动 |
| `mmap_split` | 确认收益确实落在 teardown，不误伤 touch-hot |
| 原版 `lat_mmap` / `lat_mmap_precise` | 保持与历史结果可比 |
| allocator decommit 微基准 | 覆盖 jemalloc / tcmalloc / Go runtime 等 `MADV_DONTNEED` 影响面 |
| LMDB `openclose` | 验证应用级 mmap open/close 是否改善 |
| LMDB `read` / `write` | 确认长期映射读写路径不回退 |
| `lat_mem_rd` / `bw_mem` | 确认稳态内存访问不回退 |
| `lat_pagefault` | 观察 minor fault 路径是否受阈值调整影响 |
| perf 进程计数 | 观察 cycles、instructions、TLB refill、backend stall 是否符合模型 |
| protected guest 隔离测试 | 确认 host 不能访问 protected guest memory |

测试控制项：

```text
固定 CPU / 频率 / governor
THP=never，除非专门测试 THP 影响
ASLR=0
报告 mean / median / p95，min 仅作附属信息
protected 与 nvhe 使用同一内核配置和同一 workload
```

## 8. 成功标准

性能目标需要分成微基准和真实负载两层。

微基准目标：

```text
<2 MB teardown 的 protected - nvhe gap 明显低于当前 +0.27 us/slot 模型
MADV_DONTNEED 的 sparse 6.4 MB / 16K gap 明显下降
lat_mmap 64 MB 的 pKVM 额外时间明显下降
```

真实负载目标：

```text
LMDB openclose 改善，同时 read/write 不回退
allocator decommit 相关负载改善，同时常规分配/访问不回退
lat_mem_rd / bw_mem 保持在噪声范围内
```

安全目标：

```text
protected guest 内存仍不能被 host 直接访问
host-to-guest donation 和 reclaim 路径正确
stage-2 block mapping 的拆分、降权、撤销符合 ownership model
TLBI ordering 和 break-before-make 规则正确
并发 mmap/munmap/page fault 下无 stale mapping、use-after-free 或权限泄漏
```

如果某个方案只能改善 `lat_mmap`，但让 LMDB read/write、allocator 常规路径或 protected guest 隔离回退，则不能接受。

## 9. 推荐执行顺序

建议按下面顺序推进：

1. 固化当前 baseline：在 protected / nvhe 下保存 `op_sweep`、`munmap_only`、`mmap_split`、原版 `lat_mmap`、LMDB 与 perf 结果。
2. 确认目标平台硬件能力：读取 `ID_AA64ISAR0_EL1.TLB`，明确是否支持 FEAT_TLBIRANGE。
3. 若硬件不支持 FEAT_TLBIRANGE，进入 `MAX_DVM_OPS` 阈值实验，至少比较 512 / 256 / 128 / 64。
4. 对每个阈值先跑 microbenchmark，再跑 LMDB 和 allocator decommit，再跑稳态访存回归。
5. 同步评估应用和运行时规避策略，特别是 `MADV_DONTNEED` 频率、批量大小和 `MADV_FREE` 可行性。
6. 对候选方案补齐 protected guest 隔离、donation/reclaim、并发 mmap/munmap/page fault 回归。
7. 最后按收益和风险决定：提交内核阈值 patch、形成平台选型建议，或给出应用/运行时规避指南。

## 10. 当前阶段判断

当前最值得投入的不是继续追踪 host stage-2 建表或 EL2 unmap，而是围绕下面三个问题收敛：

```text
1. 新平台是否支持 FEAT_TLBIRANGE，能否从硬件上消掉逐页 TLBI 乘数？
2. 当前硬件上，降低 MAX_DVM_OPS 是否能以可接受的 refill 成本换来 teardown 收益？
3. 真实业务里有多少 MADV_DONTNEED / munmap dirty teardown，能否通过运行时策略减少触发频率？
```

阶段性结论已经足够支撑进入优化验证阶段：根因是 host stage-2 下本地合成 TLB 条目逐页失效变贵；下一阶段的工作重点是减少这类失效发生次数，并用真实负载确认收益没有被更大的 TLB refill 成本抵消。
