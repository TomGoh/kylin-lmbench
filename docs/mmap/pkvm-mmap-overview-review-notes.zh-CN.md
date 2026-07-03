# pKVM mmap overview 文档审核记录

审核对象：`pkvm-mmap-overview.zh-CN.md` 第 9 章（Pixel 9 Pro XL 复测）新增 diff
审核日期：2026-07-02（初版 + 全流程逻辑复查）
审核状态：初版 4 个问题已处理；第二轮 3 个逻辑复查问题均已处理

---

## 第一轮审核（已处理）

### 问题 1：§9.2 覆盖表"前文章节"列的前向引用 → 已修复

### 问题 2：调查周期声明不完整 → 已修复

### 问题 3：§9.3 MADV_DONTNEED 匿名映射与文件映射可比性 → 已修复

### 问题 4：§9.5 munmap_only 与 op_sweep 数据来源差异 → 已修复

---

## 第二轮审核：全流程逻辑复查（2026-07-02）

逐段审查了 §9.1-§9.7 的实验设计、推断链、代码-文档一致性和替代解释，发现以下 3 个问题。复核后 3 项均合理，其中问题 5 的“+167 ns/页包含系统调用开销”表述在 overview 中按更精确口径处理：该值经过 touched−untouched 扣背景，重点是不能和 N80 连续 TLBI slot 斜率直接做数值等价。

---

### 问题 5 [重要]：§9.3 `single` 模式的实验设计与文档描述存在逻辑不一致——每次 `madvise` 是独立系统调用，而非"逐页 TLBI"

- **位置**：§9.3（约第 2300-2330 行），特别是 `single` 实验的描述
- **代码验证**：`pixel_madv_entry_slope.c` 第 318-322 行的 `single` 模式计时窗口为：
  ```c
  for (size_t i = 0; i < pages; i++) {
      rc = madvise(p + i * page_size, page_size, MADV_DONTNEED);
      if (rc != 0) break;
  }
  ```
  每次循环调用一次 `madvise()` 系统调用，每次只处理 4 KB。这意味着每次 `madvise` 进入内核后，该 4 KB 范围的 TLB 刷新走的是**单条目** `flush_tlb_page()` 路径（范围 = 4 KB < 2 MB，且只有 1 个 PTE 被清除），而不是 N 个 PTE 累积后的 `__flush_tlb_range_nosync` 批量路径。
- **文档描述**：§9.3 将 `single` 的作用描述为"人为放大'每页一次撤销'的成本"，将 +167 ns/页判读为"单页页面撤销下 protected 有稳定额外成本"。这个判读在定性方向上没错（单页撤销确实更贵），但文档没有指出一个关键的**路径差异**：`single` 模式测的是"每次 `madvise` 系统调用处理 1 页 → 1 次 `flush_tlb_page` → 1 条 TLBI"，而 Phytium 上的根因机制是"N 页在同一 `munmap` 内累积 → `__flush_tlb_range_nosync` 逐 4KB slot 发 TLBI"。两种路径的 TLBI 发射粒度不同：前者每条 TLBI 只需作废 1 个 4KB 条目，后者每条 TLBI 也只作废 1 个 4KB 条目但紧挨着连发 N 条——前者的 +167 ns/页包含了 N 次系统调用开销的分摊，后者的 +0.27 µs/slot 不含系统调用。
- **影响**：+167 ns/页与 N80 的 +0.27 µs/slot (=270 ns/slot) 量级接近，但两者度量的是不同层次的成本（前者含系统调用开销，后者是裸 TLBI 指令）。文档将两者直接类比可能产生误导。不过，由于 §9.3 的核心论点只依赖"single 有正信号、batched 无正信号"的方向性对比，而非绝对数值的跨平台比较，**这个路径差异不影响最终结论的正确性**。
- **建议**：在 §9.3 的 `single` 实验描述中明确说明：(1) 每次 `madvise` 是独立系统调用，内核对单 4KB 页走 `flush_tlb_page` 而非批量 `__flush_tlb_range_nosync`；(2) +167 ns/页包含系统调用开销，不能直接与 N80 的 +0.27 µs/slot（裸 TLBI）做数值比较；(3) 本探针的判读逻辑是 single vs batched 的方向性对比，不依赖跨平台绝对值。
- **处理结果**：已采纳并校正表述。§9.3 已补充 `single` 是 N 次独立 `madvise(page, 4 KB, MADV_DONTNEED)`，不是一次系统调用内的连续 N 个 4 KB flush slot；同时说明 +167 ns/页经过 touched−untouched 扣背景，但仍不能与 N80 的 +0.27 µs/slot 直接数值比较，判读只依赖 single vs batched 的方向性对照。

### 问题 6 [重要]：§9.4 `munmap_after_write_touch` 小尺寸数据呈现 protected 更慢的趋势，文档未充分讨论

- **位置**：§9.4（约第 2350-2365 行），`munmap_after_write_touch` 按尺寸展开表
- **数据**：
  | size MB | protected−NVHE | ratio |
  |---|---|---|
  | 0.5 | +2.295 µs | 1.847 |
  | 1 | +1.459 µs | 1.340 |
  | 2 | -0.775 µs | 0.905 |
  | 4 | -0.679 µs | 0.936 |
  | 8 | +0.396 µs | 1.029 |
  | 16 | -2.633 µs | 0.856 |
  | 64 | +0.341 µs | 1.008 |

  0.5 MB 和 1 MB 行 protected 比 NVHE 慢 +2.3 和 +1.5 µs，ratio 分别为 1.85 和 1.34。文档在 §9.4 中集中讨论了 64 MB 行"几乎相等"的结论，但对 0.5-1 MB 的正差距只字未提。
- **可能的解释**：在 Phytium 上，小尺寸 munmap 的逐页 TLBI 退化也呈正比例（§7.5.4 的 Kaitian 表中 0.5 MB 为 +1.433 µs、1 MB 为 +2.907 µs）。Pixel 0.5-1 MB 的小正差距是否也是同类信号的残余？还是仅属统计噪声（5 次取中位数、温度波动等）？
- **影响**：文档的结论是"真实 `mmap` 路径没有复现 Phytium 的大幅变慢"，但 0.5 MB ratio=1.85 并不小。如果 Pixel 小尺寸确实有信号，那结论应精确化为"大尺寸（≥2 MB）真实路径没有复现"而非笼统的"真实路径"。不过，查看 overview-early-diff.csv 的原始数据，0.5 MB `munmap_after_write_touch` 的 protected_median=5.006、nvhe_median=2.710，绝对值本身只有几微秒，NVHE 基线极低（2.7 µs），导致 ratio 被放大——1.85 的 ratio 对应仅 +2.3 µs 的绝对差，与 Phytium 上 0.5 MB 的 +1.433 µs（ratio=1.47，Kaitian）方向一致但绝对值极小，且从 2 MB 开始差距消失。
- **建议**：在 §9.4 的 `munmap_after_write_touch` 展开表后，补充一段讨论：(1) 0.5-1 MB 有小正差距（+1.5~2.3 µs），ratio 被低基线放大；(2) 从 2 MB 开始差距消失（甚至反向），与 Phytium 上"差距随尺寸线性增长"的模式完全不同；(3) 因此小尺寸正差距不构成 Phytium 机制复现的证据，因为它没有 Phytium 的关键特征——随尺寸增长的线性趋势。
- **处理结果**：已采纳。§9.4 已在图 9-3 后补充小尺寸正差距说明，明确 ratio 被低基线放大，且从 2 MB 起不呈现 Phytium 的线性增长形态。

### 问题 7 [中等]：§9.6 对"最合理的解释"的论证不够严密，遗漏了一个替代解释

- **位置**：§9.6（约第 2460-2463 行）
- **现状**：§9.6 写"Tensor G4 / Pixel 的真实多页拆除路径很可能通过批量或范围式 TLB 维护把单页成本隐藏了"，并在 §9.7 承认"在没有 Pixel 内核侧 TLBI 直接计时、硬件特性确认或源码级路径确认前，本文只把它写成'与批量或范围式处理相容'，不把它写成已证明"。
- **遗漏的替代解释**：文档只考虑了"FEAT_TLBIRANGE 或批量路径摊掉了成本"这一类解释，但还有另一个完全不同的替代解释：**Tensor G4 的 TLB 微架构实现中，带 VMID 的合成条目失效成本本身就比 FTC862 低得多**。在 N80 上，protected IS ≈ 289 ns/slot vs nvhe IS ≈ 23 ns/slot，差 12 倍；如果 Pixel 的 TLB 硬件设计中，合成条目和 stage-1-only 条目的失效成本差异很小（比如只差 2-3 倍），那么即使 Pixel 也不支持 FEAT_TLBIRANGE、也走逐页 TLBI 路径，其 protected 额外成本也会小到被 5 次中位数的统计噪声淹没。
- **现有证据对替代解释的约束**：§9.3 的 single 探针测到 +167 ns/页。如果 Pixel 的 TLBI 合成条目额外成本极低，那 +167 ns/页从何而来？一种可能是：+167 ns/页中系统调用开销占主导（参见问题 5），而纯 TLBI 额外成本其实很小。但 §9.3 的 simpleperf 显示 `stalled-cycles-backend` 增加了 +81.6M，这更像是 TLB/缓存行为而非系统调用开销。因此，"Tensor G4 合成条目失效成本低"这个替代解释不能完全排除，但也不完全吻合现有数据。
- **建议**：在 §9.6 的"最合理的解释"段落中，补充提及这个替代解释，并说明现有数据（single +167 ns/页 + simpleperf 后端停顿增加）对它的约束：它不能完全排除，但与后端停顿增加的证据存在一定张力，因此仍以"批量/范围式处理"为主要解释，以"TLB 微架构差异"为并列替代。
- **处理结果**：已采纳。§9.6 已新增“仍未排除的替代解释”条目，把 Tensor G4 TLB 微架构差异列为并列替代解释，同时说明 single 探针和 simpleperf 对该解释的约束。

---

## 数据交叉验证结果（全部通过）

以下 diff 中引用的关键数据均已与源 CSV 文件逐项核对：

| 数据项 | 源文件 | 结果 |
|---|---|---|
| MADV_DONTNEED single 每页增量 +167.039 ns/op, 95% CI [140.098, 193.981], 分辨率 31.382 | `pixel9proxl-.../summary/single-summary.csv` | 一致 |
| MADV_DONTNEED batched 每页增量 -13.926 ns/op, 95% CI [-24.127, -3.725], 分辨率 10.201 | `pixel9proxl-.../summary/batched-summary.csv` | 一致 |
| simpleperf page-faults 123201/123206, cpu-cycles 568500838/657753337, stalled-cycles-backend 362981067/444603460 | `pixel9proxl-.../summary/simpleperf-single-touched-4096.csv` | 一致 |
| lat_mmap_precise 多尺寸数据（0.5-64 MB） | `overview-early-5run/summary/overview-early-diff.csv` | 一致 |
| munmap_after_write_touch 多尺寸数据 | 同上 | 一致 |
| munmap_only / op_sweep 阈值扫描数据 | `pixel9proxl-...-ported/summary/ported-suite-diff.csv` | 一致 |

## 代码-文档一致性验证

| 验证项 | 代码/脚本 | 文档描述 | 一致性 |
|---|---|---|---|
| `pixel_madv_entry_slope.c` 使用 `MAP_PRIVATE \| MAP_ANONYMOUS` | 第 299-300 行 | §9.3 已补充说明匿名映射 | 一致 |
| `pixel_madv_entry_slope.c` 默认调用 `MADV_NOHUGEPAGE` | 第 54/306 行 | §9.1 "同一批二进制"+"频率不做事后筛除" | 一致 |
| `pixel_madv_entry_slope.c` `single` 模式对每页单独调用 `madvise` | 第 318-322 行 | §9.3 "对每页分别调用一次 madvise" | 一致 |
| `op_sweep.c` 文件映射使用 `MAP_SHARED` + fd | 第 124 行 | §9.5 "ported suite ... munmap_only 阈值扫描" | 一致 |
| `pixel-run-madv-entry-slope.sh` 随机化任务顺序 + cooldown + reject | 多处 | §9.1 "频率、温度和返回码保留为可审计字段" | 一致 |
| `isar0.c` 明确标注 `FTR_HIDDEN`——用户态 `MRS` 不可靠读取 TLBIRANGE 字段 | 全文注释 | §9.7 "确认 Tensor G4 是否暴露并启用 FEAT_TLBIRANGE" | 一致（文档未声称已确认，正好呼应了代码注释的警告） |

## §9.1 模式切换逻辑验证

文档描述的 Pixel protected/NVHE 切换机制（修改 `vendor_kernel_boot_b` DTB bootargs，利用 cmdline 后出现的 `kvm-arm.mode` 覆盖前面的值）在逻辑上是自洽的。A/B 对照的严谨性体现在：
- 同一 kernel image、同一用户态二进制、同一参数矩阵
- 每次切换后有 `komodo-verify.sh` 校验 live mode
- 最终恢复有 byte-perfect sha256 校验
- 温度门限 39°C 在每次任务前 gate

未发现逻辑漏洞。

## §9.5 N80 对比数据验证

文档中引用的 N80 阈值扫描数据（1.9 MB +130.2 µs、2.0 MB +0.4 µs、6.4 MB/16KB +436.6 µs、64 MB/4KB +73.8 µs）来自 `experiments/munmap-tlbi/results/op-sweep-n80/{protected,nvhe}.txt`，与前文 §7.5.3 的数据一致。跨平台对比使用同一计时窗口（只覆盖 munmap），口径一致。
