# pKVM 宿主机 mmap 性能退化调查报告

| 项目 | 内容 |
|---|---|
| 调查对象 | pKVM（protected KVM）模式下宿主机侧 `lat_mmap` 的性能退化 |
| 测试平台 | N90、Kaitian、N80（均为 Phytium / Kylin V10 aarch64，内核 6.6.30 系列，Rust nVHE hypervisor） |
| 调查周期 | 2026-06-04 至 2026-06-15 |
| 状态 | 根因已判定，证据链完整；根因的微架构归因经第 9 节在线核数复查进一步确认（"广播等待"更正为本地合成条目失效） |
| 代码仓库 | 内核：`common`（本仓库）；测试：`kylin-lmbench` |

**结论（一句话）**：pKVM 为宿主机启用了 host stage-2 第二级地址翻译，使宿主机 `lat_mmap`（mmap → 写触摸 → munmap 的完整映射生命周期）在大尺寸下慢 42%～85%，而稳态内存访问（`lat_mem_rd`、`bw_mem`）几乎不受影响。逐层定位后，退化的来源被确定为单一机制：**munmap 拆除映射时，内核对小于 2 MB 的范围逐页发出 `TLBI` 指令，而 host stage-2 使每个 4K flush slot 对应的逐页失效序列硬件代价显著增加（由阈值扫描斜率折算，约 +0.27 µs/slot）**；当范围达到 2 MB、内核改用单条整表刷新时，退化随之消失。核心缓解手段是硬件特性 FEAT_TLBIRANGE（本次测试平台不具备该特性，因而退化明显）。

本报告为自包含的完整记录：每个阶段均给出实验背景、设计依据、关键代码、完整数据与分析。调查过程中有两处早期结论被后续更精细的实验推翻（first-touch 假设、嵌套页表遍历假设），本报告如实保留这两次修正及其论证过程；主调查结束后另有一次后续复查（第 9 节）更正了根因的"广播"归因，同样如实保留其错误路径与纠正过程。

---

## 目录

1. [摘要](#1-摘要)
2. [背景与预备知识](#2-背景与预备知识)
3. [阶段一：现象确认——四种 KVM 模式对照（N90）](#3-阶段一现象确认四种-kvm-模式对照n90)
4. [阶段二：生命周期拆分——定位到写触摸后的 munmap（Kaitian）](#4-阶段二生命周期拆分定位到写触摸后的-munmapkaitian)
5. [阶段三：EL2 判别——证明退化不发生在 hypervisor 内（N80）](#5-阶段三el2-判别证明退化不发生在-hypervisor-内n80)
6. [阶段四：宿主机侧成本分层——perf 事件分解（N80）](#6-阶段四宿主机侧成本分层perf-事件分解n80)
7. [阶段五：机制判定——从两个候选到唯一解释（N80）](#7-阶段五机制判定从两个候选到唯一解释n80)
8. [结论](#8-结论)
9. [后续复查：在线核数实验——退化来自本地失效开销，而非跨核广播（N80）](#9-后续复查在线核数实验退化来自本地失效开销而非跨核广播n80)
- [附录 A：测试平台一览](#附录-a测试平台一览)
- [附录 B：复现步骤](#附录-b复现步骤)
- [附录 C：代码、脚本与数据索引](#附录-c代码脚本与数据索引)
- [附录 D：阶段性详细文档](#附录-d阶段性详细文档)

---

## 1. 摘要

调查共经历五个阶段，每个阶段回答一个明确的问题：

```
阶段一（现象）   在同一块板、同一内核上对照四种 KVM 模式：
                KVM-off / VHE / NVHE 的 lat_mmap 彼此重合（差异 < 0.25%），
                唯独 pKVM 慢 +29%（0.5 MB）至 +85%（64 MB）；
                稳态内存访问（lat_mem_rd / bw_mem）四模式无差异。
                → 开销位于映射生命周期（建立/触摸/拆除），不在稳态访问。
                  早期假设：开销来自首次触摸时的 stage-2 缺页建表（后证伪）。

阶段二（细化）   把 lat_mmap 拆成 12 个子测试，逐段隔离计时：
                写触摸本身仅慢 +3.78%【修正一：first-touch 不是主因】；
                写触摸之后的 munmap 慢 +227%，可解释完整路径额外时间的 95.7%。
                → 退化集中于"写触摸后的 munmap 拆除"。

阶段三（判别）   munmap 的额外时间是否花费在 EL2（hypervisor）中？
                用仅统计 EL2 周期的 PMU 计数测量：ΔEL2 = 0
                （计数器经 1.68 亿周期的阳性对照验证有效）。
                → 退化不在 EL2 软件路径，在宿主机（EL1）侧。

阶段四（定层）   perf 事件分解：指令数、缺页数、页表遍历次数两模式完全相同，
                额外的 +39.8M 周期几乎全部为 +40.9M 后端（访存）停顿。
                → 不是软件多做了工作，是硬件访存等待变长。
                  候选机制收敛为两个：a-1（每条 TLBI 更贵）、a-2（每次页表遍历更贵）。

阶段五（定因）   host stage-2 粒度自省排除碎片化（99.5% 为 1G 块映射）；
                密集触摸对照实验中页表遍历工作量增至 40 倍而差距趋零
                【修正二：证伪 a-2】；内核源码定位 2 MB 整表刷新阈值；
                阈值扫描显示差距在 2 MB 处陡降至 5% 以内、2 MB 以下与
                逐页 flush slot 数成正比（约 0.27 µs/slot）。
                → 根因 = a-1：逐页 TLBI 在 host stage-2 下的硬件开销。
```

最终结论与缓解方向见第 8 节。此外，第 9 节记录了一次主调查结束后的后续复查（2026-06-15）：它以"在线核数"为自变量，证明上述 +0.27 µs/slot 是**本地**合成条目失效成本而非**跨核广播**，并据此更正了 §7.7／§8.1 中的"广播等待"措辞。

---

## 2. 背景与预备知识

### 2.1 四种 KVM 运行模式与 host stage-2

arm64 内核以 `kvm-arm.mode` 启动参数选择 KVM 运行模式，四种模式下宿主机的地址翻译结构不同，这是本调查所有对照实验的基础：

| 模式 | 启动参数 | 宿主机地址翻译 | 是否存在 host stage-2 |
|---|---|---|---|
| KVM-off | `kvm-arm.mode=none` | 纯 stage-1（EL2 未启用） | 否 |
| VHE | （默认，无显式参数） | 宿主机内核自身运行于 EL2，纯 stage-1 | 否 |
| NVHE | `kvm-arm.mode=nvhe` | EL2 有最小 hypervisor 存根，但不管理宿主机内存 | 否 |
| **pKVM** | `kvm-arm.mode=protected` | 宿主机运行于 EL1，物理内存受 **host stage-2** 页表（IPA→PA 第二级翻译）保护 | **是** |

pKVM（protected KVM）的设计目标是使 hypervisor（EL2）不必信任宿主机内核：宿主机对物理内存的访问全部经过 EL2 维护的 host stage-2 页表。本内核的 EL2 部分以 Rust 实现（`arch/arm64/kvm/hyp/nvhe/rust/`），与上游 C 实现语义一致（见 §3.4 的交叉验证）。

一处容易误读的命名需要先澄清：**"host stage-2" 中的 "host" 指这张表约束的对象，而非它的管理者**。该表由 hypervisor 在 EL2 独占管理：表本身存放于 hyp 私有内存（页表页来自启动时捐赠给 hyp 的 `HOST_S2_POOL` 内存池），宿主机既不可读也不可写，其控制寄存器（`VTTBR_EL2`、`HCR_EL2.VM` 等）EL1 也无法访问。宿主机只能间接促使它变化——触发一次 stage-2 缺页，或通过 hypercall 请求所有权转移，实际的表项修改全部由 EL2 代码完成。若宿主机能修改这张表，pKVM"宿主机被攻破仍保护 guest 内存"的设计目标就不成立了。由此，两级翻译的管理权是对偶分立的：

| | stage-1（VA→IPA） | host stage-2（IPA→PA） |
|---|---|---|
| 管理者 | 宿主机内核（EL1） | hypervisor（EL2） |
| 对另一方的可见性 | hyp 刻意不陷入、不跟踪（无 `TVM`/`TTLB`，§5.1） | 宿主机完全不可见（观测须经 §7.1 的 op=3 自省接口） |
| 记录的内容 | 各进程的虚拟地址映射 | 物理页的所有权与访问权 |

这一对偶是后文多处分析的背景：munmap 修改的是宿主机自管的 stage-1，hyp 管理的 stage-2 不受影响（§2.1 末尾详述）；而宿主机发出的 TLBI 作废的却是横跨两级的合成 TLB 条目（§2.3、§7.7）——管理权分立、TLB 条目却合成，正是本调查根因的结构性来源。

代码层面可以确认，仅 protected 模式维护 host stage-2：`arch/arm64/kvm/arm.c` 中所有 `host_stage2_*` 相关调用点均位于 `if (is_protected_kvm_enabled())` 条件之内；普通 NVHE 模式不进入这些分支，宿主机的内存访问与裸机 Linux 等价。这正是 KVM-off、VHE、NVHE 三种模式可以共同作为对照基线的原因。

pKVM 启动时，`prepopulate_host_stage2()`（`mem_protect/host.rs:414`）遍历全部内存块，以尽可能大的块粒度（1 GB / 2 MB）将宿主机物理内存在 host stage-2 中恒等映射。此后宿主机访问尚未映射的地址会触发一次 stage-2 缺页进入 EL2，由 `handle_host_mem_abort()`（host.rs:2068）→ `host_stage2_idmap()`（host.rs:1930）建立映射；`host_stage2_adjust_range()`（host.rs:1839）以贪心方式选取能够容纳目标地址的最大块级别：

```rust
// host.rs:1839 host_stage2_adjust_range（节选）：
// 自当前级别向上（向 1G 方向）尝试，范围能整块容纳且该级别支持块映射即停止
loop {
    let granule = kvm_granule_size(level);
    cur.start = align_down(addr as usize, granule as usize) as u64;
    cur.end = cur.start + granule;
    level += 1;
    if level > KVM_PGTABLE_LAST_LEVEL
        || (kvm_level_supports_block_mapping(level)
            && range_ref.range_included(&cur as *const _)) {
        break;
    }
}
```

只有当某子范围的权限偏离默认值时（例如该页被共享或捐赠给 guest/hyp），`host_stage2_force_pte()`（host.rs:521）才强制使用 4 KB 页粒度，将所在大块拆分：

```rust
// host.rs:521：权限偏离默认值的范围只能使用 4K 页映射
pub extern "C" fn host_stage2_force_pte(addr: u64, end: u64, prot: u64) -> bool {
    prot != default_host_prot(range_is_memory(addr, end))
}
```

这两段代码在阶段五（§7.1）的粒度自省中将再次出现。

**nvhe 与 protected：宿主机内存访问的运行时差异**

四种模式的差异不只是"有没有 host stage-2 这张表"，更体现在宿主机运行时的硬件配置上。决定性的开关有两个：`HCR_EL2.VM` 位（是否为 EL1 启用 stage-2 翻译）与 `VTTBR_EL2` 寄存器（stage-2 页表基址与 VMID）。

protected 模式在初始化收尾阶段由 `__pkvm_prot_finalize()`（host.rs:2249）把 host stage-2 接入硬件：

```rust
params.vttbr = kvm_get_vttbr(&host_mmu_ref.arch.mmu as *const _);
                                     /* :2261 host stage-2 页表基址 + VMID */
params.vtcr = host_mmu_ref.arch.vtcr;
params.hcr_el2 |= HCR_VM;            /* :2265 为宿主机 EL1 使能 stage-2 翻译 */
...
HCR_EL2.set(params.hcr_el2);         /* :2277 写入生效 */
__load_stage2(&host_mmu_ref.arch.mmu, &host_mmu_ref.arch);
```

此后每次从 guest 切回宿主机，`__load_host_stage2()`（host.rs:2521，调用点如 switch.rs:1250）按模式分叉：

```rust
pub fn __load_host_stage2() {
    if static_branch_likely!(kvm_protected_mode_initialized, ...) {
        __load_stage2(&host_mmu_ref.arch.mmu, &host_mmu_ref.arch);
                                     /* protected：装载 host stage-2 */
    } else {
        VTTBR_EL2.set(0);            /* nvhe：宿主机无 stage-2 */
    }
}
```

nvhe 模式下 `HCR_VM` 从不为宿主机置位、`VTTBR_EL2` 为 0，宿主机的访存与裸机 Linux 完全相同。两种模式下宿主机一次内存访问的差异汇总：

| | nvhe | protected |
|---|---|---|
| 地址翻译 | 一级（VA→PA） | 两级（VA→IPA→PA，IPA 经 host stage-2 恒等映射） |
| TLB 条目 | 纯 stage-1，仅 ASID 标记 | stage-1×stage-2 合成，ASID+VMID 双标记（§2.3） |
| TLB 命中时 | 直接得到 PA | 同左（合成条目一次命中，无额外成本） |
| TLB 未命中时 | 单级页表遍历 | 嵌套遍历：stage-1 各级描述符地址还需经 stage-2 翻译（host RAM 为 1G 块映射时增量很小，§7.1） |
| 首次访问未映射的物理页 | 不存在此事件 | 至多一次 stage-2 缺页进入 EL2 建块映射（见下） |
| TLB 维护（TLBI） | 作废 stage-1 条目 | 作废合成条目，shareable 失效完成等待更重（§7.7，本调查的根因所在） |

这张表预示了全文的格局：TLB 命中主导的稳态访问两模式无差异（§3.3），差异集中在低频但代价被放大的 TLB 维护操作上（§7）。

**host stage-2 映射为何一经建立即长期有效**

§2.2 与 §5 将依赖一个事实：不创建虚拟机、不共享内存的宿主机，只有在 host stage-2 对相关 Host-owned 物理地址范围尚无映射时，首次访问才会因 stage-2 缺页进入 EL2；一旦这些范围已由启动阶段预填充或首次 stage-2 缺页补建完成，后续普通访存不再进入 EL2。其根源是 host stage-2 的语义——**它记录的是"每个物理页归谁所有、宿主机能否访问"，与宿主机自己如何在虚拟地址空间中映射这些页无关**。具体由三点构成：

1. **建立只发生一次，且以物理地址为对象**。启动时 `prepopulate_host_stage2()`（host.rs:414）已将全部物理内存以 1G/2M 块恒等映射；个别未覆盖的范围在首次访问时经 `handle_host_mem_abort()` → `host_stage2_idmap()`（见上文）建立尽量大的块。映射覆盖的是**物理地址区间**——此后无论哪个进程、经哪个虚拟地址访问该物理页，stage-2 这一级都直接命中，与 stage-1 映射如何变动无关。
2. **宿主机的 stage-1 活动不会拆除它**。能修改 host stage-2 的途径是一张封闭的清单：缺页建表（`host_mem_abort`），以及所有权转移 hypercall（`__pkvm_host_share_hyp` / `__pkvm_host_donate_hyp` / share_guest / relinquish 等，最终落到 `__host_stage2_set_owner_locked()`（host.rs:789）与 `host_stage2_force_pte()`（host.rs:521））。munmap 不在清单上：它只清除宿主机自己的 stage-1 页表项，全程不发 hypercall（§5.1）；物理页释放回伙伴系统、将来再分配给其他进程，其所有权始终是"宿主机拥有"，host stage-2 没有任何需要更新的内容。
3. **hyp 对宿主机的 stage-1 活动刻意不可见**。宿主机的 HCR 配置（§5.1）不含 `TVM`（陷页表寄存器写）、`TTLB`（陷 TLB 维护）等位——EL2 既不拦截也不需要知道宿主机何时建立或拆除自己的虚拟映射。pKVM 的隔离对象是物理内存的所有权，按所有权粒度管理即可，无须跟踪宿主机的 VA 映射。

三点合起来：基准反复 mmap/触摸/munmap 同一个后备文件，文件页在页缓存中常驻、所有权从未转移；相关 Host-owned 物理页的 host stage-2 映射要么在启动阶段已经由 `prepopulate_host_stage2()` 建好，要么在第一次访问时补建一次。完成这一步后，测量窗口内的后续宿主机访存不会产生任何 EL2 进入。这正是阶段三 gate 实验测得 ΔEL2 = 0（§5.5）的体系结构原因——零不是测量误差，而是设计的直接推论。

### 2.2 mmap 的内核实现：映射生命周期的三个阶段

`lat_mmap` 的一次迭代（mmap → 写触摸 → munmap）在内核中对应三段性质完全不同的工作。理解每一段"做什么、不做什么"，是读懂后文拆分实验（§4）与机制分析（§7）的前提。本节按本仓库源码梳理这条路径（行号以当前代码树为准）。

**预备概念：VMA——内核对一段虚拟地址区间的描述**

后文反复出现的 VMA（Virtual Memory Area，虚拟内存区域）是内核管理进程虚拟地址空间的基本单位，对应数据结构 `struct vm_area_struct`（`include/linux/mm_types.h:597`）。一个 VMA 描述一段连续且属性一致的虚拟地址区间——进程的代码段、数据段、堆、栈，以及每一次 mmap 建立的映射，各自都是一个 VMA（`cat /proc/<pid>/maps` 输出的每一行对应一个 VMA）。与本报告相关的字段：

```c
/* include/linux/mm_types.h:597（节选，省略锁、匿名映射等成员） */
struct vm_area_struct {
    unsigned long vm_start;        /* :603  区间起始地址（含） */
    unsigned long vm_end;          /* :604  区间结束地址（不含） */
    struct mm_struct *vm_mm;       /* :611  所属的进程地址空间 */
    pgprot_t vm_page_prot;         /* :612  该区间页表项的访问权限 */
    vm_flags_t vm_flags;           /* :619  VM_READ/VM_WRITE/VM_SHARED 等属性位 */
    const struct vm_operations_struct *vm_ops;
                                   /* :666  回调函数表（本节稍后详述） */
    unsigned long vm_pgoff;        /* :669  映射起点在后备文件中的页偏移 */
    struct file *vm_file;          /* :671  后备文件（匿名映射为 NULL） */
    ...
};
```

进程的全部 VMA 由其地址空间描述符 `mm_struct`（mm_types.h:710）以 maple tree（`mm_mt` 字段，:727）组织，支持按虚拟地址快速查找。

VMA 的职责可以概括为：它是内核记录"这段地址**应该**映射到什么、以什么权限映射" 的**意图层**；而页表是硬件实际查询的**翻译层**。两层的分工贯穿映射的整个生命周期，正对应本节的三个阶段：

- **mmap** 只在意图层登记（创建 VMA），翻译层留空——见下文（1）；
- 访问留空的翻译层触发**缺页**，内核拿 fault address（触发缺页的虚拟地址）查 VMA（`do_page_fault()` 中的 `lock_mm_and_find_vma()`，`arch/arm64/mm/fault.c:648`）：查不到 VMA 或权限不符即发出 SIGSEGV；合法则按 VMA 的记载（`vm_file`、`vm_pgoff`、`vm_ops`）补齐页表——见（2）；
- **munmap** 须把两层都清理：删除 VMA、清除页表项并作废 TLB（§2.3）——见（3）。

内核能把"非法访问"与"合法但尚未建表"区分开，依据正是 VMA。这也是按需分页（mmap 时不建表、推迟到首次访问）得以成立的前提。

**（1）mmap 系统调用：只登记 VMA，不建立页表**

arm64 上 `mmap` 系统调用的内核路径：

```
sys_mmap            arch/arm64/kernel/sys.c:21
  → ksys_mmap_pgoff   mm/mmap.c:1405      文件映射：由 fd 取得 struct file
  → vm_mmap_pgoff     mm/util.c:549       获取 mmap_lock 写锁
  → do_mmap           mm/mmap.c:1217      选定虚拟地址区间、检查权限与标志
  → mmap_region       mm/mmap.c:2688      创建 VMA 并插入地址空间
```

`mmap_region()` 的核心动作（mm/mmap.c:2786，节选）：

```c
vma->vm_start = addr;
vma->vm_end = end;
vm_flags_init(vma, vm_flags);
...
vma->vm_file = get_file(file);
error = call_mmap(file, vma);   /* 调用文件系统的 mmap 方法，作用见下文 */
```

其中 `call_mmap()` 本身只有一行（`include/linux/fs.h:2016`）：

```c
static inline int call_mmap(struct file *file, struct vm_area_struct *vma)
{
    return file->f_op->mmap(file, vma);
}
```

即把 VMA 交给该文件所属的文件系统处理一次。要理解这一步做了什么，需要先了解 VMA 上的 `vm_ops` 字段：它指向一张回调函数表（`struct vm_operations_struct`，定义于 `include/linux/mm.h:575`），mm 核心代码在这个 VMA 上发生特定事件时，会调用表中登记的函数。与本报告相关的两个回调是：

- `fault`（声明于 mm.h:592）——该 VMA 内发生缺页时调用，职责是找到（或准备出）对应的物理页。调用点：`__do_fault()`（`mm/memory.c:4573`），其中 :4599 行 `ret = vma->vm_ops->fault(vmf);`
- `page_mkwrite`（声明于 mm.h:600）——共享文件映射中的页**即将被写脏**时调用，给文件系统记账（预留磁盘空间、关联日志等）的机会。调用点：`do_page_mkwrite()`（`mm/memory.c:3096`），其中 :3107 行 `ret = vmf->vma->vm_ops->page_mkwrite(vmf);`

这里"文件系统的 mmap 方法"指 `struct file_operations` 中的 `.mmap` 成员。文件在 `open()` 时，`file->f_op` 就已指向其所属文件系统的文件操作表；对 ext4 上的普通文件（本调查的后备文件即属此类），这张表是 `ext4_file_operations`（`fs/ext4/file.c:931`），其中注册了 mmap 方法：

```c
/* fs/ext4/file.c:931 */
const struct file_operations ext4_file_operations = {
    .llseek         = ext4_llseek,            /* :932 */
    .read_iter      = ext4_file_read_iter,    /* :933 */
    .write_iter     = ext4_file_write_iter,   /* :934 */
    ...
    .mmap           = ext4_file_mmap,         /* :940 —— call_mmap() 实际调用的函数 */
    ...
};
```

因此 `call_mmap()` 中的 `file->f_op->mmap(file, vma)` 在本调查场景下解析为 `ext4_file_mmap()`。该函数很短，完整逻辑如下（`fs/ext4/file.c:782`）：

```c
static int ext4_file_mmap(struct file *file, struct vm_area_struct *vma)
{
    struct inode *inode = file->f_mapping->host;
    struct dax_device *dax_dev = EXT4_SB(inode->i_sb)->s_daxdev;

    if (unlikely(ext4_forced_shutdown(inode->i_sb)))
        return -EIO;                        /* 文件系统已强制下线：拒绝 */

    /* MAP_SYNC 同步映射仅 DAX 设备支持，不满足则拒绝 */
    if (!daxdev_mapping_supported(vma, dax_dev))
        return -EOPNOTSUPP;

    file_accessed(file);                    /* 更新访问时间 */
    if (IS_DAX(file_inode(file))) {
        vma->vm_ops = &ext4_dax_vm_ops;     /* DAX（持久内存直接访问）路径 */
        vm_flags_set(vma, VM_HUGEPAGE);
    } else {
        vma->vm_ops = &ext4_file_vm_ops;    /* 普通文件：安装回调表
                                               ← 本调查的后备文件走此分支 */
    }
    return 0;
}
```

可见除两项合法性检查与一次访问时间更新外，它唯一的实质动作就是末尾那条赋值——把 ext4 的回调表安装到 VMA 上（普通磁盘文件不是 DAX 设备，走 else 分支）。被安装的表定义在 `fs/ext4/file.c:776`：

```c
/* fs/ext4/file.c:776 */
static const struct vm_operations_struct ext4_file_vm_ops = {
    .fault          = filemap_fault,        /* :777  缺页：走通用页缓存路径 */
    .map_pages      = filemap_map_pages,    /* :778 */
    .page_mkwrite   = ext4_page_mkwrite,    /* :779  写脏前通知文件系统 */
};
```

表中登记的三个函数分别是：

- **`filemap_fault()`**（`mm/filemap.c:3292`）——文件页缺页的通用处理函数。ext4 未做任何包装，直接复用 mm 层的公共实现。其核心骨架：

  ```c
  folio = filemap_get_folio(mapping, index);       /* :3311 按文件偏移查页缓存 */
  if (likely(!IS_ERR(folio))) {
      fpin = do_async_mmap_readahead(vmf, folio);  /* :3318 命中：按需异步预读 */
  } else {
      ret = VM_FAULT_MAJOR;                        /* :3327 未命中：记为主缺页 */
      fpin = do_sync_mmap_readahead(vmf);          /* :3328 同步预读，发起磁盘读 */
      folio = __filemap_get_folio(mapping, index, FGP_CREAT | ..., ...); /* :3338 */
  }
  ...
  vmf->page = folio_file_page(folio, index);       /* :3402 把页交还 mm 核心 */
  ```

  即：在页缓存（该文件已驻留内存的页面集合）中按文件偏移查找目标页，命中则直接返回，未命中才发起磁盘读入。本调查的后备文件预先填充且驻留页缓存，正式测量期间走的均为命中分支，不含磁盘 I/O。

- **`filemap_map_pages()`**（`mm/filemap.c:3595`）——"缺页周边批量填 PTE"优化：处理一次**读**缺页时，顺带把页缓存中已就绪的相邻页一并填入页表，减少后续缺页次数。该优化只在读缺页路径（`do_read_fault()` → `do_fault_around()`）生效；本调查的基准是写触摸，走 `do_shared_fault()`，不经过此优化——因此 "每个被触摸的页对应一次缺页"的计数模型（§2.2 第（2）阶段、§4 拆分实验）不受它干扰。

- **`ext4_page_mkwrite()`**（`fs/ext4/inode.c:6067`）——ext4 对"共享映射页即将被写脏"的处理：`sb_start_pagefault()` 进入文件系统缺页临界区，必要时经 `block_page_mkwrite()` 为该页分配磁盘块，日志模式下通过 `ext4_journal_start()` 将修改纳入日志事务，最后锁页返回（`VM_FAULT_LOCKED`）。这一步保证页被写脏之后，将来的回写一定有磁盘空间可落、有日志可依。

换言之，mmap 阶段对文件内容唯一做的事，是在 VMA 上登记"这段地址日后缺页该由谁处理"。这张回调表真正被使用的时刻在下文第（2）阶段：`__do_fault()`（`mm/memory.c:4573`）调用 `vma->vm_ops->fault`，`do_page_mkwrite()`（`mm/memory.c:3096`）调用 `vma->vm_ops->page_mkwrite`。

整条路径只创建并登记一个 VMA，把虚拟地址区间与文件偏移、访问权限关联起来（即填好上文所列的 `vm_start`/`vm_end`/`vm_flags`/`vm_file`/`vm_pgoff`/`vm_ops` 各字段）；**不为任何页面建立页表项，也不读入任何文件页**。这是按需分页（demand paging）的设计：页表项推迟到首次访问时才建立。其直接推论是 mmap 系统调用本身的成本与映射大小基本无关——§4.3 的 `mmap_unmap` 子测试中，仅建立/删除 VMA 的开销在两种模式下均约 3 µs 且不随尺寸增长，正是这一设计的体现。

**（2）首次访问：缺页异常按需建立页表项**

先定义一个贯穿全文的概念。本报告（以及 lmbench 与拆分基准的子测试命名）中反复出现的"**触摸**"（touch），指对映射区间内某一页的**首次实际访问**——读或写该页内的任意一个字节。在按需分页之下，mmap 返回时页表是空的（见（1）），**真正决定 "哪些页拥有页表项"的是触摸，而不是 mmap**。理解触摸的三个性质，后文的实验设计才可读：

- **以页为单位生效**。地址翻译以 4 KB 页为粒度：触摸一页内的任意一个字节，就为整页建立页表项；同一页内的后续访问不再缺页。因此基准只需按页步长各写一个字节，即可精确控制"实际建表的页数"——这是 §4 与 §7.5 所有实验控制工作量的手段。
- **读触摸与写触摸走不同的内核路径，副作用不同**。读触摸走 `do_read_fault()`：建立的页表项初始为只读（共享文件页须保持"干净态"，之后的首次写入会再触发一次权限缺页）。此外，读缺页可能先经 `do_fault_around()` 调用文件映射的 `filemap_map_pages()`，把 fault address 附近已经在页缓存中且状态可用的相邻页一并填入页表，以减少后续读缺页次数；这只是批量填 PTE，不会扩大 VMA，也不会把尚未就绪的页强行读入。写触摸（对共享文件映射）走 `do_shared_fault()`：除建表外还要执行 `page_mkwrite` 记账并把页**标脏**，脏页在之后的回写与回收中有额外处理。两条路径成本与副作用不同，这是 §4 拆分实验把读、写触摸分设子测试的原因；本调查以行为更确定的写路径为主线。
- **触摸的范围与分布决定 munmap 的工作量**。只有被触摸过的页才有页表项可清、有页可释放、有 TLB 条目需作废；munmap 的 TLB 刷新范围就是实际建表区间的跨度。这解释了"未触摸映射的 munmap 接近零成本"（§4.3），也使"控制触摸范围与步长" 成为阶段五阈值扫描（§7.5）中精确控制逐页 flush slot 数的实验手段——稀疏触摸与密集触摸正是本调查区分两个候选机制的关键自变量。

真实负载中触摸无处不在：读取 mmap 进来的数据库页或模型权重文件是读触摸，向新映射写入数据是写触摸，程序加载后首次执行某个代码页是执行触摸；`MAP_POPULATE` 标志则让内核在 mmap 阶段代为预先触摸全部页面（拆分实验的 `mmap_populate_unmap` 子测试覆盖此路径）。

回到本阶段的主题。用户态首次写触摸映射中的某一页时，stage-1 页表中尚无对应表项，硬件触发数据异常，进入内核缺页处理路径：

```
do_mem_abort            arch/arm64/mm/fault.c:875   异常入口分发
  → do_translation_fault  fault.c:731
  → do_page_fault         fault.c:549               查找 VMA、检查访问权限
  → __do_page_fault       fault.c:519 → handle_mm_fault（mm/memory.c）
  → __handle_mm_fault                               逐级分配/定位 pgd/p4d/pud/pmd
  → handle_pte_fault      memory.c:5330             按表项状态分发
  → do_pte_missing        memory.c:3893             表项为空 + 文件映射 → do_fault
  → do_fault              memory.c:5062             按访问类型与映射类型三路分发
  → do_shared_fault       memory.c:5012             本基准写触摸的处理函数（见下）
```

链中最后一步分发的依据是 `do_fault()` 末尾的三路选择（mm/memory.c:5091）：

```c
} else if (!(vmf->flags & FAULT_FLAG_WRITE))
    ret = do_read_fault(vmf);       /* :5092 读触摸 → 读缺页（可触发周边批量填 PTE） */
else if (!(vma->vm_flags & VM_SHARED))
    ret = do_cow_fault(vmf);        /* :5094 私有映射的写 → 写时复制 */
else
    ret = do_shared_fault(vmf);     /* :5096 共享映射的写 → 本基准的路径 */
```

对 `lat_mmap` 而言，这两个判断条件为何成立，可以沿代码完整追溯——它们分别由 mmap 阶段和硬件异常记录留下：

**条件一：`vma->vm_flags & VM_SHARED` 成立——来自 mmap 时的标志转换。** `lat_mmap` 的调用是 `mmap(0, size, PROT_READ|PROT_WRITE, MAP_FILE|MAP_SHARED, fd, 0)`（`src/lat_mmap.c:157`）。`do_mmap()` 中，先把 `prot` 参数翻译为 VMA 属性位（mm/mmap.c:1287，其中 `calc_vm_prot_bits()` 把 `PROT_WRITE` 转换为 `VM_WRITE`，见 `include/linux/mman.h:145`），随后按 `flags & MAP_TYPE` 分支处理映射类型（mm/mmap.c:1309）：

```c
case MAP_SHARED:
    flags &= LEGACY_MAP_MASK;
    fallthrough;                              /* 与 MAP_SHARED_VALIDATE 合流 */
case MAP_SHARED_VALIDATE:
    if (prot & PROT_WRITE) {
        if (!(file->f_mode & FMODE_WRITE))    /* :1325 可写共享映射要求文件以写打开 */
            return -EACCES;
        ...
    }
    ...
    vm_flags |= VM_SHARED | VM_MAYSHARE;      /* :1336 ← VM_SHARED 在此置位 */
    if (!(file->f_mode & FMODE_WRITE))
        vm_flags &= ~(VM_MAYWRITE | VM_SHARED);  /* :1337 只读打开的文件则收回 */
```

基准的后备文件以读写方式（`O_RDWR`）打开，`FMODE_WRITE` 成立，`VM_SHARED` 得以保留。这份 `vm_flags` 随后在 `mmap_region()` 中经 `vm_flags_init(vma, vm_flags)`（:2788，见（1）的代码节选）固化到 VMA 上。缺页发生时 `do_fault()` 读取的 `vma->vm_flags & VM_SHARED`，正是这一位。

**条件二：`vmf->flags & FAULT_FLAG_WRITE` 成立——来自硬件对异常原因的记录。** 触摸循环执行的是写入（`*p = c`，`src/lat_mmap.c:172`，一条 store 指令）。store 触发数据异常时，硬件在异常综合征寄存器 ESR_EL1 的 WnR 位（Write not Read，bit 6，`arch/arm64/include/asm/esr.h:86`）记录"该访问是写"。`do_page_fault()` 据此设置缺页标志（`arch/arm64/mm/fault.c:583`）：

```c
} else if (is_write_abort(esr)) {   /* :544 即 (esr & ESR_ELx_WNR) && !(esr & ESR_ELx_CM) */
    /* It was write fault */
    vm_flags = VM_WRITE;            /* :585 校验用：VMA 必须允许写 */
    mm_flags |= FAULT_FLAG_WRITE;   /* :586 ← FAULT_FLAG_WRITE 在此置位 */
}
```

`mm_flags` 经 `handle_mm_fault()` 进入 `vmf->flags`，即 `do_fault()` 读取的 `FAULT_FLAG_WRITE`。同一处设置的 `vm_flags = VM_WRITE` 则用于权限校验：它会与 VMA 的属性位求交（即条件一链路中由 `PROT_READ|PROT_WRITE` 转换出的位），权限不符直接判为非法访问——两条链路在此交汇。

两个条件就位后，`do_fault()` 的三路分发必然落入第三个分支，`do_shared_fault()` 因此成为本基准缺页处理的终点。

`do_shared_fault()`（mm/memory.c:5012，节选）完成一页的建立：

```c
ret = __do_fault(vmf);               /* vm_ops->fault（filemap_fault，mm/filemap.c:3292）：
                                        在页缓存中查找文件页，未命中则发起读入 */
...
if (vma->vm_ops->page_mkwrite)
    tmp = do_page_mkwrite(vmf, folio);   /* 通知文件系统该页即将被写脏 */
ret |= finish_fault(vmf);            /* set_pte_range（memory.c:4722）：
                                        将物理页号与权限写入 stage-1 PTE */
ret |= fault_dirty_shared_page(vmf); /* 标记脏页 */
```

每个被触摸的 4 KB 页对应一次上述完整流程。按 `lat_mmap` 的触摸方式（只触摸前 1/10、步长 16 KB，见 §2.4），一次 64 MB 迭代发生约 410 次缺页。后备文件预先填充并驻留页缓存后，该路径不含磁盘 I/O。

pKVM 维度的补充：protected 模式下，若缺页装入的物理页尚未在 host stage-2 中建立映射，对它的首次访问还会叠加一次 stage-2 缺页进入 EL2 建表。但 host stage-2 的映射以物理页为对象，一经建立即长期有效（机制论证见 §2.1"host stage-2 映射为何一经建立即长期有效"）；基准反复映射同一个后备文件，其物理页在最初的迭代后已全部映射完毕，稳态测量窗口内不再触发该路径（阶段三的实测 ΔEL2 = 0 从测量层面证实了这一点，§5.5）。

**（3）munmap：工作量与已建立的页表项数量成正比**

```
__vm_munmap → do_vmi_munmap → unmap_region   mm/mmap.c:2346
  → unmap_vmas → … → zap_pte_range             mm/memory.c:1577   逐项清除 PTE
  → free_pgtables                                                  释放中间级页表页
  → tlb_finish_mmu → flush_tlb_range                               TLB 失效（§7.4 详述）
```

zap 路径对范围内每个有效表项执行（`zap_present_ptes()`，mm/memory.c:1530，节选）：

```c
ptep_get_and_clear_full(mm, addr, pte, tlb->fullmm); /* 原子读出并清零 PTE */
tlb_remove_tlb_entry(tlb, pte, addr);                /* 将地址登记入 mmu_gather，
                                                        留待统一 TLB 失效 */
```

对写触摸过的文件页，还须经 `folio_mark_dirty()` 标脏并归还页缓存、更新引用计数。全部表项清除后，`tlb_finish_mmu()` 对 mmu_gather 累计的地址范围执行一次 TLB 失效——该步骤的两条路径（逐页 TLBI 与整表刷新）在 §7.4 中详细分析，是本调查最终定位的退化所在。

**三个阶段的工作量来源汇总**：

| 阶段 | 工作量 | 与映射尺寸的关系 |
|---|---|---|
| mmap | 创建一个 VMA | O(1)，与尺寸无关 |
| 写触摸 | 每页一次缺页（查页缓存 + 填写 PTE） | ∝ 触摸页数 |
| munmap | 清除 PTE、释放页、TLB 失效 | 清除/释放 ∝ 已建表项数；TLB 失效条数取决于范围与刷新策略 |

这张表预告了后文的两个观测：`lat_mmap` 的三段成本必须分别计时才能定位（§4）；未触摸映射的 munmap 没有页表项可拆，成本接近于零（§4.3 的 `munmap_after_no_touch`）。

### 2.3 TLB、ASID、VMID 与 TLBI：地址翻译缓存及其失效

§2.2 的结尾提到，munmap 清除页表项后必须"作废 TLB"。本节先解释 TLB、ASID 与虚拟化引入的 VMID，再解释 TLBI 指令族如何按这些键作废缓存条目。后文的 perf 事件分析（§6）、2 MB 阈值（§7.4）与机制解释（§7.7）都建立在这组概念之上。

**TLB：地址翻译的缓存**

每次访存的虚拟地址都须经页表翻译为物理地址。为避免每次访问都遍历多级页表，MMU 将近期的翻译结果缓存在 TLB（Translation Lookaside Buffer）中：命中则直接得到物理地址；未命中则由硬件自动遍历页表并回填（这一硬件遍历正是 §6 中 perf 事件 `dtlb_walk` 统计的对象）。

**ASID：让多个地址空间的条目在 TLB 中共存**

每个进程有独立的页表，同一个虚拟地址在不同进程中翻译结果不同。若 TLB 条目不带任何归属标记，每次进程切换都必须清空整个 TLB，代价过高。arm64 的解决方案是 ASID（Address Space Identifier，地址空间标识符）：

- 内核为每个用户地址空间（`mm_struct`）分配一个 ASID（分配器位于 `arch/arm64/mm/context.c`，宽度 8 或 16 位，用尽后翻代回收）：

  ```c
  /* arch/arm64/include/asm/mmu.h:56 */
  #define ASID(mm)  (atomic64_read(&(mm)->context.id) & 0xffff)
  ```

- 切换地址空间时，ASID 随页表基址一起写入 TTBR 的高 16 位（`arch/arm64/include/asm/mmu_context.h:224`；寄存器位域定义见手册 D24.2.208 TTBR0_EL1：ASID 占 [63:48]，宽度 8 或 16 位由 TCR_ELx.AS 选择，内核经 `get_cpu_asid_bits()` 探测——代码中的 `<< 48` 即对应该字段）：

  ```c
  ttbr = phys_to_ttbr(virt_to_phys(mm->pgd)) | ASID(mm) << 48;
  ```

  ![TTBR0_EL1 位域格式](figures/ttbr0-el1-format.svg)

  *图：TTBR0_EL1 位域（手册 D24.2.208；图为 FEAT_D128 实现下的 128 位格式，经典 64 位格式中 ASID 同样位于 [63:48]）。*

- 此后硬件为该地址空间填入的每条 TLB 条目都带上此 ASID 标签，查找时只命中 "当前 ASID"的条目。用户页的页表项置 nG 位（not Global，`arch/arm64/include/asm/pgtable-hwdef.h:151` 的 `PTE_NG`）表示"按 ASID 匹配"；内核自身的全局映射不置 nG，对所有 ASID 可见。

效果：进程切换不再需要清空 TLB，多个进程的翻译条目可同时驻留，互不干扰。ASID 同时也成为 TLB 维护操作的一个"作用域键"——可以只作废某一个地址空间的全部条目，而不影响其他进程。

一个有助于理解"ASID 服务于谁"的细节：EL2 的页表基址寄存器 TTBR0_EL2 同样有 ASID 字段（手册 D24.2.209），但其描述明确规定该字段仅在实现 FEAT_VHE 且 `HCR_EL2.E2H = 1` 时生效，否则为 RES0。原因在于 ASID 只对**支持两个特权级**的翻译域有意义（D8.16.3）：VHE 模式下宿主机内核运行于 EL2、用户进程运行于 EL0，构成 EL2&0 双特权级翻译域，进程切换同样需要按 ASID 区分条目——这是 §2.1 中 VHE 宿主机行为与裸机一致的寄存器级基础。而本内核的 pKVM hypervisor 运行于 nVHE（E2H = 0），EL2 是单特权级翻译域：hypervisor 自身只有一个地址空间，其全部映射均为全局，该字段不生效——hyp 自身的 TLB 维护因此从不涉及 ASID。

![TTBR0_EL2 位域格式](figures/ttbr0-el2-format.svg)

*图：TTBR0_EL2 位域（手册 D24.2.209）。ASID 字段仅在 VHE（E2H=1）下生效，nVHE 下为 RES0。*

**VMID：stage-2 维度的"ASID"**

虚拟化引入第二级翻译后，TLB 条目还需要区分"属于哪个虚拟机的 stage-2 上下文"。这个标签是 VMID（Virtual Machine Identifier），由 VTTBR_EL2 寄存器携带，与 ASID 的关系是平行类比：**ASID 区分进程（stage-1 上下文），VMID 区分虚拟机或宿主机的 stage-2 上下文**。在 pKVM protected 模式下，宿主机自身也运行在一个 host stage-2 下，因此宿主机 TLB 条目会同时带 ASID 与 VMID 两类归属标签。

**一条 TLB 条目里存的不只是一对地址**。需要先说明：TLB 条目的真实格式属于 CPU 内部实现，软件看不到，内核里也没有任何代码定义它——ARM 体系结构手册明文规定 "架构不规定 TLB 的任何结构，仅要求其行为满足本节的约束"（DDI 0487 M.b，D8.16《Translation Lookaside Buffers》，规则 IZVNKM）。这与内存中页表描述符的格式（D8.3，精确规定到每一个比特，因为软件要亲手填写）形成对照：TLB 是硬件对遍历结果的私有缓存，架构只约束行为。下面的描述综合自 D8.16/D8.17 的行为约束，以及指令集留给软件的接口——"作废一条条目需要提供哪些键、漏了哪个键就清不干净"，反过来就说明条目登记了哪些信息。一条条目至少记录：

```
条目类型（单级还是两级合成，见下文）
归属标签（ASID 与 VMID）
输入地址及其覆盖范围、输出地址
页粒度与页表级别
访问权限与内存属性
```

这些字段不是凭空推测，内核发 TLBI 时必须把对应的"匹配键"重新编码出来：

1. **ASID/VMID 是匹配键**。按 VA 作废时，内核不会只传一个虚拟地址，而是把虚拟页号和 ASID 合成到同一个 TLBI 操作数里：

   ```c
   /* arch/arm64/include/asm/tlbflush.h:58 */
   #define __TLBI_VADDR(addr, asid)        \
   ({                                      \
       unsigned long __ta = (addr) >> 12;  \
       __ta &= GENMASK_ULL(43, 0);         \
       __ta |= (unsigned long)(asid) << 48;\
       __ta;                               \
   })
   ```

   `flush_tlb_mm()` 用 `ASID(mm)` 生成 `aside1is` 的操作数，`__flush_tlb_range_op()` 也先取 `ASID(vma->vm_mm)` 再发 `vae1is`。这和手册 D8.16 的上下文匹配规则一致：TLB 条目不是只按 VA 命中，还必须属于相同 ASID/VMID 的翻译上下文。

2. **页表级别和粒度可作为 TLBI hint**。arm64 支持 FEAT_TTL 时，内核会把"翻译粒度 + 页表级别"写入 TLBI 操作数的 TTL 字段：

   ```c
   /* arch/arm64/include/asm/tlbflush.h:105 */
   if (cpus_have_const_cap(ARM64_HAS_ARMv8_4_TTL) && level) {
       u64 ttl = level & 3;
       ttl |= get_trans_granule() << 2;    /* 4K/16K/64K 粒度 */
       arg &= ~TLBI_TTL_MASK;
       arg |= FIELD_PREP(TLBI_TTL_MASK, ttl);
   }
   __tlbi(op, arg);
   ```

   `mmu_gather` 在拆页时记录 `cleared_ptes/cleared_pmds/...`，arm64 的 `tlb_get_level()` 再把它转成 level hint。手册 D8.17 规定 TTL 级别不正确时架构不保证作废目标条目；这说明硬件条目至少按"哪一级、什么粒度"参与维护匹配。

3. **权限/属性也缓存在条目里**。`mprotect` 改权限时，内核先清旧 PTE、构造新 PTE，再在需要时登记一次 PTE 级 TLB flush：

   ```c
   /* mm/mprotect.c:166 */
   oldpte = ptep_modify_prot_start(vma, addr, pte);
   ptent = pte_modify(oldpte, newprot);
   ptep_modify_prot_commit(vma, addr, pte, oldpte, ptent);
   if (pte_needs_flush(oldpte, ptent))
       tlb_flush_pte_range(tlb, addr, PAGE_SIZE);
   ```

   在本 arm64 代码中，`ptep_modify_prot_start()` 会先移除旧 PTE：普通路径走 `ptep_get_and_clear()`，受特定 erratum 影响的 executable→non-executable 权限变化则走 `ptep_clear_flush()`（`arch/arm64/mm/mmu.c:1470-1482`）。`pte_needs_flush()` 使用 generic 默认实现（`include/asm-generic/tlb.h:737`，返回 true），因此权限修改会纳入 `mmu_gather` 的 TLB 刷新范围。若 TLB 条目没有缓存访问权限/内存属性，修改 PTE 权限后就不需要这一步；实际代码恰恰说明旧条目必须作废，硬件才会重新取到新权限。

**虚拟化下的三类条目，以及硬件如何区分 IPA 与 PA**。stage-2 开启后，翻译变成两级（VA→IPA→PA），TLB 相应可以缓存三类条目（手册原文即按"仅含 stage-1 信息的条目"与"合并 stage-1 与 stage-2 信息的条目"区分，见 D8.16.3.4；维护规则也按 stage-1 结构 / stage-2 结构 / 两级合并结构三类分别规定作用范围，见 D8.17）：

| 条目类型 | 内容 | 用途 |
|---|---|---|
| 合成（combined） | VA→PA，两级折叠后的最终结果 | CPU 访存的主路径，一次命中直接得到 PA |
| stage-1 单级 | VA→IPA | 中间结果 |
| stage-2 单级 | IPA→PA | 页表遍历器翻译描述符地址时使用 |

典型实现中，访存快路径上的 TLB 只存放合成条目——一次命中直接出 PA，两级翻译的存在对命中路径没有额外成本。这是 §3.3"稳态访问两模式无差异"的微架构原因。

一个自然的疑问：条目里既有 VA→PA 也可能有 VA→IPA，查询命中后返回的地址，硬件怎么知道它是终点（PA）还是中间值（IPA）？答案分两半。其一，**查询返回的不是一个裸地址，而是整条条目**，条目类型就写在条目里：命中合成条目，输出即 PA，直接发往内存系统；命中 stage-1 单级条目，输出是 IPA，MMU 接着对它做 stage-2 查找，拿到 PA 才放行。其二，**每次查找也声明自己要找什么**：CPU 访存发起的是 "VA 查找"，只匹配合成/stage-1 条目；页表遍历器读取描述符时发起的是"IPA 查找"，只匹配 stage-2 条目。地址数值本身从不自我描述，类型既在条目里、也在查找请求里，数值相同的 VA 与 IPA 不会互相误命中。

这个"条目分类型"的设计在指令集上留有直接证据：作废指令按条目类型分设。可以用一个例子理解：

```
进程访问 VA A
  stage-1: A -> IPA X
  stage-2: X -> PA Y

硬件可能缓存两类结果：
  combined 条目：A -> Y   （给 CPU 访存快路径用，按 VA/ASID/VMID 这类 stage-1 上下文匹配）
  stage-2 条目：X -> Y    （给页表遍历器等 stage-2 查询使用，按 IPA/VMID 匹配）
```

如果 EL2 修改了 stage-2 页表，把 `IPA X -> PA Y` 改掉，单发 `ipas2e1is X` 只能可靠清掉按 IPA 匹配的 stage-2 条目。它不能被当作"把所有用过 IPA X 的 combined 条目也找出来"的保证，因为 combined 条目是 VA 侧快路径缓存，可能有很多 VA/ASID 都曾经经由 `IPA X` 合成出最终 PA。手册 D8.17 对此给出的规则也正是这个边界：仅作用于 stage-2 条目的维护操作，不要求作用于合并 stage-1 与 stage-2 信息的结构。

这两个指令名本身就说明了作用范围：

| 指令 | 助记符拆解 | 作用对象 |
|---|---|---|
| `ipas2e1is` | `IPA` = Intermediate Physical Address，`S2` = stage-2，`E1` = EL1&0 翻译域，`IS` = Inner Shareable | 按 IPA 作废当前 VMID 下的 stage-2-only 条目 |
| `vmalle1is` | `VMALL` = 当前 VMID 下全部，`E1` = EL1&0 翻译域，`IS` = Inner Shareable | 作废当前 VMID 下 EL1 相关的 stage-1/combined 条目 |

所以本内核 hypervisor 修改 stage-2 页表后的作废序列（`tlb.rs:305-312`）是两步：

```rust
__tlbi_level!(ipas2e1is, ipa, level);  // 先按 IPA 清 stage-2-only 条目
dsb(ISH);
__tlbi!(vmalle1is);                    // 再按当前 VMID 清 EL1 stage-1/combined 条目
```

第二步比"只清某个 IPA"更粗，但它是安全兜底：既然没有 VA 列表可用，就把当前 VMID 下可能依赖旧 stage-2 结果的 stage-1/combined 条目一起作废。换句话说，combined 条目让访存命中路径很快（一次命中直接得到 PA），但当底层 stage-2 映射变化而软件又只有 IPA 信息时，作废就必须扩大作用域。§7.7 中 pKVM 下逐页 TLBI 变贵，也是在这个"合成条目参与维护"的背景下发生的。

与本报告直接相关的推论：pKVM 的 protected 模式下，宿主机自身也运行在一个 host stage-2 之下，于是宿主机的 TLB 条目从 nvhe 模式的"纯 stage-1、仅 ASID 标记"，变为"stage-1 与 stage-2 **合成**（即上文三类条目中的 combined）、同时带 ASID 与 VMID 标记"。同一条 `tlbi vae1is` 指令，在两种模式下需要查找并作废的条目种类因此不同——这是 §7.7 解释"每条 TLBI 为何更昂贵"的体系结构基础。

**TLBI：按不同的键作废 TLB 条目**

页表项被修改或删除后，TLB 中缓存的旧翻译必须作废，否则硬件会继续使用过时的映射——这由 TLBI（TLB Invalidate）指令族完成。与本报告相关的三条，按作废范围从小到大：

| 指令 | 作废范围 | 典型用途 |
|---|---|---|
| `tlbi vae1is, <VA\|ASID>` | 指定虚拟地址、且 ASID 匹配的条目 | 逐页精确作废 |
| `tlbi aside1is, <ASID>` | 该 ASID 的**全部**条目 | 一次作废整个地址空间（大范围 munmap、进程退出） |
| `tlbi vmalle1is` | 当前 VMID 下 EL1 的全部 stage-1/combined 条目 | 更大范围的维护操作 |

操作数的编码由 `__TLBI_VADDR`（`tlbflush.h:58`）完成：虚拟页号占低 44 位，ASID 占 [63:48]。两点补充：

- 指令助记符中的 `is` 后缀表示 Inner Shareable：作废请求不只作用于本核，还要经 DVM（Distributed Virtual Memory）消息广播到内部共享域的所有核心——其他核的 TLB 同样可能缓存了该条目。发出一批 TLBI 后须以 `dsb ish` 屏障等待这些失效对共享域可见。因此 **TLBI 的可观测成本主要体现为 shareable 失效的完成等待，而不在指令发射本身**——这是理解 §7.7 的关键；本文不会把这笔等待进一步武断归因到“广播网络”这一单一环节。
- 运行时实际启用 KPTI（内核页表隔离）时，同一进程的内核态与用户态使用一对 ASID，`__tlbi_user()`（`tlbflush.h:52`）会在 `arm64_kernel_unmapped_at_el0()` 为真时对用户 ASID 追加一条同类 TLBI，基础作废序列随之翻倍。仅有内核配置支持 KPTI 并不等同于运行时一定开启。

内核实现上还隔着一层批量化：清 PTE 的地方通常只调用 `tlb_remove_tlb_entry(s)` 把被拆除的地址范围登记到 `mmu_gather`，并不立即发 TLBI；真正的作废在 `tlb_flush_mmu_tlbonly()` / `tlb_finish_mmu()` 阶段统一执行。这个分层解释了为什么 §7.4 讨论"单次 `flush_tlb_range` 覆盖的范围"：阈值判断用的不是单个 PTE，而是 `mmu_gather` 累积后的 `start/end`。完整调用链与源码见 §7.4。

**与本报告的衔接**：munmap 是"修改页表后必须作废 TLB"的典型场景。内核在 "逐页精确作废（N 个 4K flush slot，每个 slot 触发基础 `vae1is` 序列）"与"按 ASID 全部作废（1 条基础 `aside1is` 序列，代价是连未拆除区域的条目也一并失效、事后需重新填充）"之间的选择策略——2 MB 阈值——在 §7.4 分析；这一选择在 pKVM 下的成本差异正是本调查的核心。

### 2.4 测试对象：lmbench lat_mmap

`lat_mmap` 是 lmbench 中测量内存映射延迟的基准。其计时循环（`src/lat_mmap.c:145`，`domapping()`，kylin-lmbench 仓库）如下：

```c
while (iterations-- > 0) {
    where = mmap(0, size, PROT_READ|PROT_WRITE, MAP_FILE|MAP_SHARED, fd, 0);
    ...
    end = where + (size / N);              /* N = 10：只触摸前 1/10 */
    for (p = where; p < end; p += PSIZE)   /* PSIZE = 16 KB：触摸步长 */
        *p = c;
    munmap(where, size);
}
```

三点对理解全文至关重要：

1. **计时区覆盖完整生命周期**：一次迭代包含建立映射（mmap）、写触摸（触发缺页、建立页表项）、拆除映射（munmap）三段。`lat_mmap` 报告的是三段之和，单看总时间无法知道开销位于哪一段——这是阶段二拆分实验的动机。
2. **触摸是稀疏的**：仅触摸前 `size/10` 字节，步长 16 KB（`PSIZE`），即每 4 页触摸 1 页。64 MB 映射实际触摸约 410 个 4 KB 页。这一触摸范围与步长的特征在阶段五被证明是退化显现的必要条件。
3. **文件映射**：`MAP_FILE | MAP_SHARED`，后备文件预先填充，排除稀疏文件因素。

由于 lmbench 原版在大尺寸下输出整数微秒（`micromb()`），仓库提供了语义等价的纳秒精度复测工具 `src/lat_mmap_precise.c`：同样的 `MAP_SHARED`、`PSIZE=16KB`、`N=10` 触摸方式（同样的触摸范围与步长），计时改用 `clock_gettime(CLOCK_MONOTONIC)`。两者结果方向一致（§3.2），本报告以精测数据为主。

### 2.5 测试平台与环境控制

调查先后使用三块板（详表见附录 A）：N90（现象确认）、Kaitian（拆分实验与应用级验证）、N80（EL2 判别与机制判定）。三块板均为 Phytium aarch64 / Kylin V10，现象方向一致，量级随平台不同。

为控制噪声，正式对照实验统一执行以下环境控制（`prepare-host.sh` 及其 V10 变体）：

- CPU governor 设为 performance，全部核心锁定同一频率（N90 为 2.1 GHz，N80 为 1.8 GHz）；
- 关闭透明大页（THP=never）与地址空间随机化（ASLR=0）；
- 关闭深度 cpuidle 状态（PSCI idle 经 SMC 进入 EL2，会污染 EL2 周期计数）；
- 基准进程以 `taskset` 绑定到固定核心（cpu0）；
- 停止桌面、更新、打印等无关后台服务，保留网络与 SSH（`quiet-host.sh`）。

统计口径：每组配置重复 10 轮取中位数，以 MAD%（中位数绝对偏差相对中位数的百分比）衡量稳定性。后文关键数据的 MAD% 大多低于 1%。

---

## 3. 阶段一：现象确认——四种 KVM 模式对照（N90）

### 3.1 实验设计

要回答的问题：**宿主机 `lat_mmap` 的退化是否由 pKVM 模式本身引入？**

设计要点：在同一块板（N90）、同一个内核镜像上，仅改变 `kvm-arm.mode` 启动参数，分别以四种模式启动并运行同一套宿主机侧测试。这样四组数据之间唯一的系统性差异就是 KVM 模式，凡是四种模式共有的因素（CPU、内存、内核版本、文件系统、后台负载控制）都被对照设计消去。每种模式的启动状态以 cmdline 与 dmesg 双重确认（例如 pKVM 须出现 `CPU features: detected: Protected KVM`）。

测试项包括 `lat_mmap`（原版与精测版）与两类稳态访问对照项：`bw_mmap_rd`（已建立映射上的顺序读带宽）以及早期数据集中的 `lat_mem_rd` / `bw_mem`。稳态对照项的作用是判别开销的位置：若 pKVM 的开销发生在"每次内存访问"上，稳态项应同步退化；若只发生在"映射生命周期"上，稳态项应不受影响。

### 3.2 结果：lat_mmap 的退化

`lat_mmap_precise`，N=10 中位数，单位 µs（内核 `6.6.30+ #4`，2026-06-09，原始数据 `results/n90-v10-mmap-4mode-summary.txt`）：

| size | KVM-off | VHE | NVHE | pKVM | pKVM vs NVHE |
|---:|---:|---:|---:|---:|---:|
| 0.5 MB | 10.356 | 10.430 | 10.363 | 13.438 | +29.68% |
| 1 MB | 13.787 | 13.699 | 13.761 | 19.649 | +42.79% |
| 2 MB | 20.526 | 20.296 | 20.554 | 31.348 | +52.51% |
| 4 MB | 33.100 | 33.382 | 32.925 | 56.237 | +70.80% |
| 8 MB | 59.623 | 59.363 | 59.851 | 106.872 | +78.56% |
| 16 MB | 110.992 | 110.677 | 110.545 | 205.056 | +85.50% |
| 64 MB | 443.084 | 441.221 | 441.187 | **816.318** | **+85.03%** |

三个非 pKVM 基线彼此差异小于 0.25%，而 pKVM 单独显著偏离；且相对退化随映射尺寸单调增大（+29% → +85%）。64 MB 各列 MAD% 均不超过 0.254%，数据稳定。原版 lmbench `lat_mmap` 给出同向结果（64 MB：429 µs 对 807 µs）。

更早（2026-06-04）在 N90 / Kylin V11 / `6.6.0-73` 环境下的一组独立四模式数据显示同向退化，但幅度较小（64 MB 约 +42%）。两组数据共同说明：退化方向稳定存在，幅度与内核版本和系统环境相关。

### 3.3 对照结果：稳态内存访问不受影响

与 `lat_mmap` 形成鲜明对比，已建立映射上的访问在四种模式下没有可比量级的差异。

本轮（V10）`bw_mmap_rd` 67.11 MB 顺序读带宽：

| 模式 | 带宽 | MAD% |
|---|---:|---:|
| KVM-off | 15919.6 MB/s | 0.408% |
| VHE | 15157.3 MB/s | 0.231% |
| NVHE | 14910.6 MB/s | 0.244% |
| pKVM | 14958.0 MB/s | 0.345% |

早期数据集（V11）中的稳态项同样如此：`lat_mem_rd` 64 MB（DRAM 区）四模式均约 10.3 ns/访问（差异 ≤ ±3.5%）；`bw_mem` 峰值带宽四模式差异小于 0.5%。

两类测试的差别在于计时区内容：`lat_mem_rd` / `bw_mem` 在计时开始前已把工作集全部触摸完毕（页表已建好），计时区内只有纯粹的访存；`lat_mmap` 则把映射的建立、首次触摸与拆除全部计入。稳态项无差异、生命周期项大幅退化，说明 **pKVM 的开销集中在映射生命周期操作中，而不是分摊在每次内存访问上**。

### 3.4 交叉验证：C 实现 pKVM 内核复测

本内核的 EL2 部分为 Rust 实现，需排除"退化由 Rust 实现引入"的可能。在同一块 N90 上换装原 C 实现 pKVM 的内核（`6.6.30-pkvm-c+ #6`），以完全相同的条件补齐四模式：

| size | C KVM-off | C VHE | C NVHE | C pKVM | C pKVM vs C NVHE |
|---:|---:|---:|---:|---:|---:|
| 64 MB | 442.237 | 442.533 | 440.190 | 814.996 | +85.15% |

C pKVM 与 Rust pKVM 的 64 MB 精测仅差 −0.16%，非 pKVM 基线亦与 Rust 内核重合（±0.3%）。**退化是 pKVM protected 模式路径本身的代价，与具体实现语言无关。**

### 3.5 阶段结论与初期机制假设

阶段一确立的事实：退化由 host stage-2 的存在引入（四模式中唯一的结构性差异，见 §2.1 表），且位于映射生命周期内。

当时对机制的推测是 **first-touch 建表开销**：写触摸每碰到一个尚未在 host stage-2 中映射的页，硬件触发 stage-2 缺页陷入 EL2，由 `handle_host_mem_abort()` 建立映射后返回。该假设有一项定量支持：早期数据集中，pKVM 相对基线的额外时间与触摸页数高度线性——按 `lat_mmap` 的触摸方式（每次迭代触摸 `size/(10×16KB)` 页）折算，每次缺页的摊销成本自 1 MB 起稳定在 505±10 ns，与一次完整"异常进入 → 读取 ESR/HPFAR/FAR → 加锁 → 页表遍历 → 建表 → TLBI/DSB → 异常返回"流程的量级估算相符。

线性关系本身是真实的，但"线性 ∝ 触摸页数"并不能区分"开销发生在触摸时"还是 "开销发生在拆除已触摸页时"——两者都与触摸页数成正比。区分它们需要把生命周期拆开计时，这就是阶段二。该假设在阶段二被修正。

### 3.6 应用级旁证：LMDB（Kaitian）

为确认微基准信号是否传导到真实应用，在 Kaitian 上以 LMDB（典型的 mmap 型嵌入式数据库）做了 NVHE 对 pKVM 的对照（5 轮中位数，`NOSYNC` 模式以排除存储设备同步延迟的干扰）：

| 指标 | NVHE | pKVM | pKVM 相对变化 |
|---|---:|---:|---:|
| openclose（反复打开/关闭环境） | 85.981 µs/op | 116.336 µs/op | **+35.30%** |
| read（长期映射上的随机读） | 1220.0 ns/op | 1237.2 ns/op | +1.41% |
| write（追加写事务） | 560.0 ns/op | 559.5 ns/op | −0.10% |

LMDB 在 `mdb_env_open` 时建立映射、长期复用、关闭时拆除。结果与微基准的结论完全一致：**频繁建立/拆除映射的路径（openclose）受到明显影响，长期复用映射后的常规读写几乎不受影响。** 这也界定了该退化的实际影响范围（详见 §8.2）。

---

## 4. 阶段二：生命周期拆分——定位到写触摸后的 munmap（Kaitian）

### 4.1 实验设计

要回答的问题：**816 µs 中，建立映射、写触摸、拆除映射各占多少额外时间？**

`lat_mmap` 的计时区是三段之和，无法区分。为此编写了拆分基准 `experiments/mmap-split/mmap_split_bench.c`，将生命周期拆成 12 个子测试，每个子测试只把一段操作放入计时区，其余作为不计时的准备工作。设计原则：

- **触摸范围与步长和 `lat_mmap` 完全一致**（`touch_divisor=10`、`stride=16KB`），保证子测试之和能对应回原始现象；
- 计时同样使用 `CLOCK_MONOTONIC`，每个子测试、每个尺寸跑 10 轮取中位数，正式计时前先跑 1 轮不计时样本；
- 在 Kaitian 上以 NVHE 与 pKVM 两种模式启动，使用同一命令口径：

```bash
MODE=<nvhe|pkvm> CORE=0 RUNS=10 REFILL=1 WARMUPS=1 scripts/mmap-split-bench.sh
python3 scripts/analyze-mmap-split.py nvhe pkvm
```

12 个子测试中与结论直接相关的 5 个：

| 子测试 | 计时区 | 隔离的对象 |
|---|---|---|
| `mmap_unmap` | mmap → munmap（无触摸） | VMA 的建立与删除 |
| `write_touch_cold` | 仅首次写触摸（mmap/munmap 不计时） | 缺页、建表、首次写入 |
| `munmap_after_no_touch` | 仅 munmap（之前未触摸） | 未触摸映射的拆除 |
| `munmap_after_write_touch` | 仅 munmap（之前已写触摸） | **写触摸后的映射拆除** |
| `mmap_write_touch_unmap` | 全程（≈ 原版 lat_mmap） | 完整写路径，作为对照锚点 |

### 4.2 测试代码与计时边界

关键在于计时边界的精确性。以最重要的 `munmap_after_write_touch` 为例（`mmap_split_bench.c:231`，`bench_munmap_only()`）：

```c
static double bench_munmap_only(const struct cfg *c, int touch_kind)
{
    int fd = open_checked(c->path, c->size);
    double total = 0.0;
    for (int i = 0; i < c->iters; ++i) {
        char *p = map_checked(fd, c, 0);
        if (touch_kind == 1)
            write_touch(p, c);          /* 写触摸：不计时 */

        double t0 = now_ns();
        unmap_checked(p, c->size);      /* 仅 munmap 计时 */
        total += now_ns() - t0;
    }
    close(fd);
    return total;
}
```

`write_touch()` 按 `stride`（16 KB）写前 `touch_bytes`（`size/10`）字节，与 `lat_mmap` 的触摸循环逐字对应。其余子测试同理，仅计时边界不同。

### 4.3 结果

Kaitian，NVHE 对 pKVM，10 轮中位数，单位 µs/iteration（完整数据见 `results/mmap-split-kaitian/{nvhe,pkvm}.csv`）。64 MB 行：

| 子测试 | NVHE | pKVM | Δ | Δ% |
|---|---:|---:|---:|---:|
| `mmap_unmap` | 3.210 | 3.247 | +0.037 | +1.15% |
| `write_touch_cold` | 333.541 | 346.159 | +12.618 | **+3.78%** |
| `munmap_after_no_touch` | 1.521 | 1.515 | −0.005 | −0.35% |
| **`munmap_after_write_touch`** | **90.215** | **295.219** | **+205.003** | **+227.24%** |
| `mmap_write_touch_unmap`（全程） | 428.058 | 642.383 | +214.325 | +50.07% |

`munmap_after_write_touch` 的退化随尺寸单调放大，且各尺寸 MAD% 均较低：

| size | NVHE µs | pKVM µs | Δ µs | Δ% |
|---:|---:|---:|---:|---:|
| 0.5 MB | 3.065 | 4.498 | +1.433 | +46.77% |
| 1 MB | 4.308 | 7.216 | +2.907 | +67.48% |
| 2 MB | 6.581 | 12.923 | +6.342 | +96.37% |
| 4 MB | 9.284 | 22.424 | +13.140 | +141.53% |
| 8 MB | 14.759 | 40.977 | +26.218 | +177.64% |
| 16 MB | 25.838 | 77.434 | +51.597 | +199.70% |
| 64 MB | 90.215 | 295.219 | +205.003 | +227.24% |

注：上表差距随尺寸线性增长（包括触摸跨度已达 6.4 MB、超过 2 MB 的 64 MB 行），与后文 §7.4 的"2 MB 整表刷新阈值"并不矛盾。64 MB 行看起来是大映射，但内核并不是一次刷新 64 MB，也不是一次刷新实际触摸的 6.4 MB；写触摸产生的脏页使刷新按 PMD 分批，16 KB 稀疏步长又让每批约为 `2 MB - 12 KB`，恰好低于整表阈值，所以这些小批次仍然逐页刷新并不断累加。定量解释见 §7.5 末尾的补充分析"阈值作用的真实粒度"。

其余子测试（openclose、`MAP_POPULATE` 变体、热触摸、读路径等）的完整数据与分析见附录 D 所列拆分实验详报；要点是：文件打开/关闭、VMA 建删、稳定映射上的反复读写在两模式下均基本持平；读触摸路径方向一致，但其 64 MB 行差距反常消失（−1.88%）——该现象的机制（干净页不强制分批、刷新范围累积越过阈值改走整表路径）同样见 §7.5 末尾的补充分析，故结论以行为更确定的写路径为准。

### 4.4 分析：第一次结论修正

三条推论：

1. **【修正一】first-touch 不是主因。** `write_touch_cold` 把全部缺页、建表与首次写入隔离在计时区内，64 MB 下仅 +12.6 µs（+3.78%）。若阶段一的"每次缺页约 500 ns"假设成立，此处应出现约 +205 µs 的差距（410 次缺页 × 500 ns），实测只有其 1/16。早期数据的线性关系实际反映的是"额外开销 ∝ 触摸页数"，而触摸页数同时决定了 munmap 需要拆除的页表项数量——线性证据与修正后的结论同样相容。
2. **瓶颈是写触摸后的 munmap。** 单独这一段的额外时间（+205.0 µs）即可解释完整写路径额外时间（+214.3 µs）的 95.7%。
3. **munmap 本身并不慢。** 未触摸映射的 munmap（`munmap_after_no_touch`）两模式均约 1.5 µs。只有当映射被真实触摸、建立了页表项之后，拆除才触发额外成本——munmap 的开销取决于"有多少东西要拆"，与 §2.2 对拆除路径工作量来源的分析一致。

### 4.5 引出的问题：munmap 的额外时间从何而来

这一定位带出一个表面上的矛盾：宿主机的 munmap 是纯粹的 EL1 内核路径（`__vm_munmap` → `unmap_region` → …），按体系结构设计它不发起 hypercall、不被陷入、对已映射的宿主机页也不触发 stage-2 缺页（详细论证见 §5.1）——**理论上它根本不进入 EL2**。那么 +205 µs 从何而来？逻辑上只有两种可能：

```
(a) 宿主机侧硬件成本：host stage-2 使能后，munmap 拆除路径中某些硬件操作
    （TLB 失效广播、页表遍历、访存）单位代价增加，全程仍在 EL1 完成；
(b) 隐藏的 EL2 路径：存在未被注意的进入 EL2 的途径（例如 hyp 页表池耗尽
    触发回收，引发缺页风暴）。
```

两者的优化方向完全不同：(a) 应分析宿主机侧硬件行为，(b) 应在 hypervisor 内部插桩。先用一个判别实验确定方向，避免在错误的一侧投入——这就是阶段三。

---

## 5. 阶段三：EL2 判别——证明退化不发生在 hypervisor 内（N80）

自本阶段起，实验平台换为 N80（1.8 GHz，Kylin V10 SP1，内核 `6.6.30xcore-stat+`）。N80 上该退化的复现幅度更大：`munmap_after_write_touch` 64 MB 下 protected 比 NVHE 慢 1.81 倍（+447 µs/iter，见 §6.2），适合作为判别与定因的平台。

### 5.1 体系结构分析：host munmap 理论上不进入 EL2

先从代码上确认"理论上不进 EL2"的依据。NVHE/protected 模式下，宿主机 EL1 的执行只在三类情况下进入 EL2，这直接体现在 EL2 异常分发函数 `handle_trap()`（`hyp_main.rs:3004`）的分支上：

```rust
match ec {
    HVC64 => host_ctxt.handle_host_hcall(),                  // 显式 hypercall
    SMC64 => host_ctxt.handle_host_smc(),                    // SMC（protected 下陷入）
    TrappedFP | TrappedSve | TrappedSME => fpsimd_host_restore(), // FP/SVE 惰性恢复
    InstrAbortLowerEL | DataAbortLowerEL =>
        host_ctxt.handle_host_mem_abort(),                   // host stage-2 缺页
    _ => { /* 默认处理，否则 bug_on */ }
}
```

普通 munmap 不触发其中任何一类：

- **不发起 hypercall**：munmap 走通用 mm 路径，其 TLB 失效由 arm64 的 `__tlbi()` 宏直接展开为 `tlbi` 指令（`arch/arm64/include/asm/tlbflush.h:40`，`asm("tlbi " #op ", %0")`），在 EL1 直接执行，不是 HVC。
- **TLBI/DSB 不被陷入**：要使 EL1 发起的 TLB 维护指令陷入 EL2，须在 `HCR_EL2` 中置 `TTLB`/`TTLBIS`/`TTLBOS` 位。而宿主机的 HCR 配置（`arch/arm64/include/asm/kvm_arm.h:101`）不含这些位：

  ```c
  #define HCR_HOST_NVHE_FLAGS           (HCR_RW | HCR_API | HCR_APK | HCR_ATA)
  #define HCR_HOST_NVHE_PROTECTED_FLAGS (HCR_HOST_NVHE_FLAGS | HCR_TSC)
  ```

  protected 相比 nvhe 仅多陷入 SMC（`HCR_TSC`），TLB 维护指令均不被拦截。
- **不触发 stage-2 缺页**：宿主机内存在 host stage-2 中按"宿主机拥有 + 恒等映射" 管理，首次访问后映射常驻；munmap 是 stage-1 操作，不改变页的所有权，不会使 host stage-2 产生缺页（所有权语义与映射长期有效性的完整论证见 §2.1）。（§5.5 的实测进一步佐证：连首次触摸路径的 ΔEL2 也为 0，因为基准的后备文件页早已驻留。）

体系结构分析支持"不进 EL2"，但分析不能代替测量——隐藏路径假设 (b) 正是要靠测量排除的。

### 5.2 测量方法：仅统计 EL2 的周期计数

arm64 PMU 的周期计数器 `PMCCNTR_EL0` 默认统计所有异常级的周期，但其过滤寄存器 `PMCCFILTR_EL0` 支持按异常级过滤。将其配置为"仅在 EL2 执行时递增"，计数器读数即为该 CPU 累计花费在 EL2 的周期数；在被测负载前后各读一次，差值就是负载期间进入 EL2 的总周期。这把"munmap 是否进入 EL2"变成一个可直接测量的量。

EL2 侧配置由 `xcore_enable_pmu_el2()` 完成（`stats.rs:48`，节选）：

```rust
const PMCCFILTR_EL2_ONLY: u64 = bit!(31) | bit!(30) | bit!(27) | bit!(26);
// bit31/30 屏蔽 EL1/EL0 计数，bit27/26 放行非安全 EL2 —— 净效果为仅统计 EL2 周期

MDCR_EL2 |= bit!(7);                  // HPME：使能 EL2 的 PMU
PMCCFILTR_EL0.set(PMCCFILTR_EL2_ONLY);
PMCNTENSET_EL0 |= bit!(31);           // 打开周期计数器
// PMCR_EL0：置 E（使能）、LC（64 位防溢出）、C（一次性清零），清 D（÷64 分频）
```

该函数按 per-CPU 保存原 PMU 现场，`xcore_disable_pmu_el2()` 时恢复，避免污染宿主机自身的 perf 使用（清位须写 `PMCNTENCLR_EL0`，因 `PMCNTENSET` 为置位型寄存器）。

宿主机侧通过 `/proc/xcore_stats`（`arch/arm64/kvm/xcore_stats.c`）触发与读取：`echo 1` 首次写入时对每个在线 CPU 经专用 hypercall（`__pkvm_xcore_stats`）执行 enable（含一次计数器清零），其后的 `echo 1` 仅在 EL1 直接 `read_sysreg(PMCCNTR_EL0)` 读数、不再 enable——因此计数器只清零一次、持续累加，读取本身不进入 EL2，对被测量的污染可忽略。

两点方法学约束：

- **读数语义为累计值**，脚本须自行取前后差；
- **PMU 为物理资源**，本计数与宿主机 perf（阶段四）不能同窗使用，测量顺序上先 gate 后 perf，中间 `echo 0` 释放。

### 5.3 测量脚本与噪声控制

`scripts/el2-gate-bench.sh` 的核心流程：

```bash
read_el2_cycles() { echo 1 > /proc/xcore_stats; awk -v c=$CORE '$1==c{print $2}' /proc/xcore_stats; }
# 绑核；关闭 cpuidle（PSCI idle 经 SMC 进入 EL2，会计入计数）；锁频 performance
for size in $SIZES; do
  c0=$(read_el2_cycles); t0=$(date +%s.%N)
  taskset -c $CORE $BENCH munmap_after_write_touch $size $ITERS $FILE ...
  t1=$(date +%s.%N); c1=$(read_el2_cycles)
  delta=$((c1-c0))                                  # 负载窗口的 EL2 周期
  e0=$(read_el2_cycles); sleep $wall; e1=$(read_el2_cycles)
  empty=$((e1-e0)); net=$((delta-empty))            # 扣除等时长空窗的背景噪声
done
```

空窗扣噪的原因：计数器统计的是该 CPU 全部 EL2 周期，包含定时器中断等与基准无关的背景活动；以等时长的空闲窗口测得背景量并扣除，余量才是基准自身引入的 EL2 周期。

判读标尺：将"protected 比 nvhe 每次迭代多花的时间 × CPU 频率"作为该额外时间 **若全部花费在 EL2** 所对应的周期数上限。N80 下为 +447 µs × 1.8 GHz ≈ 80 万周期/迭代。实测净值远小于该上限的 5% 即可判定 EL2 解释不了这笔退化。

### 5.4 计数器有效性验证

判别实验的预期结果是 0，而"读数为 0"与"计数器没有工作"不可区分，因此必须先做阳性对照——用一个确定进入 EL2 且不触碰 PMU 开关的负载验证计数器确实在累加。选用 `echo 2`（op=2，内存统计 hypercall，进入 EL2 遍历 pKVM 页表，工作量大）：在目标 CPU 上连续触发 200 次，前后读数 57 → 168,083,716，**ΔEL2 = 168,083,659 周期**（约 84 万周期/次），计数器随真实 EL2 负载精确累加。

（曾排查过一处疑点：若每次 enable 都附带 `PMCR.C` 清零，则每次读取前计数器都会被清零、差值恒为 0。复查 `xcore_stats.c` 确认 enable 受 `if (!pmu_enabled)` 门控、仅首次执行，疑点排除；上述阳性对照亦从实测层面确认了这一点。）

### 5.5 结果

N80，protected 模式，ITERS=100（原始数据 `results/n80-munmap-gate-c0/protected/gate-out/el2-gate-protected.csv`）：

| size | el2_cycles_delta | el2_cycles_empty | net | wall (s) |
|---:|---:|---:|---:|---:|
| 8 MB | 0 | 0 | **0** | 0.015 |
| 16 MB | 0 | 0 | **0** | 0.026 |
| 64 MB | 0 | 0 | **0** | 0.097 |

补充判别（ITERS=20）：`mmap_write_touch_unmap`、`write_touch_cold`、`munmap_after_write_touch` 的净值均为 0——不仅 munmap，整个触页路径都不进入 EL2。

### 5.6 阶段结论

计数器经 1.68 亿周期的阳性对照验证有效，而被测项 ΔEL2 = 0（上限约 80 万周期/迭代，实测 0）。**假设 (b) 被排除：退化不发生在 EL2 软件路径中，宿主机 munmap 全程在 EL1 完成。** 后续分析转向宿主机侧硬件成本（假设 (a)），同时省去了在 hypervisor 内部做细粒度插桩的整条路线——那些插桩点的读数必然为 0。

---

## 6. 阶段四：宿主机侧成本分层——perf 事件分解（N80）

### 6.1 事件选择的依据

要回答的问题：**额外的 +447 µs/iter 花费在宿主机的哪一层？** 使用宿主机 perf 对 `munmap_after_write_touch`（64 MB × 50 次迭代，绑定 cpu0）做事件计数。事件不是随意罗列的，每个事件对应一个需要确认或排除的具体猜想：

```bash
perf stat -e cycles,instructions,page-faults,l1d_tlb_refill,l2d_tlb_refill,r34,stall_backend \
  -- taskset -c $CORE mmap_split_bench munmap_after_write_touch 64 50 ...
```

| 事件 | 对应的问题 |
|---|---|
| `cycles` + `instructions` | 两模式是否执行同样多的指令？若指令数不同，差异属于"软件多做了工作"，无需讨论硬件 |
| `page-faults` | 负载锚点：两模式缺页数必须相同，否则比较的不是同一负载 |
| `r34`（DTLB_WALK，0x34） | stage-1 页表遍历的**次数**：直接检验"遍历更多次"类解释 |
| `l1d_tlb_refill` / `l2d_tlb_refill` | TLB 重填量：TLBI 活动的旁证 |
| `stall_backend` | 后端（访存）停顿周期：把"慢"定位到访存等待还是其他环节 |

（`dtlb_walk` 在该平台未经 sysfs 暴露命名事件，使用原始编码 `r34`。）

### 6.2 结果

N80，`munmap_after_write_touch` 64 MB × 50，nvhe 对 protected（原始数据 `results/n80-munmap-gate-c0/{nvhe,protected}/c0-*/perf-*.txt`）：

| 指标 | nvhe | protected | Δ（protected − nvhe） |
|---|---:|---:|---:|
| 墙钟时间 (s) | 0.027650 | 0.049980 | **×1.81（+447 µs/iter）** |
| cycles | 49,032,232 | 88,812,432 | **+39,780,200（+81%）** |
| instructions | 81,894,221 | 81,942,093 | +0.06%（相同） |
| IPC | 1.67 | 0.92 | −45% |
| **stall_backend** | 18,167,855 | 59,061,228 | **+40,893,373（+225%）** |
| page-faults | 21,013 | 21,011 | ≈0 |
| l1d_tlb_refill | 47,702 | 55,870 | +17% |
| l2d_tlb_refill | 21,658 | 21,614 | ≈0 |
| dtlb_walk (r34) | 21,453 | 21,371 | ≈0 |

辅助手段 function_graph 确认了结构（munmap 时间的约 97% 位于 `unmap_vmas` 子树，最终的 `tlb_finish_mmu` 在 trace 口径下占比很小），但 function_graph 的逐函数插桩开销会淹没真实差异（其绝对值甚至与 perf 相反），故仅用于确认调用结构，退化幅度一律以 perf 数据为准。

### 6.3 分析：候选机制收敛为两个

这组数据同时排除了三类解释、确立了一个事实：

- 指令数相同（+0.06%）、缺页数相同 → **不是软件多做了工作**；
- gate 已证 ΔEL2=0 → **不是进入了 EL2**；
- `dtlb_walk` 次数相同 → **不是发生了更多次页表遍历**；
- 额外的 +39.8M 周期几乎全部对应 +40.9M 后端停顿，IPC 从 1.67 降至 0.92 →**同样的指令流，在 protected 模式下访存等待显著变长**。

退化是硬件层面的单位成本变化。在"host stage-2 使能后的硬件成本"范围内，还剩两个候选机制，perf 数据对两者均相容，无法区分：

| 候选 | 机制 | 若成立，可观测的特征 |
|---|---|---|
| **a-1** | 每条宿主机 `TLBI` 指令更昂贵（需失效两级合成的 TLB 条目、广播代价更大） | 退化应与逐页 flush slot 数（基础 TLBI 序列数）成正比，与页表项数量无关 |
| **a-2** | 每次 stage-1 页表遍历更昂贵（遍历中的描述符地址需经 stage-2 嵌套翻译） | 退化应与页表遍历工作量（页表项数量）成正比 |

阶段五的全部工作就是把这两个候选分开。

---

## 7. 阶段五：机制判定——从两个候选到唯一解释（N80）

### 7.1 host stage-2 映射粒度自省（op=3）

**动机**：a-2 有一个具体的变体——若宿主机内存在 host stage-2 中已被大量拆成 4 KB 页（§2.1 所述 `force_pte` 机制），则嵌套遍历层级更深、TLB 压力更大，a-2 自然成立，且优化杠杆明确（恢复块映射）。判别这一点需要知道 host stage-2 的实际映射粒度分布。然而 host stage-2 是 hypervisor 的私有数据结构，宿主机、perf、ftrace 均无法读取，**只能在 EL2 内自省**。

**设计**：复用既有的 `__pkvm_xcore_stats` hypercall 通道，新增只读操作 op=3——遍历 host stage-2 页表，按叶子粒度（1G/2M/4K）分桶统计页数直方图。设计选择的理由：

- 用直方图而非单地址查询：一张全局分布表即可判别"是否碎片化"，且不需要预先获取基准进程的物理地址；
- 遍历对象必须是 `host_mmu.pgt`（host stage-2），而非 op=2 使用的 `PKVM_PGTABLE`（后者是 hypervisor 自身的 stage-1 页表，与宿主机内存粒度无关）;
- 只读、持 host 组件锁遍历，零功能性副作用；hypervisor 与宿主机两侧均做 protected 模式门控（NVHE 下 `host_mmu` 未初始化）。

**实现**（均在当前工作区）：

叶子回调与遍历函数（`mem_protect/host.rs:913,953`，节选）：

```rust
// 叶子回调：按映射粒度把页数累加到对应桶
let granule = kvm_granule_size(ctx_ref.level);
let pages = granule >> PAGE_SHIFT;
hist.total += pages;
if      granule == 1u64 << PAGE_SHIFT { hist.pages_4k += pages; }
else if granule == 0x20_0000          { hist.pages_2m += pages; }
else if granule == 0x4000_0000        { hist.pages_1g += pages; }

// 遍历函数：持 host 组件锁，遍历整个 host stage-2
host_lock_component();
let ret = unsafe {
    let ia_bits = host_mmu.pgt.ia_bits;
    kvm_pgtable_walk(&raw mut host_mmu.pgt, 0, 1u64 << ia_bits, &mut walker)
};
host_unlock_component();
```

hypercall 分发（`hyp_main.rs:1772`，op=3 分支）：

```rust
3 => {
    // 仅 protected 模式（遍历 host_mmu 页表，nvhe 下未初始化）
    if !unsafe { static_branch_unlikely!(kvm_protected_mode_initialized, ...) } {
        host_ctxt.set_cpu_reg(0, SMCCC_RET_NOT_SUPPORTED as u64);
        return;
    }
    let hist = host_stage2_level_histogram();
    host_ctxt.set_cpu_reg(0, hist.pages_4k);
    host_ctxt.set_cpu_reg(1, hist.pages_2m);
    host_ctxt.set_cpu_reg(2, hist.pages_1g);
    host_ctxt.set_cpu_reg(3, hist.total);
}
```

宿主机侧 `xcore_stats.c` 增加对应的 hypercall 封装与 `/proc/xcore_stats` 显示。使用方式：protected 模式下 `echo 3 > /proc/xcore_stats && cat /proc/xcore_stats`。

**结果**（N80，protected）：

```
host stage-2 mapping granularity:
4K  pages : 8046
2M  blocks: 2486  (1272832 pages)
1G  blocks: 1019  (267124736 pages)
Total     : 268405614 pages (1048459 MB)
```

| 粒度 | 叶子条目数 | 覆盖页数 | 占比 |
|---|---:|---:|---:|
| 1G 块 | 1019 | 267,124,736 | **99.52%** |
| 2M 块 | 2486 | 1,272,832 | 0.474% |
| 4K 页 | 8046 | 8,046 | 0.003%（约 31 MB） |

（总量约 1 TB，为 host stage-2 覆盖的完整宿主机物理地址空间，含 RAM 与 MMIO 区，绝大部分以 1G 块恒等映射。）

**判读**：宿主机内存 99.5% 以上为 1G 块映射，4K 页全系统仅 8046 个——而基准的 64 MB 工作集对应 16,384 页，8046 < 16,384，因此基准触及的内存**不可能**位于 4K 映射区，必然落在大块内。这 8046 个 4K 页来自启动期 hypervisor 初始化捐赠、IOMMU 恒等映射等触发 `force_pte` 的静态场景；munmap 是 stage-1 操作，不改变页的所有权，不会拆分 host stage-2 的块。**"碎片化导致深层嵌套遍历"的变体被排除。**

### 7.2 第二次误判及其修正

op=3 的数据是正确的，但当时据此做出的机制结论是错误的，有必要完整记录。

当时的推理是："既然不是碎片化，那么退化就是嵌套遍历的固有成本（a-2）"。这是一次过度外推：op=3 回答的问题是"宿主机内存是否被拆成 4K"，它只能排除 a-2 的碎片化变体，**并不能在 a-1 与 a-2 之间做判别**。更重要的是，这条数据的正确读法恰恰相反：宿主机内存以 1G 块映射意味着一条两级合成的 TLB 条目可覆盖 1 GB、stage-2 方向的遍历极浅——**"大块映射"是削弱 a-2 的证据，而非支持它的证据**。

这次误判由随后的两个对照实验（§7.3 密集触摸对照、§7.5 阈值扫描）直接推翻并修正。教训在于：一项测量只能回答它实际测量的问题；把"内存是否碎片化"的答案当作 "成本在遍历还是在 TLBI"的答案，是这次反转的根源。

### 7.3 密集触摸对照实验：证伪 a-2

**设计**：mmap 一个 64 MB 文件映射 → **以 4 KB 步长写触摸全部页面**（区别于原基准的稀疏触摸）→ 仅对 munmap 计时（计时口径与 `bench_munmap_only` 一致）。

这个对照点的设计意图需要完整说明，因为它同时对两个候选机制施加了**方向相反**的条件，单次实验即可形成判别：

1. **为何必须触摸**：munmap 的工作量取决于映射中实际建立的页表项。不触摸则没有页表项可拆、没有页可释放、没有 TLB 条目可失效，munmap 接近空操作，什么也测不到。
2. **为何全量触摸——对 a-2 施加最大压力**：触摸全部 16,384 页使页表被完全填充（32 个 PTE 页），这是 munmap 可能遇到的最大遍历与释放工作量，是原基准稀疏触摸（约 410 页）的 **40 倍**。若 a-2 成立（每次遍历更贵），此处差距应达到最大。
3. **同时对 a-1 施加消除条件**：全量触摸后 munmap 需要刷新的范围为整个 64 MB，超过内核的整表刷新阈值（§7.4），内核将以单条指令完成 TLB 失效、**不发出逐页 TLBI**。若 a-1 成立（每条 TLBI 更贵），此处差距应当消失。

**结果**（N80，仅 munmap 计时，单位 µs）：

| | nvhe | protected | 差距 |
|---|---:|---:|---:|
| 密集触摸后 munmap（16,384 个页表项） | 2828 | 2785 | **≈0** |

**判读**：页表遍历工作量增至 40 倍，差距反而趋零——**a-2 被证伪**。同一结果与 a-1 完全自洽：没有逐页 TLBI 就没有额外开销。与既有数据对照（原基准口径的 munmap-only 时间取自 C0 日志）：

| 触摸方式 | 页表项数（遍历工作量） | munmap 刷新范围 | nvhe | protected | 差距 |
|---|---:|---|---:|---:|---:|
| 稀疏（原基准，6.4 MB / 16K 步长） | ~410 | < 2 MB → 逐页 TLBI | 113 µs | 548 µs | **4.8 倍（+435 µs）** |
| 密集（本对照，全量 64 MB / 4K 步长） | 16,384 | ≥ 2 MB → 整表刷新 | 2828 µs | 2785 µs | ≈0 |

稀疏触摸有额外开销、密集触摸没有，而两者的区别不在页表项数量（密集反而多 40 倍），在于 **munmap 是否发出逐页 TLBI**。"小范围 munmap 有开销、大范围反而没有"这一反差，由下一节的内核源码给出确切解释。

### 7.4 内核源码分析：munmap TLB 失效的 2 MB 阈值

munmap 的拆除路径总体结构已在 §2.2 给出：`__vm_munmap` → … → `unmap_region()`（`mm/mmap.c:2346`）。本节关注其中最后一步 TLB 失效的路径选择：

```c
static void unmap_region(...)
{
    struct mmu_gather tlb;
    ...
    tlb_gather_mmu(&tlb, mm);
    unmap_vmas(&tlb, mas, vma, start, end, ...);   /* 清除页表项、释放页 */
    free_pgtables(&tlb, ...);                      /* 释放中间级页表 */
    tlb_finish_mmu(&tlb);                          /* 最终 TLB 刷新 */
}
```

这里有一个容易漏掉的中间层：清 PTE 时并不会立刻发 TLBI，而是先把"哪些地址真的被拆了"登记到 `mmu_gather`，最后统一刷新。PTE 拆除有两类入口：

```c
/* mm/memory.c:1545，非 normal page / 特殊 PTE 路径 */
ptep_get_and_clear_full(mm, addr, pte, tlb->fullmm);
tlb_remove_tlb_entry(tlb, pte, addr);

/* mm/memory.c:1488，普通文件页/匿名页路径，可能一次处理 nr 个连续 PTE */
ptent = get_and_clear_full_ptes(mm, addr, pte, nr, tlb->fullmm);
tlb_remove_tlb_entries(tlb, pte, nr, addr);
```

`tlb_remove_tlb_entry(s)` 的名字容易误导：它**不执行 TLB 失效指令**，只更新 `mmu_gather` 的待刷新范围。宏定义在 `include/asm-generic/tlb.h:615`：

```c
#define tlb_remove_tlb_entry(tlb, ptep, address)        \
do {                                                    \
    tlb_flush_pte_range(tlb, address, PAGE_SIZE);       \
    __tlb_remove_tlb_entry(tlb, ptep, address);         \
} while (0)

static inline void tlb_remove_tlb_entries(struct mmu_gather *tlb,
        pte_t *ptep, unsigned int nr, unsigned long address)
{
    tlb_flush_pte_range(tlb, address, PAGE_SIZE * nr);
    ...
}
```

而 `tlb_flush_pte_range()` 做的核心动作只是：

```c
__tlb_adjust_range(tlb, address, size);  /* start=min(start,address), end=max(end,address+size) */
tlb->cleared_ptes = 1;
```

因此，`mmu_gather` 在 `unmap_vmas()` 期间累积三类信息：被拆除的最小/最大虚拟地址范围（`tlb->start/end`）、拆除粒度（这里是 PTE，`cleared_ptes=1`，arm64 后续据此给 TLBI 设置 level hint）、以及待释放的页/页表页。只有走到 `tlb_finish_mmu()`，才进入真正的 TLB 失效阶段。

`tlb_finish_mmu()`（`mm/mmu_gather.c:437`）调用 `tlb_flush_mmu()`，先执行 `tlb_flush_mmu_tlbonly()`（`include/asm-generic/tlb.h:455`），再释放批量收集的页/页表页。arm64 覆盖了 generic `tlb_flush()`：`arch/arm64/include/asm/tlb.h:53` 根据 `mmu_gather` 中的 `start/end`、拆除粒度与 level hint 调用 `__flush_tlb_range()`（`arch/arm64/include/asm/tlbflush.h:443`），最终落到 `__flush_tlb_range_nosync()`（:405）。关键的分支在 :422：

```c
/* tlbflush.h:342 */
#define MAX_DVM_OPS  PTRS_PER_PTE      /* 4K 页表下 = 512 */

/* tlbflush.h:422，__flush_tlb_range_nosync 内 */
if ((!system_supports_tlb_range() &&
     (end - start) >= (MAX_DVM_OPS * stride)) ||   /* 512 × 4K = 2 MB */
    pages >= MAX_TLBI_RANGE_PAGES) {
    flush_tlb_mm(vma->vm_mm);                       /* 整表路径：单条按 ASID 失效 */
    return;
}
dsb(ishst);
/* 逐页/范围路径 */
__flush_tlb_range_op(vae1is, start, pages, stride, asid, tlb_level, true);
```

两条路径落到指令层面：

**整表路径**（`flush_tlb_mm`，:253）——无论范围多大，仅一条 TLBI，以 ASID 为键作废该进程地址空间的全部条目（ASID 的含义见 §2.3）：

```c
dsb(ishst);
asid = __TLBI_VADDR(0, ASID(mm));
__tlbi(aside1is, asid);          /* tlbi aside1is：按 ASID 失效整个地址空间 */
__tlbi_user(aside1is, asid);     /* 运行时 KPTI 实际开启时对 user ASID 追加一条 */
dsb(ish);
```

**逐页路径**（`__flush_tlb_range_op` 宏，:369）——本平台不支持 FEAT_TLBIRANGE（`system_supports_tlb_range()` 为假），循环内恒走逐页分支：

```c
while (pages > 0) {
    if (!system_supports_tlb_range() || pages == 1) {
        addr = __TLBI_VADDR(start, asid);
        __tlbi_level(op, addr, tlb_level);          /* tlbi vae1is：一页一条 */
        if (tlbi_user)
            __tlbi_user_level(op, addr, tlb_level); /* 运行时 KPTI 实际开启时每页再追加一条 */
        start += stride;
        pages -= stride >> PAGE_SHIFT;
        continue;
    }
    /* 支持 FEAT_TLBIRANGE 时走 __tlbi(r##op, ...)：一条指令覆盖一段范围 */
    ...
}
```

随后 `__flush_tlb_range()`（:443）以一条 `dsb(ish)` 等待全部失效完成。也就是说，逐页路径是“连续发出 N 个 slot 的 TLBI，再统一同步一次”，不是“每发一条 TLBI 就同步一次”。汇总成对照表：

| munmap 实际刷新范围 | 所走路径 | 刷新口径 |
|---|---|---|
| **< 2 MB** | `__flush_tlb_range_op` 逐页 | **N 个 4K flush slot**（每个 slot 触发一次基础 `tlbi vae1is`；运行时 KPTI 开启时还追加 user ASID TLBI）+ 1 条 `dsb ish` |
| **≥ 2 MB** | `flush_tlb_mm` 整表 | **1 条** `tlbi aside1is` + 1 条 `dsb ish` |

说明：下文的定量模型按源码逐页循环中的 4K flush slot 计数。KPTI、CPU erratum workaround 等运行时条件会改变底层实际发出的 TLBI 指令条数，但不会改变“差距随逐页 slot 数线性增长、在整表路径消失”这一判据。

N80 的 `ID_AA64ISAR0_EL1 = 0x0000111110212120`，TLB 字段 [59:56] = 0，确认**不支持 FEAT_TLBIRANGE**，2 MB 阈值生效。

由此得到一个可证伪的预言：**若 a-1 成立，则刷新范围小于 2 MB 时两模式差距应与范围（即逐页 flush slot 数）成正比；范围达到 2 MB 时差距应当立即消失**。页表遍历类机制（a-2）不可能在 2 MB 这一点发生这样的反向突变。下一节的扫描实验直接检验该预言。

### 7.5 阈值扫描实验：证实 a-1

**设计**：要检验上述预言，需要精确控制 munmap 的刷新范围并使其跨越 2 MB 阈值。专用微基准 `experiments/munmap-tlbi/munmap_only.c` 的核心循环：

```c
for (int it = 0; it < iters; it++) {
    char *p = mmap(NULL, sz, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    for (size_t i = 0; i < tb; i += stride)     /* 触摸前 touch_mb MB，步长可控 */
        ((volatile char *)p)[i] = 1;

    double t0 = now_ns();
    munmap(p, sz);                              /* 仅 munmap 计时 */
    double d = now_ns() - t0;
    ...
}
```

设计要点：

- **连续密集触摸前 N MB（步长 4 KB）**：被填充的页表项集中于映射起始的 N MB，munmap 的实际刷新范围因此约等于 N MB——刷新范围由参数 N 直接、干净地控制（稀疏触摸下刷新范围与触摸点分布纠缠，不适合做自变量）；
- **取点跨越 2 MB 并在阈值两侧加密**（0.25 / 0.5 / 1 / 1.9 / 2 / 4 / 8 / 32 / 64 MB），特别是 1.9 与 2.0 两点，用于确认差距是否恰在阈值处消失；
- 末行附原基准的稀疏触摸参数（6.4 MB / 16K 步长），用于与原始观测进行定量对照；
- protected 与 nvhe 各跑一轮（`run-sweep.sh`，每点 100 次迭代取 munmap-only 均值，最小值与均值接近，噪声小）。

**结果**（N80，单位 µs，差距 = protected − nvhe）：

| 触摸范围 | protected | nvhe | 差距 | 所处区间 |
|---|---:|---:|---:|---|
| 0.25 MB | 34.1 | 16.3 | +17.8 | 逐页 |
| 0.5 MB | 62.4 | 28.2 | +34.2 | 逐页 |
| 1.0 MB | 120.9 | 52.5 | +68.4 | 逐页 |
| **1.9 MB** | 227.5 | 95.0 | **+132.5（+139%）** | 逐页 |
| **2.0 MB** | 93.4 | 88.6 | **+4.8（+5%）** | **整表** |
| 4 MB | 184.1 | 173.6 | +10.5（+6%） | 整表 |
| 8 MB | 366.9 | 346.4 | +20.5（+6%） | 整表 |
| 32 MB | 1451.2 | 1369.3 | +81.9（+6%） | 整表 |
| 64 MB | 2876.3 | 2734.1 | +142.2（+5%） | 整表 |
| 稀疏 6.4 MB / 16K（原基准模式） | 546.7 | 108.6 | **+438.1（+403%）** | 逐页 |

三项相互独立的证据共同证实 a-1：

1. **阈值处的突变**。差距在 1.9 MB 时为 +132.5 µs（+139%），到 2.0 MB 骤降至 +4.8 µs（+5%）——恰好落在内核"逐页 → 整表"的切换点上。页表遍历的工作量在 1.9 与 2.0 MB 之间几乎不变（486 页对 512 页），任何遍历类机制都无法产生这种突变；唯一在该点发生变化的就是 TLBI 的发出方式。
2. **逐页区间的线性关系**。2 MB 以下差距与触摸范围严格成正比（17.8 → 34.2 → 68.4 → 132.5 µs，约 69.5 µs/MB）。按每 MB 含 256 个 4K 页槽折算，**protected 模式相对 nvhe 的额外成本约 0.27 µs/slot（1.8 GHz 下约 490 周期/slot）**。这里的 slot 是 `__flush_tlb_range_op()` 逐页循环中的 4K 刷新槽位；该数值是斜率折算出的 TLBI 序列及后续等待增量，不是裸 `tlbi` 指令本身的孤立延迟。
3. **与原始观测的定量衔接**。原基准稀疏触摸 6.4 MB，munmap 刷新范围约 6.4 MB，含 1638 个 4K flush slot：1638 × 0.27 µs/slot ≈ 442 µs，与本表实测的 +438 µs、C0 日志中的 +435 µs（§7.3）一致；Kaitian 平台同一基准的 +205 µs（§4.3）亦为同一机制在不同硬件上的量级体现。退化的来源就此与原始观测定量衔接。

**阈值作用的真实粒度：刷新按 PMD 分批，稀疏触摸每批差 12 KB 达不到整表条件**

读到这里容易产生一个疑问：§4.3 的 `munmap_after_write_touch` 表中，差距随映射尺寸一路线性放大到 64 MB（+205 µs），而 64 MB 映射的触摸跨度为 6.4 MB、已超过 2 MB——为什么没有像本节扫描那样在越过阈值后塌掉？这并不矛盾，但需要把"阈值到底和谁比较"讲到单次刷新调用这一层才能看清。

§7.4 的阈值判断（tlbflush.h:422）比较的是**单次 `flush_tlb_range` 调用所覆盖的虚拟地址范围**，既不是映射大小，也不是触摸跨度的总和。从"映射大小"到"单次刷新范围"隔着两层换算。

第一层在测试代码里：`write_touch()` 只触摸前 `size/10`、步长 16 KB（mmap_split_bench.c，`touch_divisor=10`、`stride_kb=16`，复刻 lat_mmap）。因此 0.5~16 MB 各行的触摸跨度为 0.05~1.6 MB，全部低于 2 MB——这些行落在逐页区间、差距 ∝ 尺寸，本就是 a-1 的预期。

第二层在内核里，它解释了 64 MB 行（跨度 6.4 MB > 2 MB）为何仍是逐页：**munmap 的 TLB 刷新不是对整个触摸跨度发出一次，而是按 PMD（2 MB 虚拟地址块）分批发出**。`zap_pmd_range()`（mm/memory.c:1706）对每个 PMD 调用一次 `zap_pte_range()`（:1740），而本基准写触摸过的页全部是**脏的共享文件页**，命中下面这段逻辑：

```c
/* mm/memory.c:1489（zap_present_folio_ptes，节选）：写脏的共享文件页强制本批刷新 */
if (pte_dirty(ptent)) {
    folio_mark_dirty(folio);
    if (tlb_delay_rmap(tlb)) {
        delay_rmap = true;
        *force_flush = true;    /* 脏页的反向映射拆除须推迟到 TLB 刷新之后 */
    }
}

/* mm/memory.c:1687（zap_pte_range 结尾）：持页表锁期间刷新本批累积的范围并清零 */
if (force_flush) {
    tlb_flush_mmu_tlbonly(tlb);
    tlb_flush_rmaps(tlb, vma);
}
pte_unmap_unlock(start_pte, ptl);
```

于是每个含脏页的 PMD 块结束时就发出一次刷新，**范围是该块内第一个到最后一个被清除的页表项的跨度，至多 2 MB**（后备文件映射经 ext4 的 `thp_get_unmapped_area`，fs/ext4/file.c:945，取得 PMD 对齐的基址，使该算术干净成立）。两种触摸步长由此走向相反的分支：

| 触摸步长 | 满 PMD 块内最后被触摸的页 | 单批刷新范围 | 与 2 MB 阈值比较 | 走向 |
|---|---|---|---|---|
| 16 KB（稀疏，原基准） | 2 MB − 16 KB 处 | 2 MB − 12 KB | **差 12 KB 未达到** | 逐页，约 509 个 slot / PMD |
| 4 KB（密集，§7.3 对照与本节扫描） | 2 MB − 4 KB 处 | 恰好 2 MB | **达到** | 单条整表刷新 / PMD |

这里容易误解的一点是：逐页 TLBI 的 slot 数不是"实际触摸页数"。在一个完整 PMD 内，16 KB 稀疏触摸只建立约 128 个 PTE，但 `mmu_gather` 记录的是从本批第一个被清除 PTE 到最后一个被清除 PTE 之后的**连续 VA 范围**；因此刷新范围约为 `2 MB - 12 KB`，折算为约 509 个 4K flush slot。也就是说，每多一个满 PMD，pKVM 额外增加的不是 128 个 slot，而是接近 512 个 slot；这正是 §4.3 的 Δ 能随大尺寸继续放大的原因。

稀疏触摸因此无论总跨度多大，每一批都以 12 KB 之差留在逐页区间——逐页 flush slot 总数 ∝ 触摸跨度 ∝ 映射尺寸。§4.3 那张表的线性增长由此可以直接验证：将各行 Δ 除以触摸跨度内的 4K 页槽数（= size/40960），单价全表恒定：

| size | 页槽数 | Δ (µs) | Δ/槽 (µs) |
|---:|---:|---:|---:|
| 0.5 MB | 12.8 | 1.433 | 0.112 |
| 1 MB | 25.6 | 2.907 | 0.114 |
| 2 MB | 51.2 | 6.342 | 0.124 |
| 4 MB | 102.4 | 13.140 | 0.128 |
| 8 MB | 204.8 | 26.218 | 0.128 |
| 16 MB | 409.6 | 51.597 | 0.126 |
| 64 MB | 1638.4 | 205.003 | **0.125** |

约 0.125 µs/slot 就是 Kaitian 平台上每个 4K flush slot 的 pKVM 额外单价（与 N80 的 0.27 µs/slot 是同一机制在不同硬件上的单价差异）。

Δ% 列从 +47% 升到 +227% 的走势也值得说清，以免误读为"pKVM 越来越慢"。把 munmap 时间拆成三项：固定开销 F（系统调用、VMA 摘除，与页数无关，两模式相同，约 2~4 µs）+ 释放成本 r·P（清 PTE、归还页缓存，**两模式都随触摸页数 P 增长**，由大尺寸段拟合 r ≈ 0.21 µs/页）+ pKVM 独有的逐页失效税 t·4P（每触摸页摊 4 个 4K flush slot，4 × 0.125 = 0.5 µs/页）。于是 Δ% = 4tP / (F + rP)：两个随页数增长的项比值恒定，**Δ% 随尺寸上升但收敛于 4t/r ≈ 0.5/0.21 ≈ +240%，并非无限增长**——实测序列 47→67→96→142→178→200→227% 的增幅逐步缩小，正在逼近该渐近线（64 MB 行 295/90 ≈ 3.3 倍）。小尺寸段 Δ% 偏低，是固定开销 F 在分母中占比较大所致。渐近线之所以能超过 100%，是因为每触摸页的逐页失效税（0.5 µs）高于其正常释放成本（0.21 µs）。换言之，**那张表的线性不是 2 MB 阈值的反例，而是 a-1"差距 ∝ 逐页 slot 数"的又一组独立证据**。

同一机制还顺带解释了 §4.3 提到的读触摸路径异常（64 MB 行差距消失，实测 −1.88%）：**读触摸的页是干净的**，不触发上面 :1489 处的 `force_flush`，刷新范围得以跨 PMD 持续累积，最终在 `tlb_finish_mmu` 对整个 6.4 MB 跨度一次性刷新——超过 2 MB，走整表路径，无逐页 TLBI，差距随之消失；而 0.5~16 MB 行的跨度不足 2 MB，累积后仍走逐页，差距显著（实测 +57%~+90%）。脏页与干净页在 :1489 处的一位之差，决定了"按 PMD 分批逐页"与"累积一次整刷"两种形态，写、读两张表的全部走势就此统一。

综上，"2 MB 阈值"的准确表述是：**作用于单次刷新调用的虚拟地址范围**。本调查的稀疏写触摸基准由于 per-PMD 分批与 16 KB 步长的组合，每批永远低于阈值，差距随尺寸线性增长而不会自行塌掉。

### 7.6 补充分析：阈值扫描中 2 MB 以上绝对时间为何继续上升

本节只解释 §7.5 的**连续密集触摸阈值扫描**，不是在解释 §4.3 的原基准稀疏写触摸。两张表的 `size` 口径不同：§7.5 的 2 MB 表示单次 munmap 刷新范围真的达到 2 MB，因此进入整表路径；§4.3 的 2 MB 只是 mmap 总大小，实际只写触摸 `size/10 = 0.2 MB`，远低于阈值。§4.3 的 64 MB 行虽然总触摸跨度为 6.4 MB，但脏页使刷新按 PMD 分批，16 KB 稀疏步长又让每批只有约 `2 MB - 12 KB`，仍落在逐页路径，所以它可以继续增长到 +227%，并不属于本节所说的“整表区间残差”。

在 §7.5 的阈值扫描表中，另有一处需要澄清的现象：差距在 2 MB 处消失，但两模式的**绝对时间**在 2 MB 之后仍随范围继续增长（93 → 184 → 367 → 1451 → 2876 µs）。这是与 pKVM 逐页 TLBI 额外开销无关的另一项成本，将 munmap-only 时间分解为两部分即可解释：

```
munmap-only ≈ [释放页与清除页表项的成本]      + [TLB 刷新的成本]
                与触摸页数成正比                  <2MB：N 个逐页 slot
                两模式基本相同（~0.17 µs/页）      ≥2MB：1 条整表刷新（常数）
                                                  pKVM 的额外开销仅存在于此项
```

- **第一部分（释放页/清除页表项）**：munmap 须清除每个已建立的页表项、将每页归还页缓存或伙伴系统、更新 `struct page`。该成本与触摸页数成正比，且两模式几乎相同——验证：nvhe 侧 88.6/512 ≈ 346.4/2048 ≈ 2734.1/16384 ≈ **0.17 µs/页**，斜率恒定。宿主机内存为 1G 块映射（§7.1），这些访存的 stage-2 翻译开销很小，两模式仅余 5%～6% 的残差。
- **第二部分（TLB 刷新）**：2 MB 以下为 N 个逐页 flush slot（pKVM 的额外开销集中于此），2 MB 及以上为单条整表刷新（常数）。

据此，整条曲线的形态完全自洽：

| 区段 | 释放页成本 | TLB 刷新成本 | 绝对时间 | 差距（pKVM 额外开销） |
|---|---|---|---|---|
| < 2 MB | 随页数增长 | N 个逐页 slot，随范围增长 | 增长（两项叠加） | 与范围成正比（TLBI 项） |
| 2 MB 拐点 | 略增（486 → 512 页） | N 个逐页 slot → 1 个整表刷新序列，骤降 | 反而下降（227 → 93） | 降至 ≈0 |
| > 2 MB | 随页数继续增长 | 恒为 1 个整表刷新序列，不变 | 再次增长（仅释放页项） | 5%～6%（释放页访存的小幅残差） |

即：2 MB 之后绝对时间继续上升来自"释放页"成本（两模式同等增长，与 pKVM 无关）；pKVM 的额外开销位于"TLB 刷新"项内，已随整表刷新收敛为常数项。

### 7.7 机制解释：每条宿主机 TLBI 为何在 pKVM 下更昂贵

> **更正（见第 9 节）**：本节下文将额外开销部分归因于"`dsb ish` 等待 shareable 域内失效完成"（即跨核广播等待）。2026-06-15 的在线核数复查证明这一归因**有误**——该开销**不随在线核数变化**，是**本地**失效合成条目的开销（裸 `tlbi vae1is` 在 protected 下约 289 ns、nvhe 下约 23 ns，差值即 +0.27 µs/slot）；`stall_backend` 的增加来自这条更慢的 TLBI 在**本地**执行时需要更多周期才能完成，而非等待远端核完成。下文"逐页失效序列更贵"的主干结论正确，凡涉及"广播 / DSB 完成等待"之处请以第 9 节为准。

逐页路径发出的指令在两种模式下完全相同（`tlbi vae1is, <VA|ASID>`），变化的是该指令需要完成的工作量：

- **nvhe（无 host stage-2）**：宿主机 EL1 为单级翻译，TLB 中是纯 stage-1 条目。`tlbi vae1is` 失效指定 VA/ASID 的 stage-1 条目，`dsb ish` 等待内部共享域的广播完成。
- **protected（host stage-2 使能）**：宿主机 EL1 为两级嵌套翻译（VA→IPA→PA），TLB 中是 **stage-1 与 stage-2 合成（combined）的条目，并以 VMID（§2.3，宿主机的 stage-2 上下文）标记**。同一条 `tlbi vae1is` 须失效这些合成条目，涉及 stage-2 维度与 VMID 的匹配；序列末尾的 `dsb ish` 须等待 shareable 域内这些失效动作完成。在本平台上，这个完成等待显著变长，表现为流水线后端停顿。

该解释与阶段四的全部 perf 特征吻合：TLBI 指令数与页表遍历次数两模式相同（`instructions`、`dtlb_walk` 持平），失效后的重填略增（`l1d_tlb_refill` +17%），额外时间全部表现为 `stall_backend`——消耗在等待 TLBI/DSB 完成上，而不是多执行了工作。

实测按 4K flush slot 折算的额外成本约 0.27 µs/slot（约 490 周期/slot）。该口径对应逐页路径中一个 slot 上的 TLBI 序列及其等待成本增量，而不是裸 `tlbi` 指令的孤立延迟。两点补充：

- 该成本是硬件层面的：宿主机的 TLBI 不被陷入（§5.1，HCR 无 `TTLB` 位），hypervisor 软件既无法拦截也无法加速，唯一的软件方向是**减少逐页 flush slot 数或让内核改走整表/范围刷新**；
- 运行时实际启用 KPTI（内核页表隔离）时，每个 slot 会经 `__tlbi_user` 追加 user ASID 的 TLBI，基础逐页序列翻倍，该额外开销也按相同机制放大；若 KPTI 仅在配置上可用但运行时未开启，则不会追加这一路 user ASID TLBI。

### 7.8 全部证据与两个候选机制的对照

| 证据 | 对 a-1（TLBI 成本） | 对 a-2（遍历成本） |
|---|---|---|
| gate：ΔEL2 = 0 | 相容（TLBI 是宿主机侧硬件行为） | 相容 |
| C0：指令/缺页/遍历次数相同，仅后端停顿增加 | 支持（DSB 等待即后端停顿） | 先验上也可解释 |
| C0：`l1d_tlb_refill` +17% | 支持（失效后重填） | 中性 |
| op=3：宿主机内存 99.5% 为 1G 块 | 支持（遍历廉价，瓶颈只能在别处） | **不利（遍历廉价则 a-2 失去基础）** |
| 密集触摸对照：遍历量 ×40 而差距 ≈0 | 支持（无逐页 TLBI 则无额外开销） | **证伪（工作量最大处无差距）** |
| 阈值扫描：2 MB 处突变 + 线性 ∝ 范围 | **证实（差距 ∝ 逐页 slot 数，随合并消失）** | 证伪（遍历机制无法产生该突变） |
| 平台无 FEAT_TLBIRANGE | 解释退化幅度（只能逐页发出） | 中性 |

只有 a-1 能同时解释全部观测。结论：**退化机制 = a-1**。

---

## 8. 结论

### 8.1 根因

pKVM（protected 模式）下宿主机 `lat_mmap` 的性能退化，根因为：

> **写触摸后的 munmap 在拆除映射时，对小于 2 MB 的刷新范围逐页发出 `TLBI` 指令（本平台无 FEAT_TLBIRANGE，无法使用范围 TLBI；`MAX_DVM_OPS=512` 使 ≥2 MB 的范围改走单条整表刷新）；而 host stage-2 使能后，TLB 中为带 VMID 标记的两级合成条目，每个 4K flush slot 对应的逐页失效序列与广播等待代价显著增加（由阈值扫描斜率折算约 +0.27 µs/slot，约 490 周期/slot），等待表现为后端访存停顿。**

> **更正（见第 9 节）**：上句"逐页失效序列**与广播等待**"中的"广播等待"归因有误。主调查结束后的在线核数复查（§9）证明该 +0.27 µs/slot **不随核数变化、也非跨核广播**，而是本地失效一条 VMID 标记的合成 TLB 条目所产生的开销（protected ~289 ns/slot − nvhe ~23 ns/slot ≈ +0.27 µs/slot）；"逐页失效序列本身更贵"这一判断成立。本节其余结论与边界条件不变。

完整证据链：

```
host stage-2（pKVM 隔离机制）
  → lat_mmap 生命周期退化 +29%~+85%，稳态访问不受影响        （阶段一）
  → 退化的 95.7% 位于写触摸后的 munmap                        （阶段二，修正 first-touch 假设）
  → munmap 不进入 EL2，ΔEL2=0                                 （阶段三）
  → 额外成本全部为后端访存停顿，指令/缺页/遍历次数不变        （阶段四）
  → 粒度自省排除碎片化；密集对照证伪遍历机制；
    源码定位 2 MB 阈值；扫描证实差距 ∝ 逐页 slot 数、在阈值处消失（阶段五，修正嵌套遍历假设）
  → 根因 = 逐页 TLBI 在 host stage-2 下的硬件成本（a-1）
```

每一环均由"实测数据 + 内核代码 + 体系结构机制"三方互证；原始观测（+435 µs）与机制模型（1638 个 4K flush slot × 0.27 µs/slot ≈ 442 µs）定量吻合。

### 8.2 退化的边界条件与实际影响

该退化有明确的边界，并非"pKVM 下内存操作普遍变慢"：

- **仅影响单次刷新范围小于 2 MB 的 munmap**：若单次刷新范围达到 2 MB，内核会改用整 ASID 刷新，额外开销仅余 5%～6% 的访存残差；但像 `lat_mmap` 这种 16 KB 稀疏写触摸场景，即使总映射很大，也会因脏页 per-PMD 分批而持续落在逐页路径；
- **仅在映射生命周期路径上**：稳态读写、长期复用的映射（如 LMDB 打开后的常规读写）几乎不受影响；
- **平台相关**：退化幅度取决于硬件是否支持 FEAT_TLBIRANGE。支持该特性的平台以少数几条范围 TLBI 替代逐页 TLBI，退化将大幅缩小。N80/N90/Kaitian 均不支持，因而幅度明显。

受影响的负载特征：频繁建立与拆除中小映射的程序（`lat_mmap` 类微基准、频繁 open/close mmap 环境的数据库、生命周期短的映射密集型负载）。不受影响的负载：建立一次、长期复用映射的常规应用。

**该退化不限于 munmap（2026-06-16 复查）。** 以同一套阈值扫描对照 `munmap`、`madvise(MADV_DONTNEED)`、`mprotect` 三类拆除操作，protected−nvhe 的逐页 gap 与操作种类无关、仅由刷新 slot 数决定——2 MB 以下三者逐点重合（约 +0.27 µs/slot），并在 2 MB 处同时塌缩为约 0。其中 `MADV_DONTNEED` 与 munmap 行为完全一致（稀疏 6.4 MB 跨度下 gap 同为 +436 µs），因为它同样 zap 脏页、按 PMD 强制分批而困在逐页路径；jemalloc / tcmalloc / Go runtime 的 decommit 即走此路径，故实际受影响范围远大于 `lat_mmap` 类微基准。`mprotect` 则按几何形态分化：仅当**连续改动区间本身**小于 2 MB 时受影响，稀疏大跨度因不 zap 脏页、整段一次刷新越过阈值而 gap ≈ 0。可提炼为一条判别准则——**按脏页 per-PMD 分批的操作（munmap、`MADV_DONTNEED`）即便大跨度稀疏也吃满罚时；不分批的操作（`mprotect`）只在连续改动区间小于 2 MB 时受影响**。完整数据、谱系与论证见 `pkvm-teardown-op-generality.en.md`。

### 8.3 优化方向评估

| 方向 | 评估 |
|---|---|
| **FEAT_TLBIRANGE（硬件）** | 核心缓解手段。范围 TLBI 将"N 个逐页 slot"压缩为"每段一至几条范围 TLBI 序列"，直接消去开销的乘数。属于平台选型层面，软件无需改动（内核已有完整支持，`__flush_tlb_range_op` 的范围分支）。 |
| **调整 `MAX_DVM_OPS` 阈值（内核）** | 可评估：降低阈值使更多 munmap 走整表刷新，以消除逐页 TLBI。代价是整表刷新会失效该 ASID 的全部 TLB 条目，增大后续访存的重填成本，需以实际负载权衡。这是当前唯一可在软件侧操作的杠杆。 |
| **应用层规避** | 复用映射、合并小 munmap 为大范围操作，可绕开逐页区间。 |
| **pKVM/hypervisor 侧** | 空间有限。宿主机 TLBI 不被陷入，hypervisor 无法干预其执行；"提高 host stage-2 映射粒度"对本退化无效——粒度已是最大（99.5% 为 1G 块），且瓶颈不在页表遍历。 |

### 8.4 方法回顾：早期结论的修正

调查过程中两个早期结论被更精细的对照实验推翻，修正过程本身是证据链的一部分：

1. **first-touch 建表假设**（阶段一提出，阶段二修正）。早期数据显示额外开销与触摸页数线性相关，被解读为"每次缺页约 500 ns 的建表成本"。拆分实验将首次触摸单独计时后，该段仅占额外时间的 4% 左右——线性关系是真实的，但其原因是触摸页数决定了 munmap 的拆除工作量，而非触摸本身昂贵。
2. **嵌套页表遍历假设**（阶段四后提出，阶段五修正）。perf 显示"遍历次数不变、访存停顿增加"，曾被解读为"每次遍历被 stage-2 嵌套翻译放大"；粒度自省的 "大块映射"结果也曾被误读为支持该解释。实际上大块映射恰恰说明遍历廉价；密集对照（遍历量 ×40 而差距趋零）与阈值扫描（差距在 2 MB 处消失）共同将机制修正为"每条 TLBI 更贵、DSB 等待更久"。

两次修正的共同模式：一项与多个假设都相容的观测被过早地归因于其中一个。最终的判别都依靠"对候选机制施加相反条件"的专门对照实验完成。

主调查结束后还有第三次修正，模式完全相同：§7.7／§8.1 把 +0.27 µs/slot 同时归因于"逐页失效序列"与"广播等待"，而第 9 节以"在线核数"为自变量，证明该开销来自本地失效、与广播无关。这次修正还暴露了一个独立的统计学陷阱——用 `min` 比较方差不同的机器配置——详见第 9 节。

---

## 9. 后续复查：在线核数实验——退化来自本地失效开销，而非跨核广播（N80）

| 项目 | 内容 |
|---|---|
| 日期 | 2026-06-15（主调查结束后的独立复查） |
| 平台 | N80（Phytium FTC862，8 核 / 1 路 / **2 簇**，1.8 GHz 锁频），Kylin V10 SP1，内核 `6.6.30xcore-stat2+`（Rust nVHE hyp），protected 与 nvhe 两模式 |
| 复查对象 | §7.7／§8.1 曾将 +0.27 µs/slot 表述为“逐页失效序列**与广播等待**”。本次复查要验证的是：这笔开销是否确实来自**跨核 TLB 广播同步**，即 Inner-Shareable 的 `tlbi vae1is` 经 DVM 广播到其他核后，由发起核在 `dsb ish` 处等待远端失效完成。 |
| 结论 | **不是。** 该开销**不随在线核数变化，也不是广播等待**；它来自本地失效一条 stage-1 × stage-2 合成、VMID 标记的 TLB 条目（protected 约 289 ns/slot，nvhe 约 23 ns/slot，差值约 +0.27 µs/slot）。因此，§7.7／§8.1 中“广播等待”的归因需要更正；“逐页失效序列本身变贵”这一主结论仍然成立。 |
| 数据/代码 | `kylin-lmbench/experiments/munmap-tlbi/`：`INVESTIGATION-LOG.md`（按时间顺序记录）、`results/corescaling-n80/`（CSV）、`tlbi_ab/`（TLBI 计时内核模块与用户态驱动）、`run-core-scaling.sh`。 |

> **关于证据链的说明**：本次复查曾短暂得出“存在跨核广播代价”的错误中间结论，原因是把 munmap 的**最小值（`min`）**当成了主要判据。随后用**均值（`mean`）**、`perf` 进程计数、IRQ-off 的 TLBI 指令直接计时和访存对照实验重新核验，才确认该结论是统计方式造成的假象。这里保留错误路径和修正过程，是因为这个 `min` 陷阱本身具有复用价值，也与 §8.4 保留前两次结论修正的写法一致。

### 9.1 待验证假设与判别预测

§7.7 在解释“每条 TLBI 为何更贵”时，把 +0.27 µs/slot 同时描述为“逐页失效序列”与“广播等待”的开销；同时在 §2.3 末尾和 §7.7 中已经说明，本文当时并未强行把这笔等待归因到广播网络本身。本次复查针对的是这个尚未验证的问题：+0.27 µs/slot 是否实际来自一次跨核同步？

具体假设是：宿主机发出的 Inner-Shareable `tlbi vae1is` 会经 DVM 广播到内部共享域的其他核心，随后 `dsb ish` 必须等待这些远端失效完成。因此，如果这笔开销来自跨核广播，它应当随参与核心数增加；如果它只是本地执行开销，则应当与在线核数无关。

本节围绕“在线核数”这一个自变量展开：将在线核数从 1 调到 8，并对比同簇与跨簇配置，观察 +0.27 µs/slot 是否随核数或拓扑发生变化。

### 9.2 实验方法与平台控制

主测量沿用前几个阶段的工具：用 `experiments/munmap-tlbi/munmap_only.c` 单独计时 munmap，并用按生命周期分段的 `experiments/mmap-split/mmap_split_bench.c` 交叉印证。由于目标差异只有每个 slot 数百纳秒，任何未受控噪声都可能掩盖真实趋势，甚至制造错误趋势，因此每轮测试都固定以下条件：

- 基准进程通过 `taskset -c 0` 固定在 cpu0。
- governor 设为 `performance`，频率固定为 1.8 GHz；每次 CPU 热插拔后重新锁频，因为新置为 online 的核心会回到默认 governor。
- THP 设为 `never`，ASLR 设为 0，以降低大页和地址布局带来的方差。
- 使用 `cpuidle.off=1` 禁用深度 idle，避免远端空闲核心的唤醒延迟被误读为广播代价。
- 在线核数通过 `echo 0/1 > /sys/devices/system/cpu/cpuN/online` 逐个调整。

N80 的拓扑也提供了额外判据。8 个核心分为两个簇：`{0-3}` 为一簇（capacity 56），`{4-7}` 为另一簇（capacity 572），基准核 cpu0 位于前一簇。因此，`{0,1}`（同簇）与 `{0,4}`（跨簇）这两组配置具有相同的远端核数量，只区别于远端核是否跨簇。如果广播代价与拓扑相关，二者应当分离；如果无关，二者应当重合。

除真实 munmap 计时外，本次复查还使用 TLBI 计时内核模块 `tlbi_ab.ko` 做直接测量。模块在 cpu0 上关闭中断，用 `CNTVCT_EL0` 计量一批 `vae1is`/`vae1` 失效指令，从而绕开用户态调度噪声，直接观察单独 TLBI 指令本身的耗时。补充说明：可加载模块在本内核上工作正常；早先遇到的 `BTF:-22` 加载失败，是旧构建产物与运行内核不匹配所致，并非内核配置缺失。

### 9.3 以 `min` 得到的误导性结果：多核在线后 munmap 变慢

复查的第一步是在 protected 模式下，对稀疏写触摸（6.4–8 MB 跨度、16 KB 步长）后的 munmap 计时，只改变在线核数。第一组数据表面上非常接近“广播”模式：当 cpu0 独占整机时（n=1），munmap 的最小耗时约为 220 µs；只要将任意一个远端核置为 online，最小耗时就升至约 540 µs；此后核数从 2 增至 8，结果都稳定在这一高位。同簇 `{0,1}` 与跨簇 `{0,4}` 几乎没有差别。作为对照，nvhe 模式全程稳定在约 105 µs。

如果只看这组最小值，开销似乎只取决于“是否存在其他在线核心”，而不取决于具体核数或簇间拓扑。这种二值特征与 DVM 广播机制的直觉相符，并且该现象复现了三次。正是基于这组数据，复查一度给出过“约 74% 的 pKVM munmap 罚时来自广播”的错误分解。

问题在于，上述数字全部来自**最小值（`min`）**。当时尚未意识到，`min` 会在方差不同的配置之间引入系统性偏差。下一节的 TLBI 指令直接计时首先揭示了这一点。

在进入 TLBI 指令直接计时前，需要先说明 §9.4 中对比的两个 TLBI 作用域：

- **IS（Inner Shareable）**：指令助记符带 `is` 后缀，例如 `tlbi vae1is`。该操作面向内部共享域生效，失效请求可以通过 DVM 机制传播到共享域内其他核心；随后使用 `dsb ish` 等待该共享域内的失效对观察者可见。Linux 的普通用户地址空间刷新走的正是这类 shareable TLBI，因此它代表 munmap 实际路径。
- **NSH（Non-shareable）**：指令助记符不带 shareable 后缀，例如 `tlbi vae1`。该操作只要求在本处理单元（PE，本实验中可近似理解为本核）范围内完成，不需要把失效请求广播到内部共享域，也不需要等待远端核心完成对应失效。

二者的匹配对象相同，都是按 VA/ASID（在 protected 下还涉及 VMID 标记的合成条目）查找要作废的 TLB 条目；关键区别在于**失效是否需要跨核心传播，以及后续屏障需要等待的完成范围**。因此，IS 与 NSH 的耗时差值可以直接用来判断是否存在“广播/共享域传播”开销：如果 pKVM 罚时主要来自跨核广播，protected 下 IS 应显著慢于 NSH，并且可能随在线核数或跨簇拓扑变化；如果二者相等且不随核数变化，则说明主要开销发生在本地条目失效本身。

### 9.4 TLBI 指令直接计时：本地失效耗时基本不变，IS 与 NSH 无明显差异

如果怀疑对象是 TLBI 广播，最直接的检验就是把 TLBI 从 munmap 路径中单独取出计时。`tlbi_ab.ko` 分别测量两种 TLBI 的每个 slot 耗时：带 `is` 后缀的 Inner-Shareable 版本（可广播到共享域），以及不带后缀的 NSH 本地版本（只作用于本核）。如果主要开销来自广播，IS 应当显著慢于 NSH。

| 每个 slot（reps=2） | NSH（本地） | IS（广播） | IS − NSH |
|---|---|---|---|
| nvhe | 10 ns | 23 ns | +13 ns |
| **protected** | **289 ns** | **289 ns** | **~0** |

protected 模式的结果与广播假设相反：每个 slot 的耗时稳定在 289 ns 左右，在 n=1/2/8 之间基本不变，在同簇与跨簇之间也没有差异；同时，IS 与 NSH 没有可观测差异。即使在每个 slot 后追加一条 `dsb` 强制等待完成，该数值也不变。也就是说，`tlbi` 加 `dsb` 的耗时在本平台上主要来自本地失效，在线核数和广播属性没有带来额外增量。

为排除“模块测量的 TLBI 类型与 munmap 实际发出的 TLBI 不一致”这一可能，复查还按 munmap 拆除目标重测了一轮：使用用户态 VA 加进程 ASID 作为失效对象。结果仍然一致。

至此，§9.3 与 §9.4 出现了明确冲突：基于 `min` 的 munmap 数据显示“只要有其他核心在线就变慢”，而 TLBI 指令直接计时显示“TLBI 本身与核数无关”。事后看，§9.4 的证据更直接，也排除了用户态调度噪声；但当时仍需解释 §9.3 的误导性结果，因此又补做了两组对照实验。

### 9.5 稀疏/密集对照：同样受 `min` 误导

为调和 §9.3 与 §9.4，复查曾提出一个折中假设：也许随核数变化的不是单次广播本身，而是被广播的 TLBI **条数**。条数越多，累计等待越长。检验方法是在同一段 8 MB 跨度上比较两种触摸密度，因为二者触发的 TLBI 数量差异很大。

密集的 4 KB 触摸会让内核走整表刷新路径，只发约 4 条 `aside1is`（覆盖 2048 页）；稀疏的 16 KB 触摸则走逐页路径，约发 2036 条 `vae1is`（覆盖 512 页）。按 `min` 统计时，密集组不随核数变化，稀疏组随核数增加约 367 µs。

这组结果表面上再次支持广播解释：多核在线后的变慢只在 TLBI 条数多时出现，并且更像是与 TLBI 条数相关，而不是与页数相关。但该实验与 §9.3 有相同缺陷：主要判据仍是 `min`。真正区分“广播效应”与“统计方式造成的假象”的，是接下来的访存对照和 `perf`/均值复核。

### 9.6 冷缓存访存 + TLBI：排除“广播拖慢访存”

§6.2 将额外开销表现定位为后端访存停顿。因此，如果广播解释成立，广播产生的系统流量应当拖慢并发访存。为检验这一点，复查构造了一个持续产生冷缓存访存的负载：128 MB、经 LCG 置乱的随机**依赖性**指针追逐。该工作集超过 2 MB L3，每一步又依赖前一步结果，可抑制硬件预取；每次迭代重新播种，保证每批访问都处于冷缓存状态。

将该访存负载与 TLBI 一起按在线核数分组测试，结果如下：

| 每个 slot | n=1 | n=2 跨簇 | n=8 |
|---|---|---|---|
| 仅访存（4 次冷缓存读取） | 617 | 621 | 617 |
| 仅 TLBI | 289 | 289 | 289 |
| TLBI + 冷缓存访存 | 881 | 875 | 878 |

三行数据都不随核数变化；并且 “TLBI + 访存” 的 881 小于 “仅访存 617” 与 “仅 TLBI 289” 的简单相加结果 906，说明二者合并执行后并没有相互拖慢。这说明 TLBI 广播既没有随核数放大，也没有拖慢并发访存。因此，“广播流量挤占访存带宽，进而表现为后端停顿”的综合解释不能成立。

### 9.7 `perf` 与 `mean` 复核：`min` 造成了“多核在线变慢”的假象

到这里，TLBI 指令直接计时（§9.4）和访存对照（§9.6）都说明“与核数无关”，只有基于 `min` 的 munmap 数据（§9.3、§9.5）显示“随在线核数增加而变慢”。因此，分歧更可能来自统计方式，而不是来自硬件行为本身。复查随后改用 `perf` 对真实 munmap 循环在 n=1 与 n=8 下计数（protected，原始 PMU 事件）：

| 整轮运行（300 iters） | n=1 | n=8 |
|---|---|---|
| 墙钟 | 0.362 s | 0.348 s |
| cycles | 636 M | 625 M |
| `stall_backend`（r0024） | 427 M | 431 M |
| instructions | 552 M | 549 M |

整轮运行层面，n=1 与 n=8 几乎相同，n=8 甚至略快；`stall_backend` 也基本一致，没有出现“多核更慢”的迹象。把统计方式从最小值换成**均值**后，逐段数据也得到相同结论：

| µs/iter（mean） | n=1 | n=8 |
|---|---|---|
| touch | 485 | 465 |
| **munmap（mmap_split）** | **699** | **681** |
| **munmap（munmap_only，1000 iters）** | **mean 696** / min 269 | **mean 680** / min 396 |

munmap 的均值在 n=1 与 n=8 之间不随核数增加。更关键的是，原先作为证据的 `min` 本身并不稳定：n=8 的 min 会随样本数增加而下降，200 次迭代时约为 676，1000 次迭代时降至 396，因为样本越多，越容易捕获极快的离群点。

`min` 误导判断的原因在于两种配置的**方差不同**。n=1 时，整机只有基准核心在线，背景活动集中到同一核心附近，使单次迭代的 munmap 耗时方差很大（min 约 250，mean 约 700）；n=8 时，系统负载被摊开，每次迭代反而更紧凑（约 545）。于是，§9.3 与 §9.5 实际上是在用 n=1 的最佳样本对比 n=8 的典型样本，二者并不是同一统计意义上的量，由此制造了约 2× 的“多核在线变慢”假象。

相比之下，`perf` 的进程计数排除了被抢占时间，测量的是进程实际消耗的工作量。它显示 n=1 与 n=8 的 cycles、instructions 和 `stall_backend` 基本相同。所有能够避开单核方差影响的统计方式——均值、IRQ-off 模块、`perf` 进程计数——都得到同一结论：该开销不随在线核数变化。

### 9.8 定论：退化来自本地合成条目失效

综合 §9.4 到 §9.7，可以得到确定结论：

> **pKVM 的 munmap 罚时来自本地失效一条“stage-1 与 stage-2 合成、并带 VMID 标记”的 TLB 条目。它与在线核数无关，不是跨核广播开销，也不是 `dsb ish` 等待远端核心完成失效的开销。**

该结论也解释了 +0.27 µs/slot 的量级。§9.4 的 IRQ-off 模块测得 protected 下单独 TLBI 指令约为 289 ns/slot，nvhe 约为 23 ns/slot，差值 266 ns，正好对应主报告中由阈值扫描折算出的 +0.27 µs/slot。换言之，报告测到的额外开销是真实的，但它的性质是**逐页失效本身在 protected 下变慢**：在本平台上，即使只做本地失效，合成条目的失效耗时也约为 nvhe 的 12 倍。

相应地，§6.2 中 protected 相对 nvhe 多出的 `stall_backend` 应理解为更慢的 TLBI 在本地执行时占用了更多周期、因此以 backend stall 形式表现出来，而不是流水线在等待远端核心完成广播。这也与 §9.7 中 `stall_backend` 在 n=1 与 n=8 之间基本一致相互印证。

### 9.9 代码层面：本地 TLBI 耗时为何约为 12 倍

差异既然是本地的，又只在 protected 与 nvhe 之间出现，下一步问题就是：同一条指令为什么在两种模式下会有数量级差异？答案不在内核的发射路径。`arch/arm64/include/asm/tlbflush.h` 不按 stage-2 或 KVM 模式区分 TLBI；munmap 在 nvhe 与 protected 下发出的都是同一类 `tlbi vae1is`（运行时 KPTI 开启时两边都会追加 user ASID TLBI）。既然指令路径相同，差异只能来自这条指令需要作废的 **TLB 条目类型**，而条目类型由 host stage-2 是否启用决定。

- **protected 启用 host stage-2 并产生合成条目**：初始化收尾的 `__pkvm_prot_finalize()`（`mem_protect/host.rs:2249`）将 `params.vttbr` 设为 `kvm_get_vttbr(...)`（host stage-2 基址，并带 VMID），将 `params.vtcr` 设为 `host_mmu.arch.vtcr`，并设置 `params.hcr_el2 |= HCR_VM`（`kvm_arm.h:74`，`HCR_VM = 1<<0`），随后由 `__load_stage2(...)` 生效。
- **nvhe 不启用 host stage-2**：`__load_host_stage2()`（`host.rs:2521`）走 else 分支，将 `VTTBR_EL2` 置 0；宿主机 HCR（`HCR_HOST_NVHE_FLAGS`，`kvm_arm.h:101`）也不包含 `HCR_VM`。

因此，在 protected 下，宿主机 EL1&0 的 TLB 条目是**两级折叠后的合成条目（VA→PA），并带 VMID 标记**；在 nvhe 下，则是**纯 stage-1 的单级条目（VA→PA），只带 ASID**。这里的瓶颈不是嵌套页表遍历变深：op=3 自省已经表明 host stage-2 极浅，99.5% 的宿主机内存为 1 GB 块映射。问题出在条目类别，而不是页表层数。

按 ARM DDI 0487 D8.16／D8.17，stage-2 处于激活态时，一条按 VA 的 `tlbi vae1is` 相比 nvhe 至少多了两类工作：第一，除 VA/ASID 外还要匹配 VMID，相当于对候选条目增加标签匹配；第二，它需要清理两类按 VA 编键的条目，既包括最终的**合成** VA→PA 条目，也包括**仅 stage-1** 的 VA→IPA 中间条目，而 nvhe 只涉及单一 stage-1 条目。

更多标签匹配与更多待清理结构叠加，使单条 TLBI 的执行延迟从 nvhe 的约 21 周期上升到 protected 的约 260 周期。至于为什么在 FTC862 上恰好表现为约 12 倍，还取决于该核如何存储、检索和失效带 VMID 标记的合成条目，属于具体微架构问题。要继续分析这一点，需要 Phytium 的 TLB TRM，或能够直接暴露 TLBI 耗时的核内 PMU 事件；N80 当前不提供后者。

### 9.10 方法学教训（可复用）

本次复查最可复用的教训是：**不要用 `min` 比较两种方差不同的机器配置上的同一负载。** 减少在线核数首先改变的可能不是均值，而是每次迭代的方差。单核配置噪声更集中，最小值容易代表“最佳一次”；多核配置方差更小，最小值可能更接近典型值。此时用 `min` 横向比较，就会把不同统计含义的样本放在一起，得到看似稳定、实则错误的趋势。

更稳妥的做法是使用均值或中位数观察主要趋势，并用 `perf` 的**进程**计数器交叉验证实际工作量，因为后者排除了被抢占时间，测到的是进程消耗的 cycles、instructions 和 stall，而不是单纯墙钟。在本案中，`min` 制造了一个可复现但错误的 2×“多核在线变慢”；均值、IRQ-off TLBI 指令直接计时和 `perf` 计数共同排除了它。

### 9.11 对前文的更正与开放问题

将上述结论落回主报告，需要更正三点：

- **§8.1 与 §7.7 中“广播等待”的归因有误。** +0.27 µs/slot 是本地合成条目失效的开销（约 289 − 23 ns），而不是跨核广播完成等待；与之并列的“逐页失效序列本身更贵”仍然正确。
- **该机制与核数和拓扑无关。** 它不依赖在线核数，也不依赖同簇/跨簇放置；正文中凡暗示“跨核 / 广播 / DSB 等待远端完成”的措辞都应按本节修订（§7.7、§8.1 已就地增加更正说明）。
- **主报告的其他结论不受影响。** host stage-2 使 <2 MB 的稀疏 munmap 因逐页 TLBI 路径而变慢；N80 不支持 FEAT_TLBIRANGE；nvhe 与密集/整表刷新路径不受影响；退化幅度仍为约 +0.27 µs/slot。

仍然开放的问题与缓解方向如下：

- **约 12 倍的本地耗时差异尚未进一步拆到单一微架构原因。** 主要候选包括 VMID 标签匹配、多清一类 VA 编键条目，以及 FTC862 的 TLB 组织方式。要继续判定主因，需要 Phytium TLB TRM，或能暴露 TLBI 耗时的核内 PMU 事件。
- **缓解杠杆不变，但动机更明确。** FEAT_TLBIRANGE 仍是首选，因为它把 N 条逐页 TLBI 压缩成少数几条范围 TLBI，直接减少“昂贵的合成条目失效”发生次数；下调 `MAX_DVM_OPS` 则让更多 munmap 进入单条 `aside1is` 的整表刷新路径，以一次整 ASID 重填替代长串逐页失效。这两条路径都通过减少本地昂贵 TLBI 次数起效，与广播无关。

---

## 附录 A：测试平台一览

| 平台 | SoC / 频率 | 系统 | 内核 | 用途 |
|---|---|---|---|---|
| N90 | Phytium FTC862 / 2.1 GHz（锁定） | Kylin V10 SP1 | `6.6.30+ #4`（Rust pKVM）、`6.6.30-pkvm-c+ #6`（C pKVM） | 阶段一：四模式对照与实现交叉验证 |
| Kaitian（`ryuu`） | Phytium / — | Kylin V10 | `6.6.30+ #637` | 阶段二：mmap-split 拆分；LMDB 应用级对照 |
| N80 | Phytium / 1.8 GHz（锁定） | Kylin V10 SP1 | `6.6.30xcore-stat+`（Rust nVHE hyp） | 阶段三至五：gate、perf、op=3、阈值扫描 |

N80 关键硬件常数：`ID_AA64ISAR0_EL1 = 0x0000111110212120`，TLB 字段 [59:56] = 0，**不支持 FEAT_TLBIRANGE**；`MAX_DVM_OPS = PTRS_PER_PTE = 512`，整表刷新阈值 512 × 4 KB = 2 MB。

对照模式说明：阶段二之后以 NVHE 为基线（与 protected 共用同一内核镜像，仅启动参数不同；阶段一已证明三个非 pKVM 基线等价）。

## 附录 B：复现步骤

```bash
# 0) 环境准备（每次启动后，所有平台一致）
sudo ./prepare-host.sh            # 锁频 / 关 THP / 关 ASLR / 关深度 idle
sudo ./quiet-host.sh quiet        # 压制无关后台服务

# 1) 阶段一：四模式 lat_mmap（按模式重启后分别执行）
ENV_TAG=<tag> CORE=0 ITERS=10 RUN_PRECISE=1 ./bench-mmap.sh

# 2) 阶段二：生命周期拆分（nvhe 与 pkvm 各一轮）
MODE=<nvhe|pkvm> CORE=0 RUNS=10 REFILL=1 WARMUPS=1 scripts/mmap-split-bench.sh
python3 scripts/analyze-mmap-split.py nvhe pkvm

# 3) 阶段三：EL2 gate（protected 模式；内核需启用 CONFIG_XCORE_STATS）
#    先做阳性对照：连续 echo 2 > /proc/xcore_stats 200 次，确认计数器累加
SIZES="8 16 64" ITERS=100 CORE=0 scripts/el2-gate-bench.sh

# 4) 阶段四：perf 分解（两模式各一轮；先 echo 0 释放 PMU）
scripts/host-mm-trace.sh perf      # 含 tlbirange / funcgraph 子命令

# 5) 阶段五：
#    粒度自省（protected）：
echo 3 > /proc/xcore_stats && cat /proc/xcore_stats
#    阈值扫描（两模式各一轮）：
experiments/munmap-tlbi/run-sweep.sh   # RANGES="0.25 0.5 1 1.9 2 4 8 32 64"
```

## 附录 C：代码、脚本与数据索引

**内核代码（common 仓库）**

| 路径 | 内容 |
|---|---|
| `arch/arm64/include/asm/tlbflush.h:253,342,369,405,422` | `flush_tlb_mm` / `MAX_DVM_OPS` / 逐页循环 / 阈值分支 |
| `mm/mmap.c:2346`；`mm/mmu_gather.c:437`；`arch/arm64/include/asm/tlb.h:53` | munmap 拆除路径与最终 TLB 刷新 |
| `arch/arm64/include/asm/kvm_arm.h:101` | 宿主机 HCR 配置（TLBI 不陷入的依据） |
| `arch/arm64/kvm/hyp/nvhe/rust/src/hyp_main.rs:1739,3004` | `xcore_stats_entry`（op=0/1/2/3）；`handle_trap` |
| `arch/arm64/kvm/hyp/nvhe/rust/src/mem_protect/host.rs:521,913,953,1839,1930,2068` | `force_pte` / 直方图回调与遍历 / `adjust_range` / `idmap` / 缺页处理 |
| `arch/arm64/kvm/hyp/nvhe/rust/src/stats.rs:48` | EL2 专属 PMU 周期计数的配置与现场保存 |
| `arch/arm64/kvm/xcore_stats.c` | `/proc/xcore_stats` 接口（op=0/1/2/3） |

**测试代码与脚本（kylin-lmbench 仓库）**

| 路径 | 内容 |
|---|---|
| `src/lat_mmap.c`、`src/lat_mmap_precise.c` | 原版与纳秒精度版 lat_mmap |
| `experiments/mmap-split/mmap_split_bench.c` | 12 个生命周期子测试 |
| `experiments/munmap-tlbi/{munmap_only.c,run-sweep.sh}` | 阈值扫描微基准与驱动脚本 |
| `scripts/mmap-split-bench.sh`、`scripts/analyze-mmap-split.py` | 拆分实验驱动与分析 |
| `scripts/el2-gate-bench.sh`、`scripts/host-mm-trace.sh` | EL2 gate 与 perf/funcgraph/tlbirange |
| `bench-mmap.sh`、`prepare-host.sh`、`quiet-host.sh` | 四模式测试入口与环境控制 |

**原始数据（kylin-lmbench/results/）**

| 路径 | 内容 |
|---|---|
| `n90-v10-*-mmap/`、`n90-v10-mmap-4mode-summary.txt` | 阶段一四模式数据（含 C 内核复测） |
| `mmap-split-kaitian/{nvhe,pkvm}.csv` | 阶段二拆分数据 |
| `lmdb-bench-kaitian/{nvhe,pkvm}/` | LMDB 应用级数据 |
| `n80-munmap-gate-c0/{protected,nvhe}/` | 阶段三、四的 gate CSV 与 perf/funcgraph 日志 |

## 附录 D：阶段性详细文档

本报告为自包含总览；下列一手文档保留了各阶段更完整的过程记录与逐项数据，供查证之用：

| 阶段 | 文档 |
|---|---|
| 1 现象 | `n90-v10-mmap-host-report.md`、`pkvm-mmap-overhead-analysis.md` |
| 1 应用级 | `lmdb-pkvm-benchmark-plan.zh-CN.md`、`lmdb-kaitian-nvhe-pkvm-results.zh-CN.md` |
| 2 拆分 | `lat-mmap-test-walkthrough.zh-CN.md`、`mmap-split-kaitian-pkvm-comparison.zh-CN.md` |
| 3/4 gate 与 perf | `n80-gate-c0-results.zh-CN.md`（含 §7.3 已更正的旧机制结论） |
| 5 粒度自省 | `c1-host-stage2-granularity.zh-CN.md`（含已更正的旧机制结论） |
| 5 机制判定 | `c1-tlbi-threshold.zh-CN.md`（最终结论的完整推理链） |
| 方案与插桩 | `pkvm-mmap-optimization-plan.zh-CN.md`、`agile-popping-anchor.md`、`el2-gate-instrumentation.zh-CN.md` |
