# D3000 pKVM 宿主机真实负载实验：设计、执行与数据记录

| 项目 | 内容 |
|---|---|
| 实验目标 | 比较同一台 D3000 在 `kvm-arm.mode=nvhe` 与 `kvm-arm.mode=protected` 下运行宿主机真实应用时的性能差异 |
| 测试对象 | mmap/内存访问 anchors、Redis、RabbitMQ、Geekbench 6 CPU |
| 主平台 | Phytium D3000，Kylin V10 SP1，内核 `6.6.30+` |
| 已封存 campaign | `d3000-apps-20260713-111300`；Pair 1 可作审计材料，Q3/Q5 缺陷发现后已停止，不进入正式汇总 |
| 正式 campaign 顺序 | 先全项目 `THP=never`，再全项目 `THP=always`；每套独立校准并完成 5 个 nVHE/protected boot pair |
| THP=never 完整结果 | [`d3000-thp-never-full-results.zh-CN.md`](d3000-thp-never-full-results.zh-CN.md)，包括五个 boot pair 的应用结果、机制 anchors、数据质量审计、时间漂移和统计推断边界 |
| Pair 1 初步结果 | [`d3000-pair1-preliminary-results.zh-CN.md`](d3000-pair1-preliminary-results.zh-CN.md)，包括 Redis、RabbitMQ、anchors、数据质量问题与统计边界 |
| Q3/Q5 修复核验 | [`d3000-rabbitmq-q3-q5-fix-verification.zh-CN.md`](d3000-rabbitmq-q3-q5-fix-verification.zh-CN.md)，包括实际命令、负向测试、队列闭环、runtime hash 与两套 profile preflight |
| 开始日期 | 2026-07-13 |
| 文档状态 | 实验仍在执行；本文记录已经实现并实际运行的口径，不把中途数据当作最终结论 |
| 可执行定义 | [`experiments/d3000-pkvm-apps/`](../../experiments/d3000-pkvm-apps/) |
| 机制背景 | [`pkvm-mmap-overview.zh-CN.md`](pkvm-mmap-overview.zh-CN.md) |

本文回答四类问题：为什么从 mmap 微基准扩展到真实负载；为什么选择这些应用和场景；机器上究竟如何执行、如何跨启动配对；原始数据、有效性标记和最终统计如何形成。文中“已完成”“正在执行”“计划在主 campaign 后执行”三种状态严格分开。

---

## 1. 为什么要做这一轮真实负载实验

### 1.1 前一阶段已经知道什么

此前的 Phytium/Kylin 调查已经把 `lat_mmap` 的 pKVM 退化定位到一个很窄的机制边界：宿主机写触摸后的映射拆除会触发 stage-1 TLB 失效；在 protected 模式启用 host stage-2 后，TLB 中存在 stage-1 × stage-2 合成条目，逐 4 KiB slot 的本地失效成本变高。该问题主要出现在小范围逐页 TLB 刷新路径，稳态内存访问不等价地“普遍变慢”。Pixel 9 Pro XL 又说明该现象具有平台边界：支持范围 TLBI、真实拆除路径能够批量化的平台未必出现同样幅度的应用影响。完整证据链见 [`pkvm-mmap-overview.zh-CN.md`](pkvm-mmap-overview.zh-CN.md)。

机制闭环仍不能直接回答产品问题：

1. 一台真实启用 pKVM 的宿主机，运行常见服务时究竟损失多少吞吐、延迟或综合分数？
2. 微基准中明显的映射拆除成本会不会被真实应用中更大的计算、调度、网络和 I/O 成本淹没？
3. 内存常驻服务、消息队列和综合 CPU 工作负载是否表现一致？
4. THP 策略会不会改变 protected 与 nVHE 的差值？

因此本轮不再继续只增加一个更细的 TLBI 探针，而是增加一层应用级验证。

### 1.2 这一轮真正比较的自变量

主比较只改变启动参数：

```text
nVHE:      kvm-arm.mode=nvhe
protected: kvm-arm.mode=protected
```

两种模式使用同一台机器、同一个 `6.6.30+` 内核、同一组用户态二进制和同一份输入数据。选择 nVHE 而不是 VHE 作为正式基线，是因为 nVHE 与 protected 都让宿主机运行在 EL1，但只有 protected 为宿主机启用 host stage-2；这样比“VHE 对 protected”更接近单变量对照。前一阶段也已证明 VHE、nVHE 和 KVM-off 在目标 mmap 路径上可作为等价的非 pKVM 基线。

默认 VHE 只用于以下用途：

- 安装工具、生成 Redis seed 和做短 smoke；
- 检查默认启动项仍然可用；
- 两套 campaign 全部结束后的恢复状态。

### 1.3 本轮不回答什么

本轮没有启动 guest，也没有给 pVM 施加负载。它测的是“仅仅把宿主机置于 protected/pKVM 模式后，宿主机应用本身的代价”，不是 guest 性能、VM exit 开销、内存捐赠/共享开销，也不是多 VM 密度。

D3000 当前内核未启用 `CONFIG_XCORE_STATS`，所以本轮不会重复 N80 上的 EL2 gate/op=3 计数，也不能从应用结果直接推出某一次差异必然来自 TLBI。mmap anchors 负责提供机制侧旁证；若业务差异达到预设阈值，再用独立的 `perf stat` 或 trace 复跑归因。

---

## 2. 为什么选择这些测试项目

单一基准只能覆盖一种资源形态。本轮组合有意覆盖四个互补层次：

| 层次 | 项目 | 主要覆盖 | 选择原因 |
|---|---|---|---|
| 机制锚点 | `lat_mmap_precise`、`op_sweep`、`lat_mem_rd` | 映射生命周期、2 MiB 阈值、稳态访存 | 与既有 pKVM 根因直接对接，并监测每个 boot 的漂移 |
| 内存型在线服务 | Redis + memtier | 大驻留集、随机键访问、allocator、TTL/淘汰、fork/BGSAVE | 对内存延迟和 fork 后写时复制敏感，既有吞吐也有尾延迟指标 |
| 消息队列 | RabbitMQ + PerfTest | Erlang VM、消息复制/排队、confirm、持久化、积压与追赶 | 比缓存多出调度、协议、队列状态和持久化路径，接近端到端服务负载 |
| 综合应用型 CPU | Geekbench 6 CPU | 单核/多核、压缩、浏览器、编译、文本、图像、ML、渲染 | 检查差异是否扩展为广义宿主机性能变化，而不只存在于服务端微场景 |

### 2.1 Redis 为什么用 memtier，而不是只用 `redis-benchmark`

[`memtier_benchmark`](https://github.com/redis/memtier_benchmark) 是 Redis 官方组织维护的 Redis/Memcached 流量发生器，能同时控制线程、连接、SET/GET 比例、pipeline、数据大小、TTL、键分布和 offered rate，并输出 JSON 与 HDR Histogram。上游也明确说明延迟不是正态分布，应保留 percentile 和完整直方图，而不是只看平均值。

这些能力正好支持本轮的四类问题：稳态缓存、pipeline 极限、TTL/淘汰和 BGSAVE 干扰。`redis-benchmark` 仍被构建保存，但不作为正式负载发生器。

### 2.2 RabbitMQ 为什么用官方 PerfTest

RabbitMQ 官方把 [PerfTest](https://www.rabbitmq.com/client-libraries/java-tools) 定义为基于 Java client、可配置基础和高级工作负载的吞吐测试工具。其 [完整文档](https://perftest.rabbitmq.com/) 原生支持 durable queue、persistent message、publisher confirm、prefetch/QoS、multi-ack、发布限速、固定消息数、无消费者预填队列、预声明队列排空和多队列 pattern。

官方同时提醒：单队列简单 workload 不能代表全部真实应用，且可能限制节点 CPU 利用率。因此本轮没有只跑一个“1 producer / 1 consumer”数字，而是把它作为 Q1 基线，另加入 8 queue/8 producer/8 consumer 的可靠消息场景、三个受控 offered-rate 点、消费者延迟加入和 100 万消息积压/排空。

### 2.3 Geekbench 为什么保留，UnixBench 为什么暂未加入

Geekbench 6 的 CPU suite 用真实应用形态的数据集覆盖文件压缩、导航、HTML5、PDF、照片库、Clang、文本处理、资产压缩、对象检测、背景模糊、图像编辑、HDR、光线追踪和 Structure from Motion。各 workload 的算法与数据集见 [Geekbench 6 Benchmark Internals](https://www.geekbench.com/doc/geekbench6-benchmark-internals.pdf)。它提供单核、全核以及子项分数，适合回答“protected 是否造成广义 CPU/内存性能变化”。

UnixBench 是有价值的传统 Unix 系统综合基准，但它与已有 lmbench anchors、Geekbench 的整数/系统调用/计算覆盖有较多重叠，对本轮关注的大驻留集、消息状态和尾延迟没有额外直接观测量。考虑到每个项目要跨 10 个正式 boot、每个点重复 5 次，本轮先保留 Geekbench，没有把 UnixBench 混入当前 campaign。以后若要扩展系统调用、进程创建或 shell workload，应作为独立 campaign 加入，而不是中途改变当前矩阵。

### 2.4 为什么不只复用 LMDB

既有 Kaitian 实验已经跑过 LMDB；它说明长期复用映射的稳态数据库操作对这类 teardown 税不一定敏感。本轮选择 Redis 和 RabbitMQ，是为了覆盖不同于长期文件 mmap 的匿名堆、fork、淘汰、消息积压和 Erlang 调度路径。LMDB 结果仍是背景证据，不在 D3000 campaign 中重复。

---

## 3. D3000 实机与软件环境

### 3.1 硬件与拓扑

以下信息由 D3000 上的 `lscpu`、sysfs topology 和 `numactl --hardware` 实测：

| 项目 | 实测值 |
|---|---|
| CPU | Phytium D3000，aarch64 |
| 核数 | 8 核，1 thread/core，全部 online |
| 频率范围 | 625–2500 MHz，boost disabled |
| NUMA | 单节点，约 31.2 GiB RAM |
| CPU 0–3 | sysfs `cluster_id=88`，作为服务端 cluster |
| CPU 4–7 | sysfs `cluster_id=604`，作为客户端 cluster |
| cache | L2 4 MiB、L3 8 MiB、L4 8 MiB（`lscpu` 汇总值） |

服务端和客户端放在不同 cluster，可以减少同一 L2 上的直接争用；但两者仍共享 LLC、内存控制器和同一台宿主机，不能等价于独立负载机。

### 3.2 操作系统与内核

| 项目 | 实测值 |
|---|---|
| OS | 银河麒麟桌面操作系统 V10 SP1，release 2503 |
| 内核 | `Linux 6.6.30+ #2 SMP Thu May 21 16:48:24 CST 2026` |
| 内核架构 | aarch64 |
| KVM | `CONFIG_KVM=y` |
| THP | `CONFIG_TRANSPARENT_HUGEPAGE=y` |
| xcore 统计 | 当前 config 中没有 `CONFIG_XCORE_STATS=y` |
| lmbench/anchor 源码版本 | `52d1942 docs/mmap: confirm Tensor G4 FEAT_TLBIRANGE, add madvise primer` |

`SOURCE_REVISION=52d1942` 固定的是构建 anchors 所用的仓库内容，不应误解为覆盖整个运行期 harness 的 commit：D3000 应用脚本是在本轮实验中部署和修订的。脚本可追溯性依靠远端活动副本、`WORKLOG.md`、Q3/Q5 verification marker 和第 6.3/19.2 节的 runtime bundle SHA256。两套正式 profile 必须使用同一个 hash-locked bundle；不能只看 `SOURCE_REVISION` 判断运行时脚本相同。

### 3.3 固定工具与供应链记录

| 工具 | 固定版本/标识 | 安装方式 |
|---|---|---|
| Redis | 8.8.0，jemalloc 5.3.0 | 固定 tag 源码构建 |
| memtier_benchmark | 2.3.1 | 固定 tag 源码构建 |
| RabbitMQ | 4.3.1 management ARM64 image | 官方 image，运行时使用 RepoDigest |
| RabbitMQ image digest | `rabbitmq@sha256:8734b9e9cd03d12b2e1d973415fc4c5c941c5eca351b4bd63f721782b1bf7c8b` | `docker pull` 后保存 inspect/digest |
| RabbitMQ PerfTest | 2.25.0，AMQP Client 5.33.0 | 固定 release uber JAR |
| Java | OpenJDK 17.0.6 | Kylin package |
| Geekbench | 6.7.1 Preview Build 603632 | 用户提供 ARM Preview archive，SHA256 固定 |
| lmbench anchors | 仓库 revision `52d1942` | 固定源码归档构建 |
| perf | `perf version 6.6.30.gda966ce9a047` | `/home/jose/common/tools/perf` 匹配运行内核构建 |
| 编译器 | GCC/G++ 9.3.0（Kylin build） | 系统实际可用工具链 |

下载归档的 SHA256：

| 文件 | SHA256 |
|---|---|
| Redis 8.8.0 source | `19736ce6117d90b3df032504c6e5c1ce41667ae47f073281b40d2f274c200a74` |
| memtier 2.3.1 source | `0b63a9289399dbf7e04ee2213d0229c831274bb8f64ef8ff2e8f36896aa34146` |
| PerfTest 2.25.0 JAR | `ceba54374fcbb9da113b85b3946273031ac29f24cf2a0bb90b34b613fa9867cf` |
| Geekbench ARM archive | `6e59acb83e6dea3671e2e295365fc37c40fdd280cdbddd50acf248910e14a0e3` |

完整版本输出、下载哈希、Docker inspect 和 image digest 当时保存在 D3000 的 `/home/jose/kylin-lmbench-exp/metadata/`，现已逐文件校验并归档到仓库的 [`experiments/d3000-pkvm-apps/metadata/`](../../experiments/d3000-pkvm-apps/metadata/)。

### 3.4 安装与 smoke 过程中实际解决的问题

`bootstrap.sh` 的多次启动和退出都保留在 `bootstrap.log`/`WORKLOG.md`，没有覆盖失败历史。最终环境的关键处理包括：

- 使用 Kylin 实际可用的 GCC 9.3 构建 Redis 与 memtier，所有模式复用同一二进制；
- lmbench 主构建未直接产出目标精测程序时，固定源码后单独编译 `lat_mmap_precise`；
- 运行内核对应的 perf 初次构建缺少 jevents/libtraceevent 等依赖，最终显式使用 `NO_JEVENTS=1`、`NO_LIBTRACEEVENT=1` 等开关构建所需的基础 `perf stat` 能力；
- RabbitMQ 容器的数据目录和 `.erlang.cookie` 预先以容器 uid 999、0400 权限创建；
- RabbitMQ 4.3.1 启动判据使用 `rabbitmq-diagnostics check_running`，并同时等待 AMQP 端口；
- VHE 下分别完成 Redis、RabbitMQ、Geekbench sysinfo 和 anchors 的短 smoke；
- nVHE/protected 均完成实际启动和模式硬判定后，才开始容量校准。

### 3.5 磁盘布局与空间保护

```text
/home/jose/kylin-lmbench-exp/
  scripts/ metadata/ notes/ logs/ state/ results/ tools/ utils/

/kylin-lmbench-exp-work/
  redis/ rabbitmq/ traces/ tmp/
```

工具、日志和最终结果放在 `/home`；Redis seed、每轮服务数据和其他大临时文件放在根分区下的 `WORK_ROOT`。每个 repetition 前检查根分区至少剩余 100 GiB、`/home` 至少剩余 10 GiB。当前设计不依赖 `/home` 容纳大数据集。

以上是 D3000 执行时的现场布局。实验结束后的本机证据归档位于 [`experiments/d3000-pkvm-apps/`](../../experiments/d3000-pkvm-apps/)，目录边界、SHA-256 清单和第三方运行时缓存的处理见 [`ARCHIVE.zh-CN.md`](../../experiments/d3000-pkvm-apps/ARCHIVE.zh-CN.md)。

---

## 4. 启动模式、GRUB 安全和模式硬判据

### 4.1 D3000 的初始状态

D3000 已刷入正确的 `6.6.30+` 内核，但最初仍按默认 VHE 启动，没有 nVHE/protected 的启动项。实验没有修改 `GRUB_DEFAULT=0`，默认 VHE 始终保留为恢复路径，只追加两个审计过的 one-shot 条目。

### 4.2 为什么必须处理两份 GRUB 配置

这台 D3000 真正由 ESP 上的 `/boot/efi/boot/grub/grub.cfg` 启动；`update-grub` 默认更新的 `/boot/grub/grub.cfg` 不是唯一生效副本。安装脚本执行以下保护：

1. 备份两份 `grub.cfg` 和两份 `grubenv`；
2. 安装 nVHE/protected 自定义条目后运行 `update-grub`；
3. 把生成配置复制到活动 ESP；
4. 分别运行 `grub-script-check`；
5. 用 `cmp` 要求两份配置字节一致；
6. 确认默认项仍为 index 0；
7. one-shot 重启只通过 `grub-reboot --boot-directory=/boot/efi/boot` 写活动 ESP 的 `grubenv`，并读回 `next_entry` 验证。

因此实验失败时不会把 protected 永久设成默认项，清除 one-shot 后即可回 VHE。

### 4.3 模式不是只看 cmdline

每个 boot 先校验 cmdline，再检查内核特定标志：

| 期望模式 | 必须满足 | 必须不存在 |
|---|---|---|
| VHE | `VHE mode initialized successfully` | — |
| nVHE | cmdline=`nvhe`；`Hyp mode initialized successfully` | `CPU features: detected: Protected KVM` |
| protected | cmdline=`protected`；`CPU features: detected: Protected KVM`；`Kylin X Core initialized successfully` | `Protected KVM not available with VHE` |

只要模式判定失败，当前 systemd leg 立即失败，不运行负载，也不会推进到下一启动项。

---

## 5. 宿主机环境控制及其边界

每个 campaign leg 启动后重新执行：

- CPU 0–7 全部 online；
- 每个 CPU 的 cpufreq governor 设为 `performance`；
- ASLR 保持生产默认值 `2`；
- `swapoff -a`，并验证没有活动 swap；
- 从 graphical target 切到 multi-user target；
- 检查磁盘余量；
- 记录 cmdline、内核、THP、ASLR、swap、`lscpu`、内存、dmesg、每核 governor 和 `scaling_cur_freq`。

这里的“performance”是 governor 策略，不等于把 min/max 频率固定成同一个 MHz。D3000 频率范围仍是 625–2500 MHz，因此最终报告必须检查每个 boot 保存的频率元数据，并通过 boot pairing、项目顺序轮换和首尾 anchors 抵消慢漂移。当前也没有像 Pixel 实验那样设置温度门限。

服务端与客户端的 CPU 分区为：

```text
Redis/RabbitMQ server: CPU 0-3（cluster 88）
memtier/PerfTest:      CPU 4-7（cluster 604）
Geekbench CPU suite:   CPU 0-7
anchors:               CPU 0
```

这不是 CPU isolation：内核线程、中断和残留系统服务仍可能运行在这些 CPU 上。`taskset`、container cpuset、multi-user target、重复测量和 `pidstat` 降低干扰，但不能提供独占实验室主机的强保证。

---

## 6. THP 为什么有两套 campaign

### 6.1 顺序与矩阵

正式实验先跑全项目 `THP=never`，再跑全项目 `THP=always`。在同一套 campaign 内，anchors、Redis、RabbitMQ、Geekbench 使用同一个 sysfs policy；脚本每次切换项目都会写入并立即读回 `/sys/kernel/mm/transparent_hugepage/enabled`，读回值不匹配就停止。

| campaign | anchors | Redis | RabbitMQ | Geekbench |
|---|---|---|---|---|
| 第一套 | `never` | `never` | `never` | `never` |
| 第二套 | `always` | `always` | `always` | `always` |

每套都重新做 nVHE/protected 容量校准、相同的 5 个 boot pair、相同项目顺序和所有场景 ×5。两套使用独立 campaign ID、`capacity.json` 与 rate 文件，不能把第一套某个项目的数据拼入第二套。

Redis 官方低延迟指南建议关闭 THP，特别指出 fork 后的大页 CoW 延迟和内存放大，见 [Diagnosing latency issues](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/)。因此第一套代表 Redis 常见生产配置；第二套则故意启用系统默认策略，用来测量 THP policy 是否改变 protected/nVHE 差值。对于 RabbitMQ、Geekbench 和 anchors，两套完整重复避免了只补几个点导致的时间位置与 boot 状态不可比。

sysfs 的 `always` 只是分配策略，不等价于某段映射已经形成大页。两套结果只能回答“全局 THP policy 是否改变应用级 pKVM 差值”；若需要把差异归因给大页实际形成，还要补 `/proc/<pid>/smaps`、`AnonHugePages` 或 THP fault/collapse 计数。参见 [`pkvm-thp-mitigation.zh-CN.md`](pkvm-thp-mitigation.zh-CN.md)。

### 6.2 自动接续的保护条件

两套 campaign 使用完全相同的 hash-locked runner，不在中途从 staging 替换脚本。`d3000-thp-always-chain.service` 只有在以下条件全部成立时才启动第二套：

1. `thp-always-pending` 指向当前全-never campaign；
2. 第一套成功完成 leg 12；
3. 第一套结果目录已写出 `CAMPAIGN_COMPLETE`；
4. `campaign-enabled` 已清除；
5. 机器已回默认 VHE并通过 cmdline 与 dmesg 硬判据；
6. 当前 runtime bundle SHA256 仍与 Q3/Q5 冒烟 marker 一致。

第一套失败或人工停止时不会启动第二套。第二套完成 leg 12、写出自己的 `CAMPAIGN_COMPLETE` 并回到 VHE 后，接续器才清除 pending marker 并禁用 campaign 与接续服务。接续状态机还包含 selftest：未完成第 12 leg、缺少完整结果标记或旧 `app-default` profile 都必须进入拒绝分支。

### 6.3 重跑前实机验证

2026-07-14 最终冒烟和独立审计后，`campaign.sh preflight never` 与 `campaign.sh preflight always` 都在 D3000 上通过：四个项目的实际 profile 映射全部一致，manifest 为 12 legs/5 formal pairs，handoff selftest 通过，活动 runtime bundle 为 `a1385b35a98df385e49243b7f06916bccc88d345a197d55fba537c48c722dd62`。`preflight app-default` 返回 1，证明旧混合 profile 不能再误启动。完整证据见 [`d3000-rabbitmq-q3-q5-fix-verification.zh-CN.md`](d3000-rabbitmq-q3-q5-fix-verification.zh-CN.md)。

---

## 7. 容量校准：先找共同工作点，再做固定负载对照

### 7.1 为什么不能让两种模式各跑自己的百分比

若 protected 的极限吞吐较低，却仍向两种模式施加同一个绝对高压请求，两者可能分别处于“可服务区”和“过载排队区”；反过来，若各自使用自身容量的 70%，实际 offered load 又不相同。当前做法先在两种模式各跑 5 次无限速容量测试，再取：

```text
C_common = min(median(C_nvhe), median(C_protected))
```

正式固定 rate 场景都从同一个 `C_common` 派生，使两种模式接收相同 offered load，并避免故意压过较慢模式的容量。无限速场景仍直接测饱和吞吐。

### 7.2 旧 campaign 的校准审计数据

下表来自已封存的 `d3000-apps-20260713-111300`。校准只有每种模式一个 boot，作用是定负载，不作为正式性能结论；修复后的两套 campaign 不复用这些 rate，只把它们用于 Q3 修复冒烟。

| 项目 | nVHE 五次 | nVHE 中位数 | protected 五次 | protected 中位数 | `C_common` |
|---|---|---:|---|---:|---:|
| Redis ops/s | 139405.29, 138053.91, 137688.93, 137651.88, 138564.80 | 138053.91 | 137748.82, 136430.48, 136647.92, 136614.03, 136101.27 | 136614.03 | 136614.03 |
| RabbitMQ msg/s | 49769, 49018, 50006, 50450, 48470 | 49769 | 49215, 47512, 48766, 48515, 47920 | 48515 | 48515 |

由此生成的正式 rate：

| 场景 | 计算值 | 实际参数 |
|---|---:|---:|
| Redis 70% | `int(136614.03 × 0.70)` | requested total 95629 ops/s；100 连接向上取整为每连接 957，即 target 95700 |
| Rabbit Q3 50% | `48515 × 50 / 100` | 24257 msg/s |
| Rabbit Q3 70% | `48515 × 70 / 100` | 33960 msg/s |
| Rabbit Q3 85% | `48515 × 85 / 100` | 41237 msg/s |

全 `THP=never` campaign 会先生成自己的 `capacity.json` 和 rate 文件；全 `THP=always` 接续启动时会清除 state 中的 Redis/RabbitMQ rate，再独立校准并写入自己的结果目录。

---

## 8. 跨启动配对、项目顺序和实验规模

### 8.1 每个 campaign 的 12 个 leg

| leg | 阶段 | pair | 模式 | 项目顺序 |
|---:|---|---|---|---|
| 1 | calibration | calibration | nVHE | Redis → RabbitMQ |
| 2 | calibration | calibration | protected | Redis → RabbitMQ |
| 3 | formal | 1 | nVHE | Geekbench → Redis → RabbitMQ |
| 4 | formal | 1 | protected | Geekbench → Redis → RabbitMQ |
| 5 | formal | 2 | protected | Redis → RabbitMQ → Geekbench |
| 6 | formal | 2 | nVHE | Redis → RabbitMQ → Geekbench |
| 7 | formal | 3 | nVHE | RabbitMQ → Geekbench → Redis |
| 8 | formal | 3 | protected | RabbitMQ → Geekbench → Redis |
| 9 | formal | 4 | protected | Geekbench → RabbitMQ → Redis |
| 10 | formal | 4 | nVHE | Geekbench → RabbitMQ → Redis |
| 11 | formal | 5 | nVHE | Redis → Geekbench → RabbitMQ |
| 12 | formal | 5 | protected | Redis → Geekbench → RabbitMQ |

每个 pair 内两种模式使用相同项目顺序；pair 间轮换谁先启动、哪个项目先执行。这样同时降低模式先后、温度随时间变化、页缓存和项目位置带来的系统偏差。

### 8.2 为什么每点做 5 次

每个场景、每个 boot 固定 5 次有效 repetition，不用 3 次代替。5 次允许先在 boot 内取中位数，避免一次调度抖动、后台服务或 fork 尖峰直接决定 pair 结果。2026-07-13 的首个 nVHE boot 已观察到 Redis R1 第 5 次延迟显著低于前四次；该点被如实保留并写入 worklog，正说明重复与中位数的必要性。

### 8.3 预计执行量

每个 campaign 包含：

- calibration：Redis 10 次、RabbitMQ 10 次；
- 10 个正式 boot block；
- Redis：4 场景 × 5 次 × 10 boot = 200 次；
- RabbitMQ：7 场景 × 5 次 × 10 boot = 350 次，其中 Q5 每次又分 fill/drain；
- Geekbench：5 个正式 suite × 10 boot = 50 次，另有 10 次不计分 warmup；
- anchors：每个 boot 首尾各一组，共 20 组。

第二套 `THP=always` campaign 完整重复上述规模，因此两套合计是多天量级实验，而不是一轮几小时的 smoke。

---

## 9. Boot anchors：把应用结果与已知机制连接起来

每个正式 boot 的最前和最后各跑一次 anchors，固定 CPU 0，并使用当前 campaign 的 THP profile。它们不是应用主分数，而是回答两件事：该 boot 是否仍能看到预期的 pKVM mmap 信号；长时间项目执行后宿主机是否出现明显热漂移。

### 9.1 `lat_mmap_precise`

| 映射尺寸 | 每次进程内迭代数 | 每个 anchor group 的重复数 |
|---:|---:|---:|
| 0.5 MiB | 10000 | 5 |
| 1 MiB | 8000 | 5 |
| 2 MiB | 5000 | 5 |
| 4 MiB | 3000 | 5 |
| 8 MiB | 2000 | 5 |
| 16 MiB | 1000 | 5 |
| 64 MiB | 300 | 5 |

后备文件是预先写满并 `fsync` 的 64 MiB 文件。精测程序沿用 lmbench 默认几何：映射完整 size，只写触摸前 1/10，步长 16 KiB，再 `munmap`。因此它覆盖 mmap → 稀疏写触摸 → munmap 完整生命周期。

### 9.2 `op_sweep munmap`

每点映射 64 MiB、进程内 100 iterations、跨进程重复 5 次：

| label | 写触摸跨度 | stride | 用途 |
|---|---:|---:|---|
| dense-1.9 | 1.9 MiB | 4 KiB | 2 MiB 阈值下方逐页路径 |
| dense-2.0 | 2.0 MiB | 4 KiB | 阈值边界/整表路径 |
| sparse-6.4 | 6.4 MiB | 16 KiB | 原始 `lat_mmap` 稀疏几何参考 |

1.9/2.0 MiB 对照来自既有根因：如果 D3000 也有同类逐页 TLBI 税，protected 差异应在阈值两侧呈现不同形态。

### 9.3 `lat_mem_rd`

```bash
lat_mem_rd -P 1 -W 2 -N 5 64 128
```

即 64 MiB 工作集、128 B stride、单进程，anchor group 内运行 5 次。它是稳态内存访问负对照：如果 `lat_mem_rd` 也大幅变慢，就不能再把应用差异简单解释为映射生命周期税。

### 9.4 anchor 数据状态

每组保存完整 stdout 和环境 metadata，并以 `VALID` 标记完成。当前 `analyze-results.py` 尚未自动解析 anchors；最终报告前需要单独汇总首尾漂移和阈值信号。

---

## 10. Redis：大驻留集、淘汰和 fork/BGSAVE

### 10.1 固定数据集

seed 由自建的 pipeline 生成器写入 Redis 后执行 `SAVE` 得到：

| 项目 | 实测值 |
|---|---:|
| keys | 7,000,000 |
| value 大小 | 1024 B（seed 生成阶段） |
| Redis `used_memory` | 9,288,098,680 B |
| RDB SHA256 | `fea9912028f533f5da105ea835098b70246f81d52301de59b6bec63e4b2e184a` |

每个 repetition 创建新的工作目录，从同一 RDB 拷贝开始；上一次测试对键值、TTL 或淘汰的修改不会泄漏到下一次。RDB 载入和 key-count 校验不计入 memtier 计分窗口。

### 10.2 Redis 与 memtier 的共同参数

Redis：

- `taskset -c 0-3`；
- 绑定 `127.0.0.1:6379`；
- AOF 关闭、自动 save 关闭；
- RDB compression 关闭、checksum 开启；
- latency monitor threshold=1 ms；
- THP 由当前 campaign 统一控制：第一套为 `never`，第二套为 `always`；每次启动 Redis 前都会写入并读回确认。

memtier：

```text
CPU 4-7
4 threads × 25 clients = 100 connections
key range 1..7,000,000，prefix k:
key-pattern R:R
--distinct-client-seed
--run-count=1
percentiles 50,95,99,99.9
```

不使用带时间戳的 `--randomize`，使随机序列口径可重复。每次保存完整命令，正式参数以每个 repetition 目录内的 `command.sh` 为最终证据。

### 10.3 四个正式场景

| 场景 | 时长 | 参数 | 为什么测 |
|---|---:|---|---|
| R1 steady cache | 300 s | SET:GET=1:10；1024 B；pipeline=1；uniform random；70% common rate | 典型读多写少、低延迟缓存，比较同 offered load 下尾延迟 |
| R2 pipeline throughput | 180 s | SET:GET=1:1；1024 B；pipeline=16；不限速 | 压低请求往返占比，把 Redis 推到饱和吞吐区 |
| R3 TTL/eviction | 300 s | SET:GET=1:1；64–4096 B 随机；TTL 60–300 s；`maxmemory 10gb`；`allkeys-lru`；70% rate | 覆盖变长对象、过期、淘汰和 allocator churn |
| R4 BGSAVE | 360 s | SET:GET=1:1；1024 B；pipeline=1；70% rate；120/240 s 触发 BGSAVE | 覆盖大驻留集 fork、页表复制、CoW 和持久化干扰 |

R4 的第二次 BGSAVE 只有在第一次完成后才触发；脚本保存 `first_start/first_done`、`second_start/second_done` 时间线。第一套 `THP=never` 与 Redis 官方生产建议一致，第二套 `THP=always` 则有意测量 fork/BGSAVE 对 profile 的敏感性。

### 10.4 每次 repetition 的生命周期

```text
空间检查
  → 新工作目录 + 同一 seed RDB
  → 启动 Redis，等待 PONG，校验 7,000,000 keys
  → 保存 before INFO / latency
  → 启动 Redis pidstat
  → 运行 memtier（R4 同时调度两次 BGSAVE）
  → 停 pidstat
  → 保存 after INFO / latency
  → shutdown nosave
  → 删除临时服务数据
  → 创建 VALID
  → cooldown 30 s
```

### 10.5 Redis 保存的数据

每个有效 repetition 当前保存：

- `command.sh`、`rate.env`；
- `memtier.json`、文本报告、HDR/HGRM latency 文件；
- `before/after/info.txt`；
- `before/after/latency-latest.txt` 与 `latency-histogram.txt`；
- Redis 进程 `pidstat.txt`；
- R4 的 `bgsave-events.txt`；
- `VALID`。

当前脚本在结束时删除临时 Redis data directory，因此 per-run `redis.conf` 和 `server.log` 没有复制到最终 result directory。配置可由固定脚本重建，主指标和 INFO 均在，但这是证据归档的一项缺口；不能在报告中声称已经保存了每次 Redis server log。

---

## 11. RabbitMQ：吞吐、可靠消息、积压与恢复

### 11.1 共同运行环境

- 官方 RabbitMQ 4.3.1 management ARM64 image，以 RepoDigest 运行，`--pull=never`；
- 每个 repetition 删除旧容器和 data dir，重新创建干净 broker；
- broker 使用 host network 和 CPU 0–3 cpuset；
- Erlang VM 参数 `+S 4:4`；
- PerfTest JVM 使用 CPU 4–7；
- AMQP 只走 `127.0.0.1:5672`；
- 每条消息固定 **1000 B**，不是 1024 B；
- 每个 repetition 先运行 60 s 不计分 warmup，再冷却 30 s；
- regular 正式窗口 360 s，分析时再丢弃正式 CSV 的前 60 s，使用后 300 s；
- 每次正式 repetition 结束后再冷却 30 s。

同机 loopback 排除了外部网络变化，适合模式 A/B；代价是 server/client 共享内存带宽、LLC 和宿主机调度，因此结果只能解释为“D3000 单机端到端配置”，不能外推为独立 load generator 下的集群容量。

### 11.2 七个正式场景

| 场景 | 配置 | 主要问题 |
|---|---|---|
| Q1 one-fast | 1 producer、1 consumer、1 auto-delete transient queue、全速、qos=500 | 最轻协议路径和单队列基线 |
| Q2 reliable | 8 producers、8 consumers、8 classic durable queues、persistent、confirm=500、qos=500、multi-ack=100、全速 | 多队列可靠消息的饱和能力 |
| Q3 rate50 | 复用 Q2；总目标为该 profile `C_common` 的 50%，向上取整分配给 8 producers | 共同容量下的低负载延迟 |
| Q3 rate70 | 复用 Q2；总目标为该 profile `C_common` 的 70%，向上取整分配给 8 producers | 中负载工作点 |
| Q3 rate85 | 复用 Q2；总目标为该 profile `C_common` 的 85%，向上取整分配给 8 producers | 接近共同容量但避免过载 |
| Q4 join-late | 1 producer、10 consumers、persistent、confirm=100、qos=300、rate=10000；消费者延迟 120 s 启动 | 先积压、后追赶时的队列和消费者延迟 |
| Q5 backlog | 1 producer 先写满 1,000,000 条 persistent 消息；随后 4 consumers 排空 | 分离记录 backlog fill 和 drain wall time |

Q3 的 `--rate` 是每个 producer 参数。runner 保存 `requested_total`、`per_producer_rate_arg` 和取整后的 `effective_total_target`，正式 360 秒中丢弃前 60 秒，再要求至少 120 个 published-rate 样本的均值落在目标 ±5% 内。未达到目标不创建 repetition `VALID`。

Q4 正式 CSV 丢弃前 60 s，但消费者在 120 s 才加入，因此分析窗口仍包含 60 s 的纯积压增长和之后的追赶阶段，这是场景设计的一部分。

Q5 的 fill/drain 各设置 1800 s 安全上限，但正常由固定消息数提前结束：fill 使用 `--pmessages 1000000`；确认队列恰有 100 万条 ready、0 条 unacknowledged 后，drain 使用 predeclared queue、4 consumers、`--cmessages 1000000` 和 `--exit-when empty`。drain 后还必须确认 ready/unacknowledged 都为 0。因此 Q5 比较的是同一份 100 万消息 backlog 的完整 fill/drain wall time。

### 11.3 每次 repetition 的生命周期

```text
空间检查
  → 删除旧容器和数据
  → 创建 uid=999 数据目录和固定 cookie
  → 以固定 digest 启动 RabbitMQ
  → diagnostics ping + check_running + AMQP port gate
  → 60 s warmup + 30 s cooldown
  → 保存 before status/memory/queues/docker-stats
  → 启动 broker pidstat
  → PerfTest 正式窗口（Q3 追加 observed-rate gate；Q5 为 fill → queue-count gate → drain → empty gate）
  → 保存 after snapshot、container log、container inspect
  → 删除容器和临时 data dir
  → 创建 VALID
  → cooldown 30 s
```

### 11.4 RabbitMQ 保存的数据

- 实际 PerfTest `command.sh`；
- 每秒一行的 `perftest.csv`；
- stdout/stderr；
- `/usr/bin/time -v`；
- broker `pidstat.txt`；
- before/after 的 status、memory breakdown、queue list、docker stats；
- container log 与完整 inspect；
- Q5 `fill/`、`drain/` 的独立命令、CSV、stdout/stderr、time；
- Q3 `rate-target.env` 与 `rate-validation.env`；
- Q5 fill/drain 前后的 queue JSON、`validation.env` 和 `QUEUE_COUNTS_VALID`；
- PerfTest 命令与 CSV 检查通过后的 `PERFTEST_VALID`，以及所有场景闭环完成后的 repetition `VALID`。

---

## 12. Geekbench 6 CPU：广义宿主机对照

### 12.1 执行方式

每个正式 boot：

1. 校验 Geekbench archive SHA256；
2. 设置该 campaign/profile 对应的 THP；
3. 保存 suite metadata；
4. CPU 0–7 跑 1 次不计分 warmup；
5. cooldown 30 s；
6. CPU 0–7 连续跑 5 次正式 `geekbench6 --cpu`，每次保存 `/usr/bin/time -v`；
7. 每次之间 cooldown 30 s；
8. 不跑 GPU。

Geekbench 是 vendor-defined 综合分数，不用于解释 TLBI 机制。它的价值是检查 broad CPU workload 是否也表现出稳定 protected/nVHE 差异，并可从子项判断差异是否集中在编译、压缩、文本、图像或 ML 类任务。

### 12.2 为什么结果要二次归档网页

当前 ARM Preview CLI 不提供 Pro 版的本地 export 能力，stdout 只返回 Geekbench Browser URL。官方 [Geekbench editions](https://www.geekbench.com/editions/) 也把 offline results 列为 Pro 能力。因此每次正式运行保存：

- `stdout.txt`、`stderr.txt`；
- `time.txt`；
- `result-urls.txt`；
- `VALID`。

同步后运行 `geekbench-pages.py`：

1. 从每个 repetition 选出 canonical `browser.geekbench.com/v6/cpu/<id>`；
2. 生成 `geekbench-page-manifest.csv`，给出 pair/mode/rep、URL 和 `<id>.html` 保存名；
3. 用户保存网页后，解析 single-core、multi-core 和 16 类子项；
4. 计算 HTML SHA256并生成每次 `scores.json`；
5. Cloudflare challenge 页面缺少两个 headline score，会报 `parse-error`，不能进入正式分析；
6. 最终分析前使用 `--strict`，要求所有页面齐全。

CLI 退出成功和 URL 原始证据可以让 repetition 暂时标记 `VALID`；但“可进入最终分数统计” 还需要网页严格导入，这是 Geekbench 特有的第二道有效性门。

---

## 13. 自动化、失败语义和跨 boot 状态机

### 13.1 systemd 如何跨重启续跑

`d3000-pkvm-campaign.service` 是 `Type=oneshot`、`TimeoutStartSec=infinity`。启动时用 `flock` 获取 campaign lock。runner 读取：

```text
state/campaign-enabled
state/campaign-id
state/campaign-profile
state/leg
state/manifest.tsv
```

服务完成一个 leg 后才原子更新 `leg`、验证下一 one-shot GRUB entry、`sync` 并重启。正式 boot 只有在 start anchors、全部项目和 end anchors 都成功后才创建 `BOOT_BLOCK_VALID`。每套开始时把 manifest 与 `campaign.env` 复制到自己的结果目录；leg 12 完成后再写 `CAMPAIGN_COMPLETE`。

profile 必须显式为 `never` 或 `always`；缺失、旧 `app-default` 或其他值都会停止。每次正式启动前，`preflight` 校验 manifest 结构、四个项目的有效 THP、handoff selftest、systemd unit 内容与完整 runtime bundle SHA256。两套 campaign 的 ID 分别为 `d3000-apps-never-<timestamp>` 和 `d3000-apps-always-<timestamp>`。

### 13.2 失败时会发生什么

脚本普遍启用 `set -euo pipefail`。模式错误、磁盘 guard、governor、swap、服务退出、工具非零返回或关键快照失败都会使当前 systemd leg 失败。此时：

- `campaign-enabled` 仍在；
- `leg` 不推进；
- 不设置下一 one-shot，也不自动跨过错误；
- 当前已写入的原始目录保留，用于调查。

现有自动脚本没有“同一 repetition 自动重试两次”的实现。失败后的重试必须先调查，再由控制端明确处理；文档和最终报告不能把计划中的重试描述成已经自动执行。

### 13.3 正常结束

leg 12 成功后：

- 清除 `campaign-enabled`；
- 写 `completed-leg=12`；
- 在该 campaign 结果目录写 `CAMPAIGN_COMPLETE`；
- THP 恢复 `always`；
- `swapon -a`；
- 默认 target 恢复 graphical；
- 清两份 grubenv 的 `next_entry`；
- 重启到默认 VHE。

若完成的是第一套全-never，机器回 VHE 后由第 6.2 节的 guarded chain 启动全-always。第二套结束并回 VHE 后，接续器清除 pending marker 并禁用两个服务。

---

## 14. 数据、日志和证据如何组织

### 14.1 结果目录

```text
results/<campaign-id>/
  capacity.json
  pair-calibration/
    nvhe/{redis-calibration,rabbitmq-calibration}/rep-01..05/
    protected/{redis-calibration,rabbitmq-calibration}/rep-01..05/
  pair-1/
    nvhe/
      leg-metadata/
      boot-metadata/
      anchors-start/rep-00/
      geekbench-cpu/rep-00/{warmup,rep-01..05}/
      redis-r1-steady/rep-01..05/
      redis-r2-pipeline/rep-01..05/
      redis-r3-ttl-eviction/rep-01..05/
      redis-r4-bgsave/rep-01..05/
      rabbitmq-q1-one-fast/rep-01..05/
      rabbitmq-q2-reliable/rep-01..05/
      rabbitmq-q3-rate50/rep-01..05/
      rabbitmq-q3-rate70/rep-01..05/
      rabbitmq-q3-rate85/rep-01..05/
      rabbitmq-q4-join-late/rep-01..05/
      rabbitmq-q5-backlog/rep-01..05/
      anchors-end/rep-00/
      BOOT_BLOCK_VALID
    protected/...
  pair-2..5/...
```

### 14.2 四类日志各自回答什么

| 文件 | 作用 |
|---|---|
| `logs/bootstrap.log` | apt、下载、构建、smoke 前准备的完整 stdout/stderr，保留失败尝试 |
| `logs/campaign-service.log` | 跨 boot service 自身的 stdout/stderr、阶段切换和未被单独重定向的错误；各工具的完整输出仍以 repetition 目录为准 |
| `logs/events.log` | `log()` 产生的带时间戳事件，适合快速检查 cooldown、项目切换、重启 |
| `notes/WORKLOG.md` | 人工可读的开始/有效、模式验证、GRUB、决策、偏差和异常记录 |

`state/status` 是当前项目提示，不是完成证据；正式完成以 repetition 的 `VALID`、boot 的 `BOOT_BLOCK_VALID`、`completed-leg=12` 和结果目录的 `CAMPAIGN_COMPLETE` 为准。

### 14.3 本机同步

`sync-results-local.sh` 现在把 D3000 的证据类别增量拉取到仓库归档：

```text
experiments/d3000-pkvm-apps/{configs,logs,metadata,notes,results,staged,state}
experiments/d3000-pkvm-apps/deployed-scripts
```

它只拉取不可重建的实验输出和部署脚本，使用 `rsync -a --partial`，不使用 `--delete`，并追加 `logs/local-sync.log`；第三方源码、构建缓存和工具安装树不在同步范围内。正式运行期间只应在 boot 完成或 VHE 安全窗口同步。归档迁移时保留了完整现场快照，详情见 [`ARCHIVE.zh-CN.md`](../../experiments/d3000-pkvm-apps/ARCHIVE.zh-CN.md)。

---

## 15. 指标提取与最终统计

### 15.1 Redis

从 memtier JSON `ALL STATS/Totals` 提取：

- throughput（ops/s）；
- average latency；
- p50、p95、p99 latency。

HDR/HGRM 原始直方图已经保存。当前 `analyze-results.py` 读取 JSON totals；最终若工具版本与命令类别允许，应另做 HDR 合并验证，不能对 5 个 p99 做算术平均。

### 15.2 RabbitMQ

对 regular 场景读取每秒 PerfTest CSV，正式 360 s 中丢弃前 60 s，对剩余每秒值取中位数：

- published/received msg/s；
- consumer p95/p99；
- confirm p95/p99。

这里的“p99”是每秒 p99 的时间中位数，不是把所有消息合成后的全局 p99；最终报告必须按这个统计口径命名。Q5 不用 regular CSV 主指标，分别读取 fill/drain 的 wall time。

### 15.3 Geekbench

从严格导入的 `scores.json` 提取 single-core、multi-core 和所有子项，分数越高越好。

### 15.4 Boot-paired 统计

统计单位不是 50 个 repetition 混在一起，而是 boot pair：

1. 对每个 `pair × mode × project × scenario × metric` 的 5 次取中位数；
2. 同一个 pair 内计算：

   ```text
   delta_pair = protected / nvhe - 1
   ```

3. 对 5 个 `delta_pair` 报告中位数和 MAD；
4. 固定随机种子 `20260713`，对 5 个 pair delta 做 10,000 次 paired bootstrap，报告 median 的 95% CI；
5. 标记 5 个 pair 中是否至少 4 个同方向。

等价区间：

| 指标 | 区间 |
|---|---:|
| throughput、wall time、average latency、p50、p95、Geekbench | ±3% |
| p99 | ±5% |

只有 5 个 pair 齐全且 bootstrap CI 完全落在等价区间内，才标记“等价”。CI 跨零不等于等价；CI 未落入等价区间也不自动等于存在有意义退化。

这里的“等价”是预先定义的工程筛查标签，不是确认性总体等价证明。n=5 时 percentile bootstrap 对总体 median 的覆盖保证很弱；精确双侧 sign test 即使 5/5 同方向，最小 p 值也只有 0.0625。最终报告必须同时给出五个 pair 原值、观察范围、方向计数和时间漂移，并把 bootstrap 区间明确标为描述性区间。

### 15.5 诊断复跑的触发条件

两套计分 campaign 都不附加重 tracing。完成主统计后，如果满足任一条件，再选择核心场景分别做 nVHE/protected 各 5 次 `perf stat`，必要时再做 60 s trace：

- throughput 或时间差至少 3%；
- p99 差至少 5%；
- 5 个 pair 中至少 4 个同方向。

匹配内核的 perf 已构建，但该诊断阶段尚未集成到自动 campaign，也尚未执行。诊断数据必须与无 tracing 的主分数分目录、分结论。

---

## 16. 有效性判据、已知局限和不能保证的事项

### 16.1 已实现的硬门

- 同一内核、模式 cmdline 和 dmesg 标志一致；
- CPU 0–7 online，governor 全为 performance；
- swap 必须为空；
- 根分区和 `/home` 余量满足 guard；
- 固定工具哈希/版本和 RabbitMQ image digest；
- 启动前 runtime bundle、systemd unit、manifest、profile 映射与 Q3/Q5 verification marker 必须通过 preflight；
- 服务必须 ready，客户端必须零退出；PerfTest 还必须无 `Parsing failed`、生成非空且 header 正确的 CSV；
- Redis seed key count 必须匹配；
- RabbitMQ Q3 实测 published rate 必须在目标 ±5% 内且样本数达标；
- RabbitMQ Q5 fill/drain 的固定消息数、ready 与 unacknowledged 队列计数必须闭环；
- 关键 before/after 快照成功；
- 完成后才创建 repetition `VALID`；
- 整个 boot 成功后才创建 `BOOT_BLOCK_VALID` 和推进 leg；整个 campaign 的 leg 12 成功后才创建 `CAMPAIGN_COMPLETE`。

### 16.2 已知局限

1. **同机负载发生器**：客户端和服务共享 LLC、内存、内核和 loopback，不能代表独立压测机。
2. **频率非硬锁**：performance governor 不是固定 MHz；没有温度 gate，依靠 metadata、顺序轮换、首尾 anchors 和 boot pairing 控制。
3. **后台噪声未完全消除**：没有 CPU isolation/IRQ 隔离；multi-user target 也不能保证零后台服务。单次离群点必须保留并通过中位数处理。
4. **Redis 没有单独 request warmup**：RDB 载入与 ready gate 在计分外，但 memtier 正式窗口从第一批请求开始；这是统一的 fresh-server 口径。
5. **RabbitMQ 是容器端到端结果**：包含 Docker、Erlang VM、Java client 和 loopback 的固定开销，不能解释为 broker 内核路径的纯成本。
6. **THP policy 不等于大页证据**：当前没有逐 repetition 保存 `smaps`/THP collapse 计数。
7. **Geekbench 依赖在线结果页**：URL 已保存，但最终分数仍需用户保存 HTML并通过 strict importer。
8. **anchors 尚未进入统一分析器**：原始数据齐全，最终报告前需补专门汇总。
9. **Redis server log 未最终归档**：临时 data dir 被删除，主指标、INFO、client 输出和 pidstat 在，但 per-run server log 不在 result tree。
10. **HDR 合并未实现**：直方图已收集，当前自动分析仍以 JSON totals 和 boot median 为主。
11. **没有 guest**：结果只描述 pKVM 启用对 host workload 的影响，不描述实际 pVM 并发。
12. **旧 Pair 1 的 boot pair 数不足**：它只有一个独立 boot pair，不能计算有效的跨 boot 置信区间或等价性结论；旧 campaign 已封存，不与新数据合并。
13. **旧 Pair 1 的 RabbitMQ Q3 不是原计划的工作点**：旧数据只能重标记为额外饱和重复。新 runner 已按 producer 分配总 rate，并要求实测 published rate 通过 ±5% gate。
14. **旧 Pair 1 的 RabbitMQ Q5 `VALID` 是误判**：旧数据已从分析剔除。新 runner 使用 `--pmessages`/`--cmessages`，同时要求 CSV、无解析错误、fill 后精确消息数和 drain 后清空；修复冒烟已通过，但正式结论仍必须等待新 boot pairs。

### 16.3 当前观察到的离群点如何处理

Pair 1/nVHE 的 Redis R1 第 5 次在吞吐仍约 94k ops/s 时，average latency 从前四次的 0.692–0.695 ms 降到 0.457 ms，p99 从 1.431–1.439 ms 降到 0.983 ms。脚本无错误，原始结果保留为有效；该现象已写入 `WORKLOG.md`，后续结合 pidstat、频率、background state 和其他 boot 判断。不会因为它“不好看”而手工删除。

---

## 17. 执行进度快照

> 本节记录 2026-07-14 09:56 的重跑前快照，启动后会过时。实时权威状态应读取 D3000 的 `state/`、`WORKLOG.md`、systemd 状态和结果有效性标记。

旧 campaign `d3000-apps-20260713-111300` 在 Pair 2/protected 期间停止。其 Pair 1 已同步并完成初步分析，但 Q3/Q5 缺陷意味着旧 campaign 只保留为审计数据，不再继续 Pair 2–5，也不与修复后结果合并。停止时保存了 control-state snapshot 与 `ABORTED.md`，campaign/旧接续服务均已禁用，GRUB one-shot、THP、swap 和图形目标均已恢复。

Q3/Q5 最终修复冒烟 `rabbit-fix-verification-20260714-095422` 已在 protected boot、`THP=never` 下通过。Q3 50% 冒烟目标为 24,264 msg/s，实测 24,298.878049 msg/s，偏差 +0.1437%；Q5 100,000 条冒烟在 fill 后为 ready=100000/unacked=0，drain 后为 ready=0/unacked=0。负向非法参数被拒绝，没有错误创建 `PERFTEST_VALID`。

活动 runner 的 runtime bundle SHA256 为 `a1385b35a98df385e49243b7f06916bccc88d345a197d55fba537c48c722dd62`，与 verification marker 一致。`preflight never` 与 `preflight always` 均通过 12-leg manifest、5 formal pairs、四项目 profile 映射、handoff selftest 和 unit 内容检查；`preflight app-default` 按预期失败。

该 preflight 快照结束时正式 campaign 尚未启动：campaign 与 THP=always 接续服务均为 `inactive/disabled`，`campaign-enabled` 不存在，宿主机为 protected boot，THP 已恢复 `[always] madvise never`，swap 已开启，根分区约余 722 GiB、`/home` 约余 55 GiB。

2026-07-14 10:06 随后启动了新 campaign `d3000-apps-never-20260714-100618`。启动命令再次通过相同 preflight，启用 campaign 与 guarded chain，验证 ESP one-shot 为 `d3000-6.6.30-nvhe` 后重启。重启后 `/proc/cmdline` 为 `kvm-arm.mode=nvhe`，dmesg 有 `Hyp mode initialized successfully` 且没有 `Protected KVM` feature；state 为 profile=`never`、leg=1、stage=calibration，THP 读回 `always madvise [never]`，swap=0。`thp-always-pending` 精确等于本次 campaign ID，旧 `thp-never-pending` 已清除；Redis nVHE calibration rep 1 已开始写入新结果目录。

### 17.1 2026-07-15 08:48 正式运行与 Pair 1 分析快照

全-never campaign 已完成两侧容量校准、Pair 1/nVHE、Pair 1/protected 和 Pair 2/protected。三个正式 boot block 的时长分别为 6:57:43、6:58:01 和 6:58:13。Pair 2/nVHE 于 08:37:03 开始，08:48 正在 Redis R1 rep 2，按既有时长预计约 15:35 完成。

Pair 1 两种 mode 的原始数据已同步到本机，共 2752 个文件，两侧均有 `BOOT_BLOCK_VALID`。每侧 Redis 4×5、RabbitMQ 7×5、Geekbench 5 次和首尾 anchors 均完整；Q3 每侧 15 个速率 gate 全部通过，最大目标误差 0.135%；Q5 每侧 5 次均通过一百万条 fill 和清空 drain 的队列计数闭环；未发现 `Parsing failed`。

Pair 1 的初步信号为：Redis R2 饱和吞吐 protected 比 nVHE 低 2.04%，三个受控速率 Redis 场景的平均延迟高约 3%；RabbitMQ Q3 在共同容量 85% 点的 consumer p99 和 confirm p99 分别高 18.63% 和 17.52%，而固定 10,000 msg/s 的 Q4 差异较小；64 MiB `lat_mmap_precise` 在 boot 首尾高 50.28% 和 46.51%，但 `lat_mem_rd` endpoint 只高 0.19% 和 0.06%。这些结果只有一个独立 boot pair，不能用于有效置信区间或等价性判断。完整原值、五次范围、质量门禁和统计边界见 [`d3000-thp-never-pair1-preliminary-results.zh-CN.md`](d3000-thp-never-pair1-preliminary-results.zh-CN.md)。

---

## 18. 复现与日常检查入口

本地源码目录：

```bash
cd /home/jose/kylin-lmbench/experiments/d3000-pkvm-apps
```

D3000 上的主要入口：

```bash
# 初次构建、GRUB 和 smoke（已经完成）
bash scripts/bootstrap.sh
bash scripts/install-grub-entries.sh
bash scripts/campaign.sh smoke

# 查看状态
bash scripts/campaign.sh status

# 第一套：先做只读 preflight，再启动全项目 THP=never
bash scripts/campaign.sh preflight never
bash scripts/campaign.sh start never

# 第二套通常由 guarded chain 自动启动；故障恢复时也必须先做只读检查
bash scripts/campaign.sh preflight always
bash scripts/campaign.sh start always
```

本地安全窗口同步：

```bash
cd /home/jose/kylin-lmbench
bash experiments/d3000-pkvm-apps/sync-results-local.sh
```

Geekbench 页面清单与严格导入：

```bash
python3 experiments/d3000-pkvm-apps/geekbench-pages.py \
  experiments/d3000-pkvm-apps/results/<campaign-id>

python3 experiments/d3000-pkvm-apps/geekbench-pages.py --strict \
  experiments/d3000-pkvm-apps/results/<campaign-id>
```

最终应用指标分析：

```bash
python3 experiments/d3000-pkvm-apps/analyze-results.py \
  experiments/d3000-pkvm-apps/results/<campaign-id>
```

输出包括：

```text
analysis/metrics.csv
analysis/paired-summary.csv
analysis/summary.json
analysis/REPORT.zh-CN.md
```

应用与机制 anchor 绘图：

```bash
python3 docs/mmap/scripts/plot-d3000-app-results.py \
  analysis/<campaign-id>/metrics.csv \
  --figure-dir docs/mmap/figures \
  --prefix <campaign-id>

python3 docs/mmap/scripts/plot-d3000-anchors.py \
  experiments/d3000-pkvm-apps/results/<campaign-id> \
  --figure-dir docs/mmap/figures \
  --prefix <campaign-id>
```

绘图脚本先取 boot 内 5 次中位数，再计算同 pair penalty；正值统一表示 pKVM 更差。完整图表定义、单 Pair 边界和当前示例图见 [`PLOTTING.zh-CN.md`](../../experiments/d3000-pkvm-apps/PLOTTING.zh-CN.md)。

---

## 19. 代码、日志和上游资料索引

### 19.1 本仓库

| 路径 | 内容 |
|---|---|
| [`EXPERIMENT_PLAN.zh-CN.md`](../../experiments/d3000-pkvm-apps/EXPERIMENT_PLAN.zh-CN.md) | 简版可执行实验定义 |
| [`config.env`](../../experiments/d3000-pkvm-apps/config.env) | 版本、CPU、时长、空间 guard |
| [`campaign.sh`](../../experiments/d3000-pkvm-apps/campaign.sh) | 12-leg manifest 与 campaign 控制 |
| [`resume-campaign.sh`](../../experiments/d3000-pkvm-apps/resume-campaign.sh) | 跨 boot 状态机 |
| [`lib.sh`](../../experiments/d3000-pkvm-apps/lib.sh) | 模式判据、THP、metadata、空间检查 |
| [`run-boot-block.sh`](../../experiments/d3000-pkvm-apps/run-boot-block.sh) | anchors 与项目顺序 |
| [`run-anchors.sh`](../../experiments/d3000-pkvm-apps/run-anchors.sh) | mmap/threshold/steady-memory anchors |
| [`redis.sh`](../../experiments/d3000-pkvm-apps/redis.sh) | seed、R1–R4、数据采集 |
| [`rabbitmq.sh`](../../experiments/d3000-pkvm-apps/rabbitmq.sh) | Q1–Q5、容器与 PerfTest 采集 |
| [`run-geekbench.sh`](../../experiments/d3000-pkvm-apps/run-geekbench.sh) | warmup + 5 次 CPU suite |
| [`compute-capacity.py`](../../experiments/d3000-pkvm-apps/compute-capacity.py) | 共同容量计算 |
| [`geekbench-pages.py`](../../experiments/d3000-pkvm-apps/geekbench-pages.py) | URL manifest、HTML 校验与分数导入 |
| [`analyze-results.py`](../../experiments/d3000-pkvm-apps/analyze-results.py) | boot-paired 应用结果统计 |
| [`plot-d3000-app-results.py`](scripts/plot-d3000-app-results.py) | 应用 penalty 总览、RabbitMQ 负载曲线和 pair matrix |
| [`plot-d3000-anchors.py`](scripts/plot-d3000-anchors.py) | lat_mmap 尺寸曲线、munmap anchors 与 lat_mem 负对照 |
| [`PLOTTING.zh-CN.md`](../../experiments/d3000-pkvm-apps/PLOTTING.zh-CN.md) | 绘图统计口径、命令和输出索引 |
| [`install-grub-entries.sh`](../../experiments/d3000-pkvm-apps/install-grub-entries.sh) | ESP/secondary GRUB 安装与校验 |
| [`verify-rabbitmq-fixes.sh`](../../experiments/d3000-pkvm-apps/verify-rabbitmq-fixes.sh) | Q3/Q5 负向测试、针对性冒烟与 hash marker |
| [`launch-pending-thp-always.sh`](../../experiments/d3000-pkvm-apps/launch-pending-thp-always.sh) | 全-never 完成后的全-always guarded handoff |

### 19.2 D3000 运行期证据的仓库归档

下表路径均相对于 `experiments/d3000-pkvm-apps/`。原始文件中的 `/home/jose/kylin-lmbench-exp` 是 D3000 当时的现场路径，作为审计证据原样保留。

| 仓库归档路径 | 内容 |
|---|---|
| [`metadata/`](../../experiments/d3000-pkvm-apps/metadata/) | 版本、SHA、image digest、GRUB backup、机器信息 |
| [`logs/bootstrap.log`](../../experiments/d3000-pkvm-apps/logs/bootstrap.log) | 构建与失败尝试 |
| [`logs/campaign-service.log`](../../experiments/d3000-pkvm-apps/logs/campaign-service.log) | 全量运行 stdout/stderr |
| [`logs/events.log`](../../experiments/d3000-pkvm-apps/logs/events.log) | 事件时间线 |
| [`notes/WORKLOG.md`](../../experiments/d3000-pkvm-apps/notes/WORKLOG.md) | 人工可读执行记录和偏差 |
| [`results/rabbit-fix-verification-20260714-095422/`](../../experiments/d3000-pkvm-apps/results/rabbit-fix-verification-20260714-095422/) | 最终 Q3/Q5 targeted smoke 的命令、CSV、队列快照和有效性标记 |
| [`state/rabbitmq-fixes-verified`](../../experiments/d3000-pkvm-apps/state/rabbitmq-fixes-verified) | Rabbit/config/runtime bundle 哈希与冒烟实测摘要 |
| `metadata/preflight-{never,always}-*.txt` | 两套 THP profile 的正式启动前检查 |
| [`state/`](../../experiments/d3000-pkvm-apps/state/) | campaign ID、leg、manifest、rate 和 pending marker |
| [`results/`](../../experiments/d3000-pkvm-apps/results/) | 原始结果和 `VALID`/`BOOT_BLOCK_VALID` |

### 19.3 上游一手资料

- Redis memtier_benchmark：<https://github.com/redis/memtier_benchmark>
- Redis latency 与 THP：<https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/>
- RabbitMQ Java tools/PerfTest：<https://www.rabbitmq.com/client-libraries/java-tools>
- RabbitMQ PerfTest 完整文档：<https://perftest.rabbitmq.com/>
- Geekbench 6 Benchmark Internals：<https://www.geekbench.com/doc/geekbench6-benchmark-internals.pdf>
- Geekbench editions：<https://www.geekbench.com/editions/>

---

## 20. 最终报告完成前的检查清单

- [ ] 全-never campaign 的 5 个 boot pair 全部有 `BOOT_BLOCK_VALID`；
- [ ] guarded chain 只在全-never 写出 `CAMPAIGN_COMPLETE` 并回 VHE 后启动全-always；
- [ ] 全-always campaign 的 5 个 boot pair 全部有 `BOOT_BLOCK_VALID`；
- [ ] 两个 campaign 分别安全同步到本机；
- [ ] 所有 Geekbench canonical URL 有对应 HTML、SHA256 和 `scores.json`；
- [ ] anchors 首尾数据完成单独汇总，检查每 boot 漂移；
- [ ] Redis HDR 合并口径确认，或明确只报告 JSON totals；
- [ ] RabbitMQ 指标标明“每秒 percentile 的时间中位数”；
- [ ] 每个 pair 的五次原值、boot 中位数和 protected/nVHE delta 可追溯；
- [ ] 检查 governor/频率、swap、THP、磁盘、模式 metadata；
- [ ] 调查并记录所有离群点，不基于结果方向删点；
- [ ] 达到阈值的场景再做独立 perf/trace 诊断；
- [ ] 报告明确同机 loopback、无 guest、无温度 gate、THP 无 smaps 证据等边界；
- [ ] 清除 one-shot，确认最终回默认 VHE、swap/graphical target 恢复。

只有上述检查完成后，才能把中途的“运行正常”升级为对 pKVM 宿主机真实负载影响的正式结论。
