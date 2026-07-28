# D3000 综合实验异常与恢复记录

## 2026-07-20：THP=always Pair 3 protected Geekbench warmup 死锁

THP=always campaign `d3000-apps-always-20260717-093223` 的 leg 8（Pair 3 protected）在 2026-07-19 02:16:41 开始 Geekbench 非计分 warmup。输出在 02:20:49 停留于 `Multi-Core / Running File Compression`，到 2026-07-20 09:06 仍未继续，持续超过 30 小时。

检查时 `geekbench_aarch64` 的 8 个线程全部睡眠在 `futex_wait_queue`，进程 CPU 时间为 2 分 37 秒；间隔两秒复查时 CPU 时间和 `/proc/<pid>/io` 计数均未变化，也没有活动网络 socket。内核日志中没有对应的 OOM、崩溃或硬件错误。因此该进程被判定为死锁，而不是正常的慢速 benchmark 或结果上传等待。

本次异常发生在非计分 warmup。虽然同一 boot 中此前完成的 RabbitMQ 目录均有有效性标记，但该 boot 已经历超过 30 小时的异常空闲，继续从 Geekbench 后半段执行会破坏 boot-level 配对的时间连续性。因此恢复时保留并隔离整个 `pair-3/protected` 结果目录，不将其计入正式结果；保持 campaign leg 为 8，在同一 protected 模式下重新启动并从 boot block 起点重跑。

为防止同类问题再次无限占用机器，`run-geekbench.sh` 增加每次 suite 20 分钟超时和最多 3 次尝试。失败尝试单独保存在 `failed-<label>-attempt-XX`，不创建 `VALID`；只有完整成功的尝试才移动到正式 `warmup` 或 `rep-XX` 目录并进入分析。正常 suite 约 6～7 分钟，超时阈值不会截断正常样本。修改前脚本 SHA-256 为 `ea5b54db68b1f6665f3d426fd6cb3d5cc6044f47d0e3fd87ef1897e577faf94e`，修改后为 `501396f8aada0d0a649c2055f7d5a0fd62a103fa7571ee1b0422524fbc92fc6b`。
