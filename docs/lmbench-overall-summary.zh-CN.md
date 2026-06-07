# lmbench 性能实验总览

本文汇总当前仓库中已经收集到的 lmbench 数据，并给出经过本地结果文件复核后的分析结论。实验围绕三类环境展开：

1. N90 主机侧测试：在同一台 Phytium N90 上切换 `kvm-arm.mode=none/vhe/nvhe/protected`，测试主机自身的 lmbench 表现。
2. N90 客户机侧测试：在 N90 的 NVHE 和 pKVM 环境下运行 `~/x-kernel` 客户机，并在客户机内运行 lmbench。仓库中也保留了一组 VHE 客户机结果，主要作为参考。
3. 其他机密虚拟化环境：在鲲鹏服务器上对比普通虚拟机和 VirtCCA 机密虚拟机；在海光服务器上已经收集到 CSV 机密虚拟机数据，普通虚拟机测试仍在运行。

本次整理重点解决两个问题：第一，核验总览文档中的关键数字是否能从现有结果文件复算出来；第二，把分析表述改成准确、书面、可读的中文，避免把尚未验证的推断写成定论。

## 1. 数据核验口径

本次核验使用仓库中的实际结果文件和解析脚本。

| 数据集 | 数据来源 | 核验方式 | 备注 |
|---|---|---|---|
| N90 主机 4 模式 | `results/n90-day3-host/*.csv`，`results/precise-mmap/*.log` | 直接复算 CSV 中位数；用 `scripts/analyze-precise-mmap.py` 复核 mmap 精测结果 | 这是本仓库中最完整、最干净的数据集 |
| N90 x-kernel 客户机 | `results/xkernel-n90-*/xkernel-*-iter*.txt` | 用 `parse-lmbench.py` 重新解析原始日志，再复算中位数 | 结论主要看 NVHE 与 pKVM；VHE 结果保留为参考 |
| 鲲鹏 VirtCCA | `results/virtcca-regular-results/`，`results/virtcca-cvm-results/` | 用 `parse-lmbench.py` 重新解析原始日志，再复算中位数 | 普通虚拟机与 VirtCCA 机密虚拟机都有 10 轮数据 |
| 海光 CSV | `results/hygon_csv_results/` | 用 `parse-lmbench.py` 重新解析原始日志，复算 CSV 机密虚拟机的绝对值 | 目前缺少普通虚拟机基线，不能计算 CSV 开销 |

需要注意：

1. 客户机原始日志中有一些非 lmbench 输出，例如 `lat_rpc` 在 musl 环境下被跳过、`lat_http` 缺少 `webpage-lm`、附加 DMA 测试输出等。这些内容没有纳入本文的核心结论。

2. 海光 CSV 日志中出现了 `vfork: Function not implemented` 和端口绑定冲突等信息。因此海光部分当前只报告解析器能够稳定提取的 lmbench 指标，不做机制归因。

## 2. 总体结论

| 实验对象 | 已核验结论 | 可信度 |
|---|---|---|
| N90 主机侧 `kvm-arm.mode` 对照 | `none/vhe/nvhe/protected` 对主机 syscall、IPC、STREAM、TLB 的影响很小；pKVM 在主机侧最明显的额外成本出现在 `lat_mmap`，64 MB 精测慢约 42% | 高 |
| N90 x-kernel 客户机 NVHE 与 pKVM 对照 | 丢弃第 1 轮后，pKVM 相对 NVHE 的主要稳定差异是 minor page fault 约 +5%；syscall、IPC、STREAM、随机内存访问和 TLB 基本持平 | 中高 |
| 鲲鹏 VirtCCA 与普通虚拟机对照 | VirtCCA 对 STREAM 读写混合带宽、IPC 延迟和大工作集随机访问影响显著；纯 syscall 和纯读 `stream2 sum` 基本不变 | 高 |
| 海光 CSV | 已有 CSV 机密虚拟机的 10 轮绝对数据，但还没有普通虚拟机基线，不能评价 CSV 相对开销 | 待补基线 |

最重要的分析边界是：不能把所有 pKVM 结果合并成一句“pKVM 只有 page fault 开销”。在 N90 主机侧，pKVM 的显著信号是 `lat_mmap` 建立映射慢；在 N90 x-kernel 客户机侧，显著信号是 minor page fault 慢约 5%。这两者都和页表或内存映射建立有关，但测试对象不同，不能混写。

## 3. N90 主机侧测试

### 3.1 实验设置

N90 主机侧测试只改变 `kvm-arm.mode`，其余条件保持一致：同一台 Phytium FTC862 机器、同一内核构建、CPU 锁定 1.9 GHz、关闭 THP 和 ASLR、使用 `taskset -c 0` 绑核、关闭主要后台服务，并保持 LSM 栈为 `capability,kycp`。

| 标签 | `kvm-arm.mode` | 含义 |
|---|---|---|
| `kvmoff` | `none` | KVM 关闭，主机作为裸机基线 |
| `vhe` | `vhe` | 主机内核运行在 VHE 模式 |
| `nvhe` | `nvhe` | 主机运行在 NVHE 模式 |
| `pkvm` | `protected` | pKVM 开启后的主机 |

相关脚本和配置包括 [bench.sh](../bench.sh)、[prepare-host.sh](../prepare-host.sh)、[scripts/apply-masks.sh](../scripts/apply-masks.sh)、[scripts/verify-clean-env.sh](../scripts/verify-clean-env.sh)、[configs/CONFIG.host](../configs/CONFIG.host)。

### 3.2 关键结果

下表为 10 轮中位数。

| 指标 | 单位 | kvmoff | VHE | NVHE | pKVM |
|---|---:|---:|---:|---:|---:|
| null syscall | us | 0.1028 | 0.1028 | 0.1029 | 0.1028 |
| minor page fault | us | 0.2545 | 0.2578 | 0.2547 | 0.2599 |
| fork | us | 136.19 | 136.55 | 136.48 | 139.07 |
| pipe latency | us | 5.586 | 5.615 | 5.595 | 5.544 |
| TCP loopback latency | us | 22.483 | 22.643 | 22.695 | 22.655 |
| STREAM copy | MB/s | 14334.51 | 14358.63 | 14336.91 | 14355.00 |
| STREAM triad | MB/s | 18641.91 | 18612.76 | 18639.19 | 18609.40 |
| random read, 64 MB | ns | 185.23 | 185.43 | 185.05 | 191.73 |
| TLB effective | pages | 48 | 48 | 48 | 48 |

这些结果支持两个结论。

第一，主机侧 syscall、IPC、STREAM、TLB 容量在四种模式下基本持平。也就是说，在这组受控条件下，`kvm-arm.mode` 的选择不会显著改变主机常规快速路径。

第二，pKVM 主机侧的随机内存访问有小幅变慢，64 MB 随机访问约为 191.73 ns，而非 pKVM 模式约为 185 ns。这符合 pKVM 多一层 stage-2 地址转换的预期，但幅度远小于 mmap 建表开销。

### 3.3 pKVM 的主机侧 mmap 开销

原始 lmbench 的 `lat_mmap` 使用微秒整数输出，较大的 size 会掩盖小数部分。仓库中新增了 [src/lat_mmap_precise.c](../src/lat_mmap_precise.c)，保持 `lat_mmap` 的语义不变，只把计时和输出改为纳秒精度。复核 `results/precise-mmap/*.log` 后得到：

| mmap size | kvmoff | VHE | NVHE | pKVM | pKVM 相对 VHE |
|---|---:|---:|---:|---:|---:|
| 0.5 MB | 7.776 us | 7.763 us | 7.773 us | 9.224 us | +18.8% |
| 1 MB | 11.747 us | 11.760 us | 11.784 us | 14.812 us | +25.9% |
| 2 MB | 21.182 us | 21.068 us | 21.022 us | 27.593 us | +31.0% |
| 4 MB | 36.222 us | 36.088 us | 36.448 us | 49.105 us | +36.1% |
| 8 MB | 65.812 us | 66.117 us | 65.723 us | 92.243 us | +39.5% |
| 16 MB | 123.377 us | 123.651 us | 123.697 us | 175.340 us | +41.8% |
| 64 MB | 498.153 us | 498.398 us | 498.544 us | 709.236 us | +42.3% |

这个结果是 N90 主机侧最明确的 pKVM 信号。

从 lmbench 测试代码看，`lat_mmap` 的计时区包含 `mmap`、按 16 KB 步长触摸映射区域、再 `munmap`。这会反复触发新映射建立和首次访问。相比之下，`lat_mem_rd` 在初始化阶段已经建立并触摸工作集，计时区主要是指针追逐式 load。因此两者测到的不是同一种成本：`lat_mmap` 更接近“建映射”的成本，`lat_mem_rd` 更接近“映射建立后的访问”成本。pKVM 在前者上明显变慢，而在后者上只小幅变慢，这个解释与代码路径和数据都一致。

## 4. N90 x-kernel 客户机测试

### 4.1 数据说明

N90 客户机侧使用 `~/x-kernel` 作为客户机内核，在客户机内部运行 lmbench。当前仓库中保留了三组原始日志：

| 目录 | 含义 | 本文用途 |
|---|---|---|
| `results/xkernel-n90-kvm-vhe-20260605-201819/` | VHE host 上的普通客户机 | 参考数据 |
| `results/xkernel-n90-kvm-nvhe-20260606-133103/` | NVHE host 上的普通客户机 | 作为 pKVM 对照基线 |
| `results/xkernel-n90-pkvm-np-clean-20260606-164648/` | pKVM host 上的 x-kernel 客户机 | 与 NVHE 对比 |

客户机侧配置来自结果目录中的 `CONFIG.xkernel.used`。它使用 `OS=aarch64-linux-musl`，`FILE=/root/lmb_file`，`FSDIR=/root/lmb_fs`，并关闭 `BENCHMARK_RPC`。由于客户机环境是 musl 静态构建，RPC 相关数字不参与分析。

下表使用第 2 到第 10 轮的中位数。这样处理是必要的：pKVM 的 `lat_pagefault` 第 1 轮明显偏慢，如果 10 轮全算，中位数和 MAD 会被暖机影响。丢弃第 1 轮后，数据与“稳定运行阶段”的表现更一致。

### 4.2 关键结果

| 指标 | 单位 | VHE | NVHE | pKVM | pKVM 相对 NVHE |
|---|---:|---:|---:|---:|---:|
| null syscall | us | 1.6762 | 1.6766 | 1.6763 | -0.02% |
| stat syscall | us | 5.7311 | 5.7379 | 5.7424 | +0.08% |
| signal install | us | 1.9483 | 1.9489 | 1.9490 | +0.01% |
| minor page fault | us | 76.0489 | 77.8799 | 81.7860 | +5.02% |
| fork | us | 4990.0 | 4990.0 | 4990.0 | 0.00% |
| shell | us | 10001.5 | 10024.0 | 14955.5 | +49.20% |
| ctx 16p/16K | us | 7.590 | 7.640 | 7.680 | +0.52% |
| ctx 96p/64K | us | 15.250 | 15.410 | 15.280 | -0.84% |
| pipe latency | us | 20.0366 | 20.0752 | 20.1351 | +0.30% |
| TCP loopback latency | us | 109.5330 | 111.3358 | 110.7185 | -0.55% |
| STREAM copy | MB/s | 18146.76 | 18532.99 | 18480.01 | -0.29% |
| STREAM triad | MB/s | 17314.45 | 17187.36 | 17400.76 | +1.24% |
| stream2 sum | MB/s | 7173.88 | 7170.87 | 7163.04 | -0.11% |
| random read, 64 MB | ns | 193.049 | 192.027 | 192.355 | +0.17% |
| TLB effective | pages | 48 | 48 | 48 | 0.00% |

稳定指标显示，pKVM 相对 NVHE 的主要差异是 minor page fault 约 +5%。syscall、IPC、STREAM、随机内存访问和 TLB 容量都基本持平。

`shell` 这一项不适合作为 pKVM 开销的主要证据。它在 pKVM 下明显偏慢，但 fork/shell 类指标容易出现分桶分布，受调度时机影响较大。本文保留该数字，但不把它作为核心结论。

## 5. 鲲鹏 VirtCCA 测试

### 5.1 数据说明

鲲鹏服务器上有两组客户机数据：

| 目录 | 含义 |
|---|---|
| `results/virtcca-regular-results/` | 普通虚拟机 |
| `results/virtcca-cvm-results/` | VirtCCA 机密虚拟机 |

两组数据都包含 10 轮原始日志，并可由 `parse-lmbench.py` 稳定解析。下表为 10 轮中位数。

### 5.2 关键结果

| 指标 | 单位 | 普通虚拟机 | VirtCCA | VirtCCA 相对普通虚拟机 |
|---|---:|---:|---:|---:|
| null syscall | us | 1.3178 | 1.3496 | +2.41% |
| read syscall | us | 2.9725 | 2.9832 | +0.36% |
| stat syscall | us | 4.7871 | 4.8060 | +0.40% |
| minor page fault | us | 48.6556 | 57.4806 | +18.14% |
| fork | us | 6835.0 | 5237.5 | -23.37% |
| shell | us | 10318.5 | 18990.0 | +84.04% |
| pipe latency | us | 23.3360 | 27.4900 | +17.80% |
| AF_UNIX latency | us | 60.1634 | 71.5307 | +18.89% |
| UDP loopback latency | us | 246.7185 | 362.0249 | +46.74% |
| TCP loopback latency | us | 280.7485 | 391.8587 | +39.58% |
| pipe bandwidth | MB/s | 2988.83 | 2624.69 | -12.18% |
| AF_UNIX bandwidth | MB/s | 2657.89 | 2419.52 | -8.97% |
| STREAM copy | MB/s | 42288.08 | 19841.89 | -53.08% |
| STREAM triad | MB/s | 40829.34 | 18188.92 | -55.45% |
| stream2 fill | MB/s | 22339.54 | 20022.78 | -10.37% |
| stream2 sum | MB/s | 11554.43 | 11455.68 | -0.85% |
| random read, 4 MB | ns | 24.493 | 28.865 | +17.85% |
| random read, 64 MB | ns | 52.591 | 168.407 | +220.22% |
| TLB effective | pages | 32 | 32 | 0.00% |

VirtCCA 的性能特征和 N90 pKVM 明显不同。它不只是影响首次建映射或 page fault，而是在 IPC、大工作集随机访问和 STREAM 读写混合带宽上都有显著影响。尤其是 STREAM copy 和 triad 减半，说明该机制对持续内存读写负载很敏感。

不过，fork 和上下文切换类指标不宜直接解释为“VirtCCA 更快”。例如 fork 在 VirtCCA 下看似更快，而 shell 明显更慢；这类指标很可能受到调度、计时或客户机时钟行为影响。本文只把它们作为异常现象保留，不作为正向性能结论。

## 6. 海光 CSV 测试

海光服务器目前只有 CSV 机密虚拟机数据，普通虚拟机基线还没有完成。因此本节只报告绝对值，不计算 CSV 开销。

| 指标 | 单位 | CSV 机密虚拟机 |
|---|---:|---:|
| null syscall | us | 0.6779 |
| read syscall | us | 1.5393 |
| stat syscall | us | 1.7197 |
| minor page fault | us | 166.3162 |
| fork | us | 114.5558 |
| shell | us | 6790.75 |
| ctx 16p/16K | us | 4.860 |
| pipe latency | us | 8.9484 |
| AF_UNIX latency | us | 20.1705 |
| TCP loopback latency | us | 237.9516 |
| STREAM copy | MB/s | 16516.66 |
| STREAM triad | MB/s | 17790.57 |
| stream2 sum | MB/s | 11452.09 |
| random read, 64 MB | ns | 105.3085 |
| TLB effective | pages | 64 |

这组数据已经可以作为后续对照的 CSV 侧样本，但不能单独说明 CSV 的相对开销。普通虚拟机数据完成后，应使用同一套解析脚本复算两侧中位数，再更新本节。

## 7. 分析结论与边界

### 7.1 pKVM 与 VirtCCA 的开销形态不同

N90 pKVM 的已核验结果显示，主机侧最明显的开销出现在 `lat_mmap` 建立映射路径；x-kernel 客户机侧最明显的开销出现在 minor page fault。syscall、IPC、STREAM 和随机内存访问在稳定阶段基本没有明显差异。

鲲鹏 VirtCCA 则不同。它对 STREAM copy/triad、IPC 和 64 MB 随机访问都有大幅影响。这说明 VirtCCA 的成本更像是持续运行阶段的内存访问或缓存一致性成本，而不是只在建映射时支付的一次性成本。

这个差异可以作为当前最重要的机制判断：pKVM 的成本更集中，VirtCCA 的成本更分散、更容易影响内存带宽型负载。

### 7.2 哪些结论目前不应过度表达

第一，N90 x-kernel 的 VHE 数据可以参考，但严格对比应优先看 NVHE 与 pKVM 两组较新的数据。旧文档把 VHE、NVHE、pKVM 三列放在同等可信度下，容易误导。

第二，VirtCCA 的 STREAM 和随机访问结果支持“内存路径显著受影响”这个结论，但仓库中没有 PMU 计数器或 RMM 事件计数。因此不能把“每次 dirty cacheline 都触发某个具体路径”写成已被证明的事实。更稳妥的说法是：该解释与数据形态一致，但还需要硬件计数器或更小的定向测试验证。

第三，fork、shell、上下文切换等指标容易出现分桶或计时异常。它们适合提示问题，不适合单独作为机密虚拟化开销的主要证据。

第四，海光 CSV 目前没有普通虚拟机基线。所有关于 CSV “快多少”或“慢多少”的说法都应等基线完成后再写。

## 8. 可复核文件索引

当前仓库中可直接复核本文结论的文件如下。

| 类型 | 路径 |
|---|---|
| N90 主机原始与解析结果 | `results/n90-day3-host/` |
| N90 主机综合报告 | `docs/n90-kvm-host/SUMMARY.md`，`docs/n90-kvm-host/FINAL-REPORT.md` |
| N90 主机 mmap 精测日志 | `results/precise-mmap/` |
| N90 x-kernel 客户机结果 | `results/xkernel-n90-kvm-nvhe-20260606-133103/`，`results/xkernel-n90-pkvm-np-clean-20260606-164648/` |
| N90 VHE 客户机参考结果 | `results/xkernel-n90-kvm-vhe-20260605-201819/` |
| 鲲鹏 VirtCCA 结果 | `results/virtcca-regular-results/`，`results/virtcca-cvm-results/` |
| 海光 CSV 结果 | `results/hygon_csv_results/` |
| 主机侧运行脚本 | `bench.sh`，`prepare-host.sh`，`scripts/apply-masks.sh`，`scripts/verify-clean-env.sh` |
| 解析与表格脚本 | `parse-lmbench.py`，`scripts/build-xlsx-median.py`，`scripts/build-xlsx-mean.py`，`scripts/analyze-precise-mmap.py` |
| 关键测试代码 | `src/lat_mmap.c`，`src/lat_mmap_precise.c`，`src/lat_mem_rd.c`，`src/lib_mem.c` |

## 9. 后续工作

1. 补齐海光普通虚拟机基线，并用同一解析口径更新 CSV 对照。
2. 对 N90 x-kernel 客户机结果补充更明确的 host 侧环境记录，尤其是每组数据对应的 `kvm-arm.mode`、CPU 绑核和噪声控制状态。
3. 对 VirtCCA 的 STREAM 和随机访问开销补充 PMU 或更定向的内存测试，避免只凭 lmbench 现象做过强机制判断。
4. 修复客户机结果中的辅助测试问题：`webpage-lm` 缺失导致 `lat_http` 不可用，RPC 在 musl 构建下被跳过，海光 CSV 的部分附加 DMA 命令受 `vfork` 未实现影响。

文档版本：2026-06-07，基于当前仓库结果文件复核。
