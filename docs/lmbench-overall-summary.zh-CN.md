# lmbench 性能实验总览

本文汇总当前仓库中已经收集到的 lmbench 数据，并给出经过本地结果文件复核后的分析结论。实验围绕三类环境展开：

1. N90 主机侧测试：在同一台 Phytium N90 上切换 `kvm-arm.mode=none/vhe/nvhe/protected`，测试主机自身的 lmbench 表现。
2. N90 客户机侧测试：在 N90 的 NVHE 和 pKVM 环境下运行 `~/x-kernel` 客户机，并在客户机内运行 lmbench。仓库中也保留了一组 VHE 客户机结果，主要作为参考。
3. 其他机密虚拟化环境：在鲲鹏服务器上对比普通虚拟机和 VirtCCA 机密虚拟机；在海光服务器上对比普通虚拟机和 CSV 机密虚拟机。

虚拟机测试的完整流程、各平台虚拟化配置，以及 CPU 频率、内存主频、vCPU 绑核是否一致的核对，见 [vm-lmbench-methodology.zh-CN.md](vm-lmbench-methodology.zh-CN.md)。

本次整理重点解决两个问题：第一，核验总览文档中的关键数字是否能从现有结果文件复算出来；第二，把分析表述改成准确、书面、可读的中文，避免把尚未验证的推断写成定论。

## 1. 数据核验口径

本次核验使用仓库中的实际结果文件和解析脚本。

| 数据集 | 数据来源 | 核验方式 | 备注 |
|---|---|---|---|
| N90 主机 4 模式 | `results/n90-day3-host/*.csv`，`results/precise-mmap/*.log` | 直接复算 CSV 中位数；用 `scripts/analyze-precise-mmap.py` 复核 mmap 精测结果 | 这是本仓库中最完整、最干净的数据集 |
| N90 x-kernel 客户机 | `results/xkernel-n90-*/xkernel-*-iter*.txt` | 用 `parse-lmbench.py` 重新解析原始日志，再复算中位数 | 结论主要看 NVHE 与 pKVM；VHE 结果保留为参考 |
| 鲲鹏 VirtCCA | `results/virtcca-regular-results/`，`results/virtcca-cvm-results/` | 用 `parse-lmbench.py` 重新解析原始日志，再复算中位数 | 普通虚拟机与 VirtCCA 机密虚拟机都有 10 轮数据 |
| 海光 CSV | `results/hygon_regular_results/`，`results/hygon_csv_results/` | 用 `parse-lmbench.py` 重新解析原始日志，再复算中位数 | 普通虚拟机与 CSV 机密虚拟机都有 10 轮数据 |

需要注意：

1. 客户机原始日志中有一些非 lmbench 输出，例如 `lat_rpc` 在 musl 环境下被跳过、`lat_http` 缺少 `webpage-lm`、附加 DMA 测试输出等。这些内容没有纳入本文的核心结论。

2. 海光两组日志中都出现了 `vfork: Function not implemented` 和端口绑定冲突等信息。`vfork` 报错只影响附加 DMA 测试的计时，不影响 lmbench 指标。原因是 x86_64 上 musl 调用独立的 `vfork` 系统调用，而测试时的 x-kernel 没有实现它。因此海光部分只报告解析器能够稳定提取的 lmbench 指标。

3. 本文表格使用中位数，N90 客户机表还丢弃了第 1 轮；`docs/vm-ratio-comparison.{csv,xlsx}` 使用 10 轮均值。两者的数值会有小幅差异，引用时应注明口径。

4. 各平台只比较同机比值，不比较不同服务器的绝对值。海光客户机的计时基准很可能被设为 4 GHz 而不是实际 TSC 频率，因此海光的绝对时间和带宽数值整体存在缩放，不能与鲲鹏、N90 直接比较（第 6 节）。

## 2. 总体结论

| 实验对象 | 已核验结论 | 可信度 |
|---|---|---|
| N90 主机侧 `kvm-arm.mode` 对照 | `none/vhe/nvhe/protected` 对主机 syscall、IPC、STREAM、TLB 的影响很小；pKVM 在主机侧最明显的额外成本出现在 `lat_mmap`，64 MB 精测慢约 42% | 高 |
| N90 x-kernel 客户机 NVHE 与 pKVM 对照 | 丢弃第 1 轮后，pKVM 相对 NVHE 的主要稳定差异是 minor page fault 约 +5%；syscall、IPC、STREAM、随机内存访问和 TLB 基本持平 | 中高 |
| 鲲鹏 VirtCCA 与普通虚拟机对照 | VirtCCA 对 STREAM 带宽、IPC 延迟和大工作集随机访问影响显著；syscall 基本不变 | 高 |
| 海光 CSV 与普通虚拟机对照 | CSV 对 syscall、pipe/AF_UNIX、上下文切换和 STREAM 的影响在 ±0.6% 以内，minor page fault +1.0%，64 MB 随机访问 +2.1%；TCP 在 CSV 下反而快 8%，原因未明。两组的客户机内核构建不同，但实际都只有一个 vCPU 在工作 | 中 |

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
| fork（节拍分桶，不作比较，见 7.2 节） | us | 4990.0 | 4990.0 | 4990.0 | 0.00% |
| shell（节拍分桶，不作比较，见 7.2 节） | us | 10001.5 | 10024.0 | 14955.5 | +49.20% |
| ctx 16p/16K | us | 7.590 | 7.640 | 7.680 | +0.52% |
| ctx 96p/64K | us | 15.250 | 15.410 | 15.280 | -0.84% |
| pipe latency | us | 20.0366 | 20.0752 | 20.1351 | +0.30% |
| TCP loopback latency | us | 109.5330 | 111.3358 | 110.7185 | -0.55% |
| STREAM copy | MB/s | 18146.76 | 18532.99 | 18480.01 | -0.29% |
| STREAM triad | MB/s | 17314.45 | 17187.36 | 17400.76 | +1.24% |
| stream2 sum（CPU 指标，见 7.2 节） | MB/s | 7173.88 | 7170.87 | 7163.04 | -0.11% |
| random read, 64 MB | ns | 193.049 | 192.027 | 192.355 | +0.17% |
| TLB effective | pages | 48 | 48 | 48 | 0.00% |

稳定指标显示，pKVM 相对 NVHE 的主要差异是 minor page fault 约 +5%。syscall、IPC、STREAM、随机内存访问和 TLB 容量都基本持平。

`fork` 和 `shell` 不能作为 pKVM 开销的证据。它们的逐轮值都是毫秒级：fork 集中在约 5 ms 和 10 ms 两档，shell 在 10–20 ms 之间，是客户机内核的 10 ms 调度节拍造成的（7.2 节）。`shell` 在 pKVM 下"慢 49%"反映的是节拍对齐的随机性，不代表 pKVM 的开销。

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
| fork（节拍分桶，不作比较，见 7.2 节） | us | 6835.0 | 5237.5 | -23.37% |
| shell（节拍分桶，不作比较，见 7.2 节） | us | 10318.5 | 18990.0 | +84.04% |
| pipe latency | us | 23.3360 | 27.4900 | +17.80% |
| AF_UNIX latency | us | 60.1634 | 71.5307 | +18.89% |
| UDP loopback latency | us | 246.7185 | 362.0249 | +46.74% |
| TCP loopback latency | us | 280.7485 | 391.8587 | +39.58% |
| pipe bandwidth | MB/s | 2988.83 | 2624.69 | -12.18% |
| AF_UNIX bandwidth | MB/s | 2657.89 | 2419.52 | -8.97% |
| STREAM copy | MB/s | 42288.08 | 19841.89 | -53.08% |
| STREAM triad | MB/s | 40829.34 | 18188.92 | -55.45% |
| stream2 fill | MB/s | 22339.54 | 20022.78 | -10.37% |
| stream2 sum（CPU 指标，见 7.2 节） | MB/s | 11554.43 | 11455.68 | -0.85% |
| random read, 4 MB | ns | 24.493 | 28.865 | +17.85% |
| random read, 64 MB | ns | 52.591 | 168.407 | +220.22% |
| TLB effective | pages | 32 | 32 | 0.00% |

VirtCCA 的性能特征和 N90 pKVM 明显不同。它不只是影响首次建映射或 page fault，而是在 IPC、大工作集随机访问和 STREAM 带宽上都有显著影响。尤其是 STREAM copy 和 triad 减半，说明该机制对持续内存访问负载很敏感。

`stream2 sum` 几乎不变，但这不能说明 VirtCCA 不影响内存读取。该测试受浮点加法延迟限制，衡量的是 CPU 而不是内存（7.2 节）。它与 syscall 一起不变，说明两组测试时的 CPU 核心频率一致。

fork 在 VirtCCA 下"快 23%"、shell"慢 84%"都不能解释为 VirtCCA 的影响。这两项的逐轮值在 2.4–23 ms 之间分散，是客户机内核的 10 ms 调度节拍造成的（7.2 节），测到的是节拍对齐的随机性。

## 6. 海光 CSV 测试

### 6.1 数据说明

海光服务器上有两组客户机数据：

| 目录 | 含义 |
|---|---|
| `results/hygon_regular_results/` | 普通虚拟机 |
| `results/hygon_csv_results/` | CSV 机密虚拟机 |

两组数据都包含 10 轮原始日志，并可由 `parse-lmbench.py` 稳定解析。下表为 10 轮中位数。

### 6.2 关键结果

| 指标 | 单位 | 普通虚拟机 | CSV | CSV 相对普通虚拟机 |
|---|---:|---:|---:|---:|
| null syscall | us | 0.6783 | 0.6779 | -0.07% |
| read syscall | us | 1.5392 | 1.5393 | +0.01% |
| stat syscall | us | 1.7291 | 1.7197 | -0.54% |
| minor page fault | us | 164.6645 | 166.3162 | +1.00% |
| fork | us | 114.65 | 114.56 | -0.08% |
| shell（毫秒级分散值，不作比较，见 7.2 节） | us | 7748.50 | 6790.75 | -12.36% |
| ctx 16p/16K | us | 4.880 | 4.860 | -0.41% |
| pipe latency | us | 8.9611 | 8.9484 | -0.14% |
| AF_UNIX latency | us | 20.2208 | 20.1705 | -0.25% |
| TCP loopback latency | us | 259.1420 | 237.9516 | -8.18% |
| STREAM copy | MB/s | 16530.25 | 16516.66 | -0.08% |
| STREAM triad | MB/s | 17862.12 | 17790.57 | -0.40% |
| stream2 sum（CPU 指标，见 7.2 节） | MB/s | 11449.01 | 11452.09 | +0.03% |
| random read, 64 MB | ns | 103.127 | 105.309 | +2.12% |
| TLB effective | pages | 64 | 64 | 0.00% |

CSV 在本组数据中的开销很小：syscall、pipe/AF_UNIX、上下文切换和 STREAM 的差异都在 ±0.6% 以内，可见的代价是 minor page fault +1.0% 和 64 MB 随机访问 +2.1%。这与 CSV 在内存控制器中做透明加解密的机制相符，与鲲鹏 VirtCCA 的大幅内存开销形成对比。

TCP 回环在 CSV 下反而快 8%，本文不作为正向结论。两组的客户机内核构建不同（6.3 节），可能是原因之一，但目前没有数据验证。shell 的差异来自毫秒级的分散取值，不作比较（7.2 节）。

### 6.3 解读海光数据的前提

1. **两组使用了不同的客户机内核构建。** x-kernel 在编译期把 CSV 加密位（`SEV_CBIT_POS=47`）无条件写进页表，这样的内核只能在开启加密的虚拟机中运行，所以普通虚拟机必须使用另一份构建。这一点同时说明 CSV 组的内存加密确实处于开启状态。按测试时 x-kernel 主线的配置，CSV 构建最多启用 1 个 CPU，普通构建最多 4 个。但两组的 fork、exec 延迟逐轮一致（约 114 µs、182 µs），没有多 vCPU 客户机上那种跨 vCPU 等节拍的现象，说明普通组实际也只有一个 vCPU 在工作，两组一致。
2. **绝对值存在整体缩放。** 测试时的 x-kernel 在 x86 上通过 CPUID leaf 0x16 获取 TSC 频率，海光处理器不提供该 leaf，于是退回默认值 4 GHz。海光客户机测得 L1 加载延迟 0.905 ns，若计时准确，对应约 4.4 GHz 的核心频率，超出海光服务器处理器的范围，与这一推断相符。两组的缩放因子相同，所以上表的相对变化不受影响；但海光的绝对值不能与鲲鹏、N90 直接比较。可通过客户机启动日志中的 `TSC frequency` 一行确认。

详细推理见 [vm-lmbench-methodology.zh-CN.md](vm-lmbench-methodology.zh-CN.md) 第 4.3 节和第 6.1 节。

## 7. 分析结论与边界

### 7.1 pKVM、VirtCCA 与 CSV 的开销形态不同

N90 pKVM 的已核验结果显示，主机侧最明显的开销出现在 `lat_mmap` 建立映射路径；x-kernel 客户机侧最明显的开销出现在 minor page fault。syscall、IPC、STREAM 和随机内存访问在稳定阶段基本没有明显差异。

鲲鹏 VirtCCA 则不同。它对 STREAM copy/triad、IPC 和 64 MB 随机访问都有大幅影响。这说明 VirtCCA 的成本更像是持续运行阶段的内存访问或缓存一致性成本，而不是只在建映射时支付的一次性成本。

这个差异可以作为当前最重要的机制判断：pKVM 的成本更集中，VirtCCA 的成本更分散、更容易影响内存带宽型负载。

海光 CSV 在本组数据中开销最小，只在 minor page fault 和大工作集随机访问上有 1–2% 的代价。三种机制的开销形态因此可以概括为：pKVM 集中在建映射，VirtCCA 分散在持续内存访问，CSV 在 lmbench 粒度上接近零。

### 7.2 哪些结论目前不应过度表达

第一，N90 x-kernel 的 VHE 数据可以参考，但严格对比应优先看 NVHE 与 pKVM 两组较新的数据。旧文档把 VHE、NVHE、pKVM 三列放在同等可信度下，容易误导。

第二，VirtCCA 的 STREAM 和随机访问结果支持“内存路径显著受影响”这个结论，但仓库中没有 PMU 计数器或 RMM 事件计数。因此不能把“每次 dirty cacheline 都触发某个具体路径”写成已被证明的事实。更稳妥的说法是：该解释与数据形态一致，但还需要硬件计数器或更小的定向测试验证。

第三，进程创建类指标（fork、exec、shell）不能用于比较。在 aarch64 客户机（N90、鲲鹏）上，它们的逐轮值集中在 5 ms、10 ms 这几档。原因在测试当时的 x-kernel：新进程被轮流分配到各个 vCPU，子进程不继承父进程的 CPU 亲和性（所以客户机内的 `taskset` 对测试进程无效），而跨 vCPU 交接要等 10 ms 的调度节拍。海光客户机只有一个 vCPU 在工作，fork、exec 不受影响，但 shell 同样是毫秒级分散值。pipe、AF_UNIX、上下文切换和所有单进程测试不受影响。详见 `docs/vm-lmbench-methodology.zh-CN.md` 第 6.7 节。

第四，海光的绝对值不能与其他平台横向比较（6.3 节），只能使用同机比值。海光两组的客户机内核构建不同，TCP 在 CSV 下更快这类现象不宜解释为 CSV 的收益。

第五，`stream2 sum` 不是内存带宽指标。它的内层循环是 `s += a[i]`（`src/stream.c`），是一条串行的浮点加法依赖链，带宽约等于"8 字节 / double 加法延迟"。在全部 8 组虚拟机数据上，实测值与这个估算相差不到 3%。因此它不变只能说明 CPU 核心频率一致，不能说明"纯读内存不受影响"。

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
| 海光 CSV 结果 | `results/hygon_regular_results/`，`results/hygon_csv_results/` |
| 虚拟机测试方法与基线一致性 | `docs/vm-lmbench-methodology.zh-CN.md` |
| 主机侧运行脚本 | `bench.sh`，`prepare-host.sh`，`scripts/apply-masks.sh`，`scripts/verify-clean-env.sh` |
| 解析与表格脚本 | `parse-lmbench.py`，`scripts/build-xlsx-median.py`，`scripts/build-xlsx-mean.py`，`scripts/analyze-precise-mmap.py`，`scripts/build-vm-ratio-comparison.py`，`scripts/check-vm-baseline.py` |
| 关键测试代码 | `src/lat_mmap.c`，`src/lat_mmap_precise.c`，`src/lat_mem_rd.c`，`src/lib_mem.c` |

## 9. 后续工作

1. 补测时记录宿主机侧的 CPU 频率、内存主频、vCPU 绑核、NUMA 放置和 VMM 启动命令，并保存客户机 `autorun.sh` 和启动日志。清单见 `docs/vm-lmbench-methodology.zh-CN.md` 第 9 节。海光还需确认客户机的 TSC 频率。客户机内绑核需要先确认客户机内核的 fork 会继承 CPU 亲和性。
2. 对 N90 x-kernel 客户机结果补充更明确的 host 侧环境记录，尤其是每组数据对应的 `kvm-arm.mode`、CPU 绑核和噪声控制状态。
3. 对 VirtCCA 的 STREAM 和随机访问开销补充 PMU 或更定向的内存测试，避免只凭 lmbench 现象做过强机制判断。
4. 修复客户机结果中的辅助测试问题：`webpage-lm` 缺失导致 `lat_http` 不可用，RPC 在 musl 构建下被跳过，海光的部分附加 DMA 命令受 `vfork` 未实现影响。

文档版本：2026-06-07，基于当前仓库结果文件复核；2026-09-29 补入海光普通虚拟机对照，修正 `stream2 sum` 的解读，补充统计口径和海光计时说明，说明 fork/exec/shell 的节拍分桶。
