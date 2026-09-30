# N80 宿主机内存延迟测量（2026-09-30）

这批数据**全部在宿主机 Linux 上采集**，测量程序跑在虚拟机之外，本次调查没有启动任何虚拟机。
它用来解释论文图 7（N90 宿主机四模式对比）里的内存延迟现象，不涉及图 8 的虚拟机内数据。

**测量期间后台有一个保护虚拟机**：这台机器开机时由 `pvm-manage` 自动启动了一个保护虚拟机
（`crosvm --name pvm`，2 个 vCPU，1 GiB 内存，基本空闲），下午和傍晚的全部测量期间它都在运行，当晚 19:20 才注意到。
它占用的内存页散布在几个 1 GiB 物理区间里，这些页所在的 2 MiB 区间，宿主机二级页表被拆成了 4 KiB 的表项；
取自这些区间的宿主机页做随机访问更慢（实验 S、V）。用到这批数据时要带上这个条件。
论文图 7 的 N90 宿主机数据采集时 `pvm-manage` 是被屏蔽的，没有虚拟机在运行。

## 机器与状态

| 项目 | 值 |
| --- | --- |
| 机器 | 长城 N80F3，8 核 Phytium FTC862（8 个核的 MIDR 均为 `0x700f8620`） |
| 内存 | 2 × 8 GB，共 16 GB |
| 系统 | 银河麒麟桌面 V11 SP1，内核 `6.6.0-79-generic` |
| 启动方式 | `kvm-arm.mode=protected`，`CONFIG_X1_RMS=y`，日志显示 `Protected nVHE mode initialized successfully` |
| 缓存 | L1d 64K 4 路；L2 512K 8 路，每核私有；L3 8M 16 路 8192 组，8 核共享 |
| 页大小 | 4 KiB；系统 THP 设置为 `always`，测量程序对缓冲区使用 `MADV_NOHUGEPAGE` |
| 绑核与频率 | 全部绑定 cpu0，最高 1.9 GHz，调速器 `performance` |
| 互连调频 | `nocfreq` 策略为 `performance`，频率 1800 MHz，本次没有改动。开机后最初约 16.5 秒是驱动默认的按流量调频，之后被改成 `performance`；很可能是桌面电源管理程序改的，没有直接证据 |
| 背景负载 | 桌面会话在运行，负载 0.3–1.2，没有做服务屏蔽；后台有一个空闲的保护虚拟机（见上） |

完整的硬件和软件信息见 `hw-survey-n80.txt`。

**与论文平台的差别**：论文用的是 N90F3（32 GB 内存，主频上限更高），核型号相同。
两台机器的内存条配置不同，N80 的核运行在 1.9 GHz、N90 当时是 1.8 GHz，绝对延迟不能直接比较。
64 MB 随机访问在 N80 上约 155 ns；N90 上有两个水平，干净环境约 185 ns，"快"状态约 150 ns，N80 的值与后者相当
（见 `docs/memlat/memlat-rootcause.zh-CN.md` 第 5 节）。
本目录的数据只用于两件事：每次访问发生多少次页表遍历这类与内存条无关的计数，以及在同一台机器内部做的对照。

**只测了一种模式**：这台机器当天只以 protected 方式启动，没有 nvhe、vhe、kvm-off 的对照。
"protected 比其他模式多多少时间"仍然取自 N90 的四模式数据（`results/n90-day3-host/`）。

## 文件

| 文件 | 内容 | 产生它的命令 |
| --- | --- | --- |
| `expA.log` | 随机访问（步长 16），0.5–64 MB，3 个随机种子 × 2 组计数器 | `experiments/memlat-probe/run_all.sh` |
| `expB.log` | 顺序访问步长 256，4/6/8/12/16/64 MB，每个点一个新进程，重复 30 轮 | 同上 |
| `expC.log` | 随机访问 8 MB 和 64 MB，缓冲区请求 2 MiB 大页（只拿到一部分） | 同上 |
| `expD.log` | 顺序访问 64 MB，步长 64–1024，各 3 次 | 同上 |
| `expL.log` | 同一组物理页按物理升序、随机、物理降序排列后的顺序访问延迟 | `run2.sh` |
| `expT.log` | 首次触页顺序分别为默认、随机、降序时的顺序访问延迟 | `run2.sh` |
| `expF.log` | 按物理位置挑选页集合后的 64 MB 随机访问延迟 | `run3.sh` |
| `expL-smoke.log` `expF-smoke.log` | 上面两个实验在写成脚本之前的第一次手工试跑；`expL-smoke.log` 里物理连续度达到 0.99 | 命令记在文件开头 |
| `meta.log` | 各批次的起止时间和系统负载 | |
| `hw-survey-n80.txt` | 硬件、内核配置、PMU 事件、KVM 启动日志 | |
| `devfreq-survey-n80.txt` | 互连和 GPU 调频设备的状态、可选策略，以及桌面电源管理服务的策略表（只读查看） | |
| `derived/device-tables.md` | 上述日志的汇总表 | `experiments/memlat-probe/analyze-device-logs.py` |
| `derived/host-n90-tables.md` | N90 宿主机四模式数据的对应分析 | `experiments/memlat-probe/analyze-host-memlat.py` |
| `derived/guest-n90-tables.md` | N90 上 x-kernel **客户机内**数据的对应分析（图 8 的数据，不是宿主机数据） | `experiments/memlat-probe/analyze-guest-memlat.py` |

## 日志字段

每行是一次独立进程的运行结果。

- `ns_min` `ns_med` `ns_max`：11 次重复中每跳耗时的最小值、中位数、最大值。
- `evXX`：PMU 事件 `0xXX` 在每一跳上的平均次数。事件代码见 `experiments/memlat-probe/README.zh-CN.md`。
- `contig_frac`：虚拟地址相邻的两页中，物理页号也相邻（后一页比前一页大 1）的比例。
- `rcontig_frac`：同上，但后一页比前一页小 1。
- `color_max` `over16_pages` `thrash_pages_frac`：L3 页颜色统计。颜色是物理页号对 128 取模，每种颜色在 L3 里正好容纳 16 页。
  `thrash_pages_frac` 是落在"超过 16 页的颜色"里的页所占比例。
- `gb_regions` `mb2_regions`：缓冲区的物理页分布在多少个不同的 1 GiB、2 MiB 物理区间里。
- `pfn=na`：没有以 root 运行，读不到物理页号。
