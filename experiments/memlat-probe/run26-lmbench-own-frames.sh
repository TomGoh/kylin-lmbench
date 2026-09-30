#!/bin/sh
# Exp H3: lmbench's own lat_mem_rd with the physical layout of ITS OWN buffers
# recorded.
#
# As run25 (a stopped process holds back 0 to 2560 MB before each sweep, so
# that the kernel hands out frames from larger free blocks in some sweeps),
# but here lmb-frames.py watches for the children of lat_mem_rd and reads the
# page map of each child's buffer a quarter of a second after the child
# appeared.  The layout is therefore that of the very buffer lmbench times,
# not of a stand-in.  probe3 still runs before and after every sweep.
#
# The lmbench command is the paper's: lat_mem_rd -P 1 64 256, under ./nothp
# (4 KiB pages).  Root (pagemap PFNs), benchmark on cpu0, watcher on cpu6.
# Changes no system setting.  About 11 minutes.
# Expects ./lat_mem_rd ./nothp ./probe3 ./bgload ./lmb-frames.py.
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a
st() { echo "gov=$(cat $DF/governor 2>/dev/null) noc=$(cat $DF/cur_freq 2>/dev/null)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
echo "# run26 start $(date -Is) uid=$(id -u) $(st) thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log
: > expH3.log
: > expH3-frames.log
taskset -c 6 python3 lmb-frames.py expH3-frames.log &
WATCH=$!
trap 'kill $WATCH 2>/dev/null' EXIT
trap 'exit 1' INT TERM HUP
for rep in 1 2 3; do
  for hold in 0 1024 2048 2560; do
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
    echo "## rep=$rep hold_mb=$hold start=$(date +%s.%N | cut -c1-14) $(st) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo) free blocks by order: $(grep Normal /proc/buddyinfo | tr -s ' ' | cut -d' ' -f5-)" >> expH3.log
    echo "P pre rep=$rep hold_mb=$hold $(CHASE_UNROLL=1 taskset -c 0 ./probe3 seq 8 256 64 $E 1 $rep 2>/dev/null)" >> expH3.log
    taskset -c 0 ./nothp ./lat_mem_rd -P 1 64 256 2>&1 | stamp >> expH3.log
    echo "P post rep=$rep hold_mb=$hold $(CHASE_UNROLL=1 taskset -c 0 ./probe3 seq 8 256 64 $E 1 $rep 2>/dev/null)" >> expH3.log
    echo "## end rep=$rep hold_mb=$hold $(st)" >> expH3.log
    # not a bare wait: that would also wait for the watcher
    if [ -n "$pid" ]; then
      kill -KILL $pid
      wait $pid 2>/dev/null
    fi
  done
done
kill $WATCH 2>/dev/null
echo "# run26 done $(date -Is) $(st) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
