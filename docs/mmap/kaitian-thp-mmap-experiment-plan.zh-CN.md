# Kaitian THP 缓解实验方案：透明大页能否缓解无 FEAT_TLBIRANGE 平台的 pKVM teardown 退化

**日期**：2026-06-26
**适用平台**：Kaitian（Phytium aarch64 / Kylin V10 SP1，内核 `6.6.30-pkvm-clean`，**不支持 FEAT_TLBIRANGE**，`MAX_DVM_OPS = 512` → 2 MB 整表刷新阈值）
**约束**：不改内核、不改 KVM 模式实现；仅用用户态 benchmark + sysfs 开关 + GRUB 重启切模式
**目标**：在无 FEAT_TLBIRANGE 的 Phytium 平台上，测量**透明大页（THP）能否缩小写触摸后 munmap/teardown 的 protected−nvhe 退化**——即 THP 是否能作为 FEAT_TLBIRANGE 的软件侧替代缓解手段。

> 本方案是 `pkvm-mmap-overview.zh-CN.md` 的延伸验证。根因结论（退化 = 逐页 TLBI slot 数 × 每 slot ~0.27 µs 的本地合成条目失效成本）作为既定前提；本实验只检验“减少 slot 数”的一条具体路径——用大页把 512 个 4 KB PTE 折叠成 1 个 2 MB PMD。

---

## 1. 背景与机制：THP 为什么可能有用

`pkvm-mmap-overview.zh-CN.md` 已定性：无 FEAT_TLBIRANGE 时，小于 2 MB 的刷新范围逐 4 KB slot 发 `tlbi`，每个 slot 在 protected 下失效一个带 VMID 的 stage-1×stage-2 合成条目，比 nvhe 多约 0.27 µs；总退化 ≈ slot 数 × 单 slot 成本。

FEAT_TLBIRANGE 从**单价侧**缓解（一条 range 指令覆盖多页）；**THP 从数量侧缓解**——内核拆除一个 2 MB 大页时只发**一条 PMD 级 `tlbi`**，而不是 512 条 PTE 级 `tlbi`：

- `zap_huge_pmd()`（`mm/huge_memory.c:1900`）→ `tlb_change_page_size(tlb, HPAGE_PMD_SIZE)` + `tlb_remove_pmd_tlb_entry()` 置 `cleared_pmds`；
- `tlb_get_unmap_size()` 返回 `PMD_SIZE = 2 MB`（`asm-generic/tlb.h:517,529`），arm64 `tlb_flush()` 以此为 stride、level=2（`arch/arm64/include/asm/tlb.h:57`）；
- `__flush_tlb_range_op` 的循环 `pages -= stride >> PAGE_SHIFT` 每步减 512 → **一个 2 MB 大页 = 一条 `tlbi`**。

因此若工作集被 2 MB 大页覆盖，逐页 slot 数下降约 512×，protected 退化也应随之塌缩。THP 是无 FEAT_TLBIRANGE 平台上的软件侧等价缓解，且比“调低 `MAX_DVM_OPS`”更精准（后者靠整表刷新避开逐页循环，代价是过度失效整个 ASID）。

---

## 2. 关键平台事实（已现场确认，决定实验设计）

1. **Kaitian 当前就是 `THP=always`，且处于 `kvm-arm.mode=protected`**：`THP=[always] madvise never`、`shmem_enabled=[never]`、governor=performance、Phytium 实现号 `0x70`。
2. **`lat_mmap` / `mmap-split` 映射的是可写 `MAP_SHARED` ext4 文件**，而 ext4 的 `huge_fault` 仅 DAX 可用（`fs/ext4/file.c:702,768`），`CONFIG_READ_ONLY_THP_FOR_FS` 未开启。因此这些映射**无论全局 THP 策略如何都保持 4 KB**——既有 `results/mmap-split-kaitian/*.csv`（+227% 退化基线）头部已写明 `# thp=[always]`，正是在 THP=always 下采集的。

> 推论：把全局 THP 设为 always 对文件映射的现有测试**几乎是空操作**；真正起作用的杠杆是 **anon / shmem 映射上的逐映射大页**。本方案据此设计三类实验。

3. **工具现状**：`munmap_only.c` 支持 `file | anon_base | anon_huge`（MADV_NOHUGEPAGE / MADV_HUGEPAGE）；**`op_sweep` 不支持 anon_huge**（anon 路径强制 NOHUGEPAGE）；`run-sweep.sh` 写死 `file`。E1 必须用 `munmap_only`。
4. **切模式 = GRUB cmdline + 重启 + 控制台选项**（见 `kylin-v10-kernel-deploy` skill 的 `grub-entry`）；同一内核镜像，仅 cmdline 不同，无需重新编译内核。**无法自动化**，需用户在启动时手动选择 nvhe 条目。
5. **THP / shmem / ASLR / 频率每次重启都重置**，每个 boot、每个模式都要重新施加并记录。
6. 板上路径为 **`/home/test/kylin-lmbench`**（用户 `test`），实验二进制**尚未编译**。

---

## 3. 实验设计：三类实验 × 两种模式

全程做 **protected × nvhe** 对照（nvhe 腿需用户重启选 nvhe GRUB 条目）。

| 编号 | 实验 | 工具 / 后备 | THP 杠杆 | 预期 |
|---|---|---|---|---|
| **E1** | `anon_base` vs `anon_huge` | `munmap_only` 匿名，NOHUGEPAGE vs HUGEPAGE | 逐映射（需全局 THP≠never） | anon_base 保留大的 protected−nvhe gap；**anon_huge 塌缩**（逐 PMD TLBI）。决定性正结果 |
| **E2** | 文件后备对照 | `lat_mmap_precise` / `mmap_split_bench` / `op_sweep file`（ext4） | 全局 THP always vs never | gap 在 always/never 下**基本不变**（ext4 无法获得大页）——受控复现“全局 THP 帮不了文件映射” |
| **E3** | tmpfs/shmem 共享映射 | `munmap_only file`→tmpfs + `lat_mmap_precise`→tmpfs | `shmem_enabled=always` / tmpfs `huge=always` | gap 相对 ext4**塌缩**——`lat_mmap` 形态的共享映射在 shmem 后备下能获得大页的正结果 |

### 触摸几何

- E1/E3 主用**稀疏触摸**（stride 16 KB，触摸前 `size/10`），与 overview 的 `lat_mmap` 形态一致——此时 anon_base 落在逐页 TLBI 路径、gap 最大，便于看 anon_huge 的塌缩；另加一个 **dense（stride 4，full touch）** 点对账 §7.3。
- 尺寸至少覆盖 `8 / 16 / 64 MB`，迭代数沿用既有口径（munmap_only 200~1000 iters 取 mean）。

---

## 4. 巨页生效验证（硬性前置门，不是事后补充）

“gap 塌缩”只有在大页**确实形成**时才算数。每个 anon_huge / tmpfs 运行前，用一个小工具 `experiments/munmap-tlbi/huge_check`（约 15 行）mmap + 触摸后从 `/proc/self/smaps_rollup` 读出 `AnonHugePages` / `ShmemPmdMapped` / `FilePmdMapped`：

- 读数为 0 → 大页未形成（对齐 / 内存碎片），该 huge 变体运行**作废**，需先 `drop_caches` / `compact_memory` 再重试；
- 若 `huge_check` 通过但 anon_huge gap 仍不塌缩 → 这本身是一个发现（逐 PMD 合成条目失效的单价高到抵消了数量收益），须如实记录。

---

## 5. 模式与环境控制

- 每个 boot 后先跑 `prepare-host.sh`（governor=performance @1.9 GHz、ASLR=0、关深 idle），再按实验显式设置 `transparent_hugepage/enabled` 与 `shmem_enabled`，并记录 metadata（kernel / cmdline / thp / shmem / governor）。
- `mmap-split-bench.sh` 头部已自动记录 `# thp=`，其余运行用脚本统一抓取。
- nvhe 条目若不存在，用 `kylin-v10-kernel-deploy` 的 `grub-entry` 追加 `kvm-arm.mode=nvhe`（非默认项，不影响默认 protected 启动）。

---

## 6. 执行流程

**阶段 0 — 准备（protected，当前 boot）**
1. 同步源码到板（`git -C ~/kylin-lmbench pull` 或 rsync `experiments/ scripts/ src/ bench-mmap.sh prepare-host.sh`）；**确认板上 `munmap_only.c` 含 `anon_huge`**。
2. 编译：`make build` + `make -C experiments/mmap-split` + `make -C experiments/munmap-tlbi` + 编译 `huge_check.c`。
3. `findmnt /tmp`、`/dev/shm` 确认文件系统；为 E3 挂一个专用 tmpfs `/mnt/thptmp -o huge=always`，预填后备文件。

**阶段 A — protected 腿**
4. 施加受控环境；设 `THP=always` + `shmem_enabled=always`；记录 metadata。
5. **E1**：anon_base & anon_huge 扫描（稀疏 stride 16 + 一个 dense stride 4 点，尺寸 8/16/64 MB），anon_huge 前先过 `huge_check`。
6. **E2 @ THP=always**：`lat_mmap_precise` + `mmap_split_bench`（`munmap_after_write_touch` + 完整拆分）+ `op_sweep file`。
7. 设 `THP=never`，重跑 **E2 @ THP=never**。
8. **E3**：`munmap_only file`→`/mnt/thptmp` + `lat_mmap_precise`→tmpfs（稀疏），`huge_check` 确认 `ShmemPmdMapped>0`。
9. 结果存入 `…/kaitian-thp-20260626/protected/`。

**阶段 B — nvhe 腿（需用户协助）**
10. 确保存在 `kvm-arm.mode=nvhe` GRUB 条目（缺则用 skill 追加）。**交接**：请用户重启并选择 nvhe 条目；通过 `cat /proc/cmdline` 显示 `kvm-arm.mode=nvhe` 且 dmesg 出现 `Hyp mode initialized`（非 “Protected”）确认。
11. 重新施加环境 + THP/shmem 状态（已重置），重复步骤 5–8 → `…/nvhe/`。

**阶段 C — 分析与恢复**
12. 请用户重启回默认（protected）条目；恢复板原始状态：`THP=always`、`shmem_enabled=never`、卸载 `/mnt/thptmp`。**不得遗留 nvhe / THP=never / 临时 tmpfs**。
13. 逐实验计算 protected−nvhe gap，出汇总表 +（可选）复用 `docs/mmap/scripts/plot-*.py` 风格出图；写结果文档。

---

## 7. 预期结果与判读

| 实验 | 预期 | 含义 |
|---|---|---|
| **E1** anon_base | protected−nvhe gap 大（64 MB 稀疏 ~数百 µs，逐页） | 复现逐页 TLBI 退化形态 |
| **E1** anon_huge | gap **塌缩至个位数 µs**（逐 PMD TLBI） | **THP 缓解匿名 teardown 退化（正结果）** |
| **E2** ext4 文件 | THP=always 与 THP=never gap **基本相同**，均保留完整退化 | 全局 THP 帮不了 ext4 文件映射（huge_fault 仅 DAX） |
| **E3** tmpfs 共享 | gap 相对 ext4 **塌缩**（须 `ShmemPmdMapped>0`） | shmem 后备下，`lat_mmap` 形态共享映射可受益于 THP |

一致性自检：E2 在每个模式内 always≈never（负对照）；E1 anon_base 复现已知逐页 gap；E1 anon_huge 与 E3 都应落到 2 MB 阈值后的“整表刷新”残差区（~几个百分点）。

---

## 8. 统计与判定标准

- 沿用 overview 口径：`lat_mmap` / `mmap-split` 取 **10 轮 median + MAD%**；`munmap_only` / `op_sweep` 取 **iters 内 mean**。
- `taskset -c 0`、锁频 1.9 GHz、ASLR=0、关深 idle。
- 主判据：每实验的 **protected−nvhe gap**，以及 huge 变体相对 base 的 gap 收缩比；并报告 `huge_check` 生效证据。
- 判定：
  - **THP 缓解成立**（匿名）：E1 anon_huge gap ≤ ~5% 区间，且 `huge_check` 通过；
  - **全局 THP 对文件映射无效**：E2 always vs never gap 差异 < 噪声；
  - **共享映射可经 shmem 受益**：E3 tmpfs gap 显著小于 ext4，且 `ShmemPmdMapped>0`。

---

## 9. 工具与改动（执行时新增，均为用户态）

- 新增 `experiments/munmap-tlbi/run-thp-sweep.sh`：循环 `munmap_only` 跑 `{anon_base, anon_huge}` × 尺寸 × stride（不动既有 `run-sweep.sh`）。
- 新增 `experiments/munmap-tlbi/huge_check.c`：巨页生效探针（见 §4）。
- 新增结果目录 `experiments/perf-reinvestigation/results/kaitian-thp-20260626/{protected,nvhe}/` + `README.md`（矩阵、命令、每轮 metadata 与巨页验证）。
- 实验结束后产出结果文档 `docs/mmap/pkvm-thp-mitigation.zh-CN.md`；视结果可在 overview §9.4 优化方向表补一行“THP（软件侧，减少逐页 slot 数）”。

---

## 10. 范围与风险

- **不做**同机 `system_supports_tlb_range()`-off 干预对照（需改内核；本平台本就无 FEAT_TLBIRANGE，无意义）。
- nvhe 腿阻塞在用户控制台选 GRUB 条目这一步。
- THP 大页在内存碎片下可能形成失败——靠 `huge_check` 兜底；反复失败则先 `drop_caches` + `compact_memory`。
- 结束必须把板恢复到原始状态（protected + THP=always + shmem=never，无临时挂载）。

---

## 11. 最小闭环

设备时间有限时按序执行：

1. 阶段 0 准备 + 编译 + `huge_check`。
2. protected：E1（anon_base vs anon_huge，64 MB 稀疏 + 一个 dense 点）。
3. protected：E2 64 MB（always vs never）作负对照。
4. 用户重启 nvhe；重复 2–3。
5. 计算两腿 gap：若 anon_huge gap 相对 anon_base 塌缩、而 ext4 文件 always/never 无变化，即可回答核心问题：

> 在无 FEAT_TLBIRANGE 的 Phytium 上，THP 能否缓解 pKVM teardown 退化——能（对匿名 / shmem 大页映射），但对 ext4 文件映射无效。
