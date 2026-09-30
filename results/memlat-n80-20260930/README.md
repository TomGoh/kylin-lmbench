# N80 宿主机内存延迟测量（2026-09-30）

这批数据**全部在宿主机 Linux 上采集**，测量程序跑在虚拟机之外，本次调查没有启动任何虚拟机。
它用来解释论文图 7（N90 宿主机四模式对比）里的内存延迟现象，不涉及图 8 的虚拟机内数据。

**测量期间后台有一个保护虚拟机**：这台机器开机时由 `pvm-manage` 自动启动了一个保护虚拟机
（`crosvm --name pvm ... --protected-vm`，2 个 vCPU，1 GiB 内存，基本空闲：开机 5 小时 26 分钟里两个 vCPU 线程共用了 88 秒 CPU 时间；
完整命令行和线程的 CPU 时间见 `vm-process-n80.txt`），
全部测量期间它都在运行，当晚 19:20 才注意到。它的内存是 memfd，宿主机上是 4 KiB 页（`shmem_enabled` 为 `never`）。
它占用的内存页散布在几个 1 GiB 物理区间里，这些页所在的 2 MiB 区间，宿主机二级页表被拆成了 4 KiB 的表项；
取自这些区间的宿主机页做随机访问更慢（实验 S、V）。用到这批数据时要带上这个条件。
论文图 7 的 N90 宿主机数据，按采集流程是在 `pvm-manage` 被屏蔽、没有虚拟机运行时采集的；这一点只有流程为据，结果文件里没有进程列表。

## 机器与状态

| 项目 | 值 |
| --- | --- |
| 机器 | 长城 N80F3，8 核 Phytium FTC862（8 个核的 MIDR 均为 `0x700f8620`） |
| 内存 | 2 × 8 GB，共 16 GB |
| 系统 | 银河麒麟桌面 V11 SP1，内核 `6.6.0-79-generic` |
| 启动方式 | `kvm-arm.mode=protected`，`CONFIG_X1_RMS=y`，日志显示 `Protected nVHE mode initialized successfully` |
| 缓存 | L1d 64K 4 路；L2 512K 8 路，每核私有；L3 8M 16 路 8192 组，8 核共享 |
| 页大小 | 4 KiB；系统 THP 设置为 `always`，测量程序对缓冲区使用 `MADV_NOHUGEPAGE`。内核带连续页表项折叠（`CONFIG_ARM64_CONTPTE=y`）和多种尺寸的透明大页，2 MiB 以外的尺寸都是 `never`（`thp-contpte-n80.txt`） |
| 页分配器 | cpu0 的每 CPU 空闲页链表上限约 1600 页（`pagealloc-n80.txt`，23:00 前后读到 1592 和 1655），约 6.3 MB |
| 绑核与频率 | 全部绑定 cpu0，最高 1.9 GHz，调速器 `performance` |
| 互连调频 | `nocfreq` 策略为 `performance`，频率 1800 MHz，本次没有改动。开机后最初约 16.5 秒是驱动默认的按流量调频，之后被改成 `performance`。是谁改的没有查明：只有桌面电源管理程序的二进制里有 devfreq 路径，但它的策略表里没有 `performance` 这一项；`pvm-manage` 和 crosvm 的二进制里没有 devfreq 字样 |
| 背景负载 | 桌面会话在运行，没有做服务屏蔽，各批次起止时记录的 1 分钟负载在 0.2–2.7 之间（`meta.log`）；后台有一个空闲的保护虚拟机（见上） |

完整的硬件和软件信息见 `hw-survey-n80.txt`。

**与论文平台的差别**：论文用的是 N90F3（32 GB 内存，主频上限更高），核型号相同。
两台机器的内存条配置不同，N80 的核运行在 1.9 GHz、N90 当时是 1.8 GHz，绝对延迟不能直接比较。
64 MB 随机访问在 N80 上约 155 ns；N90 上有两个水平，干净环境约 185 ns，"快"状态约 150 ns，N80 的值与后者相当
（见 `docs/memlat/memlat-rootcause.zh-CN.md` 第 5 节）。
本目录的数据只用于两件事：每次访问发生多少次页表遍历这类与内存条无关的计数，以及在同一台机器内部做的对照。

**只测了一种模式**：这台机器当天只以 protected 方式启动，没有 nvhe、vhe、kvm-off 的对照。
"protected 比其他模式多多少时间"仍然取自 N90 的四模式数据（`results/n90-day3-host/`）。
"没有二级翻译时是什么样"的参照，来自一台同型号核的工作站上不用 root 做的几项测量（`results/memlat-d80f3-20260930/`）；
那是另一台机器，只有数据不出一二级缓存的量才拿来和这里的数作数值比较。

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
| `expR.log` | 傍晚：顺序访问步长 256，4–64 MB，每个点一个新进程 20 轮；指针链只建一次与每个计时区间前重写各一遍 | `run6-current-state.sh` |
| `expBG.log` | 傍晚：别的核上有内存流量时，cpu0 上几个关键点的延迟 | 同上 |
| `expH-rand.log` `expH-seq256.log` `expH-seqall.log` | 傍晚：lmbench 原版 `lat_mem_rd` 重复多遍（随机 5 遍、步长 256 顺序 16 遍、七种步长 2 遍；缓冲区 4 KiB 页），另有系统 THP 设置下的对照。每行前面是该行输出的时刻 | `run9-lmbench-current-state.sh` |
| `expH-noc-samples.log` | 上一项运行期间每 100 ms 一次的互连频率（全部是 1800000） | 同上 |
| `expS.log` | 傍晚：按 1 GiB 物理区间分别取页做随机访问 | `run10-slots.sh` |
| `expV.log` `vm-frames-n80.txt` | 傍晚：同一个 GiB 里，与保护虚拟机共用 2 MiB 区间的页和不共用的页分别做随机访问；后一个文件是虚拟机内存的物理分布 | `run11-vm-shared.sh` |
| `expV2.log` `vm-frames-n80-run12.txt` `guest-regions.txt` | 傍晚：上一项在 2–64 MB 各做一遍；后两个文件是当时虚拟机内存的物理分布和由它得到的 2 MiB 区间清单（`expV2`、`expW` 用的就是这份；`expV` 用的是五分钟前生成的一份，区间数相同，已被覆盖） | `run12-vm-shared-sizes.sh` |
| `expV3.log` `vm-frames-v3.txt` `guest-regions-v3.txt` | 晚上：上一项换三个种子各重复一遍（6–64 MB），另加取物理连续页的三个大小 | `run16-vm-shared-repeat.sh` |
| `expW.log` | 傍晚：顺序访问，同类页按物理顺序和随机顺序映射，两类页各一遍 | `run13-vm-shared-seq.sh` |
| `expX1.log` `expX2.log` `expX3.log` `vm-frames-x.txt` `guest-regions-x.txt` | 晚上：被计时的循环两种写法的对比（`probe3`，24 KiB–64 MB）；用 lmbench 的写法重复 `expW`；同一时段 lmbench 原版 3 遍；当时虚拟机内存的物理分布 | `run14-loop-form.sh` |
| `expY.log` | 晚上：8 MB、lmbench 的写法，步长 64–1024，同一批相邻的页按物理顺序和随机顺序各测一遍 | `run15-layout-strides.sh` |
| `expZ.log` `vm-frames-z.txt` `guest-regions-z.txt` | 晚上：只量地址翻译的访问方式（每一跳换一页，每页只用 1–4 条缓存行），按 GiB 区间和页的类别分别测 | `run17-translation-only.sh` |
| `expN-n80.log` | 夜里：同一种访问方式用 `probe3` 做，不用 root（工作站上的对应日志在 `results/memlat-d80f3-20260930/`） | `run18-translation-noroot.sh` |
| `expN2.log` | 夜里：上一项以 root 运行，12 次重复，每次让另一个进程占住 0–2112 MB 内存；每行带页在各 GiB 区间的分布（`slots=`） | `run19-slot-mix.sh` |
| `expN3.log` `vm-frames-n3.txt` `guest-regions-n3.txt` | 夜里：`frames2` 按固定比例从两个 GiB 区间取页 | `run20-slot-mix-controlled.sh` |
| `expN4-n80.log` | 夜里：`probe3` 按链表顺序触页和先按地址顺序触页的对比（带 `l2over=`） | `run21-prefault.sh 0 expN4-n80.log hold` |
| `expN5.log` `vm-frames-n5.txt` `guest-regions-n5.txt` `vm-frames-n5-end.txt` `guest-regions-n5-end.txt` | 夜里：`probe3` 的缓冲区里落在虚拟机所在 2 MiB 区间的页的份额（`shared_frac=`）；虚拟机的区间清单在开始和结束时各取一次，两份相同 | `run22-page-classes.sh` |
| `expL2-n80.log` | 夜里：`thplayout`，取自 2 MiB 大页的 4 KiB 页按物理顺序、逆序、随机顺序排列后的顺序访问 | `run24-thp-layout-noroot.sh 0 expL2-n80.log`（以 root 运行） |
| `expH2.log` | 夜里：lmbench 原版 `lat_mem_rd`（步长 256），每次运行之前让另一个进程占住 0–2560 MB；前后各一次 `probe3` | `run25-lmbench-layout.sh` |
| `expH3.log` `expH3-frames.log` | 夜里：同上，另用 `lmb-frames.py` 读出 lmbench 每个子进程自己的缓冲区的物理布局（后一个文件，每个子进程一行） | `run26-lmbench-own-frames.sh` |
| `expH4.log` `expH4-shim.log` | 夜里：未改动的 `lat_mem_rd`（步长 256）加载 `layoutshim.so`，缓冲区按物理顺序、每 8 MB 内打乱、整体打乱三种布局，以及不加载的原样运行；后一个文件是动态库记下的每个缓冲区的实际连续度 | `run27-lmbench-layout-shim.sh` |
| `expH5.log` `expH5-shim.log` | 夜里：同上，步长 16、32、64、128、512、1024，物理顺序和每 8 MB 内打乱各两遍 | `run28-lmbench-layout-strides.sh` |
| `pagealloc-n80.txt` | 页分配器的状态：各阶、各迁移类型的空闲块数，每 CPU 空闲页链表的上限（只读查看，23:00 前后） | |
| `thp-contpte-n80.txt` | 内核配置里与大页、连续页表项有关的选项，透明大页各个开关的取值，启动参数（只读查看） | |
| `binaries-n80.txt` | 设备上各程序源文件和二进制的校验和、编译器版本（22:10 记录；`.pre-*` 是某个实验之前在用的版本） | |
| `iomem-n80.txt` | root 视角的物理内存布局（内核、保留区、监视器内存池的位置） | |
| `vm-process-n80.txt` | 后台那个虚拟机的进程和完整命令行（带 `--protected-vm`），以及 `shmem_enabled` 的取值 | |
| `expL-smoke.log` `expF-smoke.log` | 上面两个实验在写成脚本之前的第一次手工试跑；`expL-smoke.log` 里物理连续度达到 0.99 | 命令记在文件开头 |
| `meta.log` | 各批次的起止时间和系统负载 | |
| `hw-survey-n80.txt` | 硬件、内核配置、PMU 事件、KVM 启动日志 | |
| `devfreq-survey-n80.txt` | 互连和 GPU 调频设备的状态、可选策略，以及桌面电源管理服务的策略表（只读查看） | |
| `derived/device-tables.md` | 下午各实验（A、B、C、D、L、T、F）的汇总表 | `experiments/memlat-probe/analyze-device-logs.py` |
| `derived/state-tables.md` | 傍晚到夜里各实验（R、BG、H、S、V、V2、V3、W、X、Y、Z、N–N5、T2、L2、H2–H5）的汇总表，包括工作站上的对应测量 | `experiments/memlat-probe/analyze-state-experiments.py` |
| `derived/host-n90-tables.md` | N90 宿主机四模式数据的对应分析 | `experiments/memlat-probe/analyze-host-memlat.py` |
| `derived/guest-n90-tables.md` | N90 上 x-kernel **客户机内**数据的对应分析（图 8 的数据，不是宿主机数据） | `experiments/memlat-probe/analyze-guest-memlat.py` |

## 日志字段

每行是一次独立进程的运行结果。

- `ns_min` `ns_med` `ns_max`：重复计时中每跳耗时的最小值、中位数、最大值。`probe`、`probe2`、`probe3`、`layout`、`thplayout` 是 11 次重复，
  `frames2`（实验 S、V、V2、V3、W、X2、Y、Z、N3）是 5 次；`frames2` 的表用中位数，其余用最小值。
  `frames2` 的一个进程会打印多行（每个 GiB 区间、每类页、每一遍各一行）；其余程序一个进程一行。
  `frames2` 在这一天里改过几次（加分类、加顺序访问、加 lmbench 的循环写法、加只量地址翻译的方式、加两个区间按比例混合），
  各日志是当时的版本产生的；字段只增不改。
- `evXX`：PMU 事件 `0xXX` 在每一跳上的平均次数。事件代码见 `experiments/memlat-probe/README.zh-CN.md`。
- `contig_frac`：虚拟地址相邻的两页中，物理页号也相邻（后一页比前一页大 1）的比例。
- `rcontig_frac`：同上，但后一页比前一页小 1。
- `color_max` `over16_pages` `thrash_pages_frac`：L3 页颜色统计。颜色是物理页号对 128 取模，每种颜色在 L3 里正好容纳 16 页。
  `thrash_pages_frac` 是落在"超过 16 页的颜色"里的页所占比例。
- `gb_regions` `mb2_regions`：缓冲区的物理页分布在多少个不同的 1 GiB、2 MiB 物理区间里。
- `pfn=na`：没有以 root 运行，读不到物理页号。
- `rebuild`（`probe3`）：1 表示每个计时区间之前把指针链重写一遍，lmbench 就是这样做的。`reps` 是 11 个计时区间按先后的每跳耗时，
  `noc0`、`noc` 是第一个区间之前和每个区间之后读到的互连频率。
- `slot`、`phys`（`frames2`）：页所在的 1 GiB 物理区间的编号和起始物理地址。`class=shared` 表示页所在的 2 MiB 区间里也有保护虚拟机的页，
  `class=clear` 表示没有，`class=all` 表示没有分类。`pass=2` 是把同一批页搬到新的虚拟地址之后再测的一遍。
  `mode`、`order`：随机访问（`rand`）、顺序访问（`seq`）还是只量地址翻译的方式（`tlb`，这时 `stride` 是每页用的缓存行数）；页按物理升序还是随机顺序映射。
  `chase`（`probe3`、`frames2`，实验 X 起）：`loop` 是循环里一条取数指令，`unrolled` 是 lmbench 的连续 100 条取数指令。
  没有这个字段的日志都是 `loop`；这种写法测到的顺序访问比 lmbench 原版低 4%–9%。
  `expS.log`、`expV.log`、`expV2.log` 里的 `contig_frac` 只算物理升序相邻；`expW.log` 里两个方向都算，并多一个 `va_region_changes`
  （按虚拟地址顺序走一遍，相邻两页不在同一个 2 MiB 物理区间的次数）。
- `probe3` 的 `tlb` 方式（实验 N 起）：`stride` 是每页用的缓存行数，`pages` 是页数；`l1_ns` 是同一进程里一级缓存内的指针追逐每跳的时间（4 个周期），
  `cyc_est` 是用它换算出来的每跳周期数；`prefault=1` 表示先按地址顺序把页触了一遍；`slots=` 是页在各 1 GiB 物理区间的分布（区间编号:页数）；
  `l2over=` 是按物理页号算出来的、落在"同组超过 8 条"的二级缓存组里的数据行所占比例；`shared_frac=` 是落在虚拟机所在 2 MiB 区间里的页的份额。
- `mix=A:B`、`pct_a`、`n_a`、`n_b`（`frames2`，实验 N3）：一组页按比例取自区间 A 和区间 B（区间编号是物理页号右移 18 位）。
- `layout=`、`thp_kb=`（`thplayout`）：排列方式，以及拆开之前缓冲区里由 2 MiB 大页构成的部分（kB；等于缓冲区大小才有效）。
- `expH2.log`、`expH3.log`、`expH4.log`、`expH5.log`：`##` 开头的是每次运行的说明行，`P pre`、`P post` 是运行前后的 `probe3`，
  其余是 lmbench 自己的输出，每行前面加了输出时刻（`"stride=N` 一行之后是"大小 MB、延迟 ns"）。
  `expH3-frames.log` 每行是 lmbench 的一个子进程：`pages` 是它的缓冲区里已分配的页数（比测量大小多一页），`runs` 是物理上连续的段数，`longest_run` 是最长的一段。
  `expH4-shim.log`、`expH5-shim.log` 每行是动态库造的一个缓冲区：`adj2048=a/d` 是前 2048 页的升序、降序连续度。
