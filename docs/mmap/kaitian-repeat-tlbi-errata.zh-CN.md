# Kaitian 勘误判定：`ARM64_WORKAROUND_REPEAT_TLBI` 编译进内核但**运行时未生效**

**平台**：Kaitian（Phytium）/ Kylin V10 SP1 / aarch64 / `6.6.30-pkvm-clean`（Rust nVHE hyp，pKVM protected）
**日期**：2026-06-16
**结论一句话**：`.config` 里 `CONFIG_ARM64_WORKAROUND_REPEAT_TLBI=y` 只代表**把这条勘误绕过代码编译进了内核**；它在 Kaitian 上**没有生效**——因为该绕过是按 CPU 的 `MIDR` 白名单在启动时逐核匹配启用的，而 Kaitian 是 Phytium 核（`MIDR_EL1=0x700f8620`），不在白名单内。三条独立证据一致：MIDR 不匹配（决定性）、dmesg 未检测到该勘误、活内核 `system_cpucaps` 位 94 = 0。

> **为什么这件事重要**：这条绕过一旦生效，会把 `__tlbi()` 改写成"**两条 `tlbi` + `dsb`**"的重复序列，等于把每一次 TLB 作废的成本**翻倍**。我们整条 C0/C1 推理链（[c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md)）的核心结论是"pKVM 的 munmap 退化 = 逐页 TLBI 的 stage-2 硬件税（a-1）"。如果测量平台上恰好启用了 REPEAT_TLBI，那测到的"每条 TLBI 更贵"就有一部分是被这条绕过人为放大的——这会是一个**致命的混淆变量**。本篇就是把这个混淆变量从 Kaitian 上**排除掉**。

---

## 0. 为什么要写这篇：把"编译进内核"和"运行时生效"分开

很容易犯的一个错：在 `.config` 里 `grep` 到 `CONFIG_ARM64_WORKAROUND_REPEAT_TLBI=y`，就以为这条绕过在板子上"开着"。**这是错的**。

ARM64 的 CPU 勘误（errata）绕过走的是 **capability（cpucap）框架**：

- `CONFIG_..._REPEAT_TLBI=y` 做的事只有两件——把绕过代码**编译进内核**，并**注册一张受影响 CPU 的 `MIDR` 匹配表**；
- 真正"开不开"是在**启动时**决定的：内核拿**每个在线核的 `MIDR_EL1`** 去比对那张表，**只有命中**才把对应的 cpucap 置位，进而通过 alternatives 机制**就地改写** `__tlbi()` 调用点。

所以"是否生效"这个问题，等价于一个可判定的事实问题：

> **Kaitian 的 CPU `MIDR` 落不落在这条勘误的匹配表里?**

本篇的价值不只是给出"否"这个答案,而是给出**三条互相独立、强度递增的验证路径**,并解释**每一条为什么这样设计、各自排除了什么**——尤其是最后那条"直接读活内核能力位图"里,对照变量是怎么挑的、为什么这么挑。

---

## 1. 这条绕过是给谁用的(源码事实)

匹配表 `arm64_repeat_tlbi_list[]`,见 `arch/arm64/kernel/cpu_errata.c:214`。由四条勘误 `select`(均 `default y`,见 `arch/arm64/Kconfig`):

| Kconfig 勘误 | 受影响 CPU | 厂商(implementer) |
|---|---|---|
| `ARM64_ERRATUM_2441007` | Cortex-A55(全版本) | ARM `0x41` |
| `ARM64_ERRATUM_1286807` | Cortex-A76 `r0p0–r3p0`、Kryo4xx Gold | ARM `0x41` / Qualcomm `0x51` |
| `ARM64_ERRATUM_2441009` | Cortex-A510 `r0p0–r1p1` | ARM `0x41` |
| `QCOM_FALKOR_ERRATUM_1009` | Falkor v1、Kryo | Qualcomm `0x51` |

**关键观察**:整张表里只有 **ARM(`0x41`)** 和 **Qualcomm(`0x51`)** 两个 implementer。任何其它厂商的核都**不可能命中**。

对应的 capability 条目(`cpu_errata.c:542`):

```c
#ifdef CONFIG_ARM64_WORKAROUND_REPEAT_TLBI
{
    .desc = "Qualcomm erratum 1009, or ARM erratum 1286807, 2441009",
    .capability = ARM64_WORKAROUND_REPEAT_TLBI,
    .type = ARM64_CPUCAP_LOCAL_CPU_ERRATUM,      // 逐核本地匹配
    .matches = cpucap_multi_entry_cap_matches,
    .match_list = arm64_repeat_tlbi_list,
},
#endif
```

`.desc` 非空这一点后面会用到(方法二)。

---

## 2. 方法一 —— MIDR 比对匹配表(**决定性**)

**为什么这条是决定性的**:这不是"旁证",而是**复现内核自己在启动时做的那次判断**。内核启用 cpucap 的判据就是"`MIDR` ∈ 匹配表",我们手动算一遍这个集合归属,结论与内核**逐位等价**。

读 Kaitian 实际的 `MIDR_EL1`(来自 sysfs,是寄存器原值,比 `/proc/cpuinfo` 解码更可靠):

```
$ cat /sys/devices/system/cpu/cpu*/regs/identification/midr_el1 | sort | uniq -c
      8 0x00000000700f8620          # 8 核全部相同
```

解码 `0x700f8620`:

| 字段 | 位 | 值 | 含义 |
|---|---|---|---|
| Implementer | [31:24] | `0x70` | **Phytium(飞腾)** |
| Variant | [23:20] | `0x0` | r0 |
| Architecture | [19:16] | `0xf` | 由 ID 寄存器定义 |
| PartNum | [15:4] | `0x862` | Phytium 核型号 |
| Revision | [3:0] | `0x0` | p0 |

→ implementer `0x70` ∉ {`0x41`, `0x51`}。**Phytium 核不在、也不可能在 `arm64_repeat_tlbi_list[]` 里**,内核启动时对 8 个核逐一比对都不会命中 → cpucap 不置位 → `__tlbi()` 调用点**不会被改写**。

**仅凭这一条,结论已经成立。** 下面两条是把同一结论从"源码推理"提升到"活内核直接观测"。

---

## 3. 方法二 —— dmesg 启动日志(旁证,带一个前提)

**这条为什么能用、前提是什么**:内核在启动检测每个 cpucap 时,若该条目 `.desc != NULL`,会打印一行 `CPU features: detected: <desc>`。第 1 节已确认 REPEAT_TLBI 条目的 `.desc` **非空**,所以**如果它被启用,启动日志里必然出现** `Qualcomm erratum 1009, or ARM erratum 1286807, 2441009`。于是"日志里没有这行"就是一个**有效**的反证(对 `.desc==NULL` 的 cap 这招无效,这是它的适用前提)。

Kaitian 的检测块(uptime 几分钟、`loglevel=7`,缓冲区完整):

```
CPU features: detected: GIC system register CPU interface
CPU features: detected: Spectre-v4
CPU features: detected: 32-bit EL0 Support
CPU features: detected: Data cache clean to the PoU not required for I/D coherence
CPU features: detected: CRC32 instructions
CPU features: detected: RCpc load-acquire (LDAPR)
CPU features: detected: LSE atomic instructions
CPU features: detected: Speculative Store Bypassing Safe (SSBS)
```

全是正常特性,**没有任何一条勘误绕过**(更没有 REPEAT_TLBI 那行)→ 与方法一一致。

---

## 4. 方法三 —— 直接读活内核的能力位图(`/proc/kcore`)

**为什么还要这条**:方法一是源码推理,方法二是间接日志。最硬的证据是**直接去活内核里把那一位读出来**——读 `cpus_have_cap()` 所查询的同一张位图 `system_cpucaps`,看第 94 位(`ARM64_WORKAROUND_REPEAT_TLBI`,位号取自构建产物 `arch/arm64/include/generated/asm/cpucaps.h`)。

`system_cpucaps` 是 `DECLARE_BITMAP(.., ARM64_NCAPS=117)`,即 2 个 `unsigned long`(16 字节)。位 94 落在 **word[1]**(94/64=1,位内偏移 30)。

做法(非侵入,不污染内核、不加载模块):root 下从 `/proc/kallsyms` 取符号地址,按 `/proc/kcore` 的 ELF `PT_LOAD` 段把虚拟地址翻译成文件偏移,读 16 字节。结果:

```
system_cpucaps @ 0xffff8000827f3638
  word0 = 0x500000031000520b
  word1 = 0x0000000000000000
  bit 94  ARM64_WORKAROUND_REPEAT_TLBI = 0      ← 未启用
```

### 4.1 对照变量怎么挑的(这是本方法的"论证"所在)

读出 0 不能直接信——**得先证明"我的读法是对的、不是把哪里都读成 0"**。位图分两个 word,必须**两个 word 各有一个已知真值的对照**:

- **word[0] 的对照(挑"已知为 1"的)**:从第 3 节 dmesg 已确认开启的特性里挑四个,它们的位号都 < 64,落在 word[0]:

  | cap | 位 | 期望 | 读到 |
  |---|---|---|---|
  | `ARM64_HAS_CRC32` | 14 | 1 | **1** |
  | `ARM64_HAS_LSE_ATOMICS` | 33 | 1 | **1** |
  | `ARM64_SPECTRE_V4` | 60 | 1 | **1** |
  | `ARM64_SSBS` | 62 | 1 | **1** |

  四个全中 → word[0] 的读法正确。(顺带:`ARM64_SPECTRE_BHB`=61 读到 **0**,与 Phytium 不受 BHB 影响一致。)

- **word[1] 的对照(难点)**:目标位 94 在 word[1],可 word[1] 整个是 0。这一段位号(64–116)**全是各类勘误绕过 + 没用上的 `ANDROID_KABI_RESERVE` 占位**,在 Phytium 上预期**本就全 0**——所以**找不到一个"已知为 1"的 word[1] 对照**。退而求其次,挑一个**能从独立来源预测其真值**的 word[1] 位:`ARM64_UNMAP_KERNEL_AT_EL0`(位 64,即 KPTI),它的开关可由 meltdown 漏洞 sysfs 独立读出:

  ```
  /sys/devices/system/cpu/vulnerabilities/meltdown = "Not affected"   → KPTI 期望 = 0
  读到 bit 64 = 0                                                       → 一致
  ```

  > 诚实地说:这是一个 **0=0 的一致性**(不如"1"那么强,因为"哪里都读成 0"的 bug 也会通过)。所以 word[1] 的可信度**主要靠下面的构造性论证**,KPTI 只是锦上添花。

### 4.2 为什么 word[1]=0 是真的(构造性论证)

读取是**一次** `f.read(16)`,再 `struct.unpack("<2Q", buf)`——若返回不足 16 字节会直接抛异常;且代码**要求** `PT_LOAD` 段的 `p_filesz` 覆盖全部 16 字节才接受该段。于是:

- word[0] 由四个对照证明是**真实的 `system_cpucaps[0]`**;
- word[1] 就是**同一个缓冲区的第 8–15 字节**,与 word[0] 物理连续、同段同次读出。

word[0] 对而 word[1] 错,在这种"单段单次连续读"下**不可能发生**。故 word[1]=0 为真,位 94=0 可信。

---

## 5. 结论与对 bug930 的意义

**结论**:`ARM64_WORKAROUND_REPEAT_TLBI` 在 Kaitian(Phytium `0x700f8620`)上**编译进内核但运行时休眠、未生效**。`__tlbi()` 走的是**单条 TLBI** 路径,绕过那段"重复 `tlbi` + `dsb`"**没有被 alternatives 打补丁打进去**。

**对测量的意义**:Kaitian 上测到的 pKVM stage-2 逐页 TLBI 成本是**干净的**,**没有**被 REPEAT_TLBI 绕过翻倍。这就把一个潜在混淆变量从 C1(a-1)结论里排除了——"每条 host TLBI 在 stage-2 下更贵"是 stage-2 本身的硬件税,不是这条勘误绕过制造的假象。

> **跨平台警告**:**同一个内核二进制**若启动在受影响的 ARM 核上(典型如 **Cortex-A76 `r0p0–r3p0`**),REPEAT_TLBI 会**自动生效**,把每条广播 TLBI 翻倍。所以**换板子做对比前,必须按本篇方法逐机重测这一位**,不能假设"同一镜像 ⇒ 同样行为"。N80 等其它板若也要纳入 TLBI 成本对比,应先跑一遍第 6 节的判定流程确认其 `MIDR` 与本位状态(本篇只实测了 Kaitian,未对 N80 下结论)。

---

## 6. 附:判定任意一条 ARM64 勘误是否"运行时生效"的通用配方

1. **查编译**:`grep <CONFIG_符号> /boot/config-$(uname -r)`(确认编进来了);
2. **读匹配表**(决定性):在 `arch/arm64/kernel/cpu_errata.c` 找该 cap 的 `.match_list`,看覆盖哪些 `MIDR`;
3. **读真 MIDR**:`cat /sys/devices/system/cpu/cpu*/regs/identification/midr_el1`,判断是否落在表内——**这一步等价于内核启动时的判断**;
4. **活内核确认**(可选,最硬):从 `arch/arm64/include/generated/asm/cpucaps.h` 取位号,root 读 `/proc/kcore` 里的 `system_cpucaps` 测该位;**务必给 word[0] 和 word[1] 各挑一个已知真值的对照**验证读法;
5. **旁证**:dmesg `CPU features: detected:` 块(仅对 `.desc != NULL` 的 cap 有效)。

> 若需要第四条更强的 API 级确认(直接调内核 `this_cpu_has_cap()`),可写一个极小的 out-of-tree 模块——本机 `CONFIG_MODULE_SIG_FORCE` 未开、无 lockdown,可加载,但会给内核打 taint 标记,非必要不做(方法一已是决定性)。

### 实测命令清单(Kaitian)

```bash
# MIDR(8 核)
ssh Kaitian 'cat /sys/devices/system/cpu/cpu*/regs/identification/midr_el1 | sort | uniq -c'

# dmesg 勘误检测
ssh Kaitian 'sudo dmesg | grep -iE "errat|CPU features: detected"'

# 运行内核 config
ssh Kaitian 'grep ARM64_WORKAROUND_REPEAT_TLBI /boot/config-$(uname -r)'

# 活内核 system_cpucaps 位 94 —— 用固化脚本(自带 word0/word1 对照自检,退出码 0=可信)
ssh Kaitian 'cd / && sudo python3 -I -' < docs/mmap/scripts/check-cpucap.py
# 查任意 cap:名字=位号 作参数(位号取自 arch/arm64/include/generated/asm/cpucaps.h)
ssh Kaitian 'cd / && sudo python3 -I -' < docs/mmap/scripts/check-cpucap.py ARM64_WORKAROUND_SPECULATIVE_AT=95
```

---

*关联文档：[c1-tlbi-threshold.zh-CN.md](c1-tlbi-threshold.zh-CN.md)(TLBI 是 munmap 退化主因的机制判定)、[mmap-split-kaitian-pkvm-comparison.zh-CN.md](mmap-split-kaitian-pkvm-comparison.zh-CN.md)、[lmdb-kaitian-nvhe-pkvm-results.zh-CN.md](lmdb-kaitian-nvhe-pkvm-results.zh-CN.md)。*
