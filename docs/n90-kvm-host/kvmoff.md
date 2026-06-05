# 配置 1 / 4: `kvmoff-noLSM`

> ARM64 KVM 完全关闭（`kvm-arm.mode=none`）。主机内核启动后 KVM 子系统不 init，
> EL2 上不装载任何 hypervisor 代码。主机内核完全跑在 EL1，**这是本系列实验的
> "无虚拟化"基线**。
>
> 总体背景、方法论、跨配置对比口径请见 [`README.md`](README.md)。

**Status**: ✅ N=10 clean（6125 s ≈ 102 min, iter MAD 0.78%）；CSV 6840 行。
本配置数据采集时主机已完整经过 `apply-masks.sh` (72 system + 12 user 服务 mask)
+ `prepare-host.sh` + `verify-clean-env.sh ✓ ALL CLEAN` 的标准流程。

跨配置综合分析见 [`SUMMARY.md`](SUMMARY.md)；pKVM mmap 开销专题见
[`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)；
全部 684 项指标的 4 配置对照见 [`lmbench-N10-4config.xlsx`](lmbench-N10-4config.xlsx)。

---

## 1. 实验环境准备

### 1.1 硬件 / 内核
- 主板：Phytium FTC862（D3000M）
- CPU：8 核，ARMv8.2-A 兼容（支持 VHE / pKVM）
- 内核：`6.6.0-73-generic`（KylinOS V11，ostree 部署 `173a230c...8b.1`）
- KVM 支持：内置（`CONFIG_KVM=y`），含 pKVM (`CONFIG_PKVM_MODULE_PATH=""`)

### 1.2 cmdline 切换到本配置

```bash
sudo ostree admin instutil set-kargs --import-proc-cmdline \
  --replace=kvm-arm.mode=none --replace=lsm= --replace=audit=0
sudo update-grub
sudo reboot
```

### 1.3 启动验证（dmesg 关键行）

```
[    0.060395] CPU: All CPU(s) started at EL2
[    0.187250] kvm [1]: KVM disabled from command line
```

第一行：硬件 firmware 把内核拉起在 EL2（VHE / pKVM 前提）。
第二行：本配置的核心识别——`kvm-arm.mode=none` 被内核早期 cmdline 解析识别，
KVM 子系统**完全不 init**，EL2 vector table 不装载，立即把控制权退到 EL1 继续跑
主机内核。

此后 EL2 永远不被使用，主机内核永远住在 EL1，没有任何 hypervisor 代码存在。

### 1.4 运行时验证（`scripts/verify-clean-env.sh` 全通过）

| 项 | 值 |
|----|----|
| `/sys/kernel/security/lsm` | `capability,kycp` |
| `/sys/fs/box` | 不存在（ksaf 模块未加载） |
| `dmesg | grep KVM` | `KVM disabled from command line` |
| `lsmod | grep kvm` | 空 |
| `/sys/kernel/mm/transparent_hugepage/enabled` | `[never]` |
| `/proc/sys/kernel/randomize_va_space` | `0` |
| cpu0 频率 | `1900000 kHz`, governor `performance` |
| 噪声进程白名单外 | 0 |

### 1.5 主机噪声抑制

执行 `scripts/apply-masks.sh`：72 项系统级 + 12 项用户级守护进程
`systemctl mask`，默认 target `multi-user.target`，GUI 不启动。详见
[`README.md` §4.8](README.md)。

---

## 2. 实验配置

### 2.1 lmbench config: `configs/CONFIG.host`

全套 `BENCHMARK_*=YES`，工作集 `MB=64`，`ENOUGH=10000` µs。

### 2.2 bench.sh 入参

```bash
CORES=0 ITERS=10 \
  CONFIG=configs/CONFIG.host \
  ENV_TAG=n90-kvmoff-noLSM-full \
  ./bench.sh --no-prep
```

### 2.3 输出文件

```
results/n90-day3/n90-kvmoff-noLSM-full-cpu0.csv             # 6840 行
results/n90-day3/n90-kvmoff-noLSM-full-cpu0-iter{1..10}.txt # raw
results/n90-day3/n90-kvmoff-noLSM-full-20260604-001149-summary.txt
results/n90-day3/n90-kvmoff-noLSM-full-cpu0-parse.err       # 无害 'version' 工具告警
```

---

## 3. 实施 / 执行

### 3.1 iter 时长

| iter | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|------|---|---|---|---|---|---|---|---|---|----|
| 秒   | 613 | 610 | 620 | 611 | 611 | 615 | 613 | 612 | 624 | 616 |

总 wall time 102 min，iter MAD = 0.78%（max−min = 14 s / 614）。

### 3.2 烟测

`CONFIG.test ITERS=1` = 225 s，`lat_syscall null = 0.1029 µs, read = 0.1640 µs`，
与 N=10 CONFIG.host 中位（0.1028 / 0.1639）一致，**无暖机**。

---

## 4. 结果（N=10 中位 ± MAD%）

### 4.1 lat_syscall

| variant | 中位 (µs) | MAD% | 周期 @1.9 GHz |
|---------|---------:|-----:|--------------:|
| null    | 0.1028 | 0.00 | ~195 |
| write   | 0.1400 | 0.32 | ~266 |
| read    | 0.1639 | 0.09 | ~311 |
| fstat   | 0.2290 | 0.31 | ~435 |
| stat    | 0.9554 | 0.39 | ~1815 |
| open    | 1.4952 | 0.11 | ~2841 |

### 4.2 lat_sig

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| install | 0.1447 | 0.17 |
| prot    | 0.1590 | 0.82 |

### 4.3 lat_proc

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| fork    | 136.19 | 0.19 |
| exec    | 377.31 | 0.52 |
| shell   | 796.71 | 0.23 |

### 4.4 lat_pagefault

minor = 0.2545 µs（MAD 0.29%）。

### 4.5 lat_ctx（4 代表样本）

| 工作集 / 进程数 | (µs) | MAD% |
|----------------|-----:|-----:|
| 0 KB / 2  | 2.370 | 1.27 |
| 16 KB / 2 | 2.365 | 2.75 |
| 16 KB / 8 | 5.865 | 0.26 |
| 16 KB / 16 | 5.985 | 0.33 |

### 4.6 IPC

| 类型 | 中位 (µs) | MAD% |
|------|---------:|-----:|
| `lat_pipe rt`   |  5.586 | 1.44 |
| `lat_unix rt`   | 10.388 | 3.06 |
| `lat_tcp lhost` | 22.483 | 0.26 |
| `lat_udp lhost` | 15.844 | 0.24 |

### 4.7 lat_mmap（ns 精度复测）

| size | 中位 (µs) | MAD% |
|------|---------:|-----:|
| 0.5 MB |   7.776 | 0.20 |
| 1 MB   |  11.747 | 0.43 |
| 2 MB   |  21.182 | 0.20 |
| 4 MB   |  36.222 | 0.75 |
| 8 MB   |  65.812 | 0.07 |
| 16 MB  | 123.377 | 0.09 |
| 64 MB  | 498.153 | 0.10 |

### 4.8 lat_mem_rd_load 缓存层级（stride 256 B）

| 工作集 | 延迟 (ns) | 段 |
|--------|----------:|----|
| 64 KB | 2.22 | L1d hit (~4 cycle) |
| 0.5 MB | 3.97 | L1 → L2 |
| 1 MB | 4.44 | L2 内 |
| 8 MB | 10.82 | LLC 边界 |
| 64 MB | 10.36 | DRAM（prefetch-aware） |

### 4.9 bw_mem peak / DRAM

| 指标 | peak (MB/s) | DRAM 67 MB (MB/s) |
|------|------------:|------------------:|
| `bw_mem_rd` | 48603 | 18446 |
| `bw_mem_wr` | 57338 |  7584 |
| `bw_mem_bzero` | 57449 | 41913 |
| `bw_mem_cp` | 28669 | — |

### 4.10 lat_ops（CPU 算术）

| variant | 中位 (ns) | MAD% |
|---------|---------:|-----:|
| integer_add | 0.280 | 0.00 |
| integer_div | 4.450 | 0.00 |
| double_add | 1.110 | 0.00 |
| double_div | 6.670 | 0.00 |

10 iter 完全一致——硬件 baseline 锁死。

### 4.11 TLB

`tlb effective = 48 pages`（MAD 0%）。硬件特性。

---

## 5. 本配置的内在特征

1. **MAD% 几乎全部 ≤ 0.5%**（少数 lat_unix / lat_pipe / lat_sig 在 1-3% 范围，
   属 IPC 类正常方差）。**干净环境 + iter 间高一致性**。
2. **null syscall = 195 周期**：KylinOS 6.6.0-73-generic 在 `capability,kycp` LSM
   栈下、主机纯 EL1 模式的最便宜 syscall 价钱。
3. **lat_ops 与其它 3 配置完全相等**：CPU pipeline 不经过 EL2，与 KVM 模式无关。
4. **lat_mmap 64 MB = 498.15 µs**（ns 精度）：作为对照，pkvm 同 size = 709.24 µs（**+42.3%**）。
   差异机制详见 [`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)。

跨 4 配置对比见 [`SUMMARY.md`](SUMMARY.md)。
