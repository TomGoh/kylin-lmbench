#!/bin/sh
# Exp N4: does the order in which the pages are first touched change probe3's
# translation-only chase?
#
# In Exp N2 the configuration 4096 pages x 1 line showed 0.4-0.8 L2 cache
# refills per hop, so it did not measure address translation.  Suspected
# cause: the pages are first touched in the order of the chain, the cache line
# used within a page is a function of the position in the chain, and when the
# kernel hands out physically consecutive frames the frame number is one too,
# so the data lines crowd into few L2 sets.  TLB_PREFAULT=1 touches the pages
# in ascending virtual order first, which breaks that link.
#
# Every repetition runs each configuration without and with TLB_PREFAULT.
# As root the lines also carry slots= and l2over= (share of the data lines in
# L2 sets that hold more than 8 of them).
#
#   sh run21-prefault.sh [cpu] [output file] [hold]
#
# With "hold" as third argument (needs ./bgload) a stopped process holds back
# (repetition - 1) x 256 MB, as in run19, so that the frames differ between
# repetitions.  Changes no system setting.  About 4 minutes.
cd "$(dirname "$0")" || exit 1
CPU=${1:-0}
OUT=${2:-expN4.log}
HOLD=${3:-}
E=${EVENTS:-11,2d,17}
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
F=/sys/devices/system/cpu/cpu$CPU/cpufreq
echo "## start $(date -Is) cpu=$CPU uid=$(id -u) kernel=$(uname -r) kvm_arm_mode=${MODE:-unset} thp=$(sed 's/.*\[\(.*\)\].*/\1/' /sys/kernel/mm/transparent_hugepage/enabled) governor=$(cat $F/scaling_governor 2>/dev/null) max_khz=$(cat $F/scaling_max_freq 2>/dev/null) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
for rep in 1 2 3 4 5 6 7 8; do
  hold=0
  pid=""
  if [ -n "$HOLD" ]; then
    hold=$(( (rep - 1) * 256 ))
    if [ "$hold" -gt 0 ]; then
      taskset -c 5 ./bgload w $hold 600 > /dev/null 2>&1 &
      pid=$!
      sleep 2
      kill -STOP $pid
    fi
  fi
  for pf in 0 1; do
    # pages x lines per page: two configurations without page walks (2048 and
    # 4096 lines), then three with a walk on almost every hop
    for cfg in "4 2" "4 4" "8 1" "8 2" "16 1"; do
      set -- $cfg
      echo "N4 cpu=$CPU rep=$rep hold_mb=$hold $(TLB_PREFAULT=$pf taskset -c "$CPU" ./probe3 tlb $1 $2 64 $E 1 $rep 2>/dev/null)" >> "$OUT"
    done
  done
  [ -n "$pid" ] && kill -KILL $pid
  wait 2>/dev/null
done
echo "## done $(date -Is) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
