# Perf-only 复查结果：Kaitian，protected vs nvhe

| | |
|---|---|
| 日期 | 2026-06-24 |
| 板卡 | Kaitian，Phytium FTC862，Kylin V10 SP1，内核 `6.6.30-pkvm-clean` |
| 工具 | **只使用**从 `common/tools/perf` 编译出的 perf（`perf 6.6.30.gda966ce9a047`） |
| 模式 | `protected/`（host stage-2 开启）vs `nvhe/`（无 host stage-2），同一内核，通过 GRUB 切换 |
| 控制 | `taskset -c 0`，governor performance @1.9 GHz，THP=never，ASLR=0，paranoid=-1，**300 次迭代取 mean** |
| Bench | `op_sweep`/`munmap_only`（flush range 近似等于 touched extent；扫描 `touch_mb`，覆盖 2 MB 阈值） |

**结论：原始根因已完整地用 perf-only 链路复现。** pKVM `lat_mmap` 的额外成本，是低于 2 MB
teardown TLB invalidation 中每个 4 K flush slot 的附加税；它与具体 syscall 无关，会在 2 MB
integer-flush 阈值处消失，在这块板卡上约为 **+0.13 us/4 K flush slot**。这部分时间全部表现为
**host EL1 的 backend（memory）stall**，不是 EL2 时间，也不是更多页表 walk。

---

## 1. protected - nvhe gap 的 2 MB 断崖（`op_sweep.txt`）

单位为 mean us/iter；**gap = protected - nvhe**。这里包含 dense 4 K touch
（flush range = touch size）以及一个类似 `lat_mmap` 的 sparse 点。

### munmap

| flush range | slots | protected | nvhe | **gap** | us/slot |
|---:|---:|---:|---:|---:|---:|
| 0.25 MB | 64 | 23.1 | 15.5 | **+7.6** | 0.119 |
| 0.5 MB | 128 | 43.5 | 25.8 | **+17.7** | 0.138 |
| 1.0 MB | 256 | 79.6 | 46.6 | **+33.0** | 0.129 |
| **1.9 MB** | 486 | 148.7 | 87.3 | **+61.4** | 0.126 |
| **2.0 MB** | integer | 88.2 | 86.6 | **+1.6** | - |
| 4 MB | integer | 174.6 | 168.4 | +6.2 | - |
| 8 MB | integer | 354.6 | 334.9 | +19.7 | - |
| sparse 6.4/16K | per-PMD | 294.8 | 89.2 | **+205.6** | - |

低于 2 MB 时，gap 随 flush slot 数量线性增长；到 **2.0 MB** 时则从 +61.4 us 断崖式降到
+1.6 us。这对应内核从每个 4 K slot 一条逐页 `tlbi`，切换到单条 whole-ASID integer flush
（`MAX_DVM_OPS=512`，即 2 MB）。这就是原始根因，且这里完全通过 timing 观察到。

### 操作无关性：最强交叉验证（每个范围下的 gap）

| flush range | munmap | dontneed | mprotect |
|---:|---:|---:|---:|
| 0.25 MB | +7.6 | +7.8 | +7.7 |
| 1.0 MB | +33.0 | +31.1 | +31.9 |
| **1.9 MB** | **+61.4** | **+61.0** | **+61.0** |
| 2.0 MB | +1.6 | +1.2 | +0.2 |
| sparse 6.4/16K | +205.6 | +205.5 | **+0.1** |

低于 2 MB 时，三种不同 syscall 的 gap **几乎完全一致**（1.9 MB 下均约 +61 us）。
这说明成本来自 per-slot combined-entry TLBI 本身，而不是 `munmap` 独有逻辑。
`MADV_DONTNEED` 是完整受害者，基本跟随 munmap；而 **`mprotect` 在 sparse 场景逃逸**
（+0.1 us），因为它不执行 dirty-zap，所以会积累出一个 >=2 MB 的 flush，走 integer path。
这与原始调查中的 op-generality 规则完全一致。

**pKVM per-slot 附加成本约为 +0.13 us/slot**（Kaitian）。原始 N80 工作测得约 +0.27 us/slot；
二者是同一 FTC862 核心、同一机制，但幅度约减半。这是板级差异，不是机制差异。

## 2. EL2 归因：`cycles:h = 0`（`el2_h.txt`）

对 sparse munmap 执行 300 次迭代，使用 `perf stat -e cycles:h`：

- protected：`cycles:h = 0`，`instructions:h = 0`，全部 339M cycles 都是 `cycles:k`（host EL1）。
- nvhe：`cycles:h = 0`。

teardown 在两种模式下都花费 **0 个 EL2 cycle**。因此该成本位于 host 侧（EL1），不是 hypervisor。
这复现了原始调查的 Stage 3 gate 结论，但现在只需要一条 `perf stat`。该结果可信，因为 Stage 0
已经证明同一个计数器在 EL2 确实忙碌时会读到 392M。

## 3. Cost layering：工作量相等，额外时间是 backend stall（`cost_layering.txt`）

sparse munmap（6.4 MB / 16 K），300 次迭代，protected vs nvhe：

| event | protected | nvhe | delta（P - N） |
|---|---:|---:|---:|
| instructions | 463.7 M | 463.1 M | +0.6 M（约等于 0） |
| page-faults | 123,050 | 123,050 | **0** |
| **DTLB-walk**（`r0034`） | 122,556 | 123,506 | **约等于 0** |
| l2d_tlb_refill | 122,944 | 123,609 | 约等于 0 |
| **stall_backend**（`r0024`） | 206.2 M | 87.5 M | **+118.7 M** |
| **cycles** | 369.8 M | 250.3 M | **+119.5 M** |

instructions、faults 和**页表 walk** 都相同；+119.5M cycle gap 几乎全部对应 +118.7M
额外 **backend（memory）stall**，占比 99.3%。walk 计数相同直接**反驳 nested-walk 假设（a-2）**：
protected 并没有做更多 walk。附加成本是 per-slot TLBI 成本（a-1），在更慢的 combined-entry
invalidation 完成期间表现为 backend stall。

## 4. 数值闭环

三组独立测量在数量级上闭合：

- wall-time gap（sparse munmap）：约 203 us/iter，约等于 1.9 GHz 下的 386k cycles。
- perf cycle gap：119.5M / 300 = **398k cycles/iter**。
- 从 cycles 推出的 per-slot 成本（1 MB dense，+18.9M cycles / 256 slots / 300 iters）=
  **246 cycles，约 0.13 us/slot**，与 timing 推出的 0.13 us/slot 一致。

## 5. 与原始五阶段调查的对应关系：全部用 perf-only 复现

| 原始阶段（所需结论） | 本次 perf-only 结果 |
|---|---|
| 1 症状 | protected-nvhe gap 存在，随大小增长；steady ops 无对应成本 |
| 2 定位到 munmap | `op_sweep` 将 gap 隔离到 teardown 操作 |
| 3 EL2 gate（原为自定义 hypercall） | `cycles:h = 0`，且使用 **stock perf** |
| 4 Cost layering | instructions/faults/**walks** 相等，额外 +118.7M backend stall |
| 5 机制 a-1 vs a-2 | 2 MB 断崖 + gap 与 slot 数成正比 + **walk 相同** -> a-1（per-slot TLBI） |
| 6 泛化性 | dontneed 完整受害；mprotect 受 geometry 控制而逃逸；gap 与操作无关 |

原始 `op=3` host-stage-2 自省这次**不再需要**。nested-walk 假设已经被相同的 `r0034` walk 计数、
per-slot 结构以及 2 MB 断崖以行为证据方式反驳。

## 6. Core-scaling：成本是本地的，不是跨核 broadcast（`corescaling/corescaling.txt`）

sparse munmap 固定在 cpu0，1000 次迭代，protected 模式，改变 online core 集合
（其余核心通过 CPU hotplug offline；每次切换后重新锁频）：

| online set | mean us | min us | cycles | **stall_backend**（`r0024`） | instructions |
|---|---:|---:|---:|---:|---:|
| n8 all | 294.2 | 290.5 | 1,187.6 M | **680.8 M** | 1,442.6 M |
| n2 intra {0,1} | 294.7 | 290.4 | 1,187.9 M | **680.0 M** | 1,442.3 M |
| n2 cross {0,4} | 295.3 | 290.6 | 1,188.8 M | **681.9 M** | 1,442.6 M |
| n1 solo {0} | 303.3 | 209.3 | 1,208.1 M | **676.4 M** | 1,451.2 M |

- **mean、cycles 和 `stall_backend` 均不随 online core 数量或 cluster 位置变化**。intra {0,1}
  与 cross {0,4} 也基本相同。如果成本来自跨核 DVM broadcast 或等待 `dsb ish` 完成，则应随参与核心增长；
  实测没有增长。因此，§3 中的 +118.7M backend stall 是 invalidating combined, VMID-tagged TLB entry
  的**本地成本**，不是 broadcast wait。这复现了原始后续调查中的修正结论，而且只用 perf，
  不需要 IRQ-off 内核模块。
- **`min` 陷阱再次出现：** n1 solo 的 `min`=209 us 明显低于 `mean`=303 us（单核方差大），
  而 n8 的 `min` 接近 `mean`。如果用 min 比较，就会制造出“从 1 核到 8 核增加 +81 us”的假象；
  **mean** 才显示真实趋势是持平。原始经验仍成立：不要跨方差不同的配置比较 `min`。

## 7. `mmap_split` 阶段拆解（protected）：成本在 touched-page teardown（`protected/mmap_split.csv`）

将 `lat_mmap` 拆成独立计时阶段（`lat_mmap` geometry：64 MB，touch size/10 = 6.4 MB，
16 K stride，300 次迭代），protected 模式：

| phase | protected us/iter |
|---|---:|
| `mmap_unmap`（创建并删除 VMA，不 touch） | 3.54 |
| `write_touch_cold`（仅 first-touch faults） | 330.35 |
| `munmap_after_no_touch`（teardown，但没有实际映射页） | **1.66** |
| `munmap_after_write_touch`（touch 后 teardown） | **292.84** |
| `mmap_write_touch_unmap`（完整路径） | 625.01 |

- 完整路径（625）约等于 touch（330）+ teardown（293）+ setup（3），呈现可加性。
- **未 touch 的 munmap 几乎免费（1.66 us）；touch 后的 munmap 是 293 us。**
  因此 munmap 成本完全来自 touched PTE 的 teardown（clear + per-page TLBI），不是 syscall/VMA 机制本身。
  这正是 §1 中 protected-nvhe gap 所在的位置，也复现了原始 Stage 2 定位。

**nvhe 分支未采集（操作层面的 caveat）：** 本次会话中 GRUB one-shot（`grub-reboot`）第一次成功切到 nvhe，
之后三次不再消费 `next_entry`；即使执行 `sync` 并等待，板卡仍以 protected 启动，且 one-shot 仍保持 armed。
这是板卡层面的 grubenv 可靠性问题。teardown 定位**不依赖**这一分支：op_sweep、cost-layering（§1、§3、§4）
已经在两种模式下把 gap 隔离到 touched-page teardown；上面的 protected 内部分解
（untouched 约 0，touched 293 us）也独立确认成本来自 touched-PTE teardown。

## 文件

`protected/` 与 `nvhe/`：`op_sweep.txt`、`el2_h.txt`、`cost_layering.txt`、`kernel.txt`
（另有 `protected/mmap_split.csv`）；`corescaling/corescaling.txt`。

脚本：

- `../setup-controls.sh`
- `../run-suite.sh`
- `../core-scaling.sh`
- `../run-mmapsplit.sh`

开放项：大型 dense >=2 MB 场景中，gap 会随 freed pages 增长（例如 munmap 64 MB 的 mean gap 为
+532 us），但该值被单核方差放大（min gap 只有 +83 us）。这是一个噪声更大的次级现象，不属于
`lat_mmap` 相关的小范围/sparse 主路径。
