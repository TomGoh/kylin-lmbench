# 在 Kaitian 上基于 `common` 仓库构建匹配当前内核的 `perf`

| | |
|---|---|
| 日期 | 2026-06-24 |
| 板卡 | Kaitian（`ssh Kaitian` -> 10.42.27.22），用户 `test`，home 目录 `/home/test` |
| 发行版 | Kylin V10 SP1（Kylin-Desktop V10-SP1），gcc 9.3.0，**GNU Make 4.2.1** |
| 当前内核 | `6.6.30-pkvm-clean`，启动参数包含 `kvm-arm.mode=protected` |
| 内核源码 | 板卡本地的 `/home/test/common`，HEAD 为 `da966ce9a047bedffb02e0bdc87f3ccb5fb3f9d9` |
| CPU | Phytium **FTC862**（implementer `0x70`，part `0x862`），8 核，与 N80 是同一款核心 |
| 目标 | 在 Kaitian 上从 `/home/test/common/tools/perf` 构建一个与当前 6.6.30 内核对应、功能完整的 `perf` |
| 结果 | `/usr/local/bin/perf` 指向 `/home/test/common/tools/perf/perf`，版本为 `perf 6.6.30.gda966ce9a047`；除 `libbfd` 和 `debuginfod` 外，其余关键特性均启用 |

本文说明的不是在 `kylin-lmbench` 仓库中编译 perf，而是在 **Kaitian 板卡上，使用同一块板卡上的
`common` 内核源码仓库**构建 perf。`kylin-lmbench` 只保存本文档、脚本和复查数据。真正的 perf
源码来自 `/home/test/common/tools/perf`，因为它必须与正在运行的 6.6.30 pKVM 内核匹配。

构建过程会在板卡本地的 `common/tools/perf/` 下生成目标文件，但不需要修改开发机上的 `common`
源码，也不需要修改 `kylin-lmbench`。唯一会做文本修补的是外部依赖 `libtraceevent` 的源码，
原因是 Kaitian 上的 GNU Make 4.2.1 对 `$(shell ...)` 中的 `#` 解析有兼容性问题，后文会说明。

---

## 1. 为什么必须从 `common/tools/perf` 编译

Kylin V10 SP1 仓库提供的 `perf` 面向发行版自己的 5.4.18 内核，而 Kaitian 当前运行的是
`6.6.30-pkvm-clean`。普通 `perf stat -e cycles` 这类计数大多依赖稳定的 `perf_event_open` ABI，
跨内核版本通常还能工作；但本次 pKVM mmap 复查依赖的能力不只是普通计数：

- `:h` 异常级别修饰符需要 perf 正确识别 EL2/hyp 计数语义。
- FTC862 的命名事件表、raw event 编码、PMU JSON 到 C 的 `jevents` 生成结果都跟 perf 构建版本有关。
- `perf version --build-options` 中的 `libtraceevent`、`libpfm4`、`libunwind` 等功能会影响后续可用性。

因此，可靠做法是：在 Kaitian 上使用与当前内核来源一致的 `/home/test/common/tools/perf` 编译
perf，并把生成的二进制放到 `/usr/local/bin/perf`。这样，后续
[perf-only mmap 复查手册](perf-only-mmap-investigation-playbook.zh-CN.md) 中使用的 `cycles:h`、
`r0024`、`r0034`、`l2d_tlb_refill` 等事件，才有明确的版本对应关系。

---

## 2. 构建前确认环境

先登录 Kaitian，并确认当前运行内核、启动模式和 `common` 仓库状态。本文后续命令都默认在板卡上执行。

```bash
ssh Kaitian
uname -r
cat /proc/cmdline
cd /home/test/common
git rev-parse HEAD
test -d tools/perf && echo "common tools/perf is present"
```

本次记录对应的期望状态是：

```text
kernel: 6.6.30-pkvm-clean
cmdline: contains kvm-arm.mode=protected
common HEAD: da966ce9a047bedffb02e0bdc87f3ccb5fb3f9d9
```

如果 `common` 的提交发生变化，最终 perf 版本也会随之变化。此时应重新编译，而不是复用旧的
`/usr/local/bin/perf`。

还需要临时放开 perf 计数权限，后续 Stage 0 和正式复查都会依赖这些设置：

```bash
sudo sysctl -w kernel.perf_event_paranoid=-1 kernel.kptr_restrict=0
```

这两个 sysctl 重启后会恢复默认值。若要长期使用，可以之后再写入 `/etc/sysctl.d/`；本文只记录
本次可复现构建所需的运行时设置。

---

## 3. 安装 Kylin 仓库中的构建依赖

`common/tools/perf` 本身会根据系统上是否存在某些库，决定启用哪些功能。为了得到后续复查可用的
完整 perf，本次不是只安装最小依赖，而是把 Kylin 仓库中可用的 perf 相关开发包一次装齐：

```bash
sudo apt-get install -y \
  flex bison pkg-config zlib1g-dev libelf-dev libdw-dev libunwind-dev \
  libcap-dev libzstd-dev liblzma-dev \
  python3-dev libperl-dev libslang2-dev systemtap-sdt-dev libnuma-dev \
  libbabeltrace-dev binutils-dev libpfm4-dev libssl-dev libaio-dev libiberty-dev
```

这些包大致分成几类：

- `flex`、`bison`、`pkg-config` 是 perf 构建和 feature detection 的基础工具。
- `zlib1g-dev`、`libelf-dev`、`libdw-dev`、`libunwind-dev`、`libzstd-dev`、`liblzma-dev`
  支撑 ELF、DWARF、unwind 和压缩数据处理。
- `python3-dev` 提供 `python3-config`，用于 python scripting 支持；perf 的 `jevents`
  生成器也需要 Python 解释器。
- `libperl-dev`、`libslang2-dev`、`systemtap-sdt-dev`、`libnuma-dev`、`libbabeltrace-dev`、
  `binutils-dev`、`libpfm4-dev`、`libssl-dev`、`libaio-dev`、`libiberty-dev` 分别启用 perf
  的脚本、TUI、SDT、NUMA、Babeltrace、bfd/libiberty、libpfm4、crypto 和 AIO 等能力。

第一次尝试构建时，如果缺少 `python3-dev`，会先遇到：

```text
Makefile.config:881: *** ERROR: No python interpreter needed for jevents generation.
Makefile.config:285: *** /usr/bin/python3-config not found.
```

因此后续真正编译 perf 时需要显式传入 `PYTHON=python3`，并确保 `python3-config` 已由
`python3-dev` 提供。

---

## 4. 准备 `libtraceevent` 与 `libtracefs`

安装完 Kylin 仓库依赖后，仍不能直接编译 6.6 的 perf。关键原因是：6.6 perf 将
`libtraceevent` 视为硬依赖，用它解析 tracepoint 格式，支撑 `perf trace`、`sched`、`lock`、
`kmem` 和 tracepoint events；但 Kylin V10 SP1 仓库没有 `libtraceevent-dev`。同时，内核源码树内的
`tools/lib/traceevent` 已在 v6.2 被移除，不能再从 `common` 内部顺手构建。

解决办法是在 Kaitian 上从 kernel.org 拉取并安装 `libtraceevent`。同时安装 `libtracefs`，
用于补齐 `perf ftrace` 相关能力。

先准备一个独立依赖目录：

```bash
mkdir -p ~/perf-deps
cd ~/perf-deps
```

### 4.1 用 `common` 中的新版 `btf.h` 做单头文件 shim

Kaitian 的用户态头文件来自 Kylin 5.4 时代。直接编译新版 `libtraceevent` 时，会因为
`/usr/include/linux/btf.h` 太旧而失败：

```text
trace-btf.c:70:3: error: 'BTF_KIND_FLOAT' undeclared
                  ('BTF_KIND_DECL_TAG', 'BTF_KIND_TYPE_TAG', 'BTF_KIND_ENUM64' too)
```

这些 BTF kind 是 5.13 到 6.0 期间新增的，而 `/home/test/common` 中已经有 6.6 对应的
UAPI 头文件。这里不修改系统头文件，只把 `linux/btf.h` 单独复制到一个 shim 目录：

```bash
mkdir -p ~/perf-deps/btfinc/linux
cp /home/test/common/include/uapi/linux/btf.h ~/perf-deps/btfinc/linux/btf.h
SHIM=-I/home/test/perf-deps/btfinc
```

这个目录只包含 `linux/btf.h`。因此，编译 `libtraceevent` 和 `libtracefs` 时，
`<linux/btf.h>` 会解析到 6.6 版本；其他 `<linux/*>` 仍来自发行版系统头文件。这样既解决了
BTF kind 缺失，又避免了全局替换系统头文件带来的风险。

### 4.2 构建并安装 `libtraceevent`

`libtraceevent` 固定到 `libtraceevent-1.8.7`，不要使用浮动 HEAD。固定版本的原因是：
本手册需要可复现；当时的 1.9.0-dev HEAD 还存在额外 static-lib Makefile 回归。

```bash
cd ~/perf-deps
git clone --depth 1 --branch libtraceevent-1.8.7 \
  https://git.kernel.org/pub/scm/libs/libtrace/libtraceevent.git
cd libtraceevent
```

Kaitian 上的 GNU Make 是 4.2.1。这个版本会把 `$(shell ...)` 内的 `#` 当作注释起点，
导致 `scripts/utils.mk` 中的参数展开被截断，报错如下：

```text
scripts/utils.mk:187: *** unterminated call to function 'shell': missing ')'.
```

触发点是类似 `$${f#tep_}` 的 shell 参数展开。修复方式是在外部依赖源码中把 `#` 转义为 `\#`：

```bash
sed -i 's/$${f#tep_}/$${f\#tep_}/' scripts/utils.mk
```

这个修改只发生在 `~/perf-deps/libtraceevent`，不会改动 `/home/test/common`。随后用前面准备好的
`btf.h` shim 编译并安装到标准系统前缀：

```bash
make -j"$(nproc)" EXTRA_CFLAGS="$SHIM"
sudo make install prefix=/usr libdir=/usr/lib/aarch64-linux-gnu EXTRA_CFLAGS="$SHIM"
```

这里特意使用 `prefix=/usr libdir=/usr/lib/aarch64-linux-gnu`。如果使用默认安装路径，
`libtraceevent` 会落到 `/usr/local/lib64`，而该目录不在默认 linker 搜索路径中。perf 的
feature check 需要实际链接 `test-libtraceevent.c`，所以即使 `pkg-config` 能看到 `.pc` 文件，
链接仍会失败。安装到 `/usr/lib/aarch64-linux-gnu` 后，perf 不需要额外的 `PKG_CONFIG_PATH`
或 `-L` 参数。

### 4.3 构建并安装 `libtracefs`

`libtracefs` 用于 perf 的 ftrace 相关功能。它同样使用 `btf.h` shim 编译，并安装到相同标准前缀：

```bash
cd ~/perf-deps
git clone --depth 1 https://git.kernel.org/pub/scm/libs/libtrace/libtracefs.git
cd libtracefs
make -j"$(nproc)" EXTRA_CFLAGS="$SHIM"
sudo make install prefix=/usr libdir=/usr/lib/aarch64-linux-gnu EXTRA_CFLAGS="$SHIM"
sudo ldconfig
```

`sudo ldconfig` 用于刷新动态链接器缓存，确保后面 perf 的 feature detection 和运行期加载都能找到
新安装的 `.so`。

---

## 5. 从 `/home/test/common/tools/perf` 编译 perf

外部依赖准备好后，进入板卡本地 `common` 仓库中的 perf 目录：

```bash
cd /home/test/common/tools/perf
```

先清理旧构建产物，并删除 `FEATURE-DUMP`：

```bash
make clean >/dev/null 2>&1
rm -f FEATURE-DUMP
```

这里必须显式删除 `FEATURE-DUMP`。`make clean` 不会清掉这个文件，而它会缓存之前 feature
detection 的结果。第一次缺少 `libtraceevent` 时，`FEATURE-DUMP` 里可能已经记录了
`feature-libtraceevent=0`。如果安装依赖后不删除它，perf 仍会沿用陈旧的“缺失”判断。

然后开始编译：

```bash
make -j"$(nproc)" WERROR=0 PYTHON=python3
```

参数含义如下：

- `-j"$(nproc)"` 使用板卡上可用 CPU 并行编译。
- `WERROR=0` 避免发行版头文件或工具链差异导致 warning 被当作 error 中断构建。
- `PYTHON=python3` 避免 perf 自动探测不到 Python 解释器，保证 `jevents` 和 python scripting
  相关构建逻辑使用正确解释器。

成功后，目标二进制位于：

```text
/home/test/common/tools/perf/perf
```

---

## 6. 安装到默认 PATH

为了后续脚本统一使用 `/usr/local/bin/perf`，将刚刚构建出的二进制链接过去：

```bash
sudo ln -sf /home/test/common/tools/perf/perf /usr/local/bin/perf
```

确认当前 shell 找到的是这个新版本：

```bash
which perf
perf version
```

本次结果应为：

```text
/usr/local/bin/perf
perf version 6.6.30.gda966ce9a047
```

如果 `which perf` 仍指向 `/usr/bin/perf`，说明 PATH 顺序不对，后续测试可能误用发行版 5.4 内核对应的
perf。此时应先修正 PATH，或者在脚本中显式使用 `/usr/local/bin/perf`。

---

## 7. 验证构建功能

首先查看 build options。除 `libbfd` 和 `debuginfod` 外，本次复查需要的核心功能应处于 on 状态：

```bash
perf version --build-options
```

本次记录中确认开启的功能包括：

```text
dwarf, libelf, libnuma, libperl, libpython, libslang, libcrypto, libunwind,
bpf, aio, zstd, libpfm4, libtraceevent : [ on ]
```

随后做最小计数验证：

```bash
perf stat -e cycles,instructions -- sleep 0.2
perf stat -e cycles:u,cycles:k,cycles:h -- sleep 0.2
perf stat -e r0024 -- sleep 0.2
```

这些命令分别验证三件事：

- 普通硬件计数可用。
- `:h` EL2/hyp 修饰符被接受。`sleep` 期间 `cycles:h=0` 是合理结果，因为没有已知 EL2 工作负载。
- raw event `r0024` 可用，它对应 FTC862 上的 backend stall 计数。

本次观察到：

```text
cycles:u=259,939
cycles:k=690,240
cycles:h=0
r0024 raw STALL_BACKEND works
```

Stage 0 随后用 100,000 次 `KVM_RUN` 做了 `:h` 阳性对照，`cycles:h` 从静止状态的 0 变为
392M，证明 pKVM 没有把 EL2 自计数清零。详见
[../../../experiments/perf-reinvestigation/stage0/README.zh-CN.md](../../../experiments/perf-reinvestigation/stage0/README.zh-CN.md)。

FTC862 的事件名情况如下：

- 可按名称使用：`stall_backend`、`stall_frontend`、`l1d_tlb`、`l2d_tlb_refill`、`mem_access`
- 没有名称暴露：`dtlb_walk`，后续统一使用架构 raw code `r0034`

---

## 8. 本次构建的精确版本记录

- `common` HEAD：`da966ce9a047bedffb02e0bdc87f3ccb5fb3f9d9`
- perf：`perf version 6.6.30.gda966ce9a047`
- perf 路径：`/usr/local/bin/perf` -> `/home/test/common/tools/perf/perf`
- libtraceevent：**1.8.7**，固定 tag `libtraceevent-1.8.7`
- libtracefs：**1.8.3**，构建时 HEAD
- 动态库安装位置：`/usr/lib/aarch64-linux-gnu`
- 头文件安装位置：`/usr/include/traceevent`、`/usr/include/tracefs`
- 第一次尝试残留的 `/usr/local/lib64/libtrace*` 副本无害；若要清理，可执行
  `sudo rm /usr/local/lib64/libtrace*`

本次从 Kylin 仓库（`archive.kylinos.cn`，`10.1-kylin`）安装的开发包版本如下：

```text
flex=2.6.4-6.2  bison=2:3.5.1+dfsg-1  pkg-config=0.29.1-1kylin4
zlib1g-dev=1:1.2.11.dfsg-2kylin1.5k0.2  libelf-dev=0.176-1.1kylin0.1  libdw-dev=0.176-1.1kylin0.1
libunwind-dev=1.2.1-9build1k4  libcap-dev=1:2.32-1kylin0.2  libzstd-dev=1.4.4+dfsg-3kylin0.1
liblzma-dev=5.2.4-1kylin2.1  python3-dev=3.8.2-0kylin2  libpython3-dev=3.8.2-0kylin2
libperl-dev=5.30.0-9kylin0.5k0.3  libslang2-dev=2.3.2-4  systemtap-sdt-dev=4.2-3
libnuma-dev=2.0.12-1  libbabeltrace-dev=1.5.8-1build1kylin0  binutils-dev=2.34-6kylin1.11
libpfm4-dev=4.10.1+git20-g7700f49-2  libssl-dev=1.1.1f-1kylin2.23k0.6  libaio-dev=0.3.112-5kylin0k1
libiberty-dev=20200409-1kylin0k1
```

---

## 9. 重新应用到其他内核或其他板卡

perf 二进制与构建它的 `common` checkout 绑定。如果 Kaitian 上的内核来自新的 `common` 提交，
或者换到另一块板卡、另一个内核版本，应重新执行本文流程。复用旧 perf 可能导致事件表、raw event
解释或异常级别修饰符行为与当前内核不一致。

迁移时需要重点检查这些分支：

- 如果目标板卡的 GNU Make >= 4.3，可以跳过 `libtraceevent` 的 `sed` 修补。
- 如果发行版已经提供 `libtraceevent-dev` 和 `libtracefs-dev`，可以优先使用发行版包，但仍要确认
  `perf version --build-options` 中 `libtraceevent` 为 on。
- 如果用户态 `/usr/include/linux/btf.h` 已经足够新，可以跳过 `btf.h` shim。
- 如果板卡不能访问 `git.kernel.org`，需要提前准备 `libtraceevent-1.8.7` 和 `libtracefs` 源码包，
  但安装前缀仍建议保持为 `/usr` 与 `/usr/lib/aarch64-linux-gnu`。
- 每次重启后重新设置 `kernel.perf_event_paranoid=-1` 和 `kernel.kptr_restrict=0`，否则后续 perf
  计数可能被权限限制拦截。

随本目录提交的 [build-perf-on-kaitian.sh](build-perf-on-kaitian.sh) 将上述步骤脚本化，并对若干陷阱做了探测。
本文则保留完整背景和顺序说明，便于审计每一步为什么需要执行。
