# N90 V10 Host mmap-only 四模式复测报告

日期：2026-06-09  
目标设备：N90 / Phytium FTC862 / Kylin V10 SP1  
测试对象：Host 侧 mmap 相关 lmbench 项，不运行 guest  
测试模式：KVM-off / VHE / NVHE / pKVM  

## 1. 结论摘要

这次在 N90 的 Kylin V10 SP1 上，单独复测了 Host 侧 mmap 相关 lmbench 项。实验分成两轮：

- 第一轮使用前一版 `6.6.30+ #4` 内核，完成 KVM-off / VHE / NVHE / pKVM 四模式对照。
- 第二轮使用原 C 实现 pKVM 的 `6.6.30-pkvm-c+ #6` 内核，重新完成 KVM-off / VHE / NVHE / pKVM 四模式对照，用于排查前一轮是否是 Rust pKVM 实现导致异常。

最终结果显示：

- KVM-off、VHE、NVHE 的 Host `lat_mmap` 基本重合。
- pKVM 的 Host `lat_mmap` 明显变慢，且随映射大小增加，开销稳定到约 `+84%~85%`。
- C 实现 pKVM 内核完整复现了同样现象；C pKVM 与前一版 pKVM 的 64 MB `lat_mmap_precise` 只差 `-0.16%`。
- 普通 mmap read bandwidth 没有出现同等级别下降，因此问题集中在“建立/拆除映射 + 首次触摸”路径，不是整体 CPU 频率、绑核或内存带宽异常。
- 原生 raw `lat_mmap` / `bw_mmap_rd` / `bw_mmap_rd_o2c` 直接调用 lmbench 原始二进制和原始参数，只额外增加绑核和外层重复收集；`lat_mmap_precise` 是核心语义一致的 ns 精度复核工具。

第一轮 `6.6.30+ #4` 64 MB 精测结果：

| mode | precise `lat_mmap` median |
|---|---:|
| KVM-off | 443.084 us |
| VHE | 441.221 us |
| NVHE | 441.187 us |
| pKVM | 816.318 us |

pKVM 相对 KVM-off：`+84.24%`。  
pKVM 相对 VHE：`+85.01%`。  
pKVM 相对 NVHE：`+85.03%`。

第二轮 C pKVM 内核 `6.6.30-pkvm-c+ #6` 64 MB 精测结果：

| mode | precise `lat_mmap` median |
|---|---:|
| KVM-off | 442.237 us |
| VHE | 442.533 us |
| NVHE | 440.190 us |
| pKVM | 814.996 us |

C pKVM 相对 KVM-off：`+84.29%`。  
C pKVM 相对 VHE：`+84.17%`。  
C pKVM 相对 NVHE：`+85.15%`。

因此，当前最稳妥的结论是：

> 在 N90 / Kylin V10 SP1 上，Host 侧 `lat_mmap` 的大幅开销来自 pKVM protected-mode 路径本身；它不是 Rust pKVM 实现独有的问题。两轮四模式数据都显示，非 pKVM 基线重合，而 pKVM 在大尺寸 mmap 上稳定慢约 `84%~85%`。

## 2. 实验环境

### 2.1 N90 系统

N90 系统与内核：

```text
OS: Kylin V10 SP1
LSM: capability,kysec,box
```

本报告包含两轮内核：

| 轮次 | 内核 | 目的 |
|---|---|---|
| 第一轮 | `Linux kylin-pc 6.6.30+ #4 SMP Tue Jun 9 14:08:42 CST 2026 aarch64` | V10 四模式 mmap-only 初始复测 |
| 第二轮 | `Linux kylin-pc 6.6.30-pkvm-c+ #6 SMP Tue Jun 9 16:47:01 CST 2026 aarch64` | 原 C 实现 pKVM 内核复测，排查 Rust pKVM 实现因素 |

四个模式的启动状态判据如下：

| mode | cmdline / dmesg 判据 |
|---|---|
| KVM-off | `kvm-arm.mode=none`; dmesg: `KVM disabled from command line` |
| VHE | cmdline 未显式带 `kvm-arm.mode`; dmesg: `VHE mode initialized successfully` |
| NVHE | `kvm-arm.mode=nvhe`; dmesg: `Hyp mode initialized successfully` |
| pKVM | `kvm-arm.mode=protected` |

### 2.2 变量控制

所有模式都按同一套条件执行：

```text
benchmark core: cpu0
iterations: N=10
CPU governor: performance
CPU frequency: all CPUs locked to 2100000 kHz
THP: never
ASLR: 0
cpuidle: cmdline already has cpuidle.off=1; script also tries to disable deep idle states if present
backing file: /tmp/lmb_mmap_file for raw lmbench; /tmp/lmb_precise_<size>MB.dat for precise run
```

保留网络/SSH 相关服务，避免断开远程连接：

```text
NetworkManager
ssh
wpa_supplicant
systemd-resolved
dbus
```

尽量停止桌面、打印、蓝牙、更新、安全/杀毒、Kylin 后台服务。V10 有些服务会被 systemd 重新拉起，所以每轮测试前都检查进程状态；对网络服务不做 stop。

## 3. 本机编译与推送

N90 被当作“只测试”设备使用，不在 N90 上编译。编译在本机完成。本机也是 aarch64，因此产物可直接在 N90 上运行。

本机编译命令：

```bash
cd /home/jose/kylin-lmbench
make build
gcc -O2 -o bin/aarch64-Linux/lat_mmap_precise src/lat_mmap_precise.c
```

本机生成并推送到 N90 的最小文件集：

```text
bench-mmap.sh
scripts/precise-mmap-bench.sh
scripts/prepare-host-v10-mmap.sh
bin/aarch64-Linux/lat_mmap
bin/aarch64-Linux/bw_mmap_rd
bin/aarch64-Linux/lmdd
bin/aarch64-Linux/lat_mmap_precise
```

N90 目录：

```text
/home/kylin/kylin-lmbench-mmap
```

推送命令：

```bash
ssh N90 'mkdir -p /home/kylin/kylin-lmbench-mmap/bin/aarch64-Linux \
                  /home/kylin/kylin-lmbench-mmap/scripts \
                  /home/kylin/kylin-lmbench-mmap/results'

scp -q bench-mmap.sh N90:/home/kylin/kylin-lmbench-mmap/
scp -q scripts/precise-mmap-bench.sh scripts/prepare-host-v10-mmap.sh \
       N90:/home/kylin/kylin-lmbench-mmap/scripts/
scp -q bin/aarch64-Linux/lat_mmap \
       bin/aarch64-Linux/bw_mmap_rd \
       bin/aarch64-Linux/lmdd \
       bin/aarch64-Linux/lat_mmap_precise \
       N90:/home/kylin/kylin-lmbench-mmap/bin/aarch64-Linux/
```

测试二进制 SHA256：

```text
ebca4a0de382a53df3e8e07949517524a614d870781777ccee6da5837d5ea488  lat_mmap
6e877231258a6419c1d72c359500d63b460d651a5858aa3a4c8105ae58c18d2e  bw_mmap_rd
28aeb5ef34c0b58c2a35393280ec9b1c51deb920b7d712d6b1b08f28151b5296  lmdd
b08ff5c7b724952da82bc8e2c6bd666dc5920b48cfef212bf15c0ff99f6166b2  lat_mmap_precise
```

## 4. 准备脚本

V10 不能直接复用原 V11 的 `prepare-host.sh`，因此新增了：

```text
scripts/prepare-host-v10-mmap.sh
```

脚本目标：

- 不停止网络/SSH。
- 停止桌面、Kylin 后台、更新、安全/杀毒、打印、蓝牙等无关服务。
- 锁定所有 CPU 到同一个频率。
- 关闭 THP 和 ASLR。
- 尽量把可迁移 IRQ 从测试核 cpu0 移走。

关键逻辑摘要：

```bash
TEST_CORE="${TEST_CORE:-0}"
TARGET_KHZ="${TARGET_KHZ:-auto}"

# 保留网络/SSH：
# NetworkManager / ssh / wpa_supplicant / resolved / dbus 不 stop。

# 自动选择所有 CPU 都支持的最高公共频率。
# N90 本轮为 2100000 kHz。
for maxf in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/cpuinfo_max_freq; do
  ...
done

for c in /sys/devices/system/cpu/cpu[0-9]*/cpufreq; do
  echo performance > "$c/scaling_governor"
  echo "$TARGET_KHZ" > "$c/scaling_max_freq"
  echo "$TARGET_KHZ" > "$c/scaling_min_freq"
done

echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo 0 > /proc/sys/kernel/randomize_va_space
```

每次切 mode 重启后都重新执行：

```bash
cd /home/kylin/kylin-lmbench-mmap
TEST_CORE=0 sudo -E bash scripts/prepare-host-v10-mmap.sh
```

## 5. 测试脚本

新增：

```text
bench-mmap.sh
```

该脚本只跑 mmap 相关项目：

```text
lat_mmap
bw_mmap_rd mmap_only
bw_mmap_rd open2close
lat_mmap_precise
```

所有实际 benchmark 调用都显式绑核：

```bash
taskset -c "$CORE" "$LMDD" ...
taskset -c "$CORE" "$LAT_MMAP" -P 1 "$sz" "$FILE"
taskset -c "$CORE" "$BW_MMAP_RD" -P 1 "$sz" mmap_only "$FILE"
taskset -c "$CORE" "$BW_MMAP_RD" -P 1 "$sz" open2close "$FILE"
```

原生 lmbench size：

```text
lat_mmap:
512k 1m 2m 4m 8m 16m 32m 64m

bw_mmap_rd / bw_mmap_rd_o2c:
512 1k 2k 4k 8k 16k 32k 64k 128k 256k 512k 1m 2m 4m 8m 16m 32m 64m
```

`lat_mmap_precise` size：

```text
0.5 1 2 4 8 16 64 MB
```

`precise-mmap-bench.sh` 也做了调整：

- 去掉 `/root/lmbench-3.0-a9` 硬编码，改为仓库相对路径。
- 支持 `CORE=0` 参数。
- 使用 `taskset -c "$CORE"` 固定测试核。

### 5.1 与 lmbench 原始方法的对齐核验

复核 `scripts/lmbench`、`src/lat_mmap.c`、`src/bw_mmap_rd.c` 和本次 `bench-mmap.sh` 后，可以把本次脚本分成两类来看。

第一类是原生 lmbench raw 数据，也就是报告里的 `lat_mmap`、`bw_mmap_rd` 和 `bw_mmap_rd_o2c`。这部分没有重写 benchmark，也没有改源码，直接调用本仓库编译出的原始 lmbench 二进制：

| 项目 | 原始 `scripts/lmbench` 调用 | 本次 `bench-mmap.sh` 调用 | 核验结果 |
|---|---|---|---|
| `lat_mmap` | `lat_mmap -P $SYNC_MAX $i $FILE` | `taskset -c "$CORE" lat_mmap -P 1 "$sz" "$FILE"` | benchmark 参数一致；本次 `SYNC_MAX=1` 等价为 `-P 1`，外层增加绑核 |
| `bw_mmap_rd` | `bw_mmap_rd -P $SYNC_MAX $i mmap_only $FILE` | `taskset -c "$CORE" bw_mmap_rd -P 1 "$sz" mmap_only "$FILE"` | benchmark 参数一致；外层增加绑核 |
| `bw_mmap_rd_o2c` | `bw_mmap_rd -P $SYNC_MAX $i open2close $FILE` | `taskset -c "$CORE" bw_mmap_rd -P 1 "$sz" open2close "$FILE"` | benchmark 参数一致；外层增加绑核 |
| backing file | `lmdd of=$FILE move=${MB}m fsync=1` | `taskset -c "$CORE" lmdd of="$FILE" move="${MB}m" fsync=1 print=0` | 文件生成方法一致；`print=0` 只影响日志输出 |

size 序列也对齐。`scripts/lmbench` 中 `$ALL` 的生成逻辑是：

```text
512 1k 2k 4k 8k 16k 32k 64k 128k 256k 512k 1m 2m 4m ... MB
```

本次 `MB=64` 时：

```text
lat_mmap:
512k 1m 2m 4m 8m 16m 32m 64m

bw_mmap_rd / bw_mmap_rd_o2c:
512 1k 2k 4k 8k 16k 32k 64k 128k 256k 512k 1m 2m 4m 8m 16m 32m 64m
```

`lat_mmap` 里，小于 512 KB 的 `$ALL` size 会因为 `src/lat_mmap.c` 的 `MINSIZE = 2 * STRIDE = 320 KB` 规则返回非有效结果；本次直接从 `512k` 开始记录，等价于保留原始 lmbench 会产生有效输出的 mmap latency 行。`bw_mmap_rd` 没有这个过滤，所以保留完整 `$ALL`。

`lat_mmap` 的核心计时代码来自 `src/lat_mmap.c`：每次 iteration 都执行 file-backed `MAP_SHARED` 的 `mmap`，按 `PSIZE=16KB` 步长触摸前 `size/N` 字节，`N=10`，然后 `munmap`。本次 raw `lat_mmap` 直接运行该二进制，因此测试方法和 lmbench 原始方法没有出入。

第二类是 `lat_mmap_precise`。它不是 lmbench 官方 raw 输出路径，而是为了避免 `lat_mmap` 在大 size 上用 `micromb()` 输出整数 us 带来的精度损失。复核 `src/lat_mmap_precise.c` 后，它与 `src/lat_mmap.c` 的核心 mmap 语义一致：

- file-backed `MAP_SHARED`，不是 anonymous/private mapping。
- `PSIZE=16KB`，`N=10`。
- 每次计时 iteration 都执行 `mmap + 触摸前 size/N 字节 + munmap`。
- backing file 也用 `lmdd` 预填，避免使用不同文件生成方式引入 page-cache 状态差异。

但它与原始 lmbench harness 有两点明确差异：

- 计时与输出不同：`lat_mmap_precise` 使用 `clock_gettime(CLOCK_MONOTONIC)` 并输出 ns/us 小数；lmbench `lat_mmap` 走 `benchmp + gettimeofday + micromb()`，大 size 输出通常是整数 us。
- repetition 控制不同：`lat_mmap_precise` 对每个 size 使用固定 iteration 数并做 10 run median；lmbench `benchmp` 会按 `ENOUGH` 自适应调整 iteration。

因此，本文中的判断边界是：

> 原生 raw `lat_mmap` / `bw_mmap_rd` / `bw_mmap_rd_o2c` 与 lmbench 本身测试方法一致，只额外加了绑核和外层重复收集；`lat_mmap_precise` 是语义等价的精度复核工具，不替代 raw 结果，而是用来确认 raw `lat_mmap` 的整数 us 输出没有掩盖或制造 pKVM 差异。

## 6. 实验过程

每个 mode 的通用流程：

1. 用户切换 mode 并重启 N90。
2. 确认启动模式。
3. 执行 V10 准备脚本。
4. 停止个别重新拉起的非网络服务。
5. 运行 mmap-only 测试。
6. 拉回 N90 上的 raw log。
7. 本地解析 CSV 和汇总。

### 6.1 mode 确认

KVM-off：

```bash
cat /proc/cmdline | grep -oE 'kvm-arm.mode=[a-z]+'
sudo dmesg | grep -i 'KVM disabled'
```

VHE：

```bash
sudo dmesg | grep -i 'VHE mode initialized'
```

NVHE：

```bash
cat /proc/cmdline | grep -oE 'kvm-arm.mode=[a-z]+'
sudo dmesg | grep -i 'Hyp mode initialized'
```

pKVM：

```bash
cat /proc/cmdline | grep -oE 'kvm-arm.mode=[a-z]+'
```

### 6.2 测试命令

KVM-off：

```bash
cd /home/kylin/kylin-lmbench-mmap
ENV_TAG=n90-v10-kvmoff-mmap CORE=0 ITERS=10 PARSE=0 RUN_PRECISE=1 ./bench-mmap.sh --no-prep
```

VHE：

```bash
cd /home/kylin/kylin-lmbench-mmap
ENV_TAG=n90-v10-vhe-mmap CORE=0 ITERS=10 PARSE=0 RUN_PRECISE=1 ./bench-mmap.sh --no-prep
```

NVHE：

```bash
cd /home/kylin/kylin-lmbench-mmap
ENV_TAG=n90-v10-nvhe-mmap CORE=0 ITERS=10 PARSE=0 RUN_PRECISE=1 ./bench-mmap.sh --no-prep
```

pKVM：

```bash
cd /home/kylin/kylin-lmbench-mmap
ENV_TAG=n90-v10-pkvm-mmap CORE=0 ITERS=10 PARSE=0 RUN_PRECISE=1 ./bench-mmap.sh --no-prep
```

`PARSE=0` 的原因：N90 只负责测试，不需要 Python 解析；raw log 复制回本地后统一解析。

## 7. 数据收集与本地分析

N90 生成的文件：

```text
/home/kylin/kylin-lmbench-mmap/results/<env>-cpu0-iter{1..10}.txt
/home/kylin/kylin-lmbench-mmap/results/<env>-mmap-<timestamp>-summary.txt
/home/kylin/kylin-lmbench-mmap/results/precise-mmap/<env>.log
```

拉回本地：

```bash
mkdir -p results/n90-v10-<mode>-mmap/precise-mmap

scp -qr 'N90:/home/kylin/kylin-lmbench-mmap/results/n90-v10-<mode>-mmap*' \
        results/n90-v10-<mode>-mmap/

scp -q N90:/home/kylin/kylin-lmbench-mmap/results/precise-mmap/n90-v10-<mode>-mmap.log \
       results/n90-v10-<mode>-mmap/precise-mmap/
```

本地解析 raw lmbench：

```bash
./parse-lmbench.py results/n90-v10-<mode>-mmap/n90-v10-<mode>-mmap-cpu0-iter*.txt \
  > results/n90-v10-<mode>-mmap/n90-v10-<mode>-mmap-cpu0.csv \
  2> results/n90-v10-<mode>-mmap/n90-v10-<mode>-mmap-cpu0-parse.err
```

四个 mode 的 parse error 都是 0：

```text
results/n90-v10-kvmoff-mmap/n90-v10-kvmoff-mmap-cpu0-parse.err: 0 lines
results/n90-v10-vhe-mmap/n90-v10-vhe-mmap-cpu0-parse.err: 0 lines
results/n90-v10-nvhe-mmap/n90-v10-nvhe-mmap-cpu0-parse.err: 0 lines
results/n90-v10-pkvm-mmap/n90-v10-pkvm-mmap-cpu0-parse.err: 0 lines
```

最终四模式汇总文件：

```text
results/n90-v10-mmap-4mode-summary.txt
```

## 8. 最终数据

### 8.1 precise lat_mmap

单位：us，表中为 N=10 median。

| size | KVM-off | VHE | NVHE | pKVM | pKVM vs KVM-off | pKVM vs VHE | pKVM vs NVHE |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 10.356132 | 10.429703 | 10.362521 | 13.438333 | +29.76% | +28.85% | +29.68% |
| 1 MB | 13.787149 | 13.699023 | 13.761465 | 19.649358 | +42.52% | +43.44% | +42.79% |
| 2 MB | 20.526078 | 20.295507 | 20.554292 | 31.348366 | +52.72% | +54.46% | +52.51% |
| 4 MB | 33.100203 | 33.382131 | 32.924943 | 56.237202 | +69.90% | +68.46% | +70.80% |
| 8 MB | 59.622910 | 59.363406 | 59.851396 | 106.872015 | +79.25% | +80.03% | +78.56% |
| 16 MB | 110.991690 | 110.677476 | 110.545133 | 205.056008 | +84.75% | +85.27% | +85.50% |
| 64 MB | 443.084233 | 441.221122 | 441.186916 | 816.317767 | +84.24% | +85.01% | +85.03% |

MAD%：

| size | KVM-off | VHE | NVHE | pKVM |
|---:|---:|---:|---:|---:|
| 0.5 MB | 1.096% | 1.631% | 1.601% | 2.523% |
| 1 MB | 0.700% | 0.888% | 0.574% | 0.480% |
| 2 MB | 1.425% | 1.967% | 1.676% | 0.973% |
| 4 MB | 2.173% | 2.908% | 2.513% | 0.683% |
| 8 MB | 1.169% | 0.902% | 0.770% | 0.412% |
| 16 MB | 0.513% | 0.259% | 0.545% | 0.434% |
| 64 MB | 0.254% | 0.191% | 0.049% | 0.082% |

### 8.2 原生 lmbench lat_mmap

单位：us，表中为 N=10 median。原生 lmbench 在较大 size 上主要输出整数 us。

| variant | KVM-off | VHE | NVHE | pKVM | pKVM vs KVM-off |
|---|---:|---:|---:|---:|---:|
| sz0.524288MB | 9.073 | 9.052 | 9.088 | 12.000 | +32.26% |
| sz1.048576MB | 13.000 | 12.000 | 13.000 | 18.000 | +38.46% |
| sz2.097152MB | 19.000 | 19.000 | 19.000 | 30.000 | +57.89% |
| sz4.194304MB | 32.000 | 32.000 | 32.000 | 56.000 | +75.00% |
| sz8.388608MB | 59.000 | 59.000 | 59.000 | 106.000 | +79.66% |
| sz16.777216MB | 110.000 | 110.000 | 110.000 | 205.000 | +86.36% |
| sz33.554432MB | 215.000 | 215.500 | 216.000 | 405.000 | +88.37% |
| sz67.108864MB | 429.000 | 428.000 | 429.000 | 807.000 | +88.11% |

### 8.3 67 MB mmap bandwidth sanity check

普通 `bw_mmap_rd` 没有出现类似 `lat_mmap` 的巨大差异：

| mode | `bw_mmap_rd` 67.11 MB | MAD% |
|---|---:|---:|
| KVM-off | 15919.610 MB/s | 0.408% |
| VHE | 15157.285 MB/s | 0.231% |
| NVHE | 14910.615 MB/s | 0.244% |
| pKVM | 14957.955 MB/s | 0.345% |

`bw_mmap_rd_o2c` 67.11 MB：

| mode | `bw_mmap_rd_o2c` 67.11 MB | MAD% |
|---|---:|---:|
| KVM-off | 6320.910 MB/s | 0.391% |
| VHE | 6301.005 MB/s | 0.367% |
| NVHE | 6276.255 MB/s | 0.253% |
| pKVM | 6161.600 MB/s | 0.521% |

## 9. 与旧 N90 4config 干净数据对比

旧数据来源：

```text
docs/n90-kvm-host/lmbench-N10-4config.xlsx
```

旧表是 N90 早先的 4config 干净对照数据，内核/系统环境与本次不同：

| 数据集 | 系统/内核 | 测试形态 | 频率 | 备注 |
|---|---|---|---|---|
| 旧 4config | KylinOS V11 / `6.6.0-73-generic` | full lmbench + precise mmap 覆盖 | 1.9 GHz | `docs/n90-kvm-host/lmbench-N10-4config.xlsx` |
| 本次 V10 | Kylin V10 SP1 / `6.6.30+` | mmap-only + precise mmap | 2.1 GHz | `results/n90-v10-mmap-4mode-summary.txt` |

因此下面对比不能解读为“只改变 pKVM mode 的 A/B”；它用于回答另一个问题：**本次 V10 结果和之前干净数据相比，pKVM mmap 信号是否同向、幅度变化在哪里。**

### 9.1 旧数据 vs 本次 V10：KVM-off 与 pKVM

单位：us，均为 `lat_mmap` precise median。size 使用 lmbench 报告里的 MiB 换算显示，例如 `67.108864 MB` 对应 precise 脚本的 64 MB。

| lmbench size | 旧 kvmoff | 新 kvmoff | 旧 pKVM | 新 pKVM | 旧 pKVM/kvmoff | 新 pKVM/kvmoff |
|---:|---:|---:|---:|---:|---:|---:|
| 0.524288 MB | 7.776 | 10.356 | 9.224 | 13.438 | +18.62% | +29.76% |
| 1.048576 MB | 11.747 | 13.787 | 14.812 | 19.649 | +26.09% | +42.52% |
| 2.097152 MB | 21.182 | 20.526 | 27.593 | 31.348 | +30.27% | +52.72% |
| 4.194304 MB | 36.222 | 33.100 | 49.105 | 56.237 | +35.57% | +69.90% |
| 8.388608 MB | 65.812 | 59.623 | 92.243 | 106.872 | +40.16% | +79.25% |
| 16.777216 MB | 123.377 | 110.992 | 175.340 | 205.056 | +42.12% | +84.75% |
| 67.108864 MB | 498.153 | 443.084 | 709.236 | 816.318 | +42.37% | +84.24% |

### 9.2 这个对比说明什么

第一，**方向一致**。旧 4config 和本次 V10 都显示 pKVM 单独拉高 Host `lat_mmap`，而非 pKVM 基线之间差异很小。

第二，**本次 V10 的 pKVM 相对开销显著更大**。旧数据在 16 MB / 67 MB 上约 `+42%`；本次 V10 在 16 MB / 64 MB 上约 `+84%~85%`，几乎翻倍。

第三，差距扩大不是简单的“本次机器整体更慢”。看 67 MB：

| mode | 新/旧绝对值比例 |
|---|---:|
| kvmoff | 0.889x |
| VHE | 0.885x |
| NVHE | 0.885x |
| pKVM | 1.151x |

也就是说，本次 V10 的非 pKVM 大尺寸 `lat_mmap` 基线反而比旧数据快约 `11%`，但 pKVM 绝对延迟比旧数据慢约 `15%`。这说明差距扩大主要来自 pKVM 路径本身，而不是 CPU 频率或普通 mmap 基线变慢。

第四，小尺寸上新旧数据变化较复杂。0.5 MB / 1 MB 上本次非 pKVM 基线比旧数据更慢，这可能与 V10 的 LSM 栈、后台状态、计时粒度、文件缓存状态或内核实现差异有关。但从 2 MB 以上，非 pKVM 基线基本转为更快，而 pKVM 仍然更慢；大尺寸段的结论更稳。

### 9.3 与旧数据对比后的判断

旧数据已经支持“pKVM 对 Host `lat_mmap` 有明显开销”，但幅度约为 `+42%`。本次 V10 数据把这个信号放大到 `+85%` 左右，并且 KVM-off / VHE / NVHE 三个基线仍然互相重合。

当前最合理的表述是：

> 两套 N90 数据都显示 pKVM 会显著增加 Host 侧 `lat_mmap` 建映射开销；在旧 V11 / `6.6.0-73` 数据中，大尺寸开销约 `+42%`，而在本次 V10 / `6.6.30+` 数据中，大尺寸开销约 `+84%~85%`。本次开销扩大不是由非 pKVM 基线变慢造成的，因为 V10 的非 pKVM 大尺寸基线反而更快。

## 10. 解释与判断

### 10.1 为什么差异可信

这轮结果一开始看上去很大，因此做了三层 sanity check：

1. 原始 lmbench raw 文本里已经存在差异，例如 64 MB：
   - KVM-off: `429 us`
   - VHE: `428 us`
   - NVHE: `429 us`
   - pKVM: `807 us`

2. precise 版本复测得到同向结果，且大 size 的 MAD 很低：
   - 64 MB KVM-off MAD: `0.254%`
   - 64 MB VHE MAD: `0.191%`
   - 64 MB NVHE MAD: `0.049%`
   - 64 MB pKVM MAD: `0.082%`

3. mmap read bandwidth 没有同等幅度下降，说明不是整体频率、绑核、内存带宽或解析错误造成的。

### 10.2 当前结论

在 N90 / Kylin V10 SP1 / `6.6.30+` 这套环境下：

- KVM-off、VHE、NVHE 的 Host `lat_mmap` 基本等价。
- pKVM 对 Host `lat_mmap` 的额外成本非常明显。
- 该成本主要体现在映射建立/拆除和首次触摸路径，而不是映射建立后的稳定读取带宽。

最终可表述为：

> 在 N90 V10 的 `6.6.30+` 内核上，启用 pKVM 后，Host 侧 `lat_mmap` 在 16 MB 以上映射规模时约慢 `85%`；KVM-off、VHE、NVHE 三个非 pKVM 基线几乎重合。该信号在原生 lmbench 和 ns 精度 `lat_mmap_precise` 中均可复现。

## 11. 数据文件索引

四模式最终汇总：

```text
results/n90-v10-mmap-4mode-summary.txt
```

KVM-off：

```text
results/n90-v10-kvmoff-mmap/n90-v10-kvmoff-mmap-cpu0.csv
results/n90-v10-kvmoff-mmap/precise-mmap/n90-v10-kvmoff-mmap.log
```

VHE：

```text
results/n90-v10-vhe-mmap/n90-v10-vhe-mmap-cpu0.csv
results/n90-v10-vhe-mmap/precise-mmap/n90-v10-vhe-mmap.log
```

NVHE：

```text
results/n90-v10-nvhe-mmap/n90-v10-nvhe-mmap-cpu0.csv
results/n90-v10-nvhe-mmap/precise-mmap/n90-v10-nvhe-mmap.log
```

pKVM：

```text
results/n90-v10-pkvm-mmap/n90-v10-pkvm-mmap-cpu0.csv
results/n90-v10-pkvm-mmap/precise-mmap/n90-v10-pkvm-mmap.log
```

## 12. C pKVM 内核 protected-mode 复测

后续又在 N90 上切换到原 C 实现 pKVM 的内核，并重复 protected-mode mmap-only 测试，用于判断前面 `+85%` 是否可能来自 Rust 实现 pKVM 内核的问题。

新内核信息：

```text
Linux kylin-pc 6.6.30-pkvm-c+ #6 SMP Tue Jun 9 16:47:01 CST 2026 aarch64
cmdline: kvm-arm.mode=protected
dmesg: CPU features: detected: Protected KVM
```

测试条件保持一致：

```text
core0, N=10, THP=never, ASLR=0, freq=2.1GHz performance, LSM=capability,kysec,box
```

结果文件：

```text
results/n90-v10-cpkvm-pkvm-mmap/n90-v10-cpkvm-pkvm-mmap-cpu0.csv
results/n90-v10-cpkvm-pkvm-mmap/precise-mmap/n90-v10-cpkvm-pkvm-mmap.log
results/n90-v10-cpkvm-pkvm-mmap/cpkvm-vs-rustpkvm-summary.txt
```

### 12.1 C pKVM vs 前一版 Rust pKVM

单位：us，均为 protected-mode `lat_mmap_precise` median。

| size | KVM-off 基线 | VHE 基线 | Rust pKVM | C pKVM | C vs Rust | Rust pKVM vs KVM-off | C pKVM vs KVM-off |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 10.356132 | 10.429703 | 13.438333 | 13.015565 | -3.15% | +29.76% | +25.68% |
| 1 MB | 13.787149 | 13.699023 | 19.649358 | 19.525877 | -0.63% | +42.52% | +41.62% |
| 2 MB | 20.526078 | 20.295507 | 31.348366 | 31.474889 | +0.40% | +52.72% | +53.34% |
| 4 MB | 33.100203 | 33.382131 | 56.237202 | 56.308970 | +0.13% | +69.90% | +70.12% |
| 8 MB | 59.622910 | 59.363406 | 106.872015 | 106.316775 | -0.52% | +79.25% | +78.32% |
| 16 MB | 110.991690 | 110.677476 | 205.056008 | 204.138823 | -0.45% | +84.75% | +83.92% |
| 64 MB | 443.084233 | 441.221122 | 816.317767 | 814.995820 | -0.16% | +84.24% | +83.94% |

原生 lmbench raw `lat_mmap` 也几乎重合：

| variant | Rust pKVM | C pKVM | C vs Rust |
|---|---:|---:|---:|
| sz0.524288MB | 12.000 us | 12.000 us | 0.00% |
| sz1.048576MB | 18.000 us | 18.000 us | 0.00% |
| sz2.097152MB | 30.000 us | 30.000 us | 0.00% |
| sz4.194304MB | 56.000 us | 56.000 us | 0.00% |
| sz8.388608MB | 106.000 us | 106.000 us | 0.00% |
| sz16.777216MB | 205.000 us | 204.500 us | -0.24% |
| sz33.554432MB | 405.000 us | 403.000 us | -0.49% |
| sz67.108864MB | 807.000 us | 805.000 us | -0.25% |

67 MB bandwidth sanity check：

| bench | Rust pKVM | C pKVM |
|---|---:|---:|
| `bw_mmap_rd` | 14957.955 MB/s | 14934.660 MB/s |
| `bw_mmap_rd_o2c` | 6161.600 MB/s | 6184.295 MB/s |

### 12.2 追加判断

C 实现 pKVM 内核的 protected-mode `lat_mmap` 与前一版 Rust pKVM 内核几乎一致。64 MB 精测只差 `-0.16%`，远小于 pKVM 相对 KVM-off 的 `+84%` 量级。

因此，就当前 protected-mode 结果而言：

> N90 V10 上 `lat_mmap` 的大幅 pKVM 开销不像是 Rust pKVM 实现独有的问题；原 C pKVM 内核也复现了几乎相同的开销。

后续已经在同一个 `6.6.30-pkvm-c+` 内核下补测了 NVHE 和 VHE，见下文。就定位“Rust 实现是否引入了额外 mmap 开销”这个问题，当前 protected-mode 复测已经给出了很强的反证：C pKVM 并没有恢复到非 pKVM 基线。

### 12.3 C pKVM 内核 NVHE 补测

随后又在同一个 `6.6.30-pkvm-c+ #6` 内核下切到 `kvm-arm.mode=nvhe`，按同样条件补测了 NVHE：

```text
results/n90-v10-cpkvm-nvhe-mmap/n90-v10-cpkvm-nvhe-mmap-cpu0.csv
results/n90-v10-cpkvm-nvhe-mmap/precise-mmap/n90-v10-cpkvm-nvhe-mmap.log
results/n90-v10-cpkvm-nvhe-mmap/cpkvm-nvhe-pkvm-summary.txt
```

C 内核 NVHE / pKVM 对比：

| size | C NVHE | C pKVM | C pKVM vs C NVHE | 旧 Rust NVHE | 旧 Rust pKVM | 旧 Rust pKVM vs NVHE |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 10.130869 | 13.015565 | +28.47% | 10.362521 | 13.438333 | +29.68% |
| 1 MB | 13.526509 | 19.525877 | +44.35% | 13.761465 | 19.649358 | +42.79% |
| 2 MB | 20.149791 | 31.474889 | +56.20% | 20.554292 | 31.348366 | +52.51% |
| 4 MB | 33.313292 | 56.308970 | +69.03% | 32.924943 | 56.237202 | +70.80% |
| 8 MB | 59.647147 | 106.316775 | +78.24% | 59.851396 | 106.872015 | +78.56% |
| 16 MB | 111.092842 | 204.138823 | +83.76% | 110.545133 | 205.056008 | +85.50% |
| 64 MB | 440.190067 | 814.995820 | +85.15% | 441.186916 | 816.317767 | +85.03% |

原生 lmbench raw `lat_mmap` 也同向：

| variant | C NVHE | C pKVM | C pKVM vs C NVHE |
|---|---:|---:|---:|
| sz0.524288MB | 8.967 us | 12.000 us | +33.82% |
| sz1.048576MB | 12.000 us | 18.000 us | +50.00% |
| sz2.097152MB | 19.000 us | 30.000 us | +57.89% |
| sz4.194304MB | 32.000 us | 56.000 us | +75.00% |
| sz8.388608MB | 58.000 us | 106.000 us | +82.76% |
| sz16.777216MB | 110.000 us | 204.500 us | +85.91% |
| sz33.554432MB | 216.000 us | 403.000 us | +86.57% |
| sz67.108864MB | 427.500 us | 805.000 us | +88.30% |

这次 NVHE 补测进一步收紧了判断：

> 在同一个 C pKVM 内核 `6.6.30-pkvm-c+ #6` 内，NVHE 的 64 MB `lat_mmap_precise` 为 `440.19 us`，pKVM 为 `815.00 us`，pKVM 开销 `+85.15%`。这与前一版内核的 NVHE/pKVM 开销 `+85.03%` 基本一致。

因此，当前数据不支持“Rust pKVM 实现导致 Host mmap 异常变慢”的假设。C pKVM 内核在 NVHE/pKVM 对照下复现了相同量级的开销。

### 12.4 C pKVM 内核 VHE 补测与三模式汇总

最后在同一个 `6.6.30-pkvm-c+ #6` 内核下切回 VHE，并按完全相同条件补测：

```text
cmdline: no explicit kvm-arm.mode
dmesg: VHE mode initialized successfully
```

结果文件：

```text
results/n90-v10-cpkvm-vhe-mmap/n90-v10-cpkvm-vhe-mmap-cpu0.csv
results/n90-v10-cpkvm-vhe-mmap/precise-mmap/n90-v10-cpkvm-vhe-mmap.log
results/n90-v10-cpkvm-3mode-summary.txt
```

C 内核 VHE / NVHE / pKVM 三模式 `lat_mmap_precise` median：

| size | C VHE | C NVHE | C pKVM | C pKVM vs C VHE | C pKVM vs C NVHE | C VHE vs 旧 Rust VHE | C pKVM vs 旧 Rust pKVM |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 10.202513 | 10.130869 | 13.015565 | +27.57% | +28.47% | -2.18% | -3.15% |
| 1 MB | 13.693219 | 13.526509 | 19.525877 | +42.60% | +44.35% | -0.04% | -0.63% |
| 2 MB | 20.047234 | 20.149791 | 31.474889 | +57.00% | +56.20% | -1.22% | +0.40% |
| 4 MB | 32.823826 | 33.313292 | 56.308970 | +71.55% | +69.03% | -1.67% | +0.13% |
| 8 MB | 59.819800 | 59.647147 | 106.316775 | +77.73% | +78.24% | +0.77% | -0.52% |
| 16 MB | 111.067960 | 111.092842 | 204.138823 | +83.80% | +83.76% | +0.35% | -0.45% |
| 64 MB | 442.533067 | 440.190067 | 814.995820 | +84.17% | +85.15% | +0.30% | -0.16% |

原生 lmbench raw `lat_mmap` median：

| variant | C VHE | C NVHE | C pKVM | C pKVM vs C VHE | C pKVM vs C NVHE |
|---|---:|---:|---:|---:|---:|
| sz0.524288MB | 9.043 us | 8.967 us | 12.000 us | +32.70% | +33.82% |
| sz1.048576MB | 12.500 us | 12.000 us | 18.000 us | +44.00% | +50.00% |
| sz2.097152MB | 19.000 us | 19.000 us | 30.000 us | +57.89% | +57.89% |
| sz4.194304MB | 32.000 us | 32.000 us | 56.000 us | +75.00% | +75.00% |
| sz8.388608MB | 59.000 us | 58.000 us | 106.000 us | +79.66% | +82.76% |
| sz16.777216MB | 110.000 us | 110.000 us | 204.500 us | +85.91% | +85.91% |
| sz33.554432MB | 216.000 us | 216.000 us | 403.000 us | +86.57% | +86.57% |
| sz67.108864MB | 428.000 us | 427.500 us | 805.000 us | +88.08% | +88.30% |

VHE 补测后，同一 C 内核内的三模式关系已经清楚：

- C VHE 和 C NVHE 仍然与前一版 Rust 内核的非 pKVM 基线重合，64 MB 差异在 `±0.3%` 量级。
- C pKVM 与旧 Rust pKVM 也重合，64 MB 只差 `-0.16%`。
- C pKVM 相对 C VHE / C NVHE 的 64 MB 开销分别为 `+84.17%` / `+85.15%`。

最终判断：

> 这轮 C 实现 pKVM 内核的 VHE / NVHE / pKVM 三模式复测，完整复现了前一版内核上看到的 Host `lat_mmap` 现象：非 pKVM 基线基本不变，pKVM 在大尺寸 mmap 上稳定慢约 `85%`。因此该现象不支持“Rust pKVM 实现本身导致 mmap 异常”的解释，更像是 pKVM protected-mode 路径本身带来的 Host mmap 建映射开销。

### 12.5 C pKVM 内核 KVM-off 补测与四模式最终对照

最后又在同一个 C pKVM 内核下切到关闭 KVM 的启动模式，并复测 mmap-only：

```text
cmdline: kvm-arm.mode=none
dmesg: KVM disabled from command line
```

准备状态仍保持一致：

```text
core0, N=10, THP=never, ASLR=0, all CPUs locked to 2100000 kHz/performance
network/SSH preserved
```

结果文件：

```text
results/n90-v10-cpkvm-kvmoff-mmap/n90-v10-cpkvm-kvmoff-mmap-cpu0.csv
results/n90-v10-cpkvm-kvmoff-mmap/precise-mmap/n90-v10-cpkvm-kvmoff-mmap.log
results/n90-v10-cpkvm-4mode-summary.txt
```

C 内核四模式 `lat_mmap_precise` median：

| size | C KVM-off | C VHE | C NVHE | C pKVM | C pKVM vs KVM-off | C pKVM vs VHE | C pKVM vs NVHE |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 10.147539 | 10.202513 | 10.130869 | 13.015565 | +28.26% | +27.57% | +28.47% |
| 1 MB | 13.752110 | 13.693219 | 13.526509 | 19.525877 | +41.98% | +42.60% | +44.35% |
| 2 MB | 19.867404 | 20.047234 | 20.149791 | 31.474889 | +58.42% | +57.00% | +56.20% |
| 4 MB | 33.167137 | 32.823826 | 33.313292 | 56.308970 | +69.77% | +71.55% | +69.03% |
| 8 MB | 59.604567 | 59.819800 | 59.647147 | 106.316775 | +78.37% | +77.73% | +78.24% |
| 16 MB | 111.312677 | 111.067960 | 111.092842 | 204.138823 | +83.39% | +83.80% | +83.76% |
| 64 MB | 442.237393 | 442.533067 | 440.190067 | 814.995820 | +84.29% | +84.17% | +85.15% |

原生 lmbench raw `lat_mmap` median：

| variant | C KVM-off | C VHE | C NVHE | C pKVM | C pKVM vs KVM-off |
|---|---:|---:|---:|---:|---:|
| sz0.524288MB | 9.0175 us | 9.043 us | 8.967 us | 12.000 us | +33.07% |
| sz1.048576MB | 12.000 us | 12.500 us | 12.000 us | 18.000 us | +50.00% |
| sz2.097152MB | 19.000 us | 19.000 us | 19.000 us | 30.000 us | +57.89% |
| sz4.194304MB | 32.000 us | 32.000 us | 32.000 us | 56.000 us | +75.00% |
| sz8.388608MB | 58.000 us | 59.000 us | 58.000 us | 106.000 us | +82.76% |
| sz16.777216MB | 110.000 us | 110.000 us | 110.000 us | 204.500 us | +85.91% |
| sz33.554432MB | 215.000 us | 216.000 us | 216.000 us | 403.000 us | +87.44% |
| sz67.108864MB | 427.000 us | 428.000 us | 427.500 us | 805.000 us | +88.52% |

四模式补齐后，结论没有变化，反而更明确：

- C KVM-off / VHE / NVHE 三个非 pKVM 基线重合，64 MB 分别是 `442.237 us` / `442.533 us` / `440.190 us`。
- C pKVM 64 MB 是 `814.996 us`，相对三个非 pKVM 基线分别为 `+84.29%` / `+84.17%` / `+85.15%`。
- C KVM-off 与前一版 Rust 内核 KVM-off 的 64 MB 差异是 `-0.19%`，C pKVM 与前一版 Rust pKVM 的 64 MB 差异是 `-0.16%`。

最终四模式判断：

> 在同一台 N90、同一套 V10 环境、同一个 C 实现 pKVM 内核 `6.6.30-pkvm-c+ #6` 上，KVM-off / VHE / NVHE 的 Host `lat_mmap` 基线一致，而 pKVM protected-mode 稳定慢约 `84%~85%`。这基本排除了“上一轮 Rust pKVM 内核实现导致 mmap 差距巨大”的解释。
