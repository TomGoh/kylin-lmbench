# D3000 pKVM 真实负载实验绘图说明

本文说明如何从 D3000 campaign 的原始结果生成可审计 SVG。绘图风格沿用 `docs/mmap/scripts/` 下现有脚本：只使用 Python 标准库，直接解析 CSV 或原始日志并写出 SVG，不依赖 matplotlib、seaborn 或浏览器截图。

## 1. 统计口径

应用图和 anchor 图都以 boot pair 为统计单位。脚本先在一个 boot 内对 5 次 repetition 取中位数，再计算同一个 pair 的 protected/nVHE 差值。同一 boot 内的 5 次不会被画成 5 个独立 pKVM 样本。

应用开销图统一显示“pKVM penalty”：延迟和 wall time 使用 `protected / nVHE - 1`，吞吐和分数使用其相反数。这样无论指标原始方向如何，图中正值/红色始终表示 pKVM 更差，负值/绿色始终表示 pKVM 更好。SVG 的标题、副标题和 `<desc>` 都明确记录了这个变换。

当只有 Pair 1 时，bar 和 median 只是该单 pair 的值，图中会明确标为 preliminary。Pair 2–5 到齐并重新运行 analyzer 后，脚本会自动增加每个 pair 的点、填充 penalty matrix，并把 bar 更新为 5 个 paired penalty 的中位数。

## 2. 应用结果脚本

[`plot-d3000-app-results.py`](../../docs/mmap/scripts/plot-d3000-app-results.py) 读取 [`analyze-results.py`](analyze-results.py) 生成的 `metrics.csv`，输出三张图。

`application-overview.svg` 使用水平 bar 显示 Redis、RabbitMQ 和已导入的 Geekbench 核心指标。bar 是所有完整 boot pair 的 penalty 中位数，深色圆点是每一个独立 pair。

若尚未保存 Geekbench 结果页，统一分析器会从每次正式运行的 `time.txt` 提取 suite wall time，图中将其明确标为辅助时间指标。它包含结果上传阶段，不能替代 official single-core、multi-core 或子项分数；导入 `scores.json` 后，绘图脚本会同时显示正式分数。

`rabbitmq-load-curve.svg` 使用绝对 p99 延迟展示 Q3 50%、70%、85% 的 nVHE/pKVM 曲线。淡线表示单独 pair，粗线表示所有完整 pair 的中位数。该图只适用于 Q3 实际速率 gate 已通过的数据。

`pair-penalty-matrix.svg` 为每个核心指标保留 Pair 1–5 独立单元格，并另列 paired median。未完成 pair 显示为空白而不是 0；正值为红色，负值为绿色。

当前 Pair 1 的生成命令为：

```bash
cd /home/jose/kylin-lmbench

python3 docs/mmap/scripts/plot-d3000-app-results.py \
  analysis/d3000-apps-never-20260714-100618-pair1/metrics.csv \
  --figure-dir docs/mmap/figures \
  --prefix d3000-thp-never-pair1
```

## 3. 机制 anchor 脚本

[`plot-d3000-anchors.py`](../../docs/mmap/scripts/plot-d3000-anchors.py) 直接读取 campaign 下每个 `pair/mode/anchors-{start,end}/rep-00` 的原始文件，不依赖应用 analyzer。它要求一个 pair 的 nVHE/protected × boot start/end 四组都存在 `VALID` 后，才把该 pair 纳入图中。

`anchor-lat-mmap.svg` 展示 0.5–64 MiB `lat_mmap_precise` 的 boot 首尾绝对曲线。每个原始 size 先在 boot 内取 5 次中位数；淡线为单 pair，粗线为跨完整 pair 的中位数。横轴使用 log2 spacing 并明确标注，避免把 16→64 MiB 与普通一次倍增画成相同距离。

`anchor-controls.svg` 左侧展示 64 MiB `lat_mmap`、dense-1.9、dense-2.0、sparse-6.4 的 paired penalty，右侧使用独立窄尺度展示 `lat_mem_rd` 64 MiB endpoint 的绝对值。两种尺度分开，避免约 200% 的 sparse munmap 信号把约 0.1% 的稳态访存负对照压成不可见。

当前 Pair 1 的生成命令为：

```bash
cd /home/jose/kylin-lmbench

python3 docs/mmap/scripts/plot-d3000-anchors.py \
  experiments/d3000-pkvm-apps/results/d3000-apps-never-20260714-100618 \
  --figure-dir docs/mmap/figures \
  --prefix d3000-thp-never-pair1
```

## 4. 后续 Pair 与 THP profile

每次安全同步更多完整 pair 后，先对整个 campaign 重新运行 analyzer，再用同一个 prefix 重画。不要把 `pair-1` 子目录单独复制成五份，也不要将同一 boot 内 repetitions 当作 pair。

```bash
python3 experiments/d3000-pkvm-apps/analyze-results.py \
  experiments/d3000-pkvm-apps/results/<campaign-id> \
  --out analysis/<campaign-id>

python3 docs/mmap/scripts/plot-d3000-app-results.py \
  analysis/<campaign-id>/metrics.csv \
  --figure-dir docs/mmap/figures \
  --prefix <campaign-id>

python3 docs/mmap/scripts/plot-d3000-anchors.py \
  experiments/d3000-pkvm-apps/results/<campaign-id> \
  --figure-dir docs/mmap/figures \
  --prefix <campaign-id>
```

全-never 与全-always 是两套独立 campaign，必须分别重新分析和绘图，使用不同 prefix。最终文档可以并列两套 application overview、pair matrix 和 anchors；不能把两个 profile 的 pair 拼进同一组五 pair 统计。若后续增加跨 profile interaction 图，其输入也必须是两套各自已经完成 boot pairing 的 paired penalty，而不是 repetition 级原值。

## 5. 已生成图表

完整 THP=never 五-pair campaign：

- [`d3000-thp-never-full-application-overview.svg`](../../docs/mmap/figures/d3000-thp-never-full-application-overview.svg)
- [`d3000-thp-never-full-rabbitmq-load-curve.svg`](../../docs/mmap/figures/d3000-thp-never-full-rabbitmq-load-curve.svg)
- [`d3000-thp-never-full-pair-penalty-matrix.svg`](../../docs/mmap/figures/d3000-thp-never-full-pair-penalty-matrix.svg)
- [`d3000-thp-never-full-anchor-lat-mmap.svg`](../../docs/mmap/figures/d3000-thp-never-full-anchor-lat-mmap.svg)
- [`d3000-thp-never-full-anchor-controls.svg`](../../docs/mmap/figures/d3000-thp-never-full-anchor-controls.svg)

Pair 1 阶段性示例图仍保留用于审计绘图演进：

- [`d3000-thp-never-pair1-application-overview.svg`](../../docs/mmap/figures/d3000-thp-never-pair1-application-overview.svg)
- [`d3000-thp-never-pair1-rabbitmq-load-curve.svg`](../../docs/mmap/figures/d3000-thp-never-pair1-rabbitmq-load-curve.svg)
- [`d3000-thp-never-pair1-pair-penalty-matrix.svg`](../../docs/mmap/figures/d3000-thp-never-pair1-pair-penalty-matrix.svg)
- [`d3000-thp-never-pair1-anchor-lat-mmap.svg`](../../docs/mmap/figures/d3000-thp-never-pair1-anchor-lat-mmap.svg)
- [`d3000-thp-never-pair1-anchor-controls.svg`](../../docs/mmap/figures/d3000-thp-never-pair1-anchor-controls.svg)

带 `pair1` 前缀的图只包含 Pair 1，并明确标记 `n=1`；它们不替代带 `full` 前缀的五个完整 boot pair 正式图。

## 6. 测试

测试会验证吞吐/分数的符号反转、boot 内中位数、Q3 load curve、缺失 pair 单元格、原始 anchor 解析和 paired penalty：

```bash
python3 -m unittest \
  tests.test_d3000_analysis \
  tests.test_plot_d3000_app_results \
  tests.test_plot_d3000_anchors
```
