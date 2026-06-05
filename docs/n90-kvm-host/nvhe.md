# 配置 2 / 4: `nvhe-noLSM`

> ARM64 KVM 以 NVHE（non-VHE）模式启用：主机内核仍在 **EL1**，EL2 上装载一个最小
> hypervisor 切换桩（hyp stub）。本场景没有客户机在跑，所以 EL2 stub 空载。
> 这是 ARM 早期 KVM 设计（pre-VHE）的兼容模式。
>
> 总体背景、方法论、跨配置对比口径请见 [`README.md`](README.md)。

**Status**: ✅ N=10 clean（6128 s ≈ 102 min, iter MAD 0.49%）；CSV 6840 行。
本配置数据采集时已完整经过 `apply-masks.sh` + `prepare-host.sh` + `verify-clean-env.sh
✓ ALL CLEAN`。**注：先前 day-3 早期还有一份 N=10 数据存在 `n90-nvhe-noisy-full-*`
（因为采集时 mask 不全有污染），保留作为对照不进 SUMMARY。**

跨配置综合分析见 [`SUMMARY.md`](SUMMARY.md)；
全部 684 项指标的 4 配置对照见 [`lmbench-N10-4config.xlsx`](lmbench-N10-4config.xlsx)。

---

## 1. 实验环境准备

### 1.1 硬件 / 内核
同 [`README.md`](README.md) §4。

### 1.2 cmdline 切换

```bash
sudo ostree admin instutil set-kargs --import-proc-cmdline \
  --replace=kvm-arm.mode=nvhe --replace=lsm= --replace=audit=0
sudo update-grub
sudo reboot
```

### 1.3 启动验证（dmesg 关键行）

```
[    0.060396] CPU: All CPU(s) started at EL2
[    0.194484] kvm [1]: nv: 477 coarse grained trap handlers
[    0.194539] kvm [1]: IPA Size Limit: 40 bits
[    0.195451] kvm [1]: GIC system register CPU interface enabled
[    0.195574] kvm [1]: Hyp mode initialized successfully
```

**`Hyp mode initialized successfully`** 是本配置的核心识别——对比 VHE 的
`VHE mode initialized successfully`、pKVM 的 `Protected nVHE mode initialized successfully`。

NVHE 路径里：硬件把内核拉起在 EL2，KVM 探测 `kvm-arm.mode=nvhe` 后**把内核回退
到 EL1**，留一个最小切换桩在 EL2。没有客户机时 EL2 stub 完全空闲，主机所有 syscall
落在 EL1 vector，**不进 EL2**。

### 1.4 运行时验证（`verify-clean-env.sh` 全通过）

| 项 | 值 |
|----|----|
| `/sys/kernel/security/lsm` | `capability,kycp` |
| `/sys/fs/box` | 不存在 |
| 主机 KVM 模式 | NVHE（dmesg 确认） |
| THP / ASLR | never / 0 |
| cpu0 频率 | 1900 MHz, performance |
| 噪声进程白名单外 | 0 |

---

## 2. 实验配置

同 kvmoff.md §2：`CONFIG.host` 全套，`CORES=0 ITERS=10`。

```bash
CORES=0 ITERS=10 \
  CONFIG=configs/CONFIG.host \
  ENV_TAG=n90-nvhe-noLSM-full \
  ./bench.sh --no-prep
```

---

## 3. 实施 / 执行

### 3.1 iter 时长

| iter | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|------|---|---|---|---|---|---|---|---|---|----|
| 秒   | 611 | 607 | 613 | 618 | 613 | 611 | 613 | 618 | 608 | 615 |

总 wall 102 min，iter MAD = 0.49%（max−min = 11 s / 613）。**比 kvmoff（MAD 0.78%）
更稳**。

### 3.2 烟测

`CONFIG.test ITERS=1` = 223 s，`lat_syscall null = 0.1029, read = 0.1632 µs`，
与 N=10 CONFIG.host 中位（0.1029 / 0.1629）一致，**无暖机**。

---

## 4. 结果（N=10 中位 ± MAD%）

### 4.1 lat_syscall

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| null    | 0.1029 | 0.05 |
| write   | 0.1396 | 0.04 |
| read    | 0.1629 | 0.03 |
| fstat   | 0.2274 | 0.66 |
| stat    | 0.9536 | 0.19 |
| open    | 1.4898 | 0.13 |

### 4.2 lat_sig

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| install | 0.1446 | 0.07 |
| prot    | 0.1600 | 0.91 |

### 4.3 lat_proc

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| fork    | 136.48 | 0.36 |
| exec    | 375.74 | 0.18 |
| shell   | 792.79 | 0.24 |

### 4.4 lat_pagefault

minor = 0.2547 µs（MAD 0.22%）。

### 4.5 lat_ctx

| 工作集 / 进程数 | (µs) | MAD% |
|----------------|-----:|-----:|
| 0 KB / 2  | 2.380 | 1.26 |
| 16 KB / 2 | 2.380 | 2.31 |
| 16 KB / 8 | 5.860 | 0.85 |
| 16 KB / 16 | 6.000 | 0.42 |

### 4.6 IPC

| 类型 | 中位 (µs) | MAD% |
|------|---------:|-----:|
| `lat_pipe rt`   |  5.595 | 1.99 |
| `lat_unix rt`   |  9.974 | 2.98 |
| `lat_tcp lhost` | 22.695 | 1.01 |
| `lat_udp lhost` | 16.087 | 0.56 |

### 4.7 lat_mmap（ns 精度复测）

| size | 中位 (µs) | MAD% |
|------|---------:|-----:|
| 0.5 MB |   7.773 | 0.28 |
| 1 MB   |  11.784 | 0.28 |
| 2 MB   |  21.022 | 0.25 |
| 4 MB   |  36.448 | 0.30 |
| 8 MB   |  65.723 | 0.15 |
| 16 MB  | 123.697 | 0.07 |
| 64 MB  | 498.544 | 0.07 |

### 4.8 lat_mem_rd_load 缓存层级

| 工作集 | 延迟 (ns) | MAD% |
|--------|----------:|-----:|
| 64 KB | 2.22 | 0.00 |
| 0.5 MB | 3.96 | 0.49 |
| 1 MB | 4.44 | 0.08 |
| 8 MB | 11.41 | 9.37 |
| 64 MB | 10.24 | 1.82 |

### 4.9 bw_mem

| 指标 | peak (MB/s) | DRAM 67 MB (MB/s) |
|------|------------:|------------------:|
| `bw_mem_rd`    | 48766 | 18404 |
| `bw_mem_wr`    | 57338 |  7581 |
| `bw_mem_bzero` | 57449 | 41913 |

### 4.10 lat_ops

`integer_add 0.280` / `integer_div 4.450` / `double_add 1.110` / `double_div 6.670` ns，
MAD 0%。

### 4.11 TLB

`tlb effective = 48`，MAD 0%。

---

## 5. 本配置的内在特征

1. **MAD% 极低**（多数 < 0.3%，IPC 类 1-3%），干净环境
2. **null syscall = 0.1029 µs** ≈ kvmoff。**主机内核在 EL1 时无论 KVM 是否启用
   hyp stub 都一样**——nvhe 与 kvmoff 的 syscall fastpath 不可区分
3. **lat_mmap 64 MB = 498.54 µs**（ns 精度），与 kvmoff 498.15 µs 一致到 ±0.08%。
   **普通 nvhe 不维护 host stage-2 表**，所以 mmap 走纯 Linux 路径，跟 kvmoff 等价
4. **EL2 hyp stub 完全空载**：本配置没起客户机，nvhe 的 EL2 stub 只是装着，
   不参与 host 任何路径

跨 4 配置对比见 [`SUMMARY.md`](SUMMARY.md)。
