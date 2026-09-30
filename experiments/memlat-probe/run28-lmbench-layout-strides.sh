#!/bin/sh
# Exp H5: as run27 (lmbench's own lat_mem_rd on a buffer whose physical layout
# is set by layoutshim.so), for the other strides of the paper's command.
#
# run27 covered stride 256.  The N90 data show two levels at the 8 MB point
# for strides 64 to 1024 but none for strides 16 and 32, and high values in
# only 4 of 40 cases at stride 64 against 17 to 28 of 40 at strides 128 to
# 1024.  This run measures how large the layout effect is at each stride
# with lmbench's own program.
#
#   sh run28-lmbench-layout-strides.sh [cpu] [output prefix]
#
# Two layouts (sorted; shuffled within every 8 MB), two repetitions each,
# strides 16 32 64 128 512 1024.  As root the shim log also holds the
# adjacency actually obtained.  Changes no system setting.  About 18 minutes.
# Expects ./lat_mem_rd ./layoutshim.so.
cd "$(dirname "$0")" || exit 1
CPU=${1:-0}
OUT=${2:-expH5}
DF=/sys/class/devfreq/nocfreq
st() { echo "gov=$(cat $DF/governor 2>/dev/null) noc=$(cat $DF/cur_freq 2>/dev/null)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
echo "## start $(date -Is) cpu=$CPU uid=$(id -u) kernel=$(uname -r) kvm_arm_mode=${MODE:-unset} thp=$(sed 's/.*\[\(.*\)\].*/\1/' /sys/kernel/mm/transparent_hugepage/enabled) $(st) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT.log"
: > "$OUT-shim.log"
for rep in 1 2; do
  for v in sorted shuffled8; do
    echo "## rep=$rep layout=$v start=$(date +%s.%N | cut -c1-14) $(st)" >> "$OUT.log"
    case $v in
      sorted)    LAYOUT=sorted SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -P 1 64 16 32 64 128 512 1024 2>&1 | stamp >> "$OUT.log" ;;
      shuffled8) LAYOUT=shuffled SHUFFLE_MB=8 SHIM_SEED=$rep SHIM_LOG="$OUT-shim.log" LD_PRELOAD=./layoutshim.so taskset -c "$CPU" ./lat_mem_rd -P 1 64 16 32 64 128 512 1024 2>&1 | stamp >> "$OUT.log" ;;
    esac
    echo "## end rep=$rep layout=$v $(st)" >> "$OUT.log"
  done
done
echo "## done $(date -Is) $(st) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT.log"
