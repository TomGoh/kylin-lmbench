# memlat-probe：内存访问延迟根因探针

本目录是 2026-09-30 调查"pKVM 宿主机内存访问延迟"时写的测量工具和分析脚本。
调查的来龙去脉见 [docs/memlat/](../../docs/memlat/README.md)，原始日志见
[results/memlat-n80-20260930/](../../results/memlat-n80-20260930/)。

这些程序**全部跑在宿主机 Linux 上**，不涉及任何虚拟机。

## 它们回答什么问题

| 程序 | 回答的问题 |
| --- | --- |
| `probe.c` / `probe2.c` | 按 lmbench `lat_mem_rd` 的两种访问方式（顺序、随机）跑指针追逐，同时读硬件计数器：每次访问发生多少次页表遍历、多少次缓存回填。以 root 运行时还会读出缓冲区每一页的物理页号 |
| `layout.c` | **同一组物理页**按不同的虚拟顺序排列（物理升序、物理降序、随机），顺序访问延迟会不会变 |
| `frames.c` | 物理页集中在一处还是分散在各处，随机访问延迟会不会变 |

`probe.c` 是第一版，`probe2.c` 在它的基础上增加了"首次触页顺序"选项和反向连续度指标。
两个文件都保留，是因为 `expA`–`expD` 的日志由 `probe` 产生，`expT` 由 `probe2` 产生。

## 访问方式与 lmbench 的对应关系

链表的构造逐行照搬 `src/lib_mem.c`（lmbench 3.0-a9）：

- 顺序（`seq`）对应 `stride_initialize`：`addr[i]` 指向 `addr[i+stride]`，首次写入按地址升序。
- 随机（`rand`）对应 `thrash_initialize` 的页对齐分支：先对整个 `maxlen` 缓冲区的所有页做一次随机排列，
  取前 `size/4096` 页；每一跳换到排列中的下一页，页内的字偏移按位反转顺序递增。
  所以每一跳都落在不同的页上，访问页的顺序是一个固定的环。

与 lmbench 的差别：

- 缓冲区用 `mmap` 直接分配并 `madvise(MADV_NOHUGEPAGE)`，等价于 lmbench 在 THP=never 下的 `malloc`。
- 计时用 `clock_gettime(CLOCK_MONOTONIC)`，11 次重复，每次约 120 ms，同时给出最小值和中位数。
  lmbench 报告的是最小值。
- 每次调用是一个独立进程，对应 lmbench 每个（步长，大小）点 fork 一个子进程。

## 硬件计数器

用 `perf_event_open` 直接打开 PMU 原始事件，只统计用户态（`exclude_kernel`）。
日志里的 `evXX=` 是"每一跳的事件数"。

| 代码 | 事件 | 在本调查中的用途 |
| --- | --- | --- |
| `0x11` | cpu_cycles | 每跳周期数 |
| `0x2d` | l2d_tlb_refill | 二级 TLB 回填，即需要一次页表遍历 |
| `0x05` | l1d_tlb_refill | 一级数据 TLB 未命中 |
| `0x2a` | l3d_cache_refill | L3 回填 |
| `0x17` | l2d_cache_refill | L2 回填 |
| `0x13` | mem_access | 访存次数，用来核对每跳恰好一次 |

FTC862 的 PMU 没有 `dtlb_walk` 事件，所以用 `l2d_tlb_refill` 代表页表遍历次数。

## 编译与运行

```bash
make                      # 生成 probe probe2 layout frames
# 需要 root 才能从 /proc/self/pagemap 读到物理页号；不用 root 也能跑，只是物理布局字段为 na
sudo taskset -c 0 ./probe rand 64 16 64 0 11,2d,5,2a,17,13
sudo taskset -c 0 ./probe seq   8 256 64 0 11,2a,19,17,2d,2b
sudo taskset -c 0 ./layout 8 256 192 11,2a,17,2d,5,13 sorted,shuffled,reversed
sudo taskset -c 0 ./frames 64 16 1024 11,2d,2a,17,5,13 compact
```

参数含义见各源文件开头的注释。

`run_all.sh`、`run2.sh`、`run3.sh` 是 2026-09-30 在 N80 上实际执行的命令序列，原样保留。
它们假定程序放在 `/tmp/kx-memprobe`，换机器时改第一行的目录即可。

| 脚本 | 产生的日志 | 内容 |
| --- | --- | --- |
| `run_all.sh` | `expA` `expC` `expD` `expB` | 随机访问大小扫描、2 MiB 大页对照、顺序访问步长扫描、8 MB 附近重复 30 轮 |
| `run2.sh` | `expL` `expT` | 同一组物理页换顺序、首次触页顺序 |
| `run3.sh` | `expF` | 按物理位置挑选页集合后做随机访问 |
| `run4-noc-governor.sh` | （未执行） | 把互连调频固定在几个频率、再切回自动调频，各测一遍。**会修改系统设置**，2026-09-30 没有执行 |

## 分析脚本

```bash
python3 analyze-host-memlat.py     # N90 宿主机四模式数据：论文三个数字、逐轮值、显著性检验、增量曲线
python3 analyze-device-logs.py     # N80 日志：各实验的汇总表
python3 analyze-guest-memlat.py    # N90 上 x-kernel 客户机内的数据（图 8），与宿主机数据分开
```

两个脚本只用 Python 标准库，输出是 Markdown 表格。2026-09-30 的输出存在
`results/memlat-n80-20260930/derived/`。

## 在 N90 上补做四模式对照

N80 上只测了 protected 一种模式。要在论文平台上拿到同机证据，对 `none`、`nvhe`、`vhe`、`protected`
四种启动方式各跑一遍 `run_all.sh`（每种约 7 分钟），再用 `analyze-device-logs.py` 对比：
预期各模式的页表遍历次数相同，只有 protected 的每跳时间更长，而且多出来的时间随遍历次数同步增长。
切换启动参数的办法见 `docs/n90-kvm-host/SUMMARY.md` 第 6 节。

## 对系统的影响

- `run_all.sh`、`run2.sh`、`run3.sh` 只在用户态运行，不加载内核模块，不改任何系统设置。
- `run4-noc-governor.sh` 是例外：它会临时改写 `/sys/class/devfreq/nocfreq/governor`，退出时恢复。
- `layout` 和 `frames` 会分配一个较大的内存池（192 MB 和 1 GiB），运行结束即释放。
- 以 root 运行只是为了读物理页号。
