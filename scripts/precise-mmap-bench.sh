#!/bin/bash
# precise-mmap-bench.sh —— 用 lat_mmap_precise（ns 精度）跑 mmap 微基准
#
# 与 lmbench 的 lat_mmap 语义完全一致（file-backed MAP_SHARED + PSIZE=16K + N=10），
# 只是时钟和输出精度更高。
#
# 用法：
#   sudo bash precise-mmap-bench.sh <mode_name>
#
# 输出每个 size 跑 10 runs，每 run 跑 N 次 mmap+touch+munmap。
# Backing file 用 /var/tmp/lmb_precise_NNN.dat（per-size，复用），跑完不删，下次复用。

set -u

BIN=/root/lmbench-3.0-a9/bin/aarch64-Linux/lat_mmap_precise
LMDD=/root/lmbench-3.0-a9/bin/aarch64-Linux/lmdd
MODE="${1:-unknown}"
OUTDIR="/root/lmbench-3.0-a9/results/precise-mmap"
mkdir -p "$OUTDIR"
OUTFILE="$OUTDIR/${MODE}.log"

# size (MB) -> iter 数。size 对齐 FINAL-REPORT 表：0.5/1/2/4/8/16/64 MB
# （注：lmbench 报"67"是因为 64 × 1.048576 = 67.108864；这里我们直接用 64）
declare -A ITERS=(
    ["0.5"]=10000  ["1"]=8000   ["2"]=5000  ["4"]=3000
    ["8"]=2000     ["16"]=1000  ["64"]=300
)

SIZES=("0.5" "1" "2" "4" "8" "16" "64")

# 预填 backing file（用 lmdd，和 lmbench scripts/lmbench 完全一致）。
# 复用 /tmp/lmb_precise_<size>MB.dat —— 如果已存在且 size 足，跳过填充。
echo "=== prep backing files (lmdd-fill) ===" | tee -a "$OUTFILE"
for sz in "${SIZES[@]}"; do
    bytes=$(awk "BEGIN{printf \"%d\", $sz * 1048576}")
    fname="/tmp/lmb_precise_${sz}MB.dat"
    cur=$(stat -c %s "$fname" 2>/dev/null || echo 0)
    if [ "$cur" -lt "$bytes" ]; then
        # lmdd 不支持小数 move=，对 <1MB 一律按 1m 写（file > size 就行）
        mv_arg=$(awk "BEGIN{n=int($sz+0.999); if(n<1)n=1; print n}")
        echo "  fill $fname to ${mv_arg}m (need ${sz}MB) ..." | tee -a "$OUTFILE"
        sudo "$LMDD" of="$fname" move="${mv_arg}m" fsync=1 print=0 2>&1 | tee -a "$OUTFILE"
    else
        echo "  reuse $fname (already ${cur}B >= ${bytes}B)" | tee -a "$OUTFILE"
    fi
done

echo "=== mode=$MODE start: $(date -Iseconds) ===" | tee "$OUTFILE"

for sz in "${SIZES[@]}"; do
    n="${ITERS[$sz]}"
    fname="/tmp/lmb_precise_${sz}MB.dat"
    echo "--- $MODE size=${sz} MB iters=${n} × 10 runs file=${fname} ---" | tee -a "$OUTFILE"
    for run in $(seq 1 10); do
        out=$(sudo taskset -c 0 "$BIN" "$sz" "$n" "$fname" 2>&1)
        echo "  run $run: $out" | tee -a "$OUTFILE"
    done
done

echo "=== mode=$MODE end: $(date -Iseconds) ===" | tee -a "$OUTFILE"
echo "Saved to $OUTFILE"
