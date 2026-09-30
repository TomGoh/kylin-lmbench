#!/bin/sh
# Exp H2: does lmbench's own lat_mem_rd take two levels at the 8 MB point
# when only the frames it is given change?
#
# Exp H found the 8 MB stride-256 point of lmbench's own binary single-valued
# on the N80 (10.16-10.51 ns in 18 sweeps).  The free memory of the machine
# was fragmented at the time, so every buffer was physically scattered.  Here
# a stopped process holds back 0 to 2560 MB before each sweep (as in run19),
# so that lmbench's children get their frames from the large free blocks in
# some sweeps and from the scattered free pages in others.  lmbench does not
# report frame numbers; probe3 (same allocation pattern, lmbench's loop form)
# is run right before and right after every sweep and reports the adjacency
# of the buffer it got (contig_frac, rcontig_frac).
#
# The lmbench command is the paper's: lat_mem_rd -P 1 64 256, under ./nothp
# (4 KiB pages).  Root (pagemap PFNs for probe3), cpu0.  Changes no system
# setting.  About 14 minutes.  Expects ./lat_mem_rd ./nothp ./probe3 ./bgload.
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a
st() { echo "gov=$(cat $DF/governor 2>/dev/null) noc=$(cat $DF/cur_freq 2>/dev/null)"; }
stamp() { while IFS= read -r l; do echo "$(date +%s.%N | cut -c1-14) $l"; done; }
echo "# run25 start $(date -Is) uid=$(id -u) $(st) thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo)" >> meta.log
: > expH2.log
for rep in 1 2 3 4; do
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
    echo "## rep=$rep hold_mb=$hold start=$(date +%s.%N | cut -c1-14) $(st) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo) free blocks by order: $(grep Normal /proc/buddyinfo | tr -s ' ' | cut -d' ' -f5-)" >> expH2.log
    echo "P pre rep=$rep hold_mb=$hold $(CHASE_UNROLL=1 taskset -c 0 ./probe3 seq 8 256 64 $E 1 $rep 2>/dev/null)" >> expH2.log
    taskset -c 0 ./nothp ./lat_mem_rd -P 1 64 256 2>&1 | stamp >> expH2.log
    echo "P post rep=$rep hold_mb=$hold $(CHASE_UNROLL=1 taskset -c 0 ./probe3 seq 8 256 64 $E 1 $rep 2>/dev/null)" >> expH2.log
    echo "## end rep=$rep hold_mb=$hold $(st)" >> expH2.log
    [ -n "$pid" ] && kill -KILL $pid
    wait 2>/dev/null
  done
done
echo "# run25 done $(date -Is) $(st) loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> meta.log
