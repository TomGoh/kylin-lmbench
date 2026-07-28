# D3000 nVHE / pKVM 真实负载结果：d3000-apps-never-20260714-100618

下表的差值统一为 `protected / nVHE - 1`。吞吐/分数越高越好；延迟/时间越低越好。
统计单位是 boot pair：先在每个 boot 内取 5 次中位数，再做同 pair 差值。

| 项目 | 场景 | 指标 | pairs | 中位差值 | MAD | paired bootstrap 95% CI | 等价 | 4/5 同方向 |
|---|---|---|---:|---:|---:|---:|---|---|
| rabbitmq | q1-one-fast | consumer_p95 | 1 | +8.15% | 0.00% | [+8.15%, +8.15%] | 否/未完成 | 否 |
| rabbitmq | q1-one-fast | consumer_p99 | 1 | +5.58% | 0.00% | [+5.58%, +5.58%] | 否/未完成 | 否 |
| rabbitmq | q1-one-fast | published | 1 | -2.62% | 0.00% | [-2.62%, -2.62%] | 否/未完成 | 否 |
| rabbitmq | q1-one-fast | received | 1 | -2.65% | 0.00% | [-2.65%, -2.65%] | 否/未完成 | 否 |
| rabbitmq | q2-reliable | confirm_p95 | 1 | +1.36% | 0.00% | [+1.36%, +1.36%] | 否/未完成 | 否 |
| rabbitmq | q2-reliable | confirm_p99 | 1 | +0.84% | 0.00% | [+0.84%, +0.84%] | 否/未完成 | 否 |
| rabbitmq | q2-reliable | consumer_p95 | 1 | -6.82% | 0.00% | [-6.82%, -6.82%] | 否/未完成 | 否 |
| rabbitmq | q2-reliable | consumer_p99 | 1 | -6.77% | 0.00% | [-6.77%, -6.77%] | 否/未完成 | 否 |
| rabbitmq | q2-reliable | published | 1 | -1.80% | 0.00% | [-1.80%, -1.80%] | 否/未完成 | 否 |
| rabbitmq | q2-reliable | received | 1 | -1.45% | 0.00% | [-1.45%, -1.45%] | 否/未完成 | 否 |
| rabbitmq | q3-rate50 | confirm_p95 | 1 | +2.40% | 0.00% | [+2.40%, +2.40%] | 否/未完成 | 否 |
| rabbitmq | q3-rate50 | confirm_p99 | 1 | +7.03% | 0.00% | [+7.03%, +7.03%] | 否/未完成 | 否 |
| rabbitmq | q3-rate50 | consumer_p95 | 1 | +2.19% | 0.00% | [+2.19%, +2.19%] | 否/未完成 | 否 |
| rabbitmq | q3-rate50 | consumer_p99 | 1 | +3.35% | 0.00% | [+3.35%, +3.35%] | 否/未完成 | 否 |
| rabbitmq | q3-rate50 | published | 1 | -0.01% | 0.00% | [-0.01%, -0.01%] | 否/未完成 | 否 |
| rabbitmq | q3-rate50 | received | 1 | -0.02% | 0.00% | [-0.02%, -0.02%] | 否/未完成 | 否 |
| rabbitmq | q3-rate70 | confirm_p95 | 1 | +1.36% | 0.00% | [+1.36%, +1.36%] | 否/未完成 | 否 |
| rabbitmq | q3-rate70 | confirm_p99 | 1 | +2.79% | 0.00% | [+2.79%, +2.79%] | 否/未完成 | 否 |
| rabbitmq | q3-rate70 | consumer_p95 | 1 | -0.19% | 0.00% | [-0.19%, -0.19%] | 否/未完成 | 否 |
| rabbitmq | q3-rate70 | consumer_p99 | 1 | +5.54% | 0.00% | [+5.54%, +5.54%] | 否/未完成 | 否 |
| rabbitmq | q3-rate70 | published | 1 | -0.00% | 0.00% | [-0.00%, -0.00%] | 否/未完成 | 否 |
| rabbitmq | q3-rate70 | received | 1 | +0.00% | 0.00% | [+0.00%, +0.00%] | 否/未完成 | 否 |
| rabbitmq | q3-rate85 | confirm_p95 | 1 | +17.65% | 0.00% | [+17.65%, +17.65%] | 否/未完成 | 否 |
| rabbitmq | q3-rate85 | confirm_p99 | 1 | +17.52% | 0.00% | [+17.52%, +17.52%] | 否/未完成 | 否 |
| rabbitmq | q3-rate85 | consumer_p95 | 1 | +17.07% | 0.00% | [+17.07%, +17.07%] | 否/未完成 | 否 |
| rabbitmq | q3-rate85 | consumer_p99 | 1 | +18.63% | 0.00% | [+18.63%, +18.63%] | 否/未完成 | 否 |
| rabbitmq | q3-rate85 | published | 1 | +0.00% | 0.00% | [+0.00%, +0.00%] | 否/未完成 | 否 |
| rabbitmq | q3-rate85 | received | 1 | -0.01% | 0.00% | [-0.01%, -0.01%] | 否/未完成 | 否 |
| rabbitmq | q4-join-late | confirm_p95 | 1 | +2.16% | 0.00% | [+2.16%, +2.16%] | 否/未完成 | 否 |
| rabbitmq | q4-join-late | confirm_p99 | 1 | +3.01% | 0.00% | [+3.01%, +3.01%] | 否/未完成 | 否 |
| rabbitmq | q4-join-late | consumer_p95 | 1 | +4.83% | 0.00% | [+4.83%, +4.83%] | 否/未完成 | 否 |
| rabbitmq | q4-join-late | consumer_p99 | 1 | +0.45% | 0.00% | [+0.45%, +0.45%] | 否/未完成 | 否 |
| rabbitmq | q4-join-late | published | 1 | +0.02% | 0.00% | [+0.02%, +0.02%] | 否/未完成 | 否 |
| rabbitmq | q4-join-late | received | 1 | +0.01% | 0.00% | [+0.01%, +0.01%] | 否/未完成 | 否 |
| rabbitmq | q5-backlog | drain_time | 1 | +7.32% | 0.00% | [+7.32%, +7.32%] | 否/未完成 | 否 |
| rabbitmq | q5-backlog | fill_time | 1 | +3.09% | 0.00% | [+3.09%, +3.09%] | 否/未完成 | 否 |
| redis | r1-steady | latency_avg | 1 | +3.07% | 0.00% | [+3.07%, +3.07%] | 否/未完成 | 否 |
| redis | r1-steady | latency_p50 | 1 | +3.38% | 0.00% | [+3.38%, +3.38%] | 否/未完成 | 否 |
| redis | r1-steady | latency_p95 | 1 | +3.10% | 0.00% | [+3.10%, +3.10%] | 否/未完成 | 否 |
| redis | r1-steady | latency_p99 | 1 | +2.81% | 0.00% | [+2.81%, +2.81%] | 否/未完成 | 否 |
| redis | r1-steady | throughput | 1 | -0.00% | 0.00% | [-0.00%, -0.00%] | 否/未完成 | 否 |
| redis | r2-pipeline | latency_avg | 1 | +2.06% | 0.00% | [+2.06%, +2.06%] | 否/未完成 | 否 |
| redis | r2-pipeline | latency_p50 | 1 | +2.33% | 0.00% | [+2.33%, +2.33%] | 否/未完成 | 否 |
| redis | r2-pipeline | latency_p95 | 1 | +2.70% | 0.00% | [+2.70%, +2.70%] | 否/未完成 | 否 |
| redis | r2-pipeline | latency_p99 | 1 | +2.56% | 0.00% | [+2.56%, +2.56%] | 否/未完成 | 否 |
| redis | r2-pipeline | throughput | 1 | -2.04% | 0.00% | [-2.04%, -2.04%] | 否/未完成 | 否 |
| redis | r3-ttl-eviction | latency_avg | 1 | +3.16% | 0.00% | [+3.16%, +3.16%] | 否/未完成 | 否 |
| redis | r3-ttl-eviction | latency_p50 | 1 | +2.86% | 0.00% | [+2.86%, +2.86%] | 否/未完成 | 否 |
| redis | r3-ttl-eviction | latency_p95 | 1 | +2.46% | 0.00% | [+2.46%, +2.46%] | 否/未完成 | 否 |
| redis | r3-ttl-eviction | latency_p99 | 1 | +3.32% | 0.00% | [+3.32%, +3.32%] | 否/未完成 | 否 |
| redis | r3-ttl-eviction | throughput | 1 | -0.10% | 0.00% | [-0.10%, -0.10%] | 否/未完成 | 否 |
| redis | r4-bgsave | latency_avg | 1 | +2.92% | 0.00% | [+2.92%, +2.92%] | 否/未完成 | 否 |
| redis | r4-bgsave | latency_p50 | 1 | +3.27% | 0.00% | [+3.27%, +3.27%] | 否/未完成 | 否 |
| redis | r4-bgsave | latency_p95 | 1 | +2.73% | 0.00% | [+2.73%, +2.73%] | 否/未完成 | 否 |
| redis | r4-bgsave | latency_p99 | 1 | +3.28% | 0.00% | [+3.28%, +3.28%] | 否/未完成 | 否 |
| redis | r4-bgsave | throughput | 1 | -0.01% | 0.00% | [-0.01%, -0.01%] | 否/未完成 | 否 |

完整逐次指标见 `metrics.csv`，逐 pair 原值与 bootstrap 输入见 `summary.json`。
