# C1 机制判定：pKVM munmap 退化 = 逐页 TLBI 的 stage-2 硬件税（a-1）

**平台**：N80 / Kylin V10 SP1 / aarch64 / `6.6.30xcore-stat+`（Rust nVHE hyp，1.8 GHz，无 FEAT_TLBIRANGE）
**日期**：2026-06-12
**结论一句话**：pKVM 下 host `munmap` 的退化，来自内核**对中小范围逐页发 `TLBI`**，而**每条 host TLBI 在 host stage-2 使能后更贵**；当范围 ≥2MB、内核改用单条整表 flush 时，退化**当场消失**。这是文档假设 **a-1（TLBI/DSB 硬件成本）**，**不是** a-2（嵌套页表 walk）。

> **重要更正**：本系列早先的 [c1-host-stage2-granularity.zh-CN.md](c1-host-stage2-granularity.zh-CN.md) 曾把机制判为 a-2（嵌套 walk 的"固有税"）。**那个机制结论是错的**（其 op=3 原始数据没错，是解释下早了）。本篇用密集微基准 + 源码 + 阈值扫描把机制重新判定为 a-1，并解释了当初为什么会判错。

---

## 0. 为什么要写这篇：一次结论反转

前两步把退化逐层逼近，但**最后一公里的"机制归因"我走错了一次又自我纠正**。本篇的价值不只是结论，而是**完整的推理链**——每一条证据排除/支持了哪个假设，以及一个看似合理的结论是怎么被一个干净的对照实验推翻的。读完应能回答："为什么确定是 TLBI 而不是 walk？"

两个候选机制（都属于"host stage-2 使能后的硬件成本"，gate 已排除 EL2 软件路径）：

| | 机制 | 直觉 | 杠杆 |
|---|---|---|---|
| **a-1** | 每条 host **TLBI** 在 stage-2 下更贵（作废 combined 条目、VMID-tagged、DVM 广播，`DSB` 等更久） | teardown 的 TLB 作废变慢 | 减少 TLBI 条数（range TLBI / coalesce） |
| **a-2** | 每次 stage-1 **页表 walk** 被 stage-2 嵌套翻译，访存更慢 | teardown 的页表遍历变慢 | 减小 stage-2 翻译开销（大块映射） |

两者都能"先验地"解释 C0 看到的 backend 停顿。本篇就是要把它们分开。

---

## 1. 推理链（核心）

### 步骤 0 — 已知（前序结论）
- **gate**：munmap 不进 EL2（ΔEL2=0，计数器经 1.68 亿 cycle 阳性对照验证）→ 退化在 host 侧（EL1），不是隐藏 EL2 路径。
- **C0**（原 benchmark，protected vs nvhe）：munmap teardown **慢 1.81×**；`instructions / page-faults / dtlb_walk` 三者**两模式完全相同**，唯一变量是 **+40.9M backend 停顿**。
  → 同样的指令、同样的缺页、**同样次数的 stage-1 walk**，只是 protected 下更"卡"。剩下 a-1 / a-2 二选一。

### 步骤 1 — op=3 自省：排除"碎片化"，但**这里我多走了一步**
新增 `xcore_stats op=3` 遍历 host stage-2，得直方图：**host RAM 99.5% 是 1G block，仅 0.003%(31MB) 是 4K**。

- **正确推论**：host 内存**没有被拆成 4K** → a-2 的"碎片化导致深 walk"这个变体被排除。
- **我当时的错误推论**：进一步断言"那退化就是嵌套 walk 的**固有税**（a-2）"。
  这一步是**过度外推**——恰恰相反：**host RAM 是 1G block，意味着 stage-2 walk 极便宜**（一条 combined-TLB 条目覆盖 1GB），这本应是**反对 a-2 的证据**，我读反了。op=3 只能排除"碎片化"，**并不能**在 a-1 / a-2 之间做判别。

> **教训**：自省数据回答的是"host 内存是不是 4K"，不是"成本在 walk 还是 TLBI"。把前者的答案当成后者的结论，就是这次反转的根源。

### 步骤 2 — 密集微基准：**直接证伪 a-2**

**对照设计**：mmap 一个 64MB VMA → **写触摸每个 4K 页（全摸一遍）** → munmap，**只给 munmap 计时**
（mmap 与触摸是不计时的 setup，与原 benchmark 的 `bench_munmap_only` 口径一致）。

**为什么要先"全摸一遍"——这是本对照的关键，必须讲清**：

1. **让 munmap 真的有活干**：munmap 的开销只取决于这片 VMA **实际建了多少页表**。若只 mmap 不触摸，
   页从未缺页 → 一个 PTE 都没建 → munmap 几乎无事可做（没 PTE 要清、没页要释放、没 TLB 条目要作废），
   趋近于 0，**什么都测不到**。触摸触发缺页、把页真正映射进来、建出 PTE，munmap 才有可测的 teardown。
2. **把 walk 工作量拉满，专门压测 a-2**：**全**摸（整 64MB 每页都摸）把页表填满——32 个 PTE 页、
   16384 个 PTE 全部建好，是 munmap 能遇到的**最大遍历/释放工作量**。这是对 a-2 的压力测试：
   > 若退化真是"嵌套 walk 更贵"(a-2)，密集 case 要 walk 的 PTE 比稀疏多 **40 倍** → gap 应**最大**。

**而且这个对照点是精心选的——它同时给两个假设设了相反的条件**：
- 对 **a-2**：walk 工作量拉满（若 a-2 成立，这里 gap 该爆）；
- 对 **a-1**：因为触满后 munmap 范围 = 整 64MB ≥ 2MB 阈值（见步骤 4），内核走**单条整表 flush、
  没有逐页 TLBI**（若 a-1 成立，这里 gap 该消失）。

实测：

| | nvhe | protected | gap |
|---|---:|---:|---:|
| 密集 munmap（触满 64MB，16384 PTE，整表 flush） | 2828 µs | 2785 µs | **≈0** |

**判读**：gap≈0 → **walk 拉满也不出税 → 不是 a-2**；而这与 a-1 自洽（无逐页 TLBI → 无税）。
**只有 a-1 能同时解释这两面**："walk 再多也不要紧，要紧的是有没有逐页 TLBI"。

> 对比三种触摸强度，逻辑才完整（细节见步骤 5 的阈值扫描）：
>
> | 触摸 | PTE 数(walk 量) | munmap 范围 → flush | pKVM gap |
> |---|---|---|---|
> | 不摸 | 0 | 无 teardown | 测不到 |
> | 稀疏(原 benchmark) | ~410 | <2MB → 逐页 TLBI | **大(4.8×)** |
> | **全摸(本对照)** | **16384(拉满)** | ≥2MB → 整表 flush | **≈0** |
>
> 稀疏有税、全摸无税，区别**不在 PTE/walk 数**（全摸还多 40 倍），**而在有没有逐页 TLBI**。

### 步骤 3 — 与 C0 对账：退化在哪种 munmap？
密集无 gap，但 C0 明明有 1.81× 的 gap。差别在哪？读 C0 已存日志里**原 benchmark 自报的 munmap-only 时间**（原 benchmark 用 `bench_munmap_only` 只给 munmap 计时，且是**稀疏**触摸：前 6.4MB、16KB stride、~410 页）：

| | nvhe munmap | protected munmap | gap |
|---|---:|---:|---:|
| **原 benchmark（稀疏）** | 113 µs | 548 µs | **4.8×（+435µs）** |
| 我的密集微基准 | 2828 µs | 2785 µs | ≈0 |

→ **退化确实在 munmap，但只在"稀疏/中小范围"那种，密集大范围反而没有。** 这个"小 munmap 有税、大 munmap 没税"的反差，正是下一步的钥匙。

### 步骤 4 — 源码：内核对范围的 TLBI 有个阈值
`arch/arm64/include/asm/tlbflush.h:422`（`__flush_tlb_range_nosync`）：
```c
if ((!system_supports_tlb_range() && (end - start) >= (MAX_DVM_OPS * stride)) ||
    pages >= MAX_TLBI_RANGE_PAGES) {
    flush_tlb_mm(vma->vm_mm);   // 单条整表(ASID) flush
    return;
}
// 否则：对 [start,end) 范围内逐个页槽发 TLBI
```
- N80 **无 FEAT_TLBIRANGE**（`system_supports_tlb_range()==false`，ID_AA64ISAR0_EL1.TLB=0），所以走第一条；
- `MAX_DVM_OPS = PTRS_PER_PTE = 512`，stride=4K → 阈值 = **512×4K = 2MB**。
- **范围 < 2MB：对范围内每个页槽逐条 TLBI；范围 ≥ 2MB：单条整表 flush。**

→ 这给出可证伪预言：**逐页区间（<2MB）应有 pKVM 税且 ∝ TLBI 条数；整表区间（≥2MB）税应消失。**

### 步骤 5 — 阈值扫描：**直接证实 a-1**

**扫描设计（为什么这样扫）**：步骤 4 给出可证伪预言——逐页区间(<2MB)有税且 ∝TLBI 条数，整表区间(≥2MB)无税。
要验证它，需要**精确控制 munmap 的 flush 范围**并让它**跨过 2MB 阈值**：
- **用"连续密集触摸前 N MB"（stride 4K）**：连续触摸使被填的 PTE 集中在前 N MB → munmap 的 flush 范围 ≈ N MB，
  **范围由 N 直接、干净地控制**（不像稀疏触摸那样范围与触摸点纠缠）。
- **范围取点 0.25→1.9→2.0→4→…→64MB**，**在 2MB 两侧密集取点**（1.9 vs 2.0），就是为了**抓住断崖、看 gap 是否恰在阈值处塌掉**。
- 两模式各跑一轮、取 munmap-only mean（min 贴近 mean，噪声小）；gap = protected − nvhe。
- 末行附原 benchmark 的**稀疏**点（6.4MB/16K）做闭环对照。

| 触摸范围 | protected | nvhe | **gap** | 区间 |
|---|---:|---:|---:|---|

| 触摸范围 | protected | nvhe | **gap** | 区间 |
|---|---:|---:|---:|---|
| 0.25 MB | 34.1 | 16.3 | +17.8 | 逐页 |
| 0.5 MB | 62.4 | 28.2 | +34.2 | 逐页 |
| 1.0 MB | 120.9 | 52.5 | +68.4 | 逐页 |
| **1.9 MB** | 227.5 | 95.0 | **+132.5 (+139%)** | 逐页 |
| **2.0 MB** | 93.4 | 88.6 | **+4.8 (+5%)** | **整表** |
| 4 MB | 184.1 | 173.6 | +10.5 (+6%) | 整表 |
| 8 MB | 366.9 | 346.4 | +20.5 (+6%) | 整表 |
| 32 MB | 1451.2 | 1369.3 | +81.9 (+6%) | 整表 |
| 64 MB | 2876.3 | 2734.1 | +142.2 (+5%) | 整表 |
| 稀疏 6.4MB/16K（原 benchmark 模式） | 546.7 | 108.6 | **+438.1 (+403%)** | 逐页 |

**三个铁证**：
1. **断崖**：1.9MB 时 gap=+132.5µs(+139%)，2.0MB 时骤降到 +4.8µs(+5%)。pKVM 税**恰好随"逐页→整表"的切换点(2MB)消失**——这只能是 TLBI 机制，walk 机制不会在这一点反向塌掉。
2. **线性**：<2MB 的 gap 随范围线性增长（18→34→68→132µs）→ **gap ∝ 逐页 TLBI 条数**。斜率 ≈ 69.5µs/MB ÷ 256 页/MB = **每条 host TLBI 在 pKVM 下多花 ~0.27µs（~490 cycles@1.8GHz）**。
3. **闭环**：稀疏 6.4MB 范围 = 1638 个页槽 → 逐页 1638 条 TLBI × 0.27µs ≈ 442µs ≈ 实测 +438µs，**与 C0 的 +435µs 完全吻合**。退化的来源就此闭环到逐页 TLBI。

整表区间(≥2MB)残留的 +5~6% 是 ∝页数的**释放页**成本在 stage-2 下的小幅放大，与 TLBI 无关，量级远小于逐页税。

---

## 2. 为什么每条 host TLBI 在 pKVM 下更贵（结合实际刷新代码）

### 2.1 先看内核实际发的是什么——逐页 vs 整表，落到指令

munmap 的 TLB 作废链：`__flush_tlb_range()` → `__flush_tlb_range_nosync()` →（按范围二选一）。
关键代码（`arch/arm64/include/asm/tlbflush.h`）：

**① 阈值判断**（`__flush_tlb_range_nosync`，:422）——决定走逐页还是整表：
```c
if ((!system_supports_tlb_range() && (end - start) >= (MAX_DVM_OPS * stride)) ||
    pages >= MAX_TLBI_RANGE_PAGES) {
    flush_tlb_mm(vma->vm_mm);           // ② 整表：1 条按 ASID 的 TLBI
    return;
}
dsb(ishst);                              // 等前面的 store 落盘
__flush_tlb_range_op(vae1is, start, pages, stride, asid, tlb_level, true);  // ③ 逐页/范围
```

**② 整表路径**（`flush_tlb_mm`，:253）——**只有一条 TLBI**，与页数无关：
```c
dsb(ishst);
asid = __TLBI_VADDR(0, ASID(mm));
__tlbi(aside1is, asid);                  // tlbi aside1is, <asid>  ← 整个 ASID 一条搞定
__tlbi_user(aside1is, asid);             // KPTI 下再补一条（user ASID）
dsb(ish);                                // 等广播完成
```

**③ 逐页路径**（`__flush_tlb_range_op` 宏，:369）——N80 无 FEAT_TLBIRANGE，走"逐页"分支：
```c
while (pages > 0) {
    if (!system_supports_tlb_range() || pages == 1) {   // ← N80 恒真，逐页
        addr = __TLBI_VADDR(start, asid);
        __tlbi_level(op, addr, tlb_level);              // tlbi vae1is, <addr> ← 一页一条
        if (tlbi_user) __tlbi_user_level(op, addr, ...);// KPTI 下每页再补一条
        start += stride;  pages -= 1;  continue;
    }
    ... // 有 FEAT_TLBIRANGE 时这里走 __tlbi(r##op,...)：一条覆盖一段，N 条→几条
}
```
而 `__tlbi(op, arg)` 最终就是一条 `tlbi` 汇编（`__TLBI_1`，:40）：`asm("tlbi vae1is, %0")`。
最后由 `__flush_tlb_range()`（:443）补一条 **`dsb(ish)`** 等所有 TLBI 广播完成。

**所以落到指令层面的对比**（这就是"断崖"的根因）：

| munmap 范围 | 走哪条 | 实际发的 TLBI |
|---|---|---|
| **< 2MB** | `__flush_tlb_range_op` 逐页 | **N 条** `tlbi vae1is`（KPTI 下 2N）+ 末尾 1 条 `dsb ish` |
| **≥ 2MB** | `flush_tlb_mm` 整表 | **1 条** `tlbi aside1is` + 1 条 `dsb ish` |

> 逐页区间成本 = **N × 每条 TLBI 成本**；整表区间 = **1 × 每条 TLBI 成本**（与 N 无关）。
> 所以只要"每条 TLBI"在 pKVM 下更贵，逐页区间的 gap 就 **∝ N（∝范围）**，整表区间就**只剩一条的量、≈0**——和 §1 步骤 5 的扫描曲线一一对应。

### 2.2 为什么"同一条 `tlbi vae1is`"在 pKVM 下更贵

指令完全一样（`tlbi vae1is, <VA|ASID>`），变贵的是**它要作废的 TLB 内容**和**广播/完成的代价**：

- **nvhe（无 host stage-2）**：host EL1 是单级翻译，TLB 里是**纯 stage-1**条目。`tlbi vae1is` 作废该 VA/ASID 的 stage-1 条目，`dsb ish` 等内部共享域广播完成。
- **protected（host stage-2 开）**：host EL1 是**嵌套**翻译（VA→IPA→PA），TLB 里是 **combined(stage1×stage2)** 条目、带 **VMID**(host 的 stage-2 上下文)标记。同一条 `tlbi vae1is` 要作废这些 combined 条目——涉及 stage-2 维度/VMID 的作废与 DVM 广播路径更重，末尾那条 `dsb ish` 等**所有**这些更重的作废完成 → 排到 `dsb` 时**流水线 backend 停顿更久**（与 perf 看到的"`dtlb_walk` 不变、`stall_backend` 增加"完全吻合：卡在 TLBI/DSB 完成，不是多走 walk）。

实测每条逐页 TLBI 在 pKVM 下多 **~0.27µs（~490 cycles@1.8GHz）**。这是**硬件层面**的代价；且 host TLBI **不被 trap**（gate 已证，host HCR 无 `TTLB`），所以与 EL2 软件路径无关——hyp 既挡不住也加速不了，唯一能少花的办法是**少发几条 TLBI**（见 §4：FEAT_TLBIRANGE 用 `__tlbi(r##op)` 把"逐页 N 条"压成"一段几条"）。

> 旁注：`__tlbi_user`（上面代码里每页/整表都跟着的第二条）是 **KPTI**（kernel-unmap-at-EL0）下对 user ASID 的补刀——开了 KPTI 时逐页 TLBI 数**翻倍**，pKVM 税也随之翻倍。

---

## 3. 这如何与前序结论自洽（澄清逻辑关系）

| 证据 | 对 a-1 | 对 a-2 |
|---|---|---|
| gate：不进 EL2 | 不矛盾（TLBI 是 host 侧硬件） | 不矛盾 |
| C0：同 walk 数、同缺页、+backend 停顿 | ✓（DSB 等待 = backend 停顿；TLBI 不改 walk 数） | 也能先验解释 |
| C0：`l1d_tlb_refill` +17% | ✓（TLBI 作废后重填） | 中性 |
| **op=3：host RAM 99.5% 1G block** | ✓（**walk 便宜 → 瓶颈只能在别处 = TLBI**） | **✗（walk 便宜 → a-2 不该贵）** |
| **密集 munmap gap≈0** | ✓（密集=整表 flush=1 条 TLBI） | **✗（页多但无 gap）** |
| **2MB 断崖 + 线性** | ✓✓（gap∝TLBI 条数，随 coalesce 消失） | **✗（不会在 2MB 反向塌）** |
| 无 FEAT_TLBIRANGE | ✓（只能逐页 → 贵） | 中性 |

**关键澄清**：op=3 的"host RAM 是大块"这条数据，**不仅不支持 a-2，反而是支持 a-1 的有力证据**——大块映射让 walk 便宜，等于把嫌疑从 walk 身上摘掉。当初把它读成"a-2 固有税"是逻辑接反了。

---

## 4. 杠杆与结论

**结论**：pKVM 下 host `munmap` 的退化 = **逐页 `TLBI` 的 stage-2 硬件税**（a-1），仅出现在**范围 < 2MB（无 FEAT_TLBIRANGE 时不会 coalesce 成整表）的中小 munmap**；每条 host TLBI 多 ~0.27µs，gap ∝ TLBI 条数。

**杠杆**（按可行性/影响）：
1. **FEAT_TLBIRANGE（核心硬件杠杆）**：有此特性的 CPU 用 **range TLBI**（一段 1~几条而非逐页），TLBI 条数骤降 → 退化大幅缩小。N80 没有，所以退化明显；这也意味着**退化是平台相关的**，新硬件上会轻很多。
2. **coalesce 阈值**：大 munmap（≥2MB）已自动整表 flush、无税；退化集中在中小 munmap（lat_mmap 这类微基准、频繁小映射的负载）。可评估是否降低 `MAX_DVM_OPS` 阈值让更多 munmap 走整表（权衡：整表 flush 会作废全部 TLB，影响后续 refill）。
3. **纯 pKVM 侧空间有限**：每条 host TLBI 的 stage-2 成本是硬件层面的；hyp 能做的有限（host TLBI 不被 trap）。

**实践含义**：用大映射/大页/少而大的 munmap 的真实负载基本不受影响；命中退化的是"中小范围、频繁 munmap"的模式，且在带 FEAT_TLBIRANGE 的平台上会显著缓解。

---

## 5. 复现与数据

- 微基准：`munmap_only.c`（`<mode> <mb> <iters> <path> [touch_mb] [stride_kb]`，只给 munmap 计时，可控触摸范围/stride）。
- 阈值扫描：连续密集触摸 0.25→64MB（stride 4K）+ 稀疏参考（6.4MB/16K），protected 与 nvhe 各一轮，取 munmap-only mean（min 贴近 mean，稳）。
- 关键常数：`MAX_DVM_OPS=512` → 阈值 2MB；N80 无 FEAT_TLBIRANGE（`ID_AA64ISAR0_EL1.TLB=0`）。
- 数据见本文 §1 表；原 benchmark 自报来自 C0 日志 `results/n80-munmap-gate-c0/{protected,nvhe}/c0-*/bench-perf-*.log`。
