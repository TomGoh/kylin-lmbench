# THP 能否缓解无 FEAT_TLBIRANGE 平台的 pKVM teardown 退化：Kaitian 实测报告

| 项目 | 内容 |
|---|---|
| 平台 | Kaitian（Phytium aarch64 / Kylin V10 SP1，内核 `6.6.30-pkvm-clean`，**不支持 FEAT_TLBIRANGE**，`MAX_DVM_OPS=512` → 2 MB 整表刷新阈值） |
| 日期 | 2026-06-26 |
| 方法 | protected × nvhe 全对照（GRUB 切 `kvm-arm.mode`，同一内核镜像），三类实验，纯用户态 + sysfs，受控环境 |
| 数据 | `experiments/perf-reinvestigation/results/kaitian-thp-20260626/{protected,nvhe}/` |
| 配套方案 | [kaitian-thp-mmap-experiment-plan.zh-CN.md](kaitian-thp-mmap-experiment-plan.zh-CN.md)；机制背景见 [pkvm-mmap-overview.zh-CN.md](pkvm-mmap-overview.zh-CN.md) |

**一句话结论**：在无 FEAT_TLBIRANGE 的 Phytium 上，THP **能**缓解写触摸后 munmap/teardown 的 pKVM 退化（protected−nvhe gap）——但它是**逐映射属性，不是一个全局开关**：把 `transparent_hugepage/enabled` 设成 `always` **对 `lat_mmap` 默认的 ext4 文件映射毫无作用**（+208 µs 税原封不动），因为 ext4 的 `huge_fault` 仅 DAX 可用；只有当内存**真的拿到大页**时税才消失——匿名映射（小于 2 MB 的逐页区间）税从 +26/+50 µs 降到 0，而**同样 `lat_mmap` 形态的 `MAP_SHARED` 映射改用支持 THP 的 shmem（tmpfs `huge=always`）后端时，税从 +208 µs 塌缩到 +0.4 µs**。即 THP 是 FEAT_TLBIRANGE 的可行软件替代，但必须让内存被大页映射（匿名，或 shmem/tmpfs `huge=`），而非仅切 sysfs 开关。

---

## 1. 背景与机制

`pkvm-mmap-overview.zh-CN.md` 已确证：无 FEAT_TLBIRANGE 时，写触摸后的 munmap 在小于 2 MB 的刷新范围内**逐 4 KB slot 发 `tlbi`**，每个 slot 在 protected 下失效一个带 VMID 的 stage-1×stage-2 合成条目，比 nvhe 多 ~0.27 µs（N80）/ ~0.125 µs（Kaitian）。总退化 ≈ **逐页 slot 数 × 每 slot 税**。

THP 从**数量侧**攻击这个乘积：拆除一个 2 MB 大页只发**一条 PMD 级 `tlbi`**，而非 512 条 PTE 级 `tlbi`。源码路径（在本机内核确认）：

- `zap_huge_pmd()`（`mm/huge_memory.c:1900`）→ `tlb_change_page_size(tlb, HPAGE_PMD_SIZE)` + `tlb_remove_pmd_tlb_entry()` 置 `cleared_pmds`；
- `tlb_get_unmap_size()` 返回 `PMD_SIZE = 2 MB`（`asm-generic/tlb.h:517,529`），arm64 `tlb_flush()` 以此为 stride、`tlb_level=2`（`arch/arm64/include/asm/tlb.h:57`）；
- `__flush_tlb_range_op` 循环 `pages -= stride >> PAGE_SHIFT` 每步减 512 → **一个 2 MB 大页 = 一条 `tlbi`**。

**关键前提（决定实验设计）**：`lat_mmap` 映射的是可写 `MAP_SHARED` **ext4** 文件，而 ext4 的 `huge_fault` 仅 DAX 可用（`fs/ext4/file.c:702,768`），`CONFIG_READ_ONLY_THP_FOR_FS` 未开启。因此 ext4 文件映射**无论全局 THP 策略如何都保持 4 KB**。真正的杠杆是**匿名 / shmem 映射上的逐映射大页**。本报告据此设计三类实验。

---

## 2. 方法与受控环境

- **两种模式**：Kaitian 默认 GRUB 条目 `pkvm-clean-protected` 启 protected；另有 `6.6.30-pkvm-clean (nVHE)` 条目启 nvhe。同一内核镜像，仅 cmdline `kvm-arm.mode` 不同。nvhe 腿需在控制台手动选条目并重启。
- **唯一自变量**：每个对照只改一个变量——E1 只改 `madvise`（NOHUGEPAGE/HUGEPAGE），E2 只改全局 THP（always/never），E3 只改后端文件系统（ext4/tmpfs）；模式（protected/nvhe）是唯一的跨 boot 轴。
- **降噪**（`prepare-host.sh` + `quiet-host.sh`，每个 boot 重新施加）：governor=performance、频率锁 1.9 GHz、`ASLR=0`、关深 cpuidle、压制无关后台服务。**`ASLR=0` 在本实验尤其关键**：它使匿名 mmap 基址确定，配合下文的 2 MB 对齐使大页能稳定形成。
- **绑核**：全部 `taskset -c 0`。
- **降噪手段**：E1 在每轮内 `anon_base`/`anon_huge` **交错执行**以抵消慢漂移；E2 在每轮内 always/never 交错。
- **统计**：`lat_mmap_precise` 取 per-iter 中位数；teardown 类（`munmap_only`/`op_sweep`）每次报告 iters 内 mean，跨轮取中位数（n=8~10）。环境极稳，跨轮 spread < 1%。
- **巨页生效门（硬性前置）**：每个大页变体运行前用 `huge_check` 从 `/proc/self/smaps_rollup` 读 `AnonHugePages`/`ShmemPmdMapped`，确认大页**确实形成**；读数为 0 即作废重试。一个"塌缩的 gap"只有在大页确实形成时才算数。

### 2.1 一处必要的工具修正：匿名映射 2 MB 对齐

初次运行发现：64 MB 匿名映射稀疏触摸时大页形成（`AnonHugePages=6144 kB`），但 16 MB / 8 MB 稀疏触摸**完全不形成大页**（`0 kB`）——因为这些映射的头部不是 2 MB 对齐，小于 2 MB 的头部触摸触发不了 huge fault。为使 huge 变体在**每个尺寸**都能公平地拿到大页，把 `munmap_only.c`（与 `huge_check.c`）的匿名分支改为 **2 MB 对齐**（超额分配后裁掉首尾，计时仍只覆盖 `munmap(p, sz)`）。对齐对 `anon_base` 无害（仍 4 KB），对 `anon_huge` 是使能项，对双方公平。修正后所有尺寸均稳定形成大页（8/16 MB → 1 个，64 MB → 4 个）。

### 2.2 三类实验

| 编号 | 实验 | 工具 / 后端 | THP 杠杆 |
|---|---|---|---|
| **E1** | `anon_base` vs `anon_huge` | `munmap_only` 匿名，NOHUGEPAGE vs HUGEPAGE | 逐映射 |
| **E2** | ext4 文件对照 | `lat_mmap_precise` / `op_sweep file`（ext4 `/tmp`） | 全局 THP always vs never |
| **E3** | tmpfs/shmem 共享映射 | `op_sweep file` / `lat_mmap_precise`→tmpfs `huge=always` | shmem 大页 |

`/tmp` 经确认为 ext4（`stat -f` 报 `ext2/ext3`），E3 的 tmpfs 用独立挂载 `mount -t tmpfs -o huge=always`（不动全局 `shmem_enabled`，减少扰动）。

---

## 3. 结果：protected−nvhe gap 就是 pKVM 税

所有数值为中位数，单位 µs。**gap = protected − nvhe** 即 pKVM 的额外开销。

### 3.1 E2 ext4 文件（负对照）—— 全局 THP 帮不了文件映射

| 指标 | protected | nvhe | **gap（pKVM 税）** |
|---|---:|---:|---:|
| `lat_mmap_precise` THP=**always** | 631.7 | 423.3 | **+208.4** |
| `lat_mmap_precise` THP=**never** | 634.4 | 422.1 | **+212.3** |
| `op_sweep` teardown THP=**always** | 293.3 | 89.0 | **+204.3** |
| `op_sweep` teardown THP=**never** | 292.9 | 88.9 | **+204.0** |

ext4 文件映射有 ~+208 µs 的 pKVM 税，**always 与 never 完全一致**（+204.3 vs +204.0；+208.4 vs +212.3，差异在噪声内）。全局 THP=always 对 `lat_mmap` 默认工作负载**毫无作用**。

### 3.2 E3 tmpfs/shmem（同 `lat_mmap` 形态，但可拿大页）—— 税塌缩

| 指标 | protected | nvhe | **gap** | 巨页验证 |
|---|---:|---:|---:|---|
| `op_sweep` teardown | 3.4 | 3.4 | **0.0** | `ShmemPmdMapped` 8192 kB（稀疏）/ 65536 kB（满） |
| `lat_mmap_precise` | 13.9 | 13.5 | **+0.4** | 同上 |

把**同一个 `MAP_SHARED` 工作负载**的后端从 ext4 换成支持 THP 的 shmem（tmpfs `huge=always`），pKVM 税从 **+208 µs 塌缩到 +0.4 µs**。这是对"`lat_mmap` 是文件映射所以 THP 帮不上"这一局限的直接回应：一旦后端能拿大页，税就消失。

> shmem 的 munmap **不释放底层页**（页归 tmpfs inode 所有），所以 E3 的 teardown 几乎是**纯页表 + TLBI**——这使 E3 成为 TLBI 数量效应最干净的隔离：同一共享映射，4 KB→2 MB，512× 更少的 TLBI，teardown 从 293 µs → 3.4 µs（~77×）。

### 3.3 E1 匿名映射

| 触摸点 | 变体 | protected | nvhe | **gap** |
|---|---|---:|---:|---:|
| 8 MB 稀疏 | `anon_base` | 47.8 | 21.6 | **+26.2** |
| 8 MB 稀疏 | `anon_huge` | 5.0 | 5.0 | **0.0** |
| 16 MB 稀疏 | `anon_base` | 89.5 | 39.4 | **+50.1** |
| 16 MB 稀疏 | `anon_huge` | 5.1 | 5.1 | **0.0** |
| 64 MB 稀疏 | `anon_base` | 120.3 | 120.4 | −0.1 |
| 64 MB 稀疏 | `anon_huge` | 19.9 | 19.6 | +0.3 |
| 64 MB 密集 | `anon_base` | 6708.9 | 7069.7 | −360.8 |
| 64 MB 密集 | `anon_huge` | 197.2 | 195.7 | +1.5 |

匿名映射的 pKVM 税只在**触摸跨度 < 2 MB**（8/16 MB 稀疏）出现：+26/+50 µs；`anon_huge` 把它降到 **0**。64 MB 稀疏/密集 `anon_base` **没有税**（见 §4.2 解释）。

---

## 4. 机制分析与定量闭环

### 4.1 税就是逐页 TLBI 税，且与 overview 定量吻合

- **ext4 文件 +204 µs**：64 MB 稀疏触摸跨度 6.4 MB，脏文件页按 PMD 分批、每批约 509 个 4 KB slot、约 3.2 个满 PMD → ~1630 个 slot；1630 × **0.125 µs/slot**（Kaitian 单价，overview §7.5.5）≈ 204 µs。与 overview §4.3 的 +205 µs **完全一致**。
- **匿名 8/16 MB +26/+50 µs**：触摸跨度 0.8/1.6 MB → ~200/400 个 4 KB slot；× 0.125 µs/slot ≈ 25/50 µs。**同一单价**。

三条独立路径（ext4 文件、匿名小尺寸、以及 overview 原始 munmap_split）给出同一个 0.125 µs/slot，互相闭环。

### 4.2 为什么匿名 64 MB 没有税，而 ext4 64 MB 有

差别在 `force_flush` 的触发条件。**脏的共享文件页**在 `zap_present_folio_ptes` 中触发 per-PMD `force_flush`（须在 rmap 拆除前刷新），使刷新按 PMD 分批、每批略低于 2 MB → 持续走逐页 TLBI 路径，所以 ext4 64 MB 仍有满额税。**匿名私有页不触发这种 per-PMD 强制刷新**，刷新范围累积到整个触摸跨度：64 MB 稀疏跨度 6.4 MB > 2 MB → 一次整表 `aside1is` → 无逐页 TLBI → 无税（这与 overview §7.5.5 中干净页/读触摸的累积行为同源）。因此：

- 匿名映射的 THP 收益只在**小于 2 MB 跨度**的逐页区间显现（8/16 MB）；
- 64 MB 匿名稀疏/密集已自动走整表刷新，**没有税可消**——此时 `anon_huge` 相对 `anon_base` 的巨大加速（120→20、6709→197）是**与模式无关的 teardown 效率**（少清页表项、少释放页），不是 pKVM 税的缓解。这一点必须如实区分：**within-protected 的 base→huge 差值混了"TLBI 税"与"释放页/页表成本"两部分，只有 protected−nvhe 的 gap 才隔离出 pKVM 税。**

### 4.3 巨页生效证据

E1（对齐后，protected）：匿名 64/6.4 → `AnonHugePages 8192 kB`（4 个大页）、16/1.6 → 2048 kB（1 个）、8/0.8 → 2048 kB（1 个）、64/64 → 65536 kB（满）。E3：shmem 64/6.4 → `ShmemPmdMapped 8192 kB`、64/64 → 65536 kB。所有"塌缩的 gap"均有对应的大页生效证据。

---

## 5. 结论与实践建议

1. **THP 是无 FEAT_TLBIRANGE 平台上 pKVM teardown 税的有效软件缓解**——它从数量侧把 512 条 PTE TLBI 折叠成 1 条 PMD TLBI，与 FEAT_TLBIRANGE 从单价侧的缓解互补。
2. **但它是逐映射属性，不是全局开关**：把 `transparent_hugepage/enabled=always` 对 `lat_mmap` 默认的 ext4 文件映射无效（ext4 `huge_fault` 仅 DAX）。
3. **缓解在大页确实形成处真实有效**：
   - **匿名内存**：小于 2 MB 的逐页区间，税完全消失；分配器/运行时的大块匿名内存若用 `MADV_HUGEPAGE` 可受益。
   - **共享文件映射**：改用支持 THP 的后端（tmpfs/shmem `huge=`，或 DAX），`lat_mmap` 形态的税从 +208 µs 塌缩到 ~0。
4. **边界**：匿名触摸跨度 ≥ 2 MB 时已自动整表刷新、本无税；THP 在该区间的加速与 pKVM 无关。THP 大页能否形成依赖对齐、尺寸 ≥ 2 MB、以及内存碎片下的分配成功率。

**给受此问题影响的负载的建议**：频繁建立/拆除中小映射且无法升级到带 FEAT_TLBIRANGE 的硬件时，让热点内存被大页映射——匿名用 `MADV_HUGEPAGE`、共享用 tmpfs/shmem `huge=` 或 DAX 后端——可显著削减 pKVM 下的 teardown 税；单纯打开全局 THP 开关对 ext4 文件 mmap 无济于事。

---

## 6. 复现

```bash
# 0) 同步工具到板并编译（板上 /home/test/kylin-lmbench）
make -C experiments/munmap-tlbi           # munmap_only, op_sweep
gcc -O2 -o experiments/munmap-tlbi/huge_check experiments/munmap-tlbi/huge_check.c
gcc -O2 -o bin/lat_mmap_precise src/lat_mmap_precise.c

# 1) 每个 boot/模式跑同一驱动（自动施加受控环境、跑 E1/E2/E3、存结果）
bash experiments/munmap-tlbi/thp-leg.sh protected     # protected 腿
# —— 重启选 '6.6.30-pkvm-clean (nVHE)' 条目 ——
bash experiments/munmap-tlbi/thp-leg.sh nvhe          # nvhe 腿

# 2) 单腿汇总 / 双腿 gap
python3 experiments/munmap-tlbi/analyze-thp.py experiments/perf-reinvestigation/results/kaitian-thp-20260626/protected
```

**工具与数据索引**：

| 路径 | 内容 |
|---|---|
| `experiments/munmap-tlbi/munmap_only.c` | teardown 计时（含 `anon_base`/`anon_huge`，已加 2 MB 对齐） |
| `experiments/munmap-tlbi/op_sweep.c` | `munmap`/`dontneed`/`mprotect` × `file`/`anon` teardown 扫描 |
| `experiments/munmap-tlbi/huge_check.c` | 巨页生效门（按精确触摸几何报告 `AnonHugePages`/`ShmemPmdMapped`） |
| `experiments/munmap-tlbi/run-thp-sweep.sh` | E1 交错驱动（anon_base/anon_huge × 尺寸 × stride） |
| `experiments/munmap-tlbi/thp-leg.sh` | 单 boot/模式的 E1/E2/E3 全套驱动（环境施加 + 元数据 + 存结果） |
| `experiments/munmap-tlbi/analyze-thp.py` | 单腿中位数汇总 |
| `experiments/perf-reinvestigation/results/kaitian-thp-20260626/{protected,nvhe}/` | 全部原始数据 + 每腿 `metadata.txt`、`e1/e2/e3` 原始输出与巨页验证 |

**板卡状态**：实验后已恢复——tmpfs 卸载、临时后备文件删除、全局 THP=always（原值）/ shmem=never（原值，未改）保持不变，重启回默认 `pkvm-clean-protected` 条目。
