# D3000 pKVM 真实负载实验：Pair 1 初步对比

本文只分析旧 campaign `d3000-apps-20260713-111300` 的 Pair 1。原始数据现归档在 [`experiments/d3000-pkvm-apps/results/d3000-apps-20260713-111300/pair-1`](../../experiments/d3000-pkvm-apps/results/d3000-apps-20260713-111300/pair-1/)。分析日期为 2026-07-14。由于 Q3/Q5 的正式性缺陷，旧 campaign 已在 Pair 2 期间停止并整体封存；本文只作为发现信号和审计采集链的中间材料，不与修复后的正式 `THP=never → THP=always` campaign 合并统计。

## 1. 结论摘要

Pair 1 已经给出三个清楚但性质不同的信号。

第一，机制 anchors 明确识别出了 protected/pKVM：64 MiB `lat_mmap_precise` 在 boot 首、尾分别比 nVHE 慢 46.64% 和 45.47%，`op_sweep` 的 sparse-6.4 在首、尾分别慢 214.81% 和 208.86%；与之相对，64 MiB `lat_mem_rd` 只差 0.73% 和 0.06%。这与此前“映射拆除路径明显受影响，但稳态内存访问并未普遍变慢”的机制结论一致，也说明两次启动确实形成了预期的 nVHE/protected 对照。

第二，Redis 在 Pair 1 中没有出现大的 pKVM 退化。四个场景中，受控速率场景的吞吐差为 0.00% 到 -0.04%，平均延迟和 p99 的变化基本在 0% 到 +1.08% 内；全速 pipeline 场景 R2 的差异最大，吞吐为 -1.73%，平均延迟为 +1.74%，p99 为 +0.85%。就这一对 boot 而言，Redis 的宿主机应用影响是“小于约 2%”的量级。

第三，RabbitMQ 在全速可靠消息路径上出现了值得继续验证的负向信号。Q2 的发布吞吐为 -3.10%，接收吞吐为 -2.44%，confirm p99 为 +2.94%；原本命名为 Q3 50%/70%/85% 的三个点也都得到约 -2.8% 到 -3.3% 的发布吞吐和 +1.9% 到 +3.8% 的 confirm p99。但 Q3 的限速配置有错误，实际上三个点都在跑饱和负载，因此只能作为额外的饱和重复，不能解释成 50%/70%/85% 负载曲线。固定 10,000 msg/s 的 Q4 则几乎完全相同，发布吞吐差 0.00%，接收吞吐差 +0.01%，consumer p99 差 +0.75%。

现在还不能把上述数字写成最终的“pKVM 开销”。Pair 1 只有一个 nVHE boot 和一个 protected boot，五次 repetition 只是同一 boot 内的重复，不是五个独立 boot 样本；而且 Pair 1 的顺序固定为 nVHE 先、protected 后。它适合发现明显信号、数据缺陷和量级，不能计算有效的跨 boot 置信区间或等价性结论。

## 2. 数据完整性与比较口径

| 检查项 | nVHE | protected |
|---|---|---|
| boot block | `BOOT_BLOCK_VALID` | `BOOT_BLOCK_VALID` |
| 启动参数 | `kvm-arm.mode=nvhe` | `kvm-arm.mode=protected` |
| 内核 | `6.6.30+ #2` | `6.6.30+ #2` |
| 受保护模式判据 | 不适用 | dmesg 有 `Protected KVM` 和 `Kylin X Core initialized successfully` |
| Redis | 4 场景 × 5 次 | 4 场景 × 5 次 |
| RabbitMQ 常规场景 | Q1–Q4 共 6 个场景 × 5 次 | Q1–Q4 共 6 个场景 × 5 次 |
| RabbitMQ Q5 | 5 个目录均被错误标记为 `VALID`，实际未执行 | 5 个目录均被错误标记为 `VALID`，实际未执行 |
| Geekbench | 1 次 warmup + 5 次正式运行，URL 齐全 | 1 次 warmup + 5 次正式运行，URL 齐全 |
| anchors | boot 首尾各一组，每点 5 次 | boot 首尾各一组，每点 5 次 |

主 campaign 的应用配置为：anchors 和 Redis 使用 THP=`never`，RabbitMQ 和 Geekbench 使用 THP=`always`。anchor 与 Geekbench 的 metadata 已分别记录为 `always madvise [never]` 和 `[always] madvise never`；swap 为空，ASLR=2。

Redis 每个 repetition 直接读取 memtier JSON 的 `ALL STATS/Totals`，然后在同一 boot 的五次 repetition 上取中位数。RabbitMQ 常规场景先丢弃每次 360 秒运行的前 60 秒，再对每秒 CSV 指标取中位数，最后在同一 boot 的五次 repetition 上取中位数。本文所有百分比均为 `protected / nVHE - 1`；吞吐为负表示 protected 较慢，延迟为正表示 protected 较慢。

## 3. Redis

### 3.1 boot 内五次中位数

| 场景 | nVHE 吞吐 ops/s | protected 吞吐 ops/s | 吞吐差 | nVHE 平均延迟 ms | protected 平均延迟 ms | 平均延迟差 | nVHE p99 ms | protected p99 ms | p99 差 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R1 steady，1:10、pipeline=1、受控速率 | 94,003.7 | 94,003.7 | +0.00% | 0.692 | 0.695 | +0.43% | 1.439 | 1.439 | +0.00% |
| R2 pipeline，全速、pipeline=16 | 632,432.0 | 621,494.2 | -1.73% | 2.528 | 2.572 | +1.74% | 3.775 | 3.807 | +0.85% |
| R3 TTL/eviction、受控速率 | 93,918.7 | 93,880.8 | -0.04% | 0.830 | 0.839 | +1.08% | 1.711 | 1.727 | +0.94% |
| R4 BGSAVE、受控速率 | 93,935.8 | 93,929.7 | -0.01% | 0.727 | 0.730 | +0.41% | 1.487 | 1.495 | +0.54% |

R2 是 Redis 中唯一接近 2% 的点，而且五次结果的区间没有重叠：nVHE 吞吐范围为 629,598.3–637,322.9 ops/s，protected 为 620,223.6–623,830.6 ops/s。这个信号值得由后续 boot pair 判断是否可重复。R1、R3 和 R4 的吞吐受到共同 offered rate 限制，本来就不应通过吞吐寻找容量差，主要应看延迟；这些点的 Pair 1 延迟变化均较小。

R1 和 R4 的 nVHE 各有一次明显低于其余四次的平均延迟结果，但中位数不受单个点支配。原始值没有删除，后续仍按预先确定的 boot 内中位数处理。

## 4. RabbitMQ

### 4.1 吞吐

| 场景 | nVHE 发布 msg/s | protected 发布 msg/s | 发布差 | nVHE 接收 msg/s | protected 接收 msg/s | 接收差 |
|---|---:|---:|---:|---:|---:|---:|
| Q1 单 transient queue，全速 | 69,142 | 67,138 | -2.90% | 69,087 | 67,100 | -2.88% |
| Q2 8 durable queues，persistent+confirm，全速 | 52,105 | 50,489 | -3.10% | 50,903 | 49,660 | -2.44% |
| Q3 标称 50%，实际饱和 | 51,958 | 50,430 | -2.94% | 50,928 | 49,592 | -2.62% |
| Q3 标称 70%，实际饱和 | 51,773 | 50,042 | -3.34% | 50,552 | 48,123 | -4.80% |
| Q3 标称 85%，实际饱和 | 52,054 | 50,591 | -2.81% | 50,702 | 49,567 | -2.24% |
| Q4 固定 10,000 msg/s，consumer 延迟加入 | 10,008 | 10,008 | +0.00% | 10,007 | 10,008 | +0.01% |

Q1 的五次发布吞吐区间重叠较多：nVHE 为 64,682–72,609 msg/s，protected 为 66,530–69,739 msg/s，因此 -2.90% 仍可能受单 boot 状态影响。Q2 的区间则分离得更清楚：nVHE 为 51,598–52,202 msg/s，protected 为 50,158–51,025 msg/s。Q2 及三个实际饱和的 Q3 点共同提示 protected 的 reliable-message 饱和能力在 Pair 1 中低约 3%，但这些点共享同一对 boot，不能把它们当成多个独立的 pKVM 样本。

### 4.2 延迟

| 场景 | nVHE consumer p99 | protected consumer p99 | consumer p99 差 | nVHE confirm p99 | protected confirm p99 | confirm p99 差 |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 18.469 ms | 17.637 ms | -4.50% | 不适用 | 不适用 | 不适用 |
| Q2 | 9.313 s | 8.128 s | -12.72% | 197.359 ms | 203.156 ms | +2.94% |
| Q3 标称 50%，实际饱和 | 8.032 s | 10.969 s | +36.56% | 198.678 ms | 204.755 ms | +3.06% |
| Q3 标称 70%，实际饱和 | 8.534 s | 14.604 s | +71.12% | 197.869 ms | 205.456 ms | +3.83% |
| Q3 标称 85%，实际饱和 | 8.619 s | 7.975 s | -7.48% | 198.452 ms | 202.190 ms | +1.88% |
| Q4 | 0.666 ms | 0.671 ms | +0.75% | 0.868 ms | 0.867 ms | -0.12% |

Q2/Q3 的 consumer latency 已经达到数秒，并且五次 repetition 的离散度很大。例如 Q3 标称 70% 的 nVHE consumer p99 范围是 6.04–15.46 秒，protected 是 8.08–17.18 秒。这是生产速度超过消费/落盘能力后不断形成 backlog 的排队时间，不是相同 offered load 下的稳态请求延迟。protected 在 Q2 的 consumer p99 更低也不能解释成“pKVM 改善了延迟”，因为它同时发布得更慢；Q3 的 +36%、+71%、-7% 也不能用作 pKVM 尾延迟结论。

confirm p99 的量级和方向更稳定：Q2 以及三个饱和 Q3 点均为 protected 较慢，差值为 +1.88% 到 +3.83%。它与发布吞吐下降方向一致，是后续 boot pair 应重点复核的 RabbitMQ 指标。

### 4.3 Q3 的限速配置错误

PerfTest 2.25.0 文档说明 `--rate` 是“每个 producer”的发布速率。现行 Q3 命令使用 8 个 producers，却把期望的总速率 24,257、33,960、41,237 直接传给了每个 producer，因此理论 offered rate 实际变成 194,056、271,680、329,896 msg/s，全部远高于校准得到的共同容量 48,515 msg/s。

原始 CSV 也直接验证了这一点：三个标称工作点的 nVHE 发布中位数都在 51.8–52.1k msg/s，protected 都在 50.0–50.6k msg/s，没有随 50%/70%/85% 改变。Pair 1 的 Q3 应重新标记为三个“饱和可靠消息重复组”。如果要恢复原设计，脚本必须把总目标除以 8 后再传给 `--rate`，并在每次结果中校验实测 published rate 是否接近目标。

### 4.4 Q5 无有效数据

Q5 的 fill 命令使用 `--producer-msg-count`，drain 命令使用 `--consumer-msg-count`；PerfTest 2.25.0 实际接受 `-C`/`--pmessages` 和 `-D`/`--cmessages`。两条错误命令都打印 `Parsing failed. Reason: Unrecognized option`，没有生成正式 `perftest.csv`，但 PerfTest 在该解析错误下仍返回退出码 0，导致 shell 脚本继续创建了 `VALID`。

nVHE/protected 的 5×2 个 Q5 repetition 全部存在同样问题，所以 0.46 秒左右的所谓 fill/drain time 只是 JVM 打印帮助并退出的时间，必须完全剔除。分析器已经增加了“fill 和 drain 都必须存在非空 `perftest.csv`，且 stderr 不能有 `Parsing failed`”的检查，当前 Pair 1 的 Q5 不再进入汇总。数据采集脚本仍需改用正确参数，并在 fill 后确认队列恰有 1,000,000 条 ready messages、drain 后确认 ready/unacked 都为 0，然后在新 boot pair 中补跑。

## 5. Boot anchors

### 5.1 `lat_mmap_precise`

下表每个值都是同一 anchor group 内五次进程内结果的中位数。

| 映射尺寸 | boot 首 nVHE µs | boot 首 protected µs | 首差值 | boot 尾 nVHE µs | boot 尾 protected µs | 尾差值 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 MiB | 6.490 | 7.332 | +12.97% | 7.341 | 8.925 | +21.58% |
| 1 MiB | 10.702 | 13.147 | +22.84% | 8.888 | 11.548 | +29.92% |
| 2 MiB | 16.893 | 21.294 | +26.06% | 16.191 | 20.683 | +27.74% |
| 4 MiB | 25.810 | 36.066 | +39.74% | 25.761 | 35.338 | +37.18% |
| 8 MiB | 45.949 | 65.233 | +41.97% | 45.859 | 65.081 | +41.92% |
| 16 MiB | 84.252 | 122.846 | +45.81% | 84.276 | 121.971 | +44.73% |
| 64 MiB | 324.229 | 475.461 | +46.64% | 324.769 | 472.430 | +45.47% |

4–64 MiB 的差值在 boot 首尾高度一致。64 MiB 的 nVHE 首尾漂移为 +0.17%，protected 为 -0.64%，没有看到会掩盖模式信号的大幅长时漂移。0.5–2 MiB 的绝对时间很短、相对抖动更大，不应单独用于判断应用性能。

### 5.2 `op_sweep munmap`

| 场景 | boot 首 nVHE µs | boot 首 protected µs | 首差值 | boot 尾 nVHE µs | boot 尾 protected µs | 尾差值 |
|---|---:|---:|---:|---:|---:|---:|
| dense-1.9 | 65.9 | 113.7 | +72.53% | 66.4 | 111.4 | +67.77% |
| dense-2.0 | 64.1 | 76.0 | +18.56% | 64.5 | 64.7 | +0.31% |
| sparse-6.4 | 72.9 | 229.5 | +214.81% | 72.2 | 223.0 | +208.86% |

dense-1.9 与 sparse-6.4 的 protected 退化在首尾都很明显；dense-2.0 的首组存在较大离散，尾组则几乎没有差异。整体形态保留了此前观察到的 2 MiB 阈值边界，但 Pair 1 不能单独精确量化阈值点。

### 5.3 `lat_mem_rd` 稳态访存负对照

| 阶段 | nVHE 64 MiB endpoint | protected 64 MiB endpoint | 差值 |
|---|---:|---:|---:|
| boot 首 | 6.843 ns | 6.893 ns | +0.73% |
| boot 尾 | 7.041 ns | 7.045 ns | +0.06% |

两种模式的稳态访存端点基本相同。它支持“应用差异不应简单归因于所有内存访问都变慢”，但不能替代应用级的多 boot 配对统计。

## 6. Geekbench 状态

nVHE 和 protected 都完成了 5 次正式 Geekbench 6 CPU suite，10 个公开结果 URL 均已保留，但运行 stdout 只打印 URL，没有总分或子项分数，本地尚无结果页 HTML，因此本版报告暂不伪造或猜测 Geekbench 差值。

需要保存的公开页面及文件名见 [`pair1-geekbench-pages.csv`](../../experiments/d3000-pkvm-apps/pair1-geekbench-pages.csv)。HTML 应放到 `experiments/d3000-pkvm-apps/results/d3000-apps-20260713-111300/geekbench-pages/<result-id>.html`，再由 `geekbench-pages.py --strict` 导入为每次 repetition 的 `scores.json`。claim URL 含有领取 key，不需要保存或写入报告。

## 7. Pair 1 能回答什么、不能回答什么

Pair 1 可以支持以下初步判断：D3000 的 protected 模式仍有很强的 mmap/munmap 机制税；它没有扩展成同等幅度的稳态访存或 Redis 性能下降；RabbitMQ 的 reliable-message 饱和路径可能有约 3% 的吞吐和 2%–4% 的 confirm-latency 代价；固定在容量以下的 Q4 没有观察到明显影响。

Pair 1 不能支持以下结论：不能声称 Redis 已证明“等价”；不能给任何指标报跨 boot 95% 置信区间；不能把 Q3 当作 50%/70%/85% 负载曲线；不能把 Q2/Q3 的秒级 consumer latency 当作稳定服务延迟；不能使用 Q5；也不能在尚未导入网页时报告 Geekbench 分数。

现有分析器对单 pair 做 bootstrap 时区间会退化成该单个差值，这不是有效统计区间。正式报告仍应按原方案等待 5 个完整 boot pair：每个 boot 内先取五次中位数，再对五个 paired delta 做中位数、MAD、配对 bootstrap 和方向一致性检查。

## 8. 后续处理

1. 旧 campaign 的 Q1/Q2/Q4、Redis、anchors 和 Geekbench 原始运行继续保留；Q3 重标记为饱和重复，Q5 标记为无效，不让错误的 `VALID` 污染分析。
2. 不再只补 Q3/Q5，也不从 Pair 2 接续旧 campaign。修复后从容量校准和 Pair 1 开始完整重跑：先全项目 `THP=never` 的 5 个 boot pair，再全项目 `THP=always` 的 5 个 boot pair。
3. Q3 已改为把总目标分配给 8 个 producers，并强制核验实测 published rate；Q5 已改用 `--pmessages`/`--cmessages` 并核验 fill/drain 队列计数。最终冒烟与启动 gate 见 [`d3000-rabbitmq-q3-q5-fix-verification.zh-CN.md`](d3000-rabbitmq-q3-q5-fix-verification.zh-CN.md)。
4. Pair 1 的 10 个 Geekbench HTML 仍可导入，用于审计旧信号，但正式结论只使用新 campaign 自己的完整页面集合。

## 9. 复现入口

- 原始 Pair 1：[`results/d3000-apps-20260713-111300/pair-1`](../../experiments/d3000-pkvm-apps/results/d3000-apps-20260713-111300/pair-1/)
- 容量校准：[`capacity.json`](../../experiments/d3000-pkvm-apps/results/d3000-apps-20260713-111300/capacity.json)
- 应用分析器：[`analyze-results.py`](../../experiments/d3000-pkvm-apps/analyze-results.py)
- Geekbench 页面清单：[`pair1-geekbench-pages.csv`](../../experiments/d3000-pkvm-apps/pair1-geekbench-pages.csv)
- 完整实验设计与执行记录：[`d3000-pkvm-real-workload-experiment.zh-CN.md`](d3000-pkvm-real-workload-experiment.zh-CN.md)
- RabbitMQ PerfTest 2.25.0 参数语义：[官方文档](https://perftest.rabbitmq.com/)
