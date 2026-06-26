# Pixel 9 Pro XL pKVM mmap/teardown 实验方案

**日期**：2026-06-25
**适用平台**：Pixel 9 Pro XL，root，Android AOSP，可在 `kvm-arm.mode=nvhe` 与 `kvm-arm.mode=protected` 间切换
**约束**：不依赖内核改动；不假设可获得精确 Pixel GKI 源码；不依赖内核模块或直接 TLBI 微基准
**目标**：在纯用户态约束下，验证 Tensor G4 / Pixel 平台是否存在 pKVM protected 下的 per-entry teardown 额外成本，并判断真实多页 teardown 是否在行为上隐藏了这笔成本。

本文暂不使用已有 Pixel 实验结果作为前提。Phytium 结论只作为待检验假设，不直接迁移到 Pixel。

---

## 1. 实验要回答的问题

Phytium 平台上，pKVM protected 模式为宿主机启用 host stage-2 后，写触摸后的 `munmap` 在小于 2 MB 的刷新范围内逐 4 KB slot 发出 TLBI；由于平台不支持 FEAT_TLBIRANGE，每个 slot 在 protected 下多约 `+0.27 us`，最终表现为 `lat_mmap` 大尺寸退化。

Pixel 9 Pro XL 预计支持 TLB Range Flush，但当前约束下无法改内核，也不能把“源码确认 `__flush_tlb_range()` 走了 range TLBI”作为必要证据。因此 Pixel 实验的核心不应是单纯复刻 `lat_mmap`，而应先用用户态构造一个近似 `tlbi_ab.ko` 的黑盒测量：

> 先写触摸 N 个 4 KB 页，再逐页执行 N 次 `madvise(addr + i * 4KB, 4KB, MADV_DONTNEED)`，拟合 protected 相对 nvhe 的 per-entry teardown 斜率。

这组实验直接回答：

| 问题 | 主要证据 |
|---|---|
| Tensor G4 protected 下每个 4 KB teardown entry 是否比 nvhe 更贵 | 单页 `MADV_DONTNEED` 的 `protected - nvhe` 斜率 |
| 如果单 entry 更贵，真实多页 teardown 是否隐藏了这笔成本 | 一次性 batched `MADV_DONTNEED(base, N * 4KB)` 的斜率 |
| 如果真实 `lat_mmap` 不慢，是因为没有 per-entry 成本，还是因为批量路径把成本压下去了 | 单页 slope 与 batched slope 配对 |
| Pixel 是否仍复现 Phytium 的 2 MB / slot 指纹 | dense 阈值扫描与 sparse 参考点 |
| 时间差是否来自软件路径不公平、page fault 或调度噪声 | untouched 对照、`simpleperf`、多次 boot pair |

最终结论应分级表述：

1. **强结论**：Pixel protected 下是否存在 per-entry teardown 额外成本，主数字是 DiD 校正后的 `per_entry_cost`，单位 ns/op。
2. **强结论**：若 DiD 接近 0，必须给出 `resolution_floor_ns_per_op`，把结论写成“低于 X ns/op 上界”，而不是笼统写“没有成本”。
3. **强结论**：真实 batched teardown 是否仍随 N 线性放大。
4. **中等强度结论**：若单页有 slope、batched 无 slope，并且设备 metadata 显示支持 TLB Range Flush，则 range TLBI 是最合理解释；但这不是同机源码级证明。
5. **不能声称**：同一台 Pixel 禁用 TLB Range Flush 后退化回归。这个需要改内核或同机 feature toggle。

---

## 2. 公平性原则

Pixel 实验的唯一自变量应是 KVM 模式。其他条件尽量固定；无法固定的条件必须记录并纳入结果判读。

| 项 | 控制要求 |
|---|---|
| 设备 | 同一台 Pixel 9 Pro XL |
| 系统 | 同一套 AOSP userspace |
| 内核 | 尽量同一 kernel build，只切 `kvm-arm.mode=nvhe` / `kvm-arm.mode=protected` |
| 测试二进制 | 同一批 native benchmark，记录 `sha256sum` |
| CPU | 主测试固定一个稳定核心。若 X4 峰值频率容易中途降频，优先选一个较稳定的 A720/mid core；稳定低频比会降频的峰值核心更适合斜率实验 |
| 频率 | 优先固定 performance 模式或把目标 core cap 在稳定频点；每个 N 点前后记录 `scaling_cur_freq` |
| 温度 | 每个 N 点前后记录 thermal zone；温度越界或发生 throttling 的数据单独标记并丢弃 |
| 映射类型 | per-entry 主实验使用 anonymous private mapping，避免文件页缓存和写回噪声 |
| 页粒度 | 主实验按 `sysconf(_SC_PAGESIZE)` 确认 4 KB 页；尽量对映射调用 `MADV_NOHUGEPAGE`，避免 THP/mTHP 污染单页语义 |
| 执行顺序 | 多次交错重启，避免单次启动状态偏差；每个 boot 内随机化 N 点顺序，避免热爬升与 N 单调相关 |

推荐 boot 顺序：

```text
protected-boot01
nvhe-boot01
nvhe-boot02
protected-boot02
protected-boot03
nvhe-boot03
nvhe-boot04
protected-boot04
```

每个模式至少 4 个 boot 样本。每个 boot 内每个数据点至少 10 轮；per-entry 主实验和 2 MB 附近阈值点建议 30 轮。主统计量使用 median、mean、MAD%，不使用 min 作为主要判据。

斜率实验需要额外的热/频率协议：

1. 每个 boot 内不要按 `256 → 8192` 固定顺序扫 N，而是对 N 点随机排列；touched、untouched、batched 三类也应交错执行。
2. 每个 N 点之间加入冷却间隔，直到目标 core 的 `scaling_cur_freq` 回到预期频点、关键 thermal zone 回到预设范围。
3. 若某个 N 点执行前后频率下降、thermal 状态跨过预设阈值，或该点残差明显偏离，应标记为 reject 并在冷却后重跑。
4. 阈值、冷却时间和 reject 规则必须写入结果 README，不能事后按数据形态选择。

本仓库已将这些要求固化到三个工具中：

| 工具 | 作用 |
|---|---|
| `experiments/munmap-tlbi/pixel_madv_entry_slope.c` | 设备端用户态探针，执行 touched/untouched、single/batched `MADV_DONTNEED`，输出 per-run CSV |
| `experiments/munmap-tlbi/pixel-run-madv-entry-slope.sh` | host 端 runner，不切 KVM 模式；负责 push 工具、采 metadata、随机化任务顺序、记录频率/温度、写 reject_reason |
| `experiments/munmap-tlbi/pixel-analyze-madv-entry-slope.py` | 读取 nvhe/protected CSV，拟合 slope，计算 raw delta、untouched drift、DiD per-entry cost 与解析下限 |
| `experiments/munmap-tlbi/pixel-summarize-madv-entry-slope.py` | 汇总多个 boot pair 的 DiD 行，计算 median/mean、bootstrap CI、漂移项和最终 `resolution_floor_ns_per_op` |

构建 Android 二进制：

```bash
make -C experiments/munmap-tlbi android
```

在当前已启动的模式下采集一轮数据：

```bash
OUT=experiments/munmap-tlbi/results/pixel-madv-entry-nvhe-boot01 \
CPU=4 PAGES=256,512,1024,2048,4096,8192 RUNS=30 BLOCKS=1 COOLDOWN_SEC=2 \
bash experiments/munmap-tlbi/pixel-run-madv-entry-slope.sh
```

runner **不会**切换 `kvm-arm.mode`、不会 reboot、不会 fastboot/flash；它只在当前模式下跑用户态测试。切换 nvhe/protected 仍按 `pixel-komodo-pkvm-nvhe` skill 单独完成。

---

## 3. 阶段 0：平台确认与噪声基线

阶段 0 的目标是证明两种启动模式确实有效，并建立后续差异判断的噪声底。这里不要求源码确认，只采集设备可见证据。

每次启动后采集 metadata：

```bash
cat /proc/cmdline
uname -a
dmesg | grep -iE 'pkvm|protected kvm|nvhe|kvm-arm|tlb range|tlbirange|tlbi'
simpleperf list
cat /sys/devices/system/cpu/possible
cat /sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_max_freq
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq
cat /sys/devices/system/cpu/cpu*/topology/core_id
cat /sys/devices/system/cpu/cpu*/topology/physical_package_id
cat /sys/class/thermal/thermal_zone*/temp
```

可选辅助探测：

```bash
cat /proc/kallsyms | grep -i 'tlb' | head
ls /sys/kernel/tracing /sys/kernel/debug/tracing
```

这些信息只用于确认环境和解释结果。若 dmesg/cpucap 显示 TLB Range Flush 能力，是后续“batched 路径为何不线性放大”的重要旁证；若看不到这类信息，也不能直接否定，因为 Android 内核可能不暴露完整日志。

噪声基线建议包括：

| 测试 | 目的 |
|---|---|
| 空循环或轻量 syscall loop | 估计调度与计时噪声 |
| `lat_mem_rd` | 稳态读访问是否受 pKVM 影响 |
| `bw_mem` | 稳态带宽是否受 pKVM 影响 |
| 热映射反复读写 | 已建立 mmap 后的常规访问是否受影响 |

若这些稳态对照已经出现稳定 protected 退化，则不能直接沿用 TLBI teardown 归因，需要先排查频率、温度、调度、内核配置或 Android 后台活动。

---

## 4. 阶段 1：per-entry `MADV_DONTNEED` 斜率主实验

阶段 1 是本方案的证因核心。它强制把 N 页 teardown 拆成 N 次单页操作，让真实多页路径无法把多个 entry 合并处理，从而测出 protected 相对 nvhe 的 per-entry 成本。

### 4.1 touched single-page MADV

主测试使用 anonymous private mapping。每轮都重新 `mmap`、重新写触摸、再计时单页 `MADV_DONTNEED` 批次；计时结束后 `munmap` 整段映射。

伪代码：

```c
size_t len = n_pages * 4096;
char *p = mmap(NULL, len, PROT_READ | PROT_WRITE,
               MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
madvise(p, len, MADV_NOHUGEPAGE);

/* 计时外：确保每个 4 KB 页都有真实 PTE 和物理页 */
for (size_t i = 0; i < n_pages; i++)
    p[i * 4096] = 1;

clock_gettime(CLOCK_MONOTONIC, &t0);
for (size_t i = 0; i < n_pages; i++)
    madvise(p + i * 4096, 4096, MADV_DONTNEED);
clock_gettime(CLOCK_MONOTONIC, &t1);

munmap(p, len);
```

关键点：

1. **每轮必须重新写触摸**。`MADV_DONTNEED` 后页已经被丢弃；如果复用同一 mapping 而不重新触摸，后续轮次会变成 no-op。
2. **使用 `madvise` 而不是逐页 `munmap`**。逐页 `munmap` 会制造大量 VMA split/merge 成本；`MADV_DONTNEED` 保留 VMA，主要触发页表清理与 TLB maintenance。
3. **主实验不使用文件映射**。文件页会引入 page cache、dirty accounting 和写回语义；file-backed 版本只作为后续操作谱系对照。
4. **避免大页污染**。程序启动时应检查 `sysconf(_SC_PAGESIZE) == 4096`；映射后调用 `MADV_NOHUGEPAGE`，并用 page-fault/simpleperf 计数确认 touched 页数量随 N 线性增长。如果平台仍可能使用 mTHP，应把结果写成“4 KB syscall 粒度的 per-entry probe”，并在报告中说明大页状态。
5. **关注线性残差**。预触摸 N 页本身会改变 cache/TLB 微状态，`N=8192` 后进入计时循环时的状态不一定等同于 `N=256`。如果斜率残差出现系统性弯曲，这可能是状态随 N 变化造成的，而不必然表示模型无效；应报告残差图，并可补充只拟合中间 N 区间的敏感性分析。

扫描点：

```text
N = 256, 512, 1024, 2048, 4096, 8192
```

如果时间允许，可加：

```text
N = 16384
```

拟合模型：

```text
T_mode(N) = intercept_mode + slope_mode * N
delta_slope = slope_protected - slope_nvhe
```

主输出：

| 指标 | 含义 |
|---|---|
| `slope_nvhe` | 每个 4 KB touched MADV 在 nvhe 下的平均增量成本 |
| `slope_protected` | 每个 4 KB touched MADV 在 protected 下的平均增量成本 |
| `delta_slope` | protected 每个 entry 相对 nvhe 的额外成本 |
| `R^2` / 残差 | 判断线性模型是否适合 |

设备端 CSV 每行是一轮测量，核心字段为：

| 字段 | 含义 |
|---|---|
| `mode` / `touch` / `pages` / `run_index` | 当前组合与页数 |
| `setup_elapsed_ns` / `setup_minor_faults_delta` | 计时外 setup：`mmap`、`MADV_NOHUGEPAGE`、可选写触摸 |
| `elapsed_ns` / `timed_minor_faults_delta` | 正式计时窗口：只覆盖 single 或 batched `MADV_DONTNEED` |
| `cpu_before` / `cpu_after` | 计时窗口前后的实际 CPU；若不同，说明发生迁核 |
| `status` | `ok` 或 syscall 错误 |

host runner 会在这些字段前追加：

```text
block_id, task_index, mode_label, cpu_target,
freq_before_khz, freq_after_khz,
thermal_before_mc, thermal_after_mc,
thermal_detail_before, thermal_detail_after,
reject_reason
```

分析脚本默认只使用 `reject_reason=ok` 且 `status=ok` 的行。
若 CSV 中存在 `cpu_before` / `cpu_after` / `cpu_target`，分析脚本还会过滤计时窗口内迁核或未落在目标 CPU 上的行；这些样本不进入 slope 拟合。

判读：

| `delta_slope` | 结论 |
|---|---|
| 接近 Phytium 的数百 ns/op | Tensor G4 上 expensive combined-entry invalidation 仍存在，真实 workload 是否受影响取决于批量路径能否隐藏 |
| 接近 0，且置信区间很窄 | Tensor G4 的 per-entry invalidation 本身便宜；range TLBI 不是必要解释 |
| 小但稳定为正 | 存在剩余 per-entry 成本，但显著低于 Phytium |
| 线性差、残差大 | 调度/热/内核路径噪声过大，需要重跑或收缩 N 范围 |

### 4.2 untouched single-page MADV 对照

untouched 对照完全相同，但不写触摸页面：

```c
char *p = mmap(NULL, len, PROT_READ | PROT_WRITE,
               MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
madvise(p, len, MADV_NOHUGEPAGE);

clock_gettime(CLOCK_MONOTONIC, &t0);
for (size_t i = 0; i < n_pages; i++)
    madvise(p + i * 4096, 4096, MADV_DONTNEED);
clock_gettime(CLOCK_MONOTONIC, &t1);

munmap(p, len);
```

untouched 不是单纯的定性 sanity check，而是主估计器的漂移校正项。两个斜率的含义不同：

```text
untouched slope ≈ syscall + VMA lookup
touched slope   ≈ syscall + VMA lookup + zap PTE + page-free + TLBI
```

理想情况下，`touched_protected - touched_nvhe` 主要剩下 protected 下的 entry invalidation 额外成本。但 Pixel 实验需要跨 boot 切换模式，boot-to-boot 的 common-mode 漂移会污染这个差值。untouched slope 正好测到同一批 boot pair 中 syscall + VMA lookup 空路径的系统性漂移，因此主结果应使用 difference-in-differences：

```text
raw_delta      = slope_touched_protected   - slope_touched_nvhe
drift_delta    = slope_untouched_protected - slope_untouched_nvhe
per_entry_cost = raw_delta - drift_delta
```

每个相邻 boot pair 都单独计算一次 `per_entry_cost`，最后再对 boot-pair 结果求 median/mean 与 bootstrap CI。报告中仍保留 `raw_delta`，但 headline 数字应是 DiD 后的 `per_entry_cost`。

需要明确 DiD 的边界：它扣除的是 untouched 能观测到的 syscall + VMA lookup 漂移；touched 独有的 zap-PTE、page-free 以及由此伴随的 TLB maintenance 漂移没有干净的用户态对照可以单独扣掉。这部分不应被认为已由 DiD 完全消除，而应体现在 boot-pair 级 `per_entry_cost` CI 和 `resolution_floor_ns_per_op` 中。因此 null 结果的诚实写法仍是“低于 X ns/op 上界”，而不是“漂移已全部消除后为 0”。

判读：

| 结果 | 含义 |
|---|---|
| `raw_delta` 为正，`drift_delta` 接近 0，DiD 仍为正 | 支持真实 PTE teardown / TLB invalidation 差异 |
| `raw_delta` 与 `drift_delta` 同等为正，DiD 接近 0 | 差异主要来自 syscall、VMA 查找或 boot 漂移，不应归因到 entry invalidation |
| `drift_delta` 自身波动很大 | 当前协议的解析下限较高；需要增加 boot pair、runs、冷却或改 core |

### 4.3 `simpleperf` 嵌入主实验

`simpleperf` 不作为单独后处理，而应嵌入阶段 1 的关键点：

```bash
simpleperf stat \
  -e task-clock,cpu-cycles,instructions,page-faults \
  -- taskset -c <cpu> ./pixel_madv_entry_slope --touched --pages 4096 --runs 30
```

若平台支持，再加：

```text
stalled-cycles-backend
dTLB-load-misses
dTLB-store-misses
dTLB walk/refill 相关 raw event
```

判读：

| 现象 | 含义 |
|---|---|
| instructions/page-faults 随 N 在两模式中一致，cycles/stall 体现 slope 差异 | 支持同一软件路径下硬件等待不同 |
| instructions 漂移很大 | absolute A/B 容易被污染，优先相信 slope 和对照 |
| page-faults 不一致 | 预触摸或轮次重置有问题 |

注意 `simpleperf stat` 默认覆盖整个进程，而不是只覆盖计时窗口；它看到的 page faults 很大一部分来自计时外的预触摸阶段。因此 page-faults 主要用于确认两模式 setup 公平，不应被写成 teardown 周期的直接分解。cycles/stall 若随 DiD slope 同向变化，只能作为佐证。

---

## 5. 阶段 2：batched teardown 行为对照

阶段 2 与阶段 1 使用同样的预触摸，但计时窗口内只发一次大范围 `MADV_DONTNEED`：

```c
size_t len = n_pages * 4096;
char *p = mmap(NULL, len, PROT_READ | PROT_WRITE,
               MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
madvise(p, len, MADV_NOHUGEPAGE);

for (size_t i = 0; i < n_pages; i++)
    p[i * 4096] = 1;

clock_gettime(CLOCK_MONOTONIC, &t0);
madvise(p, len, MADV_DONTNEED);
clock_gettime(CLOCK_MONOTONIC, &t1);

munmap(p, len);
```

扫描点与阶段 1 相同：

```text
N = 256, 512, 1024, 2048, 4096, 8192, 16384(可选)
```

这组实验不需要证明内核源码里一定发了 range TLBI。它只回答行为问题：多页 batched teardown 是否仍表现为 per-entry protected 线性成本。

配对判读：

| single-page `delta_slope` | batched `delta_slope` | 解释 |
|---:|---:|---|
| 明显为正 | 接近 0 | per-entry 成本存在，但真实多页路径在行为上隐藏了它；结合 TLB Range Flush metadata，range TLBI 是最合理解释 |
| 接近 0 | 接近 0 | Tensor G4 entry invalidation 本身便宜，至少在本实验上界内便宜 |
| 明显为正 | 也明显为正 | 多页路径没有有效隐藏成本，Pixel 仍可能存在 Phytium 类 teardown 问题 |
| 明显为正 | 较小但非零 | 有批量缓解，但仍有剩余 protected 成本 |

为了排除 no-op，batched 也应加 untouched 对照。若 touched batched 与 untouched batched 都接近，说明大范围 `MADV_DONTNEED` 的实际页清理可能没有按预期发生，需要检查预触摸和 page-fault 计数。

---

## 6. 阶段 3：真实 workload 复现记录

阶段 3 保留 `lat_mmap` 与生命周期拆分，但它们不再是 Pixel 机制结论的主证据，而是用于回答“真实 lmbench 形态是否受影响”。

### 6.1 原始 `lat_mmap_precise`

| 参数 | 设置 |
|---|---|
| 映射类型 | `MAP_SHARED` 文件映射 |
| 后备文件 | 预分配、预填充，优先 tmpfs |
| 映射尺寸 | `0.5, 1, 2, 4, 8, 16, 64 MB` |
| 触摸范围 | 起始 `size / 10` |
| 触摸步长 | `16 KB` |
| 计时范围 | `mmap + write touch + munmap` 完整生命周期 |
| 轮次 | 每 size 每 boot 10 轮；64 MB 可加到 30 轮 |

图形：

1. `lat_mmap` 绝对延迟：横轴按真实 size 比例，纵轴为 us/iteration。
2. protected 相对 nvhe 的差值或百分比：横轴可按类别均匀排布，便于看小尺寸。

### 6.2 生命周期拆分

| 子测试 | 内容 | 目的 |
|---|---|---|
| `mmap_unmap` | 建立映射后立即 `munmap`，不触摸 | VMA 建删成本 |
| `write_touch_cold` | `mmap` 后写触摸，不计 `munmap` | 首次缺页、建 PTE、写页成本 |
| `munmap_after_no_touch` | 未触摸映射的 `munmap` | 无页表项拆除成本 |
| `munmap_after_write_touch` | 写触摸后只计 `munmap` | 与 Phytium 主因路径对齐 |
| `mmap_write_touch_unmap` | 完整生命周期 | 与 `lat_mmap_precise` 对账 |

判读：

| 结果 | 含义 |
|---|---|
| 真实 workload 无 gap，而阶段 1 single-page 有 gap | Pixel per-entry 成本存在，但真实批量路径隐藏了它 |
| 真实 workload 与阶段 1 都无 gap | Tensor G4 在本实验范围内没有可解析 pKVM teardown 成本 |
| 真实 workload 有 gap，但阶段 1 无 per-entry slope | 机制可能不是 entry invalidation，需要另查文件页、page fault 或 Android 环境 |

---

## 7. 阶段 4：2 MB 阈值扫描，作为指纹检查

阶段 4 保留 Phytium 风格的 2 MB 阈值扫描，但定位降级为 fingerprint check。Pixel 若支持并使用批量 TLB 维护，预期不应出现 Phytium 那种 2 MB 以下 slot-linear protected gap 与 2 MB 附近断崖。

### 7.1 dense 扫描

只计写触摸后的 teardown：

| 参数 | 设置 |
|---|---|
| 映射类型 | anonymous 主测；file-backed 可选 |
| 触摸方式 | 从起始地址开始，按 `4 KB` 步长连续写 |
| teardown 操作 | `munmap` 或 batched `MADV_DONTNEED`，二者至少选一，优先 `MADV_DONTNEED` 与阶段 2 对齐 |
| 扫描范围 | `0.25, 0.5, 1, 1.5, 1.75, 1.9, 1.95, 2.0, 2.05, 2.1, 2.5, 4, 8, 16, 64 MB` |
| 轮次 | 2 MB 附近点每 boot 30 轮，其余 10 轮 |

### 7.2 sparse 参考点

sparse 参考点复刻 lmbench 的稀疏触摸形态：

| 参数 | 设置 |
|---|---|
| 映射尺寸 | 64 MB |
| 触摸跨度 | 起始 6.4 MB |
| 触摸步长 | 16 KB |
| 计时范围 | 只计写触摸后的 teardown |

这里的“6.4 MB”来自原始 `lat_mmap` 的 `size / 10`，即 64 MB 映射只触摸起始 6.4 MB 地址跨度；16 KB 步长意味着不是连续触摸每个页，而是每 16 KB 写一次。

判读：

| 现象 | 解释 |
|---|---|
| 2 MB 以下不出现 protected slot-linear gap | 与阶段 2 的 batched 缓解相容 |
| 2 MB 附近没有 protected 特有断崖 | 不复现 Phytium 无 range 平台的阈值指纹 |
| sparse 参考点也不偏离 | 原始 lmbench 形态同样被缓解 |
| 仍出现 2 MB 以下线性 gap 和 2 MB 断崖 | Pixel 行为上仍像无 range 平台，需怀疑批量路径未生效或测试实际走了不同路径 |

建议图形：

1. dense 绝对延迟：完整范围 + 0 到 2.5 MB 细节子图。
2. dense protected−nvhe 差值：完整范围 + 0 到 2.5 MB 细节子图。
3. sparse 参考点用单独标记，不参与 dense 线性拟合。

---

## 8. 阶段 5：操作谱系

阶段 5 检验结论是否仅限 `MADV_DONTNEED`，还是 teardown / TLB maintenance 类操作都有类似行为。

| 操作 | 设计 | 优先级 |
|---|---|---|
| `MADV_DONTNEED` | single-page slope + batched slope | 主线 |
| `munmap` | dense + sparse，anonymous + file-backed | 真实 `lat_mmap` 相关 |
| `mprotect` | 连续小范围与大范围权限切换 | 可选；VMA split/merge 可能污染，不作为主证据 |

`mprotect` 不建议作为 per-entry 主实验，因为单页权限切换容易制造 VMA split/merge 成本。若要做，应把它放在操作谱系中，用于观察趋势，而不是用于拟合 entry invalidation 单价。

每类操作至少选择以下尺寸：

```text
0.5 MB, 1 MB, 1.5 MB, 1.9 MB, 2.0 MB, 2.1 MB, 4 MB, 8 MB, 64 MB
```

工具复用：

| 阶段 | 工具 |
|---|---|
| per-entry single/batched MADV slope | `experiments/munmap-tlbi/pixel_madv_entry_slope.c` + `pixel-run-madv-entry-slope.sh`，覆盖 touched/untouched、single/batched、N sweep、任务随机化、频率/温度记录 |
| slope/DiD/解析下限 | `experiments/munmap-tlbi/pixel-analyze-madv-entry-slope.py` |
| dense/sparse 阈值扫描 | 复用 `experiments/munmap-tlbi/munmap_only.c` 或 `experiments/munmap-tlbi/op_sweep.c` |
| 操作谱系 | 复用 `experiments/munmap-tlbi/op_sweep.c`，它已经覆盖 `munmap` / `dontneed` / `mprotect` 与 file/anon 模式 |
| anon/file/hugepage 对照 | 复用 `experiments/munmap-tlbi/munmap_only.c` 中的 `file` / `anon_base` / `anon_huge` 模式 |

判读：

| 结果 | 含义 |
|---|---|
| `MADV_DONTNEED` single-page 有 gap，batched/munmap 无 gap | per-entry 成本存在，但真实批量 teardown 路径隐藏 |
| 三类操作都无稳定 protected gap | Pixel 在可测范围内没有 Phytium 类 teardown 问题 |
| 多类操作在 `<2 MB` 下都有类似 gap | 支持 TLBI maintenance 仍是通用成本 |
| 只有 `mprotect` 有 gap | 优先怀疑 VMA 管理或权限变更路径，而不是直接归因到 TLBI |

---

## 9. 统计与判定标准

实验前应预先固定判据，避免事后挑选数据。

### 9.1 主估计器：DiD per-entry slope

主实验使用线性拟合，而不是只比较单点：

```text
T_mode(N) = intercept_mode + slope_mode * N
```

对每个 boot pair 分别计算：

```text
s_touched_prot
s_touched_nvhe
s_untouched_prot
s_untouched_nvhe

raw_delta      = s_touched_prot   - s_touched_nvhe
drift_delta    = s_untouched_prot - s_untouched_nvhe
per_entry_cost = raw_delta - drift_delta
```

其中 `per_entry_cost` 是 headline 数字，单位为 ns/op。`raw_delta` 是未校正的 protected−nvhe touched 差值；`drift_delta` 是同一 boot pair 中空路径测到的系统漂移。最终报告应同时列出三者，避免把 boot-to-boot 漂移误当成 TLBI 成本。

建议报告：

```text
s_touched_nvhe_ns_per_op
s_touched_protected_ns_per_op
s_untouched_nvhe_ns_per_op
s_untouched_protected_ns_per_op
raw_delta_ns_per_op
drift_delta_ns_per_op
per_entry_cost_did_ns_per_op
95% CI 或 bootstrap CI
R^2
residual summary
```

### 9.2 解析下限：minimum detectable delta_slope

null 结果只有在解析下限足够低时才有意义。实验前应先用一个 pilot sweep 估计当前协议能解析的最小 per-entry 成本；正式报告也必须给出最终解析下限。

建议流程：

1. 用阶段 1 的 touched / untouched single-page sweep 跑至少 2 个 boot pair，N 点覆盖 `256..8192`，每点至少 30 runs。
2. 对每个 boot pair 计算 `raw_delta`、`drift_delta` 和 `per_entry_cost`。
3. 用 bootstrap 或 boot-pair 级 MAD 估计 `per_entry_cost` 的 95% CI 半宽。
4. 同时记录 untouched `drift_delta` 的分布，因为它直接表示 common-mode syscall/VMA 路径在跨 boot A/B 中的漂移。
5. 预先写下本轮实验的解析下限：

```text
resolution_floor_ns_per_op =
    max(half_width_95CI(per_entry_cost),
        half_width_95CI(drift_delta),
        abs(median(drift_delta)))
```

如果 `per_entry_cost` 的点估计低于这个 floor，只能报告：

```text
Pixel per-entry protected cost is below <floor> ns/op under this protocol.
```

不能写成“没有 per-entry 成本”。目标上，若 floor 能压到约 `<= 50 ns/op`，则可以有意义地区分“Phytium 级数百 ns/op 成本”和“Tensor G4 上很小的剩余成本”；若 floor 高于 `100 ns/op`，应增加 boot pair、runs、冷却间隔，或改用更稳定 core。

### 9.3 slope 质量与线性判据

斜率模型的质量必须随结果一起报告：

```text
R^2
residual plot
per-N median/mean/MAD
fit range sensitivity, e.g. 256..8192 vs 512..4096
```

若残差随 N 单调弯曲，优先检查热爬升、频率下降、预触摸造成的 cache/TLB 状态变化，以及 N 点执行顺序是否随机化。此时可报告分段斜率，但不能只挑选最符合预期的 N 区间作为主结果。

### 9.4 结论判据

| 结论 | 判据 |
|---|---|
| per-entry 成本存在 | DiD 后的 `per_entry_cost` 稳定为正，且超过 `resolution_floor_ns_per_op` |
| per-entry 成本低于可解析上界 | DiD 后的 `per_entry_cost` 接近 0，且 95% CI / resolution floor 足够窄 |
| 批量路径隐藏成本 | single-page DiD 明显为正，batched DiD 接近 0 |
| Pixel 复现 Phytium 式行为 | single-page 与真实 workload 均有 slot-linear gap，并且阈值扫描出现 Phytium 式指纹 |
| 机制不同 | 有稳定 gap，但不满足 single-page/batched/threshold 的配对关系 |

### 9.5 原始 workload 判据

| 结论 | 判据 |
|---|---|
| 有真实 workload 退化 | protected−nvhe 同方向出现在多数 boot pair；差距大于 `max(5%, 3 * 噪声MAD)`；`simpleperf` cycles/stall 同向 |
| 无可解析 workload 退化 | 差距小于噪声阈值，或不同 boot 间方向不稳定 |
| 被批量路径缓解 | 原始 `lat_mmap`、生命周期拆分、阈值扫描、操作谱系都不再出现 slot-linear protected gap，但 single-page slope 显示 per-entry 成本存在 |

所有 summary 表至少包含：

```text
mode, boot_id, cpu, workload, mapping_type, operation, n_pages,
size_mb, touch_span_mb, stride_kb, runs,
median_us, mean_us, mad_us, mad_pct, temp_before, temp_after,
freq_before_khz, freq_after_khz, reject_reason
```

DiD summary 至少包含：

```text
boot_pair_id, cpu, n_min, n_max, fit_range,
s_touched_nvhe_ns_per_op, s_touched_protected_ns_per_op,
s_untouched_nvhe_ns_per_op, s_untouched_protected_ns_per_op,
raw_delta_ns_per_op, drift_delta_ns_per_op,
per_entry_cost_did_ns_per_op, ci95_low, ci95_high,
resolution_floor_ns_per_op, r2_touched_nvhe, r2_touched_protected,
r2_untouched_nvhe, r2_untouched_protected
```

用 runner 合并 CSV 直接分析一个 boot pair：

```bash
python3 experiments/munmap-tlbi/pixel-analyze-madv-entry-slope.py \
  --boot-pair-id pair01 \
  --nvhe-csv experiments/munmap-tlbi/results/pixel-madv-entry-nvhe-boot01/raw/nvhe_madv_entry.csv \
  --protected-csv experiments/munmap-tlbi/results/pixel-madv-entry-protected-boot01/raw/protected_madv_entry.csv \
  --probe-mode single
```

如果要分析 batched 路径，把 `--probe-mode single` 改为 `--probe-mode batched`。

对多个 boot pair 的 DiD 结果做最终汇总：

```bash
python3 experiments/munmap-tlbi/pixel-summarize-madv-entry-slope.py \
  --label single \
  --input experiments/munmap-tlbi/results/pixel-madv-entry-pair01-single.csv \
  --input experiments/munmap-tlbi/results/pixel-madv-entry-pair02-single.csv \
  --input experiments/munmap-tlbi/results/pixel-madv-entry-pair03-single.csv \
  --input experiments/munmap-tlbi/results/pixel-madv-entry-pair04-single.csv \
  > experiments/munmap-tlbi/results/pixel-madv-entry-single-summary.csv
```

汇总脚本输出的 `resolution_floor_ns_per_op` 是报告 null 结果时的上界依据。它取以下三者的最大值：`per_entry_cost` 的 95% CI 半宽、`drift_delta` 的 95% CI 半宽、以及 `|median(drift_delta)|`。因此如果 `per_entry_cost` 没超过这个 floor，结论应写成“低于该协议下的 X ns/op 上界”。

`simpleperf` summary 至少包含：

```text
mode, boot_id, cpu, workload, n_pages, event, count, count_per_iter
```

---

## 10. 结果目录建议

推荐把一次完整 Pixel 实验放在独立目录：

```text
experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-YYYYMMDD/
  metadata/
    protected-boot01.txt
    nvhe-boot01.txt
  raw/
    protected/boot01/*.csv
    nvhe/boot01/*.csv
  simpleperf/
    protected/boot01/*.txt
    nvhe/boot01/*.txt
  summary/
    madv_single_page_slope.csv
    madv_did_summary.csv
    madv_power_floor.csv
    madv_batched_slope.csv
    madv_untouched_control.csv
    lat_mmap_summary.csv
    mmap_split_summary.csv
    threshold_scan_summary.csv
    op_sweep_summary.csv
    simpleperf_summary.csv
  figures/
    madv_single_page_slope.svg
    madv_single_page_delta_slope.svg
    madv_did_ci.svg
    madv_power_floor.svg
    madv_batched_slope.svg
    madv_single_vs_batched.svg
    lat_mmap_absolute.svg
    lat_mmap_delta.svg
    mmap_split_64mb.svg
    threshold_scan_absolute.svg
    threshold_scan_delta.svg
    op_sweep_heatmap.svg
    simpleperf_cost_layering.svg
  README.md
```

`README.md` 应记录：

1. 设备型号、AOSP build、kernel build、boot 参数。
2. `nvhe` / `protected` 模式确认方式。
3. TLB Range Flush 相关 metadata；若无法确认，应明确写明。
4. CPU 选择、频率、温度控制方式。
5. benchmark 二进制来源和 hash。
6. 每个阶段的命令行。
7. pilot 得到的 `resolution_floor_ns_per_op`，以及 null 结果的上界写法。
8. 原始数据与图的生成脚本。
9. 最终判读与异常点说明。

---

## 11. 最小闭环

若设备时间有限，最小闭环按以下顺序执行：

1. 阶段 0：metadata、KVM 模式确认、噪声基线。
2. 先跑 2 个 boot pair 的 pilot：touched + untouched single-page `MADV_DONTNEED` slope，`N=256..8192`，估计 `resolution_floor_ns_per_op`。
3. 若解析下限过高，先调整 core、冷却、runs 或 boot pair 数；若可接受，再进入完整实验。
4. 阶段 1：完整 touched single-page `MADV_DONTNEED` slope。
5. 阶段 1：完整 untouched single-page `MADV_DONTNEED` slope，并计算 DiD `per_entry_cost`。
6. 阶段 2：touched + untouched batched `MADV_DONTNEED(base, N*4KB)` slope。
7. 阶段 1/2：对 `N=4096` 或 `8192` 关键点跑 `simpleperf stat`，作为 setup 公平性与 cycles/stall 佐证。
8. 阶段 3：原始 `lat_mmap_precise` 64 MB 和生命周期拆分 64 MB。
9. 阶段 4：dense 阈值扫描，至少 `1.9 / 2.0 / 2.1 MB` 与 64 MB sparse 参考点。

这些步骤不需要改内核，也不需要 Pixel 源码。它们能回答最重要的问题：

> Pixel protected 下是否存在可测的 per-entry teardown 成本；如果存在，真实多页 teardown 是否在行为上把它隐藏掉；如果不存在，Tensor G4 的 combined-entry invalidation 成本上界是多少。

---

## 12. 后续可选增强

若后续具备更高权限、源码或内核构建能力，可再增加三类增强实验：

1. **源码确认**：阅读 Pixel 对应 GKI 的 `madvise` / `zap_page_range` / `__flush_tlb_range()` 路径，确认 batched teardown 是否命中 `ARM64_HAS_TLB_RANGE` 分支。
2. **直接 TLBI 微基准**：在内核模块或内建测试中直接计时单页 TLBI 与 range TLBI，区分“单条 TLBI 是否仍更贵”和“真实 teardown 是否因 range TLBI 减少条数而不慢”。
3. **禁用 range TLBI 的同机对照**：在同一 Pixel 内核中人为让 `system_supports_tlb_range()` 为假，再重复阈值扫描。若 range-off 后重现 2 MB 阈值和 protected slot-linear gap，则可强力证明 FEAT_TLBIRANGE 是关键缓解因素。

这些增强项不是本方案的前提。当前方案默认不改内核、不依赖源码，先用用户态黑盒行为实验完成主要判断。
