# 配置 4 / 4: `pkvm-noLSM`

> ARM64 KVM 以 Protected（pKVM）模式启用：基于 **nVHE 体系**——主机内核仍跑在
> **EL1**，pKVM hypervisor 在 EL2 提供保护层（包括 host stage-2 表，防止主机
> 直接读未来客户机内存）。dmesg 自报 `Protected nVHE mode initialized successfully`。
> 本场景没有客户机在跑，pkvm 保护机制空载。
>
> 总体背景、方法论、跨配置对比口径请见 [`README.md`](README.md)。

**Status**: ✅ N=10 clean × 2 套（try1 + try2，独立重跑）
- `n90-pkvm-noLSM-try1-*`：第一次 N=10（6051 s, iter MAD 2.4%）—— 含偶发 stochastic
  iter 4-5 transition，本文 §4 数据来自这一份
- `n90-pkvm-noLSM-try2-*`：同配置同方法第二次 N=10（6166 s, iter MAD 0.7%）——
  **完全没复现 try1 的 transition**，是 pkvm 真实代表性数据；**`SUMMARY.md` /
  xlsx 用的是这份**

⚠️ **本文 §4.8 缓存层级表里 try1 的"pkvm 在 LLC 边界 + DRAM 段快 17-33%"是
一次性 stochastic 现象，try2 完全没复现**。最终修订的 paper-grade 结论：pkvm 在
随机内存访问上**比 non-pkvm 慢 3-7%**（架构上多一层 stage-2 walk）。详见
[`standalone-memory-bench-validation.md`](standalone-memory-bench-validation.md) §9。

**本配置发现两个 paper 级 pkvm 主机开销**：

1. **`lat_mmap` 大段比其它 3 配置慢 +42%**（stage-2 表建立成本）——
   详见 [`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)
2. **standalone 随机访问比其它 3 配置慢 +2-7%**（每次 TLB miss 多一层 stage-2 walk）——
   详见 [`standalone-memory-bench-validation.md`](standalone-memory-bench-validation.md)

⚠️ 这里**之前**写过"pkvm random access 反而快 17-33%"——那是
**CONFIG.host 序列副产品**，已被 standalone 验证推翻。详细机制和数据见上述
validation 文档；原过期文档 [`pkvm-memory-access-speedup.md`](pkvm-memory-access-speedup.md)
作为方法论反思保留。
跨配置综合分析见 [`SUMMARY.md`](SUMMARY.md)；
全部 684 项指标的 4 配置对照见 [`lmbench-N10-4config.xlsx`](lmbench-N10-4config.xlsx)。

---

## 1. 实验环境准备

### 1.1 硬件 / 内核
同 [`README.md`](README.md) §4。

### 1.2 cmdline 切换

```bash
sudo ostree admin instutil set-kargs --import-proc-cmdline \
  --replace=kvm-arm.mode=protected --replace=lsm= --replace=audit=0
sudo update-grub
sudo reboot
```

### 1.3 启动验证（dmesg 关键行）

```
[    0.000000] kvm [0]: Reserved 166 MiB at 0x2775800000
[    0.060356] CPU features: detected: Protected KVM
[    0.060392] CPU: All CPU(s) started at EL2
[    0.207682] kvm [1]: nv: 477 coarse grained trap handlers
[    0.207736] kvm [1]: IPA Size Limit: 40 bits
[    0.294433] kvm [1]: GICv3: no GICV resource entry
[    0.294437] kvm [1]: disabling GICv2 emulation
[    0.294650] kvm [1]: Protected nVHE mode initialized successfully
```

| 行 | 含义 |
|----|------|
| `Reserved 166 MiB at 0x2775800000` | pKVM hypervisor 预留的内存池（hyp 自己的 stage-1 表 + meta + Rust runtime） |
| `CPU features: detected: Protected KVM` | 硬件 + cmdline + 内核三者协调，决定走 protected 路径 |
| `Protected nVHE mode initialized successfully` | **核心识别行**：pKVM 完全 init，host stage-2 表已 prepopulate |

**架构要点**：尽管名字带 "nVHE"，实际 pkvm 模式下主机仍跑在 EL1（HCR_EL2.E2H=0）。
pkvm hypervisor 自己在 EL2，且**维护一份 host stage-2 表**用大 block mapping
预先把整个 hyp_memory 映射完（参见 `host.rs:prepopulate_host_stage2`）。
主机每次访问已 prepopulate 的物理地址，硬件 stage-2 TLB 命中后直接走完两级 walk，
**不进 hyp**。

### 1.4 主机噪声抑制

pkvm 模式启动时 Kylin 默认会拉起 `pvm-manage.service`——一个 pVM lifecycle
manager，**自动开一个客户机跑 biometric-auth TA**。这个守护进程是本配置噪声
源里最大的一个（占 stage-2 表 + 拉 cpu0 干扰）。
`apply-masks.sh` 列表里已 mask（`pvm-manage`），所以 N=10 跑的时候没有它在跑。

### 1.5 运行时验证（`verify-clean-env.sh` 全通过）

| 项 | 值 |
|----|----|
| `/sys/kernel/security/lsm` | `capability,kycp` |
| `dmesg \| grep Protected` | `Protected nVHE mode initialized successfully` |
| `pvm-manage.service` | masked, 不运行 |
| THP / ASLR | never / 0 |
| cpu0 频率 | 1900 MHz, performance |

---

## 2. 实验配置

同 kvmoff.md §2。`ENV_TAG=n90-pkvm-noLSM-full`。

---

## 3. 实施 / 执行

### 3.1 iter 时长

| iter | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|------|---|---|---|---|---|---|---|---|---|----|
| 秒   | 616 | 620 | 621 | 616 | 610 | 579 | 600 | 601 | 602 | 586 |

总 wall 101 min，iter MAD = 2.4%（max−min = 42 s）。**比其它 3 配置略松**
（kvmoff/nvhe/vhe 都在 0.5-0.8% 范围）。iter 6 / iter 10 跑得快一点
（579 / 586 s），可能恰好碰到 stage-2 表碎片少 / TLB 命中率高的窗口。

### 3.2 烟测

`CONFIG.test ITERS=1` = 230 s，`lat_syscall null = 0.1029, read = 0.1635 µs`，
与 N=10 中位（0.1029 / 0.1640）一致。**无暖机**。

---

## 4. 结果（N=10 中位 ± MAD%）

### 4.1 lat_syscall

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| null    | 0.1029 | 0.00 |
| write   | 0.1399 | 0.21 |
| read    | 0.1640 | 0.00 |
| fstat   | 0.2278 | 0.22 |
| stat    | 0.9635 | 0.09 |
| open    | 1.4903 | 0.27 |

### 4.2 lat_sig

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| install | 0.1446 | 0.07 |
| prot    | 0.1607 | 0.68 |

### 4.3 lat_proc

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| fork    | 134.83 | 0.98 |
| exec    | 376.38 | 1.14 |
| shell   | 787.11 | 0.83 |

### 4.4 lat_pagefault

minor = 0.2547 µs（MAD 0.37%）。

### 4.5 lat_ctx

| 工作集 / 进程数 | (µs) | MAD% |
|----------------|-----:|-----:|
| 0 KB / 2  | 2.370 | 1.27 |
| 16 KB / 2 | 2.375 | 1.26 |
| 16 KB / 8 | 5.955 | 0.42 |
| 16 KB / 16 | 6.125 | 0.41 |

### 4.6 IPC

| 类型 | 中位 (µs) | MAD% |
|------|---------:|-----:|
| `lat_pipe rt`   |  5.562 | 0.88 |
| `lat_unix rt`   | 10.267 | 2.36 |
| `lat_tcp lhost` | 22.754 | 0.92 |
| `lat_udp lhost` | 15.935 | 0.18 |

### 4.7 ⭐ lat_mmap（pKVM 的核心成本信号）

ns 精度复测数据（`lat_mmap_precise`，N=10，MAD% < 1%）：

| size | pkvm 中位 (µs) | kvmoff/nvhe/vhe (µs) | Δ% |
|------|--------------:|-----------------:|-------:|
| 0.5 MB |   **9.224** |   7.76 – 7.78 | **+18.8%** |
| 1 MB   |  **14.812** |  11.75 – 11.78 | **+25.9%** |
| 2 MB   |  **27.593** |  21.02 – 21.18 | **+31.0%** |
| 4 MB   |  **49.105** |  36.09 – 36.45 | **+36.1%** |
| 8 MB   |  **92.243** |  65.72 – 66.12 | **+39.5%** |
| 16 MB  | **175.340** | 123.38 – 123.70 | **+41.8%** |
| 64 MB  | **709.236** | 498.15 – 498.54 | **+42.3%** |

**这是 paper 级的发现**——详见 [`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)。
机制：pkvm 在 host 端建立新 VA range 时需要同步更新 stage-2 表
（`host_stage2_idmap`），其它 3 配置没有这层表，所以走纯 Linux 路径。

> 早先 lmbench 整数 µs round 让 1/16/67 MB 行的 pkvm 与其它三者**看起来一样**
> （12/124/176/487 µs round 同号），是 round 假象。精度复测后所有 size 上 pkvm 都更慢，
> 从 0.5 MB 的 +18.8% **渐进**到 64 MB 的 +42.3%——这种"size 越大 overhead% 越大"
> 的形状才是 stage-2 表建立成本 ∝ pages_touched 的真实指纹。

### 4.8 lat_mem_rd_load / lat_mem_rd_rand 缓存层级

L1d / L2 / LLC 内（≤ 1 MB）4 配置完全等价。

在 LLC 边界 + DRAM 段（≥ 3 MB）有**两套不同结果**——同配置 try1 和 try2 N=10
分别给出截然不同的中位：

| 工作集 | kvmoff CFG | nvhe CFG | vhe CFG | **try1 CFG** | **try2 CFG** | **pkvm SA** | 真实开销 |
|--------|----------:|---------:|--------:|------------:|------------:|----------:|--------:|
| 4 MB | 47.59 | 47.69 | 47.45 | **31.89** ⚠️ | 49.31 | 49.74 | **+3.6%** |
| 8 MB | 112.54 | 112.60 | 112.32 | **91.01** ⚠️ | 119.59 | 120.01 | **+6.3%** |
| 16 MB | 168.54 | 168.56 | 169.71 | **140.42** ⚠️ | 176.28 | 176.72 | **+4.6%** |
| 32 MB | 180.61 | 180.78 | 182.72 | **150.23** ⚠️ | 188.66 | 189.57 | **+4.5%** |
| 64 MB | 185.23 | 185.05 | 185.43 | **154.40** ⚠️ | 191.73 | 192.41 | **+3.5%** |
| LLC 8MB seq | 10.82 | 11.41 | 12.45 | **10.01** ⚠️ | 12.12 | 12.35 | **+12.1%** |

**try1 显示 pkvm 快 17-33%**（看起来"反而快"）；**try2 + standalone 一致显示 pkvm 慢 3-7%**。

逐 iter 分析（详见 [`standalone-memory-bench-validation.md`](standalone-memory-bench-validation.md) §9）：

```
Random 64MB:
  try1:  194 179 194 154 154 155 155 154 154 154   ← iter 4 后永久 stuck low
  try2:  193 193 192 192 191 166 191 192 192 191   ← 全过程没 stuck，仅 iter 6 一次 blip
```

→ **try1 的 transition 是一次性 stochastic 现象**：偶然碰到 Linux page allocator
让 pkvm 主机 64MB heap 落进 pkvm prepopulate stage-2 1GB block 内的"幸运对齐"状态；
状态进入随机、不稳定，try2 完全没复现。

**结论**：pkvm 真实开销 = standalone / try2 一致显示的 +3-7%（每次 TLB miss 多一层
stage-2 walk，加 5-10 ns）。CONFIG.host 中观察到的"快 17-33%"是不可复现的
偶发现象，不能作为 paper finding。

xlsx 和 SUMMARY 用的是 **try2 数据**（代表性、可复现）。

机制详解、Rust 代码引用、与 standalone 对比，见
[`standalone-memory-bench-validation.md`](standalone-memory-bench-validation.md)。

### 4.9 bw_mem（**与其它 3 配置等价**，pkvm 列 = try2）

| 指标 | peak (MB/s) | DRAM 67 MB (MB/s) | DRAM 与 kvmoff 差 |
|------|-----------:|-----------------:|-----------------:|
| `bw_mem_rd`    | 48593 | 18154 | −1.58% |
| `bw_mem_wr`    | 57337 |  7563 | −0.28% |
| `bw_mem_bzero` | 57446 | 41329 | −1.39% |

带宽差异 ≤ 1.6%，远小于 lat_mmap 的 +42%——访问已 prepopulated 的内存
（`prepopulate_host_stage2`），stage-2 walk 全部 TLB hit，不进 hyp。

> 早期 try1 数据集在 random/sequential mem access 上观察到 pkvm "+17-33%"，
> 已被同配置 try2 复测完全推翻 → stochastic outlier，已归档到
> `pkvm-memory-access-speedup.md` (DEPRECATED)。

### 4.10 lat_ops（**完全相等**）

`integer_add 0.280 / integer_div 4.450 / double_add 1.110 / double_div 6.670` ns，
MAD 0%。CPU 算术与其它 3 配置一致到 0.0001 精度——sanity check。

### 4.11 TLB

`tlb effective = 48`，MAD 0%。硬件特性。

---

## 5. 本配置的内在特征（最终修订）

1. **mmap 大段慢 +42%**（stage-2 表建立成本，控制路径开销）——
   try1 + try2 一致，文献多方一致 ✓
2. **随机内存访问慢 +3-7%**（每次 TLB miss 多一层 stage-2 walk，数据路径开销）——
   try2 + standalone 一致 ✓
3. **syscall、CPU 算术、cache 内 (≤ 1 MB) 访问、IPC、`bw_mem` peak 跟其它 3 配置
   不可区分**（±1%）
4. **iter MAD（try1 = 2.4%, try2 = 0.7%）**——try1 较松是因为含 stochastic
   transition pattern，try2 干净
5. ⚠️ **try1 上观察到的 pkvm "快 17-33%" 是一次性 stochastic 现象**——同配置同流程
   try2 完全没复现。机制可能涉及 page allocator + stage-2 block 偶然对齐，
   状态存在但进入随机、不稳定、不可控

详细机制分解、Rust 代码引用、与 standalone / try2 的方法学对比，见：
- [`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)（mmap 慢，机制坚固）
- [`standalone-memory-bench-validation.md`](standalone-memory-bench-validation.md)
  （含 §9 try2 重跑验证 ─ 推翻 stage-2 暖机假说，最终确认 pkvm +3-7% 访问开销）
- [`pkvm-memory-access-speedup.md`](pkvm-memory-access-speedup.md)
  （**作废**：原 "快 17-33%" 解释，保留作方法论反思）

跨 4 配置对比见 [`SUMMARY.md`](SUMMARY.md)。
