#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

phase=${1:?usage: run-anchors.sh start|end}
[[ "$phase" == start || "$phase" == end ]] || die "anchor phase must be start or end"
set_project_thp anchors
space_guard

out=$(run_dir anchors "$phase" 0)
rm -rf "$out"; mkdir -p "$out"
capture_metadata "$out/metadata"

backing="$WORK_ROOT/tmp/anchor-64m.dat"
if [[ ! -s "$backing" || $(stat -c %s "$backing") -lt 67108864 ]]; then
    taskset -c 0 "$TOOLS_DIR/bin/lmdd" of="$backing" move=64m fsync=1 print=0
fi

declare -A iters=( [0.5]=10000 [1]=8000 [2]=5000 [4]=3000 [8]=2000 [16]=1000 [64]=300 )
for size in 0.5 1 2 4 8 16 64; do
    for rep in $(seq 1 "$REPETITIONS"); do
        taskset -c 0 "$TOOLS_DIR/bin/lat_mmap_precise" "$size" "${iters[$size]}" "$backing" \
            | tee -a "$out/lat-mmap-precise.txt"
    done
done

for rep in $(seq 1 "$REPETITIONS"); do
    for spec in 'dense-1.9 1.9 4' 'dense-2.0 2.0 4' 'sparse-6.4 6.4 16'; do
        read -r label touched stride <<<"$spec"
        printf 'rep=%s label=%s ' "$rep" "$label" >>"$out/op-sweep.txt"
        taskset -c 0 "$TOOLS_DIR/bin/op_sweep" munmap file 64 100 "$backing" "$touched" "$stride" \
            >>"$out/op-sweep.txt"
    done
done

for rep in $(seq 1 "$REPETITIONS"); do
    taskset -c 0 "$TOOLS_DIR/bin/lat_mem_rd" -P 1 -W 2 -N 5 64 128 \
        >"$out/lat-mem-r${rep}.stdout" 2>"$out/lat-mem-r${rep}.txt"
done

touch "$out/VALID"
log "completed $phase anchors"
