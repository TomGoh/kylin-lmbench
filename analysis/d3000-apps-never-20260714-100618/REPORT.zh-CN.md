# D3000 nVHE / pKVM 真实负载结果：d3000-apps-never-20260714-100618

下表的差值统一为 `protected / nVHE - 1`。吞吐/分数越高越好；延迟/时间越低越好。
统计单位是 boot pair：先在每个 boot 内取 5 次中位数，再做同 pair 差值。
n=5 下 percentile bootstrap 区间只作描述；“等价带筛查”不是总体等价性的正式证明。

| 项目 | 场景 | 指标 | pairs | 中位差值 | MAD | 描述性 paired bootstrap 95% 区间 | 等价带筛查 | 4/5 同方向 |
|---|---|---|---:|---:|---:|---:|---|---|
| geekbench | cpu | wall_time | 5 | +0.33% | 0.13% | [+0.01%, +0.50%] | 落入 | 是 |
| rabbitmq | q1-one-fast | consumer_p95 | 5 | +5.33% | 2.82% | [-1.64%, +8.15%] | 未落入/未完成 | 是 |
| rabbitmq | q1-one-fast | consumer_p99 | 5 | +4.06% | 1.51% | [-3.05%, +5.58%] | 未落入/未完成 | 是 |
| rabbitmq | q1-one-fast | published | 5 | -2.62% | 1.57% | [-4.19%, -0.03%] | 未落入/未完成 | 是 |
| rabbitmq | q1-one-fast | received | 5 | -2.65% | 1.61% | [-4.27%, -0.08%] | 未落入/未完成 | 是 |
| rabbitmq | q2-reliable | confirm_p95 | 5 | +0.91% | 0.45% | [+0.40%, +3.30%] | 未落入/未完成 | 是 |
| rabbitmq | q2-reliable | confirm_p99 | 5 | +0.68% | 0.16% | [+0.47%, +3.39%] | 落入 | 是 |
| rabbitmq | q2-reliable | consumer_p95 | 5 | -18.47% | 11.65% | [-43.25%, +9.86%] | 未落入/未完成 | 是 |
| rabbitmq | q2-reliable | consumer_p99 | 5 | -17.61% | 10.84% | [-43.23%, +10.96%] | 未落入/未完成 | 是 |
| rabbitmq | q2-reliable | published | 5 | -1.59% | 0.21% | [-3.37%, -1.18%] | 未落入/未完成 | 是 |
| rabbitmq | q2-reliable | received | 5 | -1.39% | 0.16% | [-2.71%, -0.83%] | 落入 | 是 |
| rabbitmq | q3-rate50 | confirm_p95 | 5 | +3.04% | 0.75% | [+1.05%, +3.81%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate50 | confirm_p99 | 5 | +7.03% | 1.04% | [+2.72%, +9.33%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate50 | consumer_p95 | 5 | +2.70% | 0.51% | [+0.74%, +4.32%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate50 | consumer_p99 | 5 | +3.89% | 0.49% | [+1.31%, +4.38%] | 落入 | 是 |
| rabbitmq | q3-rate50 | published | 5 | -0.00% | 0.00% | [-0.01%, +0.01%] | 落入 | 否 |
| rabbitmq | q3-rate50 | received | 5 | -0.01% | 0.01% | [-0.02%, +0.00%] | 落入 | 否 |
| rabbitmq | q3-rate70 | confirm_p95 | 5 | +2.19% | 0.83% | [+1.36%, +27.83%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate70 | confirm_p99 | 5 | +2.79% | 2.16% | [+0.63%, +15.92%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate70 | consumer_p95 | 5 | +1.36% | 1.55% | [-0.19%, +16.42%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate70 | consumer_p99 | 5 | +5.54% | 5.88% | [-0.34%, +31.20%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate70 | published | 5 | +0.00% | 0.00% | [-0.00%, +0.01%] | 落入 | 否 |
| rabbitmq | q3-rate70 | received | 5 | +0.00% | 0.00% | [+0.00%, +0.01%] | 落入 | 是 |
| rabbitmq | q3-rate85 | confirm_p95 | 5 | +16.71% | 5.68% | [+5.24%, +24.42%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate85 | confirm_p99 | 5 | +16.85% | 5.43% | [+5.17%, +22.29%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate85 | consumer_p95 | 5 | +15.91% | 5.19% | [+4.77%, +24.01%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate85 | consumer_p99 | 5 | +18.63% | 7.68% | [+3.97%, +26.40%] | 未落入/未完成 | 是 |
| rabbitmq | q3-rate85 | published | 5 | +0.00% | 0.00% | [-0.01%, +0.00%] | 落入 | 否 |
| rabbitmq | q3-rate85 | received | 5 | +0.00% | 0.00% | [-0.01%, +0.01%] | 落入 | 否 |
| rabbitmq | q4-join-late | confirm_p95 | 5 | +1.75% | 0.41% | [-3.85%, +2.93%] | 未落入/未完成 | 是 |
| rabbitmq | q4-join-late | confirm_p99 | 5 | +1.29% | 0.60% | [+0.69%, +3.01%] | 落入 | 是 |
| rabbitmq | q4-join-late | consumer_p95 | 5 | +4.83% | 3.58% | [-31.11%, +28.43%] | 未落入/未完成 | 是 |
| rabbitmq | q4-join-late | consumer_p99 | 5 | +0.90% | 0.76% | [+0.15%, +3.63%] | 落入 | 是 |
| rabbitmq | q4-join-late | published | 5 | +0.00% | 0.01% | [-0.01%, +0.02%] | 落入 | 否 |
| rabbitmq | q4-join-late | received | 5 | +0.01% | 0.00% | [+0.00%, +0.01%] | 落入 | 否 |
| rabbitmq | q5-backlog | drain_time | 5 | +6.93% | 0.63% | [+0.14%, +7.56%] | 未落入/未完成 | 是 |
| rabbitmq | q5-backlog | fill_time | 5 | +3.09% | 0.28% | [+2.01%, +3.37%] | 未落入/未完成 | 是 |
| redis | r1-steady | latency_avg | 5 | +1.31% | 0.87% | [-0.14%, +3.07%] | 未落入/未完成 | 是 |
| redis | r1-steady | latency_p50 | 5 | +1.13% | 1.13% | [+0.00%, +3.38%] | 未落入/未完成 | 否 |
| redis | r1-steady | latency_p95 | 5 | +2.04% | 1.01% | [+1.02%, +3.10%] | 未落入/未完成 | 是 |
| redis | r1-steady | latency_p99 | 5 | +1.12% | 1.14% | [-0.56%, +2.81%] | 落入 | 否 |
| redis | r1-steady | throughput | 5 | -0.00% | 0.00% | [-0.00%, +0.00%] | 落入 | 否 |
| redis | r2-pipeline | latency_avg | 5 | +1.93% | 0.45% | [+1.26%, +2.38%] | 落入 | 是 |
| redis | r2-pipeline | latency_p50 | 5 | +1.54% | 0.77% | [+0.77%, +2.33%] | 落入 | 是 |
| redis | r2-pipeline | latency_p95 | 5 | +1.34% | 0.45% | [+0.89%, +3.15%] | 未落入/未完成 | 是 |
| redis | r2-pipeline | latency_p99 | 5 | +1.70% | 0.85% | [+0.84%, +2.99%] | 落入 | 是 |
| redis | r2-pipeline | throughput | 5 | -1.87% | 0.46% | [-2.33%, -1.25%] | 落入 | 是 |
| redis | r3-ttl-eviction | latency_avg | 5 | +2.07% | 0.73% | [+0.24%, +3.16%] | 未落入/未完成 | 是 |
| redis | r3-ttl-eviction | latency_p50 | 5 | +1.93% | 0.96% | [+0.00%, +2.89%] | 落入 | 是 |
| redis | r3-ttl-eviction | latency_p95 | 5 | +1.64% | 0.01% | [+1.63%, +2.46%] | 落入 | 是 |
| redis | r3-ttl-eviction | latency_p99 | 5 | +1.90% | 0.48% | [+0.00%, +3.32%] | 落入 | 是 |
| redis | r3-ttl-eviction | throughput | 5 | -0.06% | 0.02% | [-0.10%, -0.01%] | 落入 | 是 |
| redis | r4-bgsave | latency_avg | 5 | +1.53% | 0.56% | [+0.14%, +2.92%] | 落入 | 是 |
| redis | r4-bgsave | latency_p50 | 5 | +1.09% | 1.09% | [+0.00%, +3.27%] | 未落入/未完成 | 是 |
| redis | r4-bgsave | latency_p95 | 5 | +0.90% | 0.90% | [+0.00%, +2.73%] | 落入 | 是 |
| redis | r4-bgsave | latency_p99 | 5 | +1.64% | 0.55% | [-0.54%, +3.28%] | 落入 | 是 |
| redis | r4-bgsave | throughput | 5 | -0.00% | 0.00% | [-0.01%, -0.00%] | 落入 | 是 |

完整逐次指标见 `metrics.csv`，逐 pair 原值与 bootstrap 输入见 `summary.json`。
