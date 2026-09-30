#!/bin/sh
# Exp H4: lmbench's own lat_mem_rd on a buffer whose physical layout is set.
#
# H2 and H3 could not give lmbench's 8 MB child a physically contiguous
# buffer: in its sweep the children above about 6 MB get their frames from
# the scattered low-order free blocks every time.  Here the unmodified
# lat_mem_rd binary is run with layoutshim.so preloaded, which hands it a
# buffer made of 4 KiB pages taken from 2 MiB huge pages and laid out
#   sorted                  in physical order
#   shuffled, SHUFFLE_MB=8  the same frames per 8 MB, in random order
#   shuffled                random order over the whole 64 MB
# and once per repetition without the shim, under ./nothp, as in Exp H
# ("natural").  The timed code is lmbench's; only where the buffer comes
# from differs.  Command: lat_mem_rd -P 1 64 256 (the paper's, stride 256).
#
#   sh run27-lmbench-layout-shim.sh [cpu] [output prefix]
#
# As root the shim log also holds the adjacency actually obtained.  Changes
# no system setting.  About 12 minutes.
# Expects ./lat_mem_rd ./nothp ./layoutshim.so.
cd "$(dirname "$0")" || exit 1
CPU=${1:-0}
OUT=${2:-expH4}
DF=/sys/class/devfreq/nocfreq
st() { echo "gov=$(cat $DF/governor 2>/dev/null) noc=$(cat $DF/cur_freq 2>/dev/null)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
echo "## start $(date -Is) cpu=$CPU uid=$(id -u) kernel=$(uname -r) kvm_arm_mode=${MODE:-unset} thp=$(sed 's/.*\[\(.*\)\].*/\1/' /sys/kernel/mm/transparent_hugepage/enabled) $(st) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT.log"
: > "$OUT-shim.log"
for rep in 1 2 3 4; do
  for v in sorted shuffled8 shuffled natural; do
    echo "## rep=$rep layout=$v start=$(date +%s.%N | cut -c1-14) $(st)" >> "$OUT.log"
    case $v in
      sorted)    LAYOUT=sorted SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -P 1 64 256 2>&1 | stamp >> "$OUT.log" ;;
      shuffled8) LAYOUT=shuffled SHUFFLE_MB=8 SHIM_SEED=$rep SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -P 1 64 256 2>&1 | stamp >> "$OUT.log" ;;
      shuffled)  LAYOUT=shuffled SHIM_SEED=$rep SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -P 1 64 256 2>&1 | stamp >> "$OUT.log" ;;
      natural)   taskset -c "$CPU" ./nothp ./lat_mem_rd -P 1 64 256 2>&1 | stamp >> "$OUT.log" ;;
    esac
    echo "## end rep=$rep layout=$v $(st)" >> "$OUT.log"
  done
done
echo "## done $(date -Is) $(st) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT.log"
