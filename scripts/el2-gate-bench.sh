#!/bin/bash
# Patch B gate 实验：判别 munmap_after_write_touch 窗口的额外时间是否进入 EL2
#
# 原理：/proc/xcore_stats（CONFIG_XCORE_STATS=y 内核）的 PMCCFILTR_EL0 配置为
# 只统计 EL2 cycles，PMCCNTR_EL0 即每 CPU 的 EL2 累计周期。窗口前后取同一 CPU
# 的 delta，并用等时长空窗扣除背景噪声。
#
# 读数路径说明：`echo 1` = 必要时 enable（HVC，仅首次）+ 在所有 CPU 上以 EL1
# read_sysreg 读 PMCCNTR（不进 EL2），因此读数本身对 EL2 cycle 的污染≈0。
#
# 用法（Kaitian 板上，普通用户即可，/proc/xcore_stats 是 0666）：
#   CORE=0 SIZES="8 16 64" ITERS=100 ./el2-gate-bench.sh <输出目录>
# 可覆盖变量：
#   BENCH   benchmark 二进制（默认 ~/kylin-lmbench/experiments/mmap-split/mmap_split_bench）
#   MODE_ARG benchmark 模式（默认 munmap_after_write_touch）
#   FILE    backing 文件路径（默认 <输出目录>/backing.bin，自动 dd 填充）
set -eu

OUT=${1:?usage: el2-gate-bench.sh <outdir>}
CORE=${CORE:-0}
SIZES=${SIZES:-"8 16 64"}            # MB
ITERS=${ITERS:-100}
TOUCH_DIV=${TOUCH_DIV:-10}
STRIDE_KB=${STRIDE_KB:-16}
WARMUPS=${WARMUPS:-1}
MODE_ARG=${MODE_ARG:-munmap_after_write_touch}
BENCH=${BENCH:-$HOME/kylin-lmbench/experiments/mmap-split/mmap_split_bench}
PROC=/proc/xcore_stats

mkdir -p "$OUT"
FILE=${FILE:-$OUT/backing.bin}

[ -x "$BENCH" ] || { echo "ERROR: benchmark 不存在: $BENCH" >&2; exit 1; }
[ -w "$PROC" ] || {
    echo "ERROR: $PROC 不存在或不可写（需要 CONFIG_XCORE_STATS=y 内核，且非 VHE/mode=none）" >&2
    exit 1
}

KVM_MODE=$(grep -o 'kvm-arm.mode=[a-z]*' /proc/cmdline | cut -d= -f2)
KVM_MODE=${KVM_MODE:-default}

restore_cpuidle=""
cleanup() {
    # PMU 状态兜底恢复（Patch A2 内核会 per-cpu 恢复原 PMU 配置）
    echo 0 > "$PROC" 2>/dev/null || true
    for f in $restore_cpuidle; do
        echo 0 > "$f" 2>/dev/null || true
    done
}
trap cleanup EXIT

# 关目标 CPU 的 cpuidle（PSCI SMC 会计入 EL2 cycles）。Kaitian 无 cpuidle 目录，
# 此循环自动跳过；有 cpuidle 的板子需要 root 跑本脚本。
for f in /sys/devices/system/cpu/cpu"$CORE"/cpuidle/state*/disable; do
    [ -e "$f" ] || continue
    echo 1 > "$f" && restore_cpuidle="$restore_cpuidle $f"
done

read_el2_cycles() {
    echo 1 > "$PROC"
    awk -v cpu="$CORE" '$1 == cpu { print $2 }' "$PROC"
}

# 准备 backing 文件（取最大 size，dd 填满避免 sparse）
max_mb=0
for s in $SIZES; do [ "$s" -gt "$max_mb" ] && max_mb=$s; done
if [ ! -f "$FILE" ] || [ "$(stat -c %s "$FILE")" -lt $((max_mb * 1024 * 1024)) ]; then
    dd if=/dev/zero of="$FILE" bs=1M count="$max_mb" conv=fsync status=none
fi

cpu_khz=$(cat /sys/devices/system/cpu/cpu"$CORE"/cpufreq/scaling_cur_freq 2>/dev/null || echo "")
CSV="$OUT/el2-gate-${KVM_MODE}.csv"
echo "mode,bench,size_mb,iters,el2_cycles_delta,el2_cycles_empty,el2_cycles_net,wall_s,cpu_khz" > "$CSV"

echo "== EL2 gate: mode=$KVM_MODE core=$CORE bench=$MODE_ARG iters=$ITERS =="

# 首次 enable（含 HVC），与正式窗口分离
echo 1 > "$PROC"

for size in $SIZES; do
    log="$OUT/bench-${MODE_ARG}-${size}mb-${KVM_MODE}.log"

    # --- benchmark 窗口 ---
    c0=$(read_el2_cycles)
    t0=$(date +%s.%N)
    taskset -c "$CORE" "$BENCH" "$MODE_ARG" "$size" "$ITERS" "$FILE" \
        "$TOUCH_DIV" "$STRIDE_KB" "$WARMUPS" > "$log" 2>&1
    t1=$(date +%s.%N)
    c1=$(read_el2_cycles)
    wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN { printf "%.3f", b - a }')
    delta=$((c1 - c0))

    # --- 等时长空窗对照（扣除背景 EL2 活动）---
    e0=$(read_el2_cycles)
    sleep "$wall"
    e1=$(read_el2_cycles)
    empty=$((e1 - e0))

    net=$((delta - empty))
    echo "$KVM_MODE,$MODE_ARG,$size,$ITERS,$delta,$empty,$net,$wall,$cpu_khz" >> "$CSV"
    printf "size=%3s MB  ΔEL2=%-12s 空窗=%-10s 净值=%-12s wall=%ss\n" \
        "$size" "$delta" "$empty" "$net" "$wall"
done

echo
echo "结果: $CSV"
echo "判读: 净值 cycles / (iters) = 每次迭代的 EL2 周期；与该 size 下 pKVM 相对"
echo "      NVHE 的额外时间（us/iter × CPU GHz ≈ 额外 cycles/iter）对比："
echo "      净值远小于额外开销（<5%）→ EL2 不是主因（假设 a，走 C1）"
echo "      净值与额外开销量级可比 → 隐藏 EL2 路径（假设 b，走 C2）"
