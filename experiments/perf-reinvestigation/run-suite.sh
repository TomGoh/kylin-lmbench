#!/bin/bash
set -u
MODE="${1:?need mode tag}"
B=~/perf-reinvestigation/benches
OUT=~/perf-reinvestigation/results/$MODE
PERF=/usr/local/bin/perf
F=/tmp/mb.bin
ITERS=300
mkdir -p "$OUT"; truncate -s 160M "$F"
{ uname -r; cat /proc/cmdline; } > "$OUT/kernel.txt"
echo "### op_sweep: flush-range sweep (dense 4K) + sparse(16K), munmap/dontneed/mprotect ###" | tee "$OUT/op_sweep.txt"
for op in munmap dontneed mprotect; do
  for t in 0.25 0.5 1 1.9 2 4 8 32 64; do
    taskset -c 0 "$B/op_sweep" "$op" file 64 "$ITERS" "$F" "$t" 4
  done
  taskset -c 0 "$B/op_sweep" "$op" file 64 "$ITERS" "$F" 6.4 16
done | tee -a "$OUT/op_sweep.txt"
echo "### Stage 3: cycles:h during sparse munmap (expect ~0) ###" | tee "$OUT/el2_h.txt"
taskset -c 0 "$PERF" stat -e cycles,cycles:k,cycles:h,instructions:h \
  "$B/munmap_only" file 64 "$ITERS" "$F" 6.4 16 2>&1 | tee -a "$OUT/el2_h.txt"
echo "### Stage 4: cost layering (sparse munmap, then sub-2MB dense touch=1) ###" | tee "$OUT/cost_layering.txt"
for args in "6.4 16" "1 4"; do
  echo "--- touch/stride = $args ---" | tee -a "$OUT/cost_layering.txt"
  taskset -c 0 "$PERF" stat -e instructions,page-faults,r0034,l2d_tlb_refill,r0024,cycles \
    "$B/munmap_only" file 64 "$ITERS" "$F" $args 2>&1 | tee -a "$OUT/cost_layering.txt"
done
echo "SUITE DONE: $MODE"
