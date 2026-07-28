# D3000：nVHE 与 pKVM 真实负载对照实验执行定义

## 1. 目标与边界

目标是在同一台 D3000、同一 `6.6.30+` 内核和同一用户态工具链上，比较
`kvm-arm.mode=nvhe` 与 `kvm-arm.mode=protected` 对宿主机真实应用的影响。默认 VHE
只用于安装、smoke 和恢复，不进入主要差值。当前内核未启用 `CONFIG_XCORE_STATS`，
所以本轮不报告 EL2 gate/op3 计数。

单机负载固定为服务端 CPU 0-3、客户端 CPU 4-7。这个拓扑能回答同一宿主机上的
端到端差异，但不等价于独立负载机，因此最终报告必须明确 loopback 与共享内存带宽的边界。

## 2. 固定环境

- Phytium D3000，8 CPU，两个 4 核 cluster，32 GiB RAM。
- CPU 0-7 online，governor=`performance`；每腿记录实际频率。
- ASLR=2；正式实验期间 swap 关闭。
- Redis 与 mmap anchors：THP=`never`。
- RabbitMQ 与 Geekbench：THP=`always`。
- 服务端 CPU 0-3；负载发生器 CPU 4-7；Geekbench 使用 CPU 0-7。
- 每次有效重复之间冷却 30 秒。
- 每个场景每个 boot 做 5 次有效重复，不用 3 次结果代替。
- 大数据位于 `/kylin-lmbench-exp-work`；脚本、日志和结果位于
  `/home/jose/kylin-lmbench-exp`。

## 3. 固定工具

- Redis 8.8.0，core build，不启用 Redis modules。
- memtier_benchmark 2.3.1，4 threads × 25 clients，共 100 个连接。
- RabbitMQ 官方 `rabbitmq:4.3.1-management` ARM64 镜像；首次 pull 后以 RepoDigest 固定。
- RabbitMQ PerfTest 2.25.0 uber JAR，OpenJDK 17。
- Geekbench 6.7.1 ARM Preview Build 603632，归档 SHA256 固定。
- lmbench/mmap anchors 固定到本仓库提交 `52d1942`。
- `perf` 从运行内核对应的 `/home/jose/common/tools/perf` 构建；重观测不混入主跑分。

每个下载文件保存 SHA256，每个工具保存版本输出、完整命令和构建日志。Kylin 仓库若迫使
编译器版本与上游推荐不同，必须写入 `WORKLOG.md`，且两种 KVM 模式共用同一个二进制。

## 4. 启动与配对

自定义 GRUB 项只追加 nVHE/protected，不改变 `GRUB_DEFAULT=0` 的 VHE 默认项。D3000
活动配置在 ESP 的 `/boot/efi/boot/grub`；安装时必须备份并保持它与 `/boot/grub`
两份 `grub.cfg` 字节一致。one-shot 必须写 ESP `grubenv` 并读回 `next_entry` 后才可重启。

模式硬判据：

- nVHE：cmdline 有 `kvm-arm.mode=nvhe`，dmesg 有
  `Hyp mode initialized successfully`，没有 `CPU features: detected: Protected KVM`。
- protected：cmdline 有 `kvm-arm.mode=protected`，dmesg 同时有
  `CPU features: detected: Protected KVM` 与该 Kylin 分支的成功标志
  `Kylin X Core initialized successfully`，且没有 `Protected KVM not available with VHE`。
- VHE：dmesg 有 `VHE mode initialized successfully`。

先各做 nVHE/protected 启动 smoke。正式前在两种模式各完成 Redis/RabbitMQ 5 次容量
校准。五个正式 boot pair 顺序为：

1. nVHE → protected；项目顺序 Geekbench → Redis → RabbitMQ。
2. protected → nVHE；项目顺序 Redis → RabbitMQ → Geekbench。
3. nVHE → protected；项目顺序 RabbitMQ → Geekbench → Redis。
4. protected → nVHE；项目顺序 Geekbench → RabbitMQ → Redis。
5. nVHE → protected；项目顺序 Redis → Geekbench → RabbitMQ。

每腿成功后才原子推进状态并指定下一 one-shot；失败停在当前模式，不跨过错误。最后一腿
清除活动标记，恢复 THP、swap、graphical target，并回默认 VHE。

## 5. Boot anchors

每个正式 boot 的最前和最后各执行一次 anchor 组；组内每点重复 5 次：

- `lat_mmap_precise`：0.5/1/2/4/8/16/64 MiB。
- `op_sweep munmap`：dense 1.9 MiB、dense 2.0 MiB、sparse 6.4 MiB/16 KiB stride。
- `lat_mem_rd`：64 MiB、128 B stride。

首尾 anchor 用于检测模式信号、热漂移和异常 boot，不作为应用分数。

## 6. Redis

固定 RDB seed 的实际 `used_memory` 至少 8 GiB；保存 key count、used_memory 与 RDB
SHA256。所有正式重复从同一个 seed 拷贝开始。Redis 固定 CPU 0-3，memtier 固定 CPU
4-7。memtier 使用确定性 key range、`--distinct-client-seed`，不使用时间戳
`--randomize`。`--rate-limiting` 是每连接值，整机目标除以 100 后向上取整，并记录
舍入后的实际目标。

容量校准：nVHE/protected 各 5 次 180 秒，1 KiB、SET:GET=1:10、pipeline=1、无限速。
`C_common=min(median(C_nvhe), median(C_protected))`。

正式场景每项每 boot 5 次：

- R1：1:10、1 KiB、uniform、pipeline=1、70% `C_common`、300 秒。
- R2：1:1、1 KiB、pipeline=16、无限速、180 秒。
- R3：1:1、64-4096 B、TTL 60-300 秒、10 GiB `allkeys-lru`、pipeline=1、
  70% `C_common`、300 秒。
- R4：8 GiB seed、1:1、pipeline=1、70% `C_common`、360 秒，在 120/240 秒触发
  BGSAVE；第二次只有在第一次完成后才执行。

保存 memtier JSON、HDR、文本输出，Redis INFO memory/stats/persistence、latency histogram
和 pidstat。现行脚本会随临时 data directory 删除 per-run server log；这是已知归档缺口，
最终报告不得把 server log 列为已经保存的证据。

## 7. RabbitMQ

broker 使用已固定 digest 的官方容器、host network、CPU 0-3；PerfTest/JVM 使用 CPU
4-7。每个重复使用全新 broker data dir，startup 后做 60 秒不计分 warmup。steady 场景
正式跑 360 秒，分析丢弃前 60 秒。

容量校准：8 classic durable queues、8 producers、8 consumers、persistent 1000 B、
confirm=500、qos=500、multi-ack=100，nVHE/protected 各 5 次；取共同容量。

正式场景每项每 boot 5 次：

- Q1：单 classic transient queue，1 producer/1 consumer，全速。
- Q2：8 classic durable queues，8p/8c，persistent、confirm=500、qos=500、
  multi-ack=100，全速。
- Q3：复用 Q2，固定 50%/70%/85% `C_common` 三个相同工作点。
- Q4：persistent queue，10 consumers 延迟 120 秒加入，总发布 10k msg/s。
- Q5：先固定发布 1,000,000 条，再由 4 consumers 固定排空；分别记录 fill/drain wall time。

保存 PerfTest CSV、stdout/stderr（含 p50/p95/p99 与 confirm latency）、完整命令、容器
日志与 inspect、RabbitMQ status/memory/queues、docker stats 和 pidstat。

## 8. Geekbench

每个 boot 先做 1 次不计分 CPU warmup，再做 5 次正式 CPU suite；不跑 GPU。保存完整
stdout/stderr、`/usr/bin/time -v` 与 Browser URL。Preview CLI 没有本地结果/禁上传开关，
所以 stdout 是原始证据。

## 9. 有效性、诊断和统计

非零退出、客户端错误、模式错误、CPU governor 未设为 `performance`、swap 活跃、空间
guard 失败或关键输出缺失时，该次无效；脚本停止，不自动把部分结果算入。现行脚本没有
自动重试实现；失败后必须先人工调查，再明确决定是否重新执行当前 repetition 或 boot block。

主分数不附加重 tracing。当前自动 campaign 只采轻量指标；主 campaign 完成后，再按结果
选择核心场景做 nVHE/protected 各 5 次 `perf stat` 诊断复跑。若业务差异满足任一条件，
再做两模式各 5 次、60 秒 syscall/TLB trace：吞吐或时间差至少 3%，p99 差至少 5%，
或 5 个 boot pair 中至少 4 个同方向。诊断复跑不与主分数混合。

统计先在每个 boot 内取 5 次中位数，再做同 pair 的 `protected / nvhe - 1`。报告每个
boot pair 原值、MAD、paired bootstrap 95% CI。等价区间：吞吐、时间、平均延迟、p50、
p95 与 Geekbench 子项 ±3%，p99 ±5%。HDR 在可合并时合并直方图，禁止对五个 p99
直接求平均。

## 10. 日志与同步

- `logs/events.log`：所有脚本事件时间线。
- `logs/bootstrap.log`、`logs/campaign-service.log`：安装构建与跨 boot 活动日志。
- `notes/WORKLOG.md`：模式、决策、异常、偏差和每次有效结果的人工可读笔记。
- `metadata/`：SHA256、镜像 digest、工具版本、GRUB 备份和机器信息。
- `results/`：按 campaign/pair/mode/project/scenario/rep 保存原始数据及 `VALID` 标记。

在 boot 完成后的安全窗口从 D3000 增量同步到本机 `/home/jose/kylin-lmbench-exp`，排除
`work/` 和 `build/`，不使用 `--delete`。当前 campaign 不在计分中主动 rsync；同步由
控制端手工触发，同步日志本身也作为活动证据保留。

## 11. THP profile 顺序

先执行独立的 `THP_PROFILE=never` campaign，再执行独立的 `THP_PROFILE=always` campaign。
两套均复用同一工具、seed、场景、时长、NP/PN boot 顺序和每场景 5 次重复；anchors、Redis、
RabbitMQ、Geekbench 在一套 campaign 内统一使用该 profile。每套重新做 Redis 与 RabbitMQ
容量校准并生成独立 rate 状态，结果使用不同 campaign ID，不能跨 profile 拼接同一 boot pair。

guarded handoff 只有在全-never 完成第 12 腿、结果目录写出 `CAMPAIGN_COMPLETE`、活动标记
清除并回到 VHE 后才启动全-always。两套使用同一份 hash-locked runner，不在中途替换脚本。
第一套失败或人工停止时，pending 标记会被清除，第二套不会自动启动。
