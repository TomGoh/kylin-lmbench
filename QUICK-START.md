# Quick Start：N90 复现 4-mode KVM 性能对照

按这份 cookbook 走一遍，**~8 小时**端到端拿到跟 `lmbench-N10-4config.xlsx` 同结构的最终表格 + ns 精度 lat_mmap 数据。

```
build 机器 (任意 Linux)       N90 (Phytium FTC862 + KylinOS V11)
─────────────────────         ───────────────────────────────────
make build                    ← rsync 推过去 ─→
                                                  reboot × 4 mode
                                                  ./bench.sh × 4
                                                  lat_mmap_precise × 4
                              ← rsync 拉回来 ─    
python3 scripts/build-xlsx-median.py
                                ↓
                  lmbench-N10-4config.xlsx
```

> 不是要 paper-grade 而只想 smoke test？跳到 §4，用 `CONFIG=configs/CONFIG.test` 替代 `CONFIG.host`，单 mode ≈ 90 秒。

---

## 0. 你需要什么

| | 最低要求 |
|---|---|
| **build 机器** | 任意 Linux，gcc + make + python3 ≥ 3.8 + openpyxl + perl，能 ssh 到 N90 |
| **N90 (target)** | Phytium FTC862（D3000M 等价），KylinOS V11，kernel 6.6.0-73-generic（含 pKVM 内置），ostree 部署 |
| **网络** | build 机器 → N90 SSH 可达；建议 NOPASSWD sudo |
| **磁盘** | N90 至少 5 GB 空闲（/tmp 要放 64 MB backing file + 80 个 iter txt log） |

```bash
# build 机器 dependencies
sudo apt install build-essential libtirpc-dev rpcbind python3 python3-openpyxl perl rsync
```

---

## 1. 在 build 机器上拿仓库

```bash
git clone <this-repo> lmbench-3.0-a9
cd lmbench-3.0-a9
make build                              # ~30 秒，产出 bin/aarch64-Linux/* 或 x86_64
```

> ⚠️ 如果在 x86 build 机器上编出来的是 x86 binary，N90 跑不动——需要在 N90 上重编（看 §3）。

---

## 2. 把 repo 推到 N90

```bash
# 在 build 机器上
N90=kylin@10.x.x.x
rsync -av --exclude='bin/' --exclude='results/' . ${N90}:/root/lmbench-3.0-a9/
ssh ${N90} 'cd /root/lmbench-3.0-a9 && sudo make build'   # aarch64 binary on target
```

> N90 上仓库放 `/root/lmbench-3.0-a9/`（不放 `/home/kylin/`——历史教训：`/home` 在某次 reboot 后整层不见）。

---

## 3. 一次性环境固化（在 N90 上跑一次就够）

```bash
ssh ${N90}

# 3.1 让 ostree set-kargs 成为 cmdline 唯一权威
sudo cp /etc/default/grub /etc/default/grub.bak
sudo sed -i 's|^GRUB_CMDLINE_LINUX_SECURITY=.*|GRUB_CMDLINE_LINUX_SECURITY=""|' /etc/default/grub
sudo update-grub

# 3.2 mask 84 个噪声 systemd 服务（持久化，跨 reboot）
sudo bash scripts/apply-masks.sh
#  ⚠️ 这个脚本会保留 NetworkManager（KylinOS 桌面网络由 NM 管理；stop 它 = SSH 掉线）

# 3.3 NOPASSWD sudo（一次性，方便自动化 reboot）
echo "kylin ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/kylin-bench
```

注意：
- 改 `GRUB_CMDLINE_LINUX_SECURITY` 是因为 ostree-Kylin 的 grub 模板会拼这个变量到 cmdline 末尾，不清空的话 `ostree set-kargs` 改不动它的 `security=box`，cmdline 就两套互斥
- `apply-masks.sh` 是 idempotent 的——可以重复跑，已 mask 的不再重复 mask

---

## 4. 4-mode 循环跑 lmbench（核心循环）

`bench.sh` 一次跑 1 个 mode × N=10 iter，每 iter ~10 min（CONFIG.host 全套）。**4 mode × 100 min ≈ 7 h**。

```bash
# 在 N90 上手动循环：
for mode in none vhe nvhe protected; do
  # ostree set-kargs 切换 kvm-arm.mode
  sudo ostree admin instutil set-kargs --merge \
    --replace=kvm-arm.mode=${mode}
  
  # reboot 进新 mode
  sudo systemd-run --on-active=2s --unit=delayed-reboot systemctl reboot
done
```

但因为 reboot 要等 SSH 重连、且每次 reboot 后要重做 prepare-host，**实际人工 driver** 大概是：

```bash
# Iteration 模板（每 mode 重复一次，从 build 机器 ssh 控制）：

# Step A. 切 mode + reboot
ssh ${N90} 'sudo ostree admin instutil set-kargs --merge --replace=kvm-arm.mode=vhe \
            && sudo systemd-run --on-active=2s --unit=delayed-reboot systemctl reboot'

# Step B. 等 ~70 秒 + ping 确认起来 + verify mode
sleep 65
ssh ${N90} 'cat /proc/cmdline | grep -oE "kvm-arm.mode=[a-z]+"'
ssh ${N90} 'sudo dmesg | grep -iE "VHE|kvm.*initialized|Protected nVHE"'

# Step C. 重做 prep（cpufreq 锁 + THP + ASLR + mask）
ssh ${N90} 'sudo bash /root/lmbench-3.0-a9/scripts/apply-masks.sh'
ssh ${N90} 'sudo bash /root/lmbench-3.0-a9/prepare-host.sh'

# Step D. 跑 bench（~100 min）
ssh ${N90} 'cd /root/lmbench-3.0-a9 && \
            CORES=0 ITERS=10 CONFIG=configs/CONFIG.host \
            ENV_TAG=n90-vhe-noLSM-full ./bench.sh --no-prep'
```

每跑完 1 个 mode，N90 上 `results/` 会多出：
```
results/n90-vhe-noLSM-full-cpu0.csv               # 解析后长表 CSV
results/n90-vhe-noLSM-full-cpu0-iter{1..10}.txt   # 10 个 raw lmbench 报告
results/n90-vhe-noLSM-full-<timestamp>-summary.txt
```

注意：
- `--no-prep` 表示 bench.sh 不再 force 跑 prepare-host.sh（我们手动跑过了）
- `ENV_TAG` 决定输出文件 prefix，4 mode 必须用不同 tag（kvmoff / vhe / nvhe / pkvm 等）
- 默认每个 mode 跑**一次**就够；只有 §8.3 那种 sanity check 失败（pkvm `lat_mem_rd_rand` 看上去比 non-pkvm 快、或 MAD% 突然大于 5%）才需要复测一遍打 `-try2` tag 对照

---

## 5. ns 精度 lat_mmap 复测（每 mode 加跑 ~3 分钟）

lmbench 自带的 `lat_mmap` 在 size ≥ 1 MB 时输出整数 µs，看不到 < 0.5 µs 的差异。我们写了 `lat_mmap_precise.c` 解决：

```bash
# 在 build 机器上推到 N90 一次：
rsync -av src/lat_mmap_precise.c scripts/precise-mmap-bench.sh \
          ${N90}:/root/lmbench-3.0-a9/{src,scripts}/

# N90 上编译：
ssh ${N90} 'cd /root/lmbench-3.0-a9 && \
            sudo gcc -O2 -o bin/aarch64-Linux/lat_mmap_precise src/lat_mmap_precise.c'

# 每个 mode 跑一遍（在已 reboot 进对应 mode 之后、§4 跑完 bench 之后）：
ssh ${N90} 'sudo bash /root/lmbench-3.0-a9/scripts/precise-mmap-bench.sh vhe'
# → results/precise-mmap/vhe.log
```

输出格式（每行 1 iter）：
```
size_mb=1 iters=8000 total_ns=118622081 per_iter_ns=14827.760 per_iter_us=14.827760
```

---

## 6. 把数据拉回 build 机器

```bash
# 在 build 机器上
rsync -av ${N90}:/root/lmbench-3.0-a9/results/ ./results/
```

---

## 7. 生成 xlsx

```bash
# Median + MAD% 版（默认）
python3 scripts/build-xlsx-median.py
# → docs/n90-kvm-host/lmbench-N10-4config.xlsx

# Mean + RSD% 版
python3 scripts/build-xlsx-mean.py
# → docs/n90-kvm-host/lmbench-N10-4config-mean.xlsx
```

两个脚本都会**自动 chain** `update-xlsx-precise-mmap.py`，把 `results/precise-mmap/*.log` 的 ns 精度 lat_mmap 数据覆盖到 xlsx 的对应行（不是手动一步）。

xlsx 4 个 sheet：
- **Highlights**——论文表 32+ 项 + Δ% 5 列
- **All metrics**——684 项指标全表
- **Per-iter raw**——关键指标 10 iter × 4 mode 原始单值
- **README**——简要说明

---

## 8. 三个常见 hicup + 排查

### 8.1 SSH 重连后 cmdline 不对

```bash
ssh ${N90} 'cat /proc/cmdline | grep -oE "kvm-arm.mode=[a-z]+"'
```

如果跟期望不符：

```bash
# 看 ostree 当前 deployment 的 kargs：
ssh ${N90} 'cat /boot/loader/entries/ostree-2.conf | grep -oE "kvm-arm.mode=[a-z]+"'
# 如果这里也不对，说明 set-kargs 没生效——重跑
```

### 8.2 bench.sh 中途崩溃

```bash
# 看最后那个 iter 的 raw txt 有没有 "memory exhausted" / "OOM"
ssh ${N90} 'tail -50 /root/lmbench-3.0-a9/results/n90-*-cpu0-iter10.txt'

# CPU freq 没锁住？
ssh ${N90} 'cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'   # 期望 1900000
ssh ${N90} 'cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'    # 期望 performance

# THP 没关？
ssh ${N90} 'cat /sys/kernel/mm/transparent_hugepage/enabled'  # 期望 [never]
```

### 8.3 看到反常 finding 时（什么时候需要复测）

跑完后做几个 sanity check：

```bash
# pkvm 的 lat_mem_rd_rand 64MB 应该跟 non-pkvm 同量级（差 ±10% 内）；
# 如果看到 pkvm "比 non-pkvm 快 17-33%"，就是 stochastic outlier
# （我们这个 paper 就在 try1 翻车过）。
awk -F, '$4=="lat_mem_rd_rand" && $5=="stride16_sz64.00000MB"' \
    results/n90-pkvm-noLSM-full-cpu0.csv | \
  awk -F, '{sum+=$6; n++} END {print "pkvm median ~", sum/n}'
# 跟 vhe 同 metric 一比，差 > 10% 就触发复测

# MAD% 突然 > 5%：环境有噪声没钳死，检查 §8.2 + apply-masks 是否漏 service

# null syscall 跨 mode 差 > 2%：不正常，重做 prepare-host
```

触发条件满足时，**同 cmdline reboot 重跑一次** 同 mode（输出文件名加 `-try2`），对比两次数据：如果差异 < 1%，新数据可信；如果两次都异常，深究噪声源（systemd 服务、cpufreq 漂移、TLB 污染）。详见 `standalone-memory-bench-validation.md` 的 try1/try2 反例分析。

---

## 9. 总耗时拆解

| 阶段 | 耗时 |
|---|---|
| §1 build lmbench | 30 秒 |
| §2 rsync + 在 N90 编 aarch64 binary | 1 分钟 |
| §3 一次性环境固化 | 5 分钟 |
| §4 4-mode × 100 min × N=10 | ~7 小时（含 4 次 reboot + verify 间隙）|
| §5 4-mode × precise-mmap (~3 min) | ~12 分钟 |
| §6 rsync 数据回来 | 30 秒 |
| §7 build xlsx | 30 秒 |
| **首次端到端** | **~7.5 小时** |
| 加 1 次 pkvm 复测（若 §8.3 触发）| +100 分钟 |

---

## 10. 验证你拿到的数据跟我们一致

跑完后 sanity-check 几个 paper 级 finding：

```bash
# 1. lat_mmap pkvm 64 MB 应该 ~709 µs（precise log）
grep "size=64 MB" results/precise-mmap/pkvm.log | head -1
# expected: size_mb=64 ... per_iter_us=~709

# 2. CPU 算术应该 4 mode 一字不差
python3 -c "
import csv, statistics as st
for mode in ['kvmoff','nvhe','vhe','pkvm']:
    # ENV_TAG 对应改，例如 'n90-pkvm-noLSM-try2' 之类
    pass
# 或直接看 xlsx Highlights row 9 (intgr add) 4 mode 应该全是 0.28
"

# 3. null syscall 4 mode 应该差 ≤ 0.001 µs
# xlsx Highlights row 3 应该都是 ~0.1028
```

详细的"应该看到什么"清单见 `FINAL-REPORT.md §6`（6 个 finding）。

---

## 相关文档

- **机制深读**：[`docs/n90-kvm-host/FINAL-REPORT.md`](docs/n90-kvm-host/FINAL-REPORT.md)（独立可读，11 章，~33 KB）
- **6 finding 综合**：[`docs/n90-kvm-host/SUMMARY.md`](docs/n90-kvm-host/SUMMARY.md)
- **方法论 + 噪声控制**：[`docs/n90-kvm-host/README.md`](docs/n90-kvm-host/README.md)
- **pkvm mmap +42% 代码级机制**：[`docs/n90-kvm-host/pkvm-mmap-overhead-analysis.md`](docs/n90-kvm-host/pkvm-mmap-overhead-analysis.md)
- **stochastic outlier 反例**：[`docs/n90-kvm-host/standalone-memory-bench-validation.md`](docs/n90-kvm-host/standalone-memory-bench-validation.md)
