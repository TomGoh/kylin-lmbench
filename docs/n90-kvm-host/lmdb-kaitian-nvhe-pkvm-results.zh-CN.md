# Kaitian LMDB NVHE 与 pKVM 对照测试记录

**日期**：2026-06-10
**机器**：Kaitian / `ryuu`
**内核**：`Linux ryuu 6.6.30+ #637 SMP Wed May 13 17:04:48 CST 2026 aarch64`
**测试对象**：LMDB mmap 型嵌入式 KV 数据库
**测试脚本**：[scripts/lmdb-pkvm-bench.c](../../scripts/lmdb-pkvm-bench.c)、[scripts/lmdb-pkvm-bench.sh](../../scripts/lmdb-pkvm-bench.sh)、[scripts/analyze-lmdb-bench.py](../../scripts/analyze-lmdb-bench.py)
**原始结果**：[results/lmdb-bench-kaitian/nvhe](../../results/lmdb-bench-kaitian/nvhe)、[results/lmdb-bench-kaitian/pkvm](../../results/lmdb-bench-kaitian/pkvm)

## 1. 测试目的

前面的 lmbench 结果显示，pKVM 在宿主机侧最明显的额外开销出现在 `lat_mmap`：该测试每轮都会执行 file-backed `MAP_SHARED` 的 `mmap`、写触摸一部分映射地址，再 `munmap` 拆除映射。64 MB 精测中，pKVM 相对 VHE 慢约 42%。

LMDB 值得作为应用级补充测试，因为它是典型的 mmap 型数据库。LMDB 会把数据库文件映射到进程虚拟地址空间，读事务直接沿 mmap 出来的 B+tree 页面查找 key，写事务通过 copy-on-write 更新页面并提交新版本。

不过，LMDB 的常规使用方式和 lmbench `lat_mmap` 不完全一样：

| 项目 | lmbench `lat_mmap` | LMDB 常规路径 |
|---|---|---|
| mmap 生命周期 | 每个 iteration 都 `mmap + touch + munmap` | 通常 `mdb_env_open()` 时 mmap 一次，环境长期复用 |
| 访问模式 | 只触摸映射前 `size/10`，再立刻拆除 | 读事务访问 B+tree 页面，写事务 copy-on-write |
| 主要测量对象 | 建映射、首次触摸、拆映射 | 环境打开、随机读事务、写事务提交 |
| 对 pKVM mmap 建表开销的敏感度 | 高 | 取决于是否频繁打开环境、是否频繁首次触摸新页面 |

因此，这次测试的核心问题不是“LMDB 是否也慢 42%”，而是：

```text
pKVM 的 mmap 建表/拆表开销是否会传导到真实 LMDB 工作负载？
如果会，主要体现在 open/close、随机读，还是写事务？
```

## 2. 测试实现

本次使用仓库新增的 `lmdb-pkvm-bench` 小程序。Kaitian 上只有 `liblmdb.so.0` 运行库，没有 `lmdb.h` 开发头文件，因此 C 程序通过 `dlopen("liblmdb.so.0")` 动态加载 LMDB API，避免依赖 `liblmdb-dev`。

测试拆成四个阶段：

| 阶段 | 行为 | 主要观察对象 |
|---|---|---|
| `prepare` | 创建 LMDB 环境并写入初始记录 | 初始建库吞吐 |
| `openclose` | 反复 `mdb_env_open`、打开只读事务、关闭环境 | 环境打开/关闭成本，最接近 mmap 建立/拆除 |
| `read` | 已打开环境上执行随机 `mdb_get` | 长期 mmap 环境上的随机读 |
| `write` | 在已有 DB 上追加写入顺序 key | 写事务和 copy-on-write 路径 |

默认写入使用：

```text
MDB_NOSYNC | MDB_NOMETASYNC
```

这样做是为了降低存储设备 flush 对结果的支配程度。否则写事务可能主要反映块设备和文件系统同步延迟，而不是 mmap/page-table 相关路径。

## 3. 运行参数

NVHE 与 pKVM 使用同一组参数：

| 参数 | 值 | 含义 |
|---|---:|---|
| `RECORDS` | 1,000,000 | 初始记录数 |
| `VALUE_SIZE` | 256 B | 每条 value 大小 |
| `MAP_MB` | 4096 MB | LMDB map size |
| `BATCH` | 1000 | 每个写事务插入记录数 |
| `READ_OPS` | 5,000,000 | 每轮随机读取次数 |
| `TXN_BATCH` | 1000 | 每个只读事务内的 lookup 数 |
| `WRITE_RECORDS` | 200,000 | 每轮追加写入记录数 |
| `OPENCLOSE_ITERS` | 1000 | 每轮 open/close 次数 |
| `RUNS` | 5 | 重复轮数 |
| `NOSYNC` | 1 | 使用 `MDB_NOSYNC | MDB_NOMETASYNC` |

运行命令：

```bash
cd ~/kylin-lmbench
MODE=pkvm FRESH=1 bash scripts/lmdb-pkvm-bench.sh
MODE=nvhe FRESH=1 bash scripts/lmdb-pkvm-bench.sh
python3 scripts/analyze-lmdb-bench.py nvhe pkvm
```

## 4. 环境记录

两组测试都在 Kaitian `ryuu` 上完成，内核版本一致：

```text
Linux ryuu 6.6.30+ #637 SMP Wed May 13 17:04:48 CST 2026 aarch64
```

NVHE cmdline：

```text
kvm-arm.mode=nvhe hyp_trace_printk=1
```

pKVM cmdline：

```text
kvm-arm.mode=protected hyp_trace_printk=1
```

两组共同环境：

```text
lsm=capability,kysec,box
thp=[always] madvise never
aslr=2
```

这个环境不是最终论文级受控环境。它没有关闭 THP，没有关闭 ASLR，也保留了 `kysec,box` LSM。因此本报告先把它作为 Kaitian 上的应用级探索结果，而不是严格的最终性能数字。

## 5. 汇总结果

下表使用 5 轮中位数。`prepare` 只有一次建库结果。

| 指标 | NVHE | pKVM | pKVM 相对 NVHE | 解释 |
|---|---:|---:|---:|---|
| prepare ops/s | 1,998,221.9 | 1,995,298.5 | -0.15% | 初始建库基本持平 |
| openclose us/op | 85.981 | 116.336 | +35.30% | pKVM 打开/关闭环境明显更慢 |
| read ops/s | 819,652.3 | 808,266.1 | -1.39% | 随机读吞吐小幅下降 |
| read ns/op | 1220.030 | 1237.216 | +1.41% | 随机读延迟小幅增加 |
| write ops/s | 1,785,718.3 | 1,787,426.4 | +0.10% | 追加写基本持平 |
| write ns/op | 559.999 | 559.464 | -0.10% | 追加写基本持平 |

最明显的差异是 `openclose`：pKVM 每次 open/close 中位数为 116.336 us，NVHE 为 85.981 us，pKVM 慢约 35.30%。

随机读和追加写没有出现同量级差异。读路径 pKVM 约慢 1.4%，写路径基本完全持平。

## 6. 每轮数据与波动

### 6.1 openclose

| run | NVHE us/op | pKVM us/op |
|---:|---:|---:|
| 1 | 85.981 | 100.870 |
| 2 | 84.990 | 116.336 |
| 3 | 88.183 | 140.298 |
| 4 | 85.645 | 117.429 |
| 5 | 88.130 | 97.867 |
| 中位数 | 85.981 | 116.336 |
| MAD% | 1.15% | 13.29% |

`openclose` 是本次最接近 `lat_mmap` 的 LMDB 子测试，因为它反复打开和关闭 LMDB 环境，会反复走环境 mmap 建立与 teardown 路径。pKVM 在该项上不仅中位数更高，轮间波动也更大。

这与 lmbench `lat_mmap` 的方向一致：当工作负载频繁建立/拆除映射时，pKVM 更容易显现额外成本。

### 6.2 read

| run | DB records | NVHE ns/op | pKVM ns/op |
|---:|---:|---:|---:|
| 1 | 1,000,000 | 1096.265 | 1105.398 |
| 2 | 1,200,000 | 1166.328 | 1176.174 |
| 3 | 1,400,000 | 1220.030 | 1237.216 |
| 4 | 1,600,000 | 1267.724 | 1280.673 |
| 5 | 1,800,000 | 1332.828 | 1316.624 |
| 中位数 | - | 1220.030 | 1237.216 |
| MAD% | - | 4.40% | 4.93% |

读测试每轮之后都会执行一轮追加写，所以后续 read 面对的数据库记录数逐步增加：1.0M、1.2M、1.4M、1.6M、1.8M。随着数据库增大，随机读延迟自然上升。这是测试脚本当前设计带来的趋势，不应误解为单一环境随时间退化。

pKVM 与 NVHE 的 read 差距很小。中位数上 pKVM 慢约 1.41%，但这个幅度低于 read 自身随数据库规模增长带来的轮间变化。

### 6.3 write

| run | 起始记录数 | NVHE ns/op | pKVM ns/op |
|---:|---:|---:|---:|
| 1 | 1,000,000 | 557.535 | 545.789 |
| 2 | 1,200,000 | 555.712 | 558.033 |
| 3 | 1,400,000 | 565.247 | 562.632 |
| 4 | 1,600,000 | 559.999 | 562.099 |
| 5 | 1,800,000 | 562.915 | 559.464 |
| 中位数 | - | 559.999 | 559.464 |
| MAD% | - | 0.52% | 0.47% |

写路径在两种模式下非常接近。pKVM 与 NVHE 的中位数差异约 -0.10%，低于测量噪声，可以视为持平。

这说明在当前参数下，LMDB 追加写事务没有表现出类似 `lat_mmap` 的明显 pKVM 开销。

## 7. 机制解释

本次结果可以用 LMDB 的 mmap 生命周期解释。

`lat_mmap` 每个 iteration 都执行：

```text
mmap
触摸一部分页面
munmap
```

它把建映射、首次触摸和拆映射全部放进计时区，因此对 pKVM 的 host stage-2 相关维护路径非常敏感。

LMDB 常规读写则不同。典型流程是：

```text
mdb_env_open 时 mmap 数据库文件
之后多个读写事务复用同一个环境和同一段 mmap 区域
mdb_env_close 时释放环境
```

因此：

1. `openclose` 会频繁执行环境打开和关闭，最容易暴露 pKVM 在 mmap 建立/拆除路径上的成本。
2. `read` 在已经打开的环境上执行随机查找，更多测的是长期映射上的 B+tree 页面访问，因此 pKVM 差异较小。
3. `write` 主要受 LMDB copy-on-write、事务提交、page dirtying 和文件系统行为影响。在 `NOSYNC=1` 下，当前结果基本持平。

这和我们对 lmbench `lat_mmap` 的解释一致：pKVM 的主要应用级影响更可能出现在“频繁打开/关闭 mmap 环境”这类路径上，而不是长期复用 mmap 后的稳定读写路径上。

## 8. 当前结论

在 Kaitian 当前环境下，LMDB NVHE 与 pKVM 对照结果显示：

1. `openclose` 是最明显差异项：pKVM 比 NVHE 慢约 35.30%。
2. 随机读基本持平，仅有约 1.4% 的小幅下降。
3. 追加写基本持平，差异约 0.1%，可视为噪声。
4. 这支持一个更细化的判断：pKVM 的 mmap 相关成本会传导到 LMDB 的环境打开/关闭路径，但不会等比例传导到已经打开环境后的常规读写吞吐。

建议报告表述：

```text
Kaitian 上的 LMDB 应用级测试显示，pKVM 对长期打开的 LMDB 读写路径影响很小，但对频繁打开和关闭 LMDB 环境的 openclose 路径有明显影响。该现象与 lmbench `lat_mmap` 中 pKVM 对 mmap 建立/拆除路径更敏感的结论一致。
```

不建议表述：

```text
LMDB 使用 mmap，所以 pKVM 下 LMDB 整体慢 35% 或 42%。
```

这个说法不准确。本次只有 `openclose` 慢约 35%，read/write 并没有同等幅度的下降。

## 9. 后续改进

如果要把这组结果写成更正式的数据，建议补充以下控制：

1. 对 NVHE 和 pKVM 都运行统一的 `prepare-host.sh`，至少固定 CPU 频率、THP、ASLR。
2. 增加 `kvmoff` 和 VHE 两组，形成完整 4 模式矩阵。
3. 把 read 测试改成固定数据库大小，避免每轮 write 后记录数增长造成 read 延迟自然上升。
4. 分别测试 warm page cache 与 cold page cache。
5. 增加 `NOSYNC=0`，单独观察真实同步写入场景，但解释时要区分存储 flush 成本。
6. 对 `openclose` 增加更多轮数，因为当前 pKVM 的 MAD% 较高。
