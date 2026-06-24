# 从零开始：在 Kaitian 上构建匹配 perf 并用 perf 复查 pKVM mmap 退化

| | |
|---|---|
| 日期 | 2026-06-24 |
| 目标板卡 | Kaitian，Phytium FTC862，Kylin V10 SP1 |
| 当前内核 | `6.6.30-pkvm-clean` |
| 内核源码 | Kaitian 本地 `/home/test/common`，HEAD 为 `da966ce9a047bedffb02e0bdc87f3ccb5fb3f9d9` |
| perf 来源 | `/home/test/common/tools/perf` |
| 复查代码 | Kaitian 本地 `~/kylin-lmbench` |
| 最终结论 | 在 Kaitian 上，pKVM `lat_mmap` 退化已用 stock perf 复现：成本来自低于 2 MB teardown 中逐页 TLBI 的 host stage-2 硬件税，不在 EL2，也不是更多页表 walk |

本文是一篇**独立手册**。读者无需阅读其他文档，也无需知道原始调查历史。它从一块已经能启动 pKVM/nvhe 的 Kaitian 板卡开始，按顺序说明：

1. 为什么要在 `common` 仓库中编译与当前内核匹配的 perf。
2. 如何在 Kaitian 上完成这个 perf 构建。
3. 如何准备 `kylin-lmbench` 中的 microbench 和复查目录。
4. 如何仅用 perf 与标准 sysfs/userspace 控制，从零调查 pKVM `mmap` 退化。
5. 如何根据数据判断：成本是否在 EL2、是否来自更多 walk、是否是 2 MB 以下逐页 TLBI 的 per-slot 成本、是否随核数 broadcast。

本文不会要求修改 `common` 内核源码，也不要求打 hypervisor 补丁。唯一需要写入系统路径的是安装编译依赖、安装 `libtraceevent/libtracefs`，以及把新编出的 perf 链接到 `/usr/local/bin/perf`。

---

## 1. 调查问题是什么

`lat_mmap` 这类测试不是单纯测内存读写吞吐，而是测一个映射生命周期：创建映射、触摸部分页面、再解除映射。pKVM 下 host 侧存在 host stage-2，解除映射时的页表清理和 TLB invalidation 可能比 nvhe 更贵。因此，正确的问题不是“pKVM 是否让所有内存访问都变慢”，而是：

- `lat_mmap` 的 protected 与 nvhe 差距是否真实存在？
- 差距是在 mmap 建立、first-touch fault，还是 munmap teardown？
- teardown 的额外时间是否花在 EL2/hypervisor？
- protected 是否做了更多 page-table walk，还是做同样工作但每步更慢？
- 成本是否与 2 MB 以下逐页 TLBI 数量成正比？
- 成本是否随 online core 数量增长，即是否来自跨核 broadcast/shootdown 等待？

本手册用 perf 逐步回答这些问题。核心对照是 **protected vs nvhe**：

- `protected`：host stage-2 开启，是 pKVM 模式。
- `nvhe`：没有 host stage-2，是隔离 host-stage-2 成本的对照组。

如果 protected 比 nvhe 多出的成本只在 teardown 出现，并且 `cycles:h=0`、walk 计数相同、backend stall 增长、gap 在 2 MB 阈值处断崖消失，那么结论就是：成本不是 EL2 执行时间，也不是更多 walk，而是低于 2 MB 范围内逐页 TLBI 在 host stage-2 存在时更慢。

---

## 2. 为什么第一步是编译匹配当前内核的 perf

Kylin V10 SP1 仓库里的 perf 面向发行版 5.4.18 内核，而 Kaitian 当前运行的是 `6.6.30-pkvm-clean`。普通硬件计数依赖稳定的 `perf_event_open` ABI，跨版本往往还能跑；但这次复查依赖的不是普通 `cycles` 一项：

- 要用 `cycles:h` 判断 EL2/hyp 是否消耗时间。
- 要用 FTC862 的 raw event，例如 `r0024`（backend stall）和 `r0034`（DTLB walk）。
- 要确认 `stall_backend`、`l2d_tlb_refill` 等事件名是否在当前 perf 构建中暴露。
- 要让 perf 的 PMU event table 与当前 6.6.30 内核来源一致。

因此，必须在 Kaitian 上基于当前内核对应的 `common` 仓库编译 perf：

```text
/home/test/common/tools/perf
```

构建完成后统一使用：

```text
/usr/local/bin/perf
```

后续所有脚本也假定 perf 位于这个路径。不要混用 `/usr/bin/perf`，否则事件名、`:h` 修饰符或 raw event 解释可能与当前内核不一致。

---

## 3. 确认 Kaitian 与 `common` 仓库状态

先登录 Kaitian。本文后续所有命令都默认在 Kaitian 板卡上执行：

```bash
ssh Kaitian
```

确认运行内核、启动模式和 `common` 仓库提交：

```bash
uname -r
cat /proc/cmdline
cd /home/test/common
git rev-parse HEAD
test -d tools/perf && echo "tools/perf exists"
```

本次复查对应状态是：

```text
kernel: 6.6.30-pkvm-clean
cmdline: contains kvm-arm.mode=protected or kvm-arm.mode=nvhe
common HEAD: da966ce9a047bedffb02e0bdc87f3ccb5fb3f9d9
```

如果 `/home/test/common` 不存在，应先把与当前运行内核对应的 `common` 工作树放到该路径。关键不是路径本身，而是 **`common/tools/perf` 必须来自当前运行内核对应的源码树**。如果内核换了提交，perf 也要重新编译。

先放开 perf 计数权限：

```bash
sudo sysctl -w kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0
```

这两个设置重启后会恢复默认值。每次重新启动 protected/nvhe 后，都要重新设置。

---

## 4. 在 Kaitian 上编译匹配内核的 perf

### 4.1 安装 Kylin 仓库中的基础依赖

`common/tools/perf` 会根据系统上存在的库决定启用哪些功能。本次需要一个功能完整的 perf，因此先安装 Kylin 仓库里可用的开发包：

```bash
sudo apt-get install -y \
  flex bison pkg-config zlib1g-dev libelf-dev libdw-dev libunwind-dev \
  libcap-dev libzstd-dev liblzma-dev \
  python3-dev libperl-dev libslang2-dev systemtap-sdt-dev libnuma-dev \
  libbabeltrace-dev binutils-dev libpfm4-dev libssl-dev libaio-dev libiberty-dev
```

其中 `python3-dev` 很关键。缺它时，perf 构建会在 `jevents` 或 `python3-config` 处失败：

```text
Makefile.config:881: *** ERROR: No python interpreter needed for jevents generation.
Makefile.config:285: *** /usr/bin/python3-config not found.
```

后面编译 perf 时会显式传入 `PYTHON=python3`，避免 perf 的自动探测在这块板卡上找不到解释器。

### 4.2 准备 `libtraceevent` 和 `libtracefs`

Kylin V10 SP1 没有打包 `libtraceevent-dev`，而 6.6 perf 把 `libtraceevent` 视为硬依赖。它用于解析 tracepoint 格式，影响 `perf trace`、`sched`、`lock`、`kmem` 和 tracepoint events。同时，内核源码树内的 `tools/lib/traceevent` 已在 v6.2 移除，不能再从 `common` 内部构建。

因此，需要在 Kaitian 上单独构建并安装 `libtraceevent` 和 `libtracefs`：

```bash
mkdir -p ~/perf-deps
cd ~/perf-deps
```

Kylin 的用户态 `btf.h` 来自 5.4 时代，编译新版 `libtraceevent` 时会缺少 5.13-6.0 新增的 BTF kind。不要改系统头文件，只从当前 `common` 中复制一个 6.6 版本的 `linux/btf.h` 作为单头文件 shim：

```bash
mkdir -p ~/perf-deps/btfinc/linux
cp /home/test/common/include/uapi/linux/btf.h ~/perf-deps/btfinc/linux/btf.h
SHIM=-I/home/test/perf-deps/btfinc
```

这个 shim 目录只包含 `linux/btf.h`，因此只有 `<linux/btf.h>` 会被替换成 6.6 版本；其他系统头文件仍来自发行版。

接着构建 `libtraceevent`。版本固定为 `libtraceevent-1.8.7`，不要使用浮动 HEAD：

```bash
cd ~/perf-deps
git clone --depth 1 --branch libtraceevent-1.8.7 \
  https://git.kernel.org/pub/scm/libs/libtrace/libtraceevent.git
cd libtraceevent
```

Kaitian 上的 GNU Make 是 4.2.1。这个版本会把 `$(shell ...)` 里的 `#` 当成注释起点，导致 `scripts/utils.mk` 中的 `$${f#tep_}` 展开失败，报：

```text
scripts/utils.mk:187: *** unterminated call to function 'shell': missing ')'.
```

只需要在外部依赖源码中转义这个 `#`：

```bash
sed -i 's/$${f#tep_}/$${f\#tep_}/' scripts/utils.mk
```

然后编译并安装到标准 aarch64 系统库目录：

```bash
make -j"$(nproc)" EXTRA_CFLAGS="$SHIM"
sudo make install prefix=/usr libdir=/usr/lib/aarch64-linux-gnu EXTRA_CFLAGS="$SHIM"
```

这里不能使用默认的 `/usr/local/lib64`。perf 的 feature check 会实际链接测试程序，`/usr/local/lib64` 不在默认 linker 搜索路径里，即使 `pkg-config` 能找到 `.pc`，链接也可能失败。安装到 `/usr/lib/aarch64-linux-gnu` 后，后续编译 perf 不需要额外传 `PKG_CONFIG_PATH` 或 `-L`。

再安装 `libtracefs`：

```bash
cd ~/perf-deps
git clone --depth 1 https://git.kernel.org/pub/scm/libs/libtrace/libtracefs.git
cd libtracefs
make -j"$(nproc)" EXTRA_CFLAGS="$SHIM"
sudo make install prefix=/usr libdir=/usr/lib/aarch64-linux-gnu EXTRA_CFLAGS="$SHIM"
sudo ldconfig
```

`ldconfig` 用于刷新动态链接器缓存，确保 perf 的 feature detection 和运行期加载都能找到新库。

### 4.3 编译 `/home/test/common/tools/perf`

外部依赖安装完以后，进入当前内核对应的 `common/tools/perf`：

```bash
cd /home/test/common/tools/perf
```

先清理旧构建产物，并删除 `FEATURE-DUMP`：

```bash
make clean >/dev/null 2>&1
rm -f FEATURE-DUMP
```

`FEATURE-DUMP` 会缓存 feature detection 结果，且不会被 `make clean` 删除。如果之前在缺少 `libtraceevent` 的状态下构建过，里面可能记录了 `feature-libtraceevent=0`。安装依赖后不删除它，perf 仍可能沿用旧的“缺失”判断。

开始构建：

```bash
make -j"$(nproc)" WERROR=0 PYTHON=python3
```

`WERROR=0` 用于避免发行版头文件或工具链差异把 warning 升级为 error；`PYTHON=python3` 用于保证 `jevents` 与 python scripting 支持走正确解释器。

构建完成后，把新 perf 放到默认 PATH 前部常见的位置：

```bash
sudo ln -sf /home/test/common/tools/perf/perf /usr/local/bin/perf
which perf
perf version
```

期望结果是：

```text
/usr/local/bin/perf
perf version 6.6.30.gda966ce9a047
```

如果 `which perf` 显示 `/usr/bin/perf`，先修正 PATH 或在后续脚本里显式使用 `/usr/local/bin/perf`。

### 4.4 验证 perf 功能

查看 build options：

```bash
perf version --build-options
```

本次需要的关键功能应为 on。实测除 `libbfd`（许可证默认关闭）和 `debuginfod` 外，核心功能均启用：

```text
dwarf, libelf, libnuma, libperl, libpython, libslang, libcrypto, libunwind,
bpf, aio, zstd, libpfm4, libtraceevent : [ on ]
```

然后验证基本计数、EL2 修饰符和 raw backend stall 事件：

```bash
perf stat -e cycles,instructions -- sleep 0.2
perf stat -e cycles:u,cycles:k,cycles:h -- sleep 0.2
perf stat -e r0024 -- sleep 0.2
```

`cycles:h` 在 `sleep` 时为 0 是正确现象；这只能说明 `:h` 被接受，不能单独证明 EL2 计数会在 EL2 忙碌时变成非零。这个阳性对照在 Stage 0 中完成。

---

## 5. 准备 `kylin-lmbench` 复查目录和 bench

本文假设 `kylin-lmbench` 在 Kaitian 的 home 目录下：

```text
/home/test/kylin-lmbench
```

如果仓库还不在板卡上，先把本仓库拷贝或克隆到该路径。复查脚本会把运行时数据写到用户目录下的 `~/perf-reinvestigation`，避免使用 world-writable 的 `/tmp` 作为固定文件路径。

进入仓库，编译需要的 microbench 和 Stage 0 探测程序：

```bash
cd ~/kylin-lmbench
make -C experiments/munmap-tlbi
make -C experiments/mmap-split
make -C experiments/perf-reinvestigation/stage0
```

创建复查目录，并把运行脚本期望使用的 bench 放到 `~/perf-reinvestigation/benches`：

```bash
mkdir -p ~/perf-reinvestigation/benches ~/perf-reinvestigation/results
cp experiments/munmap-tlbi/munmap_only ~/perf-reinvestigation/benches/
cp experiments/munmap-tlbi/op_sweep ~/perf-reinvestigation/benches/
cp experiments/mmap-split/mmap_split_bench ~/perf-reinvestigation/benches/
```

本文后续会直接调用仓库里的脚本。脚本内部使用这些固定路径：

```text
bench dir: ~/perf-reinvestigation/benches
result dir: ~/perf-reinvestigation/results
backing file: ~/perf-reinvestigation/mb.bin
perf: /usr/local/bin/perf
```

`mb.bin` 是用户私有目录下的文件，不放在 `/tmp`，目的是避免固定路径在 world-writable 目录中产生 symlink/TOCTOU 风险。

---

## 6. 每次测量前统一设置运行环境

微基准差异只有微秒级甚至每个 slot 数百纳秒，必须控制频率、THP、ASLR、perf 权限和 CPU idle。每次启动到 protected 或 nvhe 后，都执行：

```bash
cd ~/kylin-lmbench
bash experiments/perf-reinvestigation/setup-controls.sh
```

该脚本会做这些事：

- 将每个 CPU 的 governor 设为 `performance`。
- 将 `scaling_min_freq` 和 `scaling_max_freq` 锁到 `cpuinfo_max_freq`。
- 关闭 THP：`/sys/kernel/mm/transparent_hugepage/enabled = never`。
- 关闭 ASLR：`/proc/sys/kernel/randomize_va_space = 0`。
- 设置 perf 权限：`kernel.perf_event_paranoid=-1`，`kernel.kptr_restrict=0`。
- 尽量禁用 CPU idle 的深层 state。

后续所有 bench 都固定在 cpu0：

```text
taskset -c 0
```

判断时使用 **mean**，不要跨配置比较 `min`。单核或 hotplug 后的方差可能很大，`min` 会把一边的偶然最佳样本拿来与另一边的典型样本比较，制造错误结论。core-scaling 阶段会再次验证这个陷阱。

---

## 7. Stage 0：确认平台能否复查

Stage 0 有两个目的：

1. 判断这块板卡是否缺少 FEAT_TLBIRANGE。如果 FEAT_TLBIRANGE 存在，内核可能使用 range TLBI，低于 2 MB 的逐页 TLBI 成本可能消失。
2. 验证 `cycles:h` 在 pKVM 下不是永远清零。只有阳性对照能读到非零 EL2 cycles，后面用它判断 munmap 是否进入 EL2 才可信。

先运行 FEAT_TLBIRANGE 探测：

```bash
cd ~/kylin-lmbench/experiments/perf-reinvestigation/stage0
./isar0
```

Kaitian 实测为：

```text
ID_AA64ISAR0_EL1 = 0x0000111110212120
  TLB[59:56] = 0 => ABSENT (no TLBIOS/TLBIRANGE)
```

这表示 FEAT_TLBIRANGE 缺失。对本调查来说，这是继续执行的条件：缺少 range TLBI 时，内核在低于 2 MB 的 teardown 中会退回逐页 TLBI，per-slot 成本才可能显现。

再验证 `cycles:h` 的阳性对照：

```bash
taskset -c 0 perf stat -e cycles,cycles:u,cycles:k,cycles:h,instructions:h ./kvm_el2_probe 100000
```

Kaitian 实测关键行是：

```text
392,139,024      cycles:h          (EL2)
672,148,644      instructions:h
```

同一个 `cycles:h` 在 `sleep` 时为 0，在 100,000 次 `KVM_RUN` 通过 pKVM hypervisor 时变为 392M。这证明 pKVM 没有把 EL2 自计数清零。后面如果 sparse munmap 的 `cycles:h=0`，就可以解释为“teardown 时间不在 EL2”，而不是“计数器不可用”。

最后确认 FTC862 事件可用性：

```bash
perf stat -e r0024,r0034,stall_backend,l2d_tlb_refill -- true
```

本次可用事件：

- `r0024`：backend stall，后续也可用命名事件 `stall_backend`。
- `r0034`：DTLB walk。FTC862 上 `dtlb_walk` 没有名称暴露，统一用 raw code `r0034`。
- `l2d_tlb_refill`：二级 DTLB refill。

若 FEAT_TLBIRANGE 存在，或者 `cycles:h` 阳性对照不成立，应停止按本文默认结论推进，转为记录该板卡的平台差异。

---

## 8. 在 protected 与 nvhe 下分别运行主复查

主复查必须在 protected 和 nvhe 两个启动模式下各跑一次。每次切换模式后，都要重新确认 `/proc/cmdline`，不能假设 GRUB one-shot 一定生效。

查看当前模式：

```bash
grep -o 'kvm-arm.mode=[^ ]*' /proc/cmdline
```

如果当前是 protected，先运行 controls 和主 suite：

```bash
cd ~/kylin-lmbench
bash experiments/perf-reinvestigation/setup-controls.sh
bash experiments/perf-reinvestigation/run-suite.sh protected
```

脚本会生成：

```text
~/perf-reinvestigation/results/protected/kernel.txt
~/perf-reinvestigation/results/protected/op_sweep.txt
~/perf-reinvestigation/results/protected/el2_h.txt
~/perf-reinvestigation/results/protected/cost_layering.txt
```

随后切到 nvhe。GRUB 条目名称按实际系统为准，先列出可用 menuentry：

```bash
grep -n "menuentry " /boot/grub/grub.cfg
```

选择包含 `kvm-arm.mode=nvhe` 的条目，用该条目的完整名称执行：

```bash
sudo grub-reboot '<exact nvhe menuentry name>'
sudo reboot
```

重启后必须验证：

```bash
grep -o 'kvm-arm.mode=[^ ]*' /proc/cmdline
```

确认已经是 `kvm-arm.mode=nvhe` 后，重新设置 controls，并运行同一套 suite：

```bash
cd ~/kylin-lmbench
bash experiments/perf-reinvestigation/setup-controls.sh
bash experiments/perf-reinvestigation/run-suite.sh nvhe
```

生成：

```text
~/perf-reinvestigation/results/nvhe/kernel.txt
~/perf-reinvestigation/results/nvhe/op_sweep.txt
~/perf-reinvestigation/results/nvhe/el2_h.txt
~/perf-reinvestigation/results/nvhe/cost_layering.txt
```

Kaitian 上 `grub-reboot` one-shot 曾出现不消费 `next_entry` 的情况：第一次切换成功，后续几次仍启动到 protected。遇到这种情况时，不要沿用模式假设，必须以 `/proc/cmdline` 为准。

---

## 9. 读 `op_sweep`：确认 2 MB 断崖和操作无关性

`run-suite.sh` 的第一部分运行 `op_sweep`。它对 `munmap`、`MADV_DONTNEED`、`mprotect` 三种 teardown 方向操作分别扫描触摸范围：

```text
0.25, 0.5, 1, 1.9, 2, 4, 8, 32, 64 MB，dense 4 K stride
以及 sparse 6.4 MB / 16 K stride
```

读数时比较：

```text
gap = protected mean - nvhe mean
```

Kaitian 的 `munmap` 结果如下：

| flush range | slots | protected us | nvhe us | gap us | us/slot |
|---:|---:|---:|---:|---:|---:|
| 0.25 MB | 64 | 23.1 | 15.5 | +7.6 | 0.119 |
| 0.5 MB | 128 | 43.5 | 25.8 | +17.7 | 0.138 |
| 1.0 MB | 256 | 79.6 | 46.6 | +33.0 | 0.129 |
| 1.9 MB | 486 | 148.7 | 87.3 | +61.4 | 0.126 |
| 2.0 MB | integer flush | 88.2 | 86.6 | +1.6 | - |
| sparse 6.4/16K | per-PMD | 294.8 | 89.2 | +205.6 | - |

判断逻辑是：

- 低于 2 MB 时，gap 随 4 K flush slot 数量近似线性增长。
- 到 2.0 MB 时，gap 从 +61.4 us 断崖式降到 +1.6 us。
- 这对应内核从逐页 TLBI 切换到 whole-ASID integer flush；阈值是 `MAX_DVM_OPS=512`，也就是 512 个 4 K slot = 2 MB。

再看操作无关性：

| flush range | munmap gap | dontneed gap | mprotect gap |
|---:|---:|---:|---:|
| 0.25 MB | +7.6 | +7.8 | +7.7 |
| 1.0 MB | +33.0 | +31.1 | +31.9 |
| 1.9 MB | +61.4 | +61.0 | +61.0 |
| 2.0 MB | +1.6 | +1.2 | +0.2 |
| sparse 6.4/16K | +205.6 | +205.5 | +0.1 |

低于 2 MB 时，三种 syscall 的 gap 几乎相同。这说明成本来自共同的 per-slot TLBI，而不是 `munmap` 自己的 VMA 或 syscall 逻辑。`mprotect` 在 sparse 场景逃逸，是因为它不执行 dirty-zap，能够积累出一个 >=2 MB 的 flush，走 integer path。

这一阶段已经给出机制主线：protected 多出来的时间与低于 2 MB 的 per-slot TLBI 数量成正比。

---

## 10. 读 `el2_h`：确认 teardown 时间不在 EL2

`run-suite.sh` 的第二部分用 perf 测 sparse munmap 的异常级别归因：

```bash
taskset -c 0 /usr/local/bin/perf stat -e cycles,cycles:k,cycles:h,instructions:h \
  ~/perf-reinvestigation/benches/munmap_only file 64 300 ~/perf-reinvestigation/mb.bin 6.4 16
```

看 `~/perf-reinvestigation/results/protected/el2_h.txt` 和 `~/perf-reinvestigation/results/nvhe/el2_h.txt`。

Kaitian 实测：

```text
protected: cycles:h = 0, instructions:h = 0
nvhe:      cycles:h = 0
```

这说明 sparse munmap teardown 的额外时间不在 EL2。这个结论可信，是因为 Stage 0 已经证明同一 `cycles:h` 计数器在 100,000 次 `KVM_RUN` 阳性对照中能读到 392M。

因此，调查方向应继续看 host EL1 的工作量和 stall，而不是怀疑 hypervisor 执行时间。

---

## 11. 读 `cost_layering`：确认不是更多 walk，而是更多 backend stall

`run-suite.sh` 的第三部分测两组 `munmap_only`：

- sparse：64 MB 映射，触摸 6.4 MB，16 K stride，复刻 `lat_mmap` 的 sparse 形态。
- dense：64 MB 映射，触摸 1 MB，4 K stride，落在 2 MB 以下逐页 TLBI 区间。

perf 事件是：

```text
instructions,page-faults,r0034,l2d_tlb_refill,r0024,cycles
```

含义如下：

- `instructions`：是否执行了更多指令。
- `page-faults`：是否 fault 数不同。
- `r0034`：DTLB walk，FTC862 上用 raw code。
- `l2d_tlb_refill`：二级 DTLB refill。
- `r0024`：backend stall。
- `cycles`：总周期。

sparse munmap 的 protected vs nvhe 结果：

| event | protected | nvhe | delta |
|---|---:|---:|---:|
| instructions | 463.7 M | 463.1 M | +0.6 M |
| page-faults | 123,050 | 123,050 | 0 |
| DTLB-walk (`r0034`) | 122,556 | 123,506 | 约 0 |
| l2d_tlb_refill | 122,944 | 123,609 | 约 0 |
| stall_backend (`r0024`) | 206.2 M | 87.5 M | +118.7 M |
| cycles | 369.8 M | 250.3 M | +119.5 M |

判断逻辑是：

- instructions 几乎相同，说明 protected 没有多执行一套软件路径。
- page-faults 相同，说明输入工作量相同。
- DTLB walk 与 l2d_tlb_refill 相同，说明 protected 没有做更多页表 walk。
- 额外 cycles 几乎完全等于额外 backend stall：+119.5M cycles 对 +118.7M stall。

因此，nested-walk 假设被反驳：protected 不是“做了更多 walk”。更合理的解释是，同样数量的 per-slot TLBI 在带 host stage-2 的 combined/VMID-tagged TLB entry 上完成得更慢，期间表现为 host EL1 的 backend memory stall。

数值也能闭合：

```text
sparse wall-time gap: about 203 us/iter ~= 386k cycles @1.9 GHz
perf cycle gap: 119.5M / 300 = 398k cycles/iter
1 MB dense per-slot: 18.9M cycles / 300 / 256 = 246 cycles ~= 0.13 us/slot
```

这与 `op_sweep` timing 推出的约 +0.13 us/slot 一致。

---

## 12. 在 protected 下跑 core-scaling：确认不是跨核 broadcast

core-scaling 只需要在 protected 下跑。若当前在 nvhe，先切回 protected，并重新验证：

```bash
grep -o 'kvm-arm.mode=[^ ]*' /proc/cmdline
```

确认是 `kvm-arm.mode=protected` 后，运行：

```bash
cd ~/kylin-lmbench
bash experiments/perf-reinvestigation/setup-controls.sh
bash experiments/perf-reinvestigation/core-scaling.sh
```

脚本会改变 online CPU 集合，只让 cpu0 跑 sparse munmap，并记录 mean、cycles、`r0024` 和 instructions：

```text
~/perf-reinvestigation/results/corescaling/corescaling.txt
```

Kaitian 实测：

| online set | mean us | min us | cycles | stall_backend (`r0024`) | instructions |
|---|---:|---:|---:|---:|---:|
| n8 all | 294.2 | 290.5 | 1,187.6 M | 680.8 M | 1,442.6 M |
| n2 intra {0,1} | 294.7 | 290.4 | 1,187.9 M | 680.0 M | 1,442.3 M |
| n2 cross {0,4} | 295.3 | 290.6 | 1,188.8 M | 681.9 M | 1,442.6 M |
| n1 solo {0} | 303.3 | 209.3 | 1,208.1 M | 676.4 M | 1,451.2 M |

判断逻辑是：

- mean 基本不随 online core 数或 cluster 位置变化。
- cycles、stall_backend、instructions 也基本持平。
- 如果成本来自跨核 DVM broadcast 或等待其他核完成 shootdown，online core 越多通常应越慢；实测没有。

因此，per-slot TLBI 成本是本地成本，不是跨核 broadcast wait。

同时注意 `min` 陷阱：n1 solo 的 `min=209 us` 明显低于 `mean=303 us`，如果用 min 比较，会错误地制造出“1 核到 8 核变慢”的假象。本文所有结论都以 mean 和 perf 进程级计数为准。

---

## 13. 跑 `mmap_split`：确认成本在 touched-page teardown

为了把 `lat_mmap` 生命周期拆开，运行 `mmap_split_bench`。当前已采集的是 protected 分支：

```bash
cd ~/kylin-lmbench
bash experiments/perf-reinvestigation/setup-controls.sh
bash experiments/perf-reinvestigation/run-mmapsplit.sh protected
```

结果写入：

```text
~/perf-reinvestigation/results/protected/mmap_split.csv
```

Kaitian protected 实测：

| phase | protected us/iter |
|---|---:|
| `mmap_unmap`：创建并删除 VMA，不 touch | 3.54 |
| `write_touch_cold`：只计 first-touch faults | 330.35 |
| `munmap_after_no_touch`：未映射实际页时 teardown | 1.66 |
| `munmap_after_write_touch`：touch 后 teardown | 292.84 |
| `mmap_write_touch_unmap`：完整路径 | 625.01 |

判断逻辑是：

- 完整路径约等于 touch、teardown 和 setup 的和：625 ~= 330 + 293 + 3。
- 未 touch 的 munmap 几乎免费：1.66 us。
- touch 后的 munmap 是 292.84 us。

因此，`lat_mmap` 中真正需要解释的是 touched PTE teardown，即 clear PTE 加 per-page TLBI，不是单纯的 VMA create/delete，也不是 first-touch fault 本身。

nvhe `mmap_split` 分支在本次 Kaitian 会话中没有完成，原因是 `grub-reboot` one-shot 后续不可靠。这不影响最终机制判断，因为 protected/nvhe 的 `op_sweep`、`el2_h` 和 `cost_layering` 已经把 gap 隔离到 touched-page teardown，并证实其表现为 per-slot TLBI 的 backend stall。

---

## 14. 最终判断流程

按本文顺序执行后，用下面的判断树收敛结论：

```text
1. FEAT_TLBIRANGE 是否存在？
   yes -> 该板卡可能使用 range TLBI，逐页 TLBI 税可能消失；记录平台免疫原因。
   no  -> 继续。

2. protected - nvhe gap 是否存在？
   no  -> 重新检查控制条件、perf 版本和启动模式；若仍无 gap，这就是该板卡的结论。
   yes -> 继续。

3. gap 是否在 2 MB 处断崖消失，并在 2 MB 以下与 4 K slot 数成正比？
   no  -> 不要套用逐页 TLBI 结论，回看 benchmark geometry 和事件可用性。
   yes -> 支持 per-slot TLBI 机制。

4. cycles:h 是否在 munmap 中为 0？
   no  -> 需要重新分析 EL2 路径。
   yes -> 成本不在 EL2。

5. DTLB walk / l2d_tlb_refill 是否相同，而 backend stall 与 cycles 同步增长？
   no  -> 可能存在额外 walk 或其他工作量差异。
   yes -> 反驳 nested-walk，支持同样工作变慢。

6. core-scaling 是否随 online core 数增长？
   yes -> 需要考虑 broadcast/shootdown wait。
   no  -> 成本是本地 TLBI 完成成本。
```

Kaitian 的实际路径是：

```text
FEAT_TLBIRANGE absent
protected - nvhe gap present
gap below 2 MB proportional to slot count
gap collapses at exactly 2 MB
cycles:h = 0 during sparse munmap
walk counts equal
extra cycles ~= extra backend stall
core-scaling flat
```

因此最终结论是：

```text
pKVM lat_mmap 退化来自 touched-page teardown 中低于 2 MB 的逐页 TLBI。
host stage-2 存在时，每个 4 K flush slot 在 Kaitian 上约多 +0.13 us。
这部分成本发生在 host EL1，表现为 backend memory stall；
它不在 EL2，不是更多页表 walk，也不是跨核 broadcast wait。
```

---

## 15. 本手册涉及的文件

本文可以独立阅读和执行；下面只列出实际用到的文件，便于审计：

```text
/home/test/common/tools/perf
~/kylin-lmbench/experiments/perf-reinvestigation/setup-controls.sh
~/kylin-lmbench/experiments/perf-reinvestigation/run-suite.sh
~/kylin-lmbench/experiments/perf-reinvestigation/core-scaling.sh
~/kylin-lmbench/experiments/perf-reinvestigation/run-mmapsplit.sh
~/kylin-lmbench/experiments/perf-reinvestigation/stage0/{isar0.c,kvm_el2_probe.c,guest.S,Makefile}
~/kylin-lmbench/experiments/munmap-tlbi/{munmap_only.c,op_sweep.c,Makefile}
~/kylin-lmbench/experiments/mmap-split/{mmap_split_bench.c,Makefile}
~/perf-reinvestigation/results/
```

若要复跑，优先复用本文的顺序：先确认内核和 `common` 匹配，再构建 perf，再做 Stage 0，最后跑 protected/nvhe 主 suite、core-scaling 和 mmap_split。不要跳过启动模式验证，也不要用 `min` 替代 mean 得出结论。
