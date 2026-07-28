# D3000 nVHE / pKVM 真实负载实验

本目录是 D3000 实验的可执行定义。正式自变量只有同一 `6.6.30+` 内核的
`kvm-arm.mode=nvhe` 与 `kvm-arm.mode=protected`；默认 VHE 只用于准备、screening
和最终恢复。

实验动机、项目选型、D3000 实机环境、所有场景的精确参数、数据目录、统计口径和已知
局限，统一记录在
[`docs/mmap/d3000-pkvm-real-workload-experiment.zh-CN.md`](../../docs/mmap/d3000-pkvm-real-workload-experiment.zh-CN.md)。
本文只保留执行入口和关键约束。

主要约束：

- 服务端固定在 CPU 0-3，客户端固定在 CPU 4-7；这是单机 cross-cluster 测试。
- 每个场景每个 boot 做 5 次有效重复；正式顺序为 NP、PN、NP、PN、NP 五个 boot pair。
- 先执行所有项目均为 THP=never 的完整 campaign，再执行所有项目均为 THP=always 的
  完整 campaign；每套都独立校准并包含 5 个 boot pair。
- 正式跑分只采轻量服务指标。`perf stat` 和 trace 是独立的诊断复跑，不混入主分数。
- 大工作集位于 `/kylin-lmbench-exp-work`；脚本和结果位于 `/home/jose/kylin-lmbench-exp`。
- 任一模式判定、磁盘余量、CPU governor、swap 或进程退出状态不合格时停止，不自动跨过错误。

操作入口：

```bash
# 初次安装构建
bash scripts/bootstrap.sh
bash scripts/install-grub-entries.sh

# 状态、短 smoke、正式活动由 campaign.sh 管理
bash scripts/campaign.sh status
bash scripts/campaign.sh smoke
bash scripts/campaign.sh preflight never
bash scripts/campaign.sh start never

# 全-never 正常结束并回到 VHE 后，guarded chain 自动执行：
bash scripts/campaign.sh preflight always
bash scripts/campaign.sh start always
```

`campaign-enabled` 标记存在时，systemd 服务会在每次指定模式启动后接续当前腿；每腿
成功后才写入下一状态并用 `grub-reboot` 选择一次性启动项。失败时机器保留在当前模式，
不会继续重启。最后一腿会删除标记并回到默认 VHE。

Geekbench Preview 版只在 stdout 中返回在线结果链接。同步结果后先生成网页清单：

```bash
python3 scripts/geekbench-pages.py \
  results/<campaign-id>
```

清单 `geekbench-page-manifest.csv` 的 `url` 是要保存的结果页，`save_as` 给出不会串号的
目标文件名（`geekbench-pages/<result-id>.html`）。保存完成后再次运行同一命令会校验 HTML、
计算 SHA256，并在每个 repetition 中生成 `scores.json`；正式分析前加 `--strict` 可要求
所有页面均已导入。Cloudflare 验证页不含分数，会被明确报为 `parse-error`，不会当作有效结果。

长实验使用 `d3000-thp-always-chain.service` 接续第二套 campaign。它只在 pending 标记
指定的全-never campaign 已完成第 12 腿、写出 `CAMPAIGN_COMPLETE`、清除
`campaign-enabled` 且机器通过 VHE 硬判据后，才执行 `campaign.sh start always`。两套
campaign 使用同一份由 smoke marker 锁定 SHA256 的 runner，不在中途替换脚本。第一套
失败或人工停止时不会接着跑；第二套完成后会清除 pending 标记并禁用两个 campaign 服务。
