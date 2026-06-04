# Experiment design

> 📌 **Status (2026-06-04)**: 本文是 day-1（2026-06-01）的**实验设计草案**，描述了
> 最初的 5-env 对照（baremetal / pkvm-host / kvm-guest / pkvm-guest-np / pkvm-guest）。
> Day-3 (2026-06-03) 实际执行时**pivot 到 4-config 主机对照**
> （`kvm-arm.mode` = none / nvhe / vhe / protected，全 noLSM），跳过 guest 维度
> （pvmfw 在 N90 上不可用 + protected guest 启动失败）。
>
> **最终 paper-grade findings 和方法论详见 [`findings-2026-06-03/`](findings-2026-06-03/)**：
> - [`README.md`](findings-2026-06-03/README.md) ── 总体方法论、噪声控制、复现要点
> - [`SUMMARY.md`](findings-2026-06-03/SUMMARY.md) ── 6 个 paper-level findings
> - 4 个 per-config 报告 + 2 个 pkvm 专题 + standalone 验证
> - [`lmbench-N10-4config.xlsx`](findings-2026-06-03/lmbench-N10-4config.xlsx)
>   ── 全部指标的对照表（pkvm 用 try2 数据）
>
> Day-1 / day-2 的中间发现见 [`findings-2026-06-01.md`](findings-2026-06-01.md)、
> [`findings-2026-06-02.md`](findings-2026-06-02.md)。

## Goal

Quantify the latency / bandwidth overhead introduced by **KVM** and especially
**protected-KVM (pKVM)** on aarch64 (Phytium D3000M), with a particular focus
on isolating which operations pay how much for the hypervisor.

The headline question we want to answer:

> For each class of workload, what is the cost ratio of running on
> pKVM-guest vs KVM-guest vs bare-metal-host?

And, where pKVM shows cost relative to KVM, can we attribute it to a specific
mechanism (stage-2 page-table walk, EL2 trap, bounce-buffer copy)?

## The hardware and what it constrains

Phytium D3000M, 8 cores:

| Cluster | CPUs | Max freq | Notes |
|---------|------|----------|-------|
| 0 (id=88)  | cpu0–3 | cpu0–2: 1.9 GHz, **cpu3: 2.9 GHz** | 1 "big" + 3 "little" |
| 1 (id=572) | cpu4–7 | cpu4–6: 1.9 GHz, **cpu7: 2.9 GHz** | 1 "big" + 3 "little" |

Implications:

1. The two big cores live in **different clusters**. Any 2-vCPU "big" guest
   forces cross-cluster IPI / L2 traffic and can't be co-located on one L2.
   2-vCPU "little" guests can be either same-cluster (cpu0+cpu1) or
   cross-cluster (cpu0+cpu4) — useful as a control for "cluster crossing cost".
2. Same `CPU part` (0x862) for all cores. Empirically (see pilot data), at the
   **same locked frequency**, big and little cores produce indistinguishable
   numbers (±2 %) on every lmbench benchmark. Conclusion: the difference is
   binning/voltage, not microarchitecture. **One frequency-locked baseline is
   enough** — we don't need to track big vs little separately.

## Variables and how they are controlled

| Variable | Risk if uncontrolled | Control |
|----------|----------------------|---------|
| CPU frequency | 1.5× swing between cores | `prepare-host.sh` locks **all** cores to 1.9 GHz (the floor) with `performance` governor; min == max == 1900 kHz |
| Deep idle (C-states) | Wake-up latency contaminates `lat_ctx`, `lat_sig` | `prepare-host.sh` disables `cpuidle/state[1-9]/disable` |
| Transparent huge pages | Adds variance to `lat_pagefault`, `lat_mmap` | `transparent_hugepage=never` |
| ASLR | Tiny systematic noise via page-table layout | `randomize_va_space=0` |
| CPU affinity | Big.LITTLE migration + cluster crossings | External `taskset -c $CORE` wraps the whole `scripts/lmbench` invocation |
| `lat_rpc` requires rpcbind | Otherwise emits errors instead of data | `prepare-host.sh` starts `rpcbind` if available |
| Page cache state between iterations | Cold-vs-warm flips for file-backed benches | **Not** flushed between iters — keeping the system warm across iterations gives lower variance than alternating cold/warm |

Pilot data (10 iters × 2 cores) confirmed MAD/median < 1.4 % across all
benchmarks once the above controls are in place, so additional cache-flushing
or sleeping between iterations is unnecessary.

## Environment matrix

| ENV_TAG          | What it is | When to run |
|------------------|-----------|--------------|
| `baremetal`      | Boot with `kvm-arm.mode=` removed from cmdline | Once, gives absolute zero point |
| `pkvm-host`      | Current default cmdline (`kvm-arm.mode=protected`), no guest | Always, gives "EL2 always-resident" baseline |
| `kvm-guest`      | QEMU/KVM guest, `kvm-arm.mode=nvhe` (reboot to switch) | Comparison vs protected guest |
| `pkvm-guest-np`  | crosvm non-protected guest under pKVM | Isolates pKVM hyp-call cost without the bounce-buffer tax |
| `pkvm-guest`     | crosvm protected guest under pKVM | The real "production pKVM" measurement |

For every environment we run `bench.sh` with the same CONFIG so the benchmark
set is identical — only the surrounding environment changes.

## Software stack (held constant across environments)

To make the host-vs-guest delta attributable purely to the hypervisor, every
layer above the hardware is held identical across `baremetal`, `kvm-guest`,
`pkvm-guest-np`, and `pkvm-guest`:

* **Kernel**: a single self-built Linux **6.6.30+** image is used as host
  kernel and as guest kernel. The kernel source lives in an internal repo.
  TODO: capture a snapshot of the build's `.config` (`zcat /proc/config.gz`
  on the target host) and commit it to `docs/kernel.config` so reviewers
  can reproduce the exact build.
* This kernel is built from the Android pKVM tree — it has both host-side
  pKVM support (`CONFIG_KVM`, `CONFIG_PROTECTED_NVHE_*`, `CONFIG_PKVM_*`)
  and the guest-side pieces needed to boot as a protected guest
  (`CONFIG_EXTRA_FIRMWARE="pvmfw.bin"`, `CONFIG_SERIAL_PKVM_PL011`,
  `CONFIG_VIRTIO_*` built-in). The same `vmlinuz` is therefore a valid
  host kernel **and** a valid (protected or non-protected) guest kernel.
  Only the boot cmdline and initramfs / rootfs differ.
* **VMM**: `crosvm` for all guest environments. Using QEMU for the KVM
  guest and crosvm for the pKVM guest would inject a VMM-implementation
  difference into every measurement — using crosvm uniformly removes it.
  pKVM protected guests require crosvm with `--protected-vm`; the other
  two guest environments use the same crosvm binary without that flag.
* **Rootfs**: one base image (read-only squashfs + tmpfs overlay) shared
  by all guests. The pKVM protected guest wraps it with a signature, but
  the file-system bytes inside are identical.
* **lmbench binaries**: built once on the host (committed in
  `bin/aarch64-Linux/`-equivalent path inside the rootfs); guests do not
  rebuild.
* **glibc / userspace**: comes from the same base image — same glibc
  version, same shell, same `coreutils`.
* **Clocksource**: every environment must report
  `arch_sys_counter` in `/sys/devices/system/clocksource/.../current_clocksource`.
  All lmbench timings flow through `clock_gettime()`; a different clocksource
  (e.g. `kvm-clock`) would change the very ruler used to measure latency.

## Benchmark coverage

`configs/CONFIG.host` enables **the full upstream lmbench suite** (equivalent
to `make rerun` with both `BENCHMARK_OS=YES` and `BENCHMARK_HARDWARE=YES`):
every category is on. The only deliberate exclusions are:

* **`DISKS=""`** — raw-block-device benchmarks (`disk`) are destructive
  (write directly to the device). Run separately on demand, never in the
  routine sweep.
* **`REMOTE=""`** — remote-networking variants would introduce physical NIC
  and link variables; we compare hypervisors, not network hardware.
* **`NETWORKS=""`** — disables `lat_select` `tcp` variant which depends on
  a usable network configuration; the `file` variant still runs.

Rationale by category (why each is in the suite and what to look at):

* **`lat_syscall` null/read/write/stat/fstat/open** — direct EL0↔EL1 trap; the
  cleanest measurement of "the cost of asking the kernel anything".
* **`lat_sig` install/catch/prot** — signal delivery + `mprotect`.
* **`lat_pipe` / `lat_unix` / `bw_pipe` / `bw_unix`** — IPC latency and bandwidth.
* **`lat_proc` fork/exec/shell** — process creation, which triggers stage-2
  page-table population in protected guests.
* **`lat_ctx` -s {0,4,8,16,32,64} {2,4,8,16,24,32,64,96}** — 6×8 grid of context-switch
  cost vs working-set size and process count; the working-set sweep separates
  "raw switch cost" from "cache pollution cost".
* **`lat_pagefault` / `lat_mmap`** size sweep — minor page faults; in a pKVM
  protected guest each first-touch can trigger stage-2 PTE allocation.
* **`lat_select -n {10,100,250,500}`** — separates per-syscall and per-fd cost.
* **`lat_udp/tcp/rpc/connect localhost`** — exercises the full protocol stack
  over loopback (no NIC variability) but still goes through `virtio` in guests.
* **`bw_tcp -m {…}` size sweep** — plotted as latency vs message size, the slope
  difference between KVM and pKVM is the per-byte cost of pKVM's shared-buffer
  bounce — likely the **largest single source of pKVM-specific overhead**.
* **`lat_mem_rd` at strides 16/32/64/128/256/512/1024 + `-t` (random)** —
  the random-stride mode at 4 KB+ stride defeats prefetchers, giving true DRAM
  latency. Compares cache-hierarchy behavior across environments; stage-2 walks
  may inflate the DRAM-segment numbers in protected guests.
* **`tlb`** — effective TLB capacity. **Critical for pKVM**: stage-2 walks
  consume TLB resource shared with the guest's stage-1.
* **`par_mem` / `stream` / STREAM2** — memory parallelism and sustained
  bandwidth. Largely insensitive to hypervisor; **included as sanity check**
  (these should be roughly identical across environments — divergence flags a
  bug in pinning or memory allocation).
* **`bw_file_rd` / `bw_mmap_rd` / `lmdd` / `lat_fs`** — disk-FS bandwidth and
  metadata operations. **For pKVM specifically these go through virtio-blk
  with bounce buffers** — likely a major source of pKVM-specific overhead, so
  must be measured. **Constraint**: `FILE` and `FSDIR` must land on a real
  disk-backed FS in the guest (not tmpfs) — otherwise virtio-blk is bypassed.
* **`bw_mem` flavors (bcopy/bzero/fcp/cp/frd/rd/fwr/wr/rdwr)** — eight
  bandwidth variants across the full size sweep. Mostly probes libc memcpy
  variants; included for completeness with `make rerun` and because pKVM
  stage-2 effects on large strided writes are worth checking even if subtle.
* **`lat_ops` / `par_ops`** — arithmetic op latency and parallelism. Pure
  user-mode ALU work; **sanity check** that hypervisor doesn't affect cycle
  cost of integer/float ops (it shouldn't — anything but ~0 difference here
  flags a frequency-lock or pinning bug).
* **`lat_http`** — HTTP throughput over loopback. The lmbench wrapper auto-
  unpacks `src/webpage-lm.tar` and starts `lmhttp` on port 8008, so guest
  setup overhead is minimal once port 8008 is free.

## Pilot vs full suite (historical note)

Before settling on driving `scripts/lmbench` directly, an earlier iteration used
a custom benchmark wrapper (`run-pilot.sh` + `run-mem.sh`). That code is kept
in the repo as a fast (~10 min) smoke test, useful for verifying that the
environment is healthy before kicking off a multi-hour `bench.sh` run.

The full `bench.sh` run with `CONFIG.host` is expected to take roughly
25–35 minutes per iteration. 10 iterations × 2 cores ≈ 9–12 hours, intended to
run overnight.

## Statistical handling (downstream of this repo)

`parse-lmbench.py` emits long-format CSV; aggregation is intentionally
out-of-band. Recommended pipeline:

1. Concatenate all `<env>-cpu*.csv` files into one master table.
2. Group by `(env, core, bench, variant)`, compute median and MAD across iters.
3. For paired comparisons (e.g. `pkvm-guest` vs `kvm-guest` on the same core),
   use per-iteration paired differences and report median + interquartile range.
4. Flag any `(env, core, bench, variant)` cell where MAD/median > 5 % as a
   data-quality issue worth investigating before reporting.

Empirically, pilot data showed MAD/median < 1.4 % on every benchmark — so a
5 % flag is loose. Tighten as needed once the full data set is in.
