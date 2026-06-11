#!/usr/bin/env bash
# Run mmap split microbenchmarks for one host mode.
#
# Usage:
#   MODE=nvhe CORE=0 bash scripts/mmap-split-bench.sh
#   MODE=pkvm CORE=0 RUNS=10 bash scripts/mmap-split-bench.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$ROOT/experiments/mmap-split"
BIN="$PROJECT/mmap_split_bench"
MODE="${MODE:-${1:-unknown}}"
CORE="${CORE:-0}"
RUNS="${RUNS:-10}"
OUTDIR="${OUTDIR:-$ROOT/results/mmap-split}"
OUTFILE="$OUTDIR/${MODE}.csv"
LMDD="${LMDD:-$ROOT/bin/aarch64-Linux/lmdd}"
TOUCH_DIVISOR="${TOUCH_DIVISOR:-10}"
STRIDE_KB="${STRIDE_KB:-16}"
WARMUPS="${WARMUPS:-1}"
REFILL="${REFILL:-0}"

mkdir -p "$OUTDIR"

echo "[mmap-split] building $BIN"
make -C "$PROJECT" >/dev/null

if [ ! -x "$BIN" ]; then
    echo "missing binary: $BIN" >&2
    exit 1
fi

declare -A ITERS=(
    ["0.5"]=10000
    ["1"]=8000
    ["2"]=5000
    ["4"]=3000
    ["8"]=2000
    ["16"]=1000
    ["64"]=300
)

SIZES=("0.5" "1" "2" "4" "8" "16" "64")
MODES=(
    "openclose"
    "mmap_unmap"
    "mmap_populate_unmap"
    "mmap_write_touch_unmap"
    "mmap_read_touch_unmap"
    "write_touch_cold"
    "read_touch_cold"
    "write_touch_hot"
    "read_touch_hot"
    "munmap_after_no_touch"
    "munmap_after_write_touch"
    "munmap_after_read_touch"
)

{
    echo "# mode=$MODE"
    echo "# date=$(date -Is)"
    echo "# host=$(hostname)"
    echo "# uname=$(uname -a)"
    echo "# cmdline=$(cat /proc/cmdline 2>/dev/null || true)"
    echo "# lsm=$(cat /sys/kernel/security/lsm 2>/dev/null || true)"
    echo "# thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true)"
    echo "# aslr=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null || true)"
    echo "# core=$CORE"
    echo "# runs=$RUNS"
    echo "# touch_divisor=$TOUCH_DIVISOR"
    echo "# stride_kb=$STRIDE_KB"
    echo "# warmups=$WARMUPS"
    echo "# backing_fill=lmdd-or-dd-fsync"
    echo "env,run,bench_mode,size_mb,iters,warmups,timed,touch_divisor,stride_kb,touch_bytes,touches_per_iter,total_ns,per_iter_ns,per_iter_us,per_touch_ns,sink"
} > "$OUTFILE"

echo "[mmap-split] preparing backing files"
for sz in "${SIZES[@]}"; do
    bytes=$(awk "BEGIN{printf \"%d\", $sz * 1048576}")
    fname="/tmp/mmap_split_${sz}MB.dat"
    if [ "$REFILL" = "1" ]; then
        rm -f "$fname"
    fi
    cur=$(stat -c %s "$fname" 2>/dev/null || echo 0)
    if [ "$cur" -lt "$bytes" ]; then
        mv_arg=$(awk "BEGIN{n=int($sz+0.999); if(n<1)n=1; print n}")
        if [ -x "$LMDD" ]; then
            echo "  fill $fname with lmdd move=${mv_arg}m"
            taskset -c "$CORE" "$LMDD" of="$fname" move="${mv_arg}m" fsync=1 print=0 >/dev/null 2>&1
        else
            echo "  fill $fname with dd count=${mv_arg} bs=1M conv=fsync"
            dd if=/dev/zero of="$fname" bs=1M count="$mv_arg" conv=fsync status=none
        fi
    else
        echo "  reuse $fname (${cur} bytes)"
    fi
done

for sz in "${SIZES[@]}"; do
    iters="${ITERS[$sz]}"
    fname="/tmp/mmap_split_${sz}MB.dat"
    for bench_mode in "${MODES[@]}"; do
        echo "[mmap-split] $MODE size=${sz} mode=${bench_mode} iters=${iters} runs=${RUNS}"
        for run in $(seq 1 "$RUNS"); do
            line=$(taskset -c "$CORE" "$BIN" "$bench_mode" "$sz" "$iters" "$fname" "$TOUCH_DIVISOR" "$STRIDE_KB" "$WARMUPS" | tail -n 1)
            echo "$MODE,$run,$line" >> "$OUTFILE"
        done
    done
done

echo "[mmap-split] saved $OUTFILE"
