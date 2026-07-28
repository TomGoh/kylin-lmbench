# D3000 pKVM 真实负载实验归档说明

本目录是 D3000 nVHE/pKVM 真实负载实验的仓库内完整证据归档。2026-07-28 归档前，材料位于本机同步目录 `/home/jose/kylin-lmbench-exp`；归档完成后，本机这一外部副本被移除。D3000 上曾经使用的同名运行目录属于远端实验现场，本次整理不修改远端目录、不重启 D3000。

## 1. 归档范围

实验产生且不可由上游重新生成的内容全部进入 Git：正式与中止 campaign 的原始数据、smoke 和修复验证数据、正常与失败日志、机器及启动元数据、人工工作记录、GRUB 备份、campaign 状态快照、暂存控制文件，以及当时实际部署到 D3000 的脚本。归档迁移共校验 33,738 个证据文件和 27 个部署脚本；脱敏前的源目录与仓库目标逐文件计算 SHA-256 后完全一致。提交前仅对 Geekbench claim key 做了下述定点脱敏。

目录含义如下：

| 路径 | 内容与使用边界 |
|---|---|
| 本目录顶层的 `*.sh`、`*.py`、`config.env` 和 service 文件 | 仓库中的当前可维护版本，包含实验期间及之后补入的分析、超时和恢复修正 |
| `deployed-scripts/` | 从实验同步目录原样保存的 D3000 最终部署快照；用于回答“当时实际跑的是哪一版”，不应被后续修正覆盖 |
| `results/` | 所有原始结果，包括正式 campaign、旧 campaign、模式 smoke、RabbitMQ Q3/Q5 负向和正向验证，以及 `invalid/` 中隔离的失败腿；Geekbench claim key 已脱敏，普通结果 URL 和结果 ID 保留 |
| `logs/` | bootstrap、campaign service、事件时间线和同步日志 |
| `metadata/` | 工具版本、SHA-256、RabbitMQ image digest/inspect、preflight、模式证据和 GRUB 备份 |
| `notes/` | `WORKLOG.md`、执行方案、事故记录、阶段分析和人工操作说明的现场快照；其中的绝对路径按历史原文保留 |
| `state/`、`staged/`、`configs/` | campaign 状态机、待执行材料和实际配置快照 |
| 仓库根目录 `analysis/` | 由当前分析器从原始数据重新生成的表格、JSON 和报告 |
| `docs/mmap/` | 实验设计、阶段报告、正式分析、绘图脚本和 SVG |

`ARCHIVE_SHA256SUMS` 覆盖 `configs/`、`deployed-scripts/`、`logs/`、`metadata/`、`notes/`、`results/`、`staged/` 和 `state/` 下脱敏后可提交的 33,765 个文件。`MIGRATION_SOURCE_SHA256SUMS` 保存同一批文件从外部目录复制完成、尚未脱敏时的摘要，前者与后者恰有 247 个文件不同。两个清单都有意不覆盖当前可维护脚本和生成型分析文件：前者由 Git 版本控制，后者应从原始数据重算。

## 2. Campaign 状态

旧 campaign `d3000-apps-20260713-111300` 在发现 RabbitMQ Q3 限速语义错误和 Q5 参数错误后停止。它只保留为问题发现与采集链审计证据，不能与修复后的数据混合统计。

正式 `THP=never` campaign `d3000-apps-never-20260714-100618` 和正式 `THP=always` campaign `d3000-apps-always-20260717-093223` 均有 `CAMPAIGN_COMPLETE`，每套都有五个完整 boot pair，每个 pair 的 nVHE/protected 两侧都有 `BOOT_BLOCK_VALID`。`THP=always` 的 Pair 3 protected 首次执行在 Geekbench warmup 中死锁；该整腿位于 `results/d3000-apps-always-20260717-093223/invalid/`，正式 Pair 3 是隔离失败腿后重新执行得到的数据。分析器只扫描正式 `pair-[1-5]/{nvhe,protected}`，不会把 `invalid/` 混入结果。

`state/` 是归档时的同步快照，其中可能留有历史 pending 或 enabled marker。同步过程过去没有使用 `--delete`，因此这些文件不能单独作为“campaign 仍在运行”的依据。完成状态应以相应 campaign 的 `CAMPAIGN_COMPLETE`、十个 `BOOT_BLOCK_VALID`、现场日志和最终恢复记录共同判定。

## 3. Geekbench claim key 脱敏

凭据扫描在 247 个 Geekbench `stdout.txt` 或 `result-urls.txt` 中发现 `https://browser.geekbench.com/.../claim?key=<value>`。claim key 可用于领取在线结果，不属于性能数据，也不应进入可能推送到远端的 Git 历史。归档只把 query 参数值替换为固定字符串 `REDACTED`；结果 ID、无 key 的 canonical URL、程序输出、退出状态、wall time、元数据和所有性能结果均未改变。

脱敏后再次扫描，未发现未脱敏的 claim key；重跑两套完整 campaign 的分析后，生成的指标和报告与脱敏前逐字节一致。`MIGRATION_SOURCE_SHA256SUMS` 证明复制进仓库的文件在脱敏前与外部源一致，`ARCHIVE_SHA256SUMS` 则是当前可直接验证的提交版本。原始 key 值本身不会出现在任何已提交文件中。

`sync-results-local.sh` 在未来增量同步后也会执行相同的定点替换并重新生成 `ARCHIVE_SHA256SUMS`，避免远端现场文件再次把 claim key 带回仓库。

## 4. 未纳入 Git 的运行时缓存

原外部目录还包含 `build/`、`downloads/`、`src/`、`tools/` 和 `utils/`。它们是第三方源码展开树、编译中间物、可重建二进制和商业 Geekbench 分发包，不是实验输出；合计约 1.2 GiB，其中单个 Geekbench workload 为 316,571,967 bytes、原始安装包为 192,088,662 bytes，均超过普通 GitHub 单文件限制。为避免把第三方/商业二进制和构建缓存写入仓库历史，这些目录不提交，但没有删除：它们已物理迁移到本目录的 `runtime-cache/{build,downloads,src,tools,utils}`，由 `.gitignore` 排除。其精确文件数、字节数和整树摘要见 `RUNTIME_INPUTS.inventory.tsv`，关键下载物的 SHA-256 见 `RUNTIME_ARTIFACTS_SHA256SUMS`，实测版本输出仍保存在 `metadata/tool-versions.txt`，RabbitMQ image digest 保存在 `metadata/rabbitmq-image-digests.txt`。

整树摘要的输入是迁移前原目录：按字节序排序后的每个普通文件 `sha256sum` 行，随后附加按字节序排序的 `L path -> target` 符号链接行，再对合并文本计算 SHA-256。摘要保留了原目录名和链接目标，因此用于证明归档时缓存身份；实际 payload 位于 `runtime-cache/`，不属于 Git 提交。关键安装包可在本目录运行 `sha256sum --check RUNTIME_ARTIFACTS_SHA256SUMS` 复核。

原目录的 `work -> /kylin-lmbench-exp-work` 是一个失效符号链接；归档时本机不存在 `/kylin-lmbench-exp-work`，因而没有可迁移的工作集。正式结果目录中的原始文件均已迁入。

## 5. 完整性验证

在仓库根目录运行：

```bash
cd experiments/d3000-pkvm-apps
sha256sum --check ARCHIVE_SHA256SUMS
```

该命令应检查 33,765 个现场文件且全部显示 `OK`。为了避免终端输出过长，可使用：

```bash
cd experiments/d3000-pkvm-apps
sha256sum --check --quiet ARCHIVE_SHA256SUMS
```

正式结果还应满足：

```bash
test -f results/d3000-apps-never-20260714-100618/CAMPAIGN_COMPLETE
test -f results/d3000-apps-always-20260717-093223/CAMPAIGN_COMPLETE
find results/d3000-apps-never-20260714-100618 results/d3000-apps-always-20260717-093223 -name BOOT_BLOCK_VALID | wc -l
```

最后一条应输出 `20`。

## 6. 从仓库内数据重新分析

以下命令完全使用仓库内路径，不依赖已移除的 `/home/jose/kylin-lmbench-exp`：

```bash
CAMPAIGN=experiments/d3000-pkvm-apps/results/d3000-apps-never-20260714-100618

python3 experiments/d3000-pkvm-apps/analyze-results.py "$CAMPAIGN" --out analysis/d3000-apps-never-20260714-100618
python3 experiments/d3000-pkvm-apps/deep-analysis.py "$CAMPAIGN" analysis/d3000-apps-never-20260714-100618/metrics.csv --out analysis/d3000-apps-never-20260714-100618
python3 docs/mmap/scripts/plot-d3000-app-results.py analysis/d3000-apps-never-20260714-100618/metrics.csv --figure-dir docs/mmap/figures --prefix d3000-thp-never-full
python3 docs/mmap/scripts/plot-d3000-anchors.py "$CAMPAIGN" --figure-dir docs/mmap/figures --prefix d3000-thp-never-full
```

把 `CAMPAIGN` 和输出前缀换成 `d3000-apps-always-20260717-093223` 与 `d3000-thp-always-full`，即可独立重算 `THP=always`。两套 profile 必须分别完成 boot pairing 后再比较，不能把 repetition 或不同 profile 的 pair 混在一起。
