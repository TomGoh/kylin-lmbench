# Kaitian mmap-split NVHE 与 pKVM 对照测试记录

**日期**：2026-06-11
**机器**：Kaitian / `ryuu`
**测试项目**：[experiments/mmap-split](../../experiments/mmap-split)
**原始结果**：
- [results/mmap-split-kaitian/nvhe.csv](../../results/mmap-split-kaitian/nvhe.csv)
- [results/mmap-split-kaitian/pkvm.csv](../../results/mmap-split-kaitian/pkvm.csv)

## 1. 测试目的

前面的 `lat_mmap` 精测显示，pKVM 在宿主机侧 `mmap + touch + munmap` 路径上明显慢于非 pKVM。LMDB 应用级测试也显示，pKVM 对长期打开后的 read/write 影响很小，但对 `openclose` 路径有明显影响。

本次 `mmap-split` 的目标是把原版 `lat_mmap` 拆成更小的测试模块，分别观察：

```text
open/close backing file
只 mmap/munmap，不访问映射内容
MAP_POPULATE 预填充映射
mmap + write touch + munmap
mmap + read touch + munmap
单独的 cold touch
单独的 hot touch
touch 之后再单独测 munmap
```

这样可以避免只看到 `lat_mmap` 的总时间，却不知道慢在 `mmap`、page fault、实际访存，还是 `munmap` teardown。

## 2. 环境确认

NVHE 组：

```text
hostname: ryuu
kernel: Linux ryuu 6.6.30+ #637 SMP Wed May 13 17:04:48 CST 2026 aarch64
cmdline: kvm-arm.mode=nvhe hyp_trace_printk=1
dmesg: Hyp mode initialized successfully
lsm: capability,kysec,box
thp: [always] madvise never
aslr: 2
```

pKVM 组：

```text
hostname: ryuu
kernel: Linux ryuu 6.6.30+ #637 SMP Wed May 13 17:04:48 CST 2026 aarch64
cmdline: kvm-arm.mode=protected
dmesg: CPU features: detected: Protected KVM
lsm: capability,kysec,box
thp: [always] madvise never
aslr: 2
```

两组的主要差异是 `kvm-arm.mode`。需要注意，当前环境没有关闭 THP/ASLR，也保留了 `kysec,box` LSM。因此这组数据应视为 Kaitian 当前系统状态下的定位数据，而不是最终论文级受控数据。

## 3. 测试口径

两组使用同一命令口径：

```bash
cd ~/kylin-lmbench
MODE=<nvhe|pkvm> CORE=0 RUNS=10 REFILL=1 WARMUPS=1 scripts/mmap-split-bench.sh
python3 scripts/analyze-mmap-split.py nvhe pkvm
```

关键参数：

```text
runs=10
core=0
touch_divisor=10
stride_kb=16
warmups=1
backing_fill=dd if=/dev/zero bs=1M conv=fsync
```

这里的计时口径尽量贴近 lmbench：

1. 每个模块和每个 size 跑 10 轮，报告中位数。
2. 正式计时前做 1 次不计时 warmup。
3. 触摸几何保持与 `lat_mmap` 一致：只访问前 `size / 10` 字节，步长为 16 KB。
4. 使用 `CLOCK_MONOTONIC` 做纳秒级计时，再换算成每次迭代的 us。
5. 远端没有 lmbench `lmdd`，因此使用 `dd + conv=fsync` 写满 backing file，避免 sparse file。

后文所有表格中的 `NVHE us` 和 `pKVM us` 都是 10 轮中位数，单位是 `us/iteration`。`MAD%` 是中位数绝对偏差相对中位数的比例，用来观察这组数据是否稳定。`Delta us` 和 `Delta%` 表示 pKVM 相对 NVHE 的变化，正数表示 pKVM 更慢，负数表示 pKVM 更快。

## 4. 完整数据总表

### 4.1 openclose

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 2.694 | 2.21% | 2.643 | 1.14% | -0.051 | -1.88% |
| 1 MB | 2.748 | 2.29% | 2.724 | 4.17% | -0.024 | -0.88% |
| 2 MB | 2.739 | 3.83% | 2.814 | 1.15% | +0.075 | +2.75% |
| 4 MB | 2.566 | 1.21% | 2.638 | 2.46% | +0.072 | +2.81% |
| 8 MB | 2.592 | 0.89% | 2.757 | 6.37% | +0.165 | +6.37% |
| 16 MB | 2.606 | 1.39% | 2.597 | 0.96% | -0.009 | -0.35% |
| 64 MB | 2.648 | 0.62% | 2.667 | 0.62% | +0.019 | +0.71% |

### 4.2 mmap_unmap

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 3.795 | 7.15% | 3.564 | 7.38% | -0.232 | -6.10% |
| 1 MB | 3.933 | 9.00% | 3.558 | 14.22% | -0.374 | -9.52% |
| 2 MB | 3.328 | 9.09% | 3.323 | 9.98% | -0.005 | -0.16% |
| 4 MB | 3.244 | 9.25% | 3.114 | 7.31% | -0.130 | -4.01% |
| 8 MB | 2.986 | 3.05% | 2.848 | 2.96% | -0.138 | -4.62% |
| 16 MB | 3.070 | 5.03% | 2.896 | 2.85% | -0.175 | -5.69% |
| 64 MB | 3.210 | 1.69% | 3.247 | 1.61% | +0.037 | +1.15% |

### 4.3 mmap_populate_unmap

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 48.095 | 0.64% | 63.821 | 0.70% | +15.726 | +32.70% |
| 1 MB | 91.769 | 1.93% | 122.773 | 0.67% | +31.004 | +33.78% |
| 2 MB | 178.804 | 0.03% | 179.253 | 0.24% | +0.449 | +0.25% |
| 4 MB | 351.467 | 0.05% | 350.574 | 0.08% | -0.893 | -0.25% |
| 8 MB | 692.322 | 0.04% | 685.088 | 0.13% | -7.235 | -1.04% |
| 16 MB | 1390.439 | 0.06% | 1370.824 | 0.26% | -19.615 | -1.41% |
| 64 MB | 5523.292 | 0.07% | 5440.985 | 0.05% | -82.307 | -1.49% |

### 4.4 mmap_write_touch_unmap

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 8.549 | 3.96% | 9.940 | 2.25% | +1.390 | +16.26% |
| 1 MB | 14.328 | 4.37% | 16.390 | 7.57% | +2.062 | +14.39% |
| 2 MB | 21.047 | 3.84% | 27.551 | 1.78% | +6.504 | +30.90% |
| 4 MB | 34.399 | 3.26% | 47.366 | 0.39% | +12.967 | +37.70% |
| 8 MB | 59.333 | 0.42% | 84.962 | 0.28% | +25.629 | +43.19% |
| 16 MB | 109.404 | 0.24% | 161.112 | 0.36% | +51.708 | +47.26% |
| 64 MB | 428.058 | 0.36% | 642.383 | 0.22% | +214.325 | +50.07% |

### 4.5 mmap_read_touch_unmap

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 9.511 | 1.82% | 11.408 | 3.57% | +1.897 | +19.94% |
| 1 MB | 17.243 | 8.20% | 19.742 | 9.20% | +2.499 | +14.50% |
| 2 MB | 27.695 | 0.95% | 35.367 | 1.88% | +7.671 | +27.70% |
| 4 MB | 42.352 | 2.70% | 56.298 | 0.37% | +13.946 | +32.93% |
| 8 MB | 69.660 | 0.51% | 94.738 | 0.41% | +25.078 | +36.00% |
| 16 MB | 130.669 | 0.76% | 184.384 | 0.23% | +53.716 | +41.11% |
| 64 MB | 498.423 | 0.20% | 501.964 | 0.30% | +3.540 | +0.71% |

### 4.6 write_touch_cold

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 3.729 | 5.56% | 4.144 | 14.72% | +0.415 | +11.14% |
| 1 MB | 7.232 | 8.72% | 6.146 | 6.14% | -1.086 | -15.01% |
| 2 MB | 11.705 | 1.81% | 11.614 | 1.05% | -0.092 | -0.78% |
| 4 MB | 22.415 | 2.55% | 22.348 | 1.85% | -0.067 | -0.30% |
| 8 MB | 42.961 | 0.35% | 42.998 | 0.27% | +0.037 | +0.09% |
| 16 MB | 82.214 | 0.19% | 82.485 | 0.29% | +0.271 | +0.33% |
| 64 MB | 333.541 | 0.36% | 346.159 | 0.37% | +12.618 | +3.78% |

### 4.7 read_touch_cold

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 3.175 | 6.85% | 2.900 | 0.39% | -0.274 | -8.64% |
| 1 MB | 7.021 | 18.25% | 6.570 | 11.13% | -0.451 | -6.43% |
| 2 MB | 12.715 | 5.20% | 12.185 | 0.53% | -0.530 | -4.17% |
| 4 MB | 20.576 | 1.37% | 20.654 | 1.55% | +0.079 | +0.38% |
| 8 MB | 37.280 | 0.74% | 37.190 | 0.25% | -0.090 | -0.24% |
| 16 MB | 72.990 | 0.10% | 73.297 | 0.38% | +0.307 | +0.42% |
| 64 MB | 293.674 | 0.32% | 301.989 | 0.23% | +8.315 | +2.83% |

### 4.8 write_touch_hot

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 0.005 | 0.04% | 0.005 | 0.04% | +0.000 | +0.00% |
| 1 MB | 0.007 | 0.06% | 0.007 | 1.77% | +0.000 | +1.82% |
| 2 MB | 0.012 | 0.53% | 0.012 | 0.83% | +0.000 | +0.30% |
| 4 MB | 0.056 | 0.01% | 0.056 | 0.02% | +0.000 | +0.02% |
| 8 MB | 0.130 | 2.93% | 0.218 | 0.36% | +0.088 | +67.28% |
| 16 MB | 0.452 | 0.06% | 0.488 | 0.34% | +0.035 | +7.80% |
| 64 MB | 2.346 | 1.09% | 2.716 | 0.79% | +0.371 | +15.80% |

### 4.9 read_touch_hot

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 0.008 | 0.01% | 0.008 | 0.02% | +0.000 | +0.01% |
| 1 MB | 0.012 | 0.01% | 0.012 | 0.00% | +0.000 | +0.01% |
| 2 MB | 0.032 | 2.10% | 0.030 | 4.27% | -0.002 | -7.37% |
| 4 MB | 0.091 | 1.58% | 0.104 | 1.06% | +0.012 | +13.42% |
| 8 MB | 0.167 | 6.28% | 0.204 | 0.44% | +0.037 | +22.34% |
| 16 MB | 0.461 | 0.65% | 0.437 | 0.14% | -0.024 | -5.25% |
| 64 MB | 2.618 | 2.57% | 3.072 | 0.39% | +0.454 | +17.36% |

### 4.10 munmap_after_no_touch

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 1.622 | 4.95% | 1.650 | 6.28% | +0.028 | +1.73% |
| 1 MB | 2.024 | 13.48% | 1.876 | 4.90% | -0.148 | -7.33% |
| 2 MB | 1.237 | 6.13% | 1.237 | 4.88% | +0.000 | +0.03% |
| 4 MB | 1.223 | 3.86% | 1.235 | 2.84% | +0.012 | +0.95% |
| 8 MB | 1.246 | 3.77% | 1.254 | 4.31% | +0.008 | +0.64% |
| 16 MB | 1.256 | 1.45% | 1.286 | 3.04% | +0.030 | +2.40% |
| 64 MB | 1.521 | 0.96% | 1.515 | 1.71% | -0.005 | -0.35% |

### 4.11 munmap_after_write_touch

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 3.065 | 11.17% | 4.498 | 3.09% | +1.433 | +46.77% |
| 1 MB | 4.308 | 7.99% | 7.216 | 5.58% | +2.907 | +67.48% |
| 2 MB | 6.581 | 1.92% | 12.923 | 2.75% | +6.342 | +96.37% |
| 4 MB | 9.284 | 0.70% | 22.424 | 2.92% | +13.140 | +141.53% |
| 8 MB | 14.759 | 0.80% | 40.977 | 1.47% | +26.218 | +177.64% |
| 16 MB | 25.838 | 1.09% | 77.434 | 0.85% | +51.597 | +199.70% |
| 64 MB | 90.215 | 0.24% | 295.219 | 0.38% | +205.003 | +227.24% |

### 4.12 munmap_after_read_touch

| size | NVHE us | NVHE MAD% | pKVM us | pKVM MAD% | Delta us | Delta% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 4.308 | 5.33% | 6.790 | 10.58% | +2.482 | +57.63% |
| 1 MB | 6.988 | 12.61% | 12.527 | 9.73% | +5.539 | +79.27% |
| 2 MB | 12.268 | 1.23% | 21.091 | 2.48% | +8.823 | +71.92% |
| 4 MB | 18.742 | 1.57% | 32.901 | 1.07% | +14.159 | +75.55% |
| 8 MB | 31.245 | 1.39% | 58.225 | 0.91% | +26.979 | +86.35% |
| 16 MB | 57.751 | 0.58% | 109.718 | 0.16% | +51.967 | +89.98% |
| 64 MB | 202.422 | 0.30% | 198.608 | 0.59% | -3.814 | -1.88% |

## 5. 逐项分析

### 5.1 openclose：底层文件 open/close 不是主要差异

`openclose` 只反复打开和关闭 backing file，不做 `mmap`，也不访问映射内存。

所有 size 下两组都在 2.5 到 2.8 us 左右。pKVM 相对 NVHE 的变化范围是 -1.88% 到 +6.37%，绝对差异最大只有 +0.165 us。

因此，在这个拆分测试里，简单的 backing file `open + close` 没有显示出 pKVM 的系统性退化。这个结论不能直接否定 LMDB `openclose` 的退化，因为 LMDB 的 open/close 还包括环境初始化、元数据页读取、锁文件、映射建立和内部数据结构初始化；这里测的只是最底层的文件描述符开关。

### 5.2 mmap_unmap：未触摸映射时，pKVM 基本不慢

`mmap_unmap` 每轮只做：

```text
mmap file-backed mapping
munmap mapping
```

它不读写映射地址，所以一般不会真正触发文件页 fault，也不会建立大量实际页映射。

数据里 pKVM 在 0.5 MB 到 16 MB 甚至略快，64 MB 只慢 +0.037 us，也就是 +1.15%。这说明“只建立一个 VMA 再删掉”本身不是 pKVM 慢的主要来源。

这点很重要：如果 pKVM 的问题主要在 `mmap` 系统调用本身，那么这个模块应该已经明显变慢。但结果没有出现这种现象。

### 5.3 mmap_populate_unmap：小 size 有退化，大 size 不明显

`mmap_populate_unmap` 使用 `MAP_POPULATE`，内核会在 `mmap` 阶段主动预填充页，而不是等用户态第一次访问时再 fault。

0.5 MB 和 1 MB 下 pKVM 分别慢 +32.70% 和 +33.78%，绝对差异是 +15.726 us 和 +31.004 us。但从 2 MB 开始，两组几乎持平，4 MB 到 64 MB 甚至是 pKVM 略快。

这说明 `MAP_POPULATE` 在小映射上确实有 pKVM 额外成本，但它不是解释 `lat_mmap` 默认路径的主因。默认 `lat_mmap` 不是 `MAP_POPULATE`，而是 `mmap` 后由用户态触摸触发 fault；并且最关键的写路径在大 size 上呈现持续放大的退化，而 `mmap_populate_unmap` 没有这种趋势。

### 5.4 mmap_write_touch_unmap：复现 lat_mmap 默认写路径退化

`mmap_write_touch_unmap` 是最接近原版 `lat_mmap` 默认语义的拆分项：

```text
mmap
写触摸前 size / 10 的区域
munmap
```

这里 pKVM 从 0.5 MB 的 +16.26% 增长到 64 MB 的 +50.07%。绝对差异也从 +1.390 us 增长到 +214.325 us。

这说明 pKVM 的问题不是只出现在某个小 size，也不是单纯的测试噪声，而是随着被触摸范围扩大而持续放大。这个模块可以作为后续优化和回归测试的主测试项，因为它最能代表原始 `lat_mmap` 看到的现象。

### 5.5 mmap_read_touch_unmap：读路径也慢，但 64 MB 有异常

`mmap_read_touch_unmap` 的结构和写路径相同，只是触摸方式从写变成读。

0.5 MB 到 16 MB 下，pKVM 慢 +14.50% 到 +41.11%，趋势和写路径相似。但 64 MB 只慢 +0.71%，明显偏离前面 size 的趋势。

因此，读路径可以说明 touched mapping 的 teardown 也可能受 pKVM 影响，但它不如写路径干净。64 MB 异常可能与 page cache 状态、fault 类型、文件页是否已经稳定驻留、读 fault 和写 fault 的内核路径差异有关。后续如果要研究读路径，需要单独复测，而不应把它和写路径混在一起下结论。

### 5.6 write_touch_cold：首次写触摸本身不是主要瓶颈

`write_touch_cold` 的设计是把映射先准备好，再计时第一次写触摸。它主要观察首次访问时的 page fault、页表建立、文件页准备和写入触发的成本。

结果显示，2 MB 到 16 MB 几乎持平；64 MB 下 pKVM 慢 +12.618 us，也就是 +3.78%。相比完整写路径 64 MB 的 +214.325 us，这个差异很小。

所以，pKVM 的主要额外时间不是“第一次写到 mmap 地址”本身。也就是说，虽然 first-touch 会触发 fault 和映射建立，但当前数据不支持把主要问题归因到 first-touch 建表。

### 5.7 read_touch_cold：首次读触摸也不是主要瓶颈

`read_touch_cold` 只测第一次读触摸。0.5 MB 到 2 MB 下 pKVM 略快，4 MB 到 16 MB 基本持平，64 MB 慢 +8.315 us，也就是 +2.83%。

这和写触摸类似：cold read touch 的绝对差异也不大，不能解释完整读写路径里几十到几百微秒的差距。

### 5.8 write_touch_hot：稳定映射上的写访问成本很小

`write_touch_hot` 在计时前已经把映射触摸过，因此计时部分主要测稳定映射上的重复写访问，不再包含主要的 fault 成本。

这个模块的百分比有波动，例如 8 MB 是 +67.28%，但绝对值只有：

```text
NVHE 0.130 us
pKVM 0.218 us
Delta +0.088 us
```

64 MB 下也只是：

```text
NVHE 2.346 us
pKVM 2.716 us
Delta +0.371 us
```

这些绝对差异远小于完整写路径 64 MB 的 +214.325 us。因此，稳定映射上的普通写访问不是主要优化目标。

### 5.9 read_touch_hot：稳定映射上的读访问也不是主要瓶颈

`read_touch_hot` 和 `write_touch_hot` 类似，只是访问方式为读。64 MB 下 pKVM 慢 +0.454 us，百分比是 +17.36%，但绝对差异仍然很小。

这说明 pKVM 并没有让已经建立好的 host 映射在普通读写访问上出现大幅退化。问题更像是发生在映射生命周期管理阶段，而不是每一次普通 load/store。

### 5.10 munmap_after_no_touch：没有触摸过的 munmap 基本正常

`munmap_after_no_touch` 把 `mmap` 放在计时前，计时部分只测 `munmap`。区别是映射从未被读写触摸过。

结果显示，所有 size 都在 1 到 2 us 左右，pKVM 相对 NVHE 的变化没有随 size 放大。64 MB 下 pKVM 还略快 -0.005 us。

这说明 `munmap` 这个系统调用本身并不天然慢。只有当映射真的被触摸、产生实际页映射之后，teardown 路径才可能触发 pKVM 的额外成本。

### 5.11 munmap_after_write_touch：当前最关键的数据

`munmap_after_write_touch` 是这次测试中最关键的模块。它在计时前完成：

```text
mmap
写触摸前 size / 10 的区域
```

然后只计时：

```text
munmap
```

结果非常清楚：pKVM 的退化随 size 持续放大。

| size | NVHE us | pKVM us | Delta us | Delta% |
|---:|---:|---:|---:|---:|
| 0.5 MB | 3.065 | 4.498 | +1.433 | +46.77% |
| 1 MB | 4.308 | 7.216 | +2.907 | +67.48% |
| 2 MB | 6.581 | 12.923 | +6.342 | +96.37% |
| 4 MB | 9.284 | 22.424 | +13.140 | +141.53% |
| 8 MB | 14.759 | 40.977 | +26.218 | +177.64% |
| 16 MB | 25.838 | 77.434 | +51.597 | +199.70% |
| 64 MB | 90.215 | 295.219 | +205.003 | +227.24% |

把它和完整写路径对比，64 MB 时：

```text
mmap_write_touch_unmap:
  NVHE 428.058 us
  pKVM 642.383 us
  Delta +214.325 us

munmap_after_write_touch:
  NVHE 90.215 us
  pKVM 295.219 us
  Delta +205.003 us
```

完整写路径的额外时间约 +214 us，其中单独的写触摸后 `munmap` 就贡献了约 +205 us。也就是说，pKVM 在这条路径上的额外成本几乎全部可以由 touched mapping 的 `munmap` teardown 解释。

这把优化重点明显推向：

```text
munmap teardown
touched mapping 的 stage-2 unmap/protect
TLBI / shootdown
dirty file-backed mapping 的回收路径
host stage-2 状态清理
```

### 5.12 munmap_after_read_touch：读触摸后的 munmap 有次要证据

`munmap_after_read_touch` 在 0.5 MB 到 16 MB 也显示明显退化：pKVM 慢 +57.63% 到 +89.98%。16 MB 下绝对差异是 +51.967 us。

但 64 MB 下结果变成 pKVM 略快 -1.88%。这和完整读路径 64 MB 的异常一致，说明读路径受额外因素影响更大。

因此，读触摸后的 `munmap` 可以作为辅助证据：它提示“触摸过的映射在 teardown 时会触发 pKVM 额外成本”。但当前最稳定、最适合拿来指导优化的证据仍然是写触摸后的 `munmap`。

## 6. 跨模块结论

把所有模块放在一起看，可以得到更严格的定位：

1. `openclose` 基本持平，底层文件描述符开关不是主要问题。
2. `mmap_unmap` 基本持平，只建立和删除未触摸映射不是主要问题。
3. `munmap_after_no_touch` 基本持平，未触摸映射的 `munmap` 也不是主要问题。
4. `write_touch_cold` 和 `read_touch_cold` 只有小幅差异，first-touch 本身不是主要问题。
5. `write_touch_hot` 和 `read_touch_hot` 的绝对差异很小，稳定映射上的普通访存不是主要问题。
6. `mmap_write_touch_unmap` 明显变慢，复现了 `lat_mmap` 的核心现象。
7. `munmap_after_write_touch` 的额外时间几乎覆盖了完整写路径的额外时间，是当前最明确的瓶颈点。

因此，当前最有依据的判断是：

```text
pKVM 下 lat_mmap 写路径变慢，主要不是 mmap 建立，也不是 first-touch 访问本身，
而是 touch 之后解除映射时的 munmap teardown 被显著放大。
```

后续 pKVM 优化和插桩应优先围绕 `munmap_after_write_touch` 展开，而不是泛泛地观察整个 `lat_mmap` 总时间。

## 7. 后续建议

建议下一步按这个顺序推进：

1. 在 pKVM hyp 侧添加 `munmap` teardown 相关 counter，优先统计 stage-2 unmap/protect 次数、TLBI 次数和耗时。
2. 先单独跑 `munmap_after_write_touch`，用 8 MB、16 MB、64 MB 三个 size 做重点采样。
3. 对同一轮测试同时记录 host 侧 `perf stat`，至少包括 page faults、cycles、TLB 相关事件。
4. 复测时尽量固定 THP、ASLR、CPU 频率和后台负载，把 Kaitian 当前定位数据升级为受控数据。
5. 如果 counter 证明 `munmap_after_write_touch` 触发大量 stage-2 teardown 或 TLBI，再考虑 range/batch TLBI、合并连续 stage-2 unmap、延迟清理等优化方向。

这些优化必须以 pKVM 的内存所有权和隔离语义为边界，不能为了降低 `munmap` 成本留下 stale mapping 或权限泄漏。
