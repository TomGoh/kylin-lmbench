#!/bin/sh
# Exp L2: the layout experiment (same frames, sorted / shuffled / reversed
# virtual order, sequential chase) with physically contiguous pages obtained
# from transparent huge pages, so that it needs no root and can be run on a
# machine that is not booted in protected mode (thplayout.c).
#
#   sh run24-thp-layout-noroot.sh [cpu] [output file]
#
# As root the lines also carry contig_frac (the adjacency actually obtained)
# and the PMU counts.  Changes no system setting.  About 4 minutes.
cd "$(dirname "$0")" || exit 1
CPU=${1:-0}
OUT=${2:-expL2.log}
E=${EVENTS:-11,2d,17,2a}
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
F=/sys/devices/system/cpu/cpu$CPU/cpufreq
echo "## start $(date -Is) cpu=$CPU uid=$(id -u) kernel=$(uname -r) kvm_arm_mode=${MODE:-unset} thp=$(sed 's/.*\[\(.*\)\].*/\1/' /sys/kernel/mm/transparent_hugepage/enabled) governor=$(cat $F/scaling_governor 2>/dev/null) max_khz=$(cat $F/scaling_max_freq 2>/dev/null) noc=$(cat /sys/class/devfreq/nocfreq/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
for rep in 1 2 3; do
  for sz in 4 8 16 32 64; do
    taskset -c "$CPU" ./thplayout $sz 256 sorted,shuffled,reversed,sorted,shuffled,aligned $rep $E 2>/dev/null | sed "s/^/L2 cpu=$CPU rep=$rep /" >> "$OUT"
  done
  # lmbench's loop form, and the smallest stride
  CHASE_UNROLL=1 taskset -c "$CPU" ./thplayout 16 256 sorted,shuffled,sorted,shuffled $rep $E 2>/dev/null | sed "s/^/L2 cpu=$CPU rep=$rep /" >> "$OUT"
  CHASE_UNROLL=1 taskset -c "$CPU" ./thplayout 16 64 sorted,shuffled,sorted,shuffled $rep $E 2>/dev/null | sed "s/^/L2 cpu=$CPU rep=$rep /" >> "$OUT"
done
echo "## done $(date -Is) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
