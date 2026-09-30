# memlat-probe：内存访问延迟根因探针

本目录是 2026-09-30 调查"pKVM 宿主机内存访问延迟"时写的测量工具和分析脚本。
调查的来龙去脉见 [docs/memlat/](../../docs/memlat/README.md)，原始日志见
[results/memlat-n80-20260930/](../../results/memlat-n80-20260930/)。

这些程序**全部跑在宿主机 Linux 上**，不在虚拟机里面跑，也不启动虚拟机。
（2026-09-30 在 N80 上测量时，后台有一个开机自启动的保护虚拟机在运行；`vm-frames.py` 和 `frames2` 的分类模式就是为了量它对宿主机的影响。）

## 程序

| 程序 | 回答的问题 |
| --- | --- |
| `probe.c` / `probe2.c` | 按 lmbench `lat_mem_rd` 的两种访问方式（顺序、随机）跑指针追逐，同时读硬件计数器：每次访问发生多少次页表遍历、多少次缓存回填。以 root 运行时还会读出缓冲区每一页的物理页号 |
| `probe3.c` | 同上，另外可以像 lmbench 那样在每个计时区间之前重写一遍指针链（`rebuild=1`），并在每个计时区间前后读一次片上互连的频率；11 个区间的时间按先后全部打印 |
| `layout.c` | **同一组物理页**按不同的虚拟顺序排列（物理升序、物理降序、随机），顺序访问延迟会不会变 |
| `frames.c` | 物理页集中在一处还是分散在各处，随机访问延迟会不会变 |
| `frames2.c` | 同一个进程里，按物理地址所在的 1 GiB 区间逐个取页做随机访问；每个区间测两遍（第二遍把同一批页搬到新的虚拟地址）。给它一份"虚拟机内存占了哪些 2 MiB 区间"的清单时，每个区间再分成与虚拟机共用 2 MiB 区间的页（shared）和不共用的页（clear）两类分别测 |
| `vm-frames.py` | 只读：读出正在运行的虚拟机的内存落在哪些 1 GiB、2 MiB 物理区间里，并写出上面那份清单 |
| `bgload.c` | 在另一个核上连续读或写一块内存，制造背景内存流量 |
| `nocsample.c` | 每隔固定时间记录一次片上互连频率，不 fork |
| `nothp.c` | 对一个进程及其子进程关掉透明大页（`prctl`），不改系统设置。用来让 lmbench 的 `malloc` 缓冲区使用 4 KiB 页 |

`probe.c` 是第一版，`probe2.c` 增加了"首次触页顺序"选项和反向连续度指标，`probe3.c` 是为平台状态实验写的。
三个都保留，是因为各自产生了一部分已存档的日志。

## 访问方式与 lmbench 的对应关系

指针链按 `src/lib_mem.c`（lmbench 3.0-a9）的算法构造：

- 顺序（`seq`）对应 `stride_initialize`：`addr[i]` 指向 `addr[i+stride]`，首次写入按地址升序。
- 随机（`rand`）对应 `thrash_initialize` 的页对齐分支：先对整个 `maxlen` 缓冲区的所有页做一次随机排列，
  取前 `size/4096` 页；每一跳换到排列中的下一页，页内的字偏移按位反转顺序递增。
  所以每一跳都落在不同的页上，访问页的顺序是一个固定的环。

与 lmbench 的差别：

- 页的随机排列用的是 Fisher-Yates 洗牌。lmbench 自己的 `permutation()` 是有偏的（用到的页略偏向缓冲区前部），
  对每跳的事件计数没有实质影响。
- 缓冲区用 `mmap` 直接分配并 `madvise(MADV_NOHUGEPAGE)`，相当于 lmbench 在 THP=never 下的 `malloc`。
- `probe`、`probe2` 只在开头建一次指针链，之后只读；lmbench 在**每个计时区间之前**都把指针链重写一遍。
  只看稳态延迟时两者一样；涉及按总线流量调频的策略时不一样，那时用 `probe3` 的 `rebuild=1`。
- 计时用 `clock_gettime(CLOCK_MONOTONIC)`，11 次重复，每次约 0.1 秒，同时给出最小值和中位数。lmbench 报告的是最小值。
- 每次调用是一个独立进程，对应 lmbench 每个（步长，大小）点 fork 一个子进程。

要与论文的数字直接对照时，用 lmbench 原版的 `lat_mem_rd`：`build-lmbench-tools.sh` 从 `../../src` 单独编译出
`lat_mem_rd` 和 `bw_mem`（源码不改）。

## 硬件计数器

用 `perf_event_open` 直接打开 PMU 原始事件，只统计用户态（`exclude_kernel`）。
日志里的 `evXX=` 是"每一跳的事件数"。

| 代码 | 事件 | 在本调查中的用途 |
| --- | --- | --- |
| `0x11` | cpu_cycles | 每跳周期数 |
| `0x2d` | l2d_tlb_refill | 二级 TLB 回填，即需要一次页表遍历 |
| `0x05` | l1d_tlb_refill | 一级数据 TLB 未命中 |
| `0x2a` | l3d_cache_refill | L3 回填。在这个核上它不是"从内存取数的次数"的干净计数：4 MB 顺序访问时每跳就有 0.48 次，而延迟只有 4.4 ns |
| `0x17` | l2d_cache_refill | L2 回填 |
| `0x03` | l1d_cache_refill | L1 回填 |
| `0x13` | mem_access | 访存次数，用来核对每跳恰好一次 |

sysfs 里没有具名的 `dtlb_walk` 事件，所以用 `l2d_tlb_refill` 代表页表遍历次数。
原始事件 `0x34` 可用；2026-06 在同型号核上的 perf 数据里，它与 `l2d_tlb_refill` 相差不到 1%。

## 编译

```bash
make                         # probe probe2 probe3 layout frames frames2 bgload nocsample nothp
sh build-lmbench-tools.sh    # lat_mem_rd bw_mem（lmbench 原版）
```

需要 root 才能从 `/proc/self/pagemap` 读到物理页号；不用 root 也能跑 `probe*`，只是物理布局字段为 `na`。
参数含义见各源文件开头的注释。

## 运行脚本

脚本都假定程序和脚本放在同一个目录（2026-09-30 在 N80 上是 `/tmp/kx-memprobe`），日志写在这个目录里。

**不改任何系统设置的（2026-09-30 在 N80 上执行过）：**

| 脚本 | 产生的日志 | 内容 |
| --- | --- | --- |
| `run_all.sh` | `expA` `expC` `expD` `expB` | 随机访问大小扫描、2 MiB 大页对照、顺序访问步长扫描、8 MB 附近重复 30 轮 |
| `run2.sh` | `expL` `expT` | 同一组物理页换顺序、首次触页顺序 |
| `run3.sh` | `expF` | 按物理位置挑选页集合后做随机访问 |
| `run6-current-state.sh` | `expR` `expBG` | 指针链建一次与每个区间前重写的对比；别的核上有内存流量时的表现 |
| `run9-lmbench-current-state.sh` | `expH-*` | lmbench 原版 `lat_mem_rd` 重复多遍（4 KiB 页），同时记录互连频率 |
| `run10-slots.sh` | `expS` | 按 1 GiB 物理区间分别做随机访问 |
| `run11-vm-shared.sh` | `expV` `vm-frames-n80.txt` | 同一个 1 GiB 区间里，与保护虚拟机共用 2 MiB 区间的页和不共用的页分别做随机访问 |
| `run12-vm-shared-sizes.sh` | `expV2` | 上一项在 2–64 MB 各个工作集大小上各做一遍 |

**不改系统设置、但还没有执行的：**

| 脚本 | 产生的日志 | 内容 |
| --- | --- | --- |
| `run5-mode-compare.sh` | `modecmp-<模式>-<时间>/` | 同一台机器换启动模式各跑一遍的对照测量，见下文。需要改启动参数并重启 |

**运行期间临时修改片上互连调频策略的（没有执行）：**

| 脚本 | 产生的日志 | 内容 |
| --- | --- | --- |
| `run4-noc-fixed.sh` | `expG1` | 把互连固定在 1800、1450、1200、900、600 MHz，各测随机访问、顺序访问和流式读写速率 |
| `run7-noc-governors.sh` | `expG2` `expG3` | 在 `performance`、`simple_ondemand`、`stable_ondemand` 三种策略下重复测 8 MB 附近的顺序访问和随机访问，记录每个计时区间后的互连频率；再加上别的核的内存流量 |
| `run8-noc-lmbench.sh` | `expG4-*` | 互连固定在最高频、按流量调频、固定在最低频三种状态下跑 lmbench 原版 `lat_mem_rd` 和 `bw_mem` |
| `run-noc-all.sh` | | 依次执行上面三个，约 1.5 小时 |

这四个脚本会改写 `/sys/class/devfreq/nocfreq/governor`，每个脚本退出时（无论什么原因）把原来的策略写回去，
并在 `meta.log` 最后一行记下恢复后的状态。2026-09-30 它们已放到 N80 上，但本次会话的权限策略不允许执行，
留给机器的使用者决定。

## 分析脚本

```bash
python3 analyze-host-memlat.py        # N90 宿主机四模式数据：论文三个数字、逐轮值、显著性检验、增量曲线
python3 analyze-guest-memlat.py       # N90 上 x-kernel 客户机内的数据（图 8），与宿主机数据分开
python3 analyze-device-logs.py        # N80 下午的实验 A、B、C、D、L、T、F
python3 analyze-state-experiments.py  # N80 傍晚的实验 R、BG、H、S、V、V2，以及 G1–G4（日志存在时）
python3 analyze-mode-compare.py modecmp-none-* modecmp-protected-*   # run5 的输出目录，第一个是对照基准
```

这些脚本只用 Python 标准库，输出是 Markdown 表格。2026-09-30 的输出存在
`results/memlat-n80-20260930/derived/`。

## 在 N90 上补做四模式对照

到 2026-09-30 为止，硬件计数器数据只有 N80 在 protected 一种模式下的；N90 四种模式的数据只有 lmbench 的时间，
而且每种模式只有一次开机，没有记录互连调频状态和 THP 细分开关。所以"保护模式下每次页表遍历更贵"
目前是与数据相符的推断，还不是同机实测。补上这一步的办法：

```bash
make
# 对 kvm-arm.mode=none、nvhe、vhe、protected 各重启一次，每次执行（约 15 分钟）：
sudo sh run5-mode-compare.sh
# 四个输出目录拿回来之后：
python3 analyze-mode-compare.py modecmp-none-* modecmp-nvhe-* modecmp-vhe-* modecmp-protected-*
```

`run5-mode-compare.sh` 做三组测量，并在开始和结束时各记录一次平台状态
（启动参数、内核配置里的 `CONFIG_X1_RMS`、THP 全部开关、CPU 频率、各 devfreq 设备的调频策略与频率、
正在运行的服务）。每跑一个点的前后还各读一次互连频率，写在该点日志行的开头。

| 日志 | 内容 | 对应的问题 |
| --- | --- | --- |
| `rand.log` | 随机访问，14 个大小 × 5 个随机种子 | 各模式每次访问的页表遍历次数、缓存回填次数是否相同；相同的话，protected 每次遍历多花多少个周期 |
| `seq.log` | 64 MB 顺序访问，6 种步长 × 5 次 | 顺序访问时每次跨页多花多少 |
| `llc.log` | 步长 256、4–64 MB，每个点一个新进程，重复 30 轮 | 8 MB 附近的两个取值跟物理页连续度走，还是跟互连频率走 |

判读方法：

- 先看对比脚本输出的第一张表。各次测量除了启动模式以外的列（THP、CPU 频率、互连调频策略和频率）必须一致，
  否则比较的就不是启动模式。
- 随机访问表里，"walks ratio"应当是 1（遍历次数与模式无关），"extra L2 refills"应当接近 0；
  在这个前提下，"extra cycles per walk"就是每次遍历多出来的周期数。
- `llc.log` 那张表里，如果延迟与"互连频率"的秩相关接近 ±1 而与物理连续度无关，两个取值就是互连调频造成的；
  反过来则是物理页布局造成的。

切换启动参数的办法见 `docs/n90-kvm-host/SUMMARY.md` 第 6 节。

## 对系统的影响

- "不改任何系统设置"的那些脚本只在用户态运行，不加载内核模块，不写任何 sysfs 或 procfs 文件。
- `layout`、`frames`、`frames2` 会分配一个较大的内存池（192 MB、1 GiB、3 GiB），运行结束即释放；
  内存紧张的机器上会挤掉一部分页缓存。
- `run6` 的背景流量实验会让另外一到两个核满负荷读写内存约一分钟。
- 以 root 运行只是为了读物理页号。
