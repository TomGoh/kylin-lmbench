# munmap TLBI 微基准

这个小项目是 pKVM mmap 调研 **C1 阶段（机制判定）** 用到的 host 侧测试工具，用来把
"写触摸后的 munmap teardown 退化"定位到根因：**munmap 对中小范围逐页发的 `TLBI`，
而每条 host TLBI 在 host stage-2(pKVM) 下更贵**。

完整背景、设计与结论见仓库文档：
- 总览：[`docs/mmap/pkvm-mmap-overview.zh-CN.md`](../../docs/mmap/pkvm-mmap-overview.zh-CN.md)
- 机制判定（含本目录工具产出的全部数据与曲线分解）：[`docs/mmap/c1-tlbi-threshold.zh-CN.md`](../../docs/mmap/c1-tlbi-threshold.zh-CN.md)

## 工具

| 文件 | 作用 | 计时口径 |
|---|---|---|
| **`munmap_only.c`** | **主工具**：只给 munmap 计时，可控触摸范围与 stride → TLBI 阈值扫描 | mmap+触摸是 untimed setup，只计 `munmap()` |
| `munmap_bench.c` | file / anon_base / anon_huge 三种 backing 的 teardown 对照（看大页效应） | 计**整段** mmap+touch+munmap（注意：会淹没 munmap 的 TLBI 税，仅作页大小对照） |
| `s1pagesize.c` | 读 `/proc/self/smaps`，确认某 file 映射在 host **stage-1** 是 4K 还是大页 | — |

`munmap_only` 用法：
```text
munmap_only <file|anon_base|anon_huge> <mb> <iters> [path] [touch_mb] [stride_kb]
  touch_mb : 只触摸前 touch_mb MB（默认=mb；用它控制 munmap 的 flush 范围）
  stride_kb: 触摸步长 KB（默认 4=密集；16=稀疏，复刻原 lat_mmap / mmap_split）
```

## 构建与运行

```bash
make                      # 编出 munmap_only / munmap_bench / s1pagesize
./run-sweep.sh            # 阈值扫描（分别以 protected / nvhe 启动各跑一次，对比 gap）
```

`run-sweep.sh` 连续密集触摸前 N MB、范围跨内核的 **2MB full-flush 阈值**
（`MAX_DVM_OPS=512×4K`，见 `arch/arm64/include/asm/tlbflush.h`）。预期：
- **<2MB**（逐页 TLBI）：`gap = protected − nvhe` 随范围线性增长（∝TLBI 条数）；
- **≥2MB**（单条整表 flush）：gap 在 2MB 处**断崖**塌到 ~0。

斜率给出"每条 host TLBI 在 pKVM 下多花的成本"（实测 N80 ≈ 0.27 µs/条）。

## 关联脚本

EL2 gate 与 host 侧对照（C0）所用脚本在仓库 `scripts/`：
`el2-gate-bench.sh`、`host-mm-trace.sh`、`trace_hyp.sh`。
