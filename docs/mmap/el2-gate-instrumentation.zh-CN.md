# EL2 判别实验与 host 侧对照观测使用说明

**日期**：2026-06-11
**适用**：pKVM mmap 性能调优第二步（插桩）的 Patch A/B/C0
**前置结论**：mmap-split 已定位 `munmap_after_write_touch` 为主要退化点
（64MB +227%，见 [mmap-split-kaitian-pkvm-comparison.zh-CN.md](mmap-split-kaitian-pkvm-comparison.zh-CN.md)）。
本步骤回答：**这 +205µs 是否花在 EL2 里**。host munmap 理论上不进 EL2（host TLBI
不被 trap、无 hypercall），所以这是整个优化路线的分叉点：

```
EL2 cycles ≈ 0 → 假设(a)：host stage-2 使能后的硬件开销（TLBI/DSB/两级 walk）
                 → 后续走 host 侧分析（C1），不做 hyp 细粒度插桩
EL2 cycles 与退化量级可比 → 假设(b)：隐藏 EL2 路径（如 HOST_S2_POOL 耗尽回收）
                 → 后续走 hyp per-cpu counter（C2）定位站点
```

## 1. 内核改动（Patch A，本仓库）

| 文件 | 改动 |
|---|---|
| `arch/arm64/configs/gwd3000_lenovox1d3000m_defconfig` | `CONFIG_XCORE_STATS=y`；显式固定 `FTRACE/FUNCTION_TRACER/FUNCTION_GRAPH_TRACER/DYNAMIC_FTRACE/DEBUG_FS` |
| `arch/arm64/kvm/hyp/nvhe/rust/src/stats.rs` | PMU 配置 per-cpu save/restore（enable 保存 PMCR/PMCCFILTR/MDCR_EL2/PMCNTENSET，disable 恢复）；清 cycle counter 改写 **PMCNTENCLR_EL0**（原 `PMCNTENSET & ~bit` 写法对 set 型寄存器无效） |
| `arch/arm64/kvm/hyp/nvhe/rust/src/hyp_main.rs` | `xcore_stats_entry` op=2（mem stats）非 protected 模式返回 `SMCCC_RET_NOT_SUPPORTED`（遍历 pKVM 页表，nvhe 下未初始化） |
| `arch/arm64/kvm/xcore_stats.c` | procfs 门控放宽到普通 nvhe（PMU op 两模式可用；VHE/mode=none 不创建）；op=2 host 侧 protected-only；`xcore_get_mem_stats` 改判 SMCCC 负值错误码（原 `a0==0` 判错会把 `NOT_SUPPORTED` 当成 total_size） |

`/proc/xcore_stats` 语义（0666，普通用户可用）：

```text
echo 0  禁用 EL2 PMU 计数并恢复各 CPU 原 PMU 配置
echo 1  （必要时）启用 EL2-only cycle 计数 + 读取所有 CPU 的 PMCCNTR 累计值
echo 2  pKVM 内存统计（仅 protected 模式）
cat     显示最后一次读取结果；CPU 行格式: <cpu> <cycles> <timestamp>
```

注意：**enable 后 cycle counter 由 xcore_stats 独占**，期间不要用 host
`perf stat` 的 cycles/相关 PMU 事件；测完 `echo 0` 恢复。脚本里已有
`trap 'echo 0 …' EXIT` 兜底。

## 2. Kaitian 环境事实（2026-06-11 实测）

```text
hostname ryuu，6.6.30+，当前 cmdline kvm-arm.mode=protected
CPU 1.9 GHz（scaling_cur_freq=1900000），arch timer 50 MHz（20ns/tick）
无 cpuidle states（PSCI idle 噪声基本不存在，脚本兼容处理）
有 perf/taskset/gcc/python3，无 trace-cmd（脚本用裸 tracefs）
benchmark：~/kylin-lmbench/experiments/mmap-split/mmap_split_bench
  <mode> <size_mb> <iters> <file> [touch_divisor] [stride_kb] [warmups]
ID 寄存器 sysfs 未暴露 → FEAT_TLBIRANGE 用 MRS 仿真在用户态读（脚本自动编译）
```

## 3. Patch B：gate 实验步骤

```bash
# 1) 安装插桩内核（Rust 变体，CONFIG_XCORE_STATS=y），分别以
#    kvm-arm.mode=protected 和 kvm-arm.mode=nvhe 启动各跑一轮

# 2) 板上执行（脚本在 scripts/）
CORE=0 SIZES="8 16 64" ITERS=100 ./el2-gate-bench.sh /tmp/gate-out

# 3) 输出 /tmp/gate-out/el2-gate-<mode>.csv：
#    mode,bench,size_mb,iters,el2_cycles_delta,el2_cycles_empty,el2_cycles_net,wall_s,cpu_khz
```

脚本固定流程：绑核 → （如有）关 cpuidle → enable PMU → 读目标 CPU baseline →
跑单项 benchmark → 读同 CPU delta → 等时长空窗再测一次作噪声对照 → `echo 0` 恢复。

### 判读

以 64MB 为例：pKVM 相对 NVHE 额外 ≈ 205 µs/iter，换算 EL2 周期上限
≈ 205µs × 1.9GHz ≈ **39 万 cycles/iter**。

| 观测（净值/iter） | 结论 | 下一步 |
|---|---|---|
| ≪ 39 万（如 < 2 万，<5%） | EL2 不是主因（假设 a） | C1：host TLBI/DSB/两级 walk 分析 |
| 与 39 万量级可比 | 隐藏 EL2 路径（假设 b） | C2：hyp per-cpu counter 定位站点 |
| nvhe 模式下净值明显非零 | 测量污染（IRQ/背景） | 修方法学再跑 |

辅证（protected 模式可选）：`/sys/kernel/debug/tracing/hypervisor/` 下短窗开
`hyp_enter/host_mem_abort/host_hcall` 事件数 EL2 入口次数（先
`echo 1024 > buffer_size_kb`，默认 7KB/CPU 必溢出）。

## 4. Patch C0：host 侧对照（两模式都跑，结果对比）

```bash
# FEAT_TLBIRANGE 确认（决定 TLBI 数量模型，也是 C1 微基准的依据）
./host-mm-trace.sh tlbirange /tmp/c0-out

# perf TLB/walk 事件（确保 xcore PMU 已 echo 0）
sudo CORE=0 SIZE=64 ITERS=50 ./host-mm-trace.sh perf /tmp/c0-out

# function_graph 抓 __vm_munmap 子树（需要插桩内核的 FUNCTION_GRAPH_TRACER）
sudo CORE=0 SIZE=64 ITERS=50 ./host-mm-trace.sh funcgraph /tmp/c0-out
```

判读（nvhe vs pkvm 同函数对比，funcgraph 绝对值含 trace 开销、只看相对差）：

```text
tlb_finish_mmu / __flush_tlb_range_nosync 膨胀为主 → TLBI/DSB 硬件成本（假设 a-1）
zap_pte_range / unmap_vmas 膨胀为主            → 两级 walk / dirty accounting（假设 a-2）
```

perf 关注 `l1d_tlb_refill / l2d_tlb_refill / dtlb_walk / stall_backend`
的两模式差，区分"TLBI 指令本身贵"还是"flush 后 walk/refill 贵"。

## 5. 已知注意事项

1. PMU 独占：xcore_stats enable 窗口内不跑 host perf 的 PMU 事件；反之亦然。
2. gate 的 Δ 用**同一 CPU**前后值；其他 CPU 桶只作背景参考。
3. 空窗对照必做：扣除背景 EL2 活动（读数本身在 EL1 完成，污染≈0，但 IRQ 等
   背景仍可能存在）。
4. funcgraph 开销显著，仅作两模式**相对**比较；perf/gate 测量不与 funcgraph 同窗。
5. nvhe 模式下 `echo 2`（mem stats）会返回不支持——这是预期行为。
