# KVM / pKVM 性能开销实验设计（简要）

> 📌 **状态（2026-06-04）**：本文是 day-1 的实验设计简要版，描述最初 5-env 对照设计。
> Day-3 实际**pivot 到 4-config 主机对照**（`kvm-arm.mode` = none/nvhe/vhe/protected
> × noLSM），跳过了 guest 维度。
>
> **本仓库中 guest 相关工件已清理**（`configs/CONFIG.{kvm,pkvm}-guest`、
> `bench-in-guest.sh`、`guest/launch-guest.sh`、`guest/mkrootfs.sh`）——
> 下面 §"五个对照环境" / §"vCPU 拓扑" 等 guest 段落作为 day-1 设计存档保留，
> 但相关脚本/配置不再随仓库分发。真正的 guest 测试逻辑在另一个仓库。
>
> **最终成果在 [`n90-kvm-host/`](n90-kvm-host/)**：
> - [`README.md`](n90-kvm-host/README.md)、[`SUMMARY.md`](n90-kvm-host/SUMMARY.md)
> - [`lmbench-N10-4config.xlsx`](n90-kvm-host/lmbench-N10-4config.xlsx)（pkvm 用 try2 数据）
>
> 关键 pkvm finding（v4 终版）：
> - **lat_mmap 大段 +42%**（stage-2 表建立成本，try1 + try2 一致 ✓）
> - **lat_mem_rd_rand +3-7%**（每次 TLB miss 多一层 stage-2 walk，try2 + standalone 一致 ✓）
> - try1 曾观察到的"快 17-33%"已识别为**一次性 stochastic outlier**，同配置 try2 完全没复现

## 目标

在 aarch64（Phytium D3000M）上量化 **KVM** 和 **pKVM**（特别是 protected guest）相对裸机的运行时开销，并尽量把差异归因到具体机制（stage-2 walk、EL2 trap、bounce buffer 等）。

## 硬件

- Phytium D3000M，8 核分两 cluster（cluster 0: cpu0–3；cluster 1: cpu4–7），每 cluster 1 大核（2.9 GHz）+ 3 小核（1.9 GHz）
- 所有核 `CPU part = 0x862`，pilot 实测同频率下大小核数据 ±2% 内 → 微架构等同，仅频率/binning 不同
- 已确认 host kernel cmdline 含 `kvm-arm.mode=protected`，pKVM 栈完整可用（crosvm + pvmfw + signed rootfs 都在 `/home/test/pvm/`）

## 五个对照环境

| ENV_TAG          | 配置 |
|------------------|------|
| `baremetal`      | 重启时去掉 `kvm-arm.mode=protected`，作为绝对零点 |
| `pkvm-host`      | 当前默认配置，guest idle，量"EL2 常驻"成本 |
| `kvm-guest`      | crosvm 起 guest，host 仍在 protected 模式但 guest 不加 `--protected-vm` |
| `pkvm-guest-np`  | crosvm protected 模式，但 guest 不申请保护 |
| `pkvm-guest`     | crosvm `--protected-vm`，完整 pKVM 保护 guest |

## 控制变量（按重要性）

### 软件栈：所有层完全一致
- **同一 kernel 二进制**：自编 `6.6.30+`，**host 和 guest 共用同一份 vmlinuz**（已确认该 kernel 同时含 host pKVM 支持 + protected guest 支持：`pvmfw.bin` extra firmware + `SERIAL_PKVM_PL011` + 全套 `VIRTIO_*` 内建）。差异只允许出现在 cmdline 和 rootfs 上。
- **同一 VMM**：所有 guest 都用 crosvm（KVM guest 也用 crosvm，不用 QEMU），消除 VMM 实现差异
- **同一 rootfs**：read-only squashfs + tmpfs overlay，三套 guest 共用；pKVM 那份只是外面包了签名 wrapper，字节一致
- **同一 lmbench 二进制**：host 上编一份，scp 到所有 guest，不在 guest 重编
- **同一 glibc / coreutils / shell**：从基础镜像继承
- **同一 clocksource**：所有环境必须是 `arch_sys_counter`（不能是 kvm-clock），否则"尺子"不同

### 硬件 / 内核运行时（由 `prepare-host.sh` 自动处理）
- 所有核锁定 **1.9 GHz**（小核上限，全核都能达到），`performance` governor
- 关 THP、关 ASLR、禁深 cpuidle
- 启动 rpcbind（lat_rpc 需要）
- guest 内单独的 `prepare-guest.sh`（待写）：guest 里 THP/ASLR/clocksource、关掉 snapd/cron/chrony 等 daemon。**注意：不把 /tmp 改成 tmpfs**——`BENCHMARK_FILE` 需要 `FILE=/tmp/lmb_file` 落在 virtio-blk 上才能测出 pKVM bounce buffer 成本

### vCPU 拓扑
- guest 配 **2 vCPU**，host 端 `taskset -c 0,1 crosvm ...` 钉到同 cluster 两个小核
- 关掉 virtio-balloon、virtio-rng、virtio-net（loopback 测试不需要网卡）；只留 virtio-blk + virtio-console
- 控制通道走串口，**不用 SSH**（sshd 后台活动会污染纳秒级测量）

## Benchmark 选择

直接调 lmbench 自己的 `scripts/lmbench` + 我们写的 CONFIG，不走 `make results`（后者要交互式 config-run 而且每项只跑一次没方差）。当前活跃配置只有 `configs/CONFIG.host`（day-1 原计划还有 `CONFIG.kvm-guest` / `CONFIG.pkvm-guest`，pivot 后已删）。

**策略：跑完整 lmbench**（等价 `make rerun` 开 `BENCHMARK_OS=YES + BENCHMARK_HARDWARE=YES`）。每类都开，只刻意排除三项：

- **`DISKS=""`** —— 裸块设备 benchmark（`disk`）会写设备，太危险，按需单独跑
- **`REMOTE=""`** —— 远程网络引入物理网卡 + 链路变量，跨主机不在 scope
- **`NETWORKS=""`** —— `lat_select` 的 tcp 变体跳过；`file` 变体仍跑

### 重点关注的项目

| benchmark | 看什么 |
|---|---|
| `lat_syscall null/read/write/stat/fstat/open` | EL0↔EL1 trap 成本 |
| `lat_sig install/catch/prot` | 信号 + mprotect |
| `lat_proc fork/exec/shell` | fork 触发 stage-2 PTE 分配 |
| `lat_ctx` 6×8 网格 | 上下文切换 ± cache 污染（pKVM 关键） |
| `lat_pagefault / lat_mmap` size 扫 | minor fault，stage-2 PTE 路径 |
| `lat_select -n {10,100,250,500}` | per-syscall vs per-fd 成本 |
| `lat_udp/tcp/connect/rpc localhost` | 协议栈 + virtio + pKVM share/unshare |
| `bw_tcp` size 扫 | **画 lat vs size 斜率 → pKVM bounce 每字节成本** |
| `lat_mem_rd` 多 stride + `-t` | 真 DRAM 延迟需 stride ≥ 4KB |
| `tlb` | **pKVM 关键**：stage-2 walk 挤占 TLB |
| `bw_file_rd / lmdd / lat_fs` | **virtio-blk bounce buffer 的主战场**；要求 `FILE`/`FSDIR` 在真实块设备 FS 上（不能 tmpfs） |
| `par_mem / stream / STREAM2 / lat_ops / par_ops` | sanity check，三套环境应基本一致；不一致 → 频率锁/绑核出错 |
| `bw_mem` 八种 flavor | 主要测 libc memcpy 变体；和 `make rerun` 完整对齐

## 迭代和统计

- 每环境跑 **10 iter**，每 iter 完整 lmbench 套件，单 iter 约 25–35 min
- 总预算：5 环境 × 2 core × 10 iter ≈ **10–14 小时**，过夜跑
- 解析器 `parse-lmbench.py` 把 lmbench 文本报告转成长表 CSV
- 下游统计：按 `(env, core, bench, variant)` group，算 median + MAD，配对比较用每 iter 配对差
- pilot 已验证 MAD/median < 1.4%，**不做 drop_caches**（清缓存反而放大方差）

## 一键执行

```bash
# host
ENV_TAG=pkvm-host CORES=0,3 ITERS=10 ./bench.sh
```

> guest 命令行原本是 `ENV_TAG=…-guest CONFIG=configs/CONFIG.…-guest ./bench.sh --no-prep`，
> 配置文件 + bench-in-guest 已随 day-3 pivot 一起从本仓库移除。

每次跑完产物：
- `results/<env>-cpu<N>-iter{1..10}.txt`：lmbench 原始报告
- `results/<env>-cpu<N>.csv`：解析后长表
- `results/<env>-<timestamp>-summary.txt`：kernel / cmdline / 频率快照

## 当前进展（2026-06-04 终版）

- ✅ 实验框架代码完整
- ✅ Pilot 验证 + day-1 / day-2 中间 finding
- ✅ Day-3 完成 4-config（kvmoff / nvhe / vhe / pkvm）× N=10 干净对照采集
- ✅ standalone 单测验证 pkvm "快 17-33%" 是 sequence-dependent 假象
- ✅ pkvm try2 重跑确认 try1 是 stochastic outlier
- ✅ 全套报告 + 综合 xlsx 在 [`n90-kvm-host/`](n90-kvm-host/)
- ⏸ 后续工作（pVM 测试、PMU counter 验证、Apple Silicon 对比）见
  [`SUMMARY.md` 第 8 节](n90-kvm-host/SUMMARY.md)

## 详细文档

- **最终 findings**：[`n90-kvm-host/`](n90-kvm-host/)
  - 总体方法论：[`README.md`](n90-kvm-host/README.md)
  - 跨配置综合：[`SUMMARY.md`](n90-kvm-host/SUMMARY.md)
  - pkvm mmap +42% 专题：[`pkvm-mmap-overhead-analysis.md`](mmap/pkvm-mmap-overhead-analysis.md)
  - standalone 验证：[`standalone-memory-bench-validation.md`](n90-kvm-host/standalone-memory-bench-validation.md)
- 实验设计完整版（英文）：[`EXPERIMENT.md`](EXPERIMENT.md)
- 管线内部细节：[`PIPELINE.md`](PIPELINE.md)
- upstream 改动说明：[`PATCHES.md`](PATCHES.md)
- 中间过程 findings：[`findings-2026-06-01.md`](findings-2026-06-01.md)、[`findings-2026-06-02.md`](findings-2026-06-02.md)