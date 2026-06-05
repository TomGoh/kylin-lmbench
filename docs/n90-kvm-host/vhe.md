# 配置 3 / 4: `vhe-noLSM`

> ARM64 KVM 以 VHE（Virtualization Host Extensions）模式启用：主机 Linux 内核
> **直接住在 EL2**（`HCR_EL2.E2H = 1`），同时复用 EL2 的页表 / 异常向量，
> syscall 从 EL0 直接进 EL2 而不是 EL1。EL2 上**没有**客户机在跑，
> 但 VHE 重新映射了 EL2 / EL1 系统寄存器使主机内核透明地用 EL2 资源。
>
> 总体背景、方法论、跨配置对比口径请见 [`README.md`](README.md)。

**Status**: ✅ N=10 clean（6140 s ≈ 102 min, iter MAD 0.65%）；CSV 6840 行。
本配置数据采集时已完整经过 `apply-masks.sh` + `prepare-host.sh` + `verify-clean-env.sh
✓ ALL CLEAN`。

跨配置综合分析见 [`SUMMARY.md`](SUMMARY.md)；
全部 684 项指标的 4 配置对照见 [`lmbench-N10-4config.xlsx`](lmbench-N10-4config.xlsx)。

---

## 1. 实验环境准备

### 1.1 硬件 / 内核
同 [`README.md`](README.md) §4。

### 1.2 cmdline 切换

```bash
sudo ostree admin instutil set-kargs --import-proc-cmdline \
  --replace=kvm-arm.mode=vhe --replace=lsm= --replace=audit=0
sudo update-grub
sudo reboot
```

### 1.3 启动验证（dmesg 关键行）

```
[    0.060395] CPU: All CPU(s) started at EL2
[    0.181033] kvm [1]: nv: 477 coarse grained trap handlers
[    0.181086] kvm [1]: IPA Size Limit: 40 bits
[    0.181270] kvm [1]: GIC system register CPU interface enabled
[    0.181388] kvm [1]: VHE mode initialized successfully
```

**`VHE mode initialized successfully`** 是本配置的核心识别。
KVM 探测 `kvm-arm.mode=vhe` 后，**保持主机内核在 EL2**（`HCR_EL2.E2H = 1`），
同时把 EL2 system register set 重映射成对主机透明的 EL1 接口——主机内核
仍然看到的是 `TTBR0_EL1`/`TTBR1_EL1` 等寄存器名，但底层硬件操作的是 EL2 的资源。

syscall 路径：EL0 → EL2 vector（而不是 EL1 vector）。架构上少一级 transition
（host 已经在 EL2，不存在 EL1 → EL2 切换）。

### 1.4 运行时验证（`verify-clean-env.sh` 全通过）

| 项 | 值 |
|----|----|
| `/sys/kernel/security/lsm` | `capability,kycp` |
| `dmesg \| grep VHE` | `VHE mode initialized successfully` |
| THP / ASLR | never / 0 |
| cpu0 频率 | 1900 MHz, performance |
| 噪声进程白名单外 | 0 |

注：dmesg 最早期会出现一条 `Malformed early option 'kvm-arm.mode'`——是因为
cmdline 里 `kvm-arm.mode` 因 grub-mkconfig 多次追加 `GRUB_CMDLINE_LINUX_DEFAULT`
出现 5 次。早期解析投诉，后续正式解析仍读到 `vhe`，VHE 正确启用。

---

## 2. 实验配置

同 kvmoff.md §2。`ENV_TAG=n90-vhe-noLSM-full`。

---

## 3. 实施 / 执行

### 3.1 iter 时长

| iter | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|------|---|---|---|---|---|---|---|---|---|----|
| 秒   | 619 | 621 | 607 | 613 | 612 | 606 | 620 | 614 | 615 | 615 |

总 wall 102 min，iter MAD = 0.65%（max−min = 15 s / 614）。

### 3.2 烟测

`CONFIG.test ITERS=1` = 222 s，`lat_syscall null = 0.1029, read = 0.1640 µs`，
与 N=10 中位（0.1028 / 0.1640）一致。**无暖机**。

### 3.3 单 iter 异常

iter 3（607 s，比 mean 偏快 1.2%）在 IPC 类指标上有几个 +8-14% 单值偏差
（`lat_unix rt i3 = 10.89` vs median 9.86；`bw_tcp i3 = 2039` vs 2380）。10 iter
中位数自动吸收，不影响最终数字。

---

## 4. 结果（N=10 中位 ± MAD%）

### 4.1 lat_syscall

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| null    | 0.1028 | 0.00 |
| write   | 0.1396 | 0.07 |
| read    | 0.1640 | 0.15 |
| fstat   | 0.2284 | 0.15 |
| stat    | 0.9525 | 0.14 |
| open    | 1.4912 | 0.13 |

### 4.2 lat_sig

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| install | 0.1451 | 0.34 |
| prot    | 0.1602 | 1.81 |

### 4.3 lat_proc

| variant | 中位 (µs) | MAD% |
|---------|---------:|-----:|
| fork    | 136.55 | 0.43 |
| exec    | 377.00 | 0.25 |
| shell   | 791.29 | 0.31 |

### 4.4 lat_pagefault

minor = 0.2578 µs（MAD 0.21%）。

### 4.5 lat_ctx

| 工作集 / 进程数 | (µs) | MAD% |
|----------------|-----:|-----:|
| 0 KB / 2  | 2.390 | 1.05 |
| 16 KB / 2 | 2.370 | 2.74 |
| 16 KB / 8 | 5.850 | 0.77 |
| 16 KB / 16 | 6.025 | 0.33 |

### 4.6 IPC

| 类型 | 中位 (µs) | MAD% |
|------|---------:|-----:|
| `lat_pipe rt`   |  5.615 | 1.32 |
| `lat_unix rt`   |  9.861 | 2.06 |
| `lat_tcp lhost` | 22.643 | 0.79 |
| `lat_udp lhost` | 15.981 | 0.96 |

### 4.7 lat_mmap（ns 精度复测）

| size | 中位 (µs) | MAD% |
|------|---------:|-----:|
| 0.5 MB |   7.763 | 0.29 |
| 1 MB   |  11.760 | 0.31 |
| 2 MB   |  21.068 | 0.34 |
| 4 MB   |  36.088 | 0.45 |
| 8 MB   |  66.117 | 0.25 |
| 16 MB  | 123.651 | 0.07 |
| 64 MB  | 498.398 | 0.05 |

### 4.8 lat_mem_rd_load 缓存层级

| 工作集 | 延迟 (ns) | MAD% |
|--------|----------:|-----:|
| 64 KB | 2.22 | 0.00 |
| 0.5 MB | 3.94 | 0.18 |
| 1 MB | 4.43 | 0.09 |
| 8 MB | 12.45 | 1.44 |
| 64 MB | 10.78 | 3.16 |

### 4.9 bw_mem

| 指标 | peak (MB/s) | DRAM 67 MB (MB/s) |
|------|------------:|------------------:|
| `bw_mem_rd`    | 48602 | 17837 |
| `bw_mem_wr`    | 57343 |  7531 |
| `bw_mem_bzero` | 57448 | 40660 |

### 4.10 lat_ops

`integer_add 0.280 / integer_div 4.450 / double_add 1.110 / double_div 6.670` ns，
MAD 0%。

### 4.11 TLB

`tlb effective = 48`，MAD 0%。

---

## 5. 本配置的内在特征

1. **MAD% < 0.5% 大部分项**，干净环境采集。
2. **null syscall = 0.1028 µs**：与 kvmoff、nvhe、pkvm 三者完全相等。**主机在
   EL2 vs EL1 在 Phytium 6.6.0-73 上对 syscall fastpath 无可测影响**——这跟
   ARM 文档/早期文献说的"VHE 比 NVHE 快"在本台机器上**没复现**。
3. **lat_mmap 64 MB = 498.40 µs**（ns 精度）：与 kvmoff 498.15 / nvhe 498.54 一致到 ±0.08%。
   VHE 没有 host stage-2 表（`arch/arm64/kvm/hyp/vhe/` 整目录 0 个 `host_stage2` 引用），
   mmap 走纯 Linux 路径。详见 [`pkvm-mmap-overhead-analysis.md`](pkvm-mmap-overhead-analysis.md)。
4. **lat_mem_rd 8 MB = 12.45 ns**：在 LLC 边界 vhe 单点比其它配置高 1-2 ns，
   MAD% 1.44% 在噪声范围，可能是单 iter 抖动。

跨 4 配置对比见 [`SUMMARY.md`](SUMMARY.md)。
