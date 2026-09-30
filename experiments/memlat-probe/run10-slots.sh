#!/bin/sh
# Exp S: random-access latency by 1 GiB physical slot, in one boot and one mode.
# Root (pagemap PFNs), cpu0.  Changes no system setting.  About 6 minutes.
# Expects ./frames2 next to this script.
#
# Each frames2 run allocates a 3 GiB pool of 4 KiB pages (released when it
# exits) and measures the lmbench random chase on 32 MB taken from each GiB
# slot that holds enough pool pages, twice per slot (the second time after
# moving the same pages to a new virtual range).
cd "$(dirname "$0")" || exit 1
DF=/sys/class/devfreq/nocfreq
E=11,2d,17,2a,3,5
st() { echo "noc_gov=$(cat $DF/governor 2>/dev/null) noc_freq=$(cat $DF/cur_freq 2>/dev/null) loadavg=$(cut -d' ' -f1-3 /proc/loadavg) memfree_kb=$(awk '/MemFree/{print $2}' /proc/meminfo) memavail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; }
echo "# run10 start $(date -Is) uid=$(id -u) $(st)" >> meta.log
: > expS.log
for rep in 1 2 3; do
  echo "## rep=$rep size_mb=32 pick=low $(date -Is) $(st)" >> expS.log
  taskset -c 0 ./frames2 32 3072 $E $((rep * 17)) low >> expS.log 2>&1
done
echo "## rep=4 size_mb=32 pick=even $(date -Is) $(st)" >> expS.log
taskset -c 0 ./frames2 32 3072 $E 5 even >> expS.log 2>&1
echo "## rep=5 size_mb=64 pick=low $(date -Is) $(st)" >> expS.log
taskset -c 0 ./frames2 64 3072 $E 7 low >> expS.log 2>&1
echo "# run10 done $(date -Is) $(st)" >> meta.log
