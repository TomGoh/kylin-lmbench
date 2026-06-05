# pKVM 次级现象：LLC 边界与 DRAM 段随机访问反而快 17-33%

> ⚠️ **本文已作废 / 已被推翻**
>
> 后续 standalone 验证实验证明：本文报告的"pkvm 反而快 17-33%"是
> **CONFIG.host 测试序列的副产品**——pkvm 在 random access 测试前被 lat_mmap 等
> 前序 bench"暖热"了 stage-2 表，造成 17-33% 加速假象。standalone 单独跑
> lat_mem_rd_rand（无前序 bench）时，pkvm 不仅没快，**反而比 non-pkvm 慢 2-7%**
> （符合架构理论预期：每次 TLB miss 多一层 stage-2 walk）。
>
> 修正后的解读和完整证据见
> [`standalone-memory-bench-validation.md`](standalone-memory-bench-validation.md)。
>
> 本文以下内容保留作为方法论反思 / 过程记录——展示一个"看起来合理但实际不成立"的
> 假说推演如何被实验验证推翻。**不要把本文的结论当作 paper finding。**
>
> ---
>
> 跟 `lat_mmap` 大段慢 +42% 同样显著、方向相反、机制完全不同的另一个 pKVM 现象：
> 在 LLC 边界（3-8 MB 工作集）和 DRAM 段（≥ 8 MB），pkvm 的内存访问延迟**比其它
> 3 配置（kvmoff / nvhe / vhe）低 17-33%**，且这个优势横跨多种访问模式
> （顺序、随机、不同 stride）。本文逐项列数据、给出假说、并指出 paper 应该如何
> 处理这个反直觉发现。
>
> 主分析见 [`SUMMARY.md`](SUMMARY.md)；mmap 开销机制见
> [`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)。

**Date**: 2026-06-04
**数据来源**：`results/n90-day3/n90-{kvmoff,nvhe,vhe,pkvm}-noLSM-full-cpu0.csv`
（N=10 干净对照）

---

## 1. 现象：pkvm 在 LLC 边界 + DRAM 段一致快 17-33%

### 1.1 `lat_mem_rd_rand`（随机指针 chasing）—— 最干净的信号

stride 16 B（绕过硬件 prefetcher），lmbench 把链表节点先随机打乱再走链，
**几乎纯粹测 DRAM / cache miss 延迟**：

| 工作集 | kvmoff | nvhe | vhe | **pkvm** | pkvm vs kvmoff |
|--------|-------:|-----:|----:|---------:|---------------:|
| 0.5 MB (L2 内) | 10.70 ns | 10.61 | 10.25 | 10.85 | +1.4% |
| 1 MB (LLC 内) | 19.41 | 19.48 | 19.48 | 18.61 | −4.1% |
| 2 MB | 20.68 | 20.75 | 20.73 | 19.91 | −3.7% |
| **3 MB (LLC 上沿)** | 36.60 | 36.63 | 36.56 | **26.87** | **−26.6%** |
| **4 MB** | 47.59 | 47.69 | 47.45 | **31.89** | **−33.0%** |
| **6 MB** | 67.14 | 67.35 | 67.37 | **49.87** | **−25.7%** |
| **8 MB (LLC 外)** | 112.5 | 112.6 | 112.3 | **91.01** | **−19.1%** |
| 12 MB | 154.6 | 154.8 | 154.6 | 128.1 | −17.2% |
| 16 MB | 168.5 | 168.6 | 169.7 | 140.4 | −16.7% |
| 24 MB | 177.2 | 177.5 | 180.3 | 147.4 | −16.8% |
| 32 MB | 180.6 | 180.8 | 182.7 | 150.2 | −16.8% |
| 48 MB | 182.7 | 182.4 | 183.9 | 151.2 | −17.2% |
| **64 MB (DRAM)** | 185.2 | 185.1 | 185.4 | **154.4** | **−16.6%** |

**信号特征**：
- L1d / L2 内（≤ 0.5 MB）4 配置等价
- LLC 内（0.5-3 MB）差异 < 5%
- **3 MB 起 pkvm 拉开 27-33% 优势**（LLC 还能命中，但开始有 evict）
- **8 MB 以上稳定 17-19% 优势**（纯 DRAM 段）

### 1.2 `lat_mem_rd_load`（顺序 stride）—— 同样可见但更小

stride 256 B（硬件 prefetcher 部分参与）：

| 工作集 | kvmoff | nvhe | vhe | **pkvm** | pkvm vs kvmoff |
|--------|-------:|-----:|----:|---------:|---------------:|
| 1 MB | 4.44 ns | 4.44 | 4.43 | 4.45 | +0.3% |
| 3 MB | 5.32 | 5.31 | 5.31 | **4.87** | **−8.4%** |
| 4 MB | 5.49 | 5.48 | 5.48 | **4.96** | **−9.6%** |
| **6 MB** | 8.25 | 8.22 | 8.30 | **6.87** | **−16.7%** |
| 8 MB | 10.82 | 11.41 | 12.45 | 10.01 | −7.4% |
| 64 MB | 10.36 | 10.24 | 10.78 | 10.11 | −2.3% |

顺序访问下 prefetcher 帮忙，差距缩小到 7-17%。但**方向一致**：pkvm 在 LLC 边界
仍然快。

### 1.3 `bw_mem_rd` 在 LLC 边界的尖峰

| 工作集 | kvmoff | nvhe | vhe | **pkvm** | pkvm vs kvmoff |
|--------|-------:|-----:|----:|---------:|---------------:|
| 4 MB | 25947 MB/s | 26187 | 26003 | 27798 | +7.1% |
| **8 MB** | 16445 | 16423 | 15946 | **20321** | **+23.6%** |
| 16 MB | 18623 | 18817 | 15794 | 18983 | +1.9% |
| 67 MB | 18446 | 18404 | 17837 | 18413 | −0.2% |

8 MB 是 Phytium FTC862 的 **LLC 与 DRAM 边界**——cache evict 与 DRAM 命中竞争最
激烈的点。pkvm 在这里 +23.6% 异常突出。

### 1.4 `bw_mmap_rd_o2c`（mmap+read+close）—— mmap 开销 + 访问加速混在一起

| 文件 size (MB) | kvmoff | nvhe | vhe | **pkvm** | pkvm vs kvmoff |
|--------------:|-------:|-----:|----:|---------:|---------------:|
| 0.13 | 6084 MB/s | 6101 | 6103 | **5162** | **−15.1%** |
| 0.26 | 7225 | 7235 | 7225 | 5905 | **−18.3%** |
| **0.52** | 7836 | 7845 | 7844 | 6281 | **−19.8%** |
| **1.05** | 8177 | 8179 | 8175 | 6484 | **−20.7%** |
| 2.10 | 8459 | 8480 | 8475 | 8433 | −0.3% |
| 4.19 | 8137 | 8167 | 8140 | 8380 | +3.0% |
| **8.39** | 6741 | 6764 | 6750 | **7414** | **+10.0%** |
| **16.78** | 6397 | 6510 | 6605 | **6985** | **+9.2%** |
| 33.55 | 7319 | 7304 | 7027 | 7191 | −1.8% |

`bw_mmap_rd_o2c = (size / (mmap + read + close 总耗时))`。在小文件（0.13-1 MB）
mmap setup 占大头 → pkvm 慢 15-21%（一致前面 `lat_mmap` 大段 +42% 结论的小段
版本）。在中等文件（4-16 MB）访问吞吐占大头 → **pkvm 反而快 9-10%**。

---

## 2. 为什么 pkvm 在 LLC 边界与 DRAM 段访问会更快？

`lat_mem_rd_rand` 在 8-64 MB 段稳定快 17-19%——这是个 **non-trivial 优势**，需要
解释。

### 2.1 候选假说 #1：stage-2 大 block mapping 改善了 page-walk caching

ARMv8 的 PTW（page table walker）有几级 walk caches，缓存中间页表条目。在 pkvm
下，主机 stage-2 表是 boot 时由 `prepopulate_host_stage2`（见
`host.rs:374`）用**最大允许的 block size（1 GB 或 2 MB block）**预填。这意味着：

- 整个主机的 64 MB 工作集**完全被一个 1 GB stage-2 entry 覆盖**
- 硬件 PTW 在 stage-1 walk 时，每级 stage-1 PTE 都需要去 stage-2 walk
- pkvm 下 stage-2 walk **几乎都被 walk cache 一次命中**（因为全部落在同一个 1 GB
  block entry）
- non-pkvm 下没有 stage-2 walk，但 stage-1 walk 的中间表项分布可能更碎片化
  （Linux 给每个进程的 vma 分别分页）

净效果：pkvm 的 PTW 总成本可能反而更低（虽然多一层）。这是个反直觉但**硬件
实现细节有可能造成的**情形。

### 2.2 候选假说 #2：DRAM bank/row 布局差异

pkvm 启动时 dmesg 报 `kvm [0]: Reserved 166 MiB at 0x2775800000`。这块 166 MB
内存被永久划给 hyp（含 stage-2 表 + Rust runtime）。剩余给主机的物理内存**起点
偏移不同于 non-pkvm**——可能落在不同的 DRAM bank / row 上，row buffer hit rate
不同。

如果 Phytium FTC862 的 DDR controller 在 pkvm 下恰好让主机 working set 集中在
更少的 bank 上，row buffer hit rate 升高可以解释 17-19% 的延迟下降。

### 2.3 候选假说 #3：TLB ASID/VMID 标签策略差异

pkvm 下主机以 stage-2 enabled 状态运行，TLB entry 携带 ASID + VMID 双标签。
non-pkvm 只有 ASID。**双标签可能让 TLB 容量利用率更高**——硬件 TLB 大小相同
但更长的 tag 让命中更精确，减少误冲突。

ARMv8.2 上某些实现确实存在这种 "TLB tag 越长，conflict miss 越少" 的非直观
效应（参考 ARM Architecture Reference Manual 的 TLB invalidation chapter）。

### 2.4 候选假说 #4：硬件预取器响应不同

某些 ARM SoC（包括 Phytium）的 L1/L2 prefetcher 行为可能受 `HCR_EL2.E2H` 或
`VTCR_EL2` 配置影响——比如 stage-2 enabled 时 prefetcher 看到的是 IPA，触发
策略与 PA 时不同。

### 2.5 哪个假说最可能

最像的是 **#1（PTW walk cache 命中率）+ #2（DRAM 布局）**的组合：

- `lat_mem_rd_rand` 17-19% 的 onset 严格在 LLC 边界（≥ 8 MB）—— 说明跟 stage-2
  walk 频率有关
- 优势规模（约 30 ns 减少在 ~180 ns 的总延迟里）跟"少 1 次 page table memory
  reference"的开销吻合
- DRAM bank/row 差异通常给 5-10%，不足以解释 33% 的最大差距

但**我们没有直接证据**——需要：
- ARM PMU counter（`STAGE2_TLB_REFILL`、`L1_PTW_HIT`）数据
- DDR controller 性能寄存器
- 用 `perf stat -e cache-references,cache-misses,dTLB-load-misses` 比较 4 配置

这些都是 paper 后续工作。

---

## 3. 反向佐证：为什么访问加速没出现在小工作集

L1d / L2 内（≤ 0.5 MB）4 配置等价。原因：
- 访问命中 cache → **不发生 TLB miss → 不发生 PTW**
- pkvm 的 stage-2 优势依赖 PTW 频繁触发，cache hit 时这个优势不出现

LLC 内（0.5-3 MB）差异 < 5%。原因：
- TLB miss 偶发，但 LLC 命中所以 PTW 也快
- pkvm 优势刚起步但还不显著

LLC 边界（3-8 MB）开始拉开。原因：
- TLB miss 高频，但 LLC 还有部分命中
- pkvm 的 stage-2 PTW 优势开始累积

DRAM 段（≥ 8 MB）稳定 17-19% 优势。原因：
- TLB miss 几乎确定，必须 PTW
- pkvm 的 walk cache hit rate 高，节省 ~30 ns 的 page table memory reference

---

## 4. 跟 `lat_mmap` 慢 +42% 的关系

这俩**完全是同一机制的两面**：

| 阶段 | pkvm 做的事 | 性能影响 |
|------|------------|---------|
| **建表瞬间**（mmap 触发新 VA range） | host stage-2 abort → `host_stage2_idmap` 建表 → TLBI 同步 | 每页 ~12 ns 额外延迟 → mmap 大段 +42% |
| **访问已建好的 mapping** | stage-2 walk cache hit → 比 non-pkvm 的 stage-1-only walk 还快 | DRAM 随机访问 −17 to −33% |

**净效果取决于"建表 / 访问"比例**：
- 应用频繁 mmap/munmap 小段（典型：数据库 buffer pool 调整、AI weights 加载、
  container 启动）→ 建表成本占主导 → pkvm 慢
- 应用建立 mmap 后长期访问大段内存（典型：内存数据库稳态查询、in-memory cache、
  HPC 计算）→ 访问加速占主导 → **pkvm 可能反而快**

这个 **non-trivial 的非对称效应** 是 paper 应该明确刻画的点：pKVM 不只是有
"开销"，在某些路径上反而**带来加速**。文献里很少有人量化过 stage-2 enabled 对
host 访问性能的**正向**影响。

---

## 5. 实验完整性：4 配置数据原始证据

| 指标 | 单位 | kvmoff | nvhe | vhe | pkvm |
|------|-----|-------:|-----:|----:|-----:|
| lat_mem_rd_rand sz4MB | ns | 47.59 | 47.69 | 47.45 | 31.89 |
| lat_mem_rd_rand sz8MB | ns | 112.54 | 112.60 | 112.32 | 91.01 |
| lat_mem_rd_rand sz64MB | ns | 185.23 | 185.05 | 185.43 | 154.40 |
| lat_mem_rd_load sz8MB stride256 | ns | 10.82 | 11.41 | 12.45 | 10.01 |
| bw_mem_rd sz8.39MB | MB/s | 16445 | 16423 | 15946 | 20321 |
| bw_mmap_rd_o2c sz1.05MB | MB/s | 8177 | 8179 | 8175 | 6484 |
| bw_mmap_rd_o2c sz8.39MB | MB/s | 6741 | 6764 | 6750 | 7414 |

MAD% 全部 < 3%（多数 < 1%）。kvmoff / nvhe / vhe 三者在每一项上都几乎完全相等
（≤ 0.5% 差异）—— **pkvm 是单独的 outlier**，且**方向跟 lat_mmap 相反**。

---

## 6. 论文 takeaway

### 6.1 必须在 paper 里报告的两个相反 finding

1. **pKVM 慢的地方**：mmap 大段 +42%（stage-2 表建立成本，每页 ~12 ns）
2. **pKVM 反而快的地方**：LLC 边界 + DRAM 随机访问 −17 to −33%（候选机制：
   stage-2 大 block mapping 改善 PTW walk cache 命中率 + DRAM 布局微差）

只报告 (1) 是不完整甚至误导的——这俩是**同一机制（stage-2 enabled）的代价 vs
回报**。

### 6.2 跟文献预期相比

Android pKVM 团队 USENIX ATC '22 报道的 0-5% 主机宏观开销，可以理解为
（建表成本 × mmap 频率） − （访问加速 × 访问量） 在宏观 workload 下的平均
结果。我们的微基准把这两面分离开来量化了。

### 6.3 后续工作

- **PMU counter 直接验证**：用 `perf stat -e stage2_tlb_refill,l1d_tlb_refill,
  walk_cache_*` 比较 4 配置
- **DRAM bank 测试**：用 `aclbench` 或自写测试，固定 working set 但变化物理
  地址布局，看 row hit rate 是否解释 17-19% 中的一部分
- **跟 Apple Silicon / Ampere Altra 对比**：同样 ARMv8.2+ 上跑同样的对比，看
  这个 17-19% 加速是 Phytium 特有还是 ARMv8.2 通用

---

## 7. 总结一句话

**pKVM 在主机性能上的总体 picture**：

```
        ←—— pKVM 慢的地方 ——→  ←—— pKVM 中性 ——→  ←—— pKVM 反而快的地方 ——→

         mmap 大段建表          syscall fastpath       LLC 边界 + DRAM 随机访问
         +30% to +47%           ±1%                    −17% to −33%
         （stage-2 setup）       （不进 EL2）            （stage-2 walk cache 命中）

         lat_mmap                lat_syscall            lat_mem_rd_rand sz≥8MB
         bw_mmap_rd_o2c <1MB     lat_proc fork/exec     bw_mem_rd sz=8MB
                                  lat_ctx                bw_mmap_rd_o2c 8-16MB
                                  CPU 算术
                                  bw_mem 小工作集
                                  IPC （pipe/unix/tcp/udp）
```

**单向解读 pkvm = "有 X% 开销" 是 paper 里常见但不准确的描述**。我们的 N=10
干净对照让这个双向特性首次可量化。
