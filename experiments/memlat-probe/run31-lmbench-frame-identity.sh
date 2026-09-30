#!/bin/sh
# Exp H7: which frames do lmbench's successive children get?
#
# H3 found the buffers of lmbench's 8 to 24 MB children physically scattered
# in every sweep, even with 2.5 GB held back, when the movable free lists of
# the zone hold no small blocks at all (holdcheck).  To see where those frames
# come from, this run stores the frame numbers of every child's buffer
# (lmb-frames.py with a dump file) together with the state of the free lists
# and of cpu0's per-CPU list at the start of every sweep, for the command
# lat_mem_rd -P 1 64 256 under ./nothp: two sweeps with nothing held back and
# two with 2560 MB held back by a stopped process.
# Root (pagemap PFNs), benchmark on cpu0, watcher on cpu6.  Changes no system
# setting.  About 4 minutes.
# Expects ./lat_mem_rd ./nothp ./bgload ./lmb-frames.py.
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
st() { echo "gov=$(cat $DF/governor 2>/dev/null) noc=$(cat $DF/cur_freq 2>/dev/null)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
pcp() { awk '/^Node/{z=$4} /cpu: 0$/{c=1; next} c&&/count:/{n=$2} c&&/high:/{printf "%s:count=%s,high=%s ", z, n, $2; c=0}' /proc/zoneinfo; }
echo "# run31 start $(date -Is) uid=$(id -u) $(st)" >> meta.log
: > expH7.log
: > expH7-frames.log
: > expH7-pfns.log
taskset -c 6 python3 lmb-frames.py expH7-frames.log lat_mem_rd expH7-pfns.log &
WATCH=$!
trap 'kill $WATCH 2>/dev/null' EXIT
trap 'exit 1' INT TERM HUP
for rep in 1 2; do
  for hold in 0 2560; do
    pid=""
    if [ "$hold" -gt 0 ]; then
      taskset -c 5 ./bgload w $hold 900 > /dev/null 2>&1 &
      pid=$!
      n=0
      while [ "$(awk '/VmRSS/{print $2}' /proc/$pid/status 2>/dev/null || echo 0)" -lt $(( hold * 1000 )) ] && [ $n -lt 150 ]; do
        sleep 0.2
        n=$((n + 1))
      done
      kill -STOP $pid
    fi
    echo "## rep=$rep hold_mb=$hold start=$(date +%s.%N | cut -c1-14) $(st) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo) pcp_cpu0: $(pcp)" >> expH7.log
    grep -E "zone +(DMA|Normal), type +(Unmovable|Movable|Reclaimable) " /proc/pagetypeinfo | sed 's/^/## free /' >> expH7.log
    taskset -c 0 ./nothp ./lat_mem_rd -P 1 64 256 2>&1 | stamp >> expH7.log
    echo "## end rep=$rep hold_mb=$hold $(st) pcp_cpu0: $(pcp)" >> expH7.log
    if [ -n "$pid" ]; then
      kill -KILL $pid
      wait $pid 2>/dev/null
    fi
  done
done
kill $WATCH 2>/dev/null
echo "# run31 done $(date -Is) $(st)" >> meta.log
