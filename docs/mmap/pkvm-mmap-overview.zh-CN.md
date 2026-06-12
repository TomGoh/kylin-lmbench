# pKVM host mmap 退化调研总览：从 4-config 症状到逐页 TLBI 根因

**一句话**：pKVM(protected) 给 host 内存加了 **host stage-2** 第二级翻译。它让 host 的 `lat_mmap`
（mmap→写触摸→munmap 的完整生命周期）在大尺寸下慢 **+42%~+85%**，但稳态内存访问(`lat_mem_rd`/`bw_mem`)
**几乎不受影响**。逐层定位后，退化的**全部来源**锁定为：**munmap teardown 时内核对中小范围发的逐页 `TLBI`，
而每条 host TLBI 在 host stage-2 下更贵**（无 FEAT_TLBIRANGE 时尤甚）。

> 本篇是贯穿全程的**总览**，每步给"背景→设计→代码→结果→与下一步的关系"，并标出对应的详细文档。
> 全链经历了**两次机制修正**（first-touch 建表 → munmap teardown；嵌套 walk(a-2) → 逐页 TLBI(a-1)），
> 本篇如实保留这条"理解收敛"的过程。

## 全景图（逻辑链）

```
步骤1 症状     4-config Host：lat_mmap pKVM 慢+85%，但稳态访问无差异
                → 开销在 mmap "生命周期"里，不在"稳态访问"。元凶是 host stage-2。
                  早期猜想：first-touch 每页 stage-2 abort 建表 ~500ns/fault。
   │
步骤2 细化     mmap-split：把 lat_mmap 拆成 12 个子阶段，逐一隔离
                → write_touch_cold 仅 +3.78% ⇒【修正①】first-touch 不是主因；
                  munmap_after_write_touch +227% ⇒ 退化在"写触摸后的 munmap teardown"。
   │
步骤3 判别     gate：munmap teardown 的额外时间是否进 EL2？
                → ΔEL2=0（计数器经阳性对照验证）⇒ 不进 EL2 ⇒ 走 host 侧分析(C1)。
   │
步骤4 定层     C0(perf)：退化在 host 的哪一层？
                → 指令/缺页/walk 次数两模式相同，只是 +40.9M backend(访存)停顿。
                  剩两个候选：a-1(每条 TLBI 更贵) / a-2(每次 walk 更贵)。
   │
步骤5 定因     op=3 自省 + 密集对照 + 源码 + 阈值扫描
                → 自省排除碎片化；密集 munmap gap≈0【修正②：证伪 a-2】；
                  源码定位 2MB full-flush 阈值；阈值扫描见 2MB 断崖、gap∝TLBI 条数
                  ⇒ 根因 = a-1 逐页 TLBI 的 stage-2 硬件税（每条多 ~0.27µs）。
   │
步骤6 收口     杠杆 = FEAT_TLBIRANGE（把逐页 N 条压成一段几条）；大 munmap 已自动整表 flush 无税。
```

平台跨了三块板子（N90→Kaitian→N80，均 Phytium/Kylin V10 aarch64），现象一致、量级随板子不同，结论可迁移。

---

## 步骤 1 — 症状：4-config Host 侧 lat_mmap 对照
**详见** [n90-v10-mmap-host-report.md](n90-v10-mmap-host-report.md)、[pkvm-mmap-overhead-analysis.md](pkvm-mmap-overhead-analysis.md)

### 背景 / 设计
为隔离"是不是 pKVM 的锅"，在**同一块板子同一内核**上以四种 KVM 模式分别启动，跑同一套 host 侧 lmbench：
- `kvm-arm.mode=none`(KVM-off) / VHE / NVHE / **protected(pKVM)**。
- 平台：N90(Phytium FTC862) / Kylin V10 SP1 / `6.6.30+` / 全核锁 2.1 GHz。

### 结果（lat_mmap_precise，64MB，N=10 median）

| 模式 | 64MB lat_mmap | vs 非 pKVM |
|---|---:|---|
| KVM-off | 443.084 µs | 基线 |
| VHE | 441.221 µs | 基线 |
| NVHE | 441.187 µs | 基线 |
| **pKVM** | **816.318 µs** | **+85.0%** |

三个非 pKVM 基线彼此差 <0.25%；pKVM 一枝独秀。size 越大退化越深：**+29%(0.5MB) → +85%(64MB)**。
**关键反差**——稳态内存访问几乎无差异：

| 指标 | 非 pKVM | pKVM | 反差 |
|---|---|---|---|
| `lat_mmap` 64MB | ~441 µs | 816 µs | **+85%** |
| `lat_mem_rd`(DRAM 64MB) | ~10.3 ns/访问 | 10.34 ns | ≤±3.5% |
| `bw_mem` 峰值带宽 | ~48.6 GB/s | 48.6 GB/s | <±0.4% |

> **C pKVM 内核复测 814.996 µs，与 Rust pKVM 仅差 −0.16%** → 排除"Rust 实现导致的异常"，是 pKVM 路径本身的代价。

### 这一步说明了什么 / 与下一步的关系
- 退化只发生在 **mmap 的"生命周期"操作**（建/触/拆），**不在稳态访问**。元凶指向 pKVM 独有的 **host stage-2**
  （host 内存受第二级翻译保护；VHE host 跑在 EL2 无 host stage-2、NVHE 非 protected 不维护 host stage-2、KVM-off 无 EL2，所以都不付这个钱）。
- **早期机制猜想**：开销在"建表瞬间"——host 首次访问新页触发 stage-2 abort 陷 EL2、`host_stage2_idmap` 建表，
  实测每 fault 摊销 **505±10 ns**（1MB~64MB 极稳）。这把矛头指向 **first-touch 建表**。
  → 但"哪一段最贵"还没拆开，于是有了步骤 2。

---

## 步骤 2 — 细化：mmap-split 把 lat_mmap 拆成 12 段，定位到 munmap teardown
**详见** [lat-mmap-test-walkthrough.zh-CN.md](lat-mmap-test-walkthrough.zh-CN.md)、[mmap-split-kaitian-pkvm-comparison.zh-CN.md](mmap-split-kaitian-pkvm-comparison.zh-CN.md)

### 背景：lat_mmap 到底测什么
`lat_mmap.c` 的计时区是**整段生命周期**（`src/lat_mmap.c:154-177`，`domapping()`）：
```c
while (iterations-- > 0) {
    where = mmap(0, size, PROT_READ|PROT_WRITE, MAP_FILE|MAP_SHARED, fd, 0);  // ① 建映射
    end = where + (size / N);                                                 // 默认触前 1/N(~size/10)
    for (p = where; p < end; p += PSIZE) *p = c;                              // ② 写触摸(步长 PSIZE=16KB)
    munmap(where, size);                                                      // ③ 拆映射
}
```
**所以 816µs 是"建 + 触 + 拆"三段之和**——光看 lat_mmap 不知道贵在哪一段。（注意 ②：触前 ~1/10、步长 16KB，
这正是后来 `mmap_split_bench` 的 `touch_divisor=10 stride=16K` 的由来——刻意复刻 lat_mmap。）

### 设计：拆成 12 个子测试，每个只隔离一段
代表性子测试（计时区 = 加粗那段）：

| 子测试 | 隔离 | 计时区 |
|---|---|---|
| `mmap_unmap` | 未触摸映射的建/拆 | **mmap → munmap**（无触摸） |
| `write_touch_cold` | 首次写触摸本身 | mmap → **write_touch** （mmap/munmap 不计时） |
| `munmap_after_no_touch` | 未触摸映射的 munmap | mmap →（无触摸）→ **munmap** |
| **`munmap_after_write_touch`** | **写触摸后的 munmap** | mmap → write_touch →（计时）**munmap** |
| `mmap_write_touch_unmap` | 完整写路径（≈原 lat_mmap） | **mmap → write_touch → munmap** 全段 |

### 结果（Kaitian，NVHE vs pKVM，64MB，单位 µs）

| 子测试 | NVHE | pKVM | Δ | Δ% | 含义 |
|---|---:|---:|---:|---:|---|
| `mmap_unmap` | — | — | ≈0 | ±1% | VMA 建/拆不是问题 |
| `write_touch_cold` | 333.5 | 346.2 | **+12.6** | **+3.78%** | **first-touch 不是主因** |
| `munmap_after_no_touch` | 1.52 | 1.52 | ≈0 | ±0.35% | 未触摸映射的 munmap 不慢 |
| **`munmap_after_write_touch`** | **90.2** | **295.2** | **+205.0** | **+227%** | **⭐ 瓶颈** |
| `mmap_write_touch_unmap`(完整) | 428.1 | 642.4 | +214.3 | +50% | — |

### 这一步说明了什么 / 与下一步的关系
- **【机制修正①】**：`write_touch_cold` 只 +3.78% → **first-touch/建表不是主因**，早期"~500ns/fault"模型被否定为主解释。
- `munmap_after_write_touch` +205µs ≈ 完整写路径 +214µs 的 **95.7%** → 退化**几乎全部**由"**写触摸后的 munmap teardown**"解释。
- 但这带出一个悖论：host 的 munmap **理论上不进 EL2**（host TLBI 不被 trap、不发 hypercall）。那 +205µs 从哪来？
  → 必须先判别"这笔钱是否花在 EL2 里"，于是有了步骤 3（gate）。

---

## 步骤 3 — 判别：gate 证明 munmap teardown 不进 EL2
**详见** [n80-gate-c0-results.zh-CN.md](n80-gate-c0-results.zh-CN.md) §1–§5（含 EL2 PMU 原理与代码）

### 背景 / 设计
退化在 munmap，但 host munmap 理论上不进 EL2——是真不进，还是有隐藏 EL2 路径（如页表池耗尽回收→abort 风暴）？
用 **EL2-only PMU 周期计数**判别：把 cycle counter 的过滤器配成"只在 EL2 执行时递增"，则窗口前后差 = 该窗口进 EL2 的总周期。

```rust
// stats.rs::xcore_enable_pmu_el2()：PMCCFILTR 配成只数 EL2 周期
PMCCFILTR_EL0 = bit31|bit30|bit27|bit26;   // 屏蔽 EL1/EL0 计数、放行 EL2(NSH)
MDCR_EL2 |= bit7(HPME);                     // 使能 EL2 PMU
```
gate 脚本对每个 size 做"读 baseline → 跑被测项 → 读 delta"，再用等时长空窗扣背景噪声。
判读尺子：把"protected 比 nvhe 多花的 µs × CPU GHz" = 这笔时间**若全花在 EL2** 的 cycle 上限。

### 结果（N80，protected）
- **阳性对照**（先证明计数器没坏）：连打 200 次 op=2 页表遍历 HVC（确定进 EL2）→ **ΔEL2 = 1.68 亿 cycle**，计数器精确累加。
- `munmap_after_write_touch` / `write_touch_cold` / `mmap_write_touch_unmap` 的 **ΔEL2 = 0**（上限是 ~80 万 cycle/iter，实测 0 ≪ 5%）。

### 这一步说明了什么 / 与下一步的关系
- **退化不在 EL2**（不是隐藏 EL2 路径），路线定为 **C1（host 侧硬件成本）**，并省掉了"在 hyp 里大规模插桩(C2)"那条注定读 0 的路。
- 既然在 host 侧，那是 host 的哪一层硬件成本？→ 步骤 4（C0）。

---

## 步骤 4 — 定层：C0(perf) 把退化定位到 backend 访存停顿
**详见** [n80-gate-c0-results.zh-CN.md](n80-gate-c0-results.zh-CN.md) §4.3 / §6.4 / §7

### 背景 / 设计
用 host PMU 拆解 munmap 的成本结构。事件不是随手列的，每个对应一个要确认/排除的猜想：
```bash
perf stat -e cycles,instructions,page-faults,l1d_tlb_refill,l2d_tlb_refill,r34,stall_backend -- ...
```
`cycles+instructions`→IPC 与"是不是同样的活"；`page-faults`→同负载锚点；`r34`(DTLB_WALK)→stage-1 walk 次数(验 a-2)；
`*_tlb_refill`→TLB 重填(TLBI 活动旁证)；`stall_backend`→把"慢"定位到访存等待。

### 结果（N80，protected vs nvhe，munmap_after_write_touch 64MB×50）

| 指标 | nvhe | protected | 差 |
|---|---:|---:|---:|
| cycles | 49.0M | 88.8M | **+39.8M (1.81×)** |
| instructions / page-faults / dtlb_walk(r34) | — | — | **两模式完全相同** |
| **stall_backend** | 18.2M | 59.1M | **+40.9M** |

### 这一步说明了什么 / 与下一步的关系
- 同样的指令、同样的缺页、**同样次数的 stage-1 walk**，额外的 +39.8M cycles **几乎全部是 +40.9M backend 停顿** →
  退化是"硬件访存/等待变慢"，不是"软件多做事"，也不是"多进 EL2"。
- 在"host stage-2 硬件成本"内还剩两个候选机制：**a-1（每条 TLBI 更贵）** vs **a-2（每次 walk 更贵）**。
  perf 都能先验解释，分不开 → 步骤 5 专门把这两个分开。

---

## 步骤 5 — 定因：op=3 + 密集对照 + 源码 + 阈值扫描 → a-1 逐页 TLBI
**详见** [c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md)（完整推理链）、[c1-host-stage2-granularity.zh-CN.md](c1-host-stage2-granularity.zh-CN.md)（op=3，含已更正的 a-2 误判）

### ① op=3 自省：排除"碎片化"
host stage-2 是 hyp 私有、host/perf/ftrace 都读不到，故新增只读 hcall **op=3** 遍历 `host_mmu.pgt`，
按粒度分桶统计 → host RAM **99.5% 是 1G block**（仅 31MB 是 4K）。
- 排除了"host 内存被拆成 4K 导致深 walk"(H1)。**但这只排除碎片化，并不能在 a-1/a-2 间判别**；
  且"大块 → walk 便宜"恰恰是**反对 a-2** 的证据（早先在这里把它误读成"a-2 固有税"——见 c1 文档的更正横幅）。

### ② 密集对照：证伪 a-2【机制修正②】
mmap 64MB → **写触摸每一页(全摸)** → 只给 munmap 计时。全摸的用意：**把 walk 工作量拉满压测 a-2**。
若 a-2 成立，PTE 多 40 倍、gap 应最大。实测：

| | nvhe | protected | gap |
|---|---:|---:|---:|
| 密集 munmap（16384 PTE） | 2828 µs | 2785 µs | **≈0** |

→ **walk 拉满也不出税 ⇒ 不是 a-2。** （而这与 a-1 自洽：全摸后范围≥2MB，走整表 flush、无逐页 TLBI。）

### ③ 源码：内核对范围的 TLBI 有个 2MB 阈值
`arch/arm64/include/asm/tlbflush.h`：munmap 的 TLB 作废按范围二选一——
```c
// __flush_tlb_range_nosync:422 —— 范围 ≥ 2MB(无 FEAT_TLBIRANGE 时)走整表
if (!system_supports_tlb_range() && (end-start) >= MAX_DVM_OPS*stride /*512×4K=2MB*/) {
    flush_tlb_mm(vma->vm_mm);   // flush_tlb_mm:253 —— 整个 ASID 只 1 条 `tlbi aside1is`
    return;
}
// 否则 __flush_tlb_range_op:369 —— 逐页：每页一条 `tlbi vae1is`
while (pages > 0) { __tlbi_level(vae1is, addr, ...); start += stride; pages -= 1; }
```
N80 **无 FEAT_TLBIRANGE** → <2MB 逐页 N 条 TLBI；≥2MB 单条整表。给出可证伪预言：逐页区有税∝N，整表区无税。

### ④ 阈值扫描：证实 a-1
连续密集触前 N MB（flush 范围≈N MB，由 N 干净控制），跨 2MB 取点，两模式比 munmap-only：

| 触摸范围 | protected | nvhe | gap |
|---|---:|---:|---:|
| 1.0 MB | 120.9 | 52.5 | +68.4 |
| **1.9 MB** | 227.5 | 95.0 | **+132.5 (+139%)** |
| **2.0 MB** | 93.4 | 88.6 | **+4.8 (+5%)** ← 断崖 |
| 64 MB | 2876.3 | 2734.1 | +142 (+5%) |
| 稀疏 6.4MB/16K(原 benchmark) | 546.7 | 108.6 | **+438 (+403%)** |

**三个铁证**：① **断崖**——gap 恰在 2MB(逐页→整表切换点)塌掉（walk 机制不会在此反向塌）；
② **线性**——<2MB 的 gap ∝ 范围(∝TLBI 条数)，斜率 → **每条 host TLBI 多 ~0.27µs(~490 cycles)**；
③ **闭环**——稀疏 6.4MB=1638 页槽×0.27µs≈442µs ≈ 实测 +438µs ≈ **C0/Kaitian 的 +205~435µs 量级**，来源闭合。

### 这一步说明了什么 / 与下一步的关系
- **根因 = a-1：munmap teardown 对中小范围逐页发 `TLBI`，而每条 host TLBI 在 host stage-2 下更贵**
  （TLB 里是 combined(stage1×stage2)+VMID 条目，作废与 DVM 广播更重，末尾 `dsb ish` 等更久 → backend 停顿；
  这与步骤 4 perf 的"walk 不变、stall_backend 增加"完全吻合）。
- → 杠杆随之清楚（步骤 6）。

---

## 步骤 6 — 收口：杠杆与适用范围

- **核心杠杆 = FEAT_TLBIRANGE**：有此特性的 CPU 用 range TLBI（`__tlbi(r##op)`）把"逐页 N 条"压成"一段几条"，
  TLBI 条数骤降 → 退化大幅缩小。**N80 没有此特性**，所以退化明显——**退化是平台相关的**，新硬件上会轻很多。
- **大 munmap 已自动 coalesce 成单条整表 flush、本就无税**；退化只发生在 **<2MB 的中小 munmap**（lat_mmap 这类微基准、频繁小映射的负载命中）。
- **纯 pKVM 侧空间有限**：每条 host TLBI 的 stage-2 成本是硬件层面的，host TLBI 不被 trap，hyp 既挡不住也加速不了；
  唯一软件方向是"少发几条 TLBI"。
- **"提高 host stage-2 粒度"对本退化无效**：粒度已最大化(1G block)，且瓶颈在 TLBI 不在 walk。

## 全链结论（闭环）

```
host stage-2(pKVM 隔离)  →  lat_mmap 生命周期慢、稳态访问不慢（步骤1）
                         →  慢在写触摸后的 munmap teardown（步骤2，修正掉 first-touch）
                         →  teardown 不进 EL2，在 host 侧硬件（步骤3）
                         →  是 backend 访存停顿，非多做软件/多 walk（步骤4）
                         →  是逐页 TLBI 在 stage-2 下每条更贵（步骤5，修正掉嵌套 walk）
                         →  杠杆 = FEAT_TLBIRANGE / coalesce（步骤6）
```

每一环都有"数据 + 代码 + 机制"三方互证，且两处早期误判（first-touch、嵌套 walk）都用更细的对照实验如实修正并留痕。

## 索引（详细文档）
| 步骤 | 文档 |
|---|---|
| 1 症状 | `n90-v10-mmap-host-report.md`、`pkvm-mmap-overhead-analysis.md` |
| 2 拆分 | `lat-mmap-test-walkthrough.zh-CN.md`、`mmap-split-kaitian-pkvm-comparison.zh-CN.md` |
| 3 gate / 4 C0 | `n80-gate-c0-results.zh-CN.md` |
| 5 op=3 自省 | `c1-host-stage2-granularity.zh-CN.md`（含 a-2→a-1 更正） |
| 5 机制判定 | `c1-tlbi-threshold.zh-CN.md`（完整推理链 + 代码 + 曲线分解） |
| 方案/脚本 | `agile-popping-anchor.md`、`el2-gate-instrumentation.zh-CN.md`、`scripts/` |
