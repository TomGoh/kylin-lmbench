#!/bin/sh
# state check: what is left on the free lists when a stopped process holds back N MB
cd "$(dirname "$0")" || exit 1
for hold in 0 2560 3000 3300; do
  pid=""
  if [ "$hold" -gt 0 ]; then
    taskset -c 5 ./bgload w $hold 300 > /dev/null 2>&1 &
    pid=$!
    n=0
    while [ "$(awk '/VmRSS/{print $2}' /proc/$pid/status 2>/dev/null || echo 0)" -lt $(( hold * 1000 )) ] && [ $n -lt 150 ]; do sleep 0.2; n=$((n + 1)); done
    kill -STOP $pid
  fi
  echo "## hold_mb=$hold memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"
  grep -E "zone +Normal, type +(Unmovable|Movable|Reclaimable) " /proc/pagetypeinfo | head -3
  if [ -n "$pid" ]; then kill -KILL $pid; wait $pid 2>/dev/null; fi
  sleep 1
done
