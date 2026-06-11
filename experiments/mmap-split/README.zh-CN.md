# mmap split microbench

这个小项目用于把 lmbench `lat_mmap` 拆成更小的测试模块。目标是定位 pKVM 下 `lat_mmap` 和 LMDB `openclose` 变慢的具体来源：

```text
mmap 建立成本
首次触摸 page fault / 建表成本
热映射上的访问成本
munmap teardown / TLB invalidation 成本
MAP_POPULATE 成本
open/close backing file 成本
```

## 1. 为什么不直接继续用 `lat_mmap`

原版 `lat_mmap` 一轮包含：

```text
mmap
写触摸前 size/10 区域，步长 16 KB
munmap
```

它可以说明整条路径慢，但不能说明慢在 `mmap`、first-touch 还是 `munmap`。本项目把这些阶段拆开，便于和 pKVM hyp 侧 counter 对齐。

## 2. 编译

```bash
cd experiments/mmap-split
make
```

也可以直接通过仓库脚本自动编译：

```bash
MODE=pkvm bash scripts/mmap-split-bench.sh
```

## 3. 单项测试用法

```bash
experiments/mmap-split/mmap_split_bench <mode> <size_mb> <iters> <file> [touch_divisor] [stride_kb]
```

默认：

```text
touch_divisor = 10
stride_kb = 16
warmups = 1
```

这与 lmbench `lat_mmap` 默认语义一致：触摸前 `size/10` 字节，步长 16 KB。默认 warmup 为 1 次，目的是对齐仓库中的 `lat_mmap_precise` 口径：正式计时前先执行一次不计时的同类操作，让 backing file/page cache/VMA 快速路径不被首次启动噪声主导。

## 4. 测试模块

| mode | 计时内容 | 用途 |
|---|---|---|
| `openclose` | `open + close` | backing file 打开/关闭基线 |
| `mmap_unmap` | `mmap + munmap`，不触摸 | 建立/拆除映射成本 |
| `mmap_populate_unmap` | `mmap(MAP_POPULATE) + munmap` | 把 populate 成本放进 mmap |
| `mmap_write_touch_unmap` | `mmap + write touch + munmap` | 对齐原版 `lat_mmap` 默认路径 |
| `mmap_read_touch_unmap` | `mmap + read touch + munmap` | 区分读 fault 与写 dirty/fault |
| `write_touch_cold` | 只计时首次写触摸，mmap/munmap 不计时 | first-touch 写路径 |
| `read_touch_cold` | 只计时首次读触摸，mmap/munmap 不计时 | first-touch 读路径 |
| `write_touch_hot` | 预触摸后重复写触摸 | 稳定映射上的写访问 |
| `read_touch_hot` | 预触摸后重复读触摸 | 稳定映射上的读访问 |
| `munmap_after_no_touch` | 只计时未触摸映射的 `munmap` | teardown 基线 |
| `munmap_after_write_touch` | 只计时写触摸后的 `munmap` | dirty/touched 映射 teardown |
| `munmap_after_read_touch` | 只计时读触摸后的 `munmap` | read fault 后 teardown |

## 5. 批量运行

```bash
MODE=nvhe CORE=0 bash scripts/mmap-split-bench.sh
MODE=pkvm CORE=0 bash scripts/mmap-split-bench.sh
```

结果默认写入：

```text
results/mmap-split/<mode>.csv
```

backing file 优先使用 lmbench 的 `lmdd ... fsync=1` 预填；如果当前机器没有 `lmdd`，脚本会退到 `dd if=/dev/zero bs=1M conv=fsync`。不要使用 sparse truncate 文件作为正式数据来源。需要强制重建 backing file 时：

```bash
MODE=nvhe REFILL=1 bash scripts/mmap-split-bench.sh
```

汇总：

```bash
python3 scripts/analyze-mmap-split.py nvhe pkvm
```

## 6. 结果解读

如果 `mmap_unmap` 或 `munmap_after_*` 慢，优先看 VMA teardown、stage-2 unmap、TLBI 和环境打开/关闭路径。

如果 `write_touch_cold` 或 `read_touch_cold` 慢，优先看 host memory abort、stage-2 map、page-table allocation 和 batch mapping 机会。

如果 `*_touch_hot` 也慢，说明问题不只在建表，可能和 stage-2 walk、TLB miss 或大工作集访问有关。这一点需要和 LMDB read/write 结果交叉验证。
