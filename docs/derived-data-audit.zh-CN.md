# lmbench 派生数据核验记录

日期：2026-06-07

## 核验范围

本次核验以 `results/**/*.txt` 中的 lmbench 原始输出为基准，检查 Claude 后续生成的 CSV/XLSX 数据是否准确。

已核验的派生文件：

- `results/n90-day3-host/*.csv`
- `docs/n90-kvm-host/lmbench-N10-4config-all-metrics.csv`
- `docs/n90-kvm-host/lmbench-N10-4config.xlsx`
- `docs/n90-kvm-host/lmbench-N10-4config-mean.xlsx`

说明：guest、VirtCCA、海光 CSV 目录当前没有已落盘的派生 CSV/XLSX 文件；这些目录下主要是原始 `iter*.txt`。

## 核验方法

1. 使用当前项目的 `parse-lmbench.py` 从 N90 host 的 `iter*.txt` 重新生成每个配置的 per-iteration CSV。
2. 将重新生成的 CSV 与 `results/n90-day3-host/*.csv` 做逐行 multiset 对比。
3. 基于 per-iteration 数据重算：
   - median 版：中位数、MAD%、跨配置百分比变化。
   - mean 版：均值、RSD%、跨配置百分比变化。
4. 对 `lat_mmap` 的高精度覆盖行，使用 `results/precise-mmap/{kvmoff,vhe,nvhe,pkvm}.log` 单独重算。
5. 使用 `openpyxl` 读取 XLSX 的 `All metrics`、`Highlights`、`Per-iter raw` 三个工作表，与重算结果逐项比较。

## 结论

总体结论：主统计数据基本可靠。初次核验发现两个数据问题和两个复现性问题；其中脚本复现性问题和 mean 版 XLSX 的 `Per-iter raw` 统计列问题已经在 2026-06-07 修复并重新生成。

### 1. N90 host per-iteration CSV

以下 4 个 CSV 与原始 `iter*.txt` 重新解析结果完全一致：

- `n90-kvmoff-noLSM-full-cpu0.csv`
- `n90-vhe-noLSM-full-cpu0.csv`
- `n90-nvhe-noLSM-full-cpu0.csv`
- `n90-pkvm-noLSM-try2-cpu0.csv`

`n90-nvhe-noisy-full-cpu0.csv` 的数值列、迭代编号和指标内容与原始数据一致，但 `env` 列写错了：

- 当前值：`n90-nvhe-noLSM-full`
- 应为：`n90-nvhe-noisy-full`

这属于元数据错误，不影响数值本身，但会误导后续按 `env` 分组的分析。

### 2. `lmbench-N10-4config-all-metrics.csv`

该 CSV 共 684 行，指标集合完整，没有缺行或多行。

除 `lat_mmap` 外，所有行均与 N90 host 原始数据重算出的 median、MAD%、跨配置百分比变化一致。

`lat_mmap` 中 7 个 size 行使用了 `results/precise-mmap/*.log` 的高精度复测数据覆盖：

- 0.5 MB
- 1 MB
- 2 MB
- 4 MB
- 8 MB
- 16 MB
- 64 MB

这些覆盖值与 `results/precise-mmap/*.log` 重新计算结果一致。`32 MB` 对应的 `sz33.554432MB` 行没有高精度复测数据，仍来自普通 lmbench 输出。

结论：该 CSV 的数值是准确的，但文档中需要明确注明 `lat_mmap` 部分混用了高精度复测数据，否则会让人误以为全部来自同一批 lmbench raw CSV。

### 3. `lmbench-N10-4config.xlsx`

median 版 XLSX 核验结果：

- `All metrics`：684 行全部正确。
- `Highlights`：45 个重点项全部正确。
- `Per-iter raw`：180 行迭代单值、中位数、MAD% 全部正确。

结论：median 版 XLSX 的数据准确。

### 4. `lmbench-N10-4config-mean.xlsx`

初次核验时，mean 版 XLSX 结果如下：

- `All metrics`：684 行全部正确。
- `Highlights`：45 个重点项全部正确。
- `Per-iter raw`：180 行中的 10 次迭代单值全部正确。
- `Per-iter raw` 右侧统计列存在问题：144 行的“均值/RSD%”实际仍是“中位数/MAD%”。

问题来源是生成脚本中的 `build_per_iter()` 固定使用 `statistics.median()` 和 MAD%，没有根据 `STAT_MODE == 'mean'` 切换到均值和 RSD%。`lat_mmap` 中部分行后来被 `update-xlsx-precise-mmap.py` 覆盖，因此没有全部 180 行都错。

修复后已重新运行 `python3 scripts/build-xlsx.py median` 和 `python3 scripts/build-xlsx.py mean`，并重新核验：

- median 版 `All metrics`：684 行，0 个 mismatch。
- median 版 `Per-iter raw`：180 行，迭代单值 0 个 mismatch，统计列 0 个 mismatch。
- mean 版 `All metrics`：684 行，0 个 mismatch。
- mean 版 `Per-iter raw`：180 行，迭代单值 0 个 mismatch，统计列 0 个 mismatch。

结论：当前 mean 版 XLSX 已修复。

## 复现性问题

### 1. 生成脚本路径已过期

初次核验时，`scripts/build-xlsx.py`、`scripts/build-xlsx-median.py`、`scripts/build-xlsx-mean.py` 中硬编码：

```python
DAY3 = 'results/n90-day3'
```

当前实际 host 数据目录是：

```text
results/n90-day3-host
```

因此这些脚本在当前项目结构下不能直接重跑。

修复后，三份脚本均已改为 `results/n90-day3-host`，并已实测可重新生成 XLSX。

### 2. XLSX README 中的数据来源路径也已过期

初次核验时，XLSX 的 README 页仍写着：

```text
results/n90-day3/n90-{kvmoff,nvhe,vhe,pkvm}-noLSM-full-cpu0.csv
```

实际应改为 `results/n90-day3-host/...`。另外，README 也应补充说明 `lat_mmap` 的部分行来自 `results/precise-mmap/*.log`。

修复后，重新生成的 XLSX README 已更新数据来源路径，并增加了 `lat_mmap` 高精度覆盖说明。

## 建议修正

1. 修正 `results/n90-day3-host/n90-nvhe-noisy-full-cpu0.csv` 的 `env` 列。
2. 已修正 `scripts/build-xlsx*.py` 的数据目录路径。
3. 已修正 `build_per_iter()`，mean 模式下的 `Per-iter raw` 末两列现在使用均值和 RSD%。
4. 已重新生成 `lmbench-N10-4config.xlsx` 和 `lmbench-N10-4config-mean.xlsx`，并重新运行对比。
5. 已在 XLSX README 中说明 `lat_mmap` 高精度覆盖数据的来源；其他分析文档仍需按引用情况补充说明。
