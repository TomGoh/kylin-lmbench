# D3000 nVHE / pKVM 真实负载结果：d3000-apps-always-20260717-093223

下表的差值统一为 `protected / nVHE - 1`。吞吐/分数越高越好；延迟/时间越低越好。
统计单位是 boot pair：先在每个 boot 内取 5 次中位数，再做同 pair 差值。
n=5 下 percentile bootstrap 区间只作描述；“等价带筛查”不是总体等价性的正式证明。

| 项目 | 场景 | 指标 | pairs | 中位差值 | MAD | 描述性 paired bootstrap 95% 区间 | 等价带筛查 | 4/5 同方向 |
|---|---|---|---:|---:|---:|---:|---|---|
| geekbench | cpu | wall_time | 5 | +0.05% | 0.10% | [-0.06%, +0.18%] | 落入 | 是 |
| rabbitmq | q1-one-fast | consumer_p95 | 5 | +2.11% | 2.33% | [-6.26%, +8.82%] | 未落入/未完成 | 否 |
| rabbitmq | q1-one-fast | consumer_p99 | 5 | +1.94% | 2.46% | [-5.21%, +6.49%] | 未落入/未完成 | 否 |
| rabbitmq | q1-one-fast | published | 5 | -1.56% | 3.28% | [-4.84%, +3.33%] | 未落入/未完成 | 否 |
| rabbitmq | q1-one-fast | received | 5 | -1.55% | 3.28% | [-4.83%, +3.32%] | 未落入/未完成 | 否 |
| rabbitmq | q2-reliable | confirm_p95 | 5 | +2.31% | 0.90% | [+1.41%, +4.37%] | 未落入/未完成 | 是 |
| rabbitmq | q2-reliable | confirm_p99 | 5 | +3.28% | 0.40% | [+1.43%, +3.68%] | 落入 | 是 |
| rabbitmq | q2-reliable | consumer_p95 | 5 | +4.31% | 6.04% | [-15.34%, +59.18%] | 未落入/未完成 | 否 |
| rabbitmq | q2-reliable | consumer_p99 | 5 | +4.23% | 6.00% | [-15.51%, +58.82%] | 未落入/未完成 | 否 |
| rabbitmq | q2-reliable | published | 5 | -3.37% | 0.63% | [-4.00%, -2.02%] | 未落入/未完成 | 是 |
| rabbitmq | q2-reliable | received | 5 | -2.29% | 1.40% | [-5.28%, -0.89%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate50 | confirm_p95 | 5 | +2.66% | 0.52% | [+1.07%, +4.09%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate50 | confirm_p99 | 5 | +4.05% | 0.81% | [+1.33%, +6.92%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate50 | consumer_p95 | 5 | +2.62% | 0.62% | [+1.00%, +4.16%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate50 | consumer_p99 | 5 | +2.43% | 0.24% | [+0.89%, +4.91%] | 落入 | 是 |
| rabbitmq | q3-rate50 | published | 5 | +0.00% | 0.00% | [-0.01%, +0.00%] | 落入 | 否 |
| rabbitmq | q3-rate50 | received | 5 | +0.00% | 0.00% | [-0.02%, +0.00%] | 落入 | 否 |
| rabbitmq | q3-rate70 | confirm_p95 | 5 | +11.21% | 5.83% | [+5.38%, +24.47%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate70 | confirm_p99 | 5 | +5.43% | 2.16% | [+3.27%, +17.17%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate70 | consumer_p95 | 5 | +4.60% | 1.62% | [+2.98%, +12.53%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate70 | consumer_p99 | 5 | +10.92% | 3.34% | [+5.39%, +29.46%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate70 | published | 5 | +0.00% | 0.00% | [-0.00%, +0.00%] | 落入 | 否 |
| rabbitmq | q3-rate70 | received | 5 | +0.00% | 0.00% | [-0.01%, +0.01%] | 落入 | 否 |
| rabbitmq | q3-rate85 | confirm_p95 | 5 | +18.85% | 4.06% | [+14.62%, +40.51%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate85 | confirm_p99 | 5 | +16.97% | 2.63% | [+14.34%, +38.55%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate85 | consumer_p95 | 5 | +19.80% | 3.44% | [+16.36%, +43.94%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate85 | consumer_p99 | 5 | +19.02% | 4.41% | [+14.60%, +42.06%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate85 | published | 5 | +0.00% | 0.00% | [-0.00%, +0.00%] | 落入 | 否 |
| rabbitmq | q3-rate85 | received | 5 | +0.00% | 0.00% | [+0.00%, +0.00%] | 落入 | 否 |
| rabbitmq | q4-join-late | confirm_p95 | 5 | +1.09% | 1.84% | [-2.00%, +4.69%] | 未落入/未完成 | 是 |
| rabbitmq | q4-join-late | confirm_p99 | 5 | +1.74% | 0.71% | [-0.23%, +3.04%] | 落入 | 是 |
| rabbitmq | q4-join-late | consumer_p95 | 5 | -0.18% | 4.50% | [-13.64%, +23.33%] | 未落入/未完成 | 否 |
| rabbitmq | q4-join-late | consumer_p99 | 5 | +1.81% | 0.30% | [+0.60%, +2.11%] | 落入 | 是 |
| rabbitmq | q4-join-late | published | 5 | +0.01% | 0.01% | [+0.00%, +0.02%] | 落入 | 否 |
| rabbitmq | q4-join-late | received | 5 | +0.00% | 0.00% | [+0.00%, +0.01%] | 落入 | 否 |
| rabbitmq | q5-backlog | drain_time | 5 | -6.62% | 0.37% | [-7.00%, +8.31%] | 未落入/未完成 | 否 |
| rabbitmq | q5-backlog | fill_time | 5 | +1.55% | 1.03% | [+0.52%, +3.19%] | 未落入/未完成 | 是 |
| redis | r1-steady | latency_avg | 5 | +1.75% | 1.18% | [-0.29%, +3.37%] | 未落入/未完成 | 是 |
| redis | r1-steady | latency_p50 | 5 | +1.13% | 1.13% | [+0.00%, +3.38%] | 未落入/未完成 | 是 |
| redis | r1-steady | latency_p95 | 5 | +2.06% | 1.04% | [+1.02%, +4.13%] | 未落入/未完成 | 是 |
| redis | r1-steady | latency_p99 | 5 | +1.70% | 1.14% | [-0.56%, +3.39%] | 落入 | 是 |
| redis | r1-steady | throughput | 5 | +0.00% | 0.00% | [-0.00%, +0.00%] | 落入 | 否 |
| redis | r2-pipeline | latency_avg | 5 | +2.02% | 0.56% | [+1.34%, +2.58%] | 落入 | 是 |
| redis | r2-pipeline | latency_p50 | 5 | +2.33% | 0.00% | [+1.54%, +2.33%] | 落入 | 是 |
| redis | r2-pipeline | latency_p95 | 5 | +1.79% | 0.91% | [+0.89%, +3.62%] | 未落入/未完成 | 是 |
| redis | r2-pipeline | latency_p99 | 5 | +1.70% | 0.86% | [+0.84%, +3.43%] | 落入 | 是 |
| redis | r2-pipeline | throughput | 5 | -1.99% | 0.54% | [-2.53%, -1.32%] | 落入 | 是 |
| redis | r3-ttl-eviction | latency_avg | 5 | +1.58% | 0.98% | [+0.60%, +3.17%] | 未落入/未完成 | 是 |
| redis | r3-ttl-eviction | latency_p50 | 5 | +0.95% | 0.01% | [+0.94%, +3.85%] | 未落入/未完成 | 是 |
| redis | r3-ttl-eviction | latency_p95 | 5 | +1.64% | 0.01% | [+1.63%, +3.28%] | 未落入/未完成 | 是 |
| redis | r3-ttl-eviction | latency_p99 | 5 | +1.42% | 0.95% | [+0.47%, +3.32%] | 落入 | 是 |
| redis | r3-ttl-eviction | throughput | 5 | -0.04% | 0.01% | [-0.10%, -0.02%] | 落入 | 是 |
| redis | r4-bgsave | latency_avg | 5 | +1.96% | 0.83% | [+0.14%, +2.78%] | 落入 | 是 |
| redis | r4-bgsave | latency_p50 | 5 | +1.09% | 1.09% | [+0.00%, +3.27%] | 未落入/未完成 | 是 |
| redis | r4-bgsave | latency_p95 | 5 | +1.80% | 0.00% | [+1.80%, +3.64%] | 未落入/未完成 | 是 |
| redis | r4-bgsave | latency_p99 | 5 | +1.64% | 1.08% | [+0.00%, +2.72%] | 落入 | 是 |
| redis | r4-bgsave | throughput | 5 | -0.01% | 0.00% | [-0.01%, +0.00%] | 落入 | 否 |

完整逐次指标见 `metrics.csv`，逐 pair 原值与 bootstrap 输入见 `summary.json`。
