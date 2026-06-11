# pKVM munmap teardown 回归：EL2 判别(gate)与 host 侧对照(C0)实测报告

**平台**：N80 / Kylin V10 SP1 / aarch64 / 内核 `6.6.30xcore-stat+`（Rust nVHE hyp，`CONFIG_X1_RMS=y`）
**日期**：2026-06-11
**前置**：mmap-split 已把 pKVM 下 host 侧 `lat_mmap` 的退化定位到 **`munmap_after_write_touch`**（写触摸后解除映射的 teardown）。
**本报告回答**：这笔多花的时间**是否进入 EL2**；若不在 EL2，**在 host 侧的哪一层**。

---

## 0. 摘要（结论先行）

1. **EL2 gate（protected）**：`munmap_after_write_touch` 及所有触页模式的 EL2 周期增量 **ΔEL2 = 0**。EL2 PMU 计数器经阳性对照验证可用（200 次页表遍历 HVC 实测累加 1.68 亿 cycle）。→ **host munmap 不进 EL2，排除"隐藏 EL2 路径"假设，路线定为 C1（host 侧）。**
2. **host 侧对照（C0，protected vs nvhe，64MB×50）**：pKVM 比 nvhe **慢 1.81×**（wall 0.0500s vs 0.0277s，+447µs/iter）。

   | 指标 | nvhe | protected | 差 |
   |---|---:|---:|---|
   | cycles | 49,032,232 | 88,812,432 | **+39.78M (+81%)** |
   | instructions | 81,894,221 | 81,942,093 | +0.06%（≈相同） |
   | **stall_backend** | 18,167,855 | 59,061,228 | **+40.89M (+225%)** |
   | page-faults | 21,013 | 21,011 | ≈0 |
   | l1d_tlb_refill | 47,702 | 55,870 | +17% |
   | l2d_tlb_refill / dtlb_walk | 21,658 / 21,453 | 21,614 / 21,371 | ≈0 |

3. **归因**：额外的 +39.78M cycles **几乎全部（+40.89M）来自 backend(访存)停顿**；指令数、缺页数、TLB walk 次数两模式**完全相同**。→ 回归不是"软件多做事"、不是"TLBI 数量爆炸"、不是"多进 EL2"，而是 **host stage-2 使能后，munmap teardown 的页表遍历/页结构访问每次都过两级翻译，访存停顿放大**（文档假设 **a-2**）。
4. **下一步**：C1——查 host stage-2 映射粒度（block vs page），降低 teardown 访存的 stage-2 翻译开销。

---

## 1. 背景与核心问题

### 1.1 体系结构前提：host munmap 理论上不进 EL2

本内核跑 **Rust nVHE hypervisor**，运行时以 `kvm-arm.mode` 区分：
- **protected（pKVM）**：host 运行在 EL1，其物理内存受 **host stage-2 页表**保护（IPA→PA 第二级翻译），EL2 是受信任的 hypervisor。
- **nvhe**：同一套 hyp 对象，但 host 不受 stage-2 隔离（对照基线）。

在 nVHE 下，host 的 EL1 执行**只有以下情况进入 EL2**：显式 hypercall（HVC）、被陷的指令/寄存器访问（trap，由 `HCR_EL2` 各 trap 位控制）、或 host stage-2 异常。这点直接体现在 host 异常分发 `handle_trap()`（`arch/arm64/kvm/hyp/nvhe/rust/src/hyp_main.rs:2985`）的 match 臂上——只有这几条：

```rust
match ec {
    HVC64 => host_ctxt.handle_host_hcall(),                              // hypercall
    SMC64 => host_ctxt.handle_host_smc(),                               // SMC(protected 下 trap)
    TrappedFP | TrappedSve | TrappedSME => fpsimd_host_restore(),       // FP/SVE 惰性恢复
    InstrAbortLowerEL | DataAbortLowerEL => host_ctxt.handle_host_mem_abort(), // stage-2 异常
    _ => { /* 默认 handler，否则 bug_on */ }
}
```

而普通 `munmap` 这三条都不触发，**代码证据**如下：

- **不发 hypercall**：munmap 走通用 mm 路径（`__vm_munmap`→…→`unmap_vmas`/`tlb_finish_mmu`），其 TLB 作废用 arm64 的 `__tlbi()` 宏**直接发 `tlbi` + `dsb ish` 指令**（`arch/arm64/include/asm/tlbflush.h:33`：`asm("tlbi " #op "\n" "dsb ish ...")`），不是 HVC。
- **host 的 `TLBI`/`DSB` 不被 trap**：要把"EL1 发起的 TLB 维护"陷入 EL2，需在 `HCR_EL2` 置 `TTLB`(bit25)/`TTLBIS`(bit54)/`TTLBOS`(bit55)（`arch/arm64/include/asm/kvm_arm.h:49,22,21`）。而 host 的 HCR 值**都不含这些位**：
  ```c
  #define HCR_HOST_NVHE_FLAGS           (HCR_RW | HCR_API | HCR_APK | HCR_ATA)   // kvm_arm.h:101
  #define HCR_HOST_NVHE_PROTECTED_FLAGS (HCR_HOST_NVHE_FLAGS | HCR_TSC)          // kvm_arm.h:102
  ```
  并在 `arch/arm64/kvm/arm.c:1887/1889` 写入 host 的 `params->hcr_el2`（protected 用后者，仅多一个 `TSC`=trap SMC；nvhe 用前者）。所以 host 的 `tlbi`/`dsb` 在 EL1 直接执行、不陷入——这也正是上面 `handle_trap` 里**没有任何 TLBI/sysreg-TLB 维护臂**的原因。
- **对已映射的 host 页，访问/解除映射不触发 stage-2 异常**：pKVM 下 host 内存按"host 拥有 + 恒等映射"管理。`host_stage2_idmap()`（`mem_protect/host.rs:1841`）以 `default_host_prot()` 把范围恒等映射给 host，并用 `host_stage2_adjust_range()` 取尽量大的 block 级别。**首次**访问从未映射的范围会触发一次 `host_mem_abort`→idmap（`host.rs:1979`），但**此后该页再被访问/解除映射都不再缺页进 EL2**。（实测佐证：§6.2 中连 `write_touch_cold`（触碰已驻留的 file 页）的 ΔEL2 也是 0。）

所以理论上 host munmap 几乎全程在 EL1 完成、**基本不进 EL2**。那么 mmap-split 观测到的额外时间从哪来？两个假设：

```
(a) 纯硬件/stage-2 开销 —— host stage-2 使能后，munmap teardown 的 TLBI 广播变贵，
    和/或两级(stage-2)页表 walk / 访存 / cache-TLB 交互成本被放大（EL2 软件不背锅）
(b) 隐藏 EL2 路径 —— 例如页表页池耗尽触发回收，进而 abort 风暴
```

**执行原则**：先用 EL2 周期计数**判别**额外时间是否进 EL2（gate）。若 ΔEL2≈0，排除(b)，重心放 host 侧分析（C1）；若 ΔEL2 与退化量级可比，再去 hyp 内部细粒度插桩（C2）。这一步避免在注定读数为 0 的 hyp 站点上空耗。

---

## 2. 测量原理：PMU 是什么，怎么测"EL2 里花了多少周期"

### 2.1 先认识 PMU（性能监控单元）

**PMU（Performance Monitoring Unit）是 CPU 核内置的一组硬件计数器**，专门用来"数"微架构事件——CPU 时钟周期、退休指令数、cache 缺失、TLB 重填、流水线停顿等等。三个关键特性：

- **硬件免费计数**：计数完全由硬件做，几乎不占 CPU 时间，不像在代码里打点那样有可观开销。
- **可编程选事件**：每个计数器可以"选"数哪种事件，事件用编号标识。例如 ARM 上 `0x11`=CPU_CYCLES、`0x08`=INST_RETIRED（退休指令）、`0x05`=L1D_TLB_REFILL、`0x34`=DTLB_WALK、`0x24`=STALL_BACKEND（后端/访存停顿周期）——正是本报告 C0 的 perf 用到的事件。
- **用法套路**：选事件 → 清零/记基线 → 跑负载 → 读计数器 → 取差，差值即这段时间内该事件发生的次数（或周期数）。

ARM64 上有一个**专用 64 位周期计数器** `PMCCNTR_EL0`（cycle counter）和若干通用计数器。C0 用的 `perf` 就是 Linux 给 PMU 的通用前端（经 `perf_event_open` 让内核替你配置 PMU）。也正因 gate 与 perf **用同一套物理 PMU**，二者不能同窗（§4.4 的"PMU 独占"纪律）。

### 2.2 关键招式：按异常级过滤，只数 EL2 的周期

普通 cycle counter 数**所有**时间的周期，分不清是 EL1（host）还是 EL2（hyp）花的。ARM PMU 支持**按异常级过滤**：`PMCCFILTR_EL0` 能配置"周期计数器只在某些异常级执行时才递增"。把它配成"**只数 EL2**"，则 `PMCCNTR_EL0` 的读数就只是该 CPU 累计花在 EL2 的周期数；窗口前后相减 = 这段时间进 EL2 的总耗时。这就是 gate 判别"munmap 是否进 EL2"的原理。

对应代码 `stats.rs::xcore_enable_pmu_el2()`（`arch/arm64/kvm/hyp/nvhe/rust/src/stats.rs:48`）做四件事：

```
MDCR_EL2 |= bit7 (HPME)          // stats.rs:61  使能 EL2 的 PMU
PMCCFILTR_EL0 = bit31|30|27|26   // stats.rs:18,68  屏蔽 EL1/EL0、放行 EL2 → 只数 EL2 周期
PMCNTENSET_EL0 |= bit31          // stats.rs:74  打开 cycle counter
PMCR_EL0: E(b0)使能 + LC(b6)64位防溢出 + C(b2)一次性归零 + 清 D(b3)÷64分频   // stats.rs:78+
```
（`PMCCFILTR_EL2_ONLY = bit31|bit30|bit27|bit26`：bit31/30 屏蔽 EL1/EL0 计数，bit27/26 放行非安全 EL2/EL3 计数，净效果即"只在 EL2 累加"。）

### 2.3 读数路径 与"为何只在 pKVM 可用"

读数本身在 **EL1** 完成、不进 EL2：host 侧 `xcore_get_cpu_stats_on_cpu()`（`xcore_stats.c:91`）直接 `read_sysreg(PMCCNTR_EL0)`，故读取对被测 EL2 周期的污染≈0。开关与读取经 `/proc/xcore_stats` 触发，对每个在线 CPU 用 `smp_call_function_single` 就地执行（`xcore_stats.c:108-114`）：

- `echo 1`：**首次**（`if (!pmu_enabled)`，`xcore_stats.c:230`）才对每 CPU 发 enable HVC，其后只读不再 enable。→ 计数器只在首次被 `PMCR.C` 复位一次、之后**持续累加**（§4.2 用阳性对照实测确认）。
- enable/disable 走 pKVM 专用 hcall `__pkvm_xcore_stats`，由 **protected 模式**的 host-hyp 调用分发处理；普通 nvhe 下该分发不放行，HVC 返回 `-ENOTSUPP`。

> **因此 nvhe 侧无法用本 gate 读 EL2 周期**——但 nvhe 是对照基线，其 host munmap 同样不会因 pKVM 进 EL2，且 nvhe 侧我们只需要 wall/perf/funcgraph（见 §4.3），不依赖本计数器。

---

## 3. 插桩与基础设施（代码级）

### 3.1 hyp 侧 EL2 PMU 配置 —— `arch/arm64/kvm/hyp/nvhe/rust/src/stats.rs`

`xcore_enable_pmu_el2()`（stats.rs:48）的寄存器配置见 §2.2。除此之外它**按 per-cpu 保存原 PMU 现场**（PMCR/PMCCFILTR/MDCR/PMCNTENSET），`xcore_disable_pmu_el2()` 时恢复，避免污染 host 自己的 `perf`；清位用 `PMCNTENCLR_EL0`（PMCNTENSET 是 set 型寄存器，`&~bit` 无效）。

> **方法学要点（PMCR.C 复位）**：`C`(bit2) 是"写 1 复位计数器"且自清（读回为 0）。若**每次** enable 都置 C，会在每次读取前把累计值清零、使 delta 恒为 0。实际不会发生——host 侧 `if (!pmu_enabled)` 门控（§3.2）使 **enable（含复位）只发生一次**，之后只读不复位，计数器持续累加。§4.2 用阳性对照实测确认了这一点。

### 3.2 host 侧接口 —— `arch/arm64/kvm/xcore_stats.c`

`/proc/xcore_stats`（0666）写入触发，按 op 分发，并对所有在线 CPU 用 `smp_call_function_single` 就地执行：
- `echo 0`：每 CPU 发 disable HVC（恢复原 PMU 现场）。
- `echo 1`：**首次**（`if (!pmu_enabled)`）每 CPU 发 enable HVC；随后每 CPU 在 **EL1** 读 `PMCCNTR_EL0` 存入 `global_cpu_stats[]`。→ 后续 `echo 1` 只读不再 enable，故计数器不被复位。
- `echo 2`：mem stats HVC（遍历 pKVM 页表，**仅 protected**；非 protected 返回 `SMCCC_RET_NOT_SUPPORTED`，host 侧也按 `is_protected_kvm_enabled()` 双重防御）。
- `cat`：按 `last_operation` 显示各 CPU `<cpu> <cycles> <timestamp>`。

### 3.3 trace 设施（辅证用）

- **HYP_EVENT**：`hyp_enter`/`host_mem_abort`/`host_hcall`/`__hyp_printk` 等事件，hyp 侧无条件生成。
- **hyp tracefs**：`/sys/kernel/debug/tracing/hypervisor/`（Kylin V10 把 tracefs 挂在 debugfs 下）。**仅 protected 模式可用**（`hyp_trace.c` 门控；nvhe 下 buffer load 走 share/donate hcall 会在未初始化 host_mmu 上 panic，勿放宽）。
- `trace_hyp.sh <0|1>`：开/关 `__hyp_printk` 事件（`trace_hyp_printk`/`trace_debug!` 的载体）。**有性能影响，用后必关**，只做短窗"是否走到这里"标记，不作主统计。

---

## 4. 测试设计与脚本

### 4.1 Patch B — EL2 gate：`scripts/el2-gate-bench.sh`

判别 munmap 窗口的额外时间是否进 EL2。脚本固定流程（核心循环）：
```bash
read_el2_cycles() { echo 1 > /proc/xcore_stats; awk -v c=$CORE '$1==c{print $2}' /proc/xcore_stats; }
# 绑核(taskset) + 关 cpuidle(PSCI idle 会计入 EL2) + 锁频(performance)
echo 1 > /proc/xcore_stats                       # 首次 enable(含一次复位)
for size in $SIZES; do
  c0=$(read_el2_cycles); t0=$(date +%s.%N)
  taskset -c $CORE $BENCH $MODE_ARG $size $ITERS $FILE ...   # 只跑被测项
  t1=$(date +%s.%N); c1=$(read_el2_cycles)
  delta=$((c1-c0)); wall=t1-t0
  e0=$(read_el2_cycles); sleep $wall; e1=$(read_el2_cycles)  # 等时长空窗
  empty=$((e1-e0)); net=$((delta-empty))                     # 扣背景 EL2 噪声
done
```
- **baseline/delta**：接口语义是"累计值"，脚本自己取同一 CPU 前后差。
- **空窗扣噪声**：跑等时长 `sleep` 测背景 EL2 活动并扣除。
- **判读口径**（64MB）：额外 µs × CPU GHz ≈ 额外 cycle 预算（N80：若 +447µs × 1.8GHz ≈ **80 万 cycle/iter**）。`net/iter` 远小于它（<5%）→ 非 EL2(假设 a)；量级可比 → 隐藏 EL2 路径(假设 b)。

### 4.2 计数器活性验证（关键的方法学一步）

gate 读出全 0 时，必须排除"计数器根本没在数"。判别过程：
1. **红鲱鱼**：曾怀疑"每次读都复位"。复查 `xcore_stats.c` 发现 `if(!pmu_enabled)` 门控——enable（及其复位）只发生一次，之后只读。排除。
2. **阳性对照**：需要一个**确定进 EL2 且不碰 PMU 开关**的负载。`echo 2`(op2，mem stats) 是一次 HVC，进 EL2 遍历 pKVM 页表（EL2 工作量大）。在目标 CPU 上连打 200 次，读计数器前后差：

   > **结果**：A=57 → B=168,083,716，**ΔEL2 = 168,083,659 cycle**（≈84 万 cycle/次页表遍历 HVC）。计数器在真有 EL2 负载时精确累加 → **计数器工作正常**。

   （首次 enable 读到的 57 cycle，正是那次 enable HVC 复位后到 `eret` 之间的 EL2 周期，本身也佐证计数器在数 EL2。）

### 4.3 Patch C0 — host 侧对照：`scripts/host-mm-trace.sh`

不依赖 EL2 计数器，两模式都能跑，回答"成本在 host 的哪一层"。三个子命令：

**(1) `tlbirange`** —— 决定 TLBI 数量模型。用户态对 ID 寄存器的 MRS 被内核仿真，可直接读 sanitised 值：
```c
asm("mrs %0, ID_AA64ISAR0_EL1" : "=r"(isar0));
tlb = (isar0 >> 56) & 0xf;   // 2 = 支持 FEAT_TLBIRANGE(range TLBI)
```

**(2) `perf`** —— host PMU 事件，区分"TLBI 指令贵"还是"flush 后 walk/refill 贵"：
```bash
perf stat -e cycles,instructions,page-faults,l1d_tlb_refill,l2d_tlb_refill,r34,stall_backend \
  -- taskset -c $CORE $BENCH munmap_after_write_touch 64 50 ...
```
- `dtlb_walk` 在本机 sysfs 未暴露命名事件，用裸码 **`r34`**（=DTLB_WALK，0x34）；`l1d/l2d_tlb_refill`、`stall_backend` 由 PMU 驱动经 sysfs 暴露，按名可用。
- **与 xcore EL2 PMU 独占**：`do_perf` 先 `echo 0 > /proc/xcore_stats` 释放 cycle counter，二者不同窗。

**(3) `funcgraph`** —— `__vm_munmap` 子树逐函数耗时，区分 `tlb_finish_mmu`(TLBI/DSB) vs `zap_pte_range/unmap_vmas`(两级 walk/释放页)：
```bash
echo __vm_munmap > set_graph_function; echo 12 > max_graph_depth   # 够深覆盖 zap 层
echo 1 > options/funcgraph-tail                                     # "}" 行补 /* 函数名 */，否则非叶函数无法按名归集
echo 65536 > per_cpu/cpu$CORE/buffer_size_kb                        # 只给目标核调大缓冲，防环形缓冲冲掉子树
# funcgraph 单独用少量迭代(FG_ITERS=5)：per-function 取平均，几次即可
cat per_cpu/cpu$CORE/trace > out                                    # 只取目标核
```
> **本次修复的两个 funcgraph 坑**：① 主 tracefs 默认 ~1.4MB/cpu 环形缓冲，50 iter 海量事件把 munmap 子树冲掉 → 只给目标核调大 per-cpu buffer + 降迭代；② 默认非叶函数耗时打在**无名** `}` 行，汇总正则只能匹配带名行 → 只看到叶子(`tlb_finish_mmu`)。开 `funcgraph-tail` + 深度 6→12 后，`unmap_vmas`/`free_pgtables` 等才正确归集。
> **funcgraph 可信度边界**：绝对耗时被 trace 自身开销淹没（见 §6.5，nvhe 绝对值反而比 protected 大，与 perf 相反），**只用于看结构（哪个子树占比大），回归幅度一律以 perf elapsed 为准**。

### 4.4 测量纪律

- 绑核（`taskset -c 0`）、关 cpuidle（state0–3，PSCI SMC 计入 EL2）、`scaling_governor=performance` 锁频 1.8GHz。
- **PMU 独占**：gate(xcore EL2 PMU) 与 C0 perf(host PMU) 不同窗；funcgraph 有开销，单独跑。一次启动顺序：gate →(echo 0)→ tlbirange → perf → funcgraph。
- 对照量：`page-faults`/`instructions` 两模式相同，作为"同一负载"的对照锚点。

---

## 5. 测试如何进行

- **provisioning**：板上原生编译 `mmap_split_bench`；部署三个脚本；确认 `/proc/xcore_stats`、`/sys/kernel/debug/tracing/hypervisor/`、`perf`、`CONFIG_XCORE_STATS/TRACING/FUNCTION_GRAPH` 就位；锁频。
- **protected 启动**：跑 计数器阳性对照 → gate(8/16/64MB) → C0(tlbirange/perf/funcgraph)。
- **nvhe 启动**：gate 因 pKVM-only 返回 ENOTSUPP（预期）→ 跳过；跑 C0(tlbirange/perf/funcgraph) 取对照。
- 结果存 `results/n80-munmap-gate-c0/{protected,nvhe}/`。

---

## 6. 全部测试结果

### 6.1 EL2 计数器阳性对照（protected）
| 负载 | ΔEL2 cycle | 含义 |
|---|---:|---|
| 200× op2 页表遍历 HVC（CPU0） | **168,083,659** | 计数器随真实 EL2 负载精确累加 → 可用 |

### 6.2 EL2 gate（protected，`el2-gate-protected.csv`，ITERS=100）
| size | el2_cycles_delta | el2_cycles_empty | **net** | wall_s |
|---:|---:|---:|---:|---:|
| 8 MB | 0 | 0 | **0** | 0.015 |
| 16 MB | 0 | 0 | **0** | 0.026 |
| 64 MB | 0 | 0 | **0** | 0.097 |

补充判别（ITERS=20，确认触页模式也不进 EL2）：`mmap_write_touch_unmap` net=0、`write_touch_cold` net=0、`munmap_after_write_touch` net=0。

### 6.3 板子常数
- CPU：1.8 GHz（`scaling_cur_freq=1800000`，governor=performance）；cpuidle state0–3 存在（测试时关闭）。
- `ID_AA64ISAR0_EL1 = 0x0000111110212120`，TLB 域[59:56]=**0** → **FEAT_TLBIRANGE: NO**（host munmap 走逐页 TLBI 或升级为整表/ASID flush）。

### 6.4 C0 — perf（`munmap_after_write_touch` 64MB ×50，core0）
| 事件 | nvhe | protected | Δ(prot−nvhe) |
|---|---:|---:|---:|
| wall elapsed (s) | 0.027650 | 0.049980 | **×1.81 / +447µs/iter** |
| cycles | 49,032,232 | 88,812,432 | **+39,780,200 (+81%)** |
| instructions | 81,894,221 | 81,942,093 | +47,872 (+0.06%) |
| IPC | 1.67 | 0.92 | −45% |
| **stall_backend** | 18,167,855 | 59,061,228 | **+40,893,373 (+225%)** |
| page-faults | 21,013 | 21,011 | −2 (≈0) |
| l1d_tlb_refill | 47,702 | 55,870 | +8,168 (+17%) |
| l2d_tlb_refill | 21,658 | 21,614 | −44 (≈0) |
| dtlb_walk (r34) | 21,453 | 21,371 | −82 (≈0) |

### 6.5 C0 — funcgraph（5 iter，**绝对值含 trace 开销，仅看结构**）
| 函数 | protected total/avg µs | nvhe total/avg µs |
|---|---:|---:|
| `__vm_munmap`（整体） | 22532 / 1877 | 25679 / 2140 |
| `unmap_vmas` | 21864 / 1822 | 25015 / 2085 |
| `free_pgtables` | 194 / 16 | 180 / 15 |
| `tlb_finish_mmu`（最终 flush） | 108 / 9 | 109 / 9 |
| `tlb_flush_mmu`（walk 内批量 flush） | 1609（24 次） | 4205（425 次） |

结构一致结论：**`unmap_vmas` 占 munmap 的 ~97%**，`free_pgtables`/`tlb_finish_mmu` 都很小。（两模式绝对值倒挂，证明 funcgraph 不可用于幅度比较，见 §7.4。）

---

## 7. 结果分析

### 7.1 gate：退化不在 EL2 → 路线 C1
计数器已验证可用（§6.1，1.68 亿 cycle），而 `munmap_after_write_touch` 及所有触页模式 **ΔEL2=0**（§6.2）。预算上限是 ~80 万 cycle/iter，实测 0 << 5%。→ **排除假设(b)（隐藏 EL2 路径），host munmap 确实全程在 EL1**。不需要在 hyp `mem_protect` 里细粒度插桩（C2），重心转 host 侧（C1）。
（这也复证了体系结构预期：本 pKVM 下 host 内存默认 stage-2 恒等映射，普通 mmap/touch/munmap 不触发 `host_mem_abort`。）

### 7.2 回归 = backend 访存停顿（铁证）
N80 强复现回归：protected 比 nvhe 慢 **1.81×**（+447µs/iter @64MB，比 Kaitian 的 +205µs 更大）。关键在差分结构：
- **额外 +39.78M cycles ≈ 额外 +40.89M backend 停顿**——多出来的周期几乎 100% 是 backend(访存)停顿。
- **instructions、page-faults、l2d_tlb_refill、dtlb_walk 两模式完全相同**——同样的指令、同样的缺页、同样的页表 walk 次数。
- IPC 从 1.67 掉到 0.92——同样的指令流，protected 下停顿剧增。

这一组对照同时**排除**了三类解释：① 不是多进 EL2（gate=0）；② 不是软件多做事或多缺页（指令/缺页相同）；③ 不是 TLBI 数量爆炸（`tlb_finish_mmu` 仅 108µs，TLBI/walk 次数相同）。**唯一变量是：同样的访存在 host stage-2 下更慢。**

### 7.3 体系结构归因（假设 a-2）
protected 模式下 host 的每次物理访存都要过 **stage-2（IPA→PA）第二级翻译**。即使 host 内存在 stage-2 恒等映射（不缺页），**TLB miss 时的页表 walk 变成嵌套 walk**：stage-1 的每一级都要再经 stage-2 翻译，单次 walk 的访存次数成倍增加；combined/stage-2 TLB 条目也加大 TLB 压力。`munmap` teardown 的 `zap_pte_range` 要遍历并拆掉 stage-1 页表、并触碰数千个 `struct page`——这些访存中每一次 TLB miss 都付更贵的嵌套 walk，于是 **backend 停顿放大**。TLBI 指令本身数量没变（host 照发），贵的是 **walk/访存**，不是 TLBI。这正是文档的 **假设 a-2**。

### 7.4 为什么不用 funcgraph 判幅度
funcgraph 绝对耗时显示 **nvhe(2140µs) 比 protected(1877µs) 还慢**，与 perf（protected 慢 1.81×）**相反**。原因：function_graph 给每个函数进/出插桩，开销叠加在被测时间上，对 `zap` 这种深而频繁的子树尤甚，足以淹没真实差异。故 funcgraph **只用于确认结构**（`unmap_vmas` 主导），**回归幅度以 perf elapsed 为准**。`tlb_flush_mmu` 次数两模式差异大（24 vs 425）可能反映批量 flush 策略不同，但同受 trace 噪声影响，本报告不据此下结论。

### 7.5 FEAT_TLBIRANGE=NO 的含义
N80 无 range TLBI，host munmap 的 TLB 作废走逐页 `TLBI` 或升级为整表/ASID flush。但 perf 显示 TLB refill/walk 次数两模式相近、`tlb_finish_mmu` 占比极小——说明**本回归的瓶颈不在 TLBI 条数**，range TLBI 的有无对本退化不是主因（但仍是 C1 微基准要量化的旁证）。

---

## 8. 结论与下一步（C1）

**结论**：pKVM 下 host `munmap_after_write_touch` 的退化**不在 EL2、不在 TLBI 数量、不在多做的软件工作**，而是 **host stage-2 嵌套翻译使 teardown 的页表 walk / 页结构访存的 backend 停顿放大**（假设 a-2）。N80 上为 +447µs/iter @64MB（×1.81）。

**C1 优化方向**（对应 `pkvm-mmap-optimization-plan.zh-CN.md §6.3`）：
1. **查 host stage-2 映射粒度**：若 teardown 区域在 host stage-2 是页(4K)粒度，嵌套 walk 更深、stage-2 TLB 压力更大；改用 **block 映射(2M/1G)** 可直接降低 walk 访存与 TLB 压力——这是与本报告归因最直接对接的杠杆。
2. **stage-2 walk 成本微基准**：量化 block vs page 粒度下单次访存/walk 的停顿差，验证 (1)。
3. 评估减少 teardown 期间 stage-2 触碰面 / 延迟回收。

**数据归档**：`results/n80-munmap-gate-c0/{protected,nvhe}/`（gate CSV、perf txt、funcgraph 汇总与原始 trace、tlbirange）。
**脚本**：`scripts/{el2-gate-bench.sh, host-mm-trace.sh, trace_hyp.sh}`。

**内核插桩（Patch A）**：`docs/mmap/patch-a-xcore-instrumentation.diff`（stats.rs / xcore_stats.c / hyp_main.rs / defconfig 的 EL2 PMU 计数改动；正文 §2/§3 已逐行引用）。
