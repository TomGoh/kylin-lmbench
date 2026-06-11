# pKVM mmap 路径性能优化启动方案

**日期**：2026-06-10
**适用范围**：N90 / Kaitian 上 pKVM 宿主机侧 mmap 建立、首次触摸和拆除路径
**相关结果**：
- [lat-mmap-test-walkthrough.zh-CN.md](lat-mmap-test-walkthrough.zh-CN.md)
- [pkvm-mmap-overhead-analysis.md](pkvm-mmap-overhead-analysis.md)
- [lmdb-kaitian-nvhe-pkvm-results.zh-CN.md](lmdb-kaitian-nvhe-pkvm-results.zh-CN.md)

## 1. 当前已知现象

已有数据给出了一个比较一致的方向：

| 测试 | 现象 | 初步含义 |
|---|---|---|
| lmbench `lat_mmap` | pKVM 明显慢，64 MB 精测约 +42% | pKVM 对 `mmap + first-touch + munmap` 路径敏感 |
| LMDB `openclose` | Kaitian 上 pKVM 比 NVHE 慢约 +35% | 应用级环境打开/关闭路径也受影响 |
| LMDB `read` | pKVM 比 NVHE 慢约 +1.4% | 长期 mmap 后的随机读基本持平 |
| LMDB `write` | pKVM 与 NVHE 基本持平 | 当前追加写事务没有明显 pKVM 开销 |
| lmbench `lat_mem_rd` / `bw_mem` | 主机侧基本持平或仅小幅差异 | 稳定映射上的普通访问不是主要问题 |

这说明问题更可能集中在：

```text
建立映射
首次访问触发缺页和页表建立
拆除映射和 TLB invalidation
```

而不是已经建立好映射之后的普通 load/store。

## 2. 优化前的核心原则

优化不能从“猜测某个函数慢”开始。pKVM 的 mmap 开销涉及 Linux mm、host stage-2、EL2 fault 处理、TLBI、页表内存分配和安全隔离边界。直接改代码风险较高。

建议遵循以下原则：

1. 先把现象拆细，再做优化。
2. 先加计数器和 trace，确认是否真的进入 EL2，以及进入多少次。
3. 每个优化候选都必须同时给出性能收益和隔离安全性解释。
4. 优化验证不能只看 `lat_mmap`，还要看 LMDB openclose/read/write 和完整 lmbench 回归。

本阶段的首要目标不是立刻把性能降下来，而是回答：

```text
pKVM 多出来的 35% 到 42% 时间，到底花在 mmap、first-touch、munmap 的哪一段？
它对应 pKVM hyp 里的哪类事件：host memory abort、stage-2 map、unmap、TLBI，还是锁/分配开销？
```

## 3. 第一步：拆分 `lat_mmap`

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

如果 `mmap-only` 已经明显慢，说明 pKVM 成本不只来自 first-touch page fault，还可能来自环境打开、VMA 建立、stage-2 权限检查或 teardown。

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

如果 `touch-cold` 慢而 `touch-hot` 不慢，基本可以确认额外开销集中在首次访问和建表路径。

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

如果 `munmap-only` 慢，后续优化重点应转向 unmap、TLBI、batch invalidation 或延迟回收路径。

### 3.4 与 LMDB 的对应关系

拆分后的 microbenchmark 可以映射到 LMDB 子测试：

| 拆分项 | 对应 LMDB 行为 |
|---|---|
| `mmap-only` | `mdb_env_open` 中的环境映射建立 |
| `touch-cold` | 初次访问数据库页、扩大工作集、page cache 页面首次映射 |
| `touch-hot` | 长期打开环境后的常规读事务 |
| `munmap-only` | `mdb_env_close` 时释放环境 |

当前 LMDB 数据显示 `openclose` 明显慢，而 read/write 基本持平，因此优先怀疑 `mmap-only` 或 `munmap-only`，其次是 open 后首次访问页面。

## 4. 第二步：增加 pKVM hyp 侧计数器

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

### 4.4 需要回答的问题

计数器要能回答：

```text
lat_mmap 64 MB 每轮触摸约 410 个点，host_mem_abort 是否也接近这个量级？
mmap-only 是否触发 host stage-2 map/unmap？
munmap-only 是否触发大量 unmap 或 TLBI？
LMDB openclose 的慢是否伴随 host_stage2_tlbi_count 增加？
```

这些答案决定优化方向。

## 5. 第三步：Linux 侧辅助观测

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

如果 Linux 侧事件数量相同，但 pKVM 总耗时更高，说明额外成本更可能在 EL2 或 stage-2 维护路径。

## 6. 候选优化方向

具体优化必须等拆分测试和计数器结果出来后再定。下面列出可能方向。

### 6.1 批量建立 host stage-2 映射

如果确认慢在 first-touch，并且每次触摸新页面都会触发 host stage-2 fault，可以考虑：

```text
一次 fault 后向前/向后扩展映射连续物理区间
对连续 range 做 batch map
优先使用 PMD/block mapping
减少逐 4 KB 页的 stage-2 page-table walk 和插入
```

目标是把：

```text
每页一次 fault/map
```

变成：

```text
每个连续区间或每个 2 MB block 一次 map
```

安全注意：

```text
不能把未来需要隔离给 protected guest 的页面永久暴露给 host。
必须保证 donation/reclaim/protect 路径能正确拆分、降权或撤销 block mapping。
```

### 6.2 优化 stage-2 页表 walk 和分配

如果时间集中在 `host_stage2_idmap_locked` 或页表插入路径，可以检查：

```text
是否每次 fault 都重复完整多级 walk
是否频繁分配和清零 hyp page-table page
是否锁粒度过粗
是否 Rust 封装路径有额外边界检查或重复验证
```

候选优化：

```text
预分配 hyp page-table page pool
缓存最近 page-table walk 结果
对连续 range 做一次性 walk 后批量插入
缩小全局锁范围
减少重复权限计算
```

### 6.3 优化 unmap 和 TLBI

如果 `munmap-only` 或 counter 显示慢在 teardown，可以考虑：

```text
range TLBI
batch TLBI
合并连续 unmap
延迟回收部分 stage-2 表项
减少全局同步范围
```

这个方向风险较高。必须严格验证 ARM break-before-make、TLBI ordering 和 stale translation 问题。任何延迟回收或延迟 invalidation 都不能破坏 pKVM 的隔离语义。

### 6.4 区分 host 普通内存和 guest 可保护内存

如果发现 host stage-2 prepopulate 没有覆盖某些 host page cache 新页，或者权限 fault 频繁出现，需要检查：

```text
prepopulate_host_stage2 是否覆盖所有 normal RAM
file page cache 新分配页是否落入未映射或权限不一致的区域
block mapping 是否被过早拆分
host 页从普通状态到 guest protected 状态的转换是否过于保守
```

一种可能优化方向是：

```text
host 普通内存默认大粒度映射
只有页面进入 protected guest 所有权转换时，才拆分、降权或撤销 host stage-2 映射
```

但这必须以 pKVM 的 ownership model 为边界，不能为了性能弱化 protected guest 隔离。

## 7. 验证矩阵

每个优化 patch 至少需要跑以下测试：

| 测试 | 目的 |
|---|---|
| `lat_mmap_split` | 判断具体路径是否改善 |
| 原版 `lat_mmap` / `lat_mmap_precise` | 保持与现有结果可比 |
| LMDB `openclose` | 验证应用级 mmap open/close 是否改善 |
| LMDB `read` | 确认长期映射读路径不回退 |
| LMDB `write` | 确认写事务不回退 |
| `lat_mem_rd` / `bw_mem` | 确认稳定内存访问不回退 |
| `lat_pagefault` | 观察 minor fault 路径是否受影响 |
| protected guest 隔离测试 | 确认 host 不能访问 protected guest memory |

建议先用 Kaitian 快速验证，再用 N90 受控环境跑完整复现。

## 8. 成功标准

性能目标可以先定为：

```text
lat_mmap 64 MB:
  pKVM vs NVHE/VHE 从 +40% 级别降到 +10% 以内

LMDB openclose:
  pKVM vs NVHE 从 +35% 降到 +10% 以内

LMDB read/write:
  保持在 ±2% 内，不引入明显回退
```

安全目标：

```text
protected guest 内存仍不能被 host 直接访问
host-to-guest donation 和 reclaim 路径正确
stage-2 block mapping 的拆分、降权、撤销符合 ownership model
TLBI ordering 和 break-before-make 规则正确
并发 mmap/munmap/page fault 下无 stale mapping、use-after-free 或权限泄漏
```

如果某个优化只能改善 `lat_mmap`，但破坏 LMDB read/write 或 protected guest 安全性，则不能接受。

## 9. 推荐执行顺序

建议按下面顺序推进：

1. 实现 `lat_mmap_split`，至少包含 `mmap-only`、`touch-cold`、`touch-hot`、`munmap-only`。
2. 在 Kaitian 和 N90 上跑 NVHE/pKVM 对照，确认慢在哪一段。
3. 在 pKVM hyp 中增加最小计数器，确认 host mem abort、stage-2 map/unmap/TLBI 数量。
4. 根据拆分结果选择一个最小优化点。
5. 先在 Kaitian 上做 smoke，再在 N90 受控环境做完整验证。
6. 用 `lat_mmap_precise + LMDB openclose/read/write + 完整 lmbench` 做回归。
7. 补充 protected guest 安全回归。

## 10. 当前最可能的起点

结合已有数据，最值得优先验证的是：

```text
LMDB openclose 慢，而 read/write 基本持平；
lat_mmap 慢，而 lat_mem_rd/bw_mem 基本持平。
```

这使得首个排查重点应放在：

```text
mmap 建立路径
munmap teardown 路径
first-touch cold fault 路径
host stage-2 map/unmap/TLBI 计数
```

如果 `lat_mmap_split` 证明 `mmap-only` 或 `munmap-only` 已经占主要差异，优化应优先看 VMA 对应的 host stage-2 维护和 TLBI。  
如果只有 `touch-cold` 慢，则优先看 host memory abort 和 stage-2 批量建表。  
如果 `touch-hot` 也慢，则需要转向 TLB miss、stage-2 walk 和大工作集访问路径，但这与当前 LMDB read/write 基本持平的结果不完全一致。
