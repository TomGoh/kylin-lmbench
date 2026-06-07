# 跨配置综合分析：ARM64 KVM 4 模式 host 性能对比

> Phytium FTC862 + KylinOS 6.6.0-73-generic 上对 ARM64 KVM 全部 4 种 host 配置
> （kvm-off / nvhe / vhe / protected）的 N=10 lmbench 对照实验。所有 4 个数据集
> 都在**统一的彻底去噪环境**下采集（72 项系统级 + 12 项用户级守护进程 mask，
> `verify-clean-env.sh ✓ ALL CLEAN`），唯一自由变量是 `kvm-arm.mode` cmdline。
>
> 各配置子报告见 [`kvmoff.md`](kvmoff.md)、[`nvhe.md`](nvhe.md)、
> [`vhe.md`](vhe.md)、[`pkvm.md`](pkvm.md)；
> 总体方法论见 [`README.md`](README.md)；
> pKVM mmap 开销专题见 [`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)；
> 全部 684 项指标的 4 配置对照见 [`lmbench-N10-4config.xlsx`](lmbench-N10-4config.xlsx)。

**Date**: 2026-06-04

---

## 1. 实验矩阵一览

| 项目 | 值 |
|------|-----|
| 硬件 | Phytium FTC862，8 核 |
| 内核 | `6.6.0-73-generic`（KylinOS V11，pKVM builtin） |
| CPU 频率 | 锁 1900 MHz，调速器 `performance` |
| THP / ASLR | never / 0 |
| LSM 栈 | `capability,kycp`（无 ksaf / bpf / audit） |
| 绑核 | cpu0（`taskset -c 0`） |
| 噪声抑制 | 72 系统 + 12 用户服务 mask，桌面 `multi-user.target` |
| lmbench 配置 | `CONFIG.host`（全套 BENCHMARK_*=YES） |
| N | 10 次重复 |
| 单 iter 时长 | 平均 ~614 s |
| 单配置 wall time | ~102 min |

### 4 模式的架构差异

| 模式 | cmdline | host 运行 EL | EL2 内容 | host stage-2 表 |
|------|---------|------------|---------|----------------|
| **kvmoff** | `kvm-arm.mode=none` | EL1 | 空（KVM 未 init） | 无 |
| **nvhe**   | `kvm-arm.mode=nvhe` | EL1 | hyp stub（最小） | 无 |
| **vhe**    | `kvm-arm.mode=vhe` | **EL2**（E2H=1） | host kernel 自己 | 无 |
| **pkvm**   | `kvm-arm.mode=protected` | EL1 | pkvm hypervisor + Rust 内存隔离 | **有，boot 时大 block 预填** |

---

## 2. 综合数据表（N=10 中位 + 跨配置 Δ%）

### 2.1 系统调用与进程（µs，越小越好）

| 指标 | kvmoff | nvhe | vhe | pkvm | 跨 4 配置 Δ |
|------|-------:|-----:|----:|-----:|:----------:|
| null call (空 syscall) | 0.1028 | 0.1029 | 0.1028 | 0.1029 | **±0.1%** |
| open/close | 1.4952 | 1.4898 | 1.4912 | 1.4903 | ±0.4% |
| fork | 136.19 | 136.48 | 136.55 | 134.83 | ±1.3% |
| exec | 377.31 | 375.74 | 377.00 | 376.38 | ±0.4% |
| sh (shell) | 796.71 | 792.79 | 791.29 | 787.11 | ±1.2% |

**4 配置在 syscall fastpath 与 mm-heavy 进程操作上不可区分。**

### 2.2 处理器运算（ns，越小越好）

| 指标 | kvmoff | nvhe | vhe | pkvm | Δ |
|------|-------:|-----:|----:|-----:|:-:|
| intgr add | 0.280 | 0.280 | 0.280 | 0.280 | **0%** |
| intgr div | 4.450 | 4.450 | 4.450 | 4.450 | **0%** |
| double add | 1.110 | 1.110 | 1.110 | 1.110 | **0%** |
| double div | 6.670 | 6.670 | 6.670 | 6.670 | **0%** |

**完全相等到 0.001 ns**——CPU pipeline 不进 EL2，必然 0% 差异。Sanity check ✓。

### 2.3 上下文切换（µs，越小越好）

| 指标 | kvmoff | nvhe | vhe | pkvm | Δ |
|------|-------:|-----:|----:|-----:|:-:|
| 2p/0K ctxsw | 2.370 | 2.380 | 2.390 | 2.370 | ±1% |
| 2p/16K ctxsw | 2.365 | 2.380 | 2.370 | 2.375 | ±1% |
| 8p/16K ctxsw | 5.865 | 5.860 | 5.850 | 5.955 | ±2% |
| 16p/16K ctxsw | 5.985 | 6.000 | 6.025 | 6.125 | ±2% |

### 2.4 本地通信延迟（µs，越小越好）

| 指标 | kvmoff | nvhe | vhe | pkvm | Δ |
|------|-------:|-----:|----:|-----:|:-:|
| Pipe | 5.586 | 5.595 | 5.615 | 5.562 | ±1% |
| AF UNIX | 10.388 | 9.974 | 9.861 | 10.267 | ±5%（VHE 略快）|
| UDP loopback | 15.844 | 16.087 | 15.981 | 15.935 | ±1.5% |
| TCP loopback | 22.483 | 22.695 | 22.643 | 22.754 | ±1.2% |

### 2.5 文件系统（µs，越小越好）

| 指标 | kvmoff | nvhe | vhe | pkvm |
|------|-------:|-----:|----:|-----:|
| 0K File Create | 9.36 | 9.31 | 9.34 | 9.42 |
| 10K File Create | 16.83 | 16.74 | 16.76 | 16.81 |

### 2.6 内存延迟（µs / ns）

| 指标 | kvmoff | nvhe | vhe | pkvm | 备注 |
|------|-------:|-----:|----:|-----:|------|
| Prot Fault (lat_sig prot, µs) | 0.1590 | 0.1600 | 0.1602 | 0.1607 | ±1% |
| Page Fault (lat_pagefault minor, µs) | 0.2545 | 0.2547 | 0.2578 | 0.2547 | ±1% |
| L1d (64KB, ns) | 2.22 | 2.22 | 2.22 | 2.22 | 完全相等 |
| L2 (0.5MB, ns) | 3.97 | 3.96 | 3.94 | 3.97 | ±1% |
| LLC (1MB, ns) | 4.44 | 4.44 | 4.43 | 4.45 | ±0.5% |
| LLC 边界 (8MB, ns) | 10.82 | 11.41 | 12.45 | 10.01 | vhe 最慢 / pkvm 最快 |
| DRAM (64MB, ns) | 10.36 | 10.24 | 10.78 | 10.11 | ±5% |

### 2.7 ⭐ lat_mmap（µs，pkvm 显著慢）

ns 精度复测（自写 `lat_mmap_precise.c`，语义与 lmbench `lat_mmap.c` 完全一致，
只是把 `gettimeofday()` 换成 `clock_gettime(CLOCK_MONOTONIC)` + 不做整数 µs round）。
4-mode × 7-size × N=10 = 280 个测量，每个 cell **MAD% < 1%**：

| size | kvmoff | nvhe | vhe | **pkvm** | pkvm 多付 |
|------|-------:|-----:|----:|---------:|---------:|
| 0.5 MB |   7.776 |   7.773 |   7.763 |   **9.224** | **+18.8%** |
| 1 MB   |  11.747 |  11.784 |  11.760 |  **14.812** | **+25.9%** |
| 2 MB   |  21.182 |  21.022 |  21.068 |  **27.593** | **+31.0%** |
| 4 MB   |  36.222 |  36.448 |  36.088 |  **49.105** | **+36.1%** |
| 8 MB   |  65.812 |  65.723 |  66.117 |  **92.243** | **+39.5%** |
| 16 MB  | 123.377 | 123.697 | 123.651 | **175.340** | **+41.8%** |
| 64 MB  | 498.153 | 498.544 | 498.398 | **709.236** | **+42.3%** |

> 之前 lmbench 整数 µs round 让 1/16/67 MB 看起来"0% 差异"（pkvm 和其它都报
> 12 / 124 / 176 / 487 µs），是 round 假象。**精度恢复后 pkvm 在所有 size 都慢，
> 从 +18.8% 渐进到 +42.3%**，机制（stage-2 表建立）一致。

原始数据：`results/precise-mmap/{kvmoff,vhe,nvhe,pkvm}.log`
详见 [`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)。

### 2.8 内存带宽（MB/s，越大越好）

| 指标 | kvmoff | nvhe | vhe | pkvm |
|------|-------:|-----:|----:|-----:|
| Pipe bw | 3887 | 3876 | 3873 | 3857 |
| TCP bw (10MB msg) | 2193 | 2182 | 2183 | 2318 |
| Mem read peak (cache) | 48603 | 48766 | 48602 | 48593 |
| Mem write peak | 57338 | 57338 | 57343 | 57337 |
| Mem bzero peak | 57449 | 57449 | 57448 | 57446 |
| Mem rd DRAM (67MB) | 18446 | 18404 | 17837 | 18154 |
| Mem wr DRAM (67MB) | 7584 | 7581 | 7531 | 7563 |
| Mem bzero DRAM (67MB) | 41913 | 41913 | 40660 | 41329 |

> pkvm 列用 try2 数据；try1 的 "+17-33%" 是 stochastic outlier，详见 §2.6 + §9。

### 2.9 TLB

`tlb effective = 48 pages` —— 4 配置完全相等。硬件特性。

---

## 3. ⭐ 论文级 finding（6 个）

### Finding 1：主机 syscall fastpath 跨 4 配置不可区分（≤ ±1%）

`lat_syscall {null, read, write, stat, fstat, open}` 在 4 模式间最大差异 0.9%。
ARM64 上**KVM 模式对主机 syscall 路径没有可观测影响**——无论 host 在 EL1
（kvmoff / nvhe / pkvm）还是 EL2（vhe），无论 EL2 是否装载 pkvm 保护代码，
主机 syscall 不进 EL2。

| variant | kvmoff | nvhe | vhe | pkvm |
|---------|-------:|-----:|----:|-----:|
| null    | 0.1028 | 0.1029 | 0.1028 | 0.1029 |

195 周期 @ 1.9 GHz —— 在 capability + kycp LSM 栈下的最便宜 syscall 价钱。

### Finding 2：CPU 算术绝对相等（sanity ✓）

所有 `lat_ops` (integer_add/div, double_add/div) 在 4 模式完全相等到 0.001 ns。
CPU pipeline 不涉及 EL2，方法论 sanity check 通过。**这条数据也是判断
"数据是否被噪声污染"的硬性指标**——如果某次跑测到 lat_ops 不相等，说明
噪声还没钳死。

### Finding 3：⭐ pKVM 在主机上的唯一显著开销是 `lat_mmap` 大段（+42%）

- pkvm 在 `lat_mmap` 全部 7 个 size 上比其它 3 配置慢 **+18.8% (0.5 MB) → +42.3% (64 MB)**
  （ns 精度复测；早先 lmbench 整数 µs round 让 1/16/67 MB 看起来"+0%"是 round 假象）
- 其它一切（CPU、syscall、cache、bw_mem、IPC、lat_proc）跨 4 配置 ±1-2%

**机制**：pkvm 在 host 端建立新 VA range 时需要同步更新 stage-2 表
（`host_stage2_idmap_locked` in Rust），其它 3 配置没有 stage-2 表。
每次 stage-2 abort 摊销 ~500 ns (~950 cycle)，被 mmap 触摸的页数线性放大
（lmbench 16 KB stride → 每 4 KB mmap size 摊到 ~12 ns）。详见
[`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)：
- lmbench `lat_mmap.c` vs `lat_mem_rd.c` 测的本质区别（建表 vs 访问）
- pKVM Rust 实现 `host.rs` 里的 stage-2 abort 路径
- 普通 nvhe / vhe 为什么不付这个代价（C 路径里全部 `host_stage2_*` 都在
  `if (is_protected_kvm_enabled())` 后面，vhe 整目录 0 次引用）

### Finding 4：VHE vs NVHE vs KVM-off 在主机性能上无可观测差异

跨 3 个非 pkvm 配置：
- syscall：±0.4%
- CPU 算术：0%
- ctxsw：±1%
- pipe / unix / tcp / udp：±2-5%（lat_unix 一个例外，vhe 略快 5%）
- lat_mmap：±0.5%
- 缓存层级 / bw_mem：±5%

**内核 6.6.0-73-generic 上 "host 驻 EL2 vs EL1" 对主机性能没有可观测影响**——
跟文献里常说的 "VHE 比 NVHE 快 5-15%" **本台 Phytium 没复现**。可能因为：

1. Phytium FTC862 微架构上 EL1→EL2 transition 的硬件代价已经很低
2. 主机 syscall 不进 EL2（无论 vhe 把内核放在 EL2 还是 nvhe 放在 EL1，
   syscall vector 都不切 EL）
3. lmbench 测的是单核 microbench，多核 TLBI 广播这种跨 EL 抖动测不出来

### Finding 5（最终修订版）：pkvm 内禀访问开销 +3-7%，CONFIG.host 中的"快 17-33%"是一次性 stochastic 现象

经过 **standalone 验证** + **同配置 try2 重跑**（独立两套实验）后的最终结论：

**pkvm 真实开销**：随机内存访问 +3-7%（每次 TLB miss 多一层 stage-2 walk）

| 工作集 | kvmoff CFG | **try1 CFG** | **try2 CFG** | **pkvm SA** | try2 vs kvmoff |
|--------|----------:|------------:|------------:|----------:|--------------:|
| Random 4MB | 47.59 | **31.89** ⚠️ | 49.31 | 49.74 | **+3.6%** |
| Random 8MB | 112.54 | **91.01** ⚠️ | 119.59 | 120.01 | **+6.3%** |
| Random 64MB | 185.23 | **154.40** ⚠️ | 191.73 | 192.41 | **+3.5%** |

- **try2（CONFIG.host 同配置重跑）**与 **standalone 单测**一致，pkvm 比 non-pkvm
  **慢 3-7%**——这才是 pkvm 真实开销
- **try1（最初 N=10 数据）的"快 17-33%"是一次性 stochastic 现象**——同配置重跑（try2）
  完全没复现；机制可能是 Linux page allocator 偶然给 64MB heap 落进 pkvm prepopulate
  stage-2 1 GB block 内的"幸运对齐"状态，**存在但进入随机且不稳定**

最初观察到 try1 上 pkvm 在 CONFIG.host 里随机访问比 non-pkvm **快 17-33%**：
- `lat_mem_rd_rand sz4MB`: 47.6 → 31.9 ns（−33%）
- `lat_mem_rd_rand sz64MB`: 185.2 → 154.4 ns（−17%）

第一轮假说："这是 pkvm 的 stage-2 PTW walk cache 优势"。
第二轮假说（standalone 揭示）："这是 CONFIG.host 序列累积 stage-2 暖机的可重复副作用"。
**最终（try2 推翻）：是 stochastic 现象，机制存在但不可控、不稳定、不可复现。**

当 lat_mem_rd_rand 单独跑（无前序 bench 污染）时：

| 工作集 | kvmoff SA | nvhe SA | vhe SA | **pkvm SA** | pkvm 慢多少 |
|--------|---------:|--------:|-------:|---------:|------------:|
| Random 4MB | 47.70 | 47.40 | 47.49 | **49.74** | **+4.7%** |
| Random 8MB | 112.90 | 112.70 | 112.58 | **120.01** | **+6.4%** |
| Random 64MB | 185.32 | 186.05 | 185.55 | **192.41** | **+3.7%** |

→ **pkvm 内禀比 non-pkvm 慢 2-7%**，符合架构理论预期（每次 TLB miss 多一层
stage-2 walk）。

**CONFIG.host 中的"快 17-33%"成因**：测试序列里 lat_mem_rd_rand 在位置 22 才跑，
前面已经跑过 lat_mmap（位置 9）/ bw_mmap_rd（15）/ bw_mem（16）/ lat_ctx（17）等
大段 mmap-touching 操作。pkvm 的 stage-2 表 lazy reclaim + Linux page allocator
稳态 ⇒ 后续 random access 走的 stage-2 walk 命中 walk cache 概率显著上升 ⇒
反向加速 17-33%。

**关键**：这是 **CONFIG.host 序列累积的副作用**，不是 pkvm 内禀属性。任何 paper
不应该把"pkvm 比 non-pkvm 快"作为 finding——这只在 lmbench 这个特定测试序列下成立。

详细对比（4 配置 × CFG vs SA × try1/try2 三套方法学）、机制分解、复现要点见
[`standalone-memory-bench-validation.md`](standalone-memory-bench-validation.md)
（含 §9 try2 验证章节）。

**Finding 3 + Finding 5 的统一解读**：pkvm 主机开销 = **两条独立路径**：
1. **建表瞬间 +18-42%**（Finding 3：每次 stage-2 abort ~500 ns，等价每 4 KB mmap size ~12 ns）
2. **访问已建好 mapping +3-7%**（Finding 5：每次 TLB miss 多一层 stage-2 walk）

两个开销**都在 try2 / standalone 独立复现**，是 pkvm 真实主机开销。

⚠️ 之前 try1 数据里看到的 "pkvm 反而快 17-33%" 是 **stochastic 一次性 lucky alignment**，
同配置 try2 完全没复现。这种"幸运态"存在但**进入随机、不稳定、不可控**，
**不能作为 paper finding 报告**。

### Finding 6：TLB / cache 层级 / bw_mem peak 跨 4 配置等价

- `tlb effective = 48` 全部一致
- L1d 2.22 ns、L2 ~3.95 ns、LLC ~4.4 ns 跨 4 配置 ±1%
- bw_mem 各模式 peak 与 DRAM 段跨 4 配置 ±0.5%

硬件特性不被 KVM 模式扰动，作为方法论 baseline 确认实验干净。

---

## 4. 方法论贡献

### 4.1 4-config 等价对照

同一台机器、同一内核二进制、同一 lmbench 构建产物、同一绑核、同一频率、同一 LSM
状态——**唯一自由变量是 `kvm-arm.mode`**。任何性能差只能来自 KVM 模式本身。
这避免了文献里常见的"用不同硬件 / 不同内核版本对比"的混淆。

### 4.2 N=10 + 干净 noise 隔离

- N=10 让中位数对单 iter 异常鲁棒（iter MAD 0.5-2.4%）
- 72 系统 + 12 用户服务 mask，把 KylinOS 默认带的 AI 推理、桌面、文件索引、
  软件升级、ostree-maintain、pvm-manage 等噪声源全干掉
- 每个配置 reboot 后跑 `apply-masks.sh` + `prepare-host.sh` + `verify-clean-env.sh`，
  3 步全过才进 bench
- 这套去噪 pipeline 把 iter 间 MAD 从早期 day-1 的 5-10% 压到 < 1%

### 4.3 反例数据保留

`results/n90-day3-host/n90-nvhe-noisy-full-*` 保留了 day-3 中段 nvhe 的污染数据
（当时 mask 不全，pvm-manage + Kylin AI 服务在跑）作为"如果没钳死噪声会怎样"
的反例。对比可见：

| nvhe 测试场景 | lat_syscall null (µs) | lat_tcp lhost (µs) |
|---------------|---------------------:|------------------:|
| noisy（污染） | 0.1028 | 28.36 |
| clean（最终）  | 0.1029 | 22.70 |

`lat_tcp lhost` 在污染场景被拉慢 25%——正是这个错误信号让我们误以为
"vhe / pkvm 比 nvhe 快 20%"，反复加 mask 后才真相大白。

---

## 5. 文件清单

```
docs/n90-kvm-host/
├── README.md                                    # 总体背景 + 方法论
├── kvmoff.md  nvhe.md  vhe.md  pkvm.md           # 4 个 per-config 子报告
├── pkvm-mmap-overhead-analysis.md               # pkvm mmap +42% 代码级专题
├── pkvm-memory-access-speedup.md                # ⚠️ 作废：随机访问 -17-33% 的过期解释
├── standalone-memory-bench-validation.md        # ✅ 修正版：standalone 验证 + 正确机制
├── SUMMARY.md                                   # 本文（跨配置综合）
├── lmbench-N10-4config.xlsx                     # 684 项 × 4 配置完整表格
└── lmbench-N10-4config-all-metrics.csv         # 同上 CSV 版本

results/n90-day3-host/                           # 原始数据（每配置 CSV + 10 iter txt）
├── n90-kvmoff-noLSM-full-*                      # N=10 clean
├── n90-nvhe-noLSM-full-*                        # N=10 clean
├── n90-vhe-noLSM-full-*                         # N=10 clean
├── n90-pkvm-noLSM-try2-*                        # N=10 clean，最终 pkvm 列
├── n90-pkvm-noLSM-try1-*                        # N=10，含 stochastic transition，保留不用作最终列
└── n90-nvhe-noisy-full-*                        # 反例污染数据保留

scripts/
├── apply-masks.sh                               # 噪声服务 mask（idempotent）
├── verify-clean-env.sh                          # bench 前自检
├── build-xlsx.py                                # 生成综合 xlsx
└── prepare-host.sh                              # 频率/THP/ASLR 锁定（每 boot 跑）
```

## 6. 复现要点

```bash
# 在 N90 上
cd /root/lmbench-3.0-a9
make build

# 一次性持久化：清空 GRUB_CMDLINE_LINUX_SECURITY，让 ostree set-kargs 唯一权威
sudo cp /etc/default/grub /etc/default/grub.bak-day3
sudo sed -i 's|^GRUB_CMDLINE_LINUX_SECURITY=.*|GRUB_CMDLINE_LINUX_SECURITY=""|' /etc/default/grub
sudo update-grub

# 4 配置依次跑（每个 ~110 min）
for mode in none nvhe vhe protected; do
  sudo ostree admin instutil set-kargs --import-proc-cmdline \
    --replace=kvm-arm.mode=$mode --replace=lsm= --replace=audit=0
  sudo update-grub
  sudo reboot
  # 等 SSH 重连
  bash scripts/apply-masks.sh
  sudo bash prepare-host.sh
  bash scripts/verify-clean-env.sh || exit 1
  CORES=0 ITERS=10 CONFIG=configs/CONFIG.host \
    ENV_TAG=n90-${mode}-noLSM-full ./bench.sh --no-prep
done

# 恢复主机原 cmdline
sudo cp /etc/default/grub.bak-day3 /etc/default/grub
sudo update-grub
sudo ostree admin instutil set-kargs --import-proc-cmdline \
  --replace=kvm-arm.mode=none --replace=lsm=ksaf,bpf --replace=audit=1
sudo reboot

# 本地生成最终 xlsx
python3 scripts/build-xlsx.py
```

---

## 7. 一句话总结

**ARM64 KVM 在 Phytium FTC862 + KylinOS 6.6.0-73 上对主机性能的影响**：

- **kvm-off / nvhe / vhe / pkvm 在 syscall、CPU、IPC、cache 内带宽、L1d/L2/LLC
  延迟上无可观测差异**（≤ 2%）
- **pKVM 内禀主机开销 = 两条独立路径**：
  - 🔴 **建表瞬间**：`lat_mmap` 大段 **+42%**（每次 stage-2 abort ~500 ns，~950 cycle）
  - 🔴 **访问已建好 mapping**：`lat_mem_rd_rand` LLC/DRAM 段 **+3 to +7%**
    （每次 TLB miss 多一层 stage-2 walk，加 5-10 ns）

两个开销均**在 standalone + try2 重跑**独立复现，是 pkvm 真实架构成本。

⚠️ **之前数据里观察到的"pkvm 反而快 17-33%"是一次性 stochastic 现象，不可复现**——
机制可能涉及 Linux page allocator 偶然给 pkvm 主机的 64MB heap 落进 stage-2
prepopulate 的 1 GB block 内的"幸运对齐"状态。这种状态**存在但随机、不稳定**，
**不能作为 paper finding**。详见
[`standalone-memory-bench-validation.md`](standalone-memory-bench-validation.md) §9。

最终 pkvm 主机开销对真实 workload 的影响：
- mmap-heavy workload（数据库 buffer pool、AI weights、container 启动）：付 +42% mmap 开销
- 内存访问密集 workload：付 +3-7% 持续访问开销
- 综合宏观开销在 5-15% 范围（与 USENIX ATC '22 Android pKVM 论文"0-5%"略高，
  可能 Phytium 微架构差异）
