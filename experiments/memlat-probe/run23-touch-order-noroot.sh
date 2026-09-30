#!/bin/sh
# Exp T2: the layout effect of the sequential chase on a machine WITHOUT a
# host stage-2, as an unprivileged program.
#
# On the N80 (protected mode) the same pages read in a shuffled virtual order
# are 17-27% slower in the sequential chase than in physically sorted order
# (Exp L, W, Y), for block-mapped and for 4 KiB-mapped host pages alike.  That
# was measured in protected mode only.  Without root the frames cannot be
# chosen, but the order of the first touch can: probe2 touches the pages of
# the buffer in ascending, descending or random virtual order before the
# chain is written.  If the kernel hands out physically consecutive frames,
# ascending first touch gives a physically sorted buffer and random first
# touch a scrambled one.  Fresh small allocations come from the short free
# lists, which hold scattered frames; to get at the large free blocks a
# stopped process first holds back <hold> MB.
#
#   sh run23-touch-order-noroot.sh [cpu] [output file] ["hold sizes in MB"]
#
# Needs ./probe2 and ./bgload.  Changes no system setting.  About 5 minutes.
cd "$(dirname "$0")" || exit 1
CPU=${1:-0}
OUT=${2:-expT2.log}
HOLDS=${3:-"0 1024 2048"}
E=${EVENTS:-11,2d,17}
MODE=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^kvm-arm\.mode=//p' | tail -1)
F=/sys/devices/system/cpu/cpu$CPU/cpufreq
echo "## start $(date -Is) cpu=$CPU uid=$(id -u) kernel=$(uname -r) kvm_arm_mode=${MODE:-unset} thp=$(sed 's/.*\[\(.*\)\].*/\1/' /sys/kernel/mm/transparent_hugepage/enabled) governor=$(cat $F/scaling_governor 2>/dev/null) max_khz=$(cat $F/scaling_max_freq 2>/dev/null) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
for rep in 1 2 3; do
  for hold in $HOLDS; do
    pid=""
    if [ "$hold" -gt 0 ]; then
      taskset -c 5 ./bgload w $hold 600 > /dev/null 2>&1 &
      pid=$!
      n=0
      while [ "$(awk '/VmRSS/{print $2}' /proc/$pid/status 2>/dev/null || echo 0)" -lt $(( hold * 1000 )) ] && [ $n -lt 100 ]; do
        sleep 0.2
        n=$((n + 1))
      done
      kill -STOP $pid
    fi
    echo "## rep=$rep hold_mb=$hold free blocks by order (zone Normal): $(grep Normal /proc/buddyinfo | tr -s ' ' | cut -d' ' -f5-)" >> "$OUT"
    for sz in 8 16 64; do
      for t in asc rand desc; do
        echo "T2 cpu=$CPU rep=$rep hold_mb=$hold $(taskset -c "$CPU" ./probe2 seq $sz 256 64 0 $E $rep $t 2>/dev/null)" >> "$OUT"
      done
    done
    [ -n "$pid" ] && kill -KILL $pid
    wait 2>/dev/null
  done
done
echo "## done $(date -Is) loadavg=$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT"
