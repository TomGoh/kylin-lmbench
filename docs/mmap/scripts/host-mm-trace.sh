#!/bin/bash
# Patch C0：host 侧 munmap teardown 对照观测（nvhe 与 pkvm 跑同一套，对比同函数耗时膨胀）
#
# 子命令：
#   tlbirange <outdir>   读 ID_AA64ISAR0_EL1.TLB（MRS 仿真），确认 FEAT_TLBIRANGE
#   funcgraph <outdir>   function_graph 抓 __vm_munmap 子树（需要 root + 插桩内核）
#   perf      <outdir>   perf stat TLB/walk 事件（与 /proc/xcore_stats PMU 不可同窗）
#   all       <outdir>   依次全跑
#
# 用法（Kaitian 板上）：
#   sudo CORE=0 SIZE=64 ITERS=50 ./host-mm-trace.sh all /tmp/c0-out
#
# 注意：funcgraph 本身有显著开销，绝对值只用于 nvhe vs pkvm 的**相对**比较
# （两个模式都开同样的 trace 配置）。
set -eu

CMD=${1:?usage: host-mm-trace.sh <tlbirange|funcgraph|perf|all> <outdir>}
OUT=${2:?usage: host-mm-trace.sh <tlbirange|funcgraph|perf|all> <outdir>}
CORE=${CORE:-0}
SIZE=${SIZE:-64}
ITERS=${ITERS:-50}
TOUCH_DIV=${TOUCH_DIV:-10}
STRIDE_KB=${STRIDE_KB:-16}
WARMUPS=${WARMUPS:-1}
MODE_ARG=${MODE_ARG:-munmap_after_write_touch}
BENCH=${BENCH:-$HOME/kylin-lmbench/experiments/mmap-split/mmap_split_bench}
MAXDEPTH=${MAXDEPTH:-12}   # 需够深以覆盖 __vm_munmap→…→zap_pte_range
# tracefs 可能在 /sys/kernel/tracing(直接挂)或 /sys/kernel/debug/tracing
# (Kylin V10 把 tracefs 挂在 debugfs 下)。自动探测,允许 TRACEFS= 覆盖。
T=${TRACEFS:-}
if [ -z "$T" ]; then
    for cand in /sys/kernel/debug/tracing /sys/kernel/tracing; do
        [ -e "$cand/current_tracer" ] && { T=$cand; break; }
    done
fi
T=${T:-/sys/kernel/debug/tracing}

mkdir -p "$OUT"
FILE=${FILE:-$OUT/backing.bin}
KVM_MODE=$(grep -o 'kvm-arm.mode=[a-z]*' /proc/cmdline | cut -d= -f2)
KVM_MODE=${KVM_MODE:-default}

prep_file() {
    [ -x "$BENCH" ] || { echo "ERROR: benchmark 不存在: $BENCH" >&2; exit 1; }
    if [ ! -f "$FILE" ] || [ "$(stat -c %s "$FILE")" -lt $((SIZE * 1024 * 1024)) ]; then
        dd if=/dev/zero of="$FILE" bs=1M count="$SIZE" conv=fsync status=none
    fi
}

run_bench() {
    taskset -c "$CORE" "$BENCH" "$MODE_ARG" "$SIZE" "$ITERS" "$FILE" \
        "$TOUCH_DIV" "$STRIDE_KB" "$WARMUPS"
}

do_tlbirange() {
    # arm64 内核对 EL0 的 ID 寄存器 MRS 做仿真，可直接在用户态读 sanitised 值
    local src="$OUT/tlbirange-check.c" bin="$OUT/tlbirange-check"
    cat > "$src" <<'EOF'
#include <stdio.h>
int main(void)
{
    unsigned long isar0;
    asm("mrs %0, ID_AA64ISAR0_EL1" : "=r"(isar0));
    unsigned long tlb = (isar0 >> 56) & 0xf;
    printf("ID_AA64ISAR0_EL1 = 0x%016lx\n", isar0);
    printf("TLB field [59:56] = %lu  (0=none, 1=TLBI-OS, 2=TLBI-OS+RANGE)\n", tlb);
    printf("FEAT_TLBIRANGE: %s\n", tlb >= 2 ? "YES (内核可用 RVAE1IS range TLBI)"
                                            : "NO (逐页 TLBI 或升级为 ASID flush)");
    return 0;
}
EOF
    gcc -O0 -o "$bin" "$src"
    "$bin" | tee "$OUT/tlbirange-$KVM_MODE.txt"
}

do_funcgraph() {
    [ "$(id -u)" = 0 ] || { echo "ERROR: funcgraph 需要 root" >&2; exit 1; }
    [ -d "$T" ] || { echo "ERROR: $T 不存在" >&2; exit 1; }
    grep -q function_graph "$T/available_tracers" || {
        echo "ERROR: 内核无 function_graph（需要 Patch A1 的插桩配置内核）" >&2; exit 1; }
    prep_file

    # 选 munmap 入口：按内核版本在候选里取第一个可用的
    local entry=""
    for f in __vm_munmap do_vmi_munmap __do_sys_munmap; do
        if grep -qx "$f" "$T/available_filter_functions"; then entry=$f; break; fi
    done
    [ -n "$entry" ] || { echo "ERROR: 找不到 munmap 入口函数" >&2; exit 1; }
    echo "graph entry: $entry"

    cleanup_fg() {
        echo 0 > "$T/tracing_on" 2>/dev/null || true
        echo nop > "$T/current_tracer" 2>/dev/null || true
        echo > "$T/set_graph_function" 2>/dev/null || true
        echo > "$T/set_ftrace_pid" 2>/dev/null || true
    }
    trap cleanup_fg EXIT

    echo nop > "$T/current_tracer"
    echo 0 > "$T/tracing_on"
    echo "$entry" > "$T/set_graph_function"
    echo "$MAXDEPTH" > "$T/max_graph_depth"
    # 跟随子进程（benchmark 由 taskset fork）
    [ -e "$T/options/function-fork" ] && echo 1 > "$T/options/function-fork"
    # funcgraph-tail：在 "}" 闭合行打印 /* 函数名 */。否则非叶函数
    # (unmap_vmas/zap_pte_range/free_pgtables 等)的耗时无法按名归集，
    # 汇总只会看到叶子(如 tlb_finish_mmu)。
    [ -e "$T/options/funcgraph-tail" ] && echo 1 > "$T/options/funcgraph-tail"
    echo $$ > "$T/set_ftrace_pid"
    echo function_graph > "$T/current_tracer"
    echo > "$T/trace"

    # funcgraph 事件量极大：默认主 tracefs 缓冲区(~1.4MB/cpu)会被 50 iter 的
    # munmap 子树瞬间冲掉，只剩末尾几条 → 汇总失真。对策：只给目标 CPU 调大
    # per-cpu 缓冲区(不影响其它核内存)，并把 funcgraph 迭代降到少量(per-function
    # 时长取平均，几次即可代表)。FG_ITERS / FG_BUF_KB 可覆盖。
    local fg_iters=${FG_ITERS:-5}
    local pcbuf="$T/per_cpu/cpu$CORE/buffer_size_kb"
    local orig_buf; orig_buf=$(cat "$pcbuf" 2>/dev/null)
    echo "${FG_BUF_KB:-65536}" > "$pcbuf" 2>/dev/null || true
    echo "funcgraph: cpu$CORE buffer=$(cat "$pcbuf" 2>/dev/null)KB iters=$fg_iters"
    echo > "$T/trace"

    echo 1 > "$T/tracing_on"
    taskset -c "$CORE" "$BENCH" "$MODE_ARG" "$SIZE" "$fg_iters" "$FILE" \
        "$TOUCH_DIV" "$STRIDE_KB" "$WARMUPS" > "$OUT/bench-funcgraph-$KVM_MODE.log" 2>&1
    echo 0 > "$T/tracing_on"

    local trace="$OUT/funcgraph-$MODE_ARG-${SIZE}mb-$KVM_MODE.txt"
    # 只取目标 CPU 的 buffer，避免其它核噪声；读完再恢复 buffer 大小
    cat "$T/per_cpu/cpu$CORE/trace" > "$trace"
    [ -n "$orig_buf" ] && echo "$orig_buf" > "$pcbuf" 2>/dev/null || true
    cleanup_fg
    trap - EXIT

    # 汇总关键函数耗时（leaf 形如 "fn();" 同行带时长；非 leaf 时长在 "} /* fn */" 行）
    local summary="$OUT/funcgraph-summary-$KVM_MODE.txt"
    {
        echo "== funcgraph summary: mode=$KVM_MODE $MODE_ARG ${SIZE}MB x$fg_iters (depth<=$MAXDEPTH) =="
        for fn in "$entry" unmap_region unmap_vmas free_pgtables tlb_finish_mmu \
                  zap_pte_range zap_pmd_range tlb_flush_mmu __flush_tlb_range_nosync; do
            grep -E "(\} /\* ${fn} \*/|[ (]${fn}\(\);)" "$trace" 2>/dev/null | \
            awk -v fn="$fn" '{
                for (i = 1; i <= NF; i++) if ($i == "us") { d = $(i-1); sub(/^\+/, "", d) }
                if (d != "") { n++; s += d; if (d > mx) mx = d }
            } END {
                if (n) printf "%-28s calls=%-8d total=%.1f us  avg=%.2f us  max=%.1f us\n",
                              fn, n, s, s/n, mx
            }'
        done
    } | tee "$summary"
    echo "完整 trace: $trace"
}

do_perf() {
    prep_file
    if [ -w /proc/xcore_stats ]; then
        echo "（先 echo 0 > /proc/xcore_stats，避免与 EL2 PMU 配置冲突）"
        echo 0 > /proc/xcore_stats 2>/dev/null || true
    fi
    local out="$OUT/perf-$MODE_ARG-${SIZE}mb-$KVM_MODE.txt"
    # dtlb_walk 未在本机 sysfs 暴露命名事件，用裸码 r34（=DTLB_WALK，0x34）。
    # l1d_tlb_refill/l2d_tlb_refill/stall_backend 已由 PMU 驱动经 sysfs 暴露，按名可用。
    perf stat -e cycles,instructions,page-faults,l1d_tlb_refill,l2d_tlb_refill,r34,stall_backend \
        -o "$out" -- taskset -c "$CORE" "$BENCH" "$MODE_ARG" "$SIZE" "$ITERS" "$FILE" \
        "$TOUCH_DIV" "$STRIDE_KB" "$WARMUPS" > "$OUT/bench-perf-$KVM_MODE.log" 2>&1
    cat "$out"
}

case "$CMD" in
    tlbirange) do_tlbirange ;;
    funcgraph) do_funcgraph ;;
    perf)      do_perf ;;
    all)       do_tlbirange; do_perf; do_funcgraph ;;
    *) echo "unknown cmd: $CMD" >&2; exit 1 ;;
esac
