# D3000 RabbitMQ Q3/Q5 修复与重跑前核验记录

本文记录 2026-07-14 对 RabbitMQ Q3/Q5 数据问题的停机、修复、负向测试、针对性冒烟和正式 campaign preflight。它的目的不是给出性能结论，而是证明新一轮全量实验不会继续使用已知错误的 Q3/Q5 命令，也不会在 THP profile 或接续状态上静默偏离计划。

## 1. 旧 campaign 为什么停止

旧 campaign `d3000-apps-20260713-111300` 的 Pair 1 已完成，但审计发现两个正式性缺陷。

Q3 使用 8 个 producers。RabbitMQ PerfTest 2.25.0 的 `--rate` 是每个 producer 的速率，旧脚本却把期望的总速率直接传给每个 producer。因此标称 50%、70%、85% 的三组都被放大为 8 倍 offered rate，并实际跑成饱和负载。

Q5 使用了 PerfTest 不支持的 `--producer-msg-count` 和 `--consumer-msg-count`。PerfTest 打印 `Parsing failed` 后仍返回 0，旧 wrapper 只检查退出码，因而错误创建 `VALID`。这些目录没有有效 fill/drain CSV，不能进入分析。

发现后立即停止并禁用 `d3000-pkvm-campaign.service` 与旧 THP 接续服务，清除 `campaign-enabled` 和 GRUB one-shot，恢复 THP、swap 与图形目标。旧结果完整保留为审计材料，但整个 campaign 不再继续，也不从 Pair 2 接着跑。Pair 1 的可用与不可用边界见 [`d3000-pair1-preliminary-results.zh-CN.md`](d3000-pair1-preliminary-results.zh-CN.md)。

## 2. Q3 修复

新脚本先计算该 profile 校准得到的共同容量 `C_common`，再按百分比计算期望总速率，并把总速率向上取整分配给 8 个 producers：

```text
requested_total = floor(C_common × percentage / 100)
per_producer_rate = ceil(requested_total / producer_count)
effective_total = per_producer_rate × producer_count
```

传给 PerfTest 的 `--rate` 只使用 `per_producer_rate`。每次 repetition 保存 `rate-target.env`，记录共同容量、百分比、producer 数、期望总速率、每 producer 参数和取整后的有效总目标。

命令正确仍不足以证明负载实际到达目标。脚本会丢弃正式 360 秒中的前 60 秒，从 CSV 计算剩余样本的 published mean，要求至少 120 个样本且与有效总目标的偏差不超过 ±5%。校验结果保存为 `rate-validation.env`；任何条件不满足都不会创建该 repetition 的 `VALID`。

## 3. Q5 修复

fill 改用 PerfTest 2.25.0 支持的 `--pmessages 1000000`，drain 改用 `--cmessages 1000000`。wrapper 现在同时要求：进程返回 0、stderr 不含 `Parsing failed`、CSV 非空且至少有一个数据行、CSV header 含预期字段。只有全部满足才创建 `PERFTEST_VALID`。

Q5 还增加了队列状态闭环。fill 完成后通过 `rabbitmqctl list_queues --formatter json` 和 `jq` 要求 `q5-backlog` 恰好有 1,000,000 条 ready、0 条 unacknowledged；drain 完成后要求 ready 与 unacknowledged 都为 0。两次检查分别保存 JSON、`validation.env` 和 `QUEUE_COUNTS_VALID`。只有 fill、队列计数、drain、清空计数全部成功才创建 repetition 的 `VALID`。

## 4. 失败保护

`rabbitmq.sh invalid-option-selftest` 故意向 PerfTest 传入不存在的参数。2026-07-14 的负向测试确认 PerfTest 确实打印了解析错误，而新 wrapper 返回失败且没有创建 `PERFTEST_VALID`。

正式启动还受 `state/rabbitmq-fixes-verified` 保护。该 marker 不只绑定 `rabbitmq.sh` 和 `config.env`，还绑定 17 个 campaign 运行时文件组成的 bundle SHA256。任一 runner、profile 逻辑、接续器或 systemd unit 在冒烟后发生变化，`campaign.sh preflight/start` 都会拒绝执行，要求重新验证。

旧 marker 的拒绝测试也已实际执行：部署 `never → always` runner 后，旧 marker 因 `config.env` 哈希不匹配使 `preflight never` 返回 1；没有创建 campaign 标记、没有启用服务、没有重启。

## 5. 最终针对性冒烟

最终权威冒烟 ID 为 `rabbit-fix-verification-20260714-095422`，运行于当前 protected boot，并明确设置 `THP_PROFILE=never`。事件日志确认 `set_project_thp rabbitmq` 写入后读回的 sysfs 状态为 `never`。冒烟结束后 cleanup 恢复了 `[always] madvise never`、swap 和 graphical target。

Q3 使用旧 Pair 1 的共同容量 48,515 msg/s 只验证速率计算和观测闭环。50% 点的 requested total 为 24,257 msg/s，8 个 producers 各传 `--rate 3033`，有效总目标为 24,264 msg/s。丢弃前 5 秒后得到 41 个样本，实测 published mean 为 24,298.878049 msg/s，误差 +0.1437%，在 ±5% gate 内。正式 campaign 不会复用这份容量；`THP=never` 和 `THP=always` 会分别重新校准。

Q5 冒烟把消息数缩短为 100,000 条，只验证固定消息数和队列闭环。实际 fill 命令使用 `--pmessages 100000`，fill 后 ready=100000、unacknowledged=0；实际 drain 命令使用 `--cmessages 100000`，drain 后 ready=0、unacknowledged=0。Q3/Q5 正式目录中没有 `Parsing failed`，所有 `PERFTEST_VALID`、`QUEUE_COUNTS_VALID` 和 repetition `VALID` 均存在。

最终 marker 为：

```text
verified_at=2026-07-14T09:56:04+08:00
verification_id=rabbit-fix-verification-20260714-095422
mode=protected
thp_profile=never
rabbitmq_sha256=c5dd818fd0f743f934cf090f855e98d7c35d94eb893d929c9ca92cac028cfc0d
config_sha256=4e7f2dafc2b1d57580080924fa78d0cb3a2d9863afe927fc7e5f7cb46f1f6ce8
runtime_bundle_sha256=a1385b35a98df385e49243b7f06916bccc88d345a197d55fba537c48c722dd62
```

## 6. THP campaign 顺序核验

正式顺序已改为两套完整、相互独立的 campaign：先全项目 `THP=never`，再全项目 `THP=always`。每套都包含 nVHE/protected 两次容量校准和 5 个正式 boot pair，每个场景在每个 boot 内运行 5 次。两套使用不同 campaign ID、不同 `capacity.json` 和 rate 状态，不能跨 profile 拼接。

profile 映射测试覆盖 anchors、Redis、RabbitMQ、Geekbench 四类项目：`never` 下四项都返回 `never`，`always` 下四项都返回 `always`。旧的混合 `app-default` 被明确拒绝，`campaign.sh preflight app-default` 返回 1。

接续器自测覆盖正常启动第二套、第一套只完成 11 个 leg、第二套完成后的清理、缺少完整结果标记和旧混合 profile 五种状态。只有第一套完成 leg 12、写出 `CAMPAIGN_COMPLETE`、清除活动标记并回到 VHE 时才允许启动 `always`；第二套完成后才清除 pending marker 并禁用服务。

2026-07-14 09:56 的 D3000 实机 preflight 结果如下：

| 检查 | `never` | `always` |
|---|---|---|
| 四项目实际 profile 映射 | 全部匹配 | 全部匹配 |
| handoff selftest | pass | pass |
| manifest | 12 legs、5 formal pairs | 12 legs、5 formal pairs |
| runtime bundle | `a1385b35…dd62` | `a1385b35…dd62` |
| preflight | pass | pass |

preflight 结束时 campaign 与接续服务均为 `inactive/disabled`，`campaign-enabled` 不存在，宿主机 THP 已恢复为 always，swap 已启用。也就是说，上述检查没有偷偷启动正式实验。

## 7. 正式参数与证据路径

RabbitMQ 正式参数为：warmup 60 秒、steady 360 秒、Q3 8 producers、丢弃 60 秒、至少 120 个速率样本、容差 ±5%、Q5 1,000,000 条消息、单阶段 timeout 1,800 秒。每个场景每个 boot 运行 5 次。

D3000 权威证据路径：

- 冒烟结果：[`results/rabbit-fix-verification-20260714-095422`](../../experiments/d3000-pkvm-apps/results/rabbit-fix-verification-20260714-095422/)
- 验证 marker：[`state/rabbitmq-fixes-verified`](../../experiments/d3000-pkvm-apps/state/rabbitmq-fixes-verified)
- `never` preflight：[`metadata/`](../../experiments/d3000-pkvm-apps/metadata/) 下的 `preflight-never-*.txt`
- `always` preflight：[`metadata/`](../../experiments/d3000-pkvm-apps/metadata/) 下的 `preflight-always-*.txt`
- 旧 marker 拒绝证据：[`preflight-before-reverification.txt`](../../experiments/d3000-pkvm-apps/metadata/preflight-before-reverification.txt)
- 事件与人工记录：[`events.log`](../../experiments/d3000-pkvm-apps/logs/events.log)、[`WORKLOG.md`](../../experiments/d3000-pkvm-apps/notes/WORKLOG.md)

PerfTest 参数语义以 [RabbitMQ PerfTest 2.25.0 文档](https://perftest.rabbitmq.com/) 和 D3000 保存的实际 `--help` 输出为准。

## 8. 正式启动后的回读核验

2026-07-14 10:06:18 创建第一套 campaign `d3000-apps-never-20260714-100618`。`start never` 在执行任何状态写入前再次通过 preflight，然后启用 `d3000-pkvm-campaign.service` 与 `d3000-thp-always-chain.service`，把 ESP one-shot 验证为 `d3000-6.6.30-nvhe` 并重启。

重启后核验不是只看 cmdline：`/proc/cmdline` 为 `kvm-arm.mode=nvhe`，dmesg 有 `X [1]: Hyp mode initialized successfully`，同时不存在 `CPU features: detected: Protected KVM`。campaign state 为 profile=`never`、leg=1、stage=calibration；服务为 `activating`，THP sysfs 为 `always madvise [never]`，swap 为空。`thp-always-pending` 的内容与本次 campaign ID 完全一致，旧 `thp-never-pending` 不存在。新结果目录已写入 12 行 manifest、`campaign.env`，Redis calibration rep 1 已开始生成 memtier 输出。
