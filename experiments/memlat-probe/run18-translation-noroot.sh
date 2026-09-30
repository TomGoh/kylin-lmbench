#!/bin/sh
# Exp N: the translation-only chase as an unprivileged program (probe3 mode
# tlb), so that the same binary source can be run on a machine that is NOT
# booted in protected mode.  Needs neither root nor the PMU: every line carries
# l1_ns (a chase inside the L1 cache in the same process, 4 cycles per hop on
# FTC862) and cyc_est (the result in those cycles).  Where the PMU is
# available the usual evXX fields are printed as well.
#
#   sh run18-translation-noroot.sh [cpu] [output file]
#
# Changes no system setting.  About 3 minutes per CPU.
cd "$(dirname "$0")" || exit 1
CPU=${1:-0}
OUT=${2:-expN.log}
E=${EVENTS:-11,2d,17}
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
F=/sys/devices/system/cpu/cpu$CPU/cpufreq
echo "## start $(date -Is) cpu=$CPU kernel=$(uname -r) kvm_arm_mode=${MODE:-unset} thp=$(sed 's/.*\[\(.*\)\].*/\1/' /sys/kernel/mm/transparent_hugepage/enabled) governor=$(cat $F/scaling_governor 2>/dev/null) max_khz=$(cat $F/scaling_max_freq 2>/dev/null) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
for seed in 1 2 3 4 5; do
  # pages x lines per page: 4096 lines in every one of the first five
  for cfg in "1 16" "2 8" "4 4" "8 2" "16 1" "8 1" "32 1" "64 1"; do
    set -- $cfg
    echo "N cpu=$CPU $(taskset -c "$CPU" ./probe3 tlb $1 $2 64 $E 1 $seed 2>/dev/null)" >> "$OUT"
  done
  echo "N cpu=$CPU $(taskset -c "$CPU" ./probe3 seq 0.0234375 256 64 $E 1 $seed 2>/dev/null)" >> "$OUT"
done
echo "## done $(date -Is) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
