#!/usr/bin/env python3
# 判定一条 ARM64 CPU 能力/勘误绕过(cpucap)是否在**活内核里真正生效**。
#
# 背景(为什么需要它)：
#   .config 里 CONFIG_ARM64_WORKAROUND_xxx=y 只代表"绕过代码被编译进内核 +
#   注册了一张受影响 CPU 的 MIDR 匹配表"。是否生效是**启动时**按每个核的
#   MIDR_EL1 逐核匹配决定的——命中才置位 cpucap，再由 alternatives 就地改写
#   调用点(例如把 __tlbi() 改成"重复 tlbi + dsb")。所以"编译进来"≠"生效"。
#   本脚本直接去读内核 cpus_have_cap() 查询的同一张位图 system_cpucaps，
#   把目标位读出来——这是最硬的运行时证据。
#   完整论证见 docs/mmap/kaitian-repeat-tlbi-errata.zh-CN.md。
#
# 原理：
#   1. 从 /proc/kallsyms 取 system_cpucaps(老内核回退 cpu_hwcaps)的虚拟地址；
#   2. 把该 vaddr 按 /proc/kcore 的 ELF PT_LOAD 段翻译成文件偏移，连续读出
#      覆盖到目标位所需的若干个 unsigned long；
#   3. 测目标位；并用"对照位"自检读法是否正确——位图按 64 位分 word，**每个
#      用到的 word 都必须有一个已知真值的对照**，否则"哪里都读成 0"的 bug 会蒙混过关。
#
# 对照怎么挑(这是本脚本可信度的关键)：
#   - word0(位<64)：挑几个 dmesg 必然"detected"、因此已知为 1 的特性位
#     (CRC32/LSE/SPECTRE_V4/SSBS)。
#   - word1(位>=64)：这一段在很多核上本就全 0(全是各厂商勘误 + KABI 占位)，
#     很难找"已知为 1"的对照；退而取一个**能由独立来源预测真值**的位——
#     KPTI(ARM64_UNMAP_KERNEL_AT_EL0)，其真值可由 meltdown 漏洞 sysfs 读出。
#     (注：若 KPTI 也=0，这是 0=0 的弱一致；word1 的强保证来自"单段单次连续读"
#      ——word0 经对照证明为真，word1 是同一 read() 的相邻 8 字节，不可能只错 word1。)
#
# 位号从哪来：
#   cpucap 的位号是构建产物，见内核源码树
#   arch/arm64/include/generated/asm/cpucaps.h(每条 #define ARM64_xxx <bit>)。
#   **换内核(改 config/版本)后位号可能漂移，必须重新取。** 取法(构建主机上)：
#     grep -E 'ARM64_WORKAROUND_REPEAT_TLBI|ARM64_HAS_CRC32|...' \
#          arch/arm64/include/generated/asm/cpucaps.h
#   下面的默认值对应内核 6.6.30-pkvm-clean(Phytium/Kaitian)。
#
# 用法(目标板上需 root 读 /proc/kcore；从构建主机经 ssh 驱动最省事)：
#   # 默认：查 ARM64_WORKAROUND_REPEAT_TLBI(位 94)
#   ssh Kaitian 'cd / && sudo python3 -I -' < check-cpucap.py
#   # 查任意 cap：把 名字=位号 作为参数(可多个)
#   ssh Kaitian 'cd / && sudo python3 -I -' < check-cpucap.py ARM64_WORKAROUND_SPECULATIVE_AT=95
#   # 或拷到板上直接跑
#   scp check-cpucap.py Kaitian:/tmp/ && ssh Kaitian 'cd / && sudo python3 -I /tmp/check-cpucap.py'
#
# 可覆盖环境变量：
#   SYM       能力位图符号名(默认 system_cpucaps，自动回退 cpu_hwcaps)
#   CONTROLS  word0 已知为 1 的对照，逗号分隔的 名字:位号
#             (默认 HAS_CRC32:14,HAS_LSE_ATOMICS:33,SPECTRE_V4:60,SSBS:62)
#   KPTI_BIT  word1 的 KPTI 对照位(默认 64；设为 -1 关闭该对照)
#
# 退出码：0=读取成功且对照自检通过；2=对照自检失败(读法可疑，结论不可信)；
#         1=运行错误(非 root / 符号缺失 / 段未覆盖等)。

import os, struct, sys

def die(msg, code=1):
    print("ERROR: " + msg, file=sys.stderr); sys.exit(code)

# ---- 解析参数：目标 cap(名字=位号) ----
targets = {}
for a in sys.argv[1:]:
    if "=" not in a: die("参数应为 名字=位号，收到: %r" % a)
    n, b = a.split("=", 1); targets[n] = int(b, 0)
if not targets:
    targets = {"ARM64_WORKAROUND_REPEAT_TLBI": 94}   # 默认目标(6.6.30-pkvm-clean)

# ---- word0 对照(已知为 1) ----
controls = {}
for pair in os.environ.get("CONTROLS",
        "HAS_CRC32:14,HAS_LSE_ATOMICS:33,SPECTRE_V4:60,SSBS:62").split(","):
    n, b = pair.split(":"); controls[n] = int(b, 0)
kpti_bit = int(os.environ.get("KPTI_BIT", "64"))

# ---- 1. 从 kallsyms 取位图符号地址(root 才看得到真地址) ----
sym_pref = os.environ.get("SYM", "system_cpucaps")
addr = None; sym_used = None
with open("/proc/kallsyms") as k:
    table = {p[2]: int(p[0], 16) for p in (ln.split() for ln in k) if len(p) >= 3}
for cand in (sym_pref, "system_cpucaps", "cpu_hwcaps"):
    if table.get(cand):           # 非 0 才算可见
        addr, sym_used = table[cand], cand; break
if addr is None:
    die("在 /proc/kallsyms 找不到 %s(需 root，且 kptr_restrict 下普通用户读到的是 0)" % sym_pref)

# ---- 需要读多少个 word：覆盖到用到的最高位 ----
all_bits = list(targets.values()) + list(controls.values())
if kpti_bit >= 0: all_bits.append(kpti_bit)
nwords = max(all_bits) // 64 + 1

# ---- 2. vaddr -> /proc/kcore 文件偏移(解析 ELF PT_LOAD) ----
with open("/proc/kcore", "rb") as f:
    h = f.read(64)
    if h[:4] != b"\x7fELF": die("/proc/kcore 不是 ELF")
    e_phoff = struct.unpack_from("<Q", h, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", h, 0x36)[0]
    e_phnum = struct.unpack_from("<H", h, 0x38)[0]
    f.seek(e_phoff); ph = f.read(e_phentsize * e_phnum)
    foff = None
    for i in range(e_phnum):
        b = i * e_phentsize
        if struct.unpack_from("<I", ph, b)[0] != 1:        # PT_LOAD
            continue
        p_offset = struct.unpack_from("<Q", ph, b + 8)[0]
        p_vaddr  = struct.unpack_from("<Q", ph, b + 16)[0]
        p_filesz = struct.unpack_from("<Q", ph, b + 32)[0]
        p_memsz  = struct.unpack_from("<Q", ph, b + 40)[0]
        # 必须 filesz 覆盖全部要读的字节，否则不接受该段(防越界读到错数据)
        if p_vaddr <= addr < p_vaddr + p_memsz and (addr - p_vaddr) + nwords * 8 <= p_filesz:
            foff = p_offset + (addr - p_vaddr); break
    if foff is None:
        die("没有 file-backed 的 PT_LOAD 段覆盖 0x%x 的全部 %d 字节" % (addr, nwords * 8))
    f.seek(foff); raw = f.read(nwords * 8)
if len(raw) != nwords * 8:
    die("kcore 读取不足：要 %d 字节，得 %d" % (nwords * 8, len(raw)))

words = struct.unpack("<%dQ" % nwords, raw)
def bit(n): return (words[n // 64] >> (n % 64)) & 1

# ---- 3. 自检 + 报告 ----
print("%s @ 0x%016x  (活读自 /proc/kcore，共 %d word)" % (sym_used, addr, nwords))
print("  raw: " + raw.hex())
for w in range(nwords):
    print("  word[%d] = 0x%016x" % (w, words[w]))
print()

ok = True
print("word0 对照(应全为 1)：")
for n, b in controls.items():
    v = bit(b); ok = ok and v == 1
    print("  bit %3d  %-22s = %d%s" % (b, n, v, "" if v == 1 else "   <-- 异常!"))

if kpti_bit >= 0:
    try:
        melt = open("/sys/devices/system/cpu/vulnerabilities/meltdown").read().strip()
    except OSError:
        melt = "(读不到)"
    exp = 1 if "PTI" in melt else 0
    v = bit(kpti_bit); match = (v == exp)
    print("word1 对照(KPTI vs meltdown sysfs)：")
    print("  bit %3d  KPTI(UNMAP_KERNEL_AT_EL0) = %d   meltdown=%r 期望=%d   -> %s"
          % (kpti_bit, v, melt, exp, "一致" if match else "不一致 <-- 异常!"))
    ok = ok and match

print()
print("================ 目标 cap ================")
for n, b in targets.items():
    v = bit(b)
    print("  bit %3d  %-32s = %d   -> %s"
          % (b, n, v, "ENABLED / 生效中" if v else "编译进内核但 DORMANT / 未生效"))

print()
if not ok:
    print("自检失败：对照位与预期不符，读法可疑，上面结论不可信。", file=sys.stderr)
    sys.exit(2)
print("自检通过：word0 对照全为 1，word1 KPTI 对照一致 —— 目标位读数可信。")
