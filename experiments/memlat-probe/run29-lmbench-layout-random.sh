#!/bin/sh
# Exp H6: lmbench's own random-access test (lat_mem_rd -t) on a buffer whose
# physical layout is set by layoutshim.so.
#
# The layout of the buffer moves lmbench's sequential numbers by 19% to 33%
# (run27, run28).  The N90 also has a "fast" state in which random access is
# 18% to 35% faster.  This run checks, with lmbench's own program, that the
# physical order of the pages does not move the random-access numbers, i.e.
# that the fast state cannot be a matter of page layout.
#
#   sh run29-lmbench-layout-random.sh [cpu] [output prefix]
#
# Command: lat_mem_rd -t -P 1 64 16 (the paper's).  Layouts: sorted; shuffled
# over the whole buffer; without the library under ./nothp ("natural"); two
# repetitions each.  Changes no system setting.  About 5 minutes.
# Expects ./lat_mem_rd ./nothp ./layoutshim.so.
cd "$(dirname "$0")" || exit 1
CPU=${1:-0}
OUT=${2:-expH6}
DF=/sys/class/devfreq/nocfreq
st() { echo "gov=$(cat $DF/governor 2>/dev/null) noc=$(cat $DF/cur_freq 2>/dev/null)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
echo "## start $(date -Is) cpu=$CPU uid=$(id -u) kernel=$(uname -r) kvm_arm_mode=${MODE:-unset} thp=$(sed 's/.*\[\(.*\)\].*/\1/' /sys/kernel/mm/transparent_hugepage/enabled) $(st) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT.log"
: > "$OUT-shim.log"
for rep in 1 2; do
  for v in sorted shuffled natural; do
    echo "## rep=$rep layout=$v start=$(date +%s.%N | cut -c1-14) $(st)" >> "$OUT.log"
    case $v in
      sorted)   LAYOUT=sorted SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -t -P 1 64 16 2>&1 | stamp >> "$OUT.log" ;;
      shuffled) LAYOUT=shuffled SHIM_SEED=$rep SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -t -P 1 64 16 2>&1 | stamp >> "$OUT.log" ;;
      natural)  taskset -c "$CPU" ./nothp ./lat_mem_rd -t -P 1 64 16 2>&1 | stamp >> "$OUT.log" ;;
    esac
    echo "## end rep=$rep layout=$v $(st)" >> "$OUT.log"
  done
done
echo "## done $(date -Is) $(st) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT.log"
