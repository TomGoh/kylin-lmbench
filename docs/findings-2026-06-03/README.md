# Phytium FTC862 上 ARM64 KVM 4-模式 Host 性能特征

**Date**: 2026-06-03
**Target**: N90 (Phytium FTC862, 8 cores, KylinOS V11)
**Kernel**: `6.6.0-73-generic` (KylinOS 自构建，内置 pKVM)

> **🚀 想直接动手复现？** 去 [`QUICK-START.md`](QUICK-START.md) ——
> N90 上端到端 cookbook，从编译到拿到 xlsx 全程 ~7.5 小时。
> 本文是 reference（为什么这么做），quick-start 是 recipe（怎么做）。

## 1. 实验目标

本报告系统刻画 **ARM64 虚拟化主机自身**（不跑客户机）在以下 4 种 KVM 模式下的 lmbench 微基准表现：

| 模式 | cmdline | 主机内核运行的特权级 | EL2 状态 |
|------|---------|----------------------|---------|
| **KVM-off**    | `kvm-arm.mode=none`      | EL1 | 空（不装载任何 hypervisor 代码） |
| **VHE**        | `kvm-arm.mode=vhe`       | **EL2**（Virtualization Host Extensions） | 主机内核自己就在 EL2 |
| **NVHE**       | `kvm-arm.mode=nvhe`      | EL1 | EL2 只放一个 hypervisor 切换桩 |
| **pKVM**       | `kvm-arm.mode=protected` | **EL2**（VHE 之上） | pKVM hypervisor 与主机内核共驻 EL2 |

目的是回答三个互相独立的问题：

1. **VHE 是不是真比"只在 EL1 跑"的主机快？** 如果是，差多少？为什么？
2. **NVHE 之所以慢，是因为多了 EL1↔EL2 切换，还是因为主机内核被压在 EL1？** —— `kvmoff`
   提供了"内核住在 EL1、但完全不进出 EL2"的对照组，可以拆解这个混淆。
3. **pKVM 在主机快速路径上是不是真的 0 开销？** ——
   pKVM 主要为客户机的保护态付出代价，主机自己被打扰多少。

## 2. 为什么这个对比有意义

公开文献中"pKVM vs 朴素 KVM"对比通常用 NVHE 当朴素基线；但 ARMv8.1+ 的实际默认是 VHE。
如果 NVHE 本身比 VHE 慢，那把"pKVM vs NVHE"的差解读成"pKVM 的开销"就是误归因。

要彻底分解这种混淆，本报告做 **4 配置等价对照** —— 同一台机器、同一内核二进制、同一份 lmbench
构建产物、同一绑核、同一频率、同一 LSM 状态（全部 noLSM）—— **只有 cmdline 的 `kvm-arm.mode=`
值不同**。任何性能差只能来自 KVM 模式本身。

## 3. ARM64 Exception Level 速览（给非 ARM 背景读者）

| EL  | 角色 |
|-----|------|
| EL0 | 用户态进程 |
| EL1 | 传统 Linux 内核态 |
| EL2 | hypervisor（KVM、Xen 等） |
| EL3 | secure firmware（TF-A） |

**VHE**（ARMv8.1 引入）让主机 Linux 内核**直接**住在 EL2，同时复用 EL2 的页表/异常向量，
syscall 从 EL0 直接进 EL2 而不是 EL1。这是为了让"装了 KVM 的主机"在没跑客户机时也跑得快。

**NVHE**（传统模式）主机内核仍在 EL1，KVM 只在 EL2 装一个最小切换桩，只有进/出客户机时才进 EL2；
主机 syscall 路径完全不进 EL2。

**Protected (pKVM)** 是 Google/Android 推的隔离强化版：在 VHE 基础上加一层保护，让主机也
不能读客户机内存。主机内核仍在 EL2。

## 4. 影响微基准的额外变量及处理

lmbench 的 syscall 快速路径单次开销在 100 ns 量级。任何能给 syscall 路径多加时钟周期的因素
（LSM 钩子、audit、cache 未命中、TLB 未命中、时钟中断、动态调频）都会污染
"KVM 模式之间的差异"信号。下面列出已识别的所有干扰源、它们对性能的影响、以及本实验如何
把它们钳死。

### 4.1 LSM (Linux Security Module)

LSM 是内核在每个安全相关操作（syscall 入口、文件打开、ptrace、bind 等）插入的钩子链。
**每多挂一个可堆叠的 LSM 模块，每个被钩住的操作就多走一遍回调链**。syscall 入口尤其敏感。

KylinOS V11 默认 LSM 栈（从 `cat /sys/kernel/security/lsm` 看）：

| 名字 | 作用 | 实测 syscall 影响 |
|------|------|-------------------|
| `capability` | POSIX capabilities，Linux 内置，不可禁用 | 已含在基线，无法分离 |
| `kycp` | KylinOS 的控制策略模块，限制特定路径访问 | 在所有配置中常在，作为公共基线 |
| `ksaf` | KylinOS Safety LSM——麒麟自研的高合规 LSM，每次 syscall 多查一遍标签库 + 一次 netlink 通信 | **每次 syscall 加 ~64 ns ≈ 1.9 GHz 下约 120 周期** |
| `bpf` | 基于 BPF 的 LSM 钩子（CO-RE 加载的 BPF 程序可以挂在 LSM 钩点上）| 视已加载的 BPF 程序数量，单次 syscall 加 ~10-40 ns |

本实验把所有 4 个配置的 LSM 栈固定为 `capability,kycp`（通过 cmdline `lsm=` 把 LSM 显式置空，
让内核只保留两项内置且不可禁的模块）。这样 4 个配置之间 LSM 开销项相等且小。

**为什么不直接 `lsm=capability`？** `kycp` 在该内核里是内置项，无法剔除；保留它对所有
配置一致，不污染对比。

### 4.2 audit framework

`audit=1` 时 Linux 内核 audit 子系统会跟用户态的 `auditd` 协作：syscall 入口往环形缓冲里塞
一条 audit 记录，守护进程读出去做规则匹配。即便没有 audit 规则（`auditctl -l` 0 条），
**audit 子系统本身的开启检查 + 写环形缓冲仍然每次 syscall 加 ~10-20 ns**。

本实验所有配置都设 `audit=0`，整个框架完全旁路。

### 4.3 THP (Transparent Huge Pages)

THP=`always` 或 `madvise` 时，khugepaged 后台扫描可能在测试进行时把基础页提升成 2 MB
大页，引起：
- 测试过程中 page fault 行为突变（minor 在提升后变为不再缺页）
- TLB 命中率突变（从 64 项 × 4 KB 跳到单项覆盖 2 MB）
- lat_pagefault 测出来比空闲基线慢得多

`THP=never` 把行为锁死成"只用 4 KB 基础页"，让 lat_pagefault / lat_mem_rd / bw_mem 之间不出现
随机突跳。

### 4.4 ASLR (Address Space Layout Randomization)

`randomize_va_space=2`（默认）时，每次 fork 产生不同的虚拟地址布局，导致：
- lat_proc/fork 的页表拷贝路径长度不一（不同地址区段落在不同缓存行）
- lat_pagefault 的 vma 查找在红黑树上走不同深度
- 5 次重复之间 MAD% 被 ASLR 抖动放大

`randomize_va_space=0` 让每次 fork 拿到固定布局，微基准之间的方差只剩硬件噪声。

### 4.5 CPU 频率 / 调速器 / 空闲态

DVFS（动态频率调整）是 syscall 微基准的头号敌人。调速器 `ondemand`/`powersave` 在空闲到忙的
跳变前 100 µs 还可能停在低频，把"预热"时段引入计时区间。

本实验：
- 调速器锁定 `performance`（永远跑在最高频率）
- 所有 CPU 核用 `cpupower frequency-set -f 1900MHz` 钉死 1.9 GHz（不让 turbo / 动态调频漂移）
- 关掉深度 cpuidle 状态（只留 state0 轮询），避免唤醒延迟渗入 lat_sig

### 4.6 CPU 绑核

不绑核时，调度器会在不同核之间迁移测试进程。每次迁移：
- L1/L2 缓存全冷
- ITLB/DTLB 全冷
- 跨集群迁移时 LLC 也冷
- 测出来的"syscall 延迟"可能是真实值的两倍

本实验用 `taskset -c 0` 把测试进程钉在 cpu0。所有 4 个配置都用 cpu0，绝对一致。

### 4.7 KYSEC 用户态守护进程

`ksaf-label-manager`、`kyseclogd`、`ksaf-devctl-sync-daemon`、`kysec-scene-init` 等
是 KylinOS 安全合规体系的用户态一侧。它们会：
- 定期 stat / 扫描根文件系统给文件加标签
- 周期性向 netlink / socket 写 audit / 日志消息
- 通过 inotify 监视目录变动

即使关掉 `ksaf` LSM 模块，这些守护进程仍会被 systemd 拉起、跑后台 I/O，对 cpu0 上的
测试制造噪声。

`quiet-host.sh` 用 `systemctl mask` 把这些守护进程全关掉并阻止重启。脚本含
`NEVER_STOP_RE` 守护，确保**不**动 NetworkManager / sshd / networking / wicked / netplan
——因为停了这些会直接掉 SSH，远端机器再无法操作。

### 4.8 桌面 + Kylin 后台服务全面禁用（持久化）

`quiet-host.sh` 在 day-2 用 `systemctl mask` 关停的几个守护进程只是表层。day-3
实测发现 N90 还有近 30 个 Kylin/UKUI 后台服务在跑，其中包括两个 CPU 重量级
进程 —— `kytensor`（Kylin triton AI 推理服务）和
`kylin-ai-cryptojacking-detect`（AI 挖矿检测引擎），都会偶发吃 cpu0。

**一次性持久化操作**（一旦执行，mask 状态跨 reboot 保留，无需每次重复）：

```bash
sudo systemctl set-default multi-user.target   # 不再启动桌面
NOISY="
  com.kylin.kysdk.SyncConfig
  dbus-com.kylin.kysdk.applicationsec
  dbus-com.kylin.secriskbox.system
  kyfs-fuse
  kylin-ai-cryptojacking-detect
  kylin-boxadm-daemon
  kylin-core-dump-monitor
  kylin-daq
  kylin-endisk-daemon
  kylin-os-manager-driver-acquirer
  kylin-printer-applet-dbus
  kylin-process-manager-daemon
  kylin-process-resource-manager-daemon
  kylin-unattended-upgrades
  kysdk-conf2
  kysdk-dbus
  kysdk-systime
  kytensor
  ukui-bluetooth
  ukui-media-control-mute-led
  lightdm
  accounts-daemon
  packagekit
  colord
  boltd
  udisks2
  ModemManager
  upower
"
for svc in $NOISY; do
  sudo systemctl stop  "${svc}.service" 2>/dev/null
  sudo systemctl mask  "${svc}.service" 2>/dev/null
done
```

**保留运行**（网络相关，停掉就掉 SSH）：
- `NetworkManager.service`
- `sshd.service`
- `kylin-nm-sysdbus.service`
- `nm-enhance-optimization.service`
- `systemd-*` 核心
- `dbus.service`、`polkit.service`

### 4.9 内核 cmdline 中的其它参数（不动）

`quiet`、`splash`、`loglevel=0`：减少 printk 噪声。
`systemd.unified_cgroup_hierarchy=1 psi=1`：开启 cgroup v2 与 PSI 统计；保持主机一致。
`resume=UUID=...`：休眠分区指向；本实验流程内不触发。

### 4.10 影响因子统一表

| 变量 | 该实验所有 4 个配置的值 | 控制手段 |
|------|------------------------|----------|
| LSM 栈 | `capability,kycp` | cmdline `lsm=` |
| audit | 关 | cmdline `audit=0` |
| THP | `never` | `prepare-host.sh` 写 `transparent_hugepage/enabled` |
| ASLR | 0 | `prepare-host.sh` 写 `randomize_va_space` |
| CPU 频率 | 锁 1900 MHz | `prepare-host.sh` + `cpupower` |
| 调速器 | `performance` | `prepare-host.sh` |
| cpuidle 深度 | 仅 state0 | `prepare-host.sh` |
| 绑核 | cpu0 | `taskset -c 0`（bench.sh 自动加） |
| KYSEC 守护进程 | 关停（systemctl mask） | `quiet-host.sh` |
| 桌面守护进程 | 关停（systemctl mask） | `quiet-host.sh` |
| 桌面 target | `multi-user.target`（无 GUI） | `systemctl set-default multi-user.target` |
| Kylin AI / 杂项 daemon | 28 项全 mask | 见 §4.8 |

**唯一自由变量**：`kvm-arm.mode` ∈ {none, vhe, nvhe, protected}。

## 5. 实验矩阵

四个配置，唯一变量是 `kvm-arm.mode`。其它一切统一：

| 项目 | 值 |
|------|-----|
| 硬件 | Phytium FTC862，8 核 |
| 内核 | `6.6.0-73-generic`（KylinOS） |
| CPU 频率 | 锁 1900 MHz，调速器 `performance` |
| THP | `never` |
| ASLR | 关 |
| LSM | `capability,kycp`（无 ksaf、无 bpf、无 audit） |
| KYSEC 用户态守护进程 | 关停（quiet-host.sh） |
| 绑核 | `taskset -c 0` |
| lmbench 配置 | `CONFIG.host`（开启全部 BENCHMARK_*） |
| N | **10 次重复**（前 1-2 iter 是暖机，使用 5 次的话部分 chrdev syscall 会被暖机污染中位数） |

**LSM 强制 `noLSM` 的原因**：KylinOS 默认带 `ksaf` LSM，每次 syscall 大约多 ~64 ns（1.9 GHz
下约 120 周期）。任何 4-模式对比若不去掉它，模式间的差就被 LSM 噪声淹没。

## 6. cmdline 切换机制

KylinOS 用 ostree 管理部署，cmdline 由两部分合成：
1. ostree 维护的 BLS 条目里的 `options` 字段（持久化到 `/boot/loader/entries/ostree-*.conf`）
2. grub 静态变量 `GRUB_CMDLINE_LINUX_DEFAULT` + `GRUB_CMDLINE_LINUX_SECURITY`（来自
   `/etc/default/grub`，通过 `update-grub` 编进 `/boot/loader/grub.cfg`）

由于内核 cmdline 解析"后写优先"（last-occurrence-wins），如果 grub 静态变量带了
`lsm=ksaf,bpf audit=1` 而追加在 ostree 的 `lsm=` 后面，静态值会反客为主。

**解决**：本报告**修改 `/etc/default/grub` 把 `GRUB_CMDLINE_LINUX_SECURITY` 设为空字符串**
（备份在 `/etc/default/grub.bak-day3`），让 ostree set-kargs 成为 cmdline 唯一权威来源。

每个配置的切换命令长这样：

```bash
sudo ostree admin instutil set-kargs \
  --import-proc-cmdline \
  --replace=kvm-arm.mode=<X> \
  --replace=lsm= \
  --replace=audit=0
sudo update-grub
sudo reboot
```

`--import-proc-cmdline` 从当前 `/proc/cmdline` 起步；`--replace=键=值` 覆盖该键现有的值；
`--replace=键=`（值为空）合法，把该键设为空值。

## 7. 4 个配置的子报告

| 文档 | 内容 |
|------|------|
| [`kvmoff.md`](kvmoff.md) | `kvm-arm.mode=none` —— KVM 完全不初始化，主机纯 EL1 |
| [`vhe.md`](vhe.md) | `kvm-arm.mode=vhe` —— 主机内核住在 EL2 |
| [`nvhe.md`](nvhe.md) | `kvm-arm.mode=nvhe` —— 主机内核在 EL1，EL2 只有切换桩 |
| [`pkvm.md`](pkvm.md) | `kvm-arm.mode=protected` —— 主机内核在 EL2，再加 pKVM 保护层 |

每个子文档独立自给：实验环境、配置、执行、结果。

## 8. 跨配置综合分析

汇总和最终结论在 [`SUMMARY.md`](SUMMARY.md)（待全部 4 个配置跑完后填入）。
跨配置分析将定量回答第 1 节列的三个问题，并对 §4 列出的影响因子做"如果没钳死会怎样"的反事实
推演。

## 9. 文件清单

```
docs/findings-2026-06-03/
├── README.md                   # 本文件
├── kvmoff.md                   # 配置 1
├── vhe.md                      # 配置 2
├── nvhe.md                     # 配置 3
├── pkvm.md                     # 配置 4
└── SUMMARY.md                  # 跨配置综合分析

results/n90-day3/
├── n90-kvmoff-noLSM-full-cpu0.csv
├── n90-kvmoff-noLSM-full-cpu0-iter{1..5}.txt
├── n90-vhe-noLSM-full-cpu0.csv
├── ...同上...
├── n90-nvhe-noLSM-full-cpu0.csv
├── ...
└── n90-pkvm-noLSM-full-cpu0.csv
```

## 10. 复现要点

```bash
# 在 N90 上
cd /root/lmbench-3.0-a9
make build
sudo cp /etc/default/grub /etc/default/grub.bak-day3
sudo sed -i 's|^GRUB_CMDLINE_LINUX_SECURITY=.*|GRUB_CMDLINE_LINUX_SECURITY=""|' /etc/default/grub
sudo update-grub

for mode in none vhe nvhe protected; do
  sudo ostree admin instutil set-kargs --import-proc-cmdline \
    --replace=kvm-arm.mode=$mode --replace=lsm= --replace=audit=0
  sudo reboot
  # ... 等 SSH 重连 ...
  sudo bash prepare-host.sh
  sudo bash quiet-host.sh
  CORES=0 ITERS=5 CONFIG=configs/CONFIG.host \
    ENV_TAG=n90-${mode}-noLSM-full ./bench.sh --no-prep
done

# 恢复主机原 cmdline 状态
sudo cp /etc/default/grub.bak-day3 /etc/default/grub
sudo update-grub
sudo ostree admin instutil set-kargs --import-proc-cmdline \
  --replace=kvm-arm.mode=none --replace=lsm=ksaf,bpf --replace=audit=1
sudo reboot
```
