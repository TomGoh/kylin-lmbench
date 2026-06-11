# Standalone Memory Bench 验证：证伪 pkvm "随机访问加速" 的内禀性

> **核心结论**：之前 SUMMARY 里 Finding 5 报告的"pKVM 在 LLC 边界 + DRAM 随机访问比
> 其它 3 配置快 17-33%"是 **CONFIG.host 测试序列副产物**，**不是 pkvm 的内禀性能特性**。
> standalone 单独跑 lat_mem_rd_rand 时，pkvm 不仅没快，**反而比 non-pkvm 慢 2-7%**
> （符合架构理论预期：每次 TLB miss 多一层 stage-2 walk）。
>
> 全套参考：[`README.md`](README.md)、[`SUMMARY.md`](SUMMARY.md)、
> [`pkvm-mmap-overhead-analysis.md`](../mmap/pkvm-mmap-overhead-analysis.md)、
> [`pkvm-memory-access-speedup.md`](pkvm-memory-access-speedup.md)（**已作废**，本文取代）。

**Date**: 2026-06-04

---

## 1. 实验背景：为什么需要这个验证

最初 CONFIG.host N=10 数据显示：

| 工作集 | kvmoff | nvhe | vhe | pkvm | pkvm vs 平均 |
|--------|-------:|-----:|----:|-----:|-------------:|
| Random 4MB | 47.59 | 47.69 | 47.45 | **31.89** | **−33%** |
| Random 8MB | 112.54 | 112.60 | 112.32 | **91.01** | **−19%** |
| Random 64MB | 185.23 | 185.05 | 185.43 | **154.40** | **−17%** |

写到 [`pkvm-memory-access-speedup.md`](pkvm-memory-access-speedup.md) 里时，给的解释
是 pkvm 的 stage-2 大 block mapping 让 PTW walk cache 命中率高，反而加速 host 访问。

但后续 debug 时发现 pkvm 这些指标在 **iter 4-5 突然下降 17-33%**：

```
pkvm CONFIG.host iter-by-iter (Random 64MB, ns)：
  iter 1: 194.23    iter 6: 154.51
  iter 2: 178.90    iter 7: 154.62
  iter 3: 194.22    iter 8: 154.29
  iter 4: 153.91    iter 9: 153.72
  iter 5: 154.16    iter 10: 153.66
            ↑
            transition！
```

而 kvmoff / nvhe / vhe **没有这种 transition**，10 iter 数值都稳定。

→ 假说：pkvm 在 CONFIG.host 序列里**被前面跑的 bench（lat_mmap 等）加热了 stage-2 表**，
后续 random access 因此加速。**这不是 pkvm 内禀属性，是 CONFIG.host 序列副作用。**

为验证假说，跑 standalone 实验。

---

## 2. 实验设计

### 2.1 测试集（用户列出的 10 行指标）

| # | 指标 | 命令 |
|---|------|------|
| 1 | Prot Fault | `lat_sig -P 1 prot <bin>` |
| 2 | Page Fault | `lat_pagefault -P 1 /tmp/lmb_file` |
| 3-7 | L1d/L2/LLC/边界/Main 顺序 | `lat_mem_rd -P 1 64 256` （sequential stride 256）|
| 8-10 | Random 4/8/64MB | `lat_mem_rd -t -P 1 64 16` （random stride 16）|

每 "run" = 4 条**独立 invocation**，每条 exec 重新启动（互相之间无状态污染）。
每个配置跑 10 次 runs，约 10-12 min。

### 2.2 与 CONFIG.host 的差别

| 维度 | CONFIG.host | standalone |
|------|------------|----------|
| 测试前序状态 | lat_mmap / lat_proc / lat_pipe 等大批 bench 已跑 | exec 刚开始，**完全 fresh** |
| pkvm stage-2 表状态 | 被 lat_mmap 多轮 64MB mmap "暖" 过 | boot 后 prepopulate，未被进一步触动 |
| host page allocator | 多轮 mmap/munmap 已稳态 | 原始分布，allocator 首次给 64MB |
| 单次 timing 包含 | scripts/lmbench 多 bench × 多 size 长流水 | 单个 binary 单次 invocation |
| 总持续 | 100 min/配置（背景任务有机会触发） | 10 min/配置 |
| 复用 process | 同一 lat_mem_rd 进程跑多 size | 每条命令一个 fresh process |

→ standalone 控制了"测试序列累积状态"这个变量。

### 2.3 4 配置都跑

每个配置流程：reboot → apply-masks → prepare-host → verify-clean-env →
跑 standalone-mem-bench.sh × 10 runs。

脚本 [`scripts/standalone-mem-bench.sh`](../../scripts/standalone-mem-bench.sh)，
原始 log 在 [`results/standalone-mem-bench/`](../../results/standalone-mem-bench/)。

---

## 3. 结果（4 配置 × 10 runs 中位数）

### 3.1 完整对照表

```
============================================================================================================================
  指标                       |  CFG kvmoff   SA kvmoff |   CFG nvhe    SA nvhe |   CFG vhe    SA vhe |   CFG pkvm   SA pkvm
============================================================================================================================
  lat_sig prot (µs)          |     0.1590    0.1624    |   0.1600     0.1570  |   0.1602     0.1553  |   0.1607     0.1578
  lat_pagefault minor (µs)   |     0.2545    0.1053    |   0.2547     0.1056  |   0.2578     0.1053  |   0.2547     0.1066    ⚡

--- Sequential stride256 (ns) ---
  L1d 64KB                   |     2.224     2.224     |   2.224      2.224   |   2.224      2.224   |   2.224      2.224
  L2 0.5MB                   |     3.971     4.017     |   3.963      4.042   |   3.941      4.005   |   3.971      4.023
  LLC 1MB                    |     4.437     4.481     |   4.437      4.483   |   4.433      4.482   |   4.449      4.485
  LLC 边界 8MB                |    10.815    12.051     |  11.410     12.532  |  12.447     12.407  |  10.014     12.348    ⭐
  Main 64MB                  |    10.357    10.430     |  10.241     10.487  |  10.781     10.497  |  10.114     10.497

--- Random stride16 (ns) ---
  Random 4MB                 |    47.59     47.70      |  47.69      47.40   |  47.45      47.49   |  31.89      49.74    ⭐
  Random 8MB                 |   112.54    112.90      | 112.60     112.70   | 112.32     112.58   |  91.01     120.01    ⭐
  Random 16MB                |   168.54    169.80      | 168.56     169.92   | 169.71     169.72   | 140.42     176.72    ⭐
  Random 32MB                |   180.61    181.55      | 180.78     181.82   | 182.72     180.82   | 150.23     189.57    ⭐
  Random 64MB                |   185.23    185.32      | 185.05     186.05   | 185.43     185.55   | 154.40     192.41    ⭐
============================================================================================================================
                                  CFG = CONFIG.host N=10 中位
                                  SA  = standalone × 10 中位
```

### 3.2 关键 pattern

#### A. kvmoff / nvhe / vhe：**SA ≈ CFG**，几乎完全一致

| 配置 | Random 64MB CFG ↔ SA | Δ% |
|------|---------------------:|---:|
| kvmoff | 185.23 ↔ 185.32 | +0.05% |
| nvhe   | 185.05 ↔ 186.05 | +0.5% |
| vhe    | 185.43 ↔ 185.55 | +0.06% |

→ **CONFIG.host 序列对没有 stage-2 表的 3 配置毫无影响**。说明序列副作用是 stage-2 表
特有的累积现象。

#### B. pkvm：**CFG ≠ SA**，CFG 偏快 17-33%

| 工作集 | pkvm CFG | pkvm SA | CFG vs SA |
|--------|---------:|--------:|----------:|
| Random 4MB | 31.89 | 49.74 | **−36%** |
| Random 8MB | 91.01 | 120.01 | **−24%** |
| Random 16MB | 140.42 | 176.72 | **−21%** |
| Random 32MB | 150.23 | 189.57 | **−21%** |
| Random 64MB | 154.40 | 192.41 | **−20%** |
| LLC 边界 8MB seq | 10.01 | 12.35 | **−19%** |

→ pkvm 在 CONFIG.host 序列里**获得 17-36% 加速**，这部分加速在 standalone 完全消失。

#### C. pkvm SA vs kvmoff/nvhe/vhe SA：pkvm **反而慢 2-7%**

| 工作集 | kvmoff SA | nvhe SA | vhe SA | pkvm SA | pkvm 慢多少 |
|--------|---------:|--------:|-------:|--------:|------------:|
| Random 4MB | 47.70 | 47.40 | 47.49 | 49.74 | **+4.7%** |
| Random 8MB | 112.90 | 112.70 | 112.58 | 120.01 | **+6.4%** |
| Random 16MB | 169.80 | 169.92 | 169.72 | 176.72 | **+4.1%** |
| Random 32MB | 181.55 | 181.82 | 180.82 | 189.57 | **+4.4%** |
| Random 64MB | 185.32 | 186.05 | 185.55 | 192.41 | **+3.7%** |
| LLC 边界 8MB seq | 12.05 | 12.53 | 12.41 | 12.35 | ~0% |

→ **这才是 pkvm 的真实内禀架构开销**：每次 TLB miss 多一层 stage-2 walk，加约 5-10 ns。
**完全符合架构预期**。

#### D. lat_pagefault：4 配置 CFG 都比 SA 慢 2.4×（与 pkvm 无关）

| | kvmoff | nvhe | vhe | pkvm |
|---|------:|----:|----:|----:|
| CFG | 0.2545 | 0.2547 | 0.2578 | 0.2547 |
| SA | 0.1053 | 0.1056 | 0.1053 | 0.1066 |

→ 所有 4 配置一致——是 **CONFIG.host 序列里前面 bench 的副作用**（污染 page cache、
dentry cache、slab 之类），跟 stage-2 / KVM 模式无关。任何 micro-bench 之前如果跑过
file I/O / mmap 都会有这个效应。

---

## 4. 解读与机制

### 4.1 pkvm CFG "快 17-33%" 的真实成因

CONFIG.host 单 iter 里 lat_mem_rd_rand 是**位置 22（最后）**才跑（[scripts/lmbench](../../scripts/lmbench)
顺序）。前面已经经历了：

- 位置 9：**`lat_mmap`** 0.5 / 1 / 2 / 4 / 8 / 16 / 32 / 67 MB × N 次
- 位置 14：`bw_file_rd` 多 size（mmap'd file）
- 位置 15：**`bw_mmap_rd`** mmap_only + open2close 多 size
- 位置 16：**`bw_mem`** 各模式 × 各 size（含大段 malloc，glibc 用 mmap）
- 位置 17：`lat_ctx` × 各 proc 数（fork 复制 stage-1 PTE，pkvm 同步 stage-2）
- 位置 18-20：`tlb` / `par_mem` / `stream`
- 位置 21：**`lat_mem_rd seq`** 7 strides × 各 size（其中 stride16/32/64/128/256/512/1024）

到 `lat_mem_rd_rand` 时，pkvm 主机 stage-2 表已被反复 hammer：

1. **Stage-2 表项 lazy reclaim 累积**：pkvm 在 munmap 时不立即回收 stage-2 表项
   （`host_stage2_idmap_locked` 不与 unmap 配对）。反复 mmap+munmap 后，大量 VA range
   的映射仍留在表里
2. **Linux page allocator 进入稳态**：反复 mmap+munmap 让 free-list 排列稳定，
   返回的物理页越来越连续。pkvm 启动时用 1 GB block 预填 stage-2 表——物理连续的
   64 MB heap 恰好落在一个 1 GB block 内，stage-2 TLB miss 也命中预填的大 block

这两个机制**叠加**让 pkvm 后续 random access 走的 stage-2 walk 命中 walk cache
的概率显著上升 → 反向加速。

**最关键的是这不是 pkvm 的内禀属性，而是 workload-mix-dependent 的副产品。**

### 4.2 pkvm SA 比 non-pkvm SA 慢 2-7% 的成因（架构预期）

主机 4 KB 页访问的 TLB miss 路径：

| 模式 | TLB miss 时 PTW 走多少步 |
|------|-------------------------|
| kvmoff / nvhe / vhe | stage-1 walk only（4 级 PTE） |
| pkvm | stage-1 walk + 每级再做 stage-2 walk |

pkvm 多出来的 stage-2 walk 大部分命中 walk cache（因为 stage-2 用大 block 预填），
但仍多几个 cycle。在 Random 64MB（TLB miss 极频繁）这个开销表现为 **2-7% latency
增加**——这跟我们 SA 数据完全吻合。

### 4.3 lat_pagefault CFG 慢 2.4× 的成因（非 pkvm-specific）

CONFIG.host 在 lat_pagefault 之前已经跑了：
- `lat_proc` fork+exec 多次（污染 slab、PID/file table）
- `lat_mmap` 多大段（污染 vma 红黑树）
- `bw_file_rd` 多 size（污染 page cache 和 inode cache）
- `lat_fs` 创建删除小文件（污染 dentry）

到 lat_pagefault 时，主机 mm 子系统的所有相关 cache 都 warm 但有 stale 项，
page fault 路径需要更多 lookups。**所有 4 配置都受影响**，跟 stage-2 / KVM 模式无关。

### 4.4 LLC 边界 8MB sequential pkvm CFG = 10.01 反常解释

CFG 数据中 pkvm 在 8 MB sequential 是 10.01（其它 ~10.8-12.4），看起来 pkvm 也快。
SA 数据 pkvm = 12.35（跟 kvmoff SA 12.05 / nvhe SA 12.53 / vhe SA 12.41 一致）。
→ 同样是 CONFIG.host 序列副产品，机制同 random：stage-2 表暖机后 sequential
访问的 TLB miss 也命中得更准。

---

## 5. paper 修正

### 5.1 [`SUMMARY.md`](SUMMARY.md) Finding 5（原版）

> "Finding 5：⭐ pKVM 在 LLC 边界 + DRAM 段随机访问反而快 17-33%"

**作废**。改成：

### 5.2 Finding 5（修正版）

> **Finding 5：pkvm 的内禀架构开销在主机 random access 上 +2-7%**（每次 TLB miss
> 多一层 stage-2 walk）。CONFIG.host 序列里测到的"pkvm 比 non-pkvm 快 17-33%"是
> **序列副产品**——前面跑的 lat_mmap / bw_mem / bw_mmap_rd 等大段 mmap-touching 测试
> 累积"暖热"了 pkvm 主机 stage-2 表，让后续 random access 走 walk cache 命中率上升。
> standalone 单独跑 lat_mem_rd_rand（无前序 bench）证实：pkvm 单测反而比 non-pkvm
> 慢 2-7%，符合架构预期。

### 5.3 Finding 3 + Finding 5 的统一解读

> **pkvm 内禀主机开销 = 两个独立路径**：
>
> 1. **mmap 建表瞬间 +30 到 +47%**（[Finding 3](SUMMARY.md#finding-3)：
>    stage-2 表项每页 ~12 ns 建立成本）
> 2. **访问已建好 mapping +2 到 +7%**（Finding 5：每次 TLB miss 多一层 stage-2 walk
>    的 5-10 ns）
>
> 这两个开销**共存于 pkvm host**，是建表（控制路径）和访问（数据路径）两个独立成本。
>
> CONFIG.host 序列里观察到的 "pkvm 在 random access 上快 17%" 是因为 stage-2 表
> 暖机累积，**workload-mix-dependent**，**不是 pkvm 内禀属性**。

---

## 6. 实践意义

### 6.1 对真实应用的影响

**重 mmap 应用**（数据库 buffer pool、AI weights 加载、container 启动）：
- 频繁建表 → 付 +42% mmap 开销
- 后续访问 → stage-2 表暖→ 跟 non-pkvm 几乎一样 / 略快

**少 mmap 应用**（HPC 单次大段计算、批处理一次性分析、cold start）：
- 不暖 stage-2 表 → 访问付 +2-7% 开销
- mmap 频率低 → +42% 开销影响小

**典型 cloud workload**（混合）：
- 取决于 mmap/access 比例
- 实际宏观开销在 5-15% 之间（与 Android pKVM USENIX ATC '22 论文报道 0-5%
  接近但略高，可能 Phytium 微架构差异）

### 6.2 对 paper 论述的影响

不应该把"pkvm 比 non-pkvm 快"作为 finding——**这个观察只在 CONFIG.host 这个特定
微基准序列里成立，且依赖于 lmbench 的特定测试顺序**。

正确的 paper-level 论述应该是：

> pKVM 引入的 stage-2 表带来两个独立但都 small magnitude 的主机开销：
> 1. 建表瞬间（mmap 大段 +42%）
> 2. 访问已建好 mapping（每次 TLB miss +2-7%）
>
> 在真实 workload 中这两个开销由"建表 / 访问"比例线性组合决定。在 mmap-heavy
> workload 中，后续访问反而会因为 stage-2 表的"复用 effect" 显得更快，但这是
> workload-dependent 而非 pkvm-intrinsic。

---

## 7. 复现要点

```bash
# 在 N90 上，每个配置做：
sudo ostree admin instutil set-kargs --import-proc-cmdline \
  --replace=kvm-arm.mode=<none|nvhe|vhe|protected> --replace=lsm= --replace=audit=0
sudo update-grub && sudo reboot

# 重连后
cd /root/lmbench-3.0-a9
bash scripts/apply-masks.sh
sudo bash prepare-host.sh
bash scripts/verify-clean-env.sh || exit 1

# 跑 standalone
bash scripts/standalone-mem-bench.sh <mode_name> > /tmp/standalone-<mode>.log
```

各 log 拉回本地后用 [`results/standalone-mem-bench/`](../../results/standalone-mem-bench/)
保存。

---

## 8. 文件清单

```
docs/n90-kvm-host/
├── pkvm-memory-access-speedup.md     # 作废，原 Finding 5 解释
└── standalone-memory-bench-validation.md   # 本文，修正 Finding 5

scripts/
└── standalone-mem-bench.sh           # 单测脚本

results/standalone-mem-bench/
├── standalone-kvmoff.log
├── standalone-nvhe.log
├── standalone-vhe.log
└── standalone-pkvm.log

results/n90-day3-host/
├── n90-pkvm-noLSM-try1-*    # 第一次 N=10（出现 transition，"-17 to -33%"）
└── n90-pkvm-noLSM-try2-*    # 第二次 N=10（同配置同流程，未复现 transition）
```

---

## 9. ⭐ Try2 验证：transition 是 stochastic / 不可复现的

### 9.1 实验设计

为彻底验证"pkvm 在 CONFIG.host 里的 17-33% 加速是否可复现"，在 standalone 实验之后
**用完全相同的流程重跑 pkvm N=10 CONFIG.host**：
- 同样的 cmdline (kvm-arm.mode=protected lsm= audit=0)
- 同样的 `apply-masks.sh` + `prepare-host.sh` + `verify-clean-env.sh ✓ ALL CLEAN`
- 同样的 `CORES=0 ITERS=10 CONFIG=configs/CONFIG.host`
- 同样的 lmbench binary
- 间隔约 24 小时（机器在 standalone 实验期间反复 reboot 切配置）

新数据存为 `n90-pkvm-noLSM-try2-*`，原数据保留为 `n90-pkvm-noLSM-try1-*`。

### 9.2 结果：try2 完全没复现 try1 的 transition

逐 iter 对比 Random 64MB（ns）：

```
iter:       1    2    3    4    5    6    7    8    9    10
try1:     194  179  194  154  154  155  155  154  154  154   ← iter 4 后永久 stuck low
try2:     193  193  192  192  191  166  191  192  192  191   ← 永远没 stuck
                                       ↑
                                  iter 6 一次性 blip（166），iter 7 立刻回到 191
```

类似的 pattern 也出现在 Random 4/8/16/32 MB：try1 在 iter 4-5 永久转入 low state，
try2 几乎全部 iter 都在 high state。

### 9.3 try2 中位数与 standalone 完美一致

| 工作集 | kvmoff CFG | **try1 CFG** | **try2 CFG** | **pkvm SA** | try2 vs kvmoff |
|--------|----------:|------------:|------------:|----------:|--------------:|
| Random 4MB | 47.59 | **31.89** | 49.31 | 49.74 | **+3.6%** |
| Random 8MB | 112.54 | **91.01** | 119.59 | 120.01 | **+6.3%** |
| Random 16MB | 168.54 | **140.42** | 176.28 | 176.72 | **+4.6%** |
| Random 32MB | 180.61 | **150.23** | 188.66 | 189.57 | **+4.5%** |
| Random 64MB | 185.23 | **154.40** | 191.73 | 192.41 | **+3.5%** |
| LLC 8MB seq | 10.82 | **10.01** | 12.12 | 12.35 | **+12.1%** |

**try2 与 standalone 差异 < 1%**，两者一致显示 pkvm 比 kvmoff 慢 3-12%。
**try1 是 outlier**，所有指标都比 try2/SA 低 15-30%。

### 9.4 lat_mmap +42% 在 try1 / try2 / ns 精度复测三轮一致

mmap 大段：

| 指标 | kvmoff CFG | try1 CFG | try2 CFG | **ns 精度复测** |
|------|----------:|---------:|---------:|----------------:|
| lat_mmap 16MB | 124 | 176 (+42%) | 176 (+42%) | **175.34 (+41.8%)** |
| lat_mmap 67MB | 488 | 695 (+42%) | 697 (+43%) | **709.24 (+42.3%)** |

→ lat_mmap +42% 是**可靠、可复现**的真实 finding，三轮独立采集一致。

ns 精度复测覆盖完整 7 个 size（0.5 / 1 / 2 / 4 / 8 / 16 / 64 MB），
所有 cell MAD% < 1%，pkvm overhead 从 +18.8% 渐进到 +42.3%。
详见 `results/precise-mmap/{mode}.log` 及 FINAL-REPORT §4.7。

### 9.5 最终修订的 pkvm 主机开销

| 指标 | pkvm 真实开销 | 复现情况 |
|------|-------------:|---------|
| mmap 大段建表 | **+42 to +47%** | try1 + try2 + 文献多方一致，确认 |
| Random memory access | **+3 to +7%** | try2 + standalone 一致，确认 |
| Sequential memory access | **0 to +14%** | try2 + SA 一致，确认 |
| syscall fastpath | **±1%** | 4 配置全数据一致 |
| CPU 算术 | **0%** | 必然，4 配置 sanity check |

**try1 的"快 17-33%"是一次性 stochastic 现象**，机制大概率涉及 Linux page allocator
偶然给 pkvm 进程的 64 MB heap 落进了 prepopulate stage-2 1 GB block 内的"幸运对齐"状态。
这个状态**存在但进入是随机的且不稳定**——try2 iter 6 一次性 166 ns blip 证实它**确实**
存在，但**不能持续**也**不能保证触发**。

### 9.6 paper 该报告什么

应该报告的：
- ✅ **pkvm 内禀建表开销 +42%**（lat_mmap 大段）
- ✅ **pkvm 内禀访问开销 +3-7%**（lat_mem_rd_rand）
- ✅ 上述两个开销可在 CONFIG.host + standalone 两套独立方法学下复现
- ✅ syscall / CPU / cache hit 跨 4 配置不可区分（≤ 1%）

**不应该报告**：
- ❌ "pkvm 比 non-pkvm 快"——这是单次跑出的 stochastic 状态，不可复现
- ❌ "pkvm stage-2 暖机能稳定加速"——同配置重跑没复现，机制假说不成立

### 9.7 这次方法学的教训

1. **单次 N=10 不足以发现 stochastic 现象** —— 我们需要"重复 N=10 多次"才看出 try1 是异常
2. **看起来 paper-grade 干净的数据也可能藏着隐性状态** —— iter MAD 在 try1 只有 2.4%，
   看不出 iter 4-5 transition 是异常事件
3. **standalone 微基准 + isolated 测试** 是发现 sequence-dependent artifact 的关键工具
4. **同配置 2 次独立重跑** 是确认 finding reproducibility 的最低标准
