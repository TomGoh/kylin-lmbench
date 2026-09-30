#!/bin/sh
# Experiments that need no system change: they run in whatever platform state
# the machine is in and only record that state.  cpu0.  About 8 minutes.
# Root is optional: without it the physical-layout fields read pfn=na.
# Expects ./probe3 ./bgload next to this script.
#
#   expR.log   Exp R: sequential stride 256 at 4..64 MB, fresh process per point,
#              chain built once (rebuild=0) versus rewritten before every
#              interval as lmbench does (rebuild=1), 20 laps
#   expBG.log  Exp BG: the headline points with memory traffic from other cores
#
# lmbench's own program is run by run9-lmbench-current-state.sh.
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,2a,17,5,13
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)"; }
echo "# run6 start $(date -Is) uid=$(id -u) $(st) thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled) cpu0_freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log

# R: does rewriting the chain before every interval change the result?
: > expR.log
for lap in $(seq 1 20); do
  for sz in 4 6 8 12 16 64; do
    for rb in 0 1; do
      echo "R lap=$lap $(taskset -c 0 ./probe3 seq $sz 256 64 $E $rb 2>&1)" >> expR.log
    done
  done
done
echo "# run6 R done $(date -Is) $(st)" >> meta.log

# BG: memory traffic from other cores while cpu0 measures
: > expBG.log
for bg in none r1 w1 w2; do
  pids=""
  case $bg in
    r1) taskset -c 5 ./bgload r 256 600 > /dev/null & pids=$! ;;
    w1) taskset -c 5 ./bgload w 256 600 > /dev/null & pids=$! ;;
    w2) taskset -c 5 ./bgload w 256 600 > /dev/null & pids=$!
        taskset -c 6 ./bgload w 256 600 > /dev/null & pids="$pids $!" ;;
  esac
  sleep 2
  for rep in 1 2 3; do
    echo "BG bg=$bg $(taskset -c 0 ./probe3 seq 4 256 64 $E 1 2>&1)" >> expBG.log
    echo "BG bg=$bg $(taskset -c 0 ./probe3 seq 8 256 64 $E 1 2>&1)" >> expBG.log
    echo "BG bg=$bg $(taskset -c 0 ./probe3 seq 64 256 64 $E 1 2>&1)" >> expBG.log
    echo "BG bg=$bg $(taskset -c 0 ./probe3 rand 8 16 64 $E 1 $((rep * 7)) 2>&1)" >> expBG.log
  done
  for rep in 1 2; do
    echo "BG bg=$bg $(taskset -c 0 ./probe3 rand 64 16 64 $E 1 $((rep * 7)) 2>&1)" >> expBG.log
  done
  [ -n "$pids" ] && kill $pids 2>/dev/null
  wait 2>/dev/null
done
echo "# run6 BG done $(date -Is) $(st)" >> meta.log

echo "# run6 done $(date -Is) $(st)" >> meta.log
