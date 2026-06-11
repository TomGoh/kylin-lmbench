# LMDB 与 pKVM 宿主机 mmap 开销测试方案

**日期**：2026-06-10
**相关背景**：[lat-mmap-test-walkthrough.zh-CN.md](lat-mmap-test-walkthrough.zh-CN.md)、[pkvm-mmap-overhead-analysis.md](pkvm-mmap-overhead-analysis.md)
**相关脚本**：[scripts/lmdb-pkvm-bench.c](../../scripts/lmdb-pkvm-bench.c)、[scripts/lmdb-pkvm-bench.sh](../../scripts/lmdb-pkvm-bench.sh)、[scripts/analyze-lmdb-bench.py](../../scripts/analyze-lmdb-bench.py)

## 1. 为什么 LMDB 值得测

LMDB 是典型的 mmap 型嵌入式 KV 数据库。它的核心设计是把数据库文件映射到进程地址空间中，读事务可以直接在 mmap 出来的地址范围内查找 B+tree 页面。写事务采用 copy-on-write 风格更新页面，并通过提交事务发布新版本。

这使 LMDB 与 `lat_mmap` 的 pKVM 发现存在自然关联：二者都依赖 Linux 的 mmap、页表、缺页处理和文件映射机制。

但是，二者不能简单等同：

| 项目 | lmbench `lat_mmap` | LMDB 常规使用 |
|---|---|---|
| mmap 生命周期 | 每个 iteration 都 `mmap + touch + munmap` | 通常 `mdb_env_open()` 时 mmap 一次，环境长期复用 |
| 访问模式 | 只触摸映射前 `size/10`，再立刻拆除 | 读事务随机访问 B+tree 页面，写事务 copy-on-write 更新页面 |
| 主要测量对象 | 建映射、首次触摸、拆映射 | 环境打开、随机读事务、写事务提交 |
| 对 pKVM 的预期敏感点 | 很高 | 取决于是否频繁 open/close、是否频繁首次触摸新页面、是否受 I/O flush 主导 |

因此，LMDB 测试的目标不是证明 `lat_mmap` 的 42% 会原样出现在数据库吞吐上，而是回答更实际的问题：

```text
pKVM 对真实 mmap 型数据库工作负载是否有可观测影响？
影响主要出现在打开环境、读事务，还是写事务？
```

## 2. 测试拆分

新增 benchmark 把 LMDB 行为拆成三类：

### 2.1 openclose

反复执行：

```text
mdb_env_create
mdb_env_set_mapsize
mdb_env_open
只读事务打开 DBI
mdb_txn_abort
mdb_env_close
```

这个测试最接近 `lat_mmap` 的“建立/拆除映射”方向。它会反复打开和关闭 LMDB 环境，因此更容易暴露 pKVM 在 mmap 建立和 teardown 路径上的开销。

预期：如果 pKVM 的 host stage-2 成本会传导到 LMDB，`openclose` 最可能先出现差异。

### 2.2 read

在已经准备好的数据库上执行随机 key lookup：

```text
打开 LMDB 环境
反复开启只读事务
随机 mdb_get
关闭事务
```

这个测试代表 LMDB 常见读路径。数据库环境只打开一次，映射长期复用。读事务主要沿 B+tree 访问已经 mmap 的页面。

预期：如果数据集已经 warm，读路径可能比 `lat_mmap` 稳定得多，pKVM 差异可能小于 `lat_mmap`。如果数据集很大、TLB miss 和 page walk 更频繁，可能出现小幅差异。

### 2.3 write

在已有数据库上追加写入顺序 key：

```text
打开 LMDB 环境
按 batch 开写事务
mdb_put 多条记录
mdb_txn_commit
```

默认使用 `MDB_NOSYNC | MDB_NOMETASYNC`，目的是降低磁盘 flush 对结果的支配程度。如果使用完全同步提交，结果很可能主要反映存储设备和文件系统 flush，而不是 pKVM 的 mmap/page-table 成本。

预期：写路径可能受 page dirtying、copy-on-write、文件系统和存储 flush 共同影响，需要谨慎解释。

## 3. 环境依赖

需要安装 LMDB 开发头文件和库：

```text
lmdb.h
liblmdb.so
```

在 Debian/Ubuntu/Kylin 类系统上通常来自：

```bash
sudo apt install liblmdb-dev
```

当前仓库环境中尚未安装 `lmdb.h`，因此本地只完成了脚本落地，未完成编译运行验证。

## 4. 推荐运行方式

每个 KVM 模式单独 reboot，保持与 lmbench 主机侧实验一致的环境控制：

```bash
sudo ./prepare-host.sh
```

然后运行对应模式：

```bash
MODE=kvmoff FRESH=1 bash scripts/lmdb-pkvm-bench.sh
MODE=pkvm   FRESH=1 bash scripts/lmdb-pkvm-bench.sh
```

如果要完整对齐 N90 4 模式矩阵：

```bash
MODE=kvmoff FRESH=1 bash scripts/lmdb-pkvm-bench.sh
MODE=vhe    FRESH=1 bash scripts/lmdb-pkvm-bench.sh
MODE=nvhe   FRESH=1 bash scripts/lmdb-pkvm-bench.sh
MODE=pkvm   FRESH=1 bash scripts/lmdb-pkvm-bench.sh
```

每个命令会：

1. 编译 `scripts/lmdb-pkvm-bench.c` 到 `bin/lmdb-pkvm-bench`。
2. 在 `/tmp/lmdb-pkvm-bench-db-<mode>` 准备 LMDB 数据库。
3. 将结果写入 `results/lmdb-bench/<mode>/`。
4. 记录 `/proc/cmdline`、LSM、THP、ASLR 等环境信息。

默认参数：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `RECORDS` | 1000000 | 初始准备的记录数 |
| `VALUE_SIZE` | 256 | value 字节数 |
| `MAP_MB` | 4096 | LMDB map size |
| `BATCH` | 1000 | 每个写事务插入记录数 |
| `READ_OPS` | 5000000 | 每轮随机读取次数 |
| `TXN_BATCH` | 1000 | 每个读事务内的 lookup 数 |
| `WRITE_RECORDS` | 200000 | 每轮追加写入记录数 |
| `OPENCLOSE_ITERS` | 1000 | 每轮 open/close 次数 |
| `RUNS` | 5 | 重复轮数 |
| `NOSYNC` | 1 | 写入使用 `MDB_NOSYNC | MDB_NOMETASYNC` |

可按需要覆盖，例如：

```bash
MODE=pkvm FRESH=1 RECORDS=5000000 MAP_MB=8192 READ_OPS=20000000 RUNS=10 \
  bash scripts/lmdb-pkvm-bench.sh
```

## 5. 汇总结果

收集至少 `kvmoff` 和 `pkvm` 两组后运行：

```bash
python3 scripts/analyze-lmdb-bench.py
```

如果也有 VHE/NVHE，脚本会自动纳入：

```text
results/lmdb-bench/kvmoff/
results/lmdb-bench/vhe/
results/lmdb-bench/nvhe/
results/lmdb-bench/pkvm/
```

输出包括：

| 指标 | 含义 |
|---|---|
| `prepare ops/s` | 初始建库吞吐 |
| `openclose us/op` | 每次打开/关闭环境平均耗时 |
| `read ops/s` | 随机读吞吐 |
| `read ns/op` | 每次随机读平均耗时 |
| `write ops/s` | 追加写吞吐 |
| `write ns/op` | 每条追加写平均耗时 |

## 6. 结果解释原则

建议优先看以下问题：

1. `openclose` 是否显著慢于 kvmoff/VHE/NVHE。
2. `read` 是否基本持平。
3. `write` 的差异是否大于轮间波动，并且是否在 `NOSYNC=1` 下仍然存在。

如果结果呈现：

```text
openclose 明显变慢
read 基本持平
write 小幅或不稳定
```

这会和 lmbench `lat_mmap` 的机制判断一致：pKVM 的主要开销集中在映射建立、首次触摸、拆除或相关页表维护路径，而不是稳定映射上的普通访问。

如果结果呈现：

```text
read 也明显变慢
```

则需要进一步区分：

1. 是否数据集超过 LLC/TLB 有效覆盖范围。
2. 是否 page cache 冷热状态不同。
3. 是否读事务频繁重新打开导致开销被放大。
4. 是否 pKVM 的 stage-2 walk 对大工作集随机访问产生了可见影响。

如果结果呈现：

```text
write 明显变慢
```

需要额外确认：

1. `NOSYNC=1` 和 `NOSYNC=0` 是否结论一致。
2. 文件系统和块设备延迟是否主导结果。
3. commit batch 大小是否改变结论。
4. 数据库是否接近 map size 或触发异常扩容路径。

## 7. 推荐报告表述

推荐：

```text
LMDB 使用 mmap 作为核心访问机制，因此可以作为 lmbench `lat_mmap` 之外的应用级补充测试。
但 LMDB 常规读写通常复用长期存在的 mmap 环境，不等价于 `lat_mmap` 的反复 mmap/touch/munmap。
本实验将 LMDB 拆分为 open/close、随机读、追加写三类路径，以判断 pKVM 的 mmap 建表开销是否传导到真实数据库工作负载。
```

不推荐：

```text
LMDB 使用 mmap，所以它一定会慢 42%。
```

这个说法过强，因为 `lat_mmap` 的 42% 对应的是特定微基准路径，而不是所有 mmap 型应用的完整性能。
