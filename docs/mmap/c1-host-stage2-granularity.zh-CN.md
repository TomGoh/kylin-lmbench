# C1 第一步：host stage-2 映射粒度自省 —— 判别 H1 / H2

**平台**：N80 / Kylin V10 SP1 / aarch64 / 内核 `6.6.30xcore-stat+`（Rust nVHE hyp，protected 模式，1.8 GHz）
**日期**：2026-06-12
**前置**：[n80-gate-c0-results.zh-CN.md](n80-gate-c0-results.zh-CN.md) 已判定 `munmap_after_write_touch` 退化**不在 EL2**，
且 perf 归因为 **host stage-2 嵌套翻译造成的 backend(访存)停顿**（protected 比 nvhe 慢 1.81×，
额外 +39.8M cycles ≈ +40.9M backend 停顿，而 `dtlb_walk` 次数两模式相同 → 不是更多次 walk，而是**每次 walk 更贵**）。
**本报告回答**：这笔"每次 walk 更贵"是否来自 **host 内存被拆成 4K**（嵌套 walk 更深）——即 H1，
还是来自"host 内存已是大块、但嵌套翻译本身就贵"——即 H2。

> ## ⚠️ 结论更正（2026-06-12）
>
> **本文档的 op=3 自省数据与方法是对的**（host RAM 99.5% 是 1G block，确凿无误），
> **但据此得出的"机制 = H2 嵌套 walk 固有税(a-2)"的结论是错的。** 真正的机制是
> **a-1：逐页 `TLBI` 的 stage-2 硬件税**，由后续阈值扫描实验证实 →
> **[c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md)**。
>
> **错在哪**：op=3 只能排除"host 内存被拆成 4K"(H1)，**并不能**在"walk 贵(a-2)"与
> "TLBI 贵(a-1)"之间判别。而且"host RAM 是大块"恰恰意味着 **stage-2 walk 便宜**，
> 本应是**反对 a-2** 的证据，当时却被读成"a-2 固有税"——逻辑接反了。下面 §6.4 与 §7 的
> 机制判断/优化方向已被 a-1 取代；正文其余部分（背景、op=3 设计与数据）仍有效，原文保留留痕。

---

## 0. 摘要（结论先行）

**结论 = H2。** 实测 host stage-2 映射粒度直方图（protected 模式，全 host IPA 空间）：

| 粒度 | 叶子条目数 | 覆盖页数 | 占总面积 | 折合大小 |
|---|---:|---:|---:|---:|
| **1G block** | 1019 | 267,124,736 | **99.52%** | 1019 GB |
| 2M block | 2486 | 1,272,832 | 0.474% | ≈4.85 GB |
| 4K page | 8046 | 8,046 | **0.003%** | ≈31.4 MB |
| 合计 | — | 268,405,614 | 100% | ≈1 TB（全 PA 空间，含 MMIO） |

- **host 内存 99.5% 是 1G block**，只有 31MB 是 4K → **不是碎片化问题，host 内存已最大化块映射**。
- 直接反证：全系统 4K 页仅 **8046 个**，而 benchmark 工作集 64MB = **16384 页**；`8046 < 16384`，
  故 benchmark 区域**不可能是 4K 映射**，必落在 2M/1G block 内。
- 这条数据**排除了"碎片化导致深 walk"**（H1）。**但它不能判别 a-1/a-2**；
  且"大块 → walk 便宜"实为**反对 a-2** 的证据。**[已更正]** 机制实为 **a-1 逐页 TLBI 税**，
  见 [c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md)。下方 §6.4 / §7 的旧机制结论作废。

---

## 1. 背景：从 gate→C1 到 H1/H2 的分叉

第一步报告确立了两点：
1. **gate**：`munmap` teardown 不进 EL2（ΔEL2=0，计数器经 1.68 亿 cycle 阳性对照验证）→ 路线 C1（host 侧）。
2. **perf 归因**：退化 = backend 访存停顿，且 `instructions / page-faults / dtlb_walk` 三个量两模式**完全相同** →
   同样的指令、同样的缺页、**同样次数的 stage-1 walk**，唯一差别是 protected 下**每次 walk 被 host stage-2 嵌套翻译**。

由此分叉出两个假设：

```
H1：benchmark 触及的 host 内存在 host stage-2 已被拆成 4K
    → 每次嵌套 walk 的 stage-2 部分更深、combined-TLB 压力大
    → 杠杆 = 保持/恢复 block 映射
H2：host 内存仍是大块（2M/1G），嵌套翻译本身就贵
    → 粒度不是杠杆 → 另寻 C1 杠杆
```

**perf 无法回答这个分叉**：`dtlb_walk` 只数 stage-1 walk 次数，看不到 host stage-2 的映射粒度；
而 host stage-2 是 hyp 私有的，host 侧读不到。所以必须做 **hyp 侧只读自省**。

---

## 2. 体系结构：host stage-2 的块映射与拆分

pKVM 下 host 物理内存受 **host stage-2 页表**（IPA→PA 第二级翻译）保护。关键事实（源码已核实）：

### 2.1 host 内存默认按"最大块"映射
`host_stage2_idmap()`（`mem_protect/host.rs`）→ `host_stage2_adjust_range()` 用贪心循环选**能容纳该范围的最大块级别**：
```rust
// host_stage2_adjust_range：从当前 level 往上（向 1G）尝试，范围能整块装下且该 level 支持块映射就停
loop {
    let granule = kvm_granule_size(level);
    cur = [align_down(addr, granule), +granule);
    level += 1;
    if level >= KVM_PGTABLE_MAX_LEVELS
       || (kvm_level_supports_block_mapping(level) && range_included(cur)) { break; }
}
```
→ 4K 基页系统下，能装下就用 **1G(L1) / 2M(L2)**，否则退到 **4K(L3)**。host RAM 因此默认是大块。

### 2.2 什么会把块拆成 4K
`host_stage2_force_pte()`（`mem_protect/host.rs`）：当某子范围的 prot **偏离 `default_host_prot()`** 时强制 4K：
```rust
pub extern "C" fn host_stage2_force_pte(addr,end,prot) -> bool {
    prot != default_host_prot(range_is_memory(addr,end))  // 偏离默认 → 只能 4K
}
```
触发场景：把单个 4K 页 **share/donate/relinquish** 给 guest 或 hyp、改权限、`__host_stage2_set_owner_locked()`
设非 host owner——所在 2M/1G block 会被拆成 512×4K，只给那几页打新状态。

### 2.3 为什么粒度影响嵌套 walk 成本
开 host stage-2 后，host 的每次 **stage-1 TLB-miss walk** 中，各级 stage-1 描述符地址都是 IPA，需再经 stage-2 翻译
（nested/combined walk）。stage-2 粒度越细，单次嵌套 walk 要解析的 stage-2 层级越多、combined-TLB/walk-cache 压力越大。
所以"host 内存是 4K 还是大块"直接决定嵌套 walk 的代价——这正是 H1/H2 的分水岭。

---

## 3. 插桩设计：xcore_stats op=3（只读 host stage-2 粒度直方图）

复用既有 hcall 通道（`__pkvm_xcore_stats`，id 64）与 op=2 的 protected 门控范式，新增 **op=3**。

**为什么是"只读直方图"这个设计**（每个选择都有原因）：
- **为什么要 hyp 自省**：判别 H1/H2 需要知道 host 内存在 host stage-2 是 4K 还是大块；而 host stage-2 是 **hyp 私有**的，**host 侧根本读不到** → 只能在 hyp 里读。perf/ftrace 都看不到 stage-2 粒度，所以非加这个 hcall 不可。
- **为什么用直方图、而不是查单个地址**：一张"按 level 分桶的页数直方图"(#1G/2M/4K) **一眼就能判 H1/H2**（碎成 4K 还是大块），且**不需要事先知道 benchmark 的物理地址**（省去从 `/proc/self/pagemap` 取 PA 再逐段查的麻烦）。
- **为什么复用 xcore_stats 通道 + op=2 范式**：最小改动、最低风险——沿用现成的 hcall 分发、protected 双侧门控、遍历器回调范式，而不是另起一套基础设施。
- **关键正确性**：遍历 **`host_mmu.pgt`（host stage-2）**，而**不是** `xcore_mem_stats` 用的 `PKVM_PGTABLE`（那是 **hyp 自己的**页表，粒度与 host 内存无关）。走错表就会得出与问题无关的直方图。

### 3.1 hyp 侧遍历器（`mem_protect/host.rs`）
新增 `host_stage2_level_histogram()` + 叶子回调 `host_s2_level_walker()`，复用 `host_stage2_get_leaf` 的锁范式
和 `stats.rs::pkvm_memory_walker` 的回调范式：
```rust
// 叶子回调：按映射粒度分桶（kvm_granule_size(level) 给出该叶子覆盖的字节数）
let granule = kvm_granule_size(ctx_ref.level);
let pages = granule >> PAGE_SHIFT;
hist.total += pages;
if      granule == 1u64 << PAGE_SHIFT { hist.pages_4k += pages; }   // 4K
else if granule == 0x20_0000          { hist.pages_2m += pages; }   // 2M
else if granule == 0x4000_0000        { hist.pages_1g += pages; }   // 1G

// 遍历函数：持 host 组件锁，walk 整个 host stage-2
host_lock_component();
let ret = unsafe {
    let ia_bits = host_mmu.pgt.ia_bits;
    kvm_pgtable_walk(&raw mut host_mmu.pgt, 0, 1u64 << ia_bits, &mut walker)  // KVM_PGTABLE_WALK_LEAF
};
host_unlock_component();
```

### 3.2 hcall 分发（`hyp_main.rs` `xcore_stats_entry`，op=3）
仿 op=2：先 `static_branch_unlikely!(kvm_protected_mode_initialized, …)` 门控（非 protected 返回 `SMCCC_RET_NOT_SUPPORTED`），
再调直方图函数，经寄存器返回：
```rust
3 => {
    if !protected { set_cpu_reg(0, SMCCC_RET_NOT_SUPPORTED); return; }
    let hist = host_stage2_level_histogram();
    set_cpu_reg(0, hist.pages_4k);  set_cpu_reg(1, hist.pages_2m);
    set_cpu_reg(2, hist.pages_1g);  set_cpu_reg(3, hist.total);
}
```

### 3.3 host 侧接口（`arch/arm64/kvm/xcore_stats.c`）
新增 `XCORE_STATS_GET_S2_LEVELS=3`、`struct xcore_s2_levels`、`xcore_get_s2_levels()`（hvc op=3，按符号判错）、
写分发 `case 3`（`is_protected_kvm_enabled()` 门控）、`seq_file` 显示（块数 + 覆盖页数 + 总量 MB）。

**输出寄存器约定**：a0=4K 页数, a1=2M 覆盖页数, a2=1G 覆盖页数, a3=总页数。
**安全**：仅 protected 双侧门控（nvhe 下 host_mmu 未初始化）；只读，不改任何映射，零功能性副作用；
遍历期间持 host 锁（与 `host_stage2_get_leaf` 一致），防并发改表。

---

## 4. 测试进行

1. 编译：增量 `make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j Image`（只改了内置代码，无模块改动）。
2. 部署：因版本串不变、仅 Image 变化，**只覆盖 `/boot/vmlinuz-6.6.30xcore-stat+`**（sha256 校验一致），不动模块/initramfs。
3. 启动：GRUB 选 `(pKVM protected)` 条目（op=3 仅 protected 可用）。
4. 实测：
   ```
   echo 3 > /proc/xcore_stats && cat /proc/xcore_stats
   ```

---

## 5. 结果（protected，N80）

```
host stage-2 mapping granularity:
4K  pages : 8046
2M  blocks: 2486  (1272832 pages)
1G  blocks: 1019  (267124736 pages)
Total     : 268405614 pages (1048459 MB)
```

| 粒度 | 叶子数 | 覆盖页数 | 占面积 | 大小 |
|---|---:|---:|---:|---:|
| 1G block | 1019 | 267,124,736 | 99.52% | 1019 GB |
| 2M block | 2486 | 1,272,832 | 0.474% | ≈4.85 GB |
| 4K page | 8046 | 8,046 | 0.003% | ≈31.4 MB |
| 合计 | — | 268,405,614 | 100% | ≈1 TB |

（总量 ≈1 TB = host stage-2 覆盖的整个 host IPA/PA 空间，含 RAM + MMIO/设备区，绝大部分以 1G block 恒等映射。）

---

## 6. 分析

### 6.1 H2 成立：host 内存已最大化块映射
host RAM 的 **99.52% 是 1G block**、0.47% 是 2M block，只有 **0.003%（31MB）是 4K**。
benchmark 的 file-cache 页、其页表页、struct page 都是普通 host RAM → 必然落在大块区。

### 6.2 一个不需要范围查询的硬反证
全系统 4K 页只有 **8046 个**，而 benchmark 工作集是 64MB = **16384 页**。
`8046 < 16384` → benchmark 那片区域**不可能是 4K 映射**（否则 4K 计数早超过 16384）→ 它必然在 2M/1G block 内。
这一条就排除了 H1，无需再做 op=4 范围查询。

### 6.3 这 8046 个 4K 是谁拆的、与 benchmark 无关
它们是 boot 时 hyp 初始化捐赠 / IOMMU idmap / 共享 bookkeeping 等触发 `force_pte`（§2.2）拆出来的少量页，
是**静态的**。而 `munmap` 是 host **stage-1** 活动，不 share/donate host 页，**不会拆 host stage-2**——
所以跑不跑 benchmark，host stage-2 这张图都一样。

### 6.4 含义 【❌ 已更正：当初判成 a-2 嵌套 walk，实为 a-1 逐页 TLBI】

> 下面这段灰字是**当初的错误结论**，保留留痕。正确机制见
> [c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md)。

> ~~+40.9M backend 停顿来自 stage-2 嵌套翻译本身：即便 host RAM 是 1G block，每次 stage-1 TLB-miss
> 的 walk 仍要对各级描述符地址做 stage-2 翻译……"提高 stage-2 粒度"这条优化路被堵死了。~~

**为什么这段错了**：把成本归给"嵌套 walk"是逻辑接反了——host RAM 是大块**恰恰说明 walk 便宜**。
随后两个对照直接推翻了它：① **密集 munmap**（触满 64MB、16384 个 PTE）gap≈0——若是 walk 机制，
页越多 walk 越多、gap 该越大，实际却没有；② **阈值扫描**显示 gap 在 **2MB 整表-flush 阈值处断崖消失**，
且 <2MB 时 **gap ∝ TLBI 条数**。两者都只能由 **逐页 TLBI（a-1）** 解释。详见新文档。

---

## 7. 优化方向 【❌ 已更正：旧表基于 a-2，作废】

> 本节原表基于错误的 a-2（嵌套 walk）机制，已作废。**正确的优化方向（基于 a-1 逐页 TLBI 税）见
> [c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md) §4。** 要点：
>
> - **核心杠杆 = FEAT_TLBIRANGE**：range TLBI 把"逐页一条"合并成"一段几条"，TLBI 条数骤降 →
>   退化大幅缩小。N80 无此特性，故退化明显（退化是**平台相关**的）。
> - 大 munmap（范围 ≥2MB）内核已自动 coalesce 成单条整表 flush，**本就无税**；退化只发生在中小 munmap。
> - **"提高 host stage-2 粒度"对本退化无效**：粒度已最大化，且瓶颈不在 walk 而在 TLBI。

---

## 8. 附：op=3 接口与复现

- 内核改动：`mem_protect/host.rs`（`host_stage2_level_histogram` + `host_s2_level_walker`）、
  `hyp_main.rs`（`xcore_stats_entry` op=3）、`xcore_stats.c`（`XCORE_STATS_GET_S2_LEVELS=3` + helper + case 3 + 显示）。
- 复用：`host_stage2_get_leaf` 锁范式、`stats.rs::pkvm_memory_walker` 回调范式、op=2 的 protected 门控范式。
- 复现：protected 模式 `echo 3 > /proc/xcore_stats && cat`；nvhe 下应返回不支持（hyp 端 `NOT_SUPPORTED` + host 端 `EOPNOTSUPP`）。
- sanity：`Total × 4K ≈ host PA 空间`（本机 ≈1 TB，含 MMIO）。
