#!/bin/sh
# Exp Y: does the layout effect (same pages in physically sorted against
# shuffled virtual order) exist at stride 64 as it does at stride 256?
# frames2 with lmbench's loop body (CHASE_UNROLL=1), 8 MB, physically adjacent
# pages (pick low), strides 64, 128, 256, 512 and 1024.
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 5 minutes.
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a,3,5
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
echo "# run15 start $(date -Is) uid=$(id -u) $(st)" >> meta.log
: > expY.log
rep=0
for stride in 64 128 256 512 1024; do
  for order in sorted shuffled; do
    rep=$((rep + 1))
    echo "## rep=$rep size_mb=8 pick=low order=$order mode=seq$stride unroll=1 $(date -Is) $(st)" >> expY.log
    CHASE_UNROLL=1 taskset -c 0 ./frames2 8 3072 $E 37 low - seq$stride $order >> expY.log 2>&1
  done
done
echo "# run15 done $(date -Is) $(st)" >> meta.log
