#!/bin/sh
# Exp H8: how does lmbench's lat_mem_rd read a buffer of which only the first
# 8 MB are physically scattered?
#
# On the N80 every 12 MB child of a sweep holds all frames of the 8 MB child
# before it (Exp H7).  If the high level of the 8 MB point came from scattered
# frames, the 12 MB point right after it would be measured on a buffer that is
# two thirds scattered.  This run gives lmbench such a buffer with
# layoutshim.so:
#   sorted     every page in physical order
#   head8      the pages of the first 8 MB in random order, the rest sorted
#   shuffled8  random order within every 8 MB
# Command: lat_mem_rd -P 1 64 128 256 (two of the paper's strides).
#
#   sh run32-lmbench-partial-layout.sh [cpu] [output prefix] [repetitions]
#
# As root the shim log also holds the adjacency actually obtained.  Changes
# no system setting.  About 15 minutes.
# Expects ./lat_mem_rd ./layoutshim.so.
cd "$(dirname "$0")" || exit 1
CPU=${1:-0}
OUT=${2:-expH8}
REPS=${3:-3}
DF=/sys/class/devfreq/nocfreq
st() { echo "gov=$(cat $DF/governor 2>/dev/null) noc=$(cat $DF/cur_freq 2>/dev/null)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
echo "## start $(date -Is) cpu=$CPU uid=$(id -u) kernel=$(uname -r) kvm_arm_mode=${MODE:-unset} thp=$(sed 's/.*\[\(.*\)\].*/\1/' /sys/kernel/mm/transparent_hugepage/enabled) $(st) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT.log"
: > "$OUT-shim.log"
rep=1
while [ "$rep" -le "$REPS" ]; do
  for v in sorted head8 shuffled8; do
    echo "## rep=$rep layout=$v start=$(date +%s.%N | cut -c1-14) $(st)" >> "$OUT.log"
    case $v in
      sorted)    LAYOUT=sorted SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -P 1 64 128 256 2>&1 | stamp >> "$OUT.log" ;;
      head8)     LAYOUT=shuffled SHUFFLE_HEAD_MB=8 SHIM_SEED=$rep SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -P 1 64 128 256 2>&1 | stamp >> "$OUT.log" ;;
      shuffled8) LAYOUT=shuffled SHUFFLE_MB=8 SHIM_SEED=$rep SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -P 1 64 128 256 2>&1 | stamp >> "$OUT.log" ;;
    esac
    echo "## end rep=$rep layout=$v $(st)" >> "$OUT.log"
  done
  rep=$((rep + 1))
done
echo "## done $(date -Is) $(st) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT.log"
