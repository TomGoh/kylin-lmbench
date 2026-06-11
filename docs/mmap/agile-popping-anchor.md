# pKVM mmap 性能调优第二步：先判别 EL2，再决定插桩面

## Context（背景）

`docs/mmap/` 已完成第一步（拆分 lat_mmap）：pKVM host 侧 lat_mmap 慢 30~42%。
mmap-split 实验（mmap-split-kaitian-pkvm-comparison.zh-CN.md）把退化定位得很窄：

| 测试项（64MB） | pKVM 额外时间 |
|---|---|
| mmap_write_touch_unmap（完整写路径） | +214.325 µs |
| **munmap_after_write_touch** | **+205.003 µs（+227%）** |
| write_touch_cold | 仅 +12.618 µs（+3.78%） |
| mmap_unmap / munmap_after_no_touch | 基本持平 |

即：完整写路径的额外时间**几乎全部**由"写触摸后的 munmap teardown"解释；旧模型
（pkvm-mmap-overhead-analysis.md 的"first-touch 每页 ~500ns 进 EL2 建表"）已被
touch_cold 数据否定，不再是主解释。

**整个计划的中心问题**（不是旁支）：host 的 munmap 理论上不进 EL2——host TLBI 不被
trap（无 HCR_EL2.TTLB，已查无 handler）、普通 munmap 不触发 hypercall。那 +205µs 从哪来？

```
(a) 纯硬件开销 —— host stage-2 使能后，host munmap 的 TLBI/DSB 广播变贵，
    和/或 touched file-backed PTE teardown 的两级 walk / dirty accounting /
    cache-TLB 交互成本放大（EL2 代码不背锅）
(b) 隐藏 EL2 路径 —— 如 HOST_S2_POOL 页表页耗尽触发 host_stage2_unmap_unmoveable_regs
    回收（host.rs:334 host_stage2_try! 的 ENOMEM 分支）→ 后续 abort 风暴
```

**执行原则：先证明 munmap_after_write_touch 的额外时间是否来自 EL2（Patch B 作为
gate）；只有证明来自 EL2，才展开 pKVM Rust mem_protect 细粒度插桩（C2）。否则重心
在 host 侧（C1），避免把精力花在注定读数为 0 的 hyp 站点上。**

板子 defconfig：`gwd3000_lenovox1d3000m_defconfig`，`CONFIG_X1_RMS` default y 生效
→ 跑的是 **Rust 版 hyp**（arch/arm64/kvm/hyp/nvhe/rust/）。普通 nvhe 对照模式跑的也是
同一个 Rust hyp 对象（运行时 kvm-arm.mode 区分）。

## 已确认的现有基础设施（直接复用，不重复造）

| 设施 | 位置 | 用途 |
|---|---|---|
| **xcore_stats（已有 EL2-only PMU cycle 计数）** | host: arch/arm64/kvm/xcore_stats.c（/proc/xcore_stats）；hyp: rust/src/stats.rs（PMCCFILTR_EL0 设 EL2-only 过滤，PMCCNTR_EL0 累计 EL2 周期）；hcall id 64，op 0/1/2 已有。`CONFIG_XCORE_STATS` default n，**defconfig 未开** | **gate 实验的已有基础，经 Patch A2 少量修复（PMU save/restore、PMCNTENCLR、门控）后可用** |
| HYP_EVENT 事件机制 | arch/arm64/include/asm/kvm_hypevents.h（唯一权威定义，host/hyp 双侧自动展开）；hyp 侧符号由 nvhe/events.c 无条件生成（X1_RMS=y 也编译）；Rust 侧 `hyp_event!` 宏 trace.rs:2022 经 extern 符号 `hyp_event_id_<name>`/`<name>_enabled` 链接 | 新增事件：**定义**改 2 个文件（kvm_hypevents.h + trace.rs）；调用点、C fallback 调用点、boot 时事件数一致性验证另算 |
| 已有事件 | hyp_enter/hyp_exit/host_hcall/host_mem_abort（Rust 已在 host.rs:1998,2035 调用）/__hyp_printk | EL2 入口计数直接可用 |
| trace_hyp_printk / trace_debug! | trace.h:81（C）；Rust 侧：FFI 声明 console.rs:8、分发 console.rs:18、trace_debug! 宏 console.rs:176（到 trace_hyp_printk_func_0..4，只能发裸 u64） | **仅作临时"有没有到这里"标记，不作为主统计手段**——munmap_after_write_touch 是高频路径，常开数据走 per-cpu counter，HYP_EVENT 只做短跑采样 |
| hyp tracefs | /sys/kernel/debug/tracing/hypervisor/（buffer_size_kb、events/*/enable、per_cpu/cpuN/trace_pipe）。**仅 protected 模式可用**（hyp_trace.c:958 门控，勿放宽：nvhe 下 buffer load 走 share/donate hcall 会在未初始化 host_mmu 上 panic） | pKVM 模式读事件 |
| per-cpu 基础设施 | rust/src/percpu.rs（define_per_cpu! / this_cpu_ptr / per_cpu_ptr）；链接脚本已收集 Rust 对象 .data..percpu | C2 计数器载体 |
| 计时原语 | rust/src/arch_timer.rs:26 arch_counter_get_cntpct（已含 ISB+ordering，~20-50 cycles/次）；存原始 tick，host 用 CNTFRQ 换算 | 区间计时 |
| 池水位 | rust/src/page_alloc.rs:191 HypPool.free_pages | HOST_S2_POOL gauge（C2） |

defconfig trace 链现状：SCHED_TRACER=y→TRACING=y（hyp events 编译）、STACK_TRACER=y→
FUNCTION_TRACER（host funcgraph 可用）、PROTECTED_NVHE_FTRACE=y、NVHE_EL2_DEBUG=y——
均为依赖推导的结果，Patch A 显式固定整组依赖以防被裁剪。**功能性缺口是
CONFIG_XCORE_STATS=y（default n，必须显式加）**。

## 实施方案

```
Patch A（配置 + PMU 最小修复 + 可用性确认）
   │
   ├──> Patch B（gate：munmap 窗口 EL2 判别实验）──┬── EL2≈0 ──> Patch C1（host 侧深入）
   │                                              └── EL2>0 ──> Patch C2（hyp per-cpu counter）
   └──> Patch C0（host 侧 L3 对照，与 B 并行，不等 gate）
                                                      Patch D（HYP_EVENT 短窗采样，验证用）
```

### Patch A：最小配置 + PMU 修复 + xcore_stats 可用性确认

**A1 配置**（显式固定整组依赖，不只加一行）：
插桩版内核的前提配置（TRACING/FUNCTION_TRACER 等）目前靠 SCHED_TRACER/STACK_TRACER
间接 select 推导——依赖链变化或配置裁剪会悄悄丢失。显式固定：
- `arch/arm64/configs/gwd3000_lenovox1d3000m_defconfig`（或独立 config fragment，如
  `kernel/configs/pkvm-prof.config`，用 `make gwd3000... pkvm-prof.config` 叠加）：
  `CONFIG_XCORE_STATS=y` + 显式写入 `CONFIG_FTRACE=y`、`CONFIG_FUNCTION_TRACER=y`、
  `CONFIG_FUNCTION_GRAPH_TRACER=y`、`CONFIG_DYNAMIC_FTRACE=y`、`CONFIG_DEBUG_FS=y`
  （STACK_TRACER/SCHED_TRACER 已有，保留）
- 验证：构建后对生成的 .config `grep -E "XCORE_STATS|^CONFIG_TRACING|FUNCTION_TRACER|FUNCTION_GRAPH|DYNAMIC_FTRACE|DEBUG_FS|PROTECTED_NVHE"`
  全部为 y（注意：本树没有 CONFIG_TRACEFS 这个 Kconfig 符号，tracefs 设施随 tracing
  编译，不要 grep 它）；`grep XCORE_STATS include/generated/rustc_cfg`（build_rust.sh
  把 =y 配置传给 rustc，`#[cfg(CONFIG_XCORE_STATS)]` 即生效）
- tracefs 板上验证：Kylin V10 下 tracefs 随 debugfs 自动挂载于
  `/sys/kernel/debug/tracing`，确认 `/sys/kernel/debug/tracing/hypervisor/events/`
  存在（protected 模式）

**A2 PMU 最小修复**（前置到 gate 实验之前，不留到后面）：
现有 op 1 改写 PMCR_EL0/PMCCFILTR_EL0/MDCR_EL2，op 0 清 PMCR.E（stats.rs:20 起）——
不是纯观测，会破坏 host perf 的 PMU 状态：
- per-cpu save/restore：enable 时按 CPU 保存 PMCR_EL0/PMCCFILTR_EL0/MDCR_EL2/
  PMCNTENSET_EL0，disable 时按 CPU 恢复（现有 pmu_enabled 是全局标志，配置是 per-cpu 的）
- ⚠ PMCNTENSET_EL0 是 **set 型寄存器**，清位必须写 **PMCNTENCLR_EL0**。当前 Rust
  register patch 只导出 pmcntenset_el0、无 pmcntenclr_el0——现有 stats.rs 的 disable
  逻辑疑似无效。需新增 PMCNTENCLR_EL0 绑定（或 write_sysreg!(pmcntenclr_el0, mask)）
- 测试期间声明 cycle counter 由 xcore_stats 独占，host `perf stat` 的 cycles 事件不
  与其同时使用；所有测试脚本 `trap 'echo 0 > /proc/xcore_stats' EXIT`
- （为后续 nvhe 对照预埋）/proc/xcore_stats 门控(:288)放宽到 nvhe 也创建，**op 分级**：
  nvhe 只放行 PMU op（0/1）；op=2（mem stats，进 stats.rs:160 遍历 pKVM 页表）保持
  protected-only，hyp 侧 xcore_stats_entry 对 op=2 也按 protected 状态返回
  SMCCC_RET_NOT_SUPPORTED（双重防御，不信任 host 过滤）
- ⚠ host 侧返回值处理配套修复：当前 `xcore_get_mem_stats()` 只把 `res.a0 == 0` 当
  失败——hyp 返回 SMCCC_RET_NOT_SUPPORTED 这类负值时会被误当成 total_size。host 侧
  必须先判 res.a0 是否为 SMCCC 错误码（负值），再解释为数据

**A3 可用性确认**（板上）：pkvm 模式 `echo 1 > /proc/xcore_stats && cat` 能读到各
CPU EL2 cycles 且随 VM 操作增长；echo 0 后 host perf cycles 正常。

### Patch B：gate——munmap 窗口 EL2 判别实验（结果决定 C1/C2 路线）

只跑 `munmap_after_write_touch`（8/16/64 MB 三个 size），固定步骤：

1. 关 cpuidle（`/sys/.../cpuidle/stateX/disable`，PSCI SMC 会计入 EL2 cycles）、绑核
   （taskset 到固定 CPU，记下目标 CPU 号）
2. `echo 1 > /proc/xcore_stats` 完成 enable，`cat` 读**目标 CPU** 的 baseline
   （⚠ 现有接口语义是"必要时 enable + 读所有 CPU 的 PMCCNTR 累计值"，不是显式
   start/stop snapshot——必须自己做 baseline/delta）
3. 跑单个 benchmark phase
4. 再次 `echo 1 && cat`，取**同一 CPU** 的 delta；其他 CPU 的桶只作背景噪声参考
5. **empty-window control（必做）**：同样 baseline/delta 流程但不跑 benchmark——
   读 /proc/xcore_stats 本身走 HVC 进 EL2，第二次 echo 1 也带固定开销，用空窗读数
   扣除 xcore_stats 自身噪声底
6. 辅证（可选）：pkvm 模式下 tracefs 短窗开 hyp_enter/host_mem_abort/host_hcall
   事件数一下窗口内 EL2 入口次数（先 `echo 1024 > buffer_size_kb`）

**判读（gate 决策，Δ 均指扣除空窗噪声后的净值）**：
- **Δ(target CPU) 远小于 +205µs 对应的 cycle 量级**（如 <5%；EL2 进出至少数百
  cycle/次，高频低耗入口也会显形）→ 可排除 EL2 是主因 → 走 **C1**，不要先大规模插
  Rust mem_protect
- **Δ 与 +205µs 量级可比** → 假设(b) 成立可能性大 → 走 **C2** 定位 EL2 内站点
- 对照基线：同样步骤在 nvhe 模式跑一遍（Patch A 已放宽 procfs 门控 + PMU op）

### Patch C0：host 侧 L3 对照（与 Patch B 并行启动，纯脚本，无内核改动）

nvhe 与 pkvm 跑**同一套** host 侧观测，对比"同一函数耗时在哪一层膨胀"——这是当前
最可能解释（两类 host 侧机制）的直接证据：
- function_graph：`__vm_munmap`/`unmap_region`/`tlb_finish_mmu`/`zap_pte_range`
  - tlb_finish_mmu 膨胀为主 → TLBI/DSB 硬件成本
  - zap_pte_range 膨胀为主 → 两级 walk / dirty accounting / cache-TLB 交互
- kprobe/tracepoint 统计 `flush_tlb_mm` vs `__flush_tlb_range` 调用比例；先确认板子
  有无 FEAT_TLBIRANGE（ID_AA64ISAR0_EL1.TLB），决定 TLBI 数量模型
- `perf stat -e cycles,page-faults,r05(L1D_TLB_REFILL),r2d(L2D_TLB_REFILL),r34(DTLB_WALK),stall_backend`
  （⚠ 不与 xcore_stats PMU 同窗使用）
- 测量纪律：绑核、关 cpuidle、固定 THP/ASLR/频率（同 mmap-split 文档 §6 建议）
- 脚本与结果模板放 `docs/mmap/`，新增一篇插桩使用说明文档

### Patch C1（若 gate 判 EL2≈0）：host 侧深入 + TLBI 微基准

- out-of-tree 微基准模块：在 `kvm-arm.mode=protected / nvhe / none` 三模式下计时，
  量化 TLBI 的模式差（stage-2 使能后 TLBI 是 VMID-tagged 且需作废 combined entries，
  DVM 广播代价可能数倍）。
  ⚠ **必须复刻本内核 `__flush_tlb_range` 的实际路径**，不要写死单条 `TLBI VALE1IS`：
  按板子是否有 FEAT_TLBIRANGE 选 VALE1IS/VAAE1IS vs RVAE1IS、匹配实际的 DSB 类型
  （ish/ishst）、复刻 range 循环与 stride、以及超阈值升级 flush_tlb_mm（ASIDE1IS）
  的分支——否则测的是"某条 TLBI"而不是 munmap 实际用的 TLBI 模型（C0 的 kprobe
  统计先确认实际走哪条分支，微基准照着配）
- C0 的 funcgraph/perf 数据细化归因：TLBI 指令本身 vs flush 后的 walk/refill
- 产出直接对接优化方向：range/batch TLBI、减少 TLBI 触发面、延迟 teardown 等
  （对应 pkvm-mmap-optimization-plan.zh-CN.md §6.3）

### Patch C2（若 gate 判 EL2>0）：Rust hyp per-cpu 计数器 + 读取通道

L1 常开计数器（两种模式可用，不依赖 tracefs，无溢出，扰动极小）。
**站点列表按 gate 证据条件展开**：优先 handle_trap 分桶、host_hcall、host_mem_abort、
s2_try_enomem、unmap_unmoveable（假设(b) 判据链），其余站点视首批数据再加。

新增文件：
- `arch/arm64/kvm/hyp/include/nvhe/xcore_perf.h`：站点 enum（Rust/C 共享）
  - ⚠ bindgen 接入：必须同时在 `rust/src/bindings/bindings_helper.h` 加 `#include`。
    bindgen 规则只依赖 helper + bindgen_parameters（nvhe/Makefile:126-128），新头本身
    不在依赖列表——把 xcore_perf.h 加进该规则依赖（或注明单改它需 touch helper）
- `rust/src/perf_stats.rs`：`define_per_cpu!(PERF_SITES: [PerfSite{count,sum_ticks,max_ticks,sum_bytes}; NR_SITES])` + `site_count()/site_begin()/site_end()`
  - 写侧普通 u64 自增，前提假设"EL2 handle_trap 单 CPU 不可重入"——**实现时验证**
    （检查 hyp 的 SError/IRQ 屏蔽窗口）
  - 数据语义 = **best-effort 观测**：跨 CPU 读与写并发可能见到不一致 {count,sum,max}
    组合；正式采数**先停 workload 再 dump**

插桩站点（计时=cntpct 区间；热路径只 count 不计时）：

| 站点 | 位置 | 计时 | bytes | 优先级 |
|---|---|---|---|---|
| el2_hvc / el2_smc / el2_abort / el2_other 分桶 | hyp_main.rs handle_trap(:2975) match 臂 | 否 | - | P0 |
| hcall[id]（HOST_HCALL.len() 个桶 + dynamic 桶） | hyp_main.rs handle_host_hcall(:1619) | 否 | - | P0 |
| mem_abort 全程 / perm_fault | host.rs handle_host_mem_abort(:1979) 首尾 | 是 | - | P0 |
| **s2_try_enomem（假设(b)直接判据）** | host.rs host_stage2_try!(:334) ENOMEM 分支 | 否 | - | P0 |
| unmap_unmoveable | host.rs(:298) | 是 | - | P0 |
| s2_idmap | host.rs host_stage2_idmap(:1841) | 是 | range 大小 | P1 |
| s2_adjust_range（按 ret 分桶） | host.rs(:1750) | 否 | - | P1 |
| s2_map_ffi | host.rs __host_stage2_idmap(:359) | 是 | end-start | P1 |
| unmap_reg / set_owner / reclaim_page | host.rs :910 / :785 / :1891 | 是 | size | P1 |

读取通道（扩展 xcore_stats hcall）：
- `hyp_main.rs xcore_stats_entry(:1737)` 新增 op：3=read_site(cpu,site)→a0=status,
  a1=count,a2=sum_ticks,a3=max_ticks；4=read_aux(sum_bytes)；5=reset_all；
  6=read_hcall_count(cpu,id)；7=read_pool(free_pages)
  - op 分级：**3-6 两种模式可用；7 与 2 一样 protected-only**（op 7 读 pKVM host
    stage-2 的 HOST_S2_POOL 水位，nvhe 下语义不成立），非 protected 返回
    SMCCC_RET_NOT_SUPPORTED
  - **参数必须校验**（cpu<hyp_nr_cpus、site<NR_SITES、id<hcall 表长度）后再传
    per_cpu_ptr——`__hyp_per_cpu_offset` 有 bug_on，未校验参数 = host 可触发 hyp panic
  - hcall 桶数**不要硬编码 66**：hyp 侧由 `HOST_HCALL.len()` 导出，host 侧经共享常量
    （xcore_perf.h）取同一值——避免把当前表长固化成接口 ABI，hcall 表扩展时埋坑
  - 寄存器约定：a0=状态码（勿沿用 op 2 的"a0==0 即失败"——count 合法为 0）
- `arch/arm64/kvm/xcore_stats.c`：新增 seq_file 全量导出（遍历 cpu×site，含
  CNTFRQ→ns 换算）；写入触发 reset

### Patch D：HYP_EVENT 短窗采样（验证用，不作为主统计面）

仅在 C2 路线需要分布/逐事件细节时做：
- `kvm_hypevents.h`：**不改动现有 host_mem_abort**（原地加字段改 ABI，且 C 侧 :96 与
  Rust 侧 trace.rs:2108 双份定义漂移风险高），**末尾追加**：
  `host_mem_abort_done(esr,addr,ret,ticks)`、`host_s2_idmap(start,size,ret,ticks)`、
  `host_s2_unmap(start,size,reason)`
- `rust/src/trace.rs`：追加三个 hyp_event!（⚠ 两侧字段顺序/类型/cfg 门控严格一致，
  否则 id 错位；boot dmesg 的 nr_events 不匹配 WARN 是哨兵）
- `rust/src/mem_protect/host.rs`：handle_host_mem_abort 出口加 host_mem_abort_done
  （旧调用点 :1998,:2035 不动）+ idmap/unmap 路径加调用
- C 版 mem_protect.c（X1_RMS=n 变体）同步加调用点：低优先级尾巴
- 使用前 `echo 1024 > buffer_size_kb`（默认 7KB/cpu 必溢出），只在短跑窗口开启

## 结果判读矩阵（写进文档交付）

| 观测 | 结论 |
|---|---|
| gate：ΔPMCCNTR≈0（munmap 窗口，目标 CPU） | 假设(a)：硬件 TLBI/walk 开销 → C1，优化方向 = 减少 TLBI 触发面/range TLBI/延迟 teardown |
| gate：Δ>0；C2 中 s2_try_enomem>0、unmap_unmoveable 有计时、随后 mem_abort 风暴 | 假设(b)：池耗尽回收 → 优化 HOST_S2_POOL 容量/回收策略 |
| C2 中 mem_abort 稳态每迭代 ~touch 页数 | 旧 500ns/fault 模型复活（与 split 数据矛盾，需复核 page cache 状态） |
| C0：tlb_finish_mmu 膨胀 vs zap_pte_range 膨胀 | TLBI/DSB 成本 vs 两级 walk/dirty accounting 成本 |
| nvhe 模式 EL2 计数非零 | 测量污染（idle/IRQ），修方法学 |

## 验证

1. 编译：`make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- gwd3000_lenovox1d3000m_defconfig pkvm-prof.config && make -j$(nproc) Image`
   （若用 config fragment **必须**在 defconfig 目标后叠加 fragment 名或用
   `scripts/kconfig/merge_config.sh`，否则构建不带插桩配置；直接改 defconfig 则用原
   命令。Rust 经 nvhe/Makefile 调 build_rust.sh，需 nightly + aarch64-unknown-none；
   clippy deny lint 注意）
2. 符号（C2/D 阶段，两步——新事件的 hyp_event_id_* **定义**在 C event 生成对象，Rust
   侧只是 extern 引用）：
   - `nm -u .../rust/nvhe_rust.o | grep -E "hyp_event_id_host_s2|host_mem_abort_done"`
     确认 Rust 引用
   - 最终链接的 hyp 对象（kvm_nvhe.o）或 nvhe/events.o 上 `nm` 确认定义存在；
     perf_stats per-cpu 符号在 nvhe_rust.o 的 .data..percpu section 确认
3. 板上（参照 memory: n90-kernel-deploy）：
   - A3 可用性确认（见 Patch A）；dmesg 无 hyp events WARN
   - nvhe 模式：/proc/xcore_stats 可读（PMU op）、跑 lat_mmap 时 EL2 cycles≈0
   - C2 后稳态跑 mmap-split：counter 数与预期对照
4. 回归：插桩常开下复跑 mmap_write_touch_unmap，确认扰动 <2%（对比无插桩内核）

## 预估

| 项 | 规模 | 风险 |
|---|---|---|
| Patch A 配置+PMU 修复 | 配置若干行 + PMU save/restore ~80 行 | 低-中：PMCNTENCLR 绑定 |
| Patch B gate 实验 | 脚本 ~60 行，半天-1 天出判别数据 | 低 |
| Patch C0 host 对照脚本 | ~150 行脚本 + 文档 | 低 |
| Patch C1（条件） | 微基准模块 ~120 行 | 低 |
| Patch C2（条件） | ~310 行 Rust+头文件 + 读取通道 ~280 行 | 中：percpu 链接、bug_on 防护、op 安全边界 |
| Patch D（条件） | ~160 行（定义+调用点+一致性验证） | 中：双侧定义一致性 |
| 合计 | A+B+C0 必做 ≈1.5-2 天；C1/C2/D 按 gate 结果选路 | |

## 风险清单

1. **EL2 bug_on 即 hyp panic**：hcall 参数（cpu、site、hcall id）必须校验后再用
2. **勿放宽 hyp tracefs 的 protected 门控**（nvhe 下 share/donate hcall 会在未初始化
   host_mmu 上崩）；/proc/xcore_stats 放宽必须按 op 分级（2/7 protected-only）
3. **PMU 状态污染**：op 0/1 改写 PMCR/PMCCFILTR/MDCR_EL2；save/restore per-cpu；
   清位走 PMCNTENCLR_EL0；脚本 trap 兜底；与 host perf cycles 不同窗
4. **CNTFRQ 分辨率**：先读 CNTFRQ_EL0 确认（24MHz≈41ns/tick 时 max 值粗糙），
   PMCCNTR 互补
5. **HYP_EVENT 双侧定义漂移**：字段顺序/类型/cfg 门控严格一致；dmesg WARN 哨兵
6. **观察者效应**：热路径只 count；事件只短窗开；counter 为 best-effort 语义
7. **测量污染**：cpuidle PSCI SMC、IRQ、CPU 漂移——绑核+关 idle+per-CPU 单独看
