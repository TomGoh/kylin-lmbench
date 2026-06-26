# Stage 0：Kaitian 能力与平台探测

本阶段仅用 stock perf 确认两件事：pKVM `lat_mmap` 退化是否**可能**在这块板卡上出现，以及
perf 原生的 EL2 归因能力（Stage 3）是否可信。完整流程见手册：
[../../../docs/mmap/perf-playbook/perf-only-mmap-investigation-playbook.zh-CN.md](../../../docs/mmap/perf-playbook/perf-only-mmap-investigation-playbook.zh-CN.md)。

在板卡上运行（需要 gcc/as/objcopy）：先执行 `make`，再执行下面的命令。

## 结果（2026-06-24，Kaitian，FTC862，内核 6.6.30-pkvm-clean，`kvm-arm.mode=protected`）

### 1. FEAT_TLBIRANGE：缺失 -> **GO**

```text
$ ./isar0
ID_AA64ISAR0_EL1 = 0x0000111110212120
  TLB[59:56] = 0 => ABSENT (no TLBIOS/TLBIRANGE)
```

`dmesg` 结果互相印证：`CPU features: detected:` 中没有 TLB-range capability，同时可以看到
`Protected KVM`。这与 N80 相同（同为 FTC862 核心）。由于缺少 range TLBI，内核在低于 2 MB 的
teardown 中会发出逐页 TLBI，因此退化机制有条件出现，复查值得继续。

### 2. `:h` EL2 计数：已验证可用

PMU 的 `:h`（EL2/hyp）修饰符被接受，并且静止状态下读数为 **0**。在已知会进入 EL2 的工作负载
下，也就是通过 pKVM hypervisor 执行 100,000 次 `KVM_RUN`，该计数器会明显亮起：

```text
$ taskset -c 0 perf stat -e cycles,cycles:u,cycles:k,cycles:h,instructions:h ./kvm_el2_probe 100000
       498,122,488      cycles
         9,292,414      cycles:u          (host EL0)
       320,200,198      cycles:k          (host EL1)
       392,139,024      cycles:h          (EL2)        <-- sleep 期间为 0，这里为 392M
       672,148,644      instructions:h    # 1.71 IPC
       0.379 s elapsed     (guest=16B KVM_RUNs=100000 mmio_exits=100000)
```

`cycles:h` 从 0 变为 392M，证明 pKVM 没有把 EL2 自计数清零。因此 Stage 3 中“munmap 时间是否花在
EL2”可以用一条 `perf stat -e cycles:h` 判断，不再需要原始调查中的自定义 EL2-cycle hypercall。

`u+k+h` 之和超过 plain `cycles` 是 perf guest/host exclusion 口径带来的预期现象；本结论只依赖
`cycles:h` 在阳性对照中显著非零。

### 3. FTC862 事件可用性

`cycles`、raw `r0024`（STALL_BACKEND），以及命名事件 `stall_backend`、`stall_frontend`、
`l1d_tlb`、`l2d_tlb_refill`、`mem_access` 均可用。**`dtlb_walk` 没有按名称暴露，需要使用 raw `r0034`。**

## 文件

- `isar0.c`：FEAT_TLBIRANGE 检测器，通过 EL0 MRS 读取 `ID_AA64ISAR0_EL1`。
- `guest.S` 与 `kvm_el2_probe.c`：最小 KVM guest 和驱动程序，用作 `:h` 的阳性对照。
- `Makefile`：编译以上三个文件。
