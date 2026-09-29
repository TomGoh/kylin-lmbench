# 虚拟机 lmbench 测试方法与基线一致性说明

本文完整说明 `docs/vm-ratio-comparison.{csv,xlsx}` 所用虚拟机数据的来源、测试流程、各平台虚拟化配置，并回应以下审阅意见：

> 为了让对比更有说服力，建议在表格或正文中简要补充说明各平台在测试时的内存主频、虚拟化配置（如 vCPU 与物理核的绑核策略）是否保持了一致，从而排除因硬件基线配置差异引入的干扰。

本文区分三类信息，避免把推断写成事实：

- **有记录**：结果目录、仓库文件或代码中能直接找到。
- **有旁证**：没有直接记录，但可以从原始数据或代码推出，并给出推理过程。
- **未记录**：仓库和本机都找不到，只能在补测时补齐。

## 1. 结论摘要

1. **对比设计是同机成对。** 每个平台都在同一台物理服务器上比较普通（或非保护）虚拟机与机密（或受保护）虚拟机，跨平台只比较比值，不比较绝对值。因此不同服务器之间的 CPU 型号、内存主频差异本身不进入比值。需要保证的是**同一台机器内两组测试的基线一致**。
2. **CPU 核心频率：三个平台都有旁证支持一致。** 与虚拟化机制无关的纯核心指标（整数和浮点运算延迟、L1 延迟、L1 带宽、`stream2 sum`），取两组各自最快一轮比较，比值全部在 0.991–1.001 之间。N90 客户机的这些指标与主机锁频 1.9 GHz 时的测量值相差不到 0.1%。
3. **内存主频：三个平台都没有记录。** 海光和 N90 两组的 DRAM 型指标相差在 ±2% 以内，与"内存配置一致"相符。鲲鹏上这些指标受 VirtCCA 影响显著（STREAM 减半，64 MB 随机访问 3.2 倍），仅凭客户机数据无法把内存配置差异与 VirtCCA 开销区分开。
4. **vCPU 与物理核的绑核：三个平台都没有留存记录。** 据实验人员回忆，测试时按"物理核—vCPU—测试进程"逐层用 `taskset` 绑定，但命令没有保存。仓库中能找到的 CSV 启动脚本 `x-kernel/scripts/start.sh` 是通用脚本，没有绑核参数。
5. **客户机内的绑核对 lmbench 测试进程没有生效（鲲鹏、N90）。** 测试当时的 x-kernel 不把 CPU 亲和性传给子进程，测试进程实际分散在多个 vCPU 上。受影响的只有进程创建类指标（fork、exec、shell）：它们在 aarch64 客户机上按 10 ms 时钟节拍分桶，不能用于比较（6.7 节）。单进程测试和 pipe/AF_UNIX 不受影响。海光两组客户机实际都只有一个 vCPU 在工作，不存在这个问题。
6. **还有两处影响解读的配置差异：**
   - 海光普通虚拟机和 CSV 虚拟机必然使用了不同的客户机内核构建（见 4.3 节），但两组实际工作的 vCPU 数一致，都是 1 个。
   - 海光客户机的计时基准很可能被错误地设为 4 GHz。它不影响海光的同机比值，但海光的绝对数值不能和其他平台直接比较（见 6.1 节）。

## 2. 数据集

| 平台 | 数据集 | 目录 | VMM | 客户机架构 | ENV_TAG（`started.txt`） | 客户机 MemTotal | 运行时段（客户机时钟，UTC） | 入库提交 |
|---|---|---|---|---|---|---:|---|---|
| 鲲鹏 | 普通虚拟机 | `results/virtcca-regular-results/` | QEMU/KVM | aarch64 | `xkernel-kunpeng-regular` | 2084584 kB | 06-06 01:09 → 03:01 | `b9b1c26e` |
| 鲲鹏 | VirtCCA 机密虚拟机 | `results/virtcca-cvm-results/` | QEMU/KVM + virtCCA | aarch64 | `xkernel-virtcca` | 2084584 kB | 06-05 07:06 → 09:07 | `b9b1c26e` |
| 海光 | 普通虚拟机 | `results/hygon_regular_results/` | QEMU/KVM | x86_64 | `xkernel-hygon_regular` | 1855556 kB | 06-07 01:13 → 05:13 | `e1468088` |
| 海光 | CSV 机密虚拟机 | `results/hygon_csv_results/` | QEMU/KVM + CSV（SEV 接口） | x86_64 | `xkernel-csv` | 1855260 kB | 06-06 07:57 → 11:53 | `b9b1c26e` |
| N90 | VHE 主机上的虚拟机 | `results/xkernel-n90-kvm-vhe-20260605-201819/` | crosvm | aarch64 | `xkernel-kvm` | 1999956 kB | 06-05 09:16 起 | `b9b1c26e` |
| N90 | NVHE 主机上的虚拟机 | `results/xkernel-n90-kvm-nvhe-20260606-133103/` | crosvm | aarch64 | `xkernel-kvm-nvhe` | 1999956 kB | 06-06 02:30 起 | `b9b1c26e` |
| N90 | pKVM 非保护虚拟机 | `results/xkernel-n90-pkvm-np-clean-20260606-164648/` | crosvm | aarch64 | `xkernel-pkvm-np` | 1999956 kB | 06-06 05:47 起 | `b9b1c26e` |
| N90 | pKVM 保护虚拟机 | `results/xkernel-n90-pkvm-pvm-20260605-163040/` | crosvm | aarch64 | `xkernel-pkvm-np`（与目录名不符，见 6.6 节） | 1999956 kB | 06-05 05:31 起 | `b9b1c26e` |

说明：

- 每组都是 10 轮，文件名为 `xkernel-<tag>-cpu0-iter<N>.txt`。
- 海光客户机的时钟可能按错误的频率计时（6.1 节），因此海光的运行时长只能作参考。
- N90 目录还保存了 `CONFIG.xkernel.used` 和 `autorun.marker`。鲲鹏和海光目录里没有这两个文件，只有 `started.txt`、`environment.txt`、`completed.txt` 和 10 份原始日志。

## 3. 客户机内部的测试流程（四个平台相同）

### 3.1 软件栈

| 层次 | 内容 | 依据 |
|---|---|---|
| 客户机内核 | x-kernel（Rust 实现、兼容 Linux ABI），`uname` 显示为 `Linux kylin-x 10.0.0` | 原始日志第 1 行 |
| 根文件系统 | alpine-busybox（BusyBox v1.37.0），`/` 为 virtio-blk 上的 ext4，`/tmp` 为 tmpfs | `environment.txt` 挂载表，原始日志 |
| lmbench | lmbench 3.0-a9，musl 静态编译（`x86_64-linux-musl` / `aarch64-linux-musl`） | 原始日志 `[OS: ...]`、`[LMBENCH VERSION: 3.0-a9]` |
| 配置文件 | `configs/CONFIG.xkernel`（副本见 N90 目录的 `CONFIG.xkernel.used`） | `started.txt` |

### 3.2 自动运行流程

客户机启动后由 `/root/.profile` 调用 `/opt/lmbench/autorun.sh`，依次执行：

1. 写 `started.txt`：记录开始时间和参数行 `[autorun] ENV_TAG=<tag> CORES=0 ITERS=10 CONFIG=configs/CONFIG.xkernel DMA_SIZE_M=128`。
2. 写 `environment.txt`：只包含客户机侧的 `/dev` 列表、挂载表和 `/proc/meminfo` 前 6 行。**不包含宿主机的任何信息。**
3. 以 `CORES=0` 连续运行 10 轮完整的 `scripts/lmbench`，每轮输出一份 `iter<N>.txt`。
4. 每轮 lmbench 结束后，运行附加的块设备（DMA）测试，输出追加在该轮日志末尾（3.4 节）。
5. 写 `completed.txt`。

`autorun.sh` 本身不在本仓库中（第 7 节），但可以确定它是由本仓库已删除的 `bench-in-guest.sh`（`git show 9e3f55de^:bench-in-guest.sh`）改写来的：

- **相同之处：** 两者读取同样格式的标记文件（`ENV_TAG=` / `CORES=` / `ITERS=` / `CONFIG=`，见 N90 目录的 `autorun.marker`），打印同样格式的启动行（`[bench-in-guest] ENV_TAG=... CORES=...` 与 `[autorun] ENV_TAG=... CORES=...`）。
- **不同之处：** 旧脚本调用 `bench.sh`，后者用 `taskset -c $core` 包住 `scripts/lmbench`；x-kernel 版改用 busybox ash 重写了循环。证据是两批日志第 2 行的报错格式：旧日志是 bash 格式、绝对路径的 `/opt/lmbench/scripts/lmbench: line 66: version: No such file or directory`，x-kernel 日志是 ash 格式、相对路径的 `../../scripts/lmbench: line 66: can't open version: no such file`。

x-kernel 版是否保留了 `taskset -c $CORES` 无法确认。即使保留了，也只作用于 lmbench 脚本本身，对它启动的测试进程无效（6.7 节）。

### 3.3 lmbench 配置要点（`CONFIG.xkernel`）

| 参数 | 值 | 含义 |
|---|---|---|
| `ENOUGH` | 10000 | 每个测量点的最短计时区间（µs） |
| `MB` | 64 | 内存类测试的最大工作集 |
| `SYNC_MAX` | 1 | 单进程延迟测试，不做并行吞吐 |
| `FILE` / `FSDIR` | `/root/lmb_file` / `/root/lmb_fs` | 文件测试落在 virtio-blk 上的 ext4，而不是 tmpfs |
| `BENCHMARK_RPC` | NO | musl 没有 libtirpc，`lat_rpc` 是空实现 |
| `DISKS` | 空 | x-kernel 不向 `/dev` 暴露 virtio-blk 设备，`disk` 测试无法运行 |
| `PROCESSORS` | "2" | **只是写进报告头的标签，不是实测值** |
| `MOTHERBOARD` | "x-kernel/crosvm-aarch64" | **只是标签**：海光和鲲鹏用的是 QEMU，报告头里仍写着这个 |

### 3.4 附加 DMA 测试

每轮日志末尾有 4 项块设备测试：

- `ext4 seq write 1 MiB x 128`
- `ext4 small write 4 KiB x 8192`
- `ext4 cold read 128 MiB`：日志打印了 `(no drop_caches)`，说明两次读之间并没有清缓存
- `lmdd 128 MiB write`

这些输出**不被 `parse-lmbench.py` 解析，没有进入任何比值表**。在海光上，前两项和第三项的计时部分因 `time: vfork: Function not implemented` 没有数据（6.3 节）。

### 3.5 数据处理与统计口径

| 产物 | 生成方式 | 统计量 |
|---|---|---|
| `docs/vm-ratio-comparison.{csv,xlsx}`、`docs/vm-ratio-comparison-highlights.csv` | `scripts/build-vm-ratio-comparison.py` 调用 `parse-lmbench.py` 解析全部 `iter*.txt` | 10 轮**均值**，比值 = 机密（受保护）虚拟机 / 普通虚拟机 |
| `docs/lmbench-overall-summary.zh-CN.md` 中的表格 | `parse-lmbench.py` 重新解析 | **中位数**；N90 客户机表丢弃第 1 轮 |
| 本文第 5 节 | `scripts/check-vm-baseline.py` | 均值比、最快一轮之比、变异系数 |

两份文档的统计量不同（均值和中位数），引用时应注明。

## 4. 各平台的虚拟化配置

下面引用的 x-kernel 配置取自测试当时 x-kernel 主线的最后一个提交 `9bab5da3`（2026-06-04）。测试实际使用的 x-kernel 提交**未记录**，这里只能说明当时主线上的配置是什么样。

### 4.1 N90（Phytium，pKVM）

| 项目 | 内容 | 状态 |
|---|---|---|
| VMM | crosvm | 有记录（`CONFIG.xkernel.used` 注释） |
| 客户机内核配置 | `platforms/aarch64-crosvm-virt/defconfig`，`CPU_NUM=2` | 有记录（x-kernel `9bab5da3`） |
| 客户机内存 | crosvm `-m 2048`，客户机 MemTotal 1999956 kB，4 组相同 | 有记录 |
| 启动脚本 | `CONFIG.xkernel.used` 提到 `scripts/boot/run-crosvm-n80.sh`，但本机 x-kernel 所有分支里都没有这个文件 | 未找到 |
| 主机 CPU 频率 | 主机测试用 `prepare-host.sh` 锁定 1.9 GHz。客户机数据与之吻合：L1 延迟客户机 2.226 ns / 主机 2.223 ns，`integer_div` 4.45 / 4.45 ns，`double_div` 6.68 / 6.67 ns | 有旁证 |
| vCPU 与物理核绑定 | 据实验人员回忆使用了 `taskset`，x-kernel 客户机测试的实际命令未留存。早期 Kylin-Linux 客户机测试有记录：`guest/launch-guest.sh`（已在 `9e3f55de` 删除）用 `taskset -c 0,1` 绑定 crosvm 进程，另见 `docs/SUMMARY-zh.md` 第 58 行、`docs/findings-2026-06-02.md` 第 64 行 | 未留存记录 |
| 客户机实际工作的 vCPU 数 | 2 个。fork、exec 延迟呈"一次跨 vCPU、一次同 vCPU"的 5 ms / 10 ms 两档分布（6.7 节），与 `CPU_NUM=2` 一致 | 有旁证 |

### 4.2 鲲鹏（VirtCCA）

| 项目 | 内容 | 状态 |
|---|---|---|
| VMM | QEMU/KVM，VirtCCA 机密虚拟机 | 有记录（目录名、ENV_TAG、`docs/lmbench-overall-summary.zh-CN.md`） |
| 客户机内核配置 | x-kernel 有 `platforms/aarch64-qemu-virt/virtcca_defconfig`。它与普通 `defconfig` 的区别：`ARM_GENERIC_TIMER_MODE="virtual"`（普通为 physical）、`PSCI_METHOD="smc"`（普通为 hvc）、打开 `KFEAT_VIRTCCA_HUK_KEY`、关闭 `KFEAT_DWARF`。两者都是 `CPU_NUM=4` | 配置有记录；实际使用哪一份未记录 |
| 两组是否同一内核镜像 | 两组 MemTotal 完全相同（2084584 kB），与"同一内核镜像 + 同一内存参数"一致，但不能据此排除其他差异 | 有旁证（弱） |
| QEMU 启动命令、vCPU 数、内存参数 | 仓库和本机都没有 | 未记录 |
| 客户机实际工作的 vCPU 数 | 两组的 fork、exec 延迟都呈跨 vCPU 等节拍的分散形态（6.7 节），说明两组都有多个 vCPU 在工作，具体数目无法确定 | 有旁证（弱） |
| 主机 CPU 型号与频率、内存主频、NUMA 放置、大页 | 没有 | 未记录 |
| vCPU 与物理核绑定 | 据实验人员回忆使用了 `taskset`，命令未留存 | 未留存记录 |

### 4.3 海光（CSV）

| 项目 | 内容 | 状态 |
|---|---|---|
| VMM | QEMU/KVM，q35 机型，OVMF UEFI，`-cpu host -accel kvm`，通过 `-object sev-guest,policy=0x1,cbitpos=47,reduced-phys-bits=5,...` 和 `-machine memory-encryption=sev0` 开启 CSV | 仓库脚本有记录（x-kernel `scripts/start.sh`），实际命令未记录 |
| 客户机内核配置 | CSV：`platforms/x86_64-qemu-virt/csv_defconfig`，`CPU_NUM=1`，`SEV_CBIT_POS=47`。普通：`defconfig`，`CPU_NUM=4`，`SEV_CBIT_POS=0` | 配置有记录 |
| 两组必然使用不同内核构建 | x-kernel 在编译期把 `1 << SEV_CBIT_POS` 无条件写进所有页表项（`boot/x86-boot-common/src/lib.rs`、`arch/karch/src/x86_64/mmu.rs`）。没有开启加密的虚拟机里，第 47 位会被当作普通物理地址位，内核无法启动；开启了加密的虚拟机里，不设 C-bit 的内核也无法正常运行。所以 CSV 组用的是 C-bit 构建，普通组用的是非 C-bit 构建。两组 MemTotal 相差 296 kB，也与此一致 | 有旁证（强） |
| CSV 加密确实开启 | 由上一条可得：C-bit 构建的内核能跑完 10 轮，就说明内存加密处于开启状态 | 有旁证（强） |
| 客户机实际工作的 vCPU 数 | CSV 内核最多启用 1 个 CPU，普通内核最多 4 个。但两组的 fork、exec 延迟逐轮一致（约 114 µs、182 µs，相差 0.1%），没有 aarch64 客户机上那种跨 vCPU 等节拍的现象（6.7 节），说明普通组实际也只有一个 vCPU 在工作 | 有旁证：一致，均为 1 个 |
| 客户机内存 | `start.sh` 默认 `-m 1G`，但两组客户机 MemTotal 都约 1.77 GiB，说明实际没有使用 `start.sh` 的默认参数 | 有旁证 |
| 主机 CPU 型号与频率、内存主频、NUMA 放置 | 没有 | 未记录 |
| vCPU 与物理核绑定 | 据实验人员回忆使用了 `taskset`；仓库中的通用脚本 `start.sh` 没有绑核参数，实际命令未留存 | 未留存记录 |

## 5. 基线一致性核对（回应审阅意见）

复现命令：`python3 scripts/check-vm-baseline.py`

### 5.1 核对思路

宿主机的 CPU 频率、内存主频和绑核都没有随数据保存，所以只能用客户机自己的 lmbench 输出做回溯检查。指标分两类：

- **A 类：纯核心指标。** 包括 `lat_ops` 的整数和浮点运算延迟、L1 加载延迟（`lat_mem_rd` 512 B 工作集）、L1 读带宽（4 KB），以及 `stream2 sum`。它们只在 CPU 核心和 L1 内运行，不经过 stage-2 页表缺失、内存加密或 RMM。只要两组测试时核心频率相同，比值就应为 1.000。
- **B 类：DRAM 型指标。** 包括 64 MB 顺序和随机访问延迟、64 MB 读带宽、STREAM copy/triad。它们同时受内存配置（主频、通道、NUMA）和保护机制开销影响。

**关于 `stream2 sum`：** 它的内层循环是 `s += a[i]`（`src/stream.c` 第 290 行），是一条串行的浮点加法依赖链。实测带宽与"8 字节 / double 加法延迟"的比值在 0.97–1.01 之间，在所有 8 组数据上都成立。所以它衡量的是 CPU 浮点加法延迟，不是内存带宽，应归入 A 类。

### 5.2 CPU 核心频率

数值为"均值比（最快一轮之比）"：

| 指标 | 鲲鹏 VirtCCA / 普通 | 海光 CSV / 普通 | N90 pKVM-NP / NVHE | N90 pKVM-pVM / NVHE |
|---|---:|---:|---:|---:|
| `integer_add` 延迟 | 1.024 (1.000) | 1.000 (1.000) | 1.000 (1.000) | 1.004 (1.000) |
| `integer_div` 延迟 | 1.014 (1.000) | 0.998 (1.000) | 1.000 (1.000) | 1.007 (1.000) |
| `double_add` 延迟 | 1.022 (1.000) | 1.000 (1.000) | 1.000 (1.000) | 1.009 (1.000) |
| `double_div` 延迟 | 1.018 (1.000) | 0.999 (1.000) | 1.000 (1.000) | 1.005 (1.000) |
| `float_div` 延迟 | 1.003 (1.000) | 1.000 (1.000) | 1.000 (1.000) | 1.000 (1.000) |
| L1 加载延迟 | 1.008 (1.001) | 0.999 (1.000) | 1.000 (1.000) | 1.000 (1.000) |
| L1 读带宽 | 0.989 (1.000) | 1.000 (1.001) | 1.000 (1.000) | 0.999 (1.000) |
| `stream2 sum` 带宽 | 0.990 (0.991) | 1.001 (1.000) | 0.999 (0.999) | 1.000 (1.000) |

解读：

- 海光和 N90 的均值比和最快一轮之比都在 1.000 附近，变异系数接近 0，**两组测试时核心频率一致**。
- 鲲鹏 VirtCCA 组的均值偏慢 1–2%，变异系数 1.5–3%（普通组约 0%）。但最快一轮与普通组完全相同（比值 1.000）。逐轮看，VirtCCA 组一部分轮次与普通组相同（例如 `double_div` 3.46–3.48 ns），另一部分偏高（3.60–3.66 ns）。频率差异会让所有轮次整体偏移，不会是这种"时有时无"的形态。所以这里是**频率一致，VirtCCA 组存在间歇性干扰**。干扰可能来自机密虚拟机的中断或定时器路径，也可能来自未绑核的 vCPU 线程被宿主机调度，现有数据无法区分。
- N90 客户机的核心指标与主机锁频 1.9 GHz 时相同（4.1 节），说明客户机测试期间主机同样运行在 1.9 GHz。

### 5.3 内存子系统（与内存主频相关）

数值为"均值比（最快一轮之比）"：

| 指标 | 鲲鹏 VirtCCA / 普通 | 海光 CSV / 普通 | N90 pKVM-NP / NVHE | N90 pKVM-pVM / NVHE |
|---|---:|---:|---:|---:|
| 64 MB 顺序加载延迟（stride 128） | 2.279 (2.266) | 1.011 (0.997) | 1.012 (1.014) | 1.008 (1.012) |
| 64 MB 随机加载延迟 | 3.222 (3.205) | 1.012 (0.996) | 0.988 (0.943) | 0.798 (0.795) |
| 64 MB 读带宽 | 0.348 (0.343) | 0.990 (1.001) | 0.983 (0.993) | 1.017 (0.994) |
| STREAM copy | 0.471 (0.473) | 0.995 (1.000) | 0.986 (0.996) | 1.007 (0.999) |
| STREAM triad | 0.445 (0.445) | 0.992 (1.002) | 1.002 (1.013) | 1.005 (1.006) |

解读：

- **海光**：CSV 与普通虚拟机的 DRAM 型指标都在 ±1.2% 以内（最快一轮之比 0.996–1.002）。如果两组的内存主频或通道配置不同，这些指标会有系统性差异，所以数据与"内存配置一致"相符。这也说明本组数据中 CSV 加密的访存开销很小。
- **N90**：pKVM-NP 与 NVHE 的 DRAM 型指标在 ±2% 以内，与内存配置一致相符。pKVM-pVM 组的 64 MB 随机访问反而快约 20%，原因未查明，并且这组数据的 ENV_TAG 有疑问（6.6 节），使用前需要确认。
- **鲲鹏**：VirtCCA 使 DRAM 型指标大幅变化。这些变化可能来自 VirtCCA 本身，也可能部分来自两组虚拟机的内存放置不同（NUMA 节点、大页），客户机数据无法区分。唯一可以确定的是，两组的核心频率一致（5.2 节）。**鲲鹏内存配置是否一致，必须补查宿主机记录才能回答。**

### 5.4 vCPU 与物理核的绑核

| 层次 | N90 | 鲲鹏 | 海光 |
|---|---|---|---|
| 宿主机：vCPU 线程绑定到固定物理核 | 据回忆用 `taskset`，未留存记录 | 据回忆用 `taskset`，未留存记录 | 据回忆用 `taskset`，未留存记录；仓库中的通用脚本 `start.sh` 没有绑核参数 |
| 宿主机：NUMA 与内存绑定 | 未记录（N90 为单路 SoC） | 未记录 | 未记录 |
| 客户机内：测试进程固定在单个 vCPU | **否**：测试进程分散在 2 个 vCPU 上（6.7 节） | **否**：分散在多个 vCPU 上（6.7 节） | 是：客户机只有一个 vCPU 在工作 |

客户机内这一层能从数据直接判断（6.7 节）；宿主机这一层只有间接证据：

- 除鲲鹏 VirtCCA 组外，A 类指标 10 轮的变异系数都接近 0。
- 在 aarch64 客户机里，测试进程每次启动会被分配到不同的 vCPU，但 A 类指标 10 轮仍完全一致，说明这些 vCPU 背后的物理核频率和特性相同。

这两点与"vCPU 绑定到同类物理核"相符，但不能证明做了绑核。

### 5.5 汇总

| 核对项 | N90 | 鲲鹏 | 海光 |
|---|---|---|---|
| 同机成对 | 是 | 是（按现有文档记载） | 是（按现有文档记载） |
| CPU 核心频率一致 | 有旁证：比值 1.000，且与 1.9 GHz 锁频吻合 | 有旁证：最快一轮之比 1.000 | 有旁证：比值 1.000 |
| 内存主频一致 | 未记录；有旁证（DRAM 指标 ±2%） | 未记录；**无法旁证** | 未记录；有旁证（DRAM 指标 ±1.2%） |
| 宿主机 vCPU 绑核 | 据回忆使用 `taskset`，未留存记录 | 据回忆使用 `taskset`，未留存记录 | 据回忆使用 `taskset`，未留存记录 |
| 客户机 vCPU 数一致 | 是（`CPU_NUM=2`，四组同一平台配置；数据旁证为 2 个） | 未记录（数据旁证两组都多于 1 个） | 有旁证：一致（均为 1 个） |
| 客户机内测试进程固定在单个 vCPU | 否（6.7 节） | 否（6.7 节） | 是（单 vCPU） |
| 客户机内核构建一致 | 未记录 | 旁证为一致（MemTotal 相同） | **不一致**（C-bit 决定了必须不同） |
| 客户机用户态与 lmbench 配置一致 | 是 | 是 | 是 |

## 6. 已知问题与数据使用边界

### 6.1 海光客户机的计时基准很可能不准（影响跨平台绝对值）

- **代码**：x-kernel `9bab5da3` 的 `drivers/timer/src/x86_lapic_tsc.rs` 先用 CPUID leaf 0x16 读取处理器基准频率作为 TSC 频率。读不到时，退回 `TIMER_FREQUENCY_HZ`，默认 4000000000。然后按 `ns = ticks × 1000 / CPU_FREQ_MHZ` 换算时间。
- **推断**：CPUID leaf 0x16 是 Intel 定义的，AMD 和海光处理器不提供，所以海光客户机会退回到 4 GHz。
- **数据旁证**：海光客户机测得 L1 加载延迟 0.905 ns。海光核心源自 Zen 架构，L1 加载延迟为 4 个周期，如果计时正确，意味着核心频率达到 4.4 GHz，超出海光服务器处理器的频率范围。
- **影响**：
  - 海光的所有时间类数值都按"实际 TSC 频率 / 4 GHz"整体缩小，带宽类数值按相反比例放大。
  - 两组海光数据在同一台主机上、使用同一段计时代码，缩放因子相同，**同机比值不受影响**。
  - 海光绝对值与鲲鹏、N90 的直接比较（例如"海光 syscall 0.68 µs 比鲲鹏 1.32 µs 快"）不成立。
- **确认方法**：
  - 查看客户机启动日志中 x-kernel 打印的 `TSC frequency: <N> MHz`。
  - 在宿主机上执行 `grep -m1 'model name' /proc/cpuinfo` 和 `dmesg | grep -i tsc`，得到实际 TSC 频率。
- aarch64 平台（鲲鹏、N90）使用 ARM 通用定时器，频率来自硬件寄存器 `CNTFRQ`，不存在这个问题。

### 6.2 客户机报告头和时间统计中的无效字段

- `[PROCESSORS: 2]` 和 `[MOTHERBOARD: x-kernel/crosvm-aarch64]` 来自配置文件，不是实测值（3.3 节）。
- 客户机 `uptime` 始终显示 `up 0 min`，例如海光 CSV 第 10 轮时距第 1 轮已约 3.5 小时。
- 鲲鹏上 `time` 输出了 `user 221h 38m 35s` 这样的异常值。
- 这些字段都不能作为运行环境证据。

### 6.3 海光 DMA 测试缺数据

busybox 的 `time` 通过 vfork 创建子进程。x86_64 上 musl 调用独立的 `vfork` 系统调用，而 x-kernel `9bab5da3` 只实现了 `clone`（支持 `CLONE_VFORK`），没有 `vfork`，因此返回 `Function not implemented`。aarch64 上没有 `vfork` 系统调用，musl 改用 `clone`，所以鲲鹏和 N90 不受影响。DMA 测试不在比值表内（3.4 节）。

### 6.4 异常数值，不宜据此下结论

- `Simple open/close`：第 1 轮海光 CSV 4.7 ms、海光普通 5.6 ms，鲲鹏 VirtCCA 1.2 ms、鲲鹏普通 0.86 ms。原生 Linux 通常是微秒级。这测的是 x-kernel 在 ext4 上打开 `/root/lmb_file` 的路径。
- `Select on 250 tcp fd's` 约 1.8 ms，并伴随 `bind: Address in use`。
- `lat_http` 因缺少 `webpage-lm` 目录未运行，`lat_rpc` 因 musl 被跳过。
- fork、exec、shell 呈分桶分布，原因见 6.7 节。

### 6.5 鲲鹏 VirtCCA 组的间歇性干扰

见 5.2 节：`null syscall` 等指标部分轮次偏高，最快一轮与普通组相同。引用均值时应说明这一点，或改用中位数、最快一轮做对照。

### 6.6 N90 pKVM-pVM 数据集的标签不一致

目录名为 `xkernel-n90-pkvm-pvm-20260605-163040`，但 `started.txt` 和 `autorun.marker` 中的 ENV_TAG 都是 `xkernel-pkvm-np`，与另一组非保护虚拟机相同。可能是 marker 没有更新，也可能是这组实际不是保护虚拟机。在确认之前，"pKVM pVM / NVHE" 的比值应谨慎使用。

### 6.7 aarch64 客户机上 fork/exec/shell 按时钟节拍分桶，客户机内绑核对测试进程无效

**现象。** 每组 10 轮的 `lat_proc fork` 原始值（µs）：

| 数据集 | fork |
|---|---|
| N90 NVHE | 10030, 4990, 4990, 4990, 4990, 4990, 4990, 4990, 5357, 4990 |
| N90 pKVM-NP | 9990, 5018, 4990, 9938, 4990, 4990, 4990, 4990, 4990, 5033 |
| 鲲鹏普通 | 9990, 7743, 7703, 4998, 4777, 5312, 8838, 5967, 4811, 8088 |
| 鲲鹏 VirtCCA | 9588, 5111, 5250, 6594, 2492, 9224, 5225, 2442, 5785, 4960 |
| 海光普通 | 109, 113, 114, 115, 114, 115, 114, 115, 115, 115 |
| 海光 CSV | 110, 113, 114, 115, 115, 114, 115, 115, 115, 115 |

`exec` 的形态与 `fork` 相同。N90 的值集中在约 5 ms 和 10 ms 两档，鲲鹏在 2.4–10 ms 之间分散，都是毫秒级；海光则稳定在约 114 µs。

**机制**（依据 x-kernel `9bab5da3` 的代码）：

1. **新任务轮流分配到各个 CPU。** `task/ktask/src/run_queue.rs` 的 `select_run_queue_index` 按 `CPU_NUM` 轮转，只受任务 cpumask 限制。
2. **子进程不继承父进程的 CPU 亲和性。** 新任务的 cpumask 默认是所有活跃 CPU（`task/ktask/src/task.rs` 的 `new_common`），fork/clone 路径上没有调用 `set_cpumask`。因此客户机里的 `taskset -c 0` 只固定调用它的进程，lmbench 脚本启动的每个测试进程都不受约束。
3. **跨 CPU 交接要等时钟节拍。** 节拍为 100 Hz（`TICKS_PER_SECOND=100`，每 10 ms 一次）。子进程被放到另一个空闲 vCPU 上时，那个 vCPU 要到下一个节拍才开始运行它。

N90 客户机有 2 个 vCPU，大约一半的 fork 落到另一个 vCPU（约 10 ms），另一半留在原 vCPU（约 0.1 ms）。lmbench 每个测量点只运行到满 10 ms（`ENOUGH=10000`），通常包含一慢一快两次 fork，平均正好约 4990 µs；只包含一次慢的就是约 9990 µs。鲲鹏客户机内核最多可用 4 个 CPU，落到其他 vCPU 的比例更高，数值更分散。海光两组都没有这种现象，说明客户机里只有一个 vCPU 在工作。

另外，`shell` 在海光上也是 5–15 ms 之间的分散值（例如 5024、10031、15204 µs）。这说明 shell 路径上还有别的毫秒级等待，很可能也和节拍有关，具体原因未查明。

**影响范围：**

| 指标类别 | 是否受影响 | 依据 |
|---|---|---|
| fork、exec、shell（aarch64 客户机） | **受影响，不能用于比较** | 测到的是节拍对齐的随机性，例如鲲鹏"fork 在 VirtCCA 下快 23%"就是这种结果 |
| shell（海光） | **受影响，不能用于比较** | 同样是毫秒级分散值 |
| fork、exec（海光） | 不受影响 | 单 vCPU，逐轮稳定 |
| pipe、AF_UNIX、上下文切换 | 不受影响 | 被唤醒的任务会移到唤醒方所在的 CPU，两个进程很快在同一个 vCPU 上交替运行；pipe 延迟逐轮稳定（N90 约 20 µs，鲲鹏约 23–27 µs） |
| 单进程测试（syscall、page fault、内存、STREAM、运算延迟） | 不受影响 | 进程启动后留在同一个 vCPU 上（当时的 x-kernel 没有负载均衡），10 轮变异系数接近 0 |

以上机制来自 `9bab5da3` 的代码。测试实际使用的 x-kernel 提交没有记录，但数据形态与这份代码的行为完全吻合。

## 7. 脚本检索结果

检索范围：

- 本仓库：所有分支、完整 git 历史、被 `.gitignore` 忽略的本地文件
- `~/Dev/x-kernel`：所有本地和远程分支
- `~/Dev/kylin100-xkernel-boots`、`~/Dev/kylin100/pvm-manage`
- `~/Dev`、`~/starkylin`、`~/xhyper-workspace` 下的全文搜索
- `~/.ssh/config`

| 需要的文件或记录 | 结果 |
|---|---|
| 客户机内 `/opt/lmbench/autorun.sh` | **未找到**。搜索了它打印的字符串（`DMA: ext4 seq write`、`INFO.xkernel`、`xkernel-csv`、`xkernel-virtcca`），均无结果 |
| `configs/CONFIG.xkernel` | 本仓库没有；N90 结果目录中有使用时的副本 `CONFIG.xkernel.used` |
| 海光 CSV 启动脚本 | x-kernel `scripts/start.sh`（`c723a526` 起存在，测试时版本见 `9bab5da3`）。这是通用脚本，不是测试实际使用的命令（内存参数与数据不符，4.3 节） |
| 海光普通虚拟机启动命令 | 未找到 |
| 鲲鹏 VirtCCA、普通虚拟机的 QEMU 启动命令 | 未找到（搜索 `tmm-guest`、`kvm-type=cvm` 无结果） |
| N90 x-kernel 客户机启动脚本 `scripts/boot/run-crosvm-n80.sh` | 未找到（x-kernel 任何分支都没有） |
| 宿主机 CPU、内存、绑核记录 | 海光、鲲鹏、N90 x-kernel 客户机测试都没有。N90 主机侧测试有（`results/*-summary.txt` 记录了 `cpu_max_freqs`） |
| 绑核的直接记录 | 只覆盖 6 月 1–2 日 N90 Kylin-Linux 客户机那一批：宿主机侧 `guest/launch-guest.sh` 的 `taskset -c 0,1 crosvm`，客户机侧 `bench.sh` 的 `taskset -c $core`（`results/n90-day1/guest-N5-bootlog.txt` 第 67 行留有 `CORES=0` 的运行记录），以及 `docs/SUMMARY-zh.md` 第 58 行、`docs/findings-2026-06-02.md` 第 64 行。这批数据不在比值表中 |
| 早期 N90 Kylin-Linux 客户机脚本 | `bench-in-guest.sh`、`guest/launch-guest.sh`、`guest/mkrootfs.sh`，在 `9e3f55de` 删除，提交说明为"guest-side testing logic now lives in a separate repository" |
| 本机 ssh 配置中的鲲鹏、海光服务器 | 没有 |

结论：海光和鲲鹏测试的客户机自动脚本、宿主机启动命令和宿主机环境记录，都不在本仓库和本机上。执行测试的服务器已无法访问，这些记录已无法补回。

## 8. 可用于报告的表述

下面这段只陈述有记录或有旁证的内容，未记录的部分如实说明：

> 各平台均采用同机成对设计：普通（非保护）虚拟机与机密（受保护）虚拟机在同一台物理服务器上，使用相同的客户机用户态（x-kernel + alpine-busybox + musl 静态编译的 lmbench 3.0-a9）和相同的 lmbench 配置，各自动运行 10 轮。跨平台只比较同机比值，不比较不同服务器的绝对值，因此不同服务器之间的 CPU 型号、内存主频等硬件差异不进入比值。对于同一台服务器内两组测试的基线一致性，我们用与虚拟化机制无关的纯核心指标（整数和浮点运算延迟、L1 访问延迟与带宽）做了回溯核验：三个平台上两组各自最快一轮之比均在 1.000–1.001 之间，说明测试期间 CPU 核心频率一致；其中 N90 客户机的上述指标与主机锁频 1.9 GHz 时的测量值相差不到 0.1%。海光和 N90 两组的 DRAM 型指标（64 MB 访存延迟、STREAM 带宽）相差在 ±2% 以内，与内存配置一致相符；鲲鹏上这类指标受 VirtCCA 影响显著，无法仅凭客户机数据排除内存配置差异。据实验人员回忆，测试时宿主机侧使用 `taskset` 将 vCPU 绑定到物理核，但命令未留存；内存主频和 NUMA 放置没有记录。相关一致性目前只有上述间接证据，我们将在补测中予以记录。此外，进程创建类指标（fork、exec、shell）在客户机内核中受 10 ms 调度节拍量化影响，未用于机制间比较。

可以附上 5.5 节的汇总表。如果报告中出现了海光与其他平台的绝对值比较，需要先按 6.1 节确认海光的计时基准。
## 9. 补测时需要记录的内容

每个平台、每组测试都应在宿主机和客户机上各保存一份记录：

| 类别 | 命令或内容 |
|---|---|
| 宿主机 CPU | `lscpu`；`cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_{governor,cur_freq,min_freq,max_freq}` |
| 宿主机内存主频 | `dmidecode -t memory \| grep -E 'Speed\|Configured'`（需要 root），`numactl -H` |
| 宿主机内核与机密计算固件 | `uname -a`，`cat /proc/cmdline`；海光为 CSV 固件版本，鲲鹏为 TMM/RMM 版本 |
| VMM 启动命令 | 完整的 QEMU 或 crosvm 命令行（`ps -o args= -p <pid>`），QEMU/crosvm 版本 |
| vCPU 绑核 | 每个 vCPU 线程的 `taskset -p <tid>` 或 `virsh vcpupin`；内存绑定 `numastat -p <pid>` |
| 客户机内绑核 | 确认客户机内核的 fork 会继承 CPU 亲和性（在客户机里跑 `taskset -c 0 sh -c 'taskset -p $$'` 检查子进程掩码）；如果不继承，改用单 vCPU 客户机，或让各组 vCPU 数相同 |
| 内存后端 | 是否使用大页（`-mem-path`、`memory-backend-*`），宿主机 THP 设置 |
| 客户机 | x-kernel 提交号和 defconfig；启动日志（含 `TSC frequency` 行）；`nproc` 或 `/proc/cpuinfo`；`autorun.sh` 副本 |
| 测试控制 | 两组测试之间的间隔，是否在同一次开机内，宿主机后台负载 |

建议把这些信息随结果目录一起入库，格式参照 N90 主机侧测试的 `*-summary.txt`。

文档版本：2026-09-29。所有数字都可用 `python3 scripts/check-vm-baseline.py` 从 `results/` 下的原始日志复算。
