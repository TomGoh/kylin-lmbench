# Kaitian mmap-split NVHE 测试记录

**日期**：2026-06-11
**机器**：Kaitian / `ryuu`
**当前模式**：NVHE
**原始结果**：[results/mmap-split-kaitian/nvhe.csv](../../results/mmap-split-kaitian/nvhe.csv)
**测试项目**：[experiments/mmap-split](../../experiments/mmap-split)

## 1. 环境确认

本次测试前先检查 Kaitian 当前环境：

```text
hostname: ryuu
kernel: Linux ryuu 6.6.30+ #637 SMP Wed May 13 17:04:48 CST 2026 aarch64
cmdline: kvm-arm.mode=nvhe hyp_trace_printk=1
dmesg: Hyp mode initialized successfully
lsm: capability,kysec,box
thp: [always] madvise never
aslr: 2
core: 0
```

因此，这组结果是 Kaitian 当前 NVHE 环境下的 mmap split 基线。它尚未与 pKVM 对照，也不是关闭 THP/ASLR/LSM 后的严格受控数据。

## 2. 计时口径修正

第一次试跑时，远端没有 lmbench `lmdd`，脚本退到了 `truncate` 创建 backing file。这样会产生 sparse file，不适合作为正式数据来源。随后已修正测试脚本：

1. backing file 优先使用 `lmdd ... fsync=1` 写满。
2. 如果远端没有 `lmdd`，使用 `dd if=/dev/zero bs=1M conv=fsync` 写满，避免 sparse file。
3. 使用 `REFILL=1` 强制重建 backing file，避免复用上一轮 sparse 文件。
4. C benchmark 默认执行 `WARMUPS=1`，也就是正式计时前先执行一次不计时的同类操作。

本次正式 NVHE 测试使用的是修正后的口径：

```text
backing_fill=dd if=/dev/zero bs=1M conv=fsync
warmups=1
touch_divisor=10
stride_kb=16
runs=10
core=0
```

这与仓库已有 `lat_mmap_precise` 的核心口径保持一致：

```text
file-backed MAP_SHARED
触摸前 size/10 字节
触摸步长 16 KB
正式计时前做一次不计时 warmup
使用 CLOCK_MONOTONIC 纳秒计时
```

与原版 lmbench harness 的差别是：这里不使用 `benchmp()` 的自适应 iteration/repetition 机制，而是显式指定每个 size 的 iteration 数，并输出纳秒级结果。这样做是为了让每个拆分模块的计时边界更清楚。

## 3. 运行命令

同步测试项目到 Kaitian 后运行：

```bash
cd ~/kylin-lmbench
MODE=nvhe CORE=0 RUNS=10 REFILL=1 WARMUPS=1 scripts/mmap-split-bench.sh
python3 scripts/analyze-mmap-split.py nvhe
```

输出文件：

```text
~/kylin-lmbench/results/mmap-split/nvhe.csv
```

并已拉回本地：

```text
results/mmap-split-kaitian/nvhe.csv
```

## 4. 测试模块

本次测试覆盖 12 个拆分模块：

| 模块 | 计时内容 | 目的 |
|---|---|---|
| `openclose` | `open + close` | backing file 打开/关闭基线 |
| `mmap_unmap` | `mmap + munmap`，不触摸 | 纯映射建立/拆除 |
| `mmap_populate_unmap` | `mmap(MAP_POPULATE) + munmap` | populate 映射成本 |
| `mmap_write_touch_unmap` | `mmap + 写触摸 + munmap` | 对齐原版 `lat_mmap` 写触摸路径 |
| `mmap_read_touch_unmap` | `mmap + 读触摸 + munmap` | 读 fault 路径 |
| `write_touch_cold` | 只计时首次写触摸 | 写 first-touch/page fault |
| `read_touch_cold` | 只计时首次读触摸 | 读 first-touch/page fault |
| `write_touch_hot` | 预触摸后重复写 | 稳定映射上的写访问 |
| `read_touch_hot` | 预触摸后重复读 | 稳定映射上的读访问 |
| `munmap_after_no_touch` | 未触摸后只计时 `munmap` | 未 fault 映射 teardown |
| `munmap_after_write_touch` | 写触摸后只计时 `munmap` | 写触摸后 teardown |
| `munmap_after_read_touch` | 读触摸后只计时 `munmap` | 读触摸后 teardown |

## 5. 关键结果

下表为 10 轮中位数，单位为 us/iteration。

| size | mmap_unmap | write_touch_cold | read_touch_cold | munmap_after_write_touch | munmap_after_read_touch | mmap_write_touch_unmap | mmap_read_touch_unmap |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 3.795 | 3.729 | 3.175 | 3.065 | 4.308 | 8.549 | 9.511 |
| 1 MB | 3.933 | 7.232 | 7.021 | 4.308 | 6.988 | 14.328 | 17.243 |
| 2 MB | 3.328 | 11.705 | 12.715 | 6.581 | 12.268 | 21.047 | 27.695 |
| 4 MB | 3.244 | 22.415 | 20.576 | 9.284 | 18.742 | 34.399 | 42.352 |
| 8 MB | 2.986 | 42.961 | 37.280 | 14.759 | 31.245 | 59.333 | 69.660 |
| 16 MB | 3.070 | 82.214 | 72.990 | 25.838 | 57.751 | 109.404 | 130.669 |
| 64 MB | 3.210 | 333.541 | 293.674 | 90.215 | 202.422 | 428.058 | 498.423 |

稳定映射上的 hot touch 很小：

| size | write_touch_hot | read_touch_hot |
|---:|---:|---:|
| 0.5 MB | 0.005 | 0.008 |
| 1 MB | 0.007 | 0.012 |
| 2 MB | 0.012 | 0.032 |
| 4 MB | 0.056 | 0.091 |
| 8 MB | 0.130 | 0.167 |
| 16 MB | 0.452 | 0.461 |
| 64 MB | 2.346 | 2.618 |

`MAP_POPULATE` 成本明显更高：

| size | mmap_populate_unmap |
|---:|---:|
| 0.5 MB | 48.095 |
| 1 MB | 91.769 |
| 2 MB | 178.804 |
| 4 MB | 351.467 |
| 8 MB | 692.322 |
| 16 MB | 1390.439 |
| 64 MB | 5523.292 |

## 6. 64 MB 拆分观察

64 MB 是和前面 `lat_mmap` 精测最相关的 size。NVHE 下结果：

```text
mmap_unmap:                  3.210 us
write_touch_cold:          333.541 us
munmap_after_write_touch:    90.215 us
mmap_write_touch_unmap:     428.058 us
write_touch_hot:              2.346 us
```

这说明在 NVHE 下，`mmap_write_touch_unmap` 的主要时间来自：

```text
首次写触摸 cold page fault / 建表路径
写触摸后的 munmap teardown 路径
```

纯 `mmap + munmap` 不触摸时只有约 3.2 us，不是主要项。热映射上的重复触摸只有约 2.3 us，也不是主要项。

读路径也类似，但 `munmap_after_read_touch` 比写路径更高：

```text
read_touch_cold:            293.674 us
munmap_after_read_touch:    202.422 us
mmap_read_touch_unmap:      498.423 us
read_touch_hot:               2.618 us
```

这提示后续 pKVM 对照时，需要重点观察：

```text
write_touch_cold / read_touch_cold 是否被放大
munmap_after_write_touch / munmap_after_read_touch 是否被放大
mmap_unmap 是否仍保持很小
hot touch 是否仍保持基本不变
```

## 7. 当前结论

这组 NVHE 数据本身还不能说明 pKVM 开销来源，但已经给出后续对照的基线：

1. 在 NVHE 下，不触摸的 `mmap_unmap` 基本是常数级小开销，64 MB 约 3.2 us。
2. `mmap_write_touch_unmap` 随 size 增长，64 MB 约 428 us，主要来自 cold write touch 和 touched munmap。
3. `mmap_read_touch_unmap` 64 MB 约 498 us，read touch 后 munmap 成本更高。
4. hot touch 极小，说明稳定映射上的访问成本远小于建表和拆表成本。
5. `MAP_POPULATE` 成本很高，不适合作为直接替代优化方向，但可用于观察“提前建页表”的上限成本。

下一步应在 Kaitian 切回 pKVM 后，用完全相同口径运行：

```bash
MODE=pkvm CORE=0 RUNS=10 REFILL=1 WARMUPS=1 scripts/mmap-split-bench.sh
```

然后用：

```bash
python3 scripts/analyze-mmap-split.py nvhe pkvm
```

比较 pKVM 相对 NVHE 的放大项，定位 pKVM 的主要额外成本是在 cold touch 还是 munmap teardown。
