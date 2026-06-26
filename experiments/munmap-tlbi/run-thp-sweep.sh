#!/bin/bash
# E1 driver for the THP-mitigation experiment: anon_base (4 KB) vs anon_huge (2 MB THP)
# munmap teardown, on one pinned core, with anon_base/anon_huge INTERLEAVED within each
# round so slow drift (thermal/background) cancels in the per-round A/B.
#
# Only variable per pair: the madvise flag (NOHUGEPAGE vs HUGEPAGE). Everything else
# (size, iters, touch span, stride, core, fill) is identical.
#
# Env: CORE (0), ITERS (300), ROUNDS (10), POINTS, OUT
set -u
CORE=${CORE:-0}
ITERS=${ITERS:-300}
ROUNDS=${ROUNDS:-10}
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$DIR/munmap_only"
# point = "size_mb:touch_mb:stride_kb:label"
#  sparse (stride 16, touch size/10) keeps anon_base on the per-page TLBI path (big gap);
#  dense (stride 4, full touch) is the reference where even base already hits the 2 MB threshold.
POINTS=${POINTS:-"8:0.8:16:sparse 16:1.6:16:sparse 64:6.4:16:sparse 64:64:4:dense"}
OUT=${OUT:-/tmp/e1-thp-sweep.txt}

[ -x "$BIN" ] || { echo "missing $BIN (build first)"; exit 1; }
: > "$OUT"
{
  echo "# E1 anon_base vs anon_huge | core=$CORE iters=$ITERS rounds=$ROUNDS"
  echo "# kernel=$(uname -r)"
  echo "# cmdline=$(cat /proc/cmdline)"
  echo "# thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled)"
  echo "# freq_start=$(cat /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_cur_freq 2>/dev/null)"
  echo "# date=$(date -Is)"
} | tee -a "$OUT"

for pt in $POINTS; do
  IFS=: read -r sz tm st lbl <<<"$pt"
  for r in $(seq 1 "$ROUNDS"); do
    for mode in anon_base anon_huge; do        # interleaved A/B within a round
      line=$(taskset -c "$CORE" "$BIN" "$mode" "$sz" "$ITERS" - "$tm" "$st")
      echo "point=${sz}MB/${lbl} round=$r $line" | tee -a "$OUT"
    done
  done
done
echo "# freq_end=$(cat /sys/devices/system/cpu/cpu$CORE/cpufreq/scaling_cur_freq 2>/dev/null)" | tee -a "$OUT"
