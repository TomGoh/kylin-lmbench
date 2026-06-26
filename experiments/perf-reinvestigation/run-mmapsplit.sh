#!/bin/bash
set -u
MODE="${1:?need mode tag}"
B=~/perf-reinvestigation/benches
OUT=~/perf-reinvestigation/results/$MODE
F=~/perf-reinvestigation/mb.bin           # user-owned, not /tmp
ITERS=300; SZ=64
mkdir -p "$OUT"; truncate -s 160M "$F"
CSV="$OUT/mmap_split.csv"; first=1
for m in mmap_unmap write_touch_cold munmap_after_no_touch munmap_after_write_touch mmap_write_touch_unmap; do
  out=$(taskset -c 0 "$B/mmap_split_bench" "$m" "$SZ" "$ITERS" "$F")
  if [ $first = 1 ]; then echo "$out" | head -1 > "$CSV"; first=0; fi
  echo "$out" | tail -1 >> "$CSV"
done
echo "=== $MODE mmap_split (lat_mmap geometry: 64MB, touch 6.4MB/16K, $ITERS iters) ==="
awk -F, 'NR>1{printf "  %-26s %9.2f us/iter\n",$5,$12}' "$CSV"
